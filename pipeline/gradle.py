from __future__ import annotations


def analyze_gradle(
    csv_path: str,
    build_file: str,
    log_dir: str,
    columns,
    artifactory_source: str,
    artifactory_repo: str,
    artifactory_username: str = "",
    artifactory_password: str = "",
    workers: int = 8,
    gradle_timeout: int = 150,
    skip_block_check: bool = False,
    xray_host: str | None = None,
    cve_packages: set[str] | None = None,
    prefetched_tree=None,
    prefetched_parsed=None,
) -> dict:
    from types import SimpleNamespace

    from managers.gradle import GradleManager
    from pipeline.runner import run_analysis

    cfg = SimpleNamespace(
        artifactory_source=artifactory_source,
        artifactory_repo=artifactory_repo,
        artifactory_username=artifactory_username,
        artifactory_password=artifactory_password,
        workers=workers,
        gradle_timeout=gradle_timeout,
        skip_block_check=skip_block_check,
        xray_host=xray_host or artifactory_source,
        skip_build_validation=True,
    )
    return run_analysis(GradleManager(), build_file, log_dir, set(cve_packages or []), cfg, prefetched_tree=prefetched_tree, prefetched_parsed=prefetched_parsed)
