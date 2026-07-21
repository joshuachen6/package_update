from __future__ import annotations


def analyze_python(
    dep_file,
    log_dir,
    workers=8,
    python_cmd="python3",
    pip_timeout=90,
    pip_index_url=None,
    cve_packages=None,
    xray_host=None,
    skip_block_check=False,
):
    from types import SimpleNamespace

    from managers.python import PythonManager
    from pipeline.runner import run_analysis

    cfg = SimpleNamespace(
        python_cmd=python_cmd,
        pip_timeout=pip_timeout,
        pip_index_url=pip_index_url,
        workers=workers,
        skip_build_validation=True,
        xray_host=xray_host,
        skip_block_check=skip_block_check,
    )
    return run_analysis(PythonManager(), dep_file, log_dir, set(cve_packages or []), cfg)
