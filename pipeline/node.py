"""npm dependency update pipeline driven by JFrog findings."""

from __future__ import annotations


def analyze_node(
    csv_path: str,
    pkg_json_path: str,
    log_dir: str,
    columns,
    npm_cmd: str = "npm",
    npm_timeout: int = 90,
    workers: int = 8,
    registry: str | None = None,
    skip_block_check: bool = False,
    xray_host: str | None = None,
    cve_packages: set[str] | None = None,
) -> dict:
    from types import SimpleNamespace

    from managers.npm import NpmManager
    from pipeline.runner import run_analysis

    cfg = SimpleNamespace(
        npm_cmd=npm_cmd,
        npm_timeout=npm_timeout,
        workers=workers,
        npm_registry=registry,
        skip_block_check=skip_block_check,
        xray_host=xray_host,
        skip_build_validation=True,
    )
    return run_analysis(NpmManager(), pkg_json_path, log_dir, set(cve_packages or []), cfg)
