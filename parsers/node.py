"""npm-specific parsers, subprocess helpers, and ADO version extraction.

Three responsibilities:
  1. Parse package.json into typed entries — DirectEntry, collect_direct_entries,
     collect_known_packages, extract_prefix_and_version, etc.
  2. Query npm and verify registry accessibility in parallel — npm_view_versions,
     parallel_npm_versions, is_version_blocked, find_unblocked_version.
  3. Extract package/version pairs from ADO task CSV rows — CVE/GHSA lookup
     (via shared.cve_lookup) runs first; unresolved rows fall back to Claude NLP
     (via resolver.claude_resolver.batch_resolve).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from ado.extractor import read_csv_full_rows
from registry import npm as npm_registry
from shared.cache import cache_by_subprocess_run
from shared.semver import SEMVER_RE, SemVer
from shared.utils import ProgressBar
from shared.xray import filter_versions_without_cves

DEFAULT_DIRECT_SECTIONS = ["dependencies", "devDependencies"]

PACKAGE_AT_VERSION_RE = re.compile(
    r"(?<![A-Za-z0-9_@/.-])"
    r"(@[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|[A-Za-z0-9][A-Za-z0-9_.-]{1,})"
    r"@v?(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)"
    r"(?![A-Za-z0-9_@/.-])"
)


@dataclass
class DirectEntry:
    package: str
    spec: str
    section: str
    path: str
    container: dict[str, Any] = field(repr=False)
    key: str = field(repr=False)


def parse_sections(value: str | None) -> list[str]:
    """Return the list of package.json sections treated as direct dependencies; defaults to dependencies + devDependencies."""
    if not value:
        return DEFAULT_DIRECT_SECTIONS
    return [part.strip() for part in value.split(",") if part.strip()]


def collect_known_packages(package_json: dict[str, Any]) -> set[str]:
    """Return every package name declared in package.json across all dep sections and the full overrides tree."""
    known: set[str] = set()
    for section in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        known.update((package_json.get(section) or {}).keys())

    def collect_override_keys(obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        for key, value in obj.items():
            known.add(key)
            collect_override_keys(value)

    collect_override_keys(package_json.get("overrides") or {})
    return known


def collect_direct_entries(package_json: dict[str, Any], sections: list[str]) -> list[DirectEntry]:
    """Return a DirectEntry for every string-valued spec in the given package.json sections."""
    entries: list[DirectEntry] = []
    for section in sections:
        value = package_json.get(section)
        if isinstance(value, dict):
            for package, spec in value.items():
                if isinstance(spec, str):
                    entries.append(
                        DirectEntry(
                            package,
                            spec,
                            section,
                            f"{section}.{package}",
                            value,
                            package,
                        )
                    )
    return entries


def collect_override_entries(package_json: dict[str, Any]) -> list[DirectEntry]:
    """Return string-valued override entries from every level of the overrides hierarchy."""
    entries: list[DirectEntry] = []
    overrides = package_json.get("overrides")
    if not isinstance(overrides, dict):
        return entries

    def walk(obj: Any, path: str) -> None:
        if not isinstance(obj, dict):
            return
        for key, value in obj.items():
            current_path = f"{path}.{key}"
            if isinstance(value, str):
                entries.append(DirectEntry(key, value, "overrides", current_path, obj, key))
            elif isinstance(value, dict):
                walk(value, current_path)

    walk(overrides, "overrides")
    return entries


def find_override_entries(overrides: Any, package: str) -> list[DirectEntry]:
    """Return all string-valued override entries for package anywhere below overrides."""
    if not isinstance(overrides, dict):
        return []
    return [
        entry
        for entry in collect_override_entries({"overrides": overrides})
        if entry.package == package
    ]


def extract_prefix_and_version(spec: str) -> tuple[str, SemVer | None]:
    """Split a version spec into its range prefix (^, ~, >=, etc.) and the trailing SemVer object."""
    if not isinstance(spec, str):
        return "", None
    match = re.search(r"v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", spec)
    if not match:
        return "", None
    return spec[: match.start()], SemVer.parse(match.group(0))


def should_skip_spec(spec: str) -> bool:
    """Return True for non-registry specs (file:, git:, workspace:, etc.) that cannot be semver-pinned."""
    stripped = spec.strip()
    return stripped.startswith(
        ("file:", "git:", "git+", "http:", "https:", "workspace:", "link:", "npm:")
    )


def parse_npm_versions_stdout(stdout: str) -> list[SemVer]:
    """Parse the JSON output of `npm view <pkg> versions --json` into sorted SemVer objects."""
    return npm_registry.parse_npm_versions_stdout(stdout)


@cache_by_subprocess_run
def npm_view_versions(
    package: str, registry: str | None, npm_cmd: str, timeout: int, cwd: str = "."
) -> tuple[str, list[SemVer], str]:
    """Run `npm view <package> versions --json` and return (package, versions, error_message).

    Kept as a thin compatibility wrapper in parsers.node so existing tests and
    callers can monkeypatch parsers.node.subprocess.run or
    parsers.node.parse_npm_versions_stdout.
    """
    cmd = [npm_cmd, "view", package, "versions", "--json"]
    if registry:
        cmd.extend(["--registry", registry])
    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, shell=False, timeout=timeout, cwd=cwd
        )
    except subprocess.TimeoutExpired:
        return package, [], f"timeout after {timeout}s"
    except Exception as exc:
        return package, [], f"failed to run npm view: {exc}"

    if completed.returncode != 0:
        error = (
            completed.stderr
            or completed.stdout
            or f"npm view exited with code {completed.returncode}"
        ).strip()
        return package, [], error[:1500]

    try:
        versions = parse_npm_versions_stdout(completed.stdout)
    except Exception as exc:
        return package, [], f"failed to parse npm view output: {exc}"
    return package, versions, ""


def parallel_npm_versions(
    packages: list[str],
    registry: str | None,
    npm_cmd: str,
    timeout: int,
    workers: int,
    show_progress: bool,
    cwd: str = ".",
) -> tuple[dict[str, list[SemVer]], list[dict[str, str]]]:
    """Fetch available npm versions for all packages in parallel.

    Kept in parsers.node for backwards compatibility and monkeypatch-friendly
    tests; the canonical implementation also exists in registry.npm.
    """
    versions_by_package: dict[str, list[SemVer]] = {}
    error_rows: list[dict[str, str]] = []
    progress = ProgressBar(
        len(packages),
        f"Querying npm/JFrog versions ({workers} workers)",
        enabled=show_progress,
    )

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(npm_view_versions, pkg, registry, npm_cmd, timeout, cwd): pkg
            for pkg in packages
        }
        for future in as_completed(futures):
            package, versions, error = future.result()
            progress.update()
            versions_by_package[package] = versions
            if error:
                error_rows.append({"package": package, "error": error})
    return versions_by_package, error_rows


def is_version_blocked(
    package: str,
    version: str,
    registry: str | None,
    npm_cmd: str,
    timeout: int,
    project_dir: str = ".",
) -> tuple[bool, str]:
    """Return (True, error_snippet) if `npm pack <package>@<version>` exits with a 403/404."""
    return npm_registry.is_version_blocked(
        package, version, registry, npm_cmd, timeout, project_dir
    )


def find_unblocked_version(
    package: str,
    blocked: SemVer,
    available: list[SemVer],
    registry: str | None,
    npm_cmd: str,
    timeout: int,
    project_dir: str = ".",
    xray_host: str | None = None,
    xray_auth: tuple[str, str] | None = None,
) -> tuple[SemVer | None, str]:
    """Return a same-major version that passes the npm pack check.

    Forward candidates are preferred. If they are all blocked or unavailable,
    fall back to lower same-major versions from nearest to oldest. The lower
    fallback is only accepted when the package is accessible; build validation
    verifies the project still compiles before the written update is retained.
    """

    forward_candidates = sorted(
        v for v in available if v.major == blocked.major and v > blocked
    )
    backward_candidates = sorted(
        (v for v in available if v.major == blocked.major and v < blocked),
        reverse=True,
    )

    forward_candidates, forward_cves, forward_xray_error = filter_versions_without_cves(
        "npm", package, forward_candidates, xray_host=xray_host, auth=xray_auth, timeout=timeout
    )
    backward_candidates, backward_cves, backward_xray_error = filter_versions_without_cves(
        "npm", package, backward_candidates, xray_host=xray_host, auth=xray_auth, timeout=timeout
    )

    checked_forward = 0
    checked_backward = 0
    for candidate in forward_candidates:
        checked_forward += 1
        blocked_flag, _snippet = is_version_blocked(
            package, str(candidate), registry, npm_cmd, timeout, project_dir
        )
        if not blocked_flag:
            return candidate, ""

    for candidate in backward_candidates:
        checked_backward += 1
        blocked_flag, _snippet = is_version_blocked(
            package, str(candidate), registry, npm_cmd, timeout, project_dir
        )
        if not blocked_flag:
            return candidate, ""

    return (
        None,
        (
            f"all {checked_forward} candidates above {blocked} and "
            f"{checked_backward} candidates below {blocked} are blocked or unavailable"
            + (
                f"; Xray lookup warning: {forward_xray_error or backward_xray_error}"
                if (forward_xray_error or backward_xray_error)
                else ""
            )
            + (
                f"; CVE-filtered candidates: {len(forward_cves) + len(backward_cves)}"
                if (forward_cves or backward_cves)
                else ""
            )
        ),
    )


def remove_nested_override_keys(obj: Any, package: str, path: str = "overrides") -> list[str]:
    """Remove every nested occurrence of `package` inside an overrides dict.

    Skips the top-level key (path == "overrides") so flat overrides are left
    to the caller to handle; only sub-object entries are removed.
    Returns the list of deleted paths for diagnostics.
    """
    removed: list[str] = []
    if not isinstance(obj, dict):
        return removed
    for key in list(obj.keys()):
        value = obj[key]
        current_path = f"{path}.{key}"
        if key == package and path != "overrides":
            del obj[key]
            removed.append(current_path)
            continue
        if isinstance(value, dict):
            removed.extend(remove_nested_override_keys(value, package, current_path))
    return removed


def resolve_transitive_with_parent(
    parent: str,
    parent_new_spec: str,
    parent_section: str,
    transitive: str,
    package_json: dict[str, Any],
    npm_cmd: str,
    timeout: int,
    cwd: str,
    registry: str | None = None,
) -> list[SemVer] | None:
    """
    Simulates updating `parent` to `parent_new_spec` in the project's package.json
    (stripping any existing flat override for `transitive`), resolves the full
    dependency tree via `npm install --package-lock-only`, and returns every
    resolved version of `transitive` found anywhere in the resulting lock file.

    Uses npm's actual resolver — results are exact, regardless of chain depth.
    Returns None on timeout, npm error, or if `transitive` is absent from the tree.
    """
    import copy as _copy

    test_pkg = _copy.deepcopy(package_json)
    section = test_pkg.get(parent_section, {})
    if parent in section:
        section[parent] = parent_new_spec

    # Remove all override pins for the transitive dep so npm resolves it freely.
    overrides = test_pkg.get("overrides")
    if isinstance(overrides, dict):
        overrides.pop(transitive, None)
        remove_nested_override_keys(overrides, transitive)
        if not overrides:
            test_pkg.pop("overrides", None)

    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as fh:
            json.dump(test_pkg, fh, indent=2)

        # Carry .npmrc so private/enterprise registries are honoured
        npmrc = os.path.join(cwd, ".npmrc")
        if os.path.exists(npmrc):
            shutil.copy2(npmrc, os.path.join(tmp, ".npmrc"))

        cmd = [npm_cmd, "install", "--package-lock-only", "--no-audit", "--no-fund"]
        if registry:
            cmd.extend(["--registry", registry])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None

        if result.returncode != 0:
            return None

        lock_path = os.path.join(tmp, "package-lock.json")
        if not os.path.exists(lock_path):
            return None

        try:
            with open(lock_path, encoding="utf-8") as fh:
                lock = json.load(fh)
        except Exception:
            return None

    versions: list[SemVer] = []

    # package-lock v2/v3: flat "packages" dict keyed by "node_modules/…" paths
    packages = lock.get("packages", {})
    for key, info in packages.items():
        if not isinstance(info, dict):
            continue
        # last segment after "node_modules/" is the package name
        name = key.rsplit("node_modules/", 1)[-1] if "node_modules/" in key else ""
        if name == transitive:
            v = SemVer.parse(info.get("version", ""))
            if v:
                versions.append(v)

    # package-lock v1 fallback: recursive "dependencies" tree
    if not versions:

        def _walk_v1(deps: dict[str, Any]) -> None:
            for name, info in deps.items():
                if not isinstance(info, dict):
                    continue
                if name == transitive:
                    v = SemVer.parse(info.get("version", ""))
                    if v:
                        versions.append(v)
                _walk_v1(info.get("dependencies") or {})

        _walk_v1(lock.get("dependencies") or {})

    return versions or None


def find_top_level_dependents_by_major(
    package: str,
    npm_cmd: str,
    timeout: int,
    cwd: str,
) -> dict[int, set[str]]:
    """
    Runs `npm ls <package> --all --json` and returns {major: {top_level_dep, ...}}
    showing which direct dependencies transitively pull in each major version.
    """
    cmd = [npm_cmd, "ls", package, "--all", "--json"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, shell=False
        )
    except Exception:
        return {}

    if not result.stdout.strip():
        return {}

    try:
        tree = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    major_to_dependents: dict[int, set[str]] = {}

    def collect(node: dict[str, Any], top_dep: str | None) -> None:
        for dep_name, dep_info in (node.get("dependencies") or {}).items():
            if not isinstance(dep_info, dict):
                continue
            current_top = top_dep if top_dep is not None else dep_name
            if dep_name == package:
                v = SemVer.parse(dep_info.get("version", ""))
                if v and current_top != package:
                    major_to_dependents.setdefault(v.major, set()).add(current_top)
            collect(dep_info, current_top)

    collect(tree, None)
    return major_to_dependents


def _load_or_generate_lockfile(
    cwd: str,
    package_json: dict[str, Any],
    npm_cmd: str,
    timeout: int,
) -> dict[str, Any] | None:
    """Return parsed package-lock.json from the project dir, generating one if absent."""
    lock_path = os.path.join(cwd, "package-lock.json")
    if os.path.exists(lock_path):
        try:
            with open(lock_path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass

    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as fh:
            json.dump(package_json, fh, indent=2)
        npmrc = os.path.join(cwd, ".npmrc")
        if os.path.exists(npmrc):
            shutil.copy2(npmrc, os.path.join(tmp, ".npmrc"))
        try:
            subprocess.run(
                [npm_cmd, "install", "--package-lock-only", "--no-audit", "--no-fund"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                shell=False,
            )
        except Exception:
            return None
        gen_lock = os.path.join(tmp, "package-lock.json")
        if not os.path.exists(gen_lock):
            return None
        try:
            with open(gen_lock, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None


def get_lockfile_installed_version(
    lockfile: dict[str, Any],
    package: str,
    under_parent: str | None = None,
) -> SemVer | None:
    """Return the installed version of `package` from the lockfile.

    Checks the non-hoisted path under `under_parent` first (if given),
    then falls back to the hoisted path.  Handles v2/v3 (packages dict)
    and v1 (dependencies dict).
    """
    packages = lockfile.get("packages", {})
    if packages:
        if under_parent:
            key = f"node_modules/{under_parent}/node_modules/{package}"
            if key in packages:
                return SemVer.parse(packages[key].get("version", ""))
        hoisted = f"node_modules/{package}"
        if hoisted in packages:
            return SemVer.parse(packages[hoisted].get("version", ""))

    deps = lockfile.get("dependencies", {})
    if deps:
        if under_parent:
            nested = deps.get(under_parent, {}).get("dependencies", {})
            if package in nested:
                return SemVer.parse(nested[package].get("version", ""))
        if package in deps:
            return SemVer.parse(deps[package].get("version", ""))

    return None


def _build_requires_map(deps: Any) -> dict[str, set[str]]:
    """Collect {package_name: {packages it directly requires}} from the v1 dependencies tree."""
    requires_map: dict[str, set[str]] = {}

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        for name, info in node.items():
            if not isinstance(info, dict):
                continue
            reqs = info.get("requires", {})
            if isinstance(reqs, dict):
                requires_map.setdefault(name, set()).update(reqs.keys())
            walk(info.get("dependencies"))

    walk(deps)
    return requires_map


def find_top_level_dependents_from_lockfile(
    package: str,
    lockfile: dict[str, Any],
    direct_dep_names: set[str],
) -> dict[int, set[str]]:
    """
    Returns {major: {top_level_direct_dep, ...}} without requiring node_modules.

    Uses lockfile v2/v3 flat `packages` paths for non-hoisted instances, and the
    v1/v2 `dependencies` requires-graph for hoisted instances.
    """
    if not lockfile:
        return {}

    major_to_dependents: dict[int, set[str]] = {}
    packages_dict = lockfile.get("packages", {})

    if packages_dict:
        hoisted_path = f"node_modules/{package}"
        hoisted_version: SemVer | None = None

        for path, info in packages_dict.items():
            if not path or not isinstance(info, dict):
                continue
            name = path.rsplit("node_modules/", 1)[-1] if "node_modules/" in path else ""
            if name != package:
                continue
            v = SemVer.parse(info.get("version", ""))
            if not v:
                continue
            if path == hoisted_path:
                hoisted_version = v
                continue
            # Non-hoisted: "node_modules/A/.../node_modules/package"
            # Root direct dep is the first segment after the leading "node_modules/"
            segments = path.split("/node_modules/")
            root = (
                segments[0].split("node_modules/", 1)[-1]
                if "node_modules/" in segments[0]
                else segments[0]
            )
            if root in direct_dep_names:
                major_to_dependents.setdefault(v.major, set()).add(root)

        if hoisted_version is not None:
            requires_map = _build_requires_map(lockfile.get("dependencies") or {})
            for top_dep in direct_dep_names:
                if top_dep == package:
                    continue
                visited: set[str] = set()
                queue = [top_dep]
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    if package in requires_map.get(current, set()):
                        major_to_dependents.setdefault(hoisted_version.major, set()).add(top_dep)
                        break
                    queue.extend(r for r in requires_map.get(current, set()) if r not in visited)
    else:
        # Pure v1 lockfile — walk the dependencies tree
        def walk_v1(node: dict[str, Any], top_dep: str | None) -> None:
            for dep_name, dep_info in (node.get("dependencies") or {}).items():
                if not isinstance(dep_info, dict):
                    continue
                current_top = top_dep if top_dep is not None else dep_name
                if (
                    dep_name == package
                    and current_top in direct_dep_names
                    and current_top != package
                ):
                    v = SemVer.parse(dep_info.get("version", ""))
                    if v:
                        major_to_dependents.setdefault(v.major, set()).add(current_top)
                walk_v1(dep_info, current_top)

        walk_v1(lockfile, None)

    return major_to_dependents


def _package_names_from_lockfile(lock: dict[str, Any]) -> set[str]:
    """Extract every package name from a parsed package-lock.json, supporting v1 (dependencies) and v2/v3 (packages)."""
    packages: set[str] = set()
    for key in lock.get("packages", {}):
        if "node_modules/" in key:
            name = key.rsplit("node_modules/", 1)[-1]
            if name:
                packages.add(name)
    if not packages:

        def _walk_v1(deps: dict[str, Any]) -> None:
            for name, info in deps.items():
                if isinstance(info, dict):
                    packages.add(name)
                    _walk_v1(info.get("dependencies") or {})

        _walk_v1(lock.get("dependencies") or {})
    return packages


def collect_lockfile_packages(
    package_json: dict[str, Any],
    npm_cmd: str,
    timeout: int,
    cwd: str,
) -> set[str]:
    """
    Returns every package name in the resolved transitive dependency tree.

    Tries the project's existing package-lock.json first (fast path), then falls
    back to generating one via `npm install --package-lock-only` in a temp dir.
    Returns an empty set on any failure so the caller can fall back gracefully.
    """
    # Fast path: use the project's existing lockfile if available.
    existing = os.path.join(cwd, "package-lock.json")
    if os.path.exists(existing):
        try:
            with open(existing, encoding="utf-8") as fh:
                lock = json.load(fh)
            pkgs = _package_names_from_lockfile(lock)
            if pkgs:
                return pkgs
        except Exception:
            pass

    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as fh:
            json.dump(package_json, fh, indent=2)

        npmrc = os.path.join(cwd, ".npmrc")
        if os.path.exists(npmrc):
            shutil.copy2(npmrc, os.path.join(tmp, ".npmrc"))

        cmd = [npm_cmd, "install", "--package-lock-only", "--no-audit", "--no-fund"]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                shell=False,
            )
        except Exception:
            return set()

        lock_path = os.path.join(tmp, "package-lock.json")
        if not os.path.exists(lock_path):
            return set()

        try:
            with open(lock_path, encoding="utf-8") as fh:
                lock = json.load(fh)
        except Exception:
            return set()

    return _package_names_from_lockfile(lock)


def extract_ado_package_versions(
    csv_path: str,
    columns: list[str] | None,
    known_packages: set[str],
    show_progress: bool,
    package_json: dict[str, Any] | None = None,
    claude_model: str = "haiku",
    claude_effort: str = "low",
    claude_timeout: int = 120,
    claude_workers: int = 4,
    claude_cmd: str = "claude",
    claude_batch_size: int = 40,
    npm_cmd: str = "npm",
    project_dir: str = ".",
) -> tuple[dict[str, set[SemVer]], dict[str, set[int]], dict[str, str], set[str]]:
    """Returns (package_versions, package_task_ids, package_constraints, osv_packages).

    Every row that contains a version number is sent to Claude in batched
    prompts.  When package_json is provided, the full transitive dependency
    tree is resolved via `npm install --package-lock-only` so packages not
    declared in package.json (e.g. tar, ip-address) are visible to the
    pattern matcher and Claude.

    package_constraints maps package name to ">=" or ">" (most restrictive
    constraint seen across all tasks mentioning that package).
    """
    rows = read_csv_full_rows(csv_path, columns)

    # Augment known_packages with the full transitive tree from the lock file
    # so transitive-only packages (e.g. tar, ip-address) are visible to Claude.
    all_packages = set(known_packages)
    if package_json is not None:
        if ProgressBar._gui_callback is not None:
            ProgressBar._gui_callback("Resolving transitive dependency tree…", 0, 0)
        print("Resolving transitive dependency tree…")
        lockfile_pkgs = collect_lockfile_packages(
            package_json,
            npm_cmd,
            max(claude_timeout, 180),
            project_dir,
        )
        new_count = len(lockfile_pkgs - known_packages)
        if lockfile_pkgs:
            print(f"  {len(lockfile_pkgs)} packages in lock file ({new_count} beyond package.json)")
        else:
            print("  lock file resolution failed — falling back to package.json only")
        all_packages |= lockfile_pkgs

    progress = ProgressBar(len(rows), "Extracting ADO package/version pairs", enabled=show_progress)
    package_versions: dict[str, set[SemVer]] = {}
    package_task_ids: dict[str, set[int]] = {}
    package_constraints: dict[str, str] = {}
    pending: list[tuple[int | None, str, set[SemVer]]] = []

    def _commit(task_id: int | None, pkg_map: dict[str, str], versions: set[SemVer]) -> None:
        for pkg, constraint in pkg_map.items():
            for v in versions:
                package_versions.setdefault(pkg, set()).add(v)
            if task_id is not None:
                package_task_ids.setdefault(pkg, set()).add(task_id)
            # ">" is more restrictive; keep it once seen
            if package_constraints.get(pkg) != ">":
                package_constraints[pkg] = constraint

    # CVE/GHSA pre-pass: look up canonical package names + fixed versions from OSV.
    # Tasks resolved this way skip the NLP/Claude path entirely.
    from shared.cve_lookup import extract_advisory_id, prefetch_advisories

    _advisory_cache = prefetch_advisories(rows, "npm")
    handled_task_ids: set[int | None] = set()
    osv_packages: set[str] = set()  # packages identified via OSV/NVD (not NLP)

    for task_id, title, _text in rows:
        aid = extract_advisory_id(title)
        if not aid or aid not in _advisory_cache:
            continue
        pkg_fixed = _advisory_cache[aid]
        if not pkg_fixed:
            continue
        for pkg_name, fixed_strs in pkg_fixed.items():
            for fixed_str in fixed_strs:
                v = SemVer.parse(fixed_str)
                if v:
                    package_versions.setdefault(pkg_name, set()).add(v)
            if task_id is not None:
                package_task_ids.setdefault(pkg_name, set()).add(task_id)
            if package_constraints.get(pkg_name) != ">":
                package_constraints[pkg_name] = ">="
            osv_packages.add(pkg_name)
        # Only skip NLP if at least one resolved name is a known package.
        # If none match (e.g. NVD uses "next.js" but npm name is "next"), let
        # NLP run to find the correct name.
        if any(p in all_packages for p in pkg_fixed):
            handled_task_ids.add(task_id)

    for task_id, _title, text in rows:
        if task_id in handled_task_ids:
            progress.update()
            continue
        progress.update()
        if not text.strip():
            continue

        row_versions: set[SemVer] = set()
        for m in SEMVER_RE.finditer(text):
            v = SemVer.parse(m.group(1))
            if v:
                row_versions.add(v)

        if not row_versions:
            continue

        pending.append((task_id, text, row_versions))

    if pending:
        from resolver.claude_resolver import batch_resolve

        claude_tasks = [(tid, txt) for tid, txt, _ in pending]
        resolved_by_idx, _ = batch_resolve(
            claude_tasks,
            all_packages,
            model=claude_model,
            effort=claude_effort,
            timeout=claude_timeout,
            workers=claude_workers,
            claude_cmd=claude_cmd,
            batch_size=claude_batch_size,
            allow_unlisted=False,
        )
        for i, (task_id, _, row_versions) in enumerate(pending):
            _commit(task_id, resolved_by_idx.get(i, {}), row_versions)

    return package_versions, package_task_ids, package_constraints, osv_packages
