"""Maven-specific build validation: run mvn, validate, and rollback on failure."""
from __future__ import annotations

import contextlib
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
    base_url: str | None = None,
    auth: tuple | None = None,
    extra_server_ids: list[str] | None = None,
) -> None:
    """Validate an updated Maven project by running mvn test-compile.

    When base_url and auth are provided a temporary settings.xml is written
    (same as for dependency:tree) so Maven resolves all repos through
    Artifactory with credentials — preventing 401 failures on BOM sub-POMs.
    """
    from parsers.pom import _write_temp_settings

    project_dir = os.path.dirname(os.path.abspath(pom_file))
    settings_path: str | None = None
    try:
        if base_url and auth:
            settings_path = _write_temp_settings(base_url, auth, extra_server_ids)
        sf = ['-s', settings_path] if settings_path else []
        # --no-transfer-progress requires Maven >= 3.6.1 — omitted for compatibility
        cmd = [mvn_cmd, 'test-compile', '-f', pom_file, '-B'] + sf
        _run_build_command(cmd, project_dir, timeout, 'mvn test-compile validation')
    finally:
        if settings_path:
            with contextlib.suppress(OSError):
                os.unlink(settings_path)


def validate_maven_project_or_rollback(
    pom_file: str,
    original_text: str,
    mvn_cmd: str = 'mvn',
    timeout: int = 300,
    changes: list[dict] | None = None,
    dm_overrides: list[dict] | None = None,
    log_dir: str | None = None,
    enable_failure_isolation: bool = False,
    base_url: str | None = None,
    auth: tuple | None = None,
    extra_server_ids: list[str] | None = None,
) -> None:
    def _validate():
        validate_maven_project(
            pom_file, mvn_cmd=mvn_cmd, timeout=timeout,
            base_url=base_url, auth=auth, extra_server_ids=extra_server_ids,
        )

    try:
        _validate()
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
        build_fn=_validate,
        revert_fn=_revert_maven_dep,
        log_dir=log_dir,
        ecosystem='maven-pom',
        enable_failure_isolation=enable_failure_isolation,
    )
