"""Node/npm-specific build validation: run install/build, and the
package.json/lockfile revert logic used by validate_node_project_or_rollback.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .core import (
    BuildValidationError,
    _clear_stale_validation_csvs,
    _read_optional,
    _run_build_command,
    validate_or_rollback,
)


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
    enable_failure_isolation: bool = False,
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
        _clear_stale_validation_csvs(log_dir)
        return
    except BuildValidationError as first_error:
        failure_output = str(first_error)

    original_pkg = json.loads(original_package_json)
    current_text = pkg_path.read_text(encoding="utf-8")

    validate_or_rollback(
        package_json_path,
        original_package_json,
        current_text,
        failure_output,
        _node_candidates(direct_changes, override_changes),
        build_fn=lambda: validate_node_project(package_json_path, npm_cmd=npm_cmd, timeout=timeout),
        revert_fn=lambda text, c: json.dumps(
            _revert_node_package(json.loads(text), original_pkg, c["package"]), indent=2
        ) + "\n",
        log_dir=log_dir,
        ecosystem="node",
        extra_snapshots=lock_snapshots,
        enable_failure_isolation=enable_failure_isolation,
    )
