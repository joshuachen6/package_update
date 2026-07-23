"""Python/pip-specific build validation: run pip install, and the
requirements.txt/pyproject.toml revert logic used by
validate_python_project_or_rollback.
"""

from __future__ import annotations

import os
from pathlib import Path

from .core import (
    BuildValidationError,
    _clear_stale_validation_csvs,
    _run_build_command,
    validate_or_rollback,
)


def _revert_python_dep(text: str, candidate: dict, file_type: str) -> str:
    from parsers.python import update_python_dependency_text
    return update_python_dependency_text(
        text,
        [{"line_index": candidate["line_index"], "new_version": candidate["old"]}],
        file_type=file_type,
    )


def _python_candidates(changes: list[dict[str, str]] | None) -> list[dict[str, str]]:
    return [
        {
            "package": row["package"],
            "change_type": "python",
            "old": row["current_version"],
            "new": row["new_version"],
            "line_index": row["line_index"],
        }
        for row in (changes or [])
    ]


def validate_python_project(
    dep_file: str,
    python_cmd: str = "python",
    timeout: int = 600,
    file_type: str = "requirements",
) -> None:
    """Validate an updated Python project by running pip install."""
    project_dir = os.path.dirname(os.path.abspath(dep_file))
    if file_type == "requirements":
        cmd = [python_cmd, "-m", "pip", "install", "-r", dep_file]
        label = "pip install validation"
    else:
        cmd = [python_cmd, "-m", "pip", "install", "-e", "."]
        label = "pip install (pyproject) validation"
    _run_build_command(cmd, project_dir, timeout, label)


def validate_python_project_or_rollback(
    dep_file: str,
    original_text: str,
    python_cmd: str = "python",
    timeout: int = 600,
    changes: list[dict[str, str]] | None = None,
    log_dir: str | None = None,
    file_type: str = "requirements",
    enable_failure_isolation: bool = False,
) -> None:
    try:
        validate_python_project(dep_file, python_cmd=python_cmd, timeout=timeout, file_type=file_type)
        _clear_stale_validation_csvs(log_dir)
        return
    except BuildValidationError as first_error:
        failure_output = str(first_error)

    current_text = Path(dep_file).read_text(encoding="utf-8")

    validate_or_rollback(
        dep_file,
        original_text,
        current_text,
        failure_output,
        _python_candidates(changes),
        build_fn=lambda: validate_python_project(dep_file, python_cmd=python_cmd, timeout=timeout, file_type=file_type),
        revert_fn=lambda text, c: _revert_python_dep(text, c, file_type),
        log_dir=log_dir,
        ecosystem="python",
        enable_failure_isolation=enable_failure_isolation,
    )
