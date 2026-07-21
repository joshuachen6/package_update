"""Version selection utilities shared by the Node and Gradle pipelines.

select_best_version picks the single best registry version to target given a set
of remediation-mentioned versions and the list of all available versions for that major.
highest_remediation_criteria_by_major reduces a flat set of remediation mentions to one minimum
per major, which is the input format expected by both apply_updates functions.
"""

from __future__ import annotations

from typing import Any


def select_best_version(
    remediation_versions: set[Any],
    available: list,
    major: int,
    constraint: str = ">=",
    current: Any | None = None,
) -> Any | None:
    """
    Select the best registry version for the installed/current major.

    Existing behavior is preserved when current is not provided: choose the best
    version within the requested major.

    When current is provided, never cross its major. If remediation also mentions a
    version in the current minor line, prefer that minor line first. For example,
    current 4.1.x with remediation mentions 4.1.133 and 4.2.13 should try 4.1.x first.
    If remediation has no version in the current minor line, a newer minor within the
    same major is allowed. The major is never changed.
    """
    remediation_for_major = {v for v in remediation_versions if v.major == major}
    if not remediation_for_major:
        return None

    current_minor = getattr(current, "minor", None)
    if current_minor is None:
        remediation_candidates = remediation_for_major
        selected_minor = None
    else:
        remediation_for_current_minor = {
            v for v in remediation_for_major if getattr(v, "minor", None) == current_minor
        }
        remediation_candidates = remediation_for_current_minor or remediation_for_major
        selected_minor = (
            current_minor if remediation_for_current_minor else getattr(max(remediation_candidates), "minor", None)
        )

    minimum = max(remediation_candidates)
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
                for v in remediation_candidates
                if str(v) in available_strs and allowed_available(v) and v > minimum
            ),
            reverse=True,
        )
        candidates = [v for v in available if allowed_available(v) and v > minimum]
    else:
        exact = sorted(
            (v for v in remediation_candidates if str(v) in available_strs and allowed_available(v)),
            reverse=True,
        )
        candidates = [v for v in available if allowed_available(v) and v >= minimum]

    if exact:
        return exact[0]
    return min(candidates) if candidates else None


def highest_remediation_criteria_by_major(
    package_versions: dict[str, set[Any]],
) -> dict[str, dict[int, Any]]:
    """
    For each package, returns the highest remediation-mentioned version per major.
    Result: {package: {major: highest_version}}
    """
    criteria: dict[str, dict[int, Any]] = {}
    for package, versions in package_versions.items():
        for version in versions:
            current = criteria.setdefault(package, {}).get(version.major)
            if current is None or version > current:
                criteria[package][version.major] = version
    return criteria
