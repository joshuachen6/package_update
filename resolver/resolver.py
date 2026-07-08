"""Version selection utilities shared by the Node and Gradle pipelines.

select_best_version picks the single best registry version to target given a set
of ADO-mentioned versions and the list of all available versions for that major.
highest_ado_criteria_by_major reduces a flat set of ADO mentions to one minimum
per major, which is the input format expected by both apply_updates functions.
"""

from __future__ import annotations

from typing import Any


def select_best_version(
    ado_versions: set[Any],
    available: list,
    major: int,
    constraint: str = ">=",
    current: Any | None = None,
) -> Any | None:
    """
    Select the best registry version for the installed/current major.

    Existing behavior is preserved when current is not provided: choose the best
    version within the requested major.

    When current is provided, never cross its major. If ADO also mentions a
    version in the current minor line, prefer that minor line first. For example,
    current 4.1.x with ADO mentions 4.1.133 and 4.2.13 should try 4.1.x first.
    If ADO has no version in the current minor line, a newer minor within the
    same major is allowed. The major is never changed.
    """
    ado_for_major = {v for v in ado_versions if v.major == major}
    if not ado_for_major:
        return None

    current_minor = getattr(current, "minor", None)
    if current_minor is None:
        ado_candidates = ado_for_major
        selected_minor = None
    else:
        ado_for_current_minor = {
            v for v in ado_for_major if getattr(v, "minor", None) == current_minor
        }
        ado_candidates = ado_for_current_minor or ado_for_major
        selected_minor = (
            current_minor if ado_for_current_minor else getattr(max(ado_candidates), "minor", None)
        )

    minimum = max(ado_candidates)
    available_strs = {str(v) for v in available}

    def allowed_available(v: Any) -> bool:
        if v.major != major:
            return False
        if current_minor is None:
            return True
        return getattr(v, "minor", None) == selected_minor

    if constraint == ">":
        exact = sorted(
            (
                v
                for v in ado_candidates
                if str(v) in available_strs and allowed_available(v) and v > minimum
            ),
            reverse=True,
        )
        candidates = [v for v in available if allowed_available(v) and v > minimum]
    else:
        exact = sorted(
            (v for v in ado_candidates if str(v) in available_strs and allowed_available(v)),
            reverse=True,
        )
        candidates = [v for v in available if allowed_available(v) and v >= minimum]

    if exact:
        return exact[0]
    return max(candidates) if candidates else None


def highest_ado_criteria_by_major(
    package_versions: dict[str, set[Any]],
) -> dict[str, dict[int, Any]]:
    """
    For each package, returns the highest ADO-mentioned version per major.
    Result: {package: {major: highest_version}}
    """
    criteria: dict[str, dict[int, Any]] = {}
    for package, versions in package_versions.items():
        for version in versions:
            current = criteria.setdefault(package, {}).get(version.major)
            if current is None or version > current:
                criteria[package][version.major] = version
    return criteria
