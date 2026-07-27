"""Gradle-specific build validation: run/validate, external-blocker (403)
auto-fixing, proactive dependency-tree pre-checks, and candidate revert/
step-down logic used by validate_gradle_project_or_rollback.
"""

from __future__ import annotations

import contextlib
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

from shared.maven_version import MavenVersion

from .core import (
    BuildValidationError,
    _clear_stale_validation_csvs,
    _dbg,
    _extract_failing_tests,
    _extract_gradle_blockers,
    _failing_gradle_task,
    _is_preexisting_failure,
    _is_transient_daemon_crash,
    _run_build_command,
    _write_csv,
    _write_external_auto_fixes,
    validate_or_rollback,
)


_CANT_RESOLVE_RE = re.compile(r"Could not resolve ([\w.]+:[\w.-]+:[^\s,.()]+)")
_REQUIRED_BY_GA_RE = re.compile(r"\b([\w][\w.-]*\.[\w.-]+:[\w][\w.-]+)(?::[\w.+\-]+)?")


def _parse_required_by(output: str) -> dict[str, set[str]]:
    """Map blocked 'group:artifact' → parent 'group:artifact' keys from Gradle's Required by chain."""
    result: dict[str, set[str]] = {}
    for m in _CANT_RESOLVE_RE.finditer(output):
        parts = m.group(1).split(":")
        if len(parts) < 2:
            continue
        blocked_key = f"{parts[0]}:{parts[1]}"
        window = output[m.end(): m.end() + 600]
        if "Required by:" not in window:
            continue
        rb_text = window[window.index("Required by:") + len("Required by:"): ]
        parents: set[str] = set()
        for ga_m in _REQUIRED_BY_GA_RE.finditer(rb_text[:400]):
            ga = ga_m.group(1)
            if ga != blocked_key:
                parents.add(ga)
        if parents:
            result.setdefault(blocked_key, set()).update(parents)
    return result


def _artifactory_auth_from_env() -> tuple[str, str] | None:
    username = os.environ.get("ARTIFACTORY_USERNAME", "")
    password = os.environ.get("ARTIFACTORY_PASSWORD", "")
    return (username, password) if username else None


def _try_fix_external_gradle_blockers(
    build_file: str,
    current_text: str,
    failure_output: str,
    gradle_cmd: str,
    timeout: int,
    log_dir: str | None,
    auth: tuple[str, str] | None = None,
    xray_host: str | None = None,
    base_url: str | None = None,
    changes: list[dict] | None = None,
    handled: set[tuple[str, str, str]] | None = None,
    repo_urls: list[str] | None = None,
) -> bool:
    """Try to remediate every 403-blocked Gradle artifact in build output.

    This is intentionally not limited to remediation/candidate dependencies. It mirrors
    Node's block checker behavior: any resolved dependency that Gradle reports as
    blocked is eligible for safe fallback selection before candidate rollback is
    attempted.

    Each round:
    - parse all blocked Maven GAVs from the latest Gradle failure
    - find an accessible, Xray-clean fallback with forward-then-backward logic
    - rewrite a direct/strict declaration when present
    - also add a force for classpath/transitive safety
    - rerun gradle build
    """

    from output.gradle import write_dependency_substitutions, write_resolution_forces
    from parsers.gradle import (
        find_accessible_version,
        get_available_versions,
        parse_gradle_deps,
        parse_gradle_repositories,
    )
    from parsers.gradle_tree import _parse_blocked_packages

    build_path = Path(build_file)
    original_trial_text = current_text
    if auth is None:
        auth = _artifactory_auth_from_env()
    changed_keys = {row.get("dependency", "") for row in (changes or [])}
    auto_rows: list[dict[str, str]] = []
    if handled is None:
        handled = set()
    last_failure: str = failure_output
    any_forces_written: bool = False

    for _round in range(1, 11):
        blocked = _parse_blocked_packages(failure_output)
        blocked = [
            row
            for row in blocked
            if (row[0], row[1], row[2]) not in handled
        ]
        _dbg(log_dir, f"round {_round}: {len(blocked)} new blocked packages")
        if not blocked:
            if any_forces_written:
                # 403s resolved; remaining failure is non-403 — keep forces applied
                # so the caller can run candidate rollback on the current state.
                _dbg(log_dir, "403s cleared; returning partial-fix state for candidate rollback")
                return last_failure  # type: ignore[return-value]
            build_path.write_text(original_trial_text, encoding="utf-8")
            return False

        required_by = _parse_required_by(failure_output)
        text = build_path.read_text(encoding="utf-8")
        deps = parse_gradle_deps(text)
        direct_by_key = {f"{dep.group}:{dep.artifact}": dep for dep in deps}
        # Prefer the Gradle-evaluated repo URLs threaded in from resolve_tree —
        # a regex parse of the build file returns unresolved property
        # references like "${ARTIFACTORY_SOURCE}" verbatim, which then breaks
        # every accessibility probe run against them. Falls back to the regex
        # parse (then base_url) when the caller didn't have a resolved list.
        build_repo_urls = repo_urls or parse_gradle_repositories(text)
        force_entries: list[dict[str, str]] = []
        found_any_fix = False

        for group, artifact, version, _repo_url in blocked:
            handled.add((group, artifact, version))
            key = f"{group}:{artifact}"
            current = MavenVersion.parse(version)
            if current is None:
                _dbg(log_dir, f"{key}:{version} — unparseable version, skipping")
                continue

            # If this blocked package is a transitive of a dependency we changed,
            # skip forcing it here — the candidate rollback will handle the parent.
            if key not in direct_by_key and changed_keys:
                parents = required_by.get(key, set())
                if parents & changed_keys:
                    _dbg(log_dir, f"{key}:{version} — transitive of changed {parents & changed_keys}, deferring to candidate rollback")
                    continue

            # Use the URLs the build file declares for accessibility checking — not
            # repo_url from Gradle's error output, which may be Maven Central or another
            # public mirror unreachable from this host.
            check_url = (build_repo_urls[0] if build_repo_urls else None) or base_url or os.environ.get("ARTIFACTORY_SOURCE", "").rstrip("/")
            if not check_url:
                _dbg(log_dir, f"{key}:{version} — no check_url, skipping")
                continue

            # Use base_url (virtual/aggregated repo) for version listing so maven-metadata.xml
            # is always available. Fall back to check_url if base_url returns nothing.
            meta_url = base_url or check_url
            _dbg(log_dir, f"{key}:{version} — listing from {meta_url}, checking access via {', '.join(build_repo_urls) if build_repo_urls else check_url}")
            available, _error = get_available_versions(group, artifact, meta_url, auth, timeout)
            if not available:
                available, _error = get_available_versions(group, artifact, check_url, auth, timeout)
            _dbg(log_dir, f"{key}:{version} — {len(available)} versions available{(': ' + _error) if not available else ''}")
            if not available:
                continue

            forced_version = find_accessible_version(
                group,
                artifact,
                current,
                available,
                check_url,
                auth,
                timeout,
                xray_host=xray_host,
                repo_urls=build_repo_urls or None,
                log_dir=log_dir,
            )
            _dbg(log_dir, f"{key}:{version} — find_accessible_version -> {forced_version!r}")
            if forced_version is None or forced_version == version:
                continue

            direct_dep = direct_by_key.get(key)
            if direct_dep is not None:
                replacement = direct_dep.original.replace(
                    direct_dep.version,
                    forced_version,
                    1,
                )
                text = text.replace(direct_dep.original, replacement, 1)

            force_entries.append(
                {
                    "dependency": key,
                    "old_version": version,
                    "new_version": forced_version,
                    "minimum_required": forced_version,
                }
            )
            auto_rows.append(
                {
                    "dependency": key,
                    "blocked_version": version,
                    "forced_version": forced_version,
                    "status": "auto_forced_blocked_gradle_artifact",
                    "reason": (
                        "project build passed after replacing a blocked Gradle "
                        "artifact with a non-vulnerable accessible fallback"
                    ),
                }
            )
            found_any_fix = True

        if not found_any_fix:
            build_path.write_text(original_trial_text, encoding="utf-8")
            return False

        text = write_resolution_forces(text, force_entries)
        text = write_dependency_substitutions(text, force_entries)
        build_path.write_text(text, encoding="utf-8")
        any_forces_written = True

        build_passed = False
        for attempt in (1, 2):
            # After a crash, the retry starts a cold daemon (no warm JIT/config
            # cache) under the same host contention that likely caused the
            # crash — reusing the original tight timeout here previously just
            # traded one failure mode for another (seen live: retry attempt
            # ran ~32s and hit a plain "timed out after 30s" instead of
            # recovering). Give the retry the same generous floor the
            # top-level post-crash retry already uses.
            attempt_timeout = timeout if attempt == 1 else max(300, timeout * 3)
            try:
                validate_gradle_project(build_file, gradle_cmd=gradle_cmd, timeout=attempt_timeout)
            except BuildValidationError as exc:
                failure_output = str(exc)
                # A crashed Gradle worker process (OOM, resource contention
                # under parallel batch execution) is unrelated to whether this
                # round's fix is correct — seen live losing an
                # already-successful jackson-databind 403 fix to a full
                # revert. --no-daemon only stops daemon *reuse*; a forked
                # single-use worker can still be killed. Retry once before
                # blaming this round's fix.
                if attempt == 1 and _is_transient_daemon_crash(failure_output):
                    _dbg(
                        log_dir,
                        f"round {_round} build hit a transient daemon crash; retrying once with a longer timeout",
                    )
                    continue
                last_failure = failure_output
                _dbg(log_dir, f"round {_round} build still failed: {failure_output[-1200:]}")
                break
            else:
                build_passed = True
                break

        if not build_passed:
            continue

        _write_external_auto_fixes(log_dir, auto_rows)
        print(
            "Build validation passed after fixing blocked Gradle artifact(s): "
            + ", ".join(
                f"{row['dependency']}:{row['forced_version']}"
                for row in auto_rows
            )
        )
        return True

    if any_forces_written:
        _dbg(log_dir, "round limit reached; returning partial-fix state for candidate rollback")
        return last_failure  # type: ignore[return-value]
    build_path.write_text(original_trial_text, encoding="utf-8")
    return False






def _make_gradle_pre_check_fn(
    build_file: str,
    repo_urls: list[str],
    base_url: str | None,
    auth: tuple[str, str] | None,
    timeout: int,
    baseline_text: str | None = None,
) -> Callable[[], None]:
    """Return a closure that HTTP-checks changed Gradle deps via JFrog.

    Re-reads the build file on every call so it reflects whatever revert has just been
    applied. Parallel HEAD requests — typically under 2 seconds. Raises
    BuildValidationError if any declared dep is inaccessible, skipping the full build.
    """
    from concurrent.futures import ThreadPoolExecutor

    from parsers.gradle import (
        normalize_gradle_version_for_probe,
        parse_gradle_deps,
    )
    from registry.maven import version_accessible

    check_urls = list(dict.fromkeys((repo_urls or []) + ([base_url] if base_url else [])))
    baseline_versions: dict[str, str] = {}
    if baseline_text is not None:
        for dep in parse_gradle_deps(baseline_text):
            probe_version = normalize_gradle_version_for_probe(dep.version)
            if probe_version is not None:
                baseline_versions[f"{dep.group}:{dep.artifact}"] = probe_version

    def _pre_check() -> None:
        if not check_urls:
            return
        text = Path(build_file).read_text(encoding="utf-8")
        deps = parse_gradle_deps(text)
        if not deps:
            return

        def _check(dep):
            probe_version = normalize_gradle_version_for_probe(
                dep.version
            )
            if probe_version is None:
                # Let Gradle resolve ranges, dynamic versions, and
                # variables. They are not valid literal Maven paths.
                return dep, None, None

            dependency_key = f"{dep.group}:{dep.artifact}"
            if baseline_versions.get(dependency_key) == probe_version:
                # This exact dependency existed before remediation. It is
                # not attributable to the proposed update, so let Gradle
                # handle it instead of rejecting every isolation trial.
                return dep, probe_version, None

            accessible = any(
                version_accessible(
                    dep.group,
                    dep.artifact,
                    probe_version,
                    url,
                    auth,
                    timeout,
                )
                for url in check_urls
            )
            return dep, probe_version, accessible
        blocked: list[str] = []
        with ThreadPoolExecutor(
            max_workers=min(8, len(deps))
        ) as pool:
            for dep, probe_version, accessible in pool.map(
                _check,
                deps,
            ):
                if accessible is False:
                    blocked.append(
                        f"{dep.group}:{dep.artifact}:"
                        f"{probe_version}"
                    )

        if blocked:
            raise BuildValidationError(
                "Accessibility pre-check failed — blocked: " + ", ".join(blocked)
            )

    return _pre_check


_GRADLE_TEST_LOGGING_INIT = """\
allprojects {
    tasks.withType(Test).configureEach {
        testLogging {
            exceptionFormat 'full'
            showStackTraces true
            showCauses true
        }
    }
}
"""


def _gradle_init_script_path() -> str:
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "pkg_update_gradle_logging.gradle")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_GRADLE_TEST_LOGGING_INIT)
    return path


def validate_gradle_project(
    build_file: str,
    gradle_cmd: str,
    timeout: int = 600,
    tasks: str = "build",
) -> None:
    """Validate an updated Gradle project by running gradle/gradlew <tasks>.

    tasks defaults to the full "build" lifecycle. Isolation trials pass a
    lighter target (e.g. "test") to skip packaging/coverage tasks that don't
    affect whether a candidate rollback actually fixes the failure — the
    winning trial is re-confirmed with the full "build" before being accepted.
    """
    project_dir = os.path.dirname(os.path.abspath(build_file))
    _run_build_command(
        [
            gradle_cmd,
            tasks,
            "--no-daemon",
            # Isolation trials must not share a reusable daemon. A timed-out
            # build can otherwise leave that daemon BUSY and cause every
            # subsequent candidate trial to hang.
            "--init-script",
            _gradle_init_script_path(),
        ],
        project_dir,
        timeout,
        "Gradle build validation",
    )


def _gradle_baseline_failure(
    build_path: Path,
    original_text: str,
    current_text: str,
    gradle_cmd: str,
    timeout: int,
) -> str | None:
    """Build once with the pre-remediation file; return its failure text, or
    None when the baseline passes (meaning the current failure is ours)."""
    if original_text == current_text:
        return None
    build_path.write_text(original_text, encoding="utf-8")
    try:
        validate_gradle_project(
            str(build_path), gradle_cmd=gradle_cmd, timeout=timeout,
        )
        return None
    except BuildValidationError as exc:
        return str(exc)
    finally:
        build_path.write_text(current_text, encoding="utf-8")


def capture_gradle_build_logs(
    build_path: Path,
    original_text: str,
    current_text: str,
    gradle_cmd: str,
    timeout: int,
    log_dir: str,
) -> None:
    """Opt-in diagnostic (cfg.capture_build_logs): run two explicit gradle
    builds -- one against the pre-remediation file, one against the
    already-written post-remediation file -- purely to leave clean
    build-log-before.txt/build-log-after.txt artifacts. An extra full build
    per repo; meant for verification runs, not production batches, hence
    gated behind a config flag rather than always-on.
    """
    cmd = [gradle_cmd, "build", "--no-daemon", "--init-script", _gradle_init_script_path()]
    cwd = str(build_path.resolve().parent)

    def _run_once(build_timeout: int) -> tuple[bool, str]:
        try:
            result = _run_build_command(cmd, cwd, build_timeout, "build log capture")
            return True, "\n".join(part for part in (result.stdout, result.stderr) if part)
        except BuildValidationError as exc:
            return False, str(exc)

    def _run_with_retry() -> str:
        passed, output = _run_once(timeout)
        # Same transient-worker-crash retry _run_candidate_trials already
        # applies elsewhere -- without it this diagnostic build would
        # reintroduce the exact false "failure" a crashed (not broken) worker
        # produces under batch memory contention.
        if not passed and _is_transient_daemon_crash(output):
            _, output = _run_once(max(300, timeout * 3))
        return output

    if original_text != current_text:
        build_path.write_text(original_text, encoding="utf-8")
        try:
            before_output = _run_with_retry()
        finally:
            build_path.write_text(current_text, encoding="utf-8")
        with contextlib.suppress(Exception):
            Path(log_dir, "build-log-before.txt").write_text(before_output, encoding="utf-8")

    after_output = _run_with_retry()
    with contextlib.suppress(Exception):
        Path(log_dir, "build-log-after.txt").write_text(after_output, encoding="utf-8")


def _record_preexisting_failure(log_dir: str | None, baseline_failure: str) -> None:
    if not log_dir:
        return
    task = _failing_gradle_task(baseline_failure)
    rows = [
        {
            "task": task,
            "test": test,
            "status": "preexisting_test_failure",
            "reason": "test already failed before remediation; updates were kept",
        }
        for test in sorted(_extract_failing_tests(baseline_failure))
    ]
    _write_csv(
        Path(log_dir) / "build-validation-preexisting-failures.csv",
        rows,
        ["task", "test", "status", "reason"],
    )


def _remove_gradle_force(build_text: str, dependency: str, version: str) -> str:
    target = f"{dependency}:{version}"
    lines = []
    for line in build_text.splitlines():
        if "force " in line and target in line:
            continue
        lines.append(line)
    return "\n".join(lines) + ("\n" if build_text.endswith("\n") else "")


def _revert_gradle_package(
    current_text,
    changes,
    force_entries,
    dependency,
):
    from output.gradle import (
        is_spring_boot_managed_project,
        spring_boot_managed_property,
        write_spring_boot_managed_properties,
        write_spring_boot_plugin_version,
    )

    text = current_text

    for row in changes or []:
        if row.get("dependency") != dependency:
            continue

        replacement = row.get("replacement", "")
        original = row.get("original", "")

        if replacement and original:
            text = text.replace(replacement, original)

    selected_entry = None
    remaining_entries = []

    for row in force_entries or []:
        if row.get("dependency") == dependency:
            selected_entry = row
        else:
            remaining_entries.append(row)

    if selected_entry is None:
        return text

    # org.springframework.boot:* (the platform itself) is pinned via the
    # Spring Boot Gradle plugin's own version declaration, not a force line —
    # write_gradle_file rewrites that line directly and never emits a force
    # for these, so the generic _remove_gradle_force fallback below would
    # find nothing to undo and silently no-op, leaving the bump in place even
    # though this candidate was supposed to be reverted. Regenerate the
    # plugin version from whatever boot-family force entries remain instead
    # (falling back to this candidate's own old_version when it was the last
    # one), mirroring how the managed_property branch below regenerates ext
    # properties from the remaining entries.
    if dependency.startswith("org.springframework.boot:") and is_spring_boot_managed_project(text):
        remaining_boot_entries = [
            row
            for row in remaining_entries
            if str(row.get("dependency", "")).startswith("org.springframework.boot:")
        ]
        if not remaining_boot_entries:
            remaining_boot_entries = [
                {
                    "dependency": dependency,
                    "new_version": selected_entry.get("old_version", ""),
                }
            ]
        text, _ = write_spring_boot_plugin_version(text, remaining_boot_entries)
        return text

    managed_property = spring_boot_managed_property(dependency)

    if (
        managed_property
        and is_spring_boot_managed_project(text)
    ):
        # Reconstruct every managed property from the force entries that remain
        # active in this rollback trial.
        managed_property_names = {
            spring_boot_managed_property(
                row.get("dependency", "")
            )
            for row in force_entries or []
        }
        managed_property_names.discard(None)

        for property_name in managed_property_names:
            text = re.sub(
                r"(?m)^\s*set\(\s*['\"]"
                + re.escape(property_name)
                + r"['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)\s*$\n?",
                "",
                text,
            )
            text = re.sub(
                r"(?m)^\s*ext\[\s*['\"]"
                + re.escape(property_name)
                + r"['\"]\s*\]\s*=\s*['\"][^'\"]+['\"]\s*$\n?",
                "",
                text,
            )

        text, _ = write_spring_boot_managed_properties(
            text,
            remaining_entries,
        )
        return text

    return _remove_gradle_force(
        text,
        dependency,
        selected_entry.get("new_version", ""),
    )


def _step_down_gradle_force(build_text: str, dependency: str, from_version: str, to_version: str) -> str:
    """Like _remove_gradle_force, but pins to `to_version` instead of dropping the force."""
    target = f"{dependency}:{from_version}"
    replacement = f"{dependency}:{to_version}"
    lines = []
    for line in build_text.splitlines():
        if "force " in line and target in line:
            lines.append(line.replace(target, replacement))
        else:
            lines.append(line)
    return "\n".join(lines) + ("\n" if build_text.endswith("\n") else "")


def _revert_gradle_package_to_version(
    current_text: str,
    changes: list[dict[str, str]] | None,
    force_entries: list[dict[str, str]] | None,
    dependency: str,
    target_version: str,
) -> str | None:
    """Pin `dependency` to `target_version` instead of fully reverting it.

    Used to try a still-non-vulnerable version between the originally chosen
    target and the pre-remediation original, before giving up on this
    package's CVE fix entirely. Returns None when this candidate isn't safe
    to step (Spring Boot BOM-managed properties apply to every family member
    at once, so partially stepping one down isn't representable this way).
    """
    from output.gradle import is_spring_boot_managed_project, spring_boot_managed_property

    for row in changes or []:
        if row.get("dependency") != dependency:
            continue
        original = row.get("original", "")
        replacement = row.get("replacement", "")
        old_version = row.get("old_version", "")
        if not (original and replacement):
            return None
        stepped = original.replace(old_version, target_version, 1)
        return current_text.replace(replacement, stepped)

    if dependency.startswith("org.springframework.boot:") and is_spring_boot_managed_project(current_text):
        # Same reasoning as the managed_property check below: the platform
        # version applies to every org.springframework.boot:* artifact at
        # once via the plugin declaration, and there's no force line for
        # _step_down_gradle_force to find (write_gradle_file rewrites the
        # plugin version directly) — partial stepping isn't representable.
        return None

    for row in force_entries or []:
        if row.get("dependency") != dependency:
            continue
        if spring_boot_managed_property(dependency) and is_spring_boot_managed_project(current_text):
            return None
        return _step_down_gradle_force(
            current_text,
            dependency,
            row.get("new_version", ""),
            target_version,
        )

    return None


def _make_gradle_step_down_fn(
    base_url: str | None,
    auth: tuple[str, str] | None,
    xray_host: str | None,
    timeout: int,
    repo_urls: list[str] | None,
) -> Callable[[dict, str], str | None] | None:
    """Build a step_down_fn that finds the next-lower non-vulnerable, accessible
    version for a candidate, reusing the same accessibility+CVE search already
    trusted for the blocked-version fallback path. Returns None (no ladder) when
    there's no base_url to query — the CVE filter can't be trusted without it.
    """
    if not base_url:
        return None

    def _step_down(candidate: dict, last_version: str) -> str | None:
        dependency = candidate.get("package", "")
        if ":" not in dependency:
            return None
        group, artifact = dependency.split(":", 1)

        start = MavenVersion.parse(last_version)
        old = MavenVersion.parse(candidate.get("old", ""))
        if start is None or old is None or old >= start:
            return None

        from parsers.gradle import find_accessible_version, get_available_versions

        available, _ = get_available_versions(group, artifact, base_url, auth, timeout)
        if not available:
            return None

        candidates_below = [v for v in available if old < v < start]
        if not candidates_below:
            return None

        return find_accessible_version(
            group, artifact, start, candidates_below, base_url, auth, timeout,
            xray_host=xray_host, repo_urls=repo_urls,
        )

    return _step_down


def _gradle_candidates(
    changes: list[dict[str, str]] | None,
    force_entries: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for row in changes or []:
        package = row.get("dependency", "")
        if not package or package in seen:
            continue
        rows.append(
            {
                "package": package,
                "change_type": "gradle",
                "old": row.get("old_version", ""),
                "new": row.get("new_version", ""),
            }
        )
        seen.add(package)
    for row in force_entries or []:
        package = row.get("dependency", "")
        if not package or package in seen:
            continue
        rows.append(
            {
                "package": package,
                "change_type": "gradle-force",
                "old": row.get("old_version", ""),
                "new": row.get("new_version", ""),
            }
        )
        seen.add(package)
    return rows


def _proactive_check_and_fix(
    build_file: str,
    gradle_cmd: str,
    timeout: int,
    log_dir: str | None,
    auth: tuple[str, str] | None,
    xray_host: str | None,
    base_url: str | None,
    repo_urls: list[str] | None = None,
) -> None:
    """Resolve the post-change dependency tree and proactively force any Xray-blocked
    transitives before running the full build.

    `gradlew dependencies` is far cheaper than a full build, so doing this once here
    replaces the multi-round reactive ext-fix loop that each require a complete rebuild.
    """
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import as_completed as _as_completed

    from output.gradle import (
        _align_competing_pins,
        write_dependency_substitutions,
        write_resolution_forces,
    )
    from parsers.gradle import (
        find_accessible_version,
        get_available_versions,
        parse_gradle_deps,
        parse_gradle_repositories,
    )
    from parsers.gradle_tree import (
        parse_gradle_dep_tree,
        run_gradle_dependencies_with_fallback,
    )
    from registry.maven import version_accessible

    if not base_url:
        return

    project_dir = os.path.dirname(os.path.abspath(build_file))
    build_path = Path(build_file)

    # Prefer the Gradle-evaluated repo URLs threaded in from resolve_tree — a
    # regex parse of the build file returns unresolved property references
    # like "${ARTIFACTORY_SOURCE}" verbatim, which then breaks every
    # accessibility probe run against them. Falls back to the regex parse
    # when the caller didn't have a resolved list available.
    build_text = build_path.read_text(encoding="utf-8")
    build_repo_urls = repo_urls or (parse_gradle_repositories(build_text) or None)

    _dbg(log_dir, "proactive check: resolving post-change dependency tree...")

    # `gradle dependencies` is the same operation resolve_tree runs, which floors
    # its timeout at 180s (managers/gradle.py) because large projects routinely
    # exceed the 30s default gradle_timeout on this step alone. Without the same
    # floor here, this check timed out on every single batch run for some repos
    # (e.g. ins-cp-mgmt-admin-api's dependency tree never resolved inside 30s in
    # any of its runs) — pure wasted time with zero benefit.
    tree_timeout = max(timeout, 180)

    # A package blocked severely enough to break tree resolution itself (not just
    # the final build) used to make this whole proactive check bail out silently
    # — there was no resolved tree to scan for accessibility, so the pipeline fell
    # through to the real, expensive build, which failed for the identical reason
    # and only got fixed reactively (_try_fix_external_gradle_blockers) after that
    # failure. run_gradle_dependencies_with_fallback already implements exactly
    # the "detect blocked from a failed scan, force an accessible replacement,
    # retry the scan" loop — resolve_tree (managers/gradle.py) already uses it for
    # the pre-change tree. Reusing it here closes the gap: scan first, then build.
    deps = parse_gradle_deps(build_text)
    stdout = None
    scan_bumped: dict[str, str] = {}
    for config in ("runtimeClasspath", "compileClasspath"):
        out, err, cfg_bumped = run_gradle_dependencies_with_fallback(
            project_dir=project_dir,
            build_file=build_file,
            deps=deps,
            available_by_key={},
            base_url=base_url,
            auth=auth,
            gradle_cmd=gradle_cmd,
            timeout=tree_timeout,
            configuration=config,
        )
        if cfg_bumped:
            scan_bumped.update(cfg_bumped)
        if out:
            stdout = out
            break
        _dbg(log_dir, f"proactive check: {config} failed — {(err or '')[:200]}")
        # The debug log only keeps a 200-char preview above; the parser that
        # decides whether this failure is fixable (_parse_blocked_packages,
        # inside run_gradle_dependencies_with_fallback) needs the full text,
        # and whether it actually matched real 403 output here has not yet
        # been confirmed against a real batch run — keep the untruncated
        # failure so that can be checked directly next time.
        if log_dir:
            with contextlib.suppress(Exception):
                Path(log_dir, f"gradle-dependency-tree-scan-failure-{config}.txt").write_text(
                    err or "", encoding="utf-8",
                )

    if scan_bumped:
        old_version_by_key = {f"{dep.group}:{dep.artifact}": dep.version for dep in deps}
        scan_force_entries = [
            {
                "dependency": key,
                "old_version": old_version_by_key.get(key, ""),
                "new_version": forced_version,
                "minimum_required": forced_version,
            }
            for key, forced_version in scan_bumped.items()
        ]

        # A package can already carry its own direct `version { strictly '...' }`
        # pin (or a pre-existing force / capabilitiesResolution.select()) for a
        # DIFFERENT version than what this scan just decided is actually
        # accessible. Writing only a new force here left that competing pin
        # untouched, so the file ended up declaring two different versions for
        # the same package side by side (confirmed live:
        # cwih-cnp-mgmt-consent-publish-api's jackson-databind kept its direct
        # `strictly '2.22.1'` declaration while a force to the actually-
        # accessible 2.21.5 was added right next to it — misleading even
        # though this run's real Gradle resolution happened to settle on the
        # forced version). Realign those competing pins the same way the main
        # write path already does for its own force entries.
        for row in _align_competing_pins(build_text, [], scan_force_entries):
            build_text = build_text.replace(row["original"], row["replacement"], 1)

        build_text = write_resolution_forces(build_text, scan_force_entries)
        build_text = write_dependency_substitutions(build_text, scan_force_entries)
        build_path.write_text(build_text, encoding="utf-8")
        _write_external_auto_fixes(
            log_dir,
            [
                {
                    "dependency": row["dependency"],
                    "blocked_version": row["old_version"],
                    "forced_version": row["new_version"],
                    "status": "proactive_scan_force",
                    "reason": (
                        "forced to make the post-change dependency tree "
                        "resolvable before the real build"
                    ),
                }
                for row in scan_force_entries
            ],
        )
        _dbg(
            log_dir,
            f"proactive check: forced {len(scan_force_entries)} artifact(s) just to "
            "make the dependency tree resolve: "
            + ", ".join(f"{row['dependency']}:{row['new_version']}" for row in scan_force_entries),
        )

    if not stdout:
        _dbg(
            log_dir,
            "proactive check: could not resolve dependency tree even after "
            "forcing accessible replacements, skipping",
        )
        return

    installed, _ = parse_gradle_dep_tree(stdout)
    if not installed:
        return

    if log_dir:
        with contextlib.suppress(Exception):
            Path(log_dir, "gradle-dependency-tree-after.txt").write_text(
                stdout,
                encoding="utf-8",
            )

    _dbg(log_dir, f"proactive check: {len(installed)} resolved artifacts — checking accessibility...")

    def _check(item: tuple) -> tuple:
        key, mv = item
        group, artifact = key.split(":", 1)
        version = str(mv)
        check_urls = list(dict.fromkeys((build_repo_urls or []) + ([base_url] if base_url else [])))
        ok = any(version_accessible(group, artifact, version, url, auth, timeout) for url in check_urls)
        return key, group, artifact, version, ok

    blocked_items: list[tuple[str, str, str, str]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_check, item): item for item in installed.items()}
        for future in _as_completed(futures):
            try:
                key, group, artifact, version, accessible = future.result()
                if not accessible:
                    blocked_items.append((key, group, artifact, version))
            except Exception:
                pass

    if not blocked_items:
        _dbg(log_dir, "proactive check: all artifacts accessible — no pre-flight forces needed")
        return

    # A repository/authentication/transport failure can make every probe return
    # inaccessible at once. Treating that as hundreds of independent Xray blocks
    # causes bogus replacement searches, manual-update records, and rollbacks.
    # Real policy blocks normally affect only a subset of the resolved graph, so
    # let the normal Gradle build provide the authoritative failure in this case.
    if len(installed) >= 10 and len(blocked_items) == len(installed):
        _dbg(
            log_dir,
            "proactive check: all resolved artifacts were reported inaccessible; "
            "assuming repository/authentication/transport failure and skipping "
            "pre-flight forces",
        )
        return

    _dbg(log_dir, f"proactive check: {len(blocked_items)} blocked artifact(s) — finding replacements...")

    text = build_text
    force_entries: list[dict[str, str]] = []
    auto_rows: list[dict[str, str]] = []
    unresolved_rows: list[dict[str, str]] = []

    def _find_replacement(
        item: tuple[str, str, str, str],
    ) -> tuple[str, str, str, str, str | None, int, float, float]:
        key, group, artifact, version = item
        current = MavenVersion.parse(version)
        if current is None:
            return key, group, artifact, version, None, 0, 0.0, 0.0

        metadata_start = time.perf_counter()
        available, _ = get_available_versions(
            group,
            artifact,
            base_url,
            auth,
            timeout,
        )
        metadata_elapsed = time.perf_counter() - metadata_start
        if not available:
            return (
                key,
                group,
                artifact,
                version,
                None,
                0,
                metadata_elapsed,
                0.0,
            )

        search_start = time.perf_counter()
        forced = find_accessible_version(
            group,
            artifact,
            current,
            available,
            base_url,
            auth,
            timeout,
            xray_host=xray_host,
            repo_urls=build_repo_urls,
            log_dir=log_dir,
        )
        search_elapsed = time.perf_counter() - search_start

        return (
            key,
            group,
            artifact,
            version,
            forced,
            len(available),
            metadata_elapsed,
            search_elapsed,
        )

    # Metadata retrieval and replacement searches are independent across blocked
    # artifacts. Run those network-bound operations concurrently, while consuming
    # results in input order so generated Gradle changes and reports stay stable.
    lookup_workers = min(16, len(blocked_items))
    with ThreadPoolExecutor(max_workers=lookup_workers) as pool:
        replacement_results = pool.map(_find_replacement, blocked_items)

        for result in replacement_results:
            (
                key,
                group,
                artifact,
                version,
                forced,
                available_count,
                metadata_elapsed,
                search_elapsed,
            ) = result

            if not available_count:
                reason = (
                    "unparseable version"
                    if metadata_elapsed == 0.0
                    else "no versions available"
                )
                _dbg(
                    log_dir,
                    f"proactive check: {key}:{version} — "
                    f"{reason}; manual review required",
                )
                unresolved_rows.append(
                    {
                        "package": key,
                        "change_type": "external_blocker",
                        "old": version,
                        "new": "",
                        "status": "manual_update_required",
                        "reason": reason,
                    }
                )
                continue

            _dbg(
                log_dir,
                f"proactive check: metadata for {group}:{artifact} returned "
                f"{available_count} version(s) in {metadata_elapsed:.2f}s",
            )
            _dbg(
                log_dir,
                f"proactive check: replacement search for "
                f"{group}:{artifact}:{version} completed in "
                f"{search_elapsed:.2f}s -> {forced!r}",
            )

            if forced and forced != version:
                force_entries.append(
                    {
                        "dependency": key,
                        "old_version": version,
                        "new_version": forced,
                        "minimum_required": forced,
                    }
                )
                auto_rows.append(
                    {
                        "dependency": key,
                        "blocked_version": version,
                        "forced_version": forced,
                        "status": "proactive_force",
                        "reason": (
                            "blocked transitive detected in post-change "
                            "dependency tree"
                        ),
                    }
                )
            else:
                unresolved_rows.append(
                    {
                        "package": key,
                        "change_type": "external_blocker",
                        "old": version,
                        "new": "",
                        "status": "manual_update_required",
                        "reason": (
                            "no accessible non-vulnerable replacement found"
                        ),
                    }
                )

    if unresolved_rows and log_dir:
        _write_csv(
            Path(log_dir) / "build-validation-manual-updates.csv",
            unresolved_rows,
            [
                "package",
                "change_type",
                "old",
                "new",
                "status",
                "reason",
            ],
        )

    if not force_entries:
        _dbg(
            log_dir,
            "proactive check: no accessible replacement found for any "
            "blocked artifact — manual review required",
        )
        return unresolved_rows

    text = write_resolution_forces(text, force_entries)
    text = write_dependency_substitutions(text, force_entries)
    build_path.write_text(text, encoding="utf-8")
    _write_external_auto_fixes(log_dir, auto_rows)
    print(
        f"Proactive block check: forced {len(force_entries)} "
        "blocked transitive(s): "
        + ", ".join(
            f"{row['dependency']}:{row['forced_version']}"
            for row in auto_rows
        )
    )

    if unresolved_rows:
        _dbg(
            log_dir,
            f"proactive check: {len(unresolved_rows)} blocked artifact(s) "
            "still require manual review",
        )

    return unresolved_rows


def validate_gradle_project_or_rollback(
    build_file: str,
    original_build_text: str,
    gradle_cmd: str,
    timeout: int = 600,
    changes: list[dict[str, str]] | None = None,
    force_entries: list[dict[str, str]] | None = None,
    log_dir: str | None = None,
    auth: tuple[str, str] | None = None,
    xray_host: str | None = None,
    base_url: str | None = None,
    enable_failure_isolation: bool = False,
    repo_urls: list[str] | None = None,
) -> None:
    from parsers.gradle import parse_gradle_repositories

    build_path = Path(build_file)

    # Pre-flight: resolve the post-change dependency tree and force any Xray-blocked
    # transitives before the first gradle build. gradlew dependencies is substantially
    # cheaper than gradle build and avoids multi-round reactive ext-fix loops.
    unresolved_blockers: list[dict[str, str]] = []
    if base_url:
        unresolved_blockers = _proactive_check_and_fix(
            build_file,
            gradle_cmd,
            timeout,
            log_dir,
            auth=auth,
            xray_host=xray_host,
            base_url=base_url,
            repo_urls=repo_urls,
        ) or []

    try:
        validate_gradle_project(
            build_file,
            gradle_cmd=gradle_cmd,
            timeout=timeout,
        )
    except BuildValidationError as first_error:
        failure_output = str(first_error)
        if "timed out after" in failure_output.lower() or _is_transient_daemon_crash(failure_output):
            retry_timeout = max(300, timeout * 3)
            _dbg(
                log_dir,
                "initial Gradle validation timed out or hit a transient daemon "
                f"crash; retrying the complete updated build with a {retry_timeout}s "
                "timeout before isolation",
            )
            try:
                validate_gradle_project(
                    build_file,
                    gradle_cmd=gradle_cmd,
                    timeout=retry_timeout,
                )
            except BuildValidationError as retry_error:
                failure_output = str(retry_error)
            else:
                if unresolved_blockers:
                    packages = ", ".join(
                        f"{row['package']}:{row['old']}"
                        for row in unresolved_blockers
                    )
                    _dbg(
                        log_dir,
                        "build passed on adaptive timeout retry, but blocked "
                        f"artifact(s) remain unresolved: {packages}",
                    )
                _clear_stale_validation_csvs(log_dir)
                return
    else:
        if unresolved_blockers:
            packages = ", ".join(
                f"{row['package']}:{row['old']}"
                for row in unresolved_blockers
            )
            _dbg(
                log_dir,
                "build passed, but blocked artifact(s) remain unresolved: "
                f"{packages}",
            )
        _clear_stale_validation_csvs(log_dir)
        return

    current_text = build_path.read_text(encoding="utf-8")
    external_blockers = _extract_gradle_blockers(failure_output)

    # Before blaming the updates, check whether this failure predates them.
    # Enterprise services routinely carry tests that cannot pass in the
    # remediation environment (Vault/Kafka/Mongo context loads, flaky suites);
    # without this check every trial fails, everything rolls back, and the
    # repo is reported Failed even though the updates broke nothing. Skipped
    # when the failure names download blockers — those come from the new
    # versions and the ext-fix path owns them.
    if not external_blockers and _extract_failing_tests(failure_output):
        baseline_failure = _gradle_baseline_failure(
            build_path, original_build_text, current_text, gradle_cmd, timeout,
        )
        if baseline_failure is not None and _is_preexisting_failure(
            baseline_failure, failure_output,
        ):
            _record_preexisting_failure(log_dir, baseline_failure)
            _clear_stale_validation_csvs(log_dir)
            print(
                "Build failure matches the pre-remediation baseline "
                "(same failing task and tests); keeping dependency updates."
            )
            return

    # Shared across the initial ext-fix call and all inline calls — prevents re-evaluating
    # the same blocked transitives at every greedy accumulation step.
    _ext_fix_handled: set[tuple[str, str, str]] = set()

    ext_fix_result = _try_fix_external_gradle_blockers(
        build_file, current_text, failure_output, gradle_cmd, timeout, log_dir,
        auth=auth, xray_host=xray_host, base_url=base_url,
        changes=changes, handled=_ext_fix_handled, repo_urls=repo_urls,
    ) if external_blockers else False
    if ext_fix_result is True:
        _clear_stale_validation_csvs(log_dir)
        return
    if isinstance(ext_fix_result, str):
        failure_output = ext_fix_result
        current_text = build_path.read_text(encoding="utf-8")

    def _inline_ext_fix(fail_str: str) -> bool:
        result = _try_fix_external_gradle_blockers(
            build_file, build_path.read_text(encoding="utf-8"), fail_str,
            gradle_cmd, timeout, log_dir,
            auth=auth, xray_host=xray_host, base_url=base_url,
            changes=None, handled=_ext_fix_handled, repo_urls=repo_urls,
        )
        return result is True

    # Prefer the Gradle-evaluated repo URLs threaded in from resolve_tree —
    # a regex parse of the build file returns unresolved property references
    # like "${ARTIFACTORY_SOURCE}" verbatim, which then breaks every
    # accessibility probe run against them. Falls back to the regex parse
    # when the caller didn't have a resolved list available (e.g. Phase 2
    # replay, whose cached result strips the GradleTree object).
    build_repo_urls = repo_urls if repo_urls else parse_gradle_repositories(current_text)

    validate_or_rollback(
        build_file,
        original_build_text,
        current_text,
        failure_output,
        _gradle_candidates(changes, force_entries),
        # A lighter task target during the search — compile + test, skipping
        # packaging/coverage tasks that don't bear on whether this candidate
        # fixes the failure. confirm_fn re-validates with the full "build"
        # before any trial is accepted, so this can't produce a false-positive
        # success just because a probe took a cheaper path than production.
        build_fn=lambda: validate_gradle_project(
            build_file, gradle_cmd=gradle_cmd, timeout=timeout, tasks="test",
        ),
        revert_fn=lambda text, c: _revert_gradle_package(text, changes, force_entries, c["package"]),
        log_dir=log_dir,
        ecosystem="gradle",
        pre_check_fn=_make_gradle_pre_check_fn(
            build_file,
            build_repo_urls,
            base_url,
            auth,
            timeout,
            baseline_text=original_build_text,
        ),
        ext_fix_fn=_inline_ext_fix,
        skip_implicate_check=isinstance(ext_fix_result, str),
        enable_failure_isolation=enable_failure_isolation,
        step_down_fn=_make_gradle_step_down_fn(base_url, auth, xray_host, timeout, build_repo_urls),
        revert_to_version_fn=lambda text, c, target: _revert_gradle_package_to_version(
            text, changes, force_entries, c["package"], target,
        ),
        confirm_fn=lambda: validate_gradle_project(
            build_file, gradle_cmd=gradle_cmd, timeout=timeout,
        ),
    )
