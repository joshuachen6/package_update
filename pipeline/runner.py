from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.utils import ensure_dir

if TYPE_CHECKING:
    from managers import EcosystemManager, WritePlan


def run_write_validate(plan: WritePlan, skip_build_validation: bool = False) -> bool:
    """Write a file and optionally validate the build, returning True if the file was written.

    This is the single shared write+validate path. Managers provide a WritePlan
    capturing all ecosystem-specific callbacks; this function handles the shared
    orchestration: has-changes guard, write, skip check, validate.
    """
    if not plan.has_changes:
        print(f"Nothing to update for {plan.file_path}.")
        return False
    print(f"Writing {plan.file_path} in place...")
    plan.write()
    if skip_build_validation or plan.validate is None:
        print("Build validation skipped.")
        return True
    plan.validate()
    return True


def run_analysis(
    manager: EcosystemManager,
    file_path: str,
    log_dir: str,
    cve_packages: set[str],
    cfg: Any,
    prefetched_tree: Any = None,
    prefetched_parsed: Any = None,
) -> dict:
    ensure_dir(log_dir)
    parsed = prefetched_parsed if prefetched_parsed is not None else manager.parser.parse(file_path)
    tree = prefetched_tree if prefetched_tree is not None else manager.parser.resolve_tree(file_path, parsed, cfg, log_dir)

    refresh = getattr(manager, "refresh_cves_from_tree", None)
    if callable(refresh):
        cve_packages = refresh(
            parsed,
            tree,
            cve_packages,
            cfg,
            log_dir,
        )

    packages = manager.packages_to_fetch(parsed, tree, cve_packages)
    prefetched = getattr(tree, "prefetched_versions", None)
    versions = manager.registry.fetch_versions(packages, cfg, prefetched) if prefetched is not None \
        else manager.registry.fetch_versions(packages, cfg)
    result = manager.output.apply_updates(parsed, tree, versions, cve_packages, cfg, log_dir)
    manager.output.write_logs(log_dir, result)
    return {
        "display_changes": result.display_changes,
        "skipped_display": result.skipped_display,
        "file_path": file_path,
        "tree_failed": getattr(tree, "tree_failed", False),
        "_tree": tree,
        "_parsed": parsed,
        **result.extra,
    }
