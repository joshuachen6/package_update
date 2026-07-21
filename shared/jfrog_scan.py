from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from shared.xray import ComponentVersion, search_cves_by_components

_GRADLE_DEP_RE = re.compile(
    r"([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)(?::([A-Za-z0-9_.+-]+))?(?:\s+->\s+([A-Za-z0-9_.+-]+))?"
)
_PYTHON_TREE_DEP_RE = re.compile(r"\+--\s+([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)")
def _strip_jfrog_service_path(host):
    for suffix in ("/artifactory", "/xray"):
        if host.endswith(suffix):
            return host[: -len(suffix)]
    return host


def _normalize_xray_host(host):
    host = (host or os.environ.get("JFROG_XRAY_HOST") or "").strip().rstrip("/")
    if not host:
        return None
    if not host.startswith(("http://", "https://")):
        host = "https://" + host
    return _strip_jfrog_service_path(host)


def _component_key(component):
    return (component.ecosystem, component.package, component.version)
def _dedupe_components(components):
    seen = set()
    deduped = []
    for component in components:
        if not component.package or not component.version:
            continue
        key = _component_key(component)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(component)
    return deduped


def _walk_npm_lock_deps(deps, components):
    if not isinstance(deps, dict):
        return
    for package, info in deps.items():
        if not isinstance(info, dict):
            continue
        version = info.get("version")
        if isinstance(version, str) and version:
            components.append(ComponentVersion("npm", package, version))
        _walk_npm_lock_deps(info.get("dependencies"), components)


def _is_skipped_path(path):
    return any(part.startswith(".") or part == ".venv" for part in Path(path).parts)


def _collect_npm_components(project_dir, package_dirs=None, lock_paths=None):
    components = []
    root = Path(project_dir)
    if lock_paths is not None:
        resolved_paths = [Path(p) for p in lock_paths]
    elif package_dirs is not None:
        resolved_paths = [Path(d) / "package-lock.json" for d in package_dirs]
    else:
        resolved_paths = [
            p for p in root.rglob("package-lock.json")
            if not _is_skipped_path(p.relative_to(root))
        ]

    for lock_path in resolved_paths:
        if not lock_path.is_file():
            continue
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        packages = payload.get("packages")
        if isinstance(packages, dict):
            for package_path, info in packages.items():
                if not package_path or not isinstance(info, dict):
                    continue
                version = info.get("version")
                if not isinstance(version, str) or not version:
                    continue
                marker = "node_modules/"
                if marker not in package_path:
                    continue
                package = package_path.split(marker, 1)[1]
                if package:
                    components.append(ComponentVersion("npm", package, version))
        _walk_npm_lock_deps(payload.get("dependencies"), components)
    return components


def _collect_gradle_components(log_dir, tree_paths=None):
    components = []
    if tree_paths is None:
        tree_paths = [Path(log_dir) / "gradle-dependency-tree.txt"]
    else:
        tree_paths = [Path(tree_path) for tree_path in tree_paths]
    for tree_path in tree_paths:
        if _is_skipped_path(tree_path) or not tree_path.is_file():
            continue
        try:
            text = tree_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            if "+---" not in line and "\\---" not in line:
                continue
            if "FAILED" in line:
                continue
            match = _GRADLE_DEP_RE.search(line)
            if not match:
                continue
            group, artifact = match.group(1), match.group(2)
            version = match.group(4) or match.group(3)
            if group and artifact and version:
                components.append(ComponentVersion("maven", f"{group}:{artifact}", version))
    return components


def _python_dependency_paths(project_dir, dependency_paths=None):
    if dependency_paths is not None:
        return [Path(p) for p in dependency_paths]
    from parsers.python import is_supported_python_dependency_file
    root = Path(project_dir)
    return [
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file()
        and not _is_skipped_path(candidate.relative_to(root))
        and is_supported_python_dependency_file(candidate)
    ]


def _collect_python_components(project_dir, requirement_paths=None):
    components = []
    try:
        from parsers.python import parse_python_dependency_file
    except Exception:
        return components

    for dep_path in _python_dependency_paths(project_dir, requirement_paths):
        if not dep_path.is_file():
            continue
        try:
            _, requirements = parse_python_dependency_file(dep_path)
        except Exception:
            continue
        for req in requirements:
            if req.name and req.version:
                components.append(ComponentVersion("pypi", req.normalized_name, req.version))
    return components
def _collect_python_tree_components(log_dir, tree_paths=None):
    components = []
    if tree_paths is None:
        tree_paths = [Path(log_dir) / "python-dependency-tree.txt"]
    else:
        tree_paths = [Path(p) for p in tree_paths]
    for tree_path in tree_paths:
        if _is_skipped_path(tree_path) or not tree_path.is_file():
            continue
        try:
            text = tree_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            if "+--" not in line:
                continue
            match = _PYTHON_TREE_DEP_RE.search(line)
            if not match:
                continue
            package, version = match.group(1), match.group(2)
            if package and version:
                normalized = package.replace("_", "-").lower()
                components.append(ComponentVersion("pypi", normalized, version))
    return components


def _component_id(component):
    if component.ecosystem == "npm":
        return f"npm://{component.package}:{component.version}"
    if component.ecosystem == "maven":
        group, artifact = component.package.split(":", 1)
        return f"gav://{group}:{artifact}:{component.version}"
    return f"{component.ecosystem}://{component.package}:{component.version}"


def run_jfrog_audit(
    project_dir,
    log_dir,
    timeout=600,
    xray_host=None,
    auth=None,
    batch_size=100,
    ecosystems=None,
    npm_package_dirs=None,
    npm_lock_paths=None,
    gradle_tree_paths=None,
    python_requirement_paths=None,
    python_tree_paths=None,
    output_name="jfrog-audit.json",
):
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    host = _normalize_xray_host(xray_host)
    enabled_ecosystems = set(ecosystems or ("npm", "maven", "pypi"))

    components = []
    if "npm" in enabled_ecosystems:
        components.extend(_collect_npm_components(project_dir, npm_package_dirs, npm_lock_paths))
    if "maven" in enabled_ecosystems:
        components.extend(_collect_gradle_components(log_dir, gradle_tree_paths))
    if "pypi" in enabled_ecosystems:
        tree_comps = _collect_python_tree_components(log_dir, python_tree_paths)
        if tree_comps:
            components.extend(tree_comps)
        else:
            components.extend(_collect_python_components(project_dir, python_requirement_paths))
    components = _dedupe_components(components)

    out_path = os.path.join(log_dir, output_name)
    result = {
        "available": bool(host),
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "json_path": out_path,
        "vulnerability_count": 0,
        "component_count": len(components),
        "vulnerable_component_count": 0,
        "vulnerable_components": [],
        "errors": [],
    }

    def _write_audit_json(vulnerable_components=None, errors=None, skipped_reason=""):
        payload = {
            "xray_host": host,
            "ecosystems": sorted(enabled_ecosystems),
            "component_count": len(components),
            "vulnerable_component_count": len(vulnerable_components or []),
            "vulnerability_count": sum(len(row.get("cves", [])) for row in (vulnerable_components or [])),
            "vulnerable_components": vulnerable_components or [],
            "errors": errors or [],
        }
        if skipped_reason:
            payload["skipped_reason"] = skipped_reason
        Path(out_path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        result["stdout"] = json.dumps(payload, indent=2, sort_keys=True)
        result["vulnerability_count"] = payload["vulnerability_count"]
        result["vulnerable_component_count"] = payload["vulnerable_component_count"]
        result["vulnerable_components"] = payload["vulnerable_components"]
        result["errors"] = payload["errors"]
        return result

    if not host:
        result["stderr"] = (
            "JFrog Xray API host is not configured. Set the Xray URL in the UI "
            "or JFROG_XRAY_HOST in the environment."
        )
        print("JFrog API CVE scan skipped: Xray host is not configured.")
        print(f"JFrog audit log -> {out_path}")
        return _write_audit_json(skipped_reason=result["stderr"])

    if not components:
        result["stderr"] = (
            "No resolved dependency components found. Generate package-lock.json, "
            "gradle-dependency-tree.txt, Python requirements files, or pyproject.toml before running the CVE scan."
        )
        print("JFrog API CVE scan skipped: no resolved dependency components found.")
        print(f"JFrog audit log -> {out_path}")
        return _write_audit_json(skipped_reason=result["stderr"])
    print(f"Running JFrog Xray API CVE scan for {len(components)} resolved component(s)...")
    vulnerable_components = {}
    errors = []
    effective_batch_size = max(1, int(batch_size or 100))
    batches = [
        components[start : start + effective_batch_size]
        for start in range(0, len(components), effective_batch_size)
    ]
    with ThreadPoolExecutor(max_workers=min(len(batches), 8)) as executor:
        futures = [
            executor.submit(search_cves_by_components, batch, xray_host=host, auth=auth, timeout=timeout)
            for batch in batches
        ]
        for future in as_completed(futures):
            batch_vulns, error = future.result()
            if error:
                errors.append(error)
            vulnerable_components.update(batch_vulns)

    rows = []
    by_id = {_component_id(component): component for component in components}
    for component_id, cves in sorted(vulnerable_components.items()):
        component = by_id.get(component_id)
        rows.append(
            {
                "component_id": component_id,
                "ecosystem": component.ecosystem if component else "",
                "package": component.package if component else "",
                "version": component.version if component else "",
                "cves": sorted(cves),
            }
        )

    result["stderr"] = chr(10).join(errors)
    result["returncode"] = 1 if errors else 0
    _write_audit_json(vulnerable_components=rows, errors=errors)

    print(
        "JFrog Xray API CVE scan complete: "
        f"{result['vulnerability_count']} CVE record(s) across "
        f"{result['vulnerable_component_count']} vulnerable component(s)."
    )
    print(f"JFrog audit log -> {out_path}")
    if errors:
        print("JFrog Xray API CVE scan completed with error(s):")
        for error in errors:
            print(f"  {error}")
    return result


def vulnerable_packages_by_ecosystem(jfrog_result):
    grouped = {"npm": set(), "maven": set(), "pypi": set()}
    if not isinstance(jfrog_result, dict):
        return grouped
    for row in jfrog_result.get("vulnerable_components") or []:
        if not isinstance(row, dict):
            continue
        ecosystem = row.get("ecosystem")
        package = row.get("package")
        if ecosystem in grouped and isinstance(package, str) and package:
            grouped[ecosystem].add(package)
    return grouped


def audit_scan_usable(jfrog_result: dict) -> bool:
    """Return False if the JFrog/Xray scan itself failed or was incomplete.

    A transient network failure (timeout, connection reset, DNS failure) in
    even one batch of search_cves_by_components calls still leaves
    `vulnerability_count`/`vulnerable_components` populated with whatever
    partial results happened to succeed -- indistinguishable from a
    genuinely clean scan when that partial result is empty. Confirmed live:
    several real batch runs recorded `vulnerability_count: 0` alongside a
    populated `errors` list (e.g. "Connection reset by peer"), and callers
    that only checked vulnerability_count silently treated "scan failed" as
    "nothing to remediate" -- the initial audit drove zero remediation
    attempts for those repos, then a second, working post-audit reported the
    real (unchanged) vulnerability count, making the report read as if the
    tool had introduced new CVEs rather than never having attempted a fix.

    Any caller deciding "is this vulnerability count trustworthy" -- before
    building remediation criteria from an initial audit, or before trusting
    a post-remediation audit's outcome -- must go through this one check
    rather than re-deriving it inline.
    """
    return (
        isinstance(jfrog_result, dict)
        and bool(jfrog_result.get("available"))
        and not jfrog_result.get("errors")
        and not jfrog_result.get("stderr")
    )


def run_jfrog_audit_with_retry(
    *,
    max_attempts: int = 3,
    retry_delay: float = 5.0,
    **kwargs,
) -> dict:
    """run_jfrog_audit, retrying on a transient scan failure.

    A batch of 28+ repos scanned in the same run showed 5 hit a transient
    per-request network error (connection reset, timeout, DNS failure) --
    the same Xray endpoint and credentials worked for every other repo in
    the same run, so these are blips, not an outage. Simply gating on
    audit_scan_usable (raising instead of silently treating the result as
    "clean") makes the failure honest but still leaves those repos
    unattempted; retrying the same, idempotent, read-only scan call
    recovers them into a normal remediation pass instead.
    """
    result: dict = {}
    for attempt in range(1, max_attempts + 1):
        result = run_jfrog_audit(**kwargs)
        if audit_scan_usable(result):
            return result
        if attempt < max_attempts:
            print(
                f"JFrog CVE audit attempt {attempt}/{max_attempts} did not "
                f"complete successfully ({'; '.join(result.get('errors') or []) or result.get('stderr')}); "
                f"retrying in {retry_delay:.0f}s..."
            )
            time.sleep(retry_delay)
    return result
