"""Maven-specific build validation: run mvn, validate, and rollback on failure."""
from __future__ import annotations

import os
from pathlib import Path

from .core import (
    BuildValidationError,
    _clear_stale_validation_csvs,
    _run_build_command,
    validate_or_rollback,
)


def _revert_maven_dep(pom_text: str, candidate: dict) -> str:
    """Revert a single change in pom_text by restoring old_version at stored span."""
    from output.maven_pom import apply_pom_changes

    revert_change = {
        'dependency': candidate['package'],
        'old_version': candidate['new'],
        'new_version': candidate['old'],
        'version_span': candidate.get('version_span'),
        'property_span': candidate.get('property_span'),
    }
    # apply_pom_changes works on the *current* file text, not the cached pom_text.
    # The caller (validate_or_rollback) passes the current file text via revert_fn.
    return apply_pom_changes(pom_text, [revert_change], [])


def _maven_candidates(changes: list[dict] | None) -> list[dict]:
    return [
        {
            'package': row['dependency'],
            'change_type': row.get('change_type', 'maven'),
            'old': row['old_version'],
            'new': row['new_version'],
            'version_span': row.get('version_span'),
            'property_span': row.get('property_span'),
        }
        for row in (changes or [])
    ]


def validate_maven_project(
    pom_file: str,
    mvn_cmd: str = 'mvn',
    timeout: int = 300,
) -> None:
    """Validate an updated Maven project by running mvn test-compile."""
    project_dir = os.path.dirname(os.path.abspath(pom_file))
    cmd = [mvn_cmd, 'test-compile', '-f', pom_file, '--no-transfer-progress', '-B']
    _run_build_command(cmd, project_dir, timeout, 'mvn test-compile validation')


def validate_maven_project_or_rollback(
    pom_file: str,
    original_text: str,
    mvn_cmd: str = 'mvn',
    timeout: int = 300,
    changes: list[dict] | None = None,
    dm_overrides: list[dict] | None = None,
    log_dir: str | None = None,
    enable_failure_isolation: bool = False,
) -> None:
    try:
        validate_maven_project(pom_file, mvn_cmd=mvn_cmd, timeout=timeout)
        _clear_stale_validation_csvs(log_dir)
        return
    except BuildValidationError as first_error:
        failure_output = str(first_error)

    current_text = Path(pom_file).read_text(encoding='utf-8')

    all_changes = list(changes or []) + list(dm_overrides or [])

    validate_or_rollback(
        pom_file,
        original_text,
        current_text,
        failure_output,
        _maven_candidates(all_changes),
        build_fn=lambda: validate_maven_project(pom_file, mvn_cmd=mvn_cmd, timeout=timeout),
        revert_fn=_revert_maven_dep,
        log_dir=log_dir,
        ecosystem='maven-pom',
        enable_failure_isolation=enable_failure_isolation,
    )
