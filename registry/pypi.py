from __future__ import annotations

import json
import subprocess
import tempfile
from functools import lru_cache


def _run_pip_index_versions(
    package: str,
    *,
    python_cmd: str = "python3",
    timeout: int = 90,
    index_url: str | None = None,
) -> str:
    cmd = [python_cmd, "-m", "pip", "index", "versions", package]
    if index_url:
        cmd.extend(["--index-url", index_url])
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    return proc.stdout
def _parse_pip_index_versions(output: str) -> list:
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Available versions:"):
            values = line.split(":", 1)[1]
            return [part.strip() for part in values.split(",") if part.strip()]
    return []


@lru_cache(maxsize=2048)
def available_versions(
    package: str,
    python_cmd: str = "python3",
    timeout: int = 90,
    index_url: str | None = None,
) -> tuple[str, ...]:
    return tuple(
        _parse_pip_index_versions(
            _run_pip_index_versions(
                package,
                python_cmd=python_cmd,
                timeout=timeout,
                index_url=index_url,
            )
        )
    )


def latest_version(
    package: str,
    *,
    python_cmd: str = "python3",
    timeout: int = 90,
    index_url: str | None = None,
) -> str | None:
    versions = available_versions(package, python_cmd, timeout, index_url)
    return versions[0] if versions else None
def pip_inspect_tree(
    *,
    python_cmd: str = "python3",
    timeout: int = 90,
) -> dict:
    proc = subprocess.run(
        [python_cmd, "-m", "pip", "inspect", "--local"],
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    return json.loads(proc.stdout)


def is_version_blocked(
    package: str,
    version: str,
    index_url: str | None,
    python_cmd: str,
    timeout: int,
) -> tuple[bool, str]:
    """Return (True, error_snippet) if `pip download <package>==<version>` exits
    with a 403/404/no-matching-distribution error, else (False, "").

    Mirrors registry.npm.is_version_blocked's shape: `available_versions` only
    reports what a bare metadata listing returns, which does not by itself
    prove the actual artifact is downloadable -- an Artifactory/Xray policy
    can block the real file the same way it can 403 a Maven jar or npm
    tarball after the version shows up in a listing.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cmd = [
            python_cmd,
            "-m",
            "pip",
            "download",
            f"{package}=={version}",
            "--no-deps",
            "--dest",
            tmp_dir,
            "--quiet",
        ]
        if index_url:
            cmd.extend(["--index-url", index_url])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=False,
                timeout=timeout,
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
            or "no matching distribution" in combined
        ):
            return True, snippet
        return False, snippet


def find_unblocked_version(
    package: str,
    blocked,
    available: list,
    index_url: str | None,
    python_cmd: str,
    timeout: int,
    xray_host: str | None = None,
    xray_auth: tuple[str, str] | None = None,
) -> tuple:
    """Return a same-major version that passes the `pip download` check, or
    (None, reason).

    Thin PyPI-specific adapter over `shared.version_search.find_safe_version`,
    mirroring registry.npm.find_unblocked_version's shape: builds same-major
    forward/backward candidate lists and the `pip download` accessibility
    probe, then delegates the CVE-filter + concurrent-probe orchestration to
    the shared implementation (also used by Maven and npm).
    """
    from shared.semver import SemVer
    from shared.version_search import find_safe_version

    forward_candidates = sorted(
        v for v in available if v.major == blocked.major and v > blocked
    )
    backward_candidates = sorted(
        (v for v in available if v.major == blocked.major and v < blocked),
        reverse=True,
    )

    def _accessible(candidate: SemVer) -> bool:
        blocked_flag, _snippet = is_version_blocked(
            package, str(candidate), index_url, python_cmd, timeout
        )
        return not blocked_flag

    return find_safe_version(
        forward_candidates,
        backward_candidates,
        _accessible,
        "pypi",
        package,
        xray_host=xray_host,
        xray_auth=xray_auth,
        timeout=timeout,
    )
