from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from shared.maven_version import MavenVersion


class BuildValidationError(RuntimeError):
    """Raised when a post-update project build validation fails."""


class BuildValidationManualUpdatesError(BuildValidationError):
    """Raised when validation cannot auto-isolate/fix breaking package updates."""


def _snippet(text: str, limit: int = 4000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _run_build_command(
    cmd: list[str],
    cwd: str,
    timeout: int,
    label: str,
) -> subprocess.CompletedProcess:
    print(f"Validating updated project: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise BuildValidationError(f"{label} command not found: {cmd[0]!r}") from exc
    except subprocess.TimeoutExpired as exc:
        raise BuildValidationError(f"{label} timed out after {timeout}s") from exc

    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout, result.stderr] if part)
        raise BuildValidationError(
            f"{label} failed with exit code {result.returncode}.\n{_snippet(output)}"
        )
    return result


def _read_optional(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _restore_optional(path: Path, content: str | None) -> None:
    if content is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(content, encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _candidate_rank(output, package):
    if not output:
        return 0
    compact_package = package.lower()
    artifact = compact_package.split(":")[-1].split("/")[-1]
    lowered = output.lower()
    score = 0
    if compact_package and compact_package in lowered:
        score += 10
    if len(artifact) >= 3 and artifact in lowered:
        score += 4
    for token in re.split(r"[^a-z0-9]+", artifact):
        if len(token) >= 5 and token in lowered:
            score += 1
    return score


def _ordered_candidates(candidates: list[dict[str, str]], output: str) -> list[dict[str, str]]:
    return sorted(
        candidates,
        key=lambda row: (
            _candidate_rank(output, row.get("package", "")),
            row.get("change_type", ""),
            row.get("package", ""),
        ),
        reverse=True,
    )
def _failure_implicates_candidate(candidates: list[dict[str, str]], output: str) -> bool:
    return any(_candidate_rank(output, row.get("package", "")) > 0 for row in candidates)


def _extract_gradle_blockers(output):
    blockers = []

    for match in re.finditer(r"Could not download (\S+)", output):
        filename = match.group(1).strip(".,;:()")
        for suffix in (".jar", ".pom"):
            if filename.endswith(suffix):
                filename = filename[: -len(suffix)]
                break

        version_start = None
        for idx, char in enumerate(filename):
            if char == "-" and idx + 1 < len(filename) and filename[idx + 1].isdigit():
                version_start = idx

        if version_start is None:
            blocker = filename
        else:
            blocker = f"{filename[:version_start]}:{filename[version_start + 1:]}"

        if blocker and blocker not in blockers:
            blockers.append(blocker)

    for match in re.finditer(r"Could not resolve (\S+)", output):
        blocker = match.group(1).strip(".,;:()")
        if blocker.lower() in {"all"}:
            continue
        if ":" not in blocker:
            continue
        if blocker and blocker not in blockers:
            blockers.append(blocker)

    return blockers


def _write_external_blockers(
    log_dir: str | None,
    ecosystem: str,
    failure_output: str,
    candidates: list[dict[str, str]],
) -> None:
    if not log_dir:
        return
    blockers = _extract_gradle_blockers(failure_output) if ecosystem == "gradle" else []
    if not blockers:
        blockers = ["unknown"]
    candidate_names = ", ".join(row.get("package", "") for row in candidates if row.get("package"))
    rows = [
        {
            "ecosystem": ecosystem,
            "blocker": blocker,
            "status": "external_build_blocker",
            "reason": "build failure did not mention any package changed by this run",
            "changed_candidates": candidate_names,
            "failure": _snippet(failure_output, 1000),
        }
        for blocker in blockers
    ]
    _write_csv(
        Path(log_dir) / "build-validation-external-blockers.csv",
        rows,
        ["ecosystem", "blocker", "status", "reason", "changed_candidates", "failure"],
    )
def _write_external_auto_fixes(
    log_dir: str | None,
    rows: list[dict[str, str]],
) -> None:
    if not log_dir or not rows:
        return
    _write_csv(
        Path(log_dir) / "build-validation-external-auto-fixes.csv",
        rows,
        [
            "dependency",
            "blocked_version",
            "forced_version",
            "status",
            "reason",
        ],
    )


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
) -> bool:
    """Try to remediate every 403-blocked Gradle artifact in build output.

    This is intentionally not limited to ADO/candidate dependencies. It mirrors
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

    from output.gradle import write_resolution_forces
    from parsers.gradle import find_accessible_version, get_available_versions, parse_gradle_deps
    from parsers.gradle_tree import _parse_blocked_packages

    build_path = Path(build_file)
    original_trial_text = current_text
    auth = _artifactory_auth_from_env()
    auto_rows: list[dict[str, str]] = []
    handled: set[tuple[str, str, str]] = set()

    for _round in range(1, 11):
        blocked = _parse_blocked_packages(failure_output)
        blocked = [
            row
            for row in blocked
            if (row[0], row[1], row[2]) not in handled
        ]
        if not blocked:
            build_path.write_text(original_trial_text, encoding="utf-8")
            return False

        text = build_path.read_text(encoding="utf-8")
        deps = parse_gradle_deps(text)
        direct_by_key = {f"{dep.group}:{dep.artifact}": dep for dep in deps}
        force_entries: list[dict[str, str]] = []
        found_any_fix = False

        for group, artifact, version, repo_url in blocked:
            handled.add((group, artifact, version))
            key = f"{group}:{artifact}"
            current = MavenVersion.parse(version)
            if current is None:
                continue
            check_url = repo_url or os.environ.get("ARTIFACTORY_SOURCE", "").rstrip("/")
            if not check_url:
                continue

            available, _error = get_available_versions(group, artifact, check_url, auth, timeout)
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
                xray_host=check_url,
            )
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
        build_path.write_text(text, encoding="utf-8")

        try:
            validate_gradle_project(build_file, gradle_cmd=gradle_cmd, timeout=timeout)
        except BuildValidationError as exc:
            failure_output = str(exc)
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

    build_path.write_text(original_trial_text, encoding="utf-8")
    return False






def _remove_key_recursive(value: Any, target: str) -> None:
    if not isinstance(value, dict):
        return
    value.pop(target, None)
    for child in list(value.values()):
        _remove_key_recursive(child, target)


def _restore_key_recursive(current: Any, original: Any, target: str) -> None:
    if not isinstance(current, dict):
        return
    if isinstance(original, dict) and target in original:
        current[target] = deepcopy(original[target])
    elif target in current:
        current.pop(target, None)

    keys = set(current)
    if isinstance(original, dict):
        keys.update(original)
    for key in keys:
        cur_child = current.get(key)
        orig_child = original.get(key) if isinstance(original, dict) else None
        if isinstance(cur_child, dict) or isinstance(orig_child, dict):
            if key not in current or not isinstance(current.get(key), dict):
                current[key] = {}
            _restore_key_recursive(current[key], orig_child, target)
            if current.get(key) == {} and not (isinstance(orig_child, dict) and orig_child):
                current.pop(key, None)


def _revert_node_package(
    current: dict[str, Any], original: dict[str, Any], package: str
) -> dict[str, Any]:
    trial = deepcopy(current)
    for section in [
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
        "overrides",
        "resolutions",
    ]:
        cur_section = trial.get(section)
        orig_section = original.get(section)
        if not isinstance(cur_section, dict):
            continue
        if isinstance(orig_section, dict) and package in orig_section:
            cur_section[package] = deepcopy(orig_section[package])
        else:
            cur_section.pop(package, None)
        if section in {"overrides", "resolutions"}:
            _restore_key_recursive(
                cur_section, orig_section if isinstance(orig_section, dict) else {}, package
            )
            _remove_key_recursive(cur_section, package)
            if isinstance(orig_section, dict):
                _restore_key_recursive(cur_section, orig_section, package)
        if cur_section == {} and not isinstance(orig_section, dict):
            trial.pop(section, None)
    return trial


def _node_candidates(
    direct_changes: list[dict[str, str]] | None,
    override_changes: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for row in direct_changes or []:
        package = row.get("package", "")
        if not package or package in seen:
            continue
        rows.append(
            {
                "package": package,
                "change_type": "direct",
                "old": row.get("old_spec", ""),
                "new": row.get("new_spec", ""),
            }
        )
        seen.add(package)
    for row in override_changes or []:
        package = row.get("package", "")
        if not package or package in seen:
            continue
        rows.append(
            {
                "package": package,
                "change_type": "override",
                "old": row.get("old_override", ""),
                "new": row.get("new_override", ""),
            }
        )
        seen.add(package)
    return rows


def validate_node_project(
    package_json_path: str,
    npm_cmd: str = "npm",
    timeout: int = 600,
) -> None:
    """Validate an updated Node project by installing and running its build script.

    The install step verifies dependency resolution and refreshes the lockfile.
    If package.json has a scripts.build entry, npm run build is executed too.
    """

    pkg_path = Path(package_json_path)
    project_dir = str(pkg_path.resolve().parent)
    package_json = json.loads(pkg_path.read_text(encoding="utf-8"))
    _run_build_command(
        [npm_cmd, "install", "--no-audit", "--no-fund"],
        project_dir,
        timeout,
        "npm install validation",
    )

    scripts: dict[str, Any] = package_json.get("scripts", {})
    if isinstance(scripts, dict) and scripts.get("build"):
        _run_build_command(
            [npm_cmd, "run", "build"],
            project_dir,
            timeout,
            "npm build validation",
        )
    else:
        print("No npm build script found; npm install validation completed.")


def validate_node_project_or_rollback(
    package_json_path: str,
    original_package_json: str,
    npm_cmd: str = "npm",
    timeout: int = 600,
    direct_changes: list[dict[str, str]] | None = None,
    override_changes: list[dict[str, str]] | None = None,
    log_dir: str | None = None,
) -> None:
    pkg_path = Path(package_json_path)
    project_dir = pkg_path.resolve().parent
    lock_paths = [
        project_dir / "package-lock.json",
        project_dir / "npm-shrinkwrap.json",
    ]
    lock_snapshots = {path: _read_optional(path) for path in lock_paths}

    try:
        validate_node_project(package_json_path, npm_cmd=npm_cmd, timeout=timeout)
        return
    except BuildValidationError as first_error:
        failure_output = str(first_error)

    current_package_json = json.loads(pkg_path.read_text(encoding="utf-8"))
    original_package = json.loads(original_package_json)
    candidates = _ordered_candidates(
        _node_candidates(direct_changes, override_changes),
        failure_output,
    )
    if candidates and not _failure_implicates_candidate(candidates, failure_output):
        pkg_path.write_text(original_package_json, encoding="utf-8")
        for path, content in lock_snapshots.items():
            _restore_optional(path, content)
        _write_external_blockers(log_dir, "node", failure_output, candidates)
        print(f"Validation failed due to a non-candidate build blocker; restored {pkg_path}")
        raise BuildValidationManualUpdatesError(
            "Build validation failed before implicating a package changed by this run. "
            "External blocker details were logged."
        )

    auto_rows: list[dict[str, str]] = []
    manual_rows: list[dict[str, str]] = []

    for candidate in candidates:
        package = candidate["package"]
        print(f"Build failed; trying automatic rollback for Node package {package}...")
        trial = _revert_node_package(current_package_json, original_package, package)
        pkg_path.write_text(json.dumps(trial, indent=2) + "\n", encoding="utf-8")
        for path, content in lock_snapshots.items():
            _restore_optional(path, content)
        try:
            validate_node_project(package_json_path, npm_cmd=npm_cmd, timeout=timeout)
            auto_rows.append(
                {
                    **candidate,
                    "status": "auto_rolled_back",
                    "reason": "project build passed after reverting this package update",
                }
            )
            if log_dir:
                _write_csv(
                    Path(log_dir) / "build-validation-auto-fixes.csv",
                    auto_rows,
                    ["package", "change_type", "old", "new", "status", "reason"],
                )
            print(
                f"Build validation passed after reverting {package}; leaving it for manual update."
            )
            return
        except BuildValidationError:
            continue

    for candidate in candidates:
        manual_rows.append(
            {
                **candidate,
                "status": "manual_update_required",
                "reason": "build failed and automatic single-package rollback did not isolate a safe fix",
            }
        )

    pkg_path.write_text(original_package_json, encoding="utf-8")
    for path, content in lock_snapshots.items():
        _restore_optional(path, content)
    if log_dir:
        _write_csv(
            Path(log_dir) / "build-validation-manual-updates.csv",
            manual_rows,
            ["package", "change_type", "old", "new", "status", "reason"],
        )
    print(f"Validation failed; restored {pkg_path}")
    raise BuildValidationManualUpdatesError(
        "Build validation failed. Candidate package updates were logged for manual update."
    )


def validate_gradle_project(
    build_file: str,
    gradle_cmd: str,
    timeout: int = 600,
) -> None:
    """Validate an updated Gradle project by running gradle/gradlew build."""
    project_dir = os.path.dirname(os.path.abspath(build_file))
    _run_build_command(
        [gradle_cmd, "build"],
        project_dir,
        timeout,
        "Gradle build validation",
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
    current_text: str,
    changes: list[dict[str, str]] | None,
    force_entries: list[dict[str, str]] | None,
    dependency: str,
) -> str:
    text = current_text
    for row in changes or []:
        if row.get("dependency") != dependency:
            continue
        replacement = row.get("replacement", "")
        original = row.get("original", "")
        if replacement and original:
            text = text.replace(replacement, original)
    for row in force_entries or []:
        if row.get("dependency") != dependency:
            continue
        text = _remove_gradle_force(text, dependency, row.get("new_version", ""))
    return text


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


def validate_gradle_project_or_rollback(
    build_file: str,
    original_build_text: str,
    gradle_cmd: str,
    timeout: int = 600,
    changes: list[dict[str, str]] | None = None,
    force_entries: list[dict[str, str]] | None = None,
    log_dir: str | None = None,
) -> None:
    build_path = Path(build_file)
    try:
        validate_gradle_project(build_file, gradle_cmd=gradle_cmd, timeout=timeout)
        return
    except BuildValidationError as first_error:
        failure_output = str(first_error)

    current_text = build_path.read_text(encoding="utf-8")
    candidates = _ordered_candidates(_gradle_candidates(changes, force_entries), failure_output)
    external_blockers = _extract_gradle_blockers(failure_output)

    # Blocked Gradle artifacts must be handled before candidate rollback,
    # regardless of whether the blocked package is ADO-related, candidate-related,
    # transitive, direct, or only appears during compileClasspath/buildscript
    # resolution. This mirrors Node's all-dependencies block checker.
    if external_blockers and _try_fix_external_gradle_blockers(
        build_file,
        current_text,
        failure_output,
        gradle_cmd,
        timeout,
        log_dir,
    ):
        return
    if (
        candidates
        and external_blockers
        and not _failure_implicates_candidate(candidates, failure_output)
    ):
        build_path.write_text(original_build_text, encoding="utf-8")
        _write_external_blockers(log_dir, "gradle", failure_output, candidates)
        print(f"Validation failed due to a non-candidate build blocker; restored {build_file}")
        raise BuildValidationManualUpdatesError(
            "Build validation failed before implicating a dependency changed by this run. "
            "External blocker details were logged."
        )

    auto_rows: list[dict[str, str]] = []
    manual_rows: list[dict[str, str]] = []

    for candidate in candidates:
        package = candidate["package"]
        print(f"Build failed; trying automatic rollback for Gradle dependency {package}...")
        trial = _revert_gradle_package(current_text, changes, force_entries, package)
        build_path.write_text(trial, encoding="utf-8")
        try:
            validate_gradle_project(build_file, gradle_cmd=gradle_cmd, timeout=timeout)
            auto_rows.append(
                {
                    **candidate,
                    "status": "auto_rolled_back",
                    "reason": "project build passed after reverting this dependency update",
                }
            )
            if log_dir:
                _write_csv(
                    Path(log_dir) / "build-validation-auto-fixes.csv",
                    auto_rows,
                    ["package", "change_type", "old", "new", "status", "reason"],
                )
            print(
                f"Build validation passed after reverting {package}; leaving it for manual update."
            )
            return
        except BuildValidationError:
            continue

    for candidate in candidates:
        manual_rows.append(
            {
                **candidate,
                "status": "manual_update_required",
                "reason": "build failed and automatic single-dependency rollback did not isolate a safe fix",
            }
        )

    build_path.write_text(original_build_text, encoding="utf-8")
    if log_dir:
        _write_csv(
            Path(log_dir) / "build-validation-manual-updates.csv",
            manual_rows,
            ["package", "change_type", "old", "new", "status", "reason"],
        )
    print(f"Validation failed; restored {build_file}")
    raise BuildValidationManualUpdatesError(
        "Build validation failed. Candidate dependency updates were logged for manual update."
    )
