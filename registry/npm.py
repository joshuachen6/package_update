"""npm registry subprocess helpers.

This module owns npm-facing operations that were previously mixed into
``parsers.node``. Keeping these helpers separate makes the parser module focused
on package.json / lockfile interpretation while this module handles external
registry commands and parallel fetch/check behavior.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.cache import cache_by_subprocess_run
from shared.semver import SemVer
from shared.utils import ProgressBar
from shared.xray import filter_versions_without_cves


def parse_npm_versions_stdout(stdout: str) -> list[SemVer]:
    """Parse the JSON output of `npm view <pkg> versions --json` into a sorted, deduplicated list of SemVer objects."""
    stdout = stdout.strip()
    if not stdout:
        return []
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        parsed = stdout

    if isinstance(parsed, list):
        raw_versions = [str(v) for v in parsed]
    elif isinstance(parsed, str):
        raw_versions = [parsed]
    else:
        raw_versions = []

    versions = []
    for raw in raw_versions:
        v = SemVer.parse(raw)
        if v:
            versions.append(v)
    return sorted(set(versions))


@cache_by_subprocess_run
def npm_view_versions(
    package: str, registry: str | None, npm_cmd: str, timeout: int, cwd: str = "."
) -> tuple[str, list[SemVer], str]:
    """Run `npm view <package> versions --json` and return (package, versions, error_message)."""
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
    """Fetch available npm versions for all packages in parallel; returns (versions_by_package, error_rows)."""
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
    """Return (True, error_snippet) if `npm pack <package>@<version>` exits with a 403/404, else (False, "")."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cmd = [
            npm_cmd,
            "pack",
            f"{package}@{version}",
            "--no-audit",
            "--no-fund",
            "--pack-destination",
            tmp_dir,
        ]
        if registry:
            cmd.extend(["--registry", registry])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=False,
                timeout=timeout,
                cwd=project_dir,
            )
        except subprocess.TimeoutExpired:
            return False, f"timeout after {timeout}s"
        except Exception as exc:
            return False, str(exc)[:200]

        if result.returncode == 0:
            return False, ""
        combined = (result.stderr or result.stdout or "").lower()
        snippet = (result.stderr or result.stdout or "").strip()[:400]
        if (
            "403" in combined
            or "forbidden" in combined
            or "404" in combined
            or "not found" in combined
        ):
            return True, snippet
        return False, snippet


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
    """Return a same-major version that passes the npm pack check, or (None, reason).

    Prefer the existing safer behavior first: try the nearest higher same-major
    version because security work should not downgrade unless necessary. If no
    higher same-major candidate is accessible, try lower same-major versions from
    nearest to oldest. Lower candidates are only accepted when the registry pack
    check succeeds; the caller's later build validation remains responsible for
    proving the resulting project still compiles before the update is kept.
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
