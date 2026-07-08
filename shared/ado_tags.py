from __future__ import annotations

_SPRING_FRAMEWORK_PROPERTY_KEY = "org.springframework:spring-framework.version"


def _spring_framework_task_ids(task_ids_by_pkg):
    ids = set()
    for pkg, pkg_ids in task_ids_by_pkg.items():
        if pkg.startswith("org.springframework:spring-") and pkg != _SPRING_FRAMEWORK_PROPERTY_KEY:
            ids.update(pkg_ids)
    return ids


def normalize_task_ids(
    task_ids: dict[str, set[int]],
    deps,
    installed: dict,
) -> dict[str, set[int]]:
    """Remap artifact-only keys (e.g. "netty-codec-http") to full group:artifact form.

    Uses `deps` (objects with .group and .artifact) and `installed` (dict keyed by
    group:artifact) to build the mapping.  Keys that are already in group:artifact form
    are left unchanged.
    """
    artifact_to_full: dict[str, str] = {}

    for dep in deps:
        artifact_to_full[dep.artifact] = f"{dep.group}:{dep.artifact}"
    for full_key in installed:
        artifact_to_full.setdefault(full_key.split(":")[-1], full_key)

    out: dict[str, set[int]] = {}
    for k, v in task_ids.items():
        full = k if ":" in k else artifact_to_full.get(k, k)
        out.setdefault(full, set()).update(v)

    return out


def tag_display_changes(
    display_changes: list[dict],
    task_ids_by_pkg: dict[str, set[int]],
) -> None:
    """Stamp a sorted task_ids list onto each display change record in-place.

    Tries both the full group:artifact key and the artifact-only key so that
    records survive any remaining normalization gaps.

    A synthetic spring-framework.version change is tagged with ADO tasks for
    actual Spring Framework modules, e.g. org.springframework:spring-web, but not
    Spring Boot starter tasks.
    """
    for change in display_changes:
        pkg = change.get("package", "")
        artifact_only = pkg.split(":")[-1] if ":" in pkg else pkg
        ids = task_ids_by_pkg.get(pkg) or task_ids_by_pkg.get(artifact_only, set())

        if not ids and pkg == _SPRING_FRAMEWORK_PROPERTY_KEY:
            ids = _spring_framework_task_ids(task_ids_by_pkg)

        change["task_ids"] = sorted(ids)
