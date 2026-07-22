from __future__ import annotations

import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from parsers.gradle import GradleDep, _is_prerelease, find_accessible_version
from parsers.gradle_tree import resolve_transitive_with_gradle
from resolver.resolver import select_best_version
from shared.maven_version import MavenVersion
from shared.utils import ProgressBar

_RES_STRATEGY_RE = re.compile(
    r"(configurations\.all\s*\{[^}]*?resolutionStrategy\s*\{)",
    re.DOTALL,
)


_SPRING_FRAMEWORK_MODULES = {
    "org.springframework:spring-aop",
    "org.springframework:spring-beans",
    "org.springframework:spring-context",
    "org.springframework:spring-context-support",
    "org.springframework:spring-core",
    "org.springframework:spring-expression",
    "org.springframework:spring-jcl",
    "org.springframework:spring-messaging",
    "org.springframework:spring-oxm",
    "org.springframework:spring-tx",
    "org.springframework:spring-web",
    "org.springframework:spring-webflux",
    "org.springframework:spring-webmvc",
}

_SPRING_FRAMEWORK_PROP_RE = re.compile(
    r"set\('spring-framework\.version',\s*\"(?P<version>[^\"]+)\"\)"
)


_DIRECT_DEP_CONFIGS = (
    "implementation|api|compileOnly|runtimeOnly|annotationProcessor|"
    "testImplementation|testRuntimeOnly|testCompileOnly"
)


def _versionless_direct_dependencies(build_text):
    result = set()

    configs = _DIRECT_DEP_CONFIGS

    quoted = re.compile(r"\b(" + configs + r")\s+(['\"])([^:'\"]+):([^:'\"]+)\2")
    for m in quoted.finditer(build_text or ""):
        result.add(m.group(3) + ":" + m.group(4))

    mapped = re.compile(
        r"\b(" + configs + r")\s*\(\s*"
        r"group\s*:\s*(['\"])(.*?)\2\s*,\s*"
        r"name\s*:\s*(['\"])(.*?)\4",
        re.DOTALL,
    )
    for m in mapped.finditer(build_text or ""):
        result.add(m.group(3) + ":" + m.group(5))
    return result


def _prefer_stable_versions(
    versions: list[MavenVersion],
) -> list[MavenVersion]:
    """Prefer stable releases, retaining previews only when no stable release exists."""
    stable = [version for version in versions if not _is_prerelease(version)]
    return stable or list(versions)


def apply_updates(
    deps: list[GradleDep],
    remediation_by_key: dict[str, set[MavenVersion]],
    available_by_key: dict[str, list[MavenVersion]],
    package_constraints: dict[str, str],
    installed: dict[str, MavenVersion],
    parents_of: dict[str, set[str]],
    build_file: str,
    base_url: str,
    auth: tuple[str, str] | None,
    gradle_cmd: str,
    timeout: int,
    skip_block_check: bool,
    show_progress: bool,
    xray_host: str | None = None,
    workers: int = 8,
    repo_urls: list[str] | None = None,
    log_dir: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Returns (changes, skipped, force_entries).

    changes       — direct dep version updates
    skipped       — packages not updated with reason
    force_entries — [{"dependency", "old_version", "new_version", "minimum_required"}]
                    written as resolutionStrategy.force lines
    """
    direct_by_key: dict[str, GradleDep] = {f"{d.group}:{d.artifact}": d for d in deps}
    direct_occurrences_by_key: dict[str, list[GradleDep]] = {}
    for d in deps:
        direct_occurrences_by_key.setdefault(f"{d.group}:{d.artifact}", []).append(d)
    all_criteria_keys: set[str] = set(remediation_by_key.keys()) | set(package_constraints.keys())

    try:
        build_text_for_strategy = Path(build_file).read_text(encoding="utf-8") if build_file else ""
    except Exception:
        build_text_for_strategy = ""
    versionless_direct_keys = _versionless_direct_dependencies(build_text_for_strategy)

    changes: list[dict] = []
    skipped: list[dict] = []
    force_entries: list[dict] = []
    progress = ProgressBar(len(all_criteria_keys), "Applying updates", enabled=show_progress)

    lock = threading.Lock()
    spring_framework_property_updated = [False]

    def _process_one(key_orig: str) -> tuple[list, list, list]:
        kc: list[dict] = []
        ks: list[dict] = []
        kf: list[dict] = []
        key = key_orig

        remediation_versions: set[MavenVersion] = set()
        for lookup in (key, key.split(":")[-1]):
            remediation_versions.update(remediation_by_key.get(lookup, set()))

        if ":" not in key:
            for full in list(direct_by_key) + list(installed) + list(versionless_direct_keys):
                if full.split(":")[-1] == key:
                    key = full
                    break

        artifact_key = key.split(":")[-1]
        available = _prefer_stable_versions(
            available_by_key.get(key, available_by_key.get(artifact_key, []))
        )
        constraint = package_constraints.get(key, package_constraints.get(artifact_key, ">="))

        if key in direct_by_key:
            dep = direct_by_key[key]
            current = MavenVersion.parse(dep.version)
            if current is None:
                ks.append({"dependency": key, "reason": "unparseable version", "current": dep.version, "target": ""})
                return kc, ks, kf
        else:
            current = installed.get(key)
            if current is None:
                if available:
                    target = max(available)
                    kf.append({"dependency": key, "old_version": "", "new_version": str(target), "minimum_required": str(target)})
                    return kc, ks, kf
                ks.append({"dependency": key, "reason": "package was reported by JFrog but no resolved version or available Artifactory versions were found", "current": "", "target": ""})
                return kc, ks, kf

        target = select_best_version(remediation_versions, available, current.major, constraint, current)
        if target is None:
            remediation_for_current_major = [v for v in remediation_versions if v.major == current.major]
            if remediation_for_current_major:
                target = max(remediation_for_current_major)
            else:
                same_major_updates = sorted(
                    (v for v in available if v.major == current.major and v > current),
                    reverse=True,
                )
                if key in direct_by_key and same_major_updates:
                    dep_for_access = direct_by_key[key]
                    if skip_block_check:
                        target = same_major_updates[0]
                    else:
                        for candidate in same_major_updates:
                            accessible = find_accessible_version(
                                dep_for_access.group, dep_for_access.artifact,
                                candidate, [candidate], base_url, auth, timeout,
                                xray_host=xray_host, repo_urls=repo_urls,
                                log_dir=log_dir,
                            )
                            if accessible:
                                target = candidate
                                break
                elif same_major_updates:
                    target = same_major_updates[0]

                if target is None:
                    ks.append({"dependency": key, "reason": "no fixed versions for current major and no accessible same-major update found", "current": str(current), "target": ""})
                    return kc, ks, kf

        already_ok = (current > target) if constraint == ">" else (current >= target)
        if already_ok:
            ks.append({"dependency": key, "reason": "current version already meets remediation target", "current": str(current), "target": str(target)})
            return kc, ks, kf

        # Confirm target is actually reachable in Artifactory before doing
        # anything expensive with it — a real Gradle build (Case 1/2's build
        # validation), or Case 2's own per-candidate Gradle probe. A blocked
        # target used to only surface reactively, after a full build already
        # ran and hit a 403; a single HTTP check here is far cheaper, and it
        # means Case 2/3 never force/probe a version already known blocked.
        if not skip_block_check and ":" in key:
            group, artifact = key.split(":", 1)
            accessible_target = find_accessible_version(
                group, artifact, target, available, base_url, auth, timeout,
                xray_host=xray_host, repo_urls=repo_urls, log_dir=log_dir,
            )
            if accessible_target is None:
                ks.append({"dependency": key, "reason": "no accessible version found >= target", "current": str(current), "target": str(target)})
                return kc, ks, kf
            target = MavenVersion.parse(accessible_target) or target

        if key in versionless_direct_keys and key not in direct_by_key:
            kf.append({"dependency": key, "old_version": str(current), "new_version": str(target), "minimum_required": str(target)})
            return kc, ks, kf

        if key in _SPRING_FRAMEWORK_MODULES and key not in direct_by_key:
            m = _SPRING_FRAMEWORK_PROP_RE.search(build_text_for_strategy)
            if m:
                prop_current = MavenVersion.parse(m.group("version"))
                if prop_current and target > prop_current:
                    with lock:
                        if not spring_framework_property_updated[0]:
                            original = m.group(0)
                            replacement = f"set('spring-framework.version', \"{target}\")"
                            kc.append({
                                "dependency": "org.springframework:spring-framework.version",
                                "config": "ext",
                                "old_version": str(prop_current),
                                "new_version": str(target),
                                "remediation_guided": f"transitive {key}>={target}",
                                "original": original,
                                "replacement": replacement,
                            })
                            spring_framework_property_updated[0] = True
                elif prop_current and prop_current >= target:
                    ks.append({"dependency": key, "reason": "spring-framework.version already meets remediation target", "current": str(current), "target": str(target)})
            return kc, ks, kf

        # -----------------------------------------------------------------
        # Case 1: direct dependency — update version in build.gradle
        # -----------------------------------------------------------------
        if key in direct_by_key:
            dep = direct_by_key[key]
            # Already confirmed accessible above (unless skip_block_check).
            final = str(target)

            # A build.gradle can declare the same group:artifact more than
            # once (e.g. two identical strict-version blocks at different
            # locations). direct_by_key only keeps one representative entry
            # per key, so iterate every parsed occurrence here -- otherwise
            # only the first textual occurrence gets patched and the rest
            # stay at the vulnerable version even though the pipeline
            # believes the package was fixed.
            occurrences = direct_occurrences_by_key.get(key, [dep])
            changed_any = False
            for occurrence in occurrences:
                if occurrence.version == final:
                    continue
                new_decl = occurrence.original.replace(occurrence.version, final, 1)
                kc.append({
                    "dependency": key,
                    "config": occurrence.config,
                    "old_version": occurrence.version,
                    "new_version": final,
                    "remediation_guided": "yes",
                    "original": occurrence.original,
                    "replacement": new_decl,
                })
                changed_any = True

            if not changed_any:
                ks.append({"dependency": key, "reason": "selected version equals current", "current": str(current), "target": ""})
            return kc, ks, kf

        # -----------------------------------------------------------------
        # Case 2: transitive — try updating a direct parent first
        # -----------------------------------------------------------------
        direct_parents = parents_of.get(key, set())
        if not direct_parents:
            kf.append({"dependency": key, "old_version": str(current), "new_version": str(target), "minimum_required": str(target)})
            return kc, ks, kf

        project_dir = os.path.dirname(os.path.abspath(build_file))
        did_parent_update = False
        case2_start = time.perf_counter()
        gradle_probe_count = 0

        # Each candidate here costs a full cold `--no-daemon` gradle
        # dependencies subprocess in a fresh temp-directory project copy
        # (resolve_transitive_with_gradle), not a cheap HTTP probe -- and a
        # per-parent cap alone wasn't enough: a transitive key with several
        # direct parents (e.g. jackson-databind pulled in independently by
        # multiple unrelated top-level dependencies) got a full budget for
        # *each* parent, multiplying probes back up. Confirmed live across a
        # real batch: 275 Case 2 searches sampled, 0 ever succeeded, ~213
        # minutes total, ~40-60s per probe (up to 372s for one package at 9
        # probes). Candidates are already tried highest-version-first, and
        # Gradle's default "highest version wins" conflict resolution means
        # if the highest available parent version doesn't satisfy the
        # target, a lower same-major version essentially never will either
        # -- so trying more than one candidate bought nothing in this data.
        # Bound the *total* probes across every parent for this key, not per
        # parent, to 1: the single best shot, at roughly a minute instead of
        # several.
        _CASE2_MAX_TOTAL_PROBES = 1

        for parent_key in sorted(direct_parents):
            if gradle_probe_count >= _CASE2_MAX_TOTAL_PROBES:
                break
            if parent_key not in direct_by_key:
                continue
            if parent_key in all_criteria_keys:
                continue

            parent_dep = direct_by_key[parent_key]
            parent_current = MavenVersion.parse(parent_dep.version)
            if not parent_current:
                continue

            parent_avail = _prefer_stable_versions(
                available_by_key.get(parent_key, [])
            )
            remaining_budget = _CASE2_MAX_TOTAL_PROBES - gradle_probe_count
            candidates = sorted(
                (
                    version
                    for version in parent_avail
                    if version.major == parent_current.major
                    and version > parent_current
                ),
                reverse=True,
            )[:remaining_budget]
            if not candidates:
                continue

            for ptarget in candidates:
                gradle_probe_count += 1
                resolved = resolve_transitive_with_gradle(
                    parent_key,
                    str(ptarget),
                    key,
                    project_dir,
                    build_file,
                    gradle_cmd,
                    timeout,
                )
                if resolved is None:
                    continue

                satisfied = resolved >= target
                if not satisfied:
                    continue

                new_decl = parent_dep.original.replace(
                    parent_dep.version,
                    str(ptarget),
                    1,
                )
                kc.append(
                    {
                        "dependency": parent_key,
                        "config": parent_dep.config,
                        "old_version": parent_dep.version,
                        "new_version": str(ptarget),
                        "remediation_guided": f"transitive {key}>={target}",
                        "original": parent_dep.original,
                        "replacement": new_decl,
                    }
                )
                did_parent_update = True
                break

            if did_parent_update:
                break

        from shared.build_validation import _dbg

        _dbg(
            log_dir,
            f"[perf] transitive-parent search ({key}) ran {gradle_probe_count} "
            f"gradle probe(s) in {time.perf_counter() - case2_start:.2f}s "
            f"(resolved={did_parent_update})",
        )
        if did_parent_update:
            return kc, ks, kf

        # -----------------------------------------------------------------
        # Case 3: no parent update fixed it — add resolutionStrategy.force
        # -----------------------------------------------------------------
        kf.append({"dependency": key, "old_version": str(current), "new_version": str(target), "minimum_required": str(target)})
        return kc, ks, kf

    max_workers = min(workers, len(all_criteria_keys) or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_one, key): key for key in sorted(all_criteria_keys)}
        for future in as_completed(futures):
            kc, ks, kf = future.result()
            with lock:
                progress.update()
                changes.extend(kc)
                skipped.extend(ks)
                force_entries.extend(kf)

    force_entries.extend(
        _sibling_family_forces(changes, force_entries, installed, available_by_key)
    )
    changes.extend(
        _align_competing_pins(build_text_for_strategy, changes, force_entries)
    )

    return changes, skipped, force_entries


_EXISTING_FORCE_LINE_RE = re.compile(
    r"""force\s*\(?\s*(['"])([^'"$]+):([^'"$]+):([^'"$]+)\1(?:\s*\))?"""
)


def _align_competing_pins(
    build_text: str,
    changes: list[dict],
    force_entries: list[dict],
) -> list[dict]:
    """Rewrite pre-existing pins that would silently defeat this run's updates.

    Projects accumulate pins from earlier manual CVE fixes — resolutionStrategy
    `force 'g:a:v'` lines and `version { strictly 'v' }` constraints. Both
    outrank the Spring Boot BOM version properties and the force entries this
    pipeline writes, so an update routed through either mechanism silently
    loses to the stale pin: the flagged artifact moves but its pinned family
    sibling stays behind, and the resulting mixed-version classpath fails the
    build in a way isolation can't attribute. Returned rows carry
    original/replacement like any direct change, so writing, reporting, and
    rollback all treat them uniformly.
    """
    from parsers.gradle import parse_gradle_deps

    targets: dict[str, str] = {}
    for row in list(changes) + list(force_entries):
        dependency = row.get("dependency", "")
        new_version = row.get("new_version", "")
        if dependency and new_version:
            targets.setdefault(dependency, new_version)

    handled_originals = {row.get("original") for row in changes}
    rows: list[dict] = []

    # Declarations (including `strictly` blocks) still pinned to another version.
    for dep in parse_gradle_deps(build_text):
        key = f"{dep.group}:{dep.artifact}"
        target = targets.get(key)
        if not target or dep.version == target or "$" in dep.version:
            continue
        if dep.original in handled_originals:
            continue
        rows.append({
            "dependency": key,
            "config": dep.config,
            "old_version": dep.version,
            "new_version": target,
            "remediation_guided": "competing pin realigned",
            "original": dep.original,
            "replacement": dep.original.replace(dep.version, target, 1),
        })
        handled_originals.add(dep.original)

    # Pre-existing resolutionStrategy force lines pinning an old version.
    for match in _EXISTING_FORCE_LINE_RE.finditer(build_text):
        key = f"{match.group(2)}:{match.group(3)}"
        old_version = match.group(4)
        target = targets.get(key)
        if not target or old_version == target:
            continue
        original = match.group(0)
        if original in handled_originals:
            continue
        rows.append({
            "dependency": key,
            "config": "force",
            "old_version": old_version,
            "new_version": target,
            "remediation_guided": "competing pin realigned",
            "original": original,
            "replacement": original.replace(f"{key}:{old_version}", f"{key}:{target}", 1),
        })
        handled_originals.add(original)

    return rows


def _sibling_family_forces(
    changes: list[dict],
    force_entries: list[dict],
    installed: dict[str, MavenVersion],
    available_by_key: dict[str, list[MavenVersion]],
) -> list[dict]:
    """Keep version-locked dependency families (Netty, Spring, Jackson, ...) consistent.

    JFrog often flags only one artifact within a family whose members must all
    share an identical version (e.g. io.netty:netty-* or org.springframework:*).
    Bumping just that artifact via resolutionStrategy.force while its siblings
    stay on the old version reliably breaks compilation, and the resulting
    failure never implicates the changed artifact, so isolation can't recover
    it.

    Family membership is not a hardcoded prefix list: any other artifact
    sharing the same Maven groupId that is *currently at the exact same
    resolved version* as the artifact being changed is treated as locked to
    it and forced to match. Same-group artifacts already sitting on a
    different version are left untouched — a group like org.apache.commons
    bundles several independently-versioned artifacts (commons-lang3,
    commons-io, commons-collections4, ...), and the only reliable signal
    that two artifacts are actually part of one BOM-locked release train is
    that they already move in lockstep today.
    """
    handled_keys = {entry["dependency"] for entry in changes}
    handled_keys.update(entry["dependency"] for entry in force_entries)

    sibling_forces: dict[str, dict] = {}
    for entry in list(changes) + list(force_entries):
        dependency = entry["dependency"]
        group_prefix = dependency.split(":", 1)[0] + ":"
        old_version = MavenVersion.parse(entry.get("old_version", ""))
        target_version = MavenVersion.parse(entry["new_version"])
        if old_version is None or target_version is None:
            continue

        for sibling_key, sibling_version in installed.items():
            if sibling_key == dependency or not sibling_key.startswith(group_prefix):
                continue
            if sibling_key in handled_keys or sibling_key in sibling_forces:
                continue
            if sibling_version != old_version:
                continue

            # The trigger's exact version string doesn't necessarily exist for
            # every sibling -- Jackson's own annotations module releases on a
            # coarser cadence than databind/core (no patch digit some minors),
            # so stamping databind's "2.22.1" onto jackson-annotations forced a
            # version that was never published. Gradle can't resolve it
            # ("jackson-annotations:2.22.1 FAILED" in the tree, confirmed live)
            # and the real build never gets far enough to blame the actual
            # cause. Only force to a version confirmed to exist for THIS
            # sibling; fall back to the closest existing one below the
            # trigger's target, and skip forcing entirely if none exists.
            sibling_available = available_by_key.get(sibling_key, [])
            if target_version in sibling_available:
                resolved_target = target_version
            else:
                lower_candidates = [
                    v for v in sibling_available if old_version < v <= target_version
                ]
                resolved_target = max(lower_candidates) if lower_candidates else None
            if resolved_target is None:
                continue

            sibling_forces[sibling_key] = {
                "dependency": sibling_key,
                "old_version": str(sibling_version),
                "new_version": str(resolved_target),
                "minimum_required": str(resolved_target),
                "remediation_guided": f"version-locked sibling of {dependency}",
            }

    return list(sibling_forces.values())


def _find_block_end(text: str, open_brace: int) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    i = open_brace
    while i < len(text):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        else:
            if ch in ("'", '"'):
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return len(text)


def _top_level_block_end(text: str, name: str) -> int | None:
    pattern = re.compile(r"(?m)^\s*" + re.escape(name) + r"\s*\{")
    match = pattern.search(text)
    if not match:
        return None
    open_brace = text.find("{", match.start(), match.end())
    if open_brace < 0:
        return None
    return _find_block_end(text, open_brace)


def _insert_project_forces(build_text: str, project_block: str) -> str:
    insertion_points = [
        end
        for end in (
            _top_level_block_end(build_text, "plugins"),
            _top_level_block_end(build_text, "buildscript"),
        )
        if end is not None
    ]
    if insertion_points:
        insert_at = max(insertion_points)
        spacer = "\n\n" if not build_text[insert_at:].startswith("\n") else "\n"
        return build_text[:insert_at] + spacer + project_block + build_text[insert_at:]
    return project_block + build_text


_SPRING_BOOT_PLUGIN_RE = re.compile(
    r"""id\s*\(?\s*['"]org\.springframework\.boot['"]"""
)
_SPRING_DEPENDENCY_MANAGEMENT_PLUGIN_RE = re.compile(
    r"""id\s*\(?\s*['"]io\.spring\.dependency-management['"]"""
)

_SPRING_BOOT_MANAGED_FAMILIES = (
    ("org.springframework.kafka:", "spring-kafka.version"),
    ("org.springframework:", "spring-framework.version"),
    ("io.micrometer:", "micrometer.version"),
    ("io.netty:", "netty.version"),
    ("ch.qos.logback:", "logback.version"),
    ("org.apache.tomcat.embed:", "tomcat.version"),
    ("com.fasterxml.jackson.core:", "jackson-bom.version"),
    ("com.fasterxml.jackson.dataformat:", "jackson-bom.version"),
    ("com.fasterxml.jackson.datatype:", "jackson-bom.version"),
    ("com.fasterxml.jackson.module:", "jackson-bom.version"),
    ("com.fasterxml.jackson:", "jackson-bom.version"),
)
def is_spring_boot_managed_project(build_text):
    return bool(
        _SPRING_BOOT_PLUGIN_RE.search(build_text or "")
        and _SPRING_DEPENDENCY_MANAGEMENT_PLUGIN_RE.search(
            build_text or ""
        )
    )


def spring_boot_managed_property(dependency):
    dependency = str(dependency or "")

    for prefix, property_name in _SPRING_BOOT_MANAGED_FAMILIES:
        if dependency.startswith(prefix):
            return property_name

    return None


_SPRING_BOOT_GROUP_PREFIX = "org.springframework.boot:"
_SPRING_BOOT_PLUGIN_VERSION_RE = re.compile(
    r"""(id\s*\(?\s*['"]org\.springframework\.boot['"]\)?\s*version\s*['"])[^'"]+(['"])"""
)


def write_spring_boot_plugin_version(build_text, force_entries):
    """org.springframework.boot:* artifacts (the platform itself — spring-boot,
    spring-boot-starter-*, spring-boot-autoconfigure, ...) are version-pinned
    by the Spring Boot Gradle plugin declaration via the
    io.spring.dependency-management BOM import, not by resolutionStrategy.force.
    force is silently ineffective against them: confirmed live, forcing
    spring-boot-starter-* 3.5.13 -> 3.5.16 left the resolved dependency tree
    (and the CVE it targeted) unchanged at 3.5.13. Rewrite the plugin's own
    version instead and drop those entries from the forces list, since a
    force for them would be a no-op; falls back to leaving forces untouched
    if the plugin version isn't declared in the expected literal form.
    """
    if not is_spring_boot_managed_project(build_text):
        return build_text, list(force_entries or [])

    boot_versions = [
        entry.get("new_version", "")
        for entry in force_entries or []
        if str(entry.get("dependency", "")).startswith(_SPRING_BOOT_GROUP_PREFIX)
    ]
    if not boot_versions:
        return build_text, list(force_entries or [])

    target_version = _preferred_property_version(boot_versions)
    if not target_version:
        return build_text, list(force_entries or [])

    new_text, count = _SPRING_BOOT_PLUGIN_VERSION_RE.subn(
        lambda m: f"{m.group(1)}{target_version}{m.group(2)}",
        build_text,
        count=1,
    )
    if not count:
        return build_text, list(force_entries or [])

    remaining_forces = [
        entry
        for entry in force_entries or []
        if not str(entry.get("dependency", "")).startswith(_SPRING_BOOT_GROUP_PREFIX)
    ]
    return new_text, remaining_forces


def _find_named_block(build_text, block_name):
    match = re.search(
        r"(?m)^\s*" + re.escape(block_name) + r"\s*\{",
        build_text,
    )
    if not match:
        return None

    open_brace = build_text.find(
        "{",
        match.start(),
        match.end(),
    )
    if open_brace < 0:
        return None

    close_index = _find_block_end(build_text, open_brace)
    if close_index <= open_brace:
        return None

    return match.start(), open_brace, close_index


def _preferred_property_version(versions):
    parsed = []

    for version in versions:
        parsed_version = MavenVersion.parse(str(version))
        if parsed_version is not None:
            parsed.append(parsed_version)

    if parsed:
        return str(max(parsed))

    raw_versions = [
        str(version)
        for version in versions
        if str(version or "").strip()
    ]
    return max(raw_versions) if raw_versions else ""


def write_spring_boot_managed_properties(
    build_text,
    force_entries,
):
    """Write Spring Boot BOM overrides and return remaining normal forces."""
    if not is_spring_boot_managed_project(build_text):
        return build_text, list(force_entries or [])

    managed_versions = {}
    remaining_forces = []

    for entry in force_entries or []:
        property_name = spring_boot_managed_property(
            entry.get("dependency", "")
        )
        if property_name is None:
            remaining_forces.append(entry)
            continue

        managed_versions.setdefault(property_name, []).append(
            entry.get("new_version", "")
        )

    if not managed_versions:
        return build_text, remaining_forces

    selected_versions = {
        property_name: _preferred_property_version(versions)
        for property_name, versions in managed_versions.items()
    }

    # Remove old values for properties this run controls. This supports both
    # set('name', "version") and ext['name'] = 'version' declarations.
    for property_name in selected_versions:
        build_text = re.sub(
            r"(?m)^\s*set\(\s*['\"]"
            + re.escape(property_name)
            + r"['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)\s*$\n?",
            "",
            build_text,
        )
        build_text = re.sub(
            r"(?m)^\s*ext\[\s*['\"]"
            + re.escape(property_name)
            + r"['\"]\s*\]\s*=\s*['\"][^'\"]+['\"]\s*$\n?",
            "",
            build_text,
        )

    property_lines = "".join(
        f"    set('{property_name}', \"{version}\")\n"
        for property_name, version in sorted(
            selected_versions.items()
        )
        if version
    )

    ext_block = _find_named_block(build_text, "ext")

    if ext_block is not None:
        _, _, close_index = ext_block
        closing_brace = close_index - 1
        build_text = (
            build_text[:closing_brace]
            + property_lines
            + build_text[closing_brace:]
        )
    else:
        ext_text = "ext {\n" + property_lines + "}\n\n"
        insertion_point = _top_level_block_end(
            build_text,
            "plugins",
        )
        if insertion_point is None:
            build_text = ext_text + build_text
        else:
            build_text = (
                build_text[:insertion_point]
                + "\n\n"
                + ext_text
                + build_text[insertion_point:]
            )

    return build_text, remaining_forces


def write_resolution_forces(build_text: str, forces: list[dict]) -> str:
    """Insert resolutionStrategy.force entries into build_text.

    Forces are written in both places Gradle can need them:
    - buildscript configurations for classpath/plugin artifacts
    - project configurations for compile/runtime artifacts

    Always add a new project-level configurations.all block instead of trying to
    merge into an existing one. Some legacy build.gradle files have compact or
    non-standard formatting that makes safely identifying scope-sensitive
    existing blocks unreliable, and duplicate resolutionStrategy.force entries
    are safer than missing the force entirely.
    """
    if not forces:
        return build_text

    force_lines = "\n".join(
        f"            force '{f['dependency']}:{f['new_version']}'" for f in forces
    )

    buildscript_snippet = (
        "\n    configurations.all {\n"
        "        resolutionStrategy {\n"
        f"{force_lines}\n"
        "        }\n"
        "    }\n"
    )

    buildscript_match = re.search(r"buildscript\s*\{", build_text)
    if buildscript_match:
        build_text = (
            build_text[: buildscript_match.end()]
            + buildscript_snippet
            + build_text[buildscript_match.end() :]
        )

    project_block = (
        "configurations.all {\n"
        "    resolutionStrategy {\n"
        f"{force_lines}\n"
        "    }\n"
        "}\n"
    )
    return _insert_project_forces(build_text, project_block).rstrip() + "\n"


def write_dependency_substitutions(build_text: str, forces: list[dict]) -> str:
    """Insert dependencySubstitution blocks for packages that resolutionStrategy.force
    cannot override (e.g. Gradle Module Metadata strict version constraints).

    dependencySubstitution runs before version conflict resolution, substituting the
    entire module reference before strict constraints from component metadata are applied.
    """
    if not forces:
        return build_text

    sub_lines = "\n".join(
        f"        substitute module('{f['dependency']}') "
        f"using module('{f['dependency']}:{f['new_version']}')"
        for f in forces
    )

    project_block = (
        "configurations.all {\n"
        "    resolutionStrategy.dependencySubstitution {\n"
        f"{sub_lines}\n"
        "    }\n"
        "}\n"
    )
    return _insert_project_forces(build_text, project_block).rstrip() + "\n"


def write_gradle_file(
    build_text,
    changes,
    force_entries,
    output_path,
    source_path,
    in_place,
):
    updated_text = build_text

    for change in changes:
        updated_text = updated_text.replace(
            change["original"],
            change["replacement"],
            1,
        )

    updated_text, remaining_forces = write_spring_boot_plugin_version(
        updated_text,
        force_entries,
    )
    updated_text, remaining_forces = (
        write_spring_boot_managed_properties(
            updated_text,
            remaining_forces,
        )
    )
    updated_text = write_resolution_forces(
        updated_text,
        remaining_forces,
    )

    # Spring dependency-management rules can override resolutionStrategy.force
    # for BOM-managed Spring Data modules. Dependency substitution runs before
    # those selection rules, while retaining the force as a compatibility
    # fallback for configurations where it is effective.
    substitution_forces = [
        entry
        for entry in remaining_forces
        if str(entry.get("dependency", "")).startswith(
            "org.springframework.data:"
        )
    ]
    updated_text = write_dependency_substitutions(
        updated_text,
        substitution_forces,
    )

    if in_place:
        backup_path = source_path + ".bak"

        if not os.path.exists(backup_path):
            Path(backup_path).write_text(
                build_text,
                encoding="utf-8",
            )
            print(f"Backup: {backup_path}")
        else:
            print(
                "Backup already exists, not overwritten: "
                f"{backup_path}"
            )

        Path(source_path).write_text(
            updated_text,
            encoding="utf-8",
        )
        print(f"Updated in place: {source_path}")
    else:
        Path(output_path).write_text(
            updated_text,
            encoding="utf-8",
        )
        print(f"Output: {output_path}")

