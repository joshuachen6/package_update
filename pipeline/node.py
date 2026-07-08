"""npm dependency update pipeline.

Single entry point (analyze_node) that wires together parsers, resolver, output,
and the block-check pass.  All heavy work — npm version queries, lockfile generation,
ADO extraction, and override resolution — happens inside the called modules; this
module owns the sequencing and the shape of the dict returned to the GUI/CLI.
"""

from __future__ import annotations

import json
import os
import re


def analyze_node(
    csv_path: str,
    pkg_json_path: str,
    log_dir: str,
    columns,
    npm_cmd: str = "npm",
    npm_timeout: int = 90,
    workers: int = 8,
    registry: str | None = None,
    skip_block_check: bool = False,
    xray_host: str | None = None,
) -> dict:
    """Run the full npm update pipeline and return display-ready results.

    Returns a dict with keys: display_changes, skipped_display, pkg,
    pkg_json_path, pkg_json_dir.  display_changes entries carry package,
    change_type, old, new, ado_guided, nlp_resolved, and ado_task_ids.
    Writes diagnostic CSV/TXT files to log_dir as a side effect.
    """
    from output.node import (
        apply_updates,
        check_and_fix_blocked_versions,
        write_npm_available_versions_txt,
        write_package_versions_txt,
    )
    from parsers.node import (
        _load_or_generate_lockfile,
        collect_direct_entries,
        collect_known_packages,
        extract_ado_package_versions,
        parallel_npm_versions,
        parse_sections,
        should_skip_spec,
    )
    from resolver.resolver import highest_ado_criteria_by_major
    from shared.utils import ensure_dir, write_csv_rows

    ensure_dir(log_dir)
    project_dir = os.path.dirname(os.path.abspath(pkg_json_path))
    sections = parse_sections(None)

    with open(pkg_json_path, encoding="utf-8") as f:
        pkg = json.load(f)

    direct_entries = collect_direct_entries(pkg, sections)
    known = collect_known_packages(pkg)
    pkg_versions, pkg_task_ids, pkg_constraints, osv_packages = extract_ado_package_versions(
        csv_path,
        columns,
        known,
        True,
        package_json=pkg,
        npm_cmd=npm_cmd,
        project_dir=project_dir,
    )
    # Load lockfile once here so apply_updates doesn't need to re-generate it.
    lockfile = _load_or_generate_lockfile(project_dir, pkg, npm_cmd, max(npm_timeout, 180))
    criteria = highest_ado_criteria_by_major(pkg_versions)

    write_package_versions_txt(
        os.path.join(log_dir, "ado-extracted-package-versions.txt"),
        pkg_versions,
        criteria,
    )

    packages = sorted(criteria.keys(), key=str.lower)
    versions_by_pkg, npm_errs = parallel_npm_versions(
        packages=packages,
        registry=registry,
        npm_cmd=npm_cmd,
        timeout=npm_timeout,
        workers=workers,
        show_progress=True,
        cwd=project_dir,
    )
    write_npm_available_versions_txt(
        os.path.join(log_dir, "npm-available-versions.txt"),
        packages,
        versions_by_pkg,
    )
    write_csv_rows(os.path.join(log_dir, "npm-view-errors.csv"), npm_errs, ["package", "error"])

    # Pre-fetch npm versions for direct deps not already covered by ADO criteria so
    # apply_updates never has to make serial npm_view_versions calls inline.
    extra_pkgs = [
        e.package
        for e in direct_entries
        if e.package not in versions_by_pkg and not should_skip_spec(e.spec)
    ]
    if extra_pkgs:
        print(f"Pre-fetching npm versions for {len(extra_pkgs)} direct deps…")
        extra_versions, extra_errs = parallel_npm_versions(
            packages=extra_pkgs,
            registry=registry,
            npm_cmd=npm_cmd,
            timeout=npm_timeout,
            workers=workers,
            show_progress=True,
            cwd=project_dir,
        )
        versions_by_pkg.update(extra_versions)
        npm_errs.extend(extra_errs)

    dc, oc, sk = apply_updates(
        package_json=pkg,
        direct_entries=direct_entries,
        criteria=criteria,
        package_versions=pkg_versions,
        versions_by_package=versions_by_pkg,
        package_constraints=pkg_constraints,
        allow_ambiguous_highest_major=False,
        keep_nested_overrides=False,
        npm_cmd=npm_cmd,
        npm_timeout=npm_timeout,
        package_json_dir=project_dir,
        registry=registry,
        lockfile=lockfile,
    )
    write_csv_rows(
        os.path.join(log_dir, "direct-dependency-version-changes.csv"),
        dc,
        [
            "package",
            "section",
            "old_spec",
            "new_spec",
            "minimum_required",
            "selected_version",
            "path",
        ],
    )
    write_csv_rows(
        os.path.join(log_dir, "forced-overrides-changes.csv"),
        oc,
        [
            "package",
            "old_override",
            "new_override",
            "minimum_required",
            "removed_nested_override_paths",
        ],
    )
    write_csv_rows(
        os.path.join(log_dir, "forced-overrides-skipped.csv"),
        sk,
        ["package", "reason", "details"],
    )

    bc, be = [], []
    if not skip_block_check:
        print("\nBlock-checking versions…")
        bc, be = check_and_fix_blocked_versions(
            package_json=pkg,
            direct_sections=sections,
            versions_by_package=versions_by_pkg,
            registry=registry,
            npm_cmd=npm_cmd,
            timeout=npm_timeout,
            workers=workers,
            show_progress=True,
            project_dir=project_dir,
            xray_host=xray_host,
        )
        write_csv_rows(
            os.path.join(log_dir, "block-check-changes.csv"),
            bc,
            ["package", "blocked_version", "unblocked_version"],
        )
        write_csv_rows(
            os.path.join(log_dir, "block-check-errors.csv"),
            be,
            ["package", "blocked_version", "status", "error"],
        )

    print(
        f"\nNode counts: ADO={len(pkg_versions)}, direct={len(dc)}, overrides={len(oc)}, skipped={len(sk)}"
    )

    from shared.ado_tags import tag_display_changes

    display_changes = []
    pkg_to_display_idx: dict = {}

    for r in dc:
        idx = len(display_changes)
        display_changes.append(
            {
                "package": r["package"],
                "change_type": "direct",
                "old": r.get("old_spec", ""),
                "new": r.get("new_spec", ""),
                "ado_guided": r["package"] in pkg_versions,
                "nlp_resolved": r["package"] not in osv_packages,
            }
        )
        pkg_to_display_idx[r["package"]] = idx

    for r in oc:
        idx = len(display_changes)
        new_val = r.get("new_override", "")
        # Nested overrides store path notation ("overrides.X.Y=ver; ...") — extract unique versions for display.
        if "=" in new_val:
            versions = sorted(set(p.split("=")[-1] for p in new_val.split("; ") if "=" in p))
            new_val = ", ".join(versions) if versions else new_val
        display_changes.append(
            {
                "package": r["package"],
                "change_type": "override",
                "old": r.get("old_override", ""),
                "new": new_val,
                "ado_guided": r["package"] in pkg_versions,
                "nlp_resolved": r["package"] not in osv_packages,
            }
        )
        pkg_to_display_idx[r["package"]] = idx

    for r in bc:
        bpkg = r["package"]
        unblocked = r.get("unblocked_version", "")
        if bpkg in pkg_to_display_idx:
            # Already recorded from ADO analysis — keep whichever new version is higher.
            existing = display_changes[pkg_to_display_idx[bpkg]]
            from shared.semver import SemVer

            unblocked_v = SemVer.parse(unblocked)
            # Extract the first semver from the existing new field (handles "^1.2.3" prefixes).
            existing_m = re.search(r"\d+\.\d+\.\d+", existing.get("new", ""))
            existing_v = SemVer.parse(existing_m.group(0)) if existing_m else None
            if unblocked_v and (existing_v is None or unblocked_v > existing_v):
                existing["new"] = unblocked
        else:
            display_changes.append(
                {
                    "package": bpkg,
                    "change_type": "block-fix",
                    "old": r.get("blocked_version", ""),
                    "new": unblocked,
                    "ado_guided": False,
                    "nlp_resolved": False,
                }
            )

    tag_display_changes(display_changes, pkg_task_ids)

    changed_packages = {r["package"] for r in display_changes}
    skipped_display = []
    for r in sk:
        if r.get("package", "") not in changed_packages:
            skipped_display.append(
                {
                    "package": r.get("package", ""),
                    "current": r.get("current", ""),
                    "target": r.get("target", ""),
                    "reason": r.get("reason", ""),
                    "detail": r.get("details", ""),
                }
            )
    tag_display_changes(skipped_display, pkg_task_ids)

    return {
        "display_changes": display_changes,
        "skipped_display": skipped_display,
        "pkg": pkg,
        "direct_changes": dc,
        "override_changes": oc,
        "pkg_json_path": pkg_json_path,
        "pkg_json_dir": project_dir,
    }
