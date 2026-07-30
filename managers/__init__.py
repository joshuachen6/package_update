from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class EcosystemUpdateResult:
    display_changes: list[dict]
    skipped_display: list[dict]
    extra: dict = field(default_factory=dict)


@dataclass
class WritePlan:
    """Everything the shared write+validate pipeline needs for one file.

    Captured at plan-creation time so that original_text, paths, and cfg
    values are frozen before write() modifies the file on disk.
    """
    has_changes: bool
    file_path: str
    write: Callable[[], None]
    validate: Callable[[], None] | None = None


@runtime_checkable
class EcosystemParser(Protocol):
    def parse(self, file_path: str) -> Any: ...
    def resolve_tree(self, file_path: str, parsed: Any, cfg: Any, log_dir: str) -> Any: ...


@runtime_checkable
class EcosystemRegistry(Protocol):
    def fetch_versions(self, packages: Any, cfg: Any) -> Any: ...


@runtime_checkable
class EcosystemOutput(Protocol):
    def apply_updates(
        self, parsed: Any, tree: Any, versions: Any,
        cve_packages: set[str], cfg: Any, log_dir: str | None = None,
    ) -> EcosystemUpdateResult: ...
    def write_logs(self, log_dir: str, result: EcosystemUpdateResult) -> None: ...


@runtime_checkable
class EcosystemManager(Protocol):
    ecosystem: str
    type: str
    label: str
    explicit_arg_attr: str
    explicit_arg_name: str
    explicit_arg_help: str
    total_keys: tuple[str, ...]
    parser: EcosystemParser
    registry: EcosystemRegistry
    output: EcosystemOutput

    def packages_to_fetch(self, parsed: Any, tree: Any, cve_packages: set[str]) -> Any: ...
    def summarize(self, result: dict) -> dict[str, int]: ...
    def make_write_plan(self, cfg: Any, result: dict, log_dir: str | None) -> WritePlan: ...
    def write_result(self, cfg: Any, result: dict, log_dir: str) -> None: ...


_MANAGER_SPECS: dict[str, EcosystemManager] = {}


def _ensure_specs() -> None:
    if _MANAGER_SPECS:
        return
    from managers.gradle import GradleManager
    from managers.maven import MavenPomManager
    from managers.npm import NpmManager
    from managers.python import PythonManager

    _MANAGER_SPECS.update({
        "node": NpmManager(),
        "gradle": GradleManager(),
        "maven": MavenPomManager(),
        "python": PythonManager(),
    })


MANAGER_SPECS: dict[str, EcosystemManager] = _MANAGER_SPECS


def get_manager_spec(manager_type: str) -> EcosystemManager:
    _ensure_specs()
    try:
        return _MANAGER_SPECS[manager_type]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported dependency manager type: {manager_type}") from exc


def manager_total_keys() -> list[str]:
    _ensure_specs()
    keys: list[str] = []
    for spec in _MANAGER_SPECS.values():
        for key in spec.total_keys:
            if key not in keys:
                keys.append(key)
    return keys
