"""Apply computed version updates to package.json and write diagnostic artefacts.

apply_updates is the core mutator: it works through the resolved criteria and
edits the package_json dict in place — updating direct dep specs or writing/refreshing
overrides entries. Each selected version's registry accessibility is verified
inline, before it is written (see apply_updates' docstring), the same timing
Gradle and PyPI use — there is no separate post-write block-check pass.

Callers are responsible for serialising the mutated dict with write_package_json.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any

from parsers.node import (
    DirectEntry,
    _load_or_generate_lockfile,
    extract_prefix_and_version,
    find_override_entries,
    find_top_level_dependents_from_lockfile,
    get_lockfile_installed_version,
    remove_nested_override_keys,
    resolve_transitive_with_parent,
    should_skip_spec,
)
from registry.npm import (
    find_unblocked_version,
    is_version_blocked,
    npm_view_versions,
)
from resolver.resolver import select_best_version
from shared.semver import SemVer
from shared.version_search import find_safe_version


def write_package_versions_txt(
    path: str,
    package_versions: dict[str, set[SemVer]],
    criteria: dict[str, dict[int, SemVer]],
) -> None:
    """Write extracted versions and per-major resolved criteria to a human-readable text file."""
    with open(path, "w", encoding="utf-8") as f:
        for package in sorted(package_versions.keys(), key=str.lower):
            versions = sorted(package_versions[package])
            criteria_text = "; ".join(
                f"criteria {major}.x >= {version}"
                for major, version in sorted(criteria.get(package, {}).items())
            )
            f.write(f"{package}: {', '.join(str(v) for v in versions)} | {criteria_text}\n")


def write_npm_available_versions_txt(
    path: str, packages: list[str], versions_by_package: dict[str, list[SemVer]]
) -> None:
    """Write all registry-fetched versions per package to a text file for post-run diagnostics."""
    with open(path, "w", encoding="utf-8") as f:
        for package in packages:
            versions = versions_by_package.get(package, [])
            if versions:
                f.write(f"{package}: {', '.join(str(v) for v in versions)}\n")
            else:
                f.write(f"{package}: (no versions returned by npm view)\n")


def apply_updates(
    package_json: dict[str, Any],
    direct_entries: list[DirectEntry],
    criteria: dict[str, dict[int, SemVer]],
    package_versions: dict[str, set[SemVer]],
    versions_by_package: dict[str, list[SemVer]],
    package_constraints: dict[str, str],
    allow_ambiguous_highest_major: bool,
    keep_nested_overrides: bool,
    npm_cmd: str = "npm",
    npm_timeout: int = 90,
    package_json_dir: str = ".",
    registry: str | None = None,
    lockfile: dict[str, Any] | None = None,
    skip_block_check: bool = False,
    xray_host: str | None = None,
    xray_auth: tuple[str, str] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Mutate package_json in place to satisfy criteria; return
    (direct_changes, override_changes, skipped, block_changes).

    Resolution priority for each criteria package:
      1. Direct dep — update the version spec in dependencies/devDependencies.
      2. Transitive, single major — try bumping a parent direct dep (verified via npm install
         --package-lock-only) so no override is needed.
      3. Transitive, multiple majors — write nested overrides keyed by the lockfile-resolved
         top-level dependents that pull in each major.
      4. Fallback — write or update a flat overrides entry.

    Stale flat overrides that would downgrade an already-compliant direct dep are removed.

    Every write path below reads its version only via `selected_by_major`, so the
    CVE-remediation target's accessibility is verified once, right after it is
    selected below -- matching Gradle/PyPI's inline (write-time, not a separate
    post-write pass) accessibility check. If no accessible same-major substitute
    exists, the original (possibly blocked) target is kept as-is rather than
    dropping the major entirely: unlike Gradle's flatter per-key model, several
    branches below assume every major in `major_map` has a `selected_by_major`
    entry, so dropping one here would risk `next(iter(selected_by_major))`
    crashing downstream on an empty dict for packages with no direct dependency
    and no actionable override. This mirrors today's behavior when nothing
    accessible is found (write the target and let build validation / isolation
    catch it), while every accessible substitute found is now applied here
    instead of reactively.
    """
    direct_by_package = {entry.package: entry for entry in direct_entries}
    direct_dep_names = set(direct_by_package.keys())
    direct_changes: list[dict[str, str]] = []
    override_changes: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    block_changes: list[dict[str, str]] = []

    overrides = package_json.setdefault("overrides", {})
    if not isinstance(overrides, dict):
        skipped.append(
            {
                "package": "",
                "reason": "package.json overrides exists but is not an object",
                "details": str(type(overrides)),
            }
        )
        return direct_changes, override_changes, skipped, block_changes

    # Use the pre-loaded lockfile if provided, otherwise load lazily on first use.
    _lockfile: dict[str, Any] | None = lockfile
    _lockfile_loaded = lockfile is not None

    def _get_lockfile() -> dict[str, Any]:
        nonlocal _lockfile, _lockfile_loaded
        if not _lockfile_loaded:
            _lockfile_loaded = True
            _lockfile = _load_or_generate_lockfile(
                package_json_dir, package_json, npm_cmd, max(npm_timeout, 180)
            )
        return _lockfile or {}

    lock_timeout = max(npm_timeout, 180)

    for package in sorted(criteria.keys(), key=str.lower):
        major_map = criteria[package]
        all_remediation_versions = package_versions.get(package, set())
        available = versions_by_package.get(package, [])
        constraint = package_constraints.get(package, ">=")

        selected_by_major: dict[int, SemVer] = {}
        for major, minimum_required in major_map.items():
            selected = (
                select_best_version(all_remediation_versions, available, major, constraint)
                or minimum_required
            )
            if not skip_block_check:
                # select_best_version only reasons about version numbers -- it
                # has no way to know whether Xray still flags the candidate it
                # picked. Verifying only when that candidate happens to also be
                # registry-blocked used to leave plenty of accessible-but-still
                # -vulnerable picks unverified (observed live: dompurify,
                # fast-uri, js-yaml all landed on a version Xray still flagged
                # after the write, because nothing here ever asked). Same-major
                # forward/backward candidates around `selected`, CVE-filtered
                # then accessibility-probed, mirrors Gradle's inline Case 1
                # check (parsers/gradle.py::find_accessible_version) via the
                # same shared shared.version_search.find_safe_version.
                forward_candidates = sorted(
                    v for v in available if v.major == selected.major and v >= selected
                )[:10]
                backward_candidates = sorted(
                    (v for v in available if v.major == selected.major and v < selected),
                    reverse=True,
                )[:10]

                def _accessible(candidate: SemVer, _package: str = package) -> bool:
                    blocked_flag, _snippet = is_version_blocked(
                        _package, str(candidate), registry, npm_cmd, npm_timeout, package_json_dir
                    )
                    return not blocked_flag

                verified, _search_err = find_safe_version(
                    forward_candidates,
                    backward_candidates,
                    _accessible,
                    "npm",
                    package,
                    xray_host=xray_host,
                    xray_auth=xray_auth,
                    timeout=npm_timeout,
                )
                if verified is not None:
                    if verified != selected:
                        block_changes.append(
                            {
                                "package": package,
                                "blocked_version": str(selected),
                                "unblocked_version": str(verified),
                            }
                        )
                    selected = verified
                # else: nothing in this major is both CVE-clean and accessible.
                # Keep the original target -- see the module docstring for why
                # this major is not dropped from selected_by_major.
            selected_by_major[major] = selected

        if package in direct_by_package:
            entry = direct_by_package[package]
            if should_skip_spec(entry.spec):
                skipped.append(
                    {
                        "package": package,
                        "reason": "direct dependency uses non-registry spec",
                        "details": entry.spec,
                    }
                )
                continue
            prefix, current = extract_prefix_and_version(entry.spec)
            if not current:
                skipped.append(
                    {
                        "package": package,
                        "reason": "direct dependency has no semver current version",
                        "details": entry.spec,
                    }
                )
                continue
            selected = selected_by_major.get(current.major)
            if not selected:
                fallback, fallback_err = find_unblocked_version(
                    package,
                    current,
                    available,
                    registry,
                    npm_cmd,
                    npm_timeout,
                    package_json_dir,
                    xray_host=xray_host,
                    xray_auth=xray_auth,
                )
                if fallback:
                    selected = fallback
                    major_map[current.major] = fallback
                    selected_by_major[current.major] = fallback
                else:
                    skipped.append(
                        {
                            "package": package,
                            "reason": "no criteria for direct dependency current major and no unblocked same-major update found",
                            "details": f"current={current}; {fallback_err}",
                            "current": str(current),
                            "target": "",
                        }
                    )
                    continue
            if current >= selected:
                # Remove any stale flat override — npm overrides apply even to direct
                # deps, so an old pinned override would downgrade the direct dep.
                stale_entries = []
                for override_entry in find_override_entries(overrides, package):
                    stale_v = SemVer.parse(override_entry.spec)
                    if stale_v is not None and stale_v < current:
                        stale_entries.append(override_entry)
                if stale_entries:
                    old_values = []
                    removed_paths = []
                    for override_entry in stale_entries:
                        old_values.append(f"{override_entry.path}={override_entry.spec}")
                        removed_paths.append(override_entry.path)
                        del override_entry.container[override_entry.key]
                    override_changes.append(
                        {
                            "package": package,
                            "old_override": ";".join(old_values),
                            "new_override": "",
                            "minimum_required": str(major_map[current.major]),
                            "removed_nested_override_paths": ";".join(removed_paths),
                        }
                    )
                    continue
                skipped.append(
                    {
                        "package": package,
                        "reason": "direct dependency already meets selected version",
                        "details": f"current={current}, selected={selected}",
                        "current": str(current),
                        "target": str(selected),
                    }
                )
                continue
            new_spec = f"{prefix}{selected}"
            entry.container[entry.key] = new_spec
            # Remove any flat override for this package — it was likely added to force
            # transitive instances and is now superseded by the direct dep being pinned.
            for override_entry in find_override_entries(overrides, package):
                del override_entry.container[override_entry.key]
            direct_changes.append(
                {
                    "package": package,
                    "section": entry.section,
                    "old_spec": entry.spec,
                    "new_spec": new_spec,
                    "minimum_required": str(major_map[current.major]),
                    "selected_version": str(selected),
                    "path": entry.path,
                }
            )
            continue

        # If there's already a flat override for this package, check whether it's
        # adequate before doing any resolver work. A flat override is global — it
        # forces all instances regardless of major, so satisfying the criteria for
        # its own major is sufficient to cover the whole tree.
        existing_override_entries = find_override_entries(overrides, package)
        actionable_override_entries = []
        for override_entry in existing_override_entries:
            existing_v = SemVer.parse(override_entry.spec)
            if existing_v is not None and existing_v.major in major_map:
                actionable_override_entries.append((override_entry, existing_v))

        if actionable_override_entries:
            updates = []
            already_ok_entries = []
            best_available_entries = []
            for override_entry, existing_v in actionable_override_entries:
                min_req = major_map[existing_v.major]
                spec_prefix, _ = extract_prefix_and_version(override_entry.spec)
                if spec_prefix:
                    # Range spec (>=, >, ^, ~): npm resolves to the highest matching version,
                    # so if the range lower-bound already meets the minimum, leave it alone.
                    already_ok = existing_v >= min_req
                else:
                    already_ok = (
                        (existing_v > min_req) if constraint == ">" else (existing_v >= min_req)
                    )
                if already_ok:
                    already_ok_entries.append((override_entry, existing_v, min_req))
                    continue
                target = selected_by_major[existing_v.major]
                if str(target) == override_entry.spec:
                    best_available_entries.append((override_entry, existing_v))
                    continue
                updates.append((override_entry, target, min_req))

            if updates:
                old_values = []
                new_values = []
                minimum_required_values = []
                has_flat_update = False
                for override_entry, target, min_req in updates:
                    is_flat = override_entry.path == f"overrides.{package}"
                    has_flat_update = has_flat_update or is_flat
                    old_values.append(
                        override_entry.spec
                        if is_flat
                        else f"{override_entry.path}={override_entry.spec}"
                    )
                    override_entry.container[override_entry.key] = str(target)
                    new_values.append(str(target) if is_flat else f"{override_entry.path}={target}")
                    minimum_required_values.append(str(min_req))

                # If a flat override is updated, remove duplicate nested pins unless
                # explicitly requested to keep them. If only nested overrides exist,
                # keep and update those nested entries in place.
                removed_paths = []
                if has_flat_update and not keep_nested_overrides:
                    removed_paths = remove_nested_override_keys(overrides, package)

                override_changes.append(
                    {
                        "package": package,
                        "old_override": ";".join(old_values),
                        "new_override": ";".join(new_values),
                        "minimum_required": ";".join(minimum_required_values),
                        "removed_nested_override_paths": ";".join(removed_paths),
                    }
                )
                continue
            if already_ok_entries:
                details = ";".join(
                    f"{entry.path}={entry.spec}" for entry, _, _ in already_ok_entries
                )
                current = ";".join(str(existing_v) for _, existing_v, _ in already_ok_entries)
                target = ";".join(str(min_req) for _, _, min_req in already_ok_entries)
                reason = (
                    "flat override already satisfies guidance criteria"
                    if all(
                        entry.path == f"overrides.{package}" for entry, _, _ in already_ok_entries
                    )
                    else "override already satisfies guidance criteria"
                )
                skipped.append(
                    {
                        "package": package,
                        "reason": reason,
                        "details": details,
                        "current": current,
                        "target": target,
                    }
                )
                continue

            if best_available_entries:
                details = ";".join(
                    f"{entry.path}={entry.spec}" for entry, _ in best_available_entries
                )
                skipped.append(
                    {
                        "package": package,
                        "reason": "override already at best available version",
                        "details": details,
                        "current": details,
                        "target": details,
                    }
                )
                continue

        if len(selected_by_major) > 1:
            dependents_by_major = find_top_level_dependents_from_lockfile(
                package, _get_lockfile(), direct_dep_names
            )
            if dependents_by_major:
                nested_paths: list[str] = []
                installed_versions: set = set()
                lf = _get_lockfile()
                for major, selected in sorted(selected_by_major.items()):
                    for top_dep in sorted(dependents_by_major.get(major, [])):
                        installed_v = get_lockfile_installed_version(lf, package, top_dep)
                        if installed_v is not None:
                            installed_versions.add(str(installed_v))
                            if (
                                installed_v >= selected
                            ):  # override would write same or lower version — skip
                                continue
                        dep_slot = overrides.setdefault(top_dep, {})
                        if not isinstance(dep_slot, dict):
                            continue
                        dep_slot[package] = str(selected)
                        nested_paths.append(f"overrides.{top_dep}.{package}={selected}")
                if nested_paths:
                    override_changes.append(
                        {
                            "package": package,
                            "old_override": "",
                            "new_override": "; ".join(nested_paths),
                            "minimum_required": ", ".join(
                                f"{m}.x>={v}" for m, v in sorted(major_map.items())
                            ),
                            "removed_nested_override_paths": "",
                        }
                    )
                else:
                    skipped.append(
                        {
                            "package": package,
                            "reason": "installed version already satisfies guidance criteria",
                            "details": ", ".join(
                                f"{m}.x installed>={v}" for m, v in sorted(major_map.items())
                            ),
                            "current": ", ".join(sorted(installed_versions)),
                            "target": ", ".join(str(v) for v in sorted(major_map.values())),
                        }
                    )
                continue
            if not allow_ambiguous_highest_major:
                skipped.append(
                    {
                        "package": package,
                        "reason": "multiple majors; lockfile returned no dependents, global override would be ambiguous",
                        "details": ", ".join(
                            f"{m}.x -> {v}" for m, v in sorted(selected_by_major.items())
                        ),
                    }
                )
                continue
            chosen_major = max(selected_by_major.keys())
            selected = selected_by_major[chosen_major]
            minimum_required = major_map[chosen_major]
        else:
            major = next(iter(selected_by_major.keys()))
            selected = selected_by_major[major]
            minimum_required = major_map[major]
        installed_v_for_fallback = get_lockfile_installed_version(_get_lockfile(), package)
        if (
            installed_v_for_fallback is not None
            and installed_v_for_fallback.major not in selected_by_major
        ):
            fallback, fallback_err = find_unblocked_version(
                package,
                installed_v_for_fallback,
                available,
                registry,
                npm_cmd,
                npm_timeout,
                package_json_dir,
                xray_host=xray_host,
                xray_auth=xray_auth,
            )
            if fallback:
                major = installed_v_for_fallback.major
                selected = fallback
                minimum_required = fallback
                major_map[major] = fallback
                selected_by_major = {major: fallback}
            else:
                skipped.append(
                    {
                        "package": package,
                        "reason": "no criteria for installed major and no unblocked same-major update found",
                        "details": f"current={installed_v_for_fallback}; {fallback_err}",
                        "current": str(installed_v_for_fallback),
                        "target": "",
                    }
                )
                continue

        # For single-major transitive packages, prefer updating a parent direct dep
        # over adding a global override. The lockfile tells us which direct deps pull in
        # this package; we then take the latest same-major version of each candidate
        # parent and ask npm's own resolver (--package-lock-only) whether that update
        # would bring every instance of the transitive dep up to the required version.
        did_parent_update = False
        if not selected_by_major:
            installed_candidates = []
            lockfile_obj = _get_lockfile()
            for lock_pkg, meta in (lockfile_obj.get("packages") or {}).items():
                if not lock_pkg.endswith(f"node_modules/{package}"):
                    continue
                installed_v = SemVer.parse(str((meta or {}).get("version", "")))
                if not installed_v:
                    continue
                fallback, _fallback_err = find_unblocked_version(
                    package,
                    installed_v,
                    available,
                    registry,
                    npm_cmd,
                    npm_timeout,
                    package_json_dir,
                    xray_host=xray_host,
                    xray_auth=xray_auth,
                )
                if fallback:
                    installed_candidates.append((installed_v.major, fallback))
            if installed_candidates:
                chosen_major, selected = sorted(installed_candidates, key=lambda r: r[1])[0]
                selected_by_major[chosen_major] = selected
                major_map[chosen_major] = selected
            else:
                skipped.append(
                    {
                        "package": package,
                        "reason": "no criteria for installed major and no unblocked same-major update found",
                        "details": "",
                    }
                )
                continue

        if len(selected_by_major) == 1:
            dependents_by_major = find_top_level_dependents_from_lockfile(
                package, _get_lockfile(), direct_dep_names
            )
            for top_dep in sorted(dependents_by_major.get(major, [])):
                if top_dep not in direct_by_package or top_dep in criteria:
                    continue
                pentry = direct_by_package[top_dep]
                if should_skip_spec(pentry.spec):
                    continue
                prefix, pcurrent = extract_prefix_and_version(pentry.spec)
                if not pcurrent:
                    continue
                avail = versions_by_package.get(top_dep)
                if avail is None:
                    _, avail, _ = npm_view_versions(
                        top_dep, registry, npm_cmd, npm_timeout, package_json_dir
                    )
                candidates = sorted(
                    (v for v in avail if v.major == pcurrent.major and v > pcurrent),
                    reverse=True,
                )
                if not candidates:
                    continue

                op = ">" if constraint == ">" else ">="
                for ptarget in candidates:
                    new_spec = f"{prefix}{ptarget}"
                    resolved = resolve_transitive_with_parent(
                        top_dep,
                        new_spec,
                        pentry.section,
                        package,
                        package_json,
                        npm_cmd,
                        lock_timeout,
                        package_json_dir,
                        registry=registry,
                    )
                    if resolved is None:
                        continue
                    all_satisfied = all(
                        v > minimum_required if constraint == ">" else v >= minimum_required
                        for v in resolved
                    )
                    if not all_satisfied:
                        continue

                    pentry.container[pentry.key] = new_spec
                    direct_changes.append(
                        {
                            "package": top_dep,
                            "section": pentry.section,
                            "old_spec": pentry.spec,
                            "new_spec": new_spec,
                            "minimum_required": f"transitive {package}{op}{minimum_required}",
                            "selected_version": str(ptarget),
                            "path": pentry.path,
                        }
                    )
                    did_parent_update = True
                    break

                if did_parent_update:
                    break

        if did_parent_update:
            continue

        existing_override_entries = find_override_entries(overrides, package)
        parsed_existing_overrides = []
        for override_entry in existing_override_entries:
            old_v = SemVer.parse(override_entry.spec)
            if old_v is not None:
                parsed_existing_overrides.append((override_entry, old_v))
        if parsed_existing_overrides:
            all_ok = all(
                (old_v > selected) if constraint == ">" else (old_v >= selected)
                for _, old_v in parsed_existing_overrides
            )
            if all_ok:
                details = ";".join(
                    f"{override_entry.path}={override_entry.spec}"
                    for override_entry, _ in parsed_existing_overrides
                )
                skipped.append(
                    {
                        "package": package,
                        "reason": "override already satisfies guidance criteria",
                        "details": details,
                        "current": details,
                        "target": str(selected),
                    }
                )
                continue
        installed_v = get_lockfile_installed_version(_get_lockfile(), package)
        if installed_v is not None and installed_v >= selected:
            hoisted_key = f"node_modules/{package}"
            has_vulnerable_nested = False
            for lock_pkg, meta in (_get_lockfile().get("packages") or {}).items():
                if lock_pkg == hoisted_key or not lock_pkg.endswith(hoisted_key):
                    continue
                nested_v = SemVer.parse(str((meta or {}).get("version", "")))
                if nested_v is not None and nested_v < selected:
                    has_vulnerable_nested = True
                    break
            if not has_vulnerable_nested:
                skipped.append(
                    {
                        "package": package,
                        "reason": "installed version already satisfies guidance criteria",
                        "details": str(installed_v),
                        "current": str(installed_v),
                        "target": str(selected),
                    }
                )
                continue
        old_override = ";".join(
            f"{override_entry.path}={override_entry.spec}"
            for override_entry in existing_override_entries
        )
        if existing_override_entries:
            for override_entry in existing_override_entries:
                override_entry.container[override_entry.key] = str(selected)
            new_override = "; ".join(
                f"{override_entry.path}={selected}" for override_entry in existing_override_entries
            )
            removed_paths: list[str] = []
        else:
            overrides[package] = str(selected)
            new_override = str(selected)
            removed_paths = []
            if not keep_nested_overrides:
                removed_paths = remove_nested_override_keys(overrides, package)

        override_changes.append(
            {
                "package": package,
                "old_override": old_override,
                "new_override": new_override,
                "minimum_required": str(minimum_required),
                "removed_nested_override_paths": ";".join(removed_paths),
            }
        )

    return direct_changes, override_changes, skipped, block_changes


def write_package_json(
    package_json: dict[str, Any], output_path: str, source_path: str, in_place: bool
) -> None:
    """Serialise package_json as indented JSON to output_path, creating a .bak of source_path when in_place is True."""
    if in_place:
        backup_path = source_path + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy2(source_path, backup_path)
            print(f"Backup created: {backup_path}")
        else:
            print(f"Backup already exists, not overwritten: {backup_path}")
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(package_json, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Updated package.json written to: {output_path}")
