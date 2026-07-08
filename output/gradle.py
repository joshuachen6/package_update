from __future__ import annotations

import os
import re
from pathlib import Path

from parsers.gradle import GradleDep, find_accessible_version
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


def apply_updates(
    deps: list[GradleDep],
    ado_by_key: dict[str, set[MavenVersion]],
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
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Returns (changes, skipped, force_entries).

    changes       — direct dep version updates
    skipped       — packages not updated with reason
    force_entries — [{"dependency", "old_version", "new_version", "minimum_required"}]
                    written as resolutionStrategy.force lines
    """
    direct_by_key: dict[str, GradleDep] = {f"{d.group}:{d.artifact}": d for d in deps}
    all_criteria_keys: set[str] = set(ado_by_key.keys()) | set(package_constraints.keys())

    try:
        build_text_for_strategy = Path(build_file).read_text(encoding="utf-8") if build_file else ""
    except Exception:
        build_text_for_strategy = ""
    versionless_direct_keys = _versionless_direct_dependencies(build_text_for_strategy)

    changes: list[dict] = []
    skipped: list[dict] = []
    force_entries: list[dict] = []
    progress = ProgressBar(len(all_criteria_keys), "Applying updates", enabled=show_progress)
    try:
        build_text_for_strategy = Path(build_file).read_text(encoding="utf-8") if build_file else ""
    except Exception:
        build_text_for_strategy = ""
    spring_framework_property_updated = False

    for key in sorted(all_criteria_keys):
        progress.update()

        ado_versions: set[MavenVersion] = set()
        for lookup in (key, key.split(":")[-1]):
            ado_versions.update(ado_by_key.get(lookup, set()))
        # If Claude identified a package from an ADO task that did not include an
        # explicit fixed version, ado_versions can be empty. Keep processing so
        # the no-current-major fallback below can try the latest accessible
        # same-major version from Artifactory/JFrog.

        # Resolve artifact-only key to full group:artifact form for dep/version lookups
        if ":" not in key:
            for full in list(direct_by_key) + list(installed) + list(versionless_direct_keys):
                if full.split(":")[-1] == key:
                    key = full
                    break

        artifact_key = key.split(":")[-1]
        available = available_by_key.get(key, available_by_key.get(artifact_key, []))
        constraint = package_constraints.get(key, package_constraints.get(artifact_key, ">="))

        if key in direct_by_key:
            dep = direct_by_key[key]
            current = MavenVersion.parse(dep.version)
            if current is None:
                skipped.append(
                    {
                        "dependency": key,
                        "reason": "unparseable version",
                        "current": dep.version,
                        "target": "",
                    }
                )
                continue
        else:
            current = installed.get(key)
            if current is None:
                if key in versionless_direct_keys:
                    skipped.append(
                        {
                            "dependency": key,
                            "reason": "direct dependency is version-managed but was not found in resolved dependency tree",
                            "current": "",
                            "target": "",
                        }
                    )
                else:
                    skipped.append(
                        {
                            "dependency": key,
                            "reason": "not found in build file or dependency tree",
                            "current": "",
                            "target": "",
                        }
                    )
                continue

        target = select_best_version(ado_versions, available, current.major, constraint, current)
        if target is None:
            ado_for_current_major = [v for v in ado_versions if v.major == current.major]
            if ado_for_current_major:
                target = max(ado_for_current_major)
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
                            try:
                                accessible = find_accessible_version(
                                    dep_for_access.group,
                                    dep_for_access.artifact,
                                    candidate,
                                    [candidate],
                                    base_url,
                                    auth,
                                    timeout,
                                    xray_host=xray_host,
                                )
                            except TypeError:
                                accessible = find_accessible_version(
                                    dep_for_access.group,
                                    dep_for_access.artifact,
                                    candidate,
                                    [candidate],
                                    base_url,
                                    auth,
                                    timeout,
                                )
                            if accessible:
                                target = candidate
                                break
                elif same_major_updates:
                    target = same_major_updates[0]

                if target is None:
                    skipped.append(
                        {
                            "dependency": key,
                            "reason": "no ADO versions for current major and no accessible same-major update found",
                            "current": str(current),
                            "target": "",
                        }
                    )
                    continue

        already_ok = (current > target) if constraint == ">" else (current >= target)
        if already_ok:
            skipped.append(
                {
                    "dependency": key,
                    "reason": "current version already meets ADO target",
                    "current": str(current),
                    "target": str(target),
                }
            )
            continue

        if key in versionless_direct_keys and key not in direct_by_key:
            skipped.append(
                {
                    "dependency": key,
                    "reason": "direct dependency is version-managed; no inline version to update",
                    "current": str(current),
                    "target": str(target),
                }
            )
            continue
        # Prefer Spring dependency-management property over forcing individual
        # Spring Framework modules such as spring-web or spring-webflux, but only
        # when the ADO package itself is a Spring Framework module. Version-managed
        # direct dependencies such as spring-boot-starter-webflux must stay skipped
        # instead of producing an unrelated spring-framework.version change.
        if key in _SPRING_FRAMEWORK_MODULES and key not in direct_by_key:
            m = _SPRING_FRAMEWORK_PROP_RE.search(build_text_for_strategy)
            if m:
                prop_current = MavenVersion.parse(m.group("version"))
                if prop_current and target > prop_current and not spring_framework_property_updated:
                    original = m.group(0)
                    replacement = f"set('spring-framework.version', \"{target}\")"
                    changes.append(
                        {
                            "dependency": "org.springframework:spring-framework.version",
                            "config": "ext",
                            "old_version": str(prop_current),
                            "new_version": str(target),
                            "ado_guided": f"transitive {key}>={target}",
                            "original": original,
                            "replacement": replacement,
                        }
                    )
                    spring_framework_property_updated = True
                elif prop_current and prop_current >= target:
                    skipped.append(
                        {
                            "dependency": key,
                            "reason": "spring-framework.version already meets ADO target",
                            "current": str(current),
                            "target": str(target),
                        }
                    )
                continue

        # -----------------------------------------------------------------
        # Case 1: direct dependency — update version in build.gradle
        # -----------------------------------------------------------------
        if key in direct_by_key:
            dep = direct_by_key[key]
            group, artifact = dep.group, dep.artifact

            if skip_block_check:
                final = str(target)
            else:
                try:
                    final = find_accessible_version(
                        group,
                        artifact,
                        target,
                        available,
                        base_url,
                        auth,
                        timeout,
                        xray_host=xray_host,
                    )
                except TypeError:
                    final = find_accessible_version(
                        group,
                        artifact,
                        target,
                        available,
                        base_url,
                        auth,
                        timeout,
                    )
                if final is None:
                    skipped.append(
                        {
                            "dependency": key,
                            "reason": "no accessible version found >= target",
                            "current": str(current),
                            "target": str(target),
                        }
                    )
                    continue

            if final == dep.version:
                skipped.append(
                    {
                        "dependency": key,
                        "reason": "selected version equals current",
                        "current": str(current),
                        "target": "",
                    }
                )
                continue

            new_decl = dep.original.replace(dep.version, final, 1)
            changes.append(
                {
                    "dependency": key,
                    "config": dep.config,
                    "old_version": dep.version,
                    "new_version": final,
                    "ado_guided": "yes",
                    "original": dep.original,
                    "replacement": new_decl,
                }
            )
            continue

        # -----------------------------------------------------------------
        # Case 2: transitive — try updating a direct parent first
        # -----------------------------------------------------------------
        direct_parents = parents_of.get(key, set())
        if not direct_parents:
            skipped.append(
                {
                    "dependency": key,
                    "reason": "transitive dep not found in dependency tree",
                    "current": str(current),
                    "target": str(target),
                }
            )
            continue

        project_dir = os.path.dirname(os.path.abspath(build_file))
        did_parent_update = False

        for parent_key in sorted(direct_parents):
            if parent_key not in direct_by_key:
                continue  # parent is itself transitive — can't update directly
            if parent_key in all_criteria_keys:
                continue  # parent already handled separately

            parent_dep = direct_by_key[parent_key]
            parent_current = MavenVersion.parse(parent_dep.version)
            if not parent_current:
                continue

            parent_avail = available_by_key.get(parent_key, [])
            candidates = sorted(
                v for v in parent_avail if v.major == parent_current.major and v > parent_current
            )
            if not candidates:
                continue

            ptarget = candidates[-1]
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

            satisfied = (resolved > target) if constraint == ">" else (resolved >= target)
            if not satisfied:
                continue

            new_decl = parent_dep.original.replace(parent_dep.version, str(ptarget), 1)
            changes.append(
                {
                    "dependency": parent_key,
                    "config": parent_dep.config,
                    "old_version": parent_dep.version,
                    "new_version": str(ptarget),
                    "ado_guided": f"transitive {key}>={target}",
                    "original": parent_dep.original,
                    "replacement": new_decl,
                }
            )
            did_parent_update = True
            break

        if did_parent_update:
            continue

        # -----------------------------------------------------------------
        # Case 3: no parent update fixed it — add resolutionStrategy.force
        # -----------------------------------------------------------------
        force_entries.append(
            {
                "dependency": key,
                "old_version": str(current),
                "new_version": str(target),
                "minimum_required": str(target),
            }
        )

    return changes, skipped, force_entries


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
def write_gradle_file(
    build_text: str,
    changes: list[dict],
    force_entries: list[dict],
    output_path: str,
    source_path: str,
    in_place: bool,
) -> None:
    updated_text = build_text
    for change in changes:
        updated_text = updated_text.replace(change["original"], change["replacement"], 1)
    updated_text = write_resolution_forces(updated_text, force_entries)

    if in_place:
        bak = source_path + ".bak"
        if not os.path.exists(bak):
            Path(bak).write_text(build_text, encoding="utf-8")
            print(f"Backup: {bak}")
        else:
            print(f"Backup already exists, not overwritten: {bak}")
        Path(source_path).write_text(updated_text, encoding="utf-8")
        print(f"Updated in place: {source_path}")
    else:
        Path(output_path).write_text(updated_text, encoding="utf-8")
        print(f"Output: {output_path}")
