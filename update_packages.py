#!/usr/bin/env python3
"""
update_packages.py

Forces package.json overrides/direct deps to the versions called out by ADO task
descriptions. Transitive deps get a top-level override; direct deps get their spec
updated directly.

Recommended dry run:
  python update_packages.py \\
    --package-json package.json \\
    --csv task_descriptions.csv \\
    --columns title,description,description_html \\
    --workers 8 \\
    --dry-run

Update package.json in place:
  python update_packages.py \\
    --package-json package.json \\
    --csv task_descriptions.csv \\
    --columns title,description,description_html \\
    --workers 8 \\
    --in-place
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from output.node import (
    apply_updates,
    check_and_fix_blocked_versions,
    write_npm_available_versions_txt,
    write_package_json,
    write_package_versions_txt,
)
from parsers.node import (
    collect_direct_entries,
    collect_known_packages,
    extract_ado_package_versions,
    parse_sections,
)
from registry.npm import parallel_npm_versions
from resolver.resolver import highest_ado_criteria_by_major
from shared import log as app_log
from shared.build_validation import validate_node_project_or_rollback
from shared.preflight import check as preflight_check
from shared.utils import ensure_dir, parse_columns, write_csv_rows


def main() -> None:
    preflight_check()
    parser = argparse.ArgumentParser(
        description="Force transitive package versions via package.json overrides based on ADO CSV criteria."
    )
    parser.add_argument("--package-json", required=True, help="Path to package.json")
    parser.add_argument("--csv", required=True, help="ADO CSV with package/version mentions")
    parser.add_argument(
        "--columns",
        default=None,
        help="CSV columns to scan, e.g. title,description,description_html",
    )
    parser.add_argument(
        "--direct-sections",
        default=None,
        help="Direct dependency sections to update. Default: dependencies,devDependencies",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Directory to run npm commands from. Defaults to the directory containing --package-json",
    )
    parser.add_argument("--registry", default=None, help="Optional npm registry URL")
    parser.add_argument("--npm-cmd", default="npm", help="npm command path/name. Default: npm")
    parser.add_argument(
        "--workers", type=int, default=8, help="Parallel npm view workers. Default: 8"
    )
    parser.add_argument(
        "--npm-timeout",
        type=int,
        default=90,
        help="Timeout seconds for each npm call. Default: 90",
    )
    parser.add_argument(
        "--allow-ambiguous-highest-major",
        action="store_true",
        help="If transitive package has multiple ADO majors, force the highest",
    )
    parser.add_argument(
        "--keep-nested-overrides",
        action="store_true",
        help="Do not remove nested overrides for packages forced globally",
    )
    parser.add_argument(
        "--out",
        default="package.forced-overrides.json",
        help="Output package.json path",
    )
    parser.add_argument("--log-dir", default="logs", help="Log directory")
    parser.add_argument("--dry-run", action="store_true", help="Do not write package.json")
    parser.add_argument(
        "--in-place", action="store_true", help="Overwrite package.json and create .bak"
    )
    parser.add_argument(
        "--skip-block-check",
        action="store_true",
        help="Skip Artifactory 403 block check",
    )
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bars")
    parser.add_argument(
        "--skip-build-validation",
        action="store_true",
        help="Do not run npm install / npm run build after writing updates",
    )
    parser.add_argument(
        "--build-timeout",
        type=int,
        default=600,
        help="Timeout seconds for post-update npm build validation. Default: 600",
    )
    parser.add_argument(
        "--claude-model",
        default="haiku",
        help="Claude model alias for resolver. Default: haiku",
    )
    parser.add_argument(
        "--claude-effort",
        default="low",
        help="Claude effort level for resolver. Default: low",
    )
    parser.add_argument(
        "--claude-timeout",
        type=int,
        default=120,
        help="Timeout per claude batch call in seconds. Default: 120",
    )
    parser.add_argument(
        "--claude-workers",
        type=int,
        default=4,
        help="Parallel claude batch workers. Default: 4",
    )
    parser.add_argument(
        "--claude-batch-size",
        type=int,
        default=40,
        help="Tasks per claude call. Default: 40",
    )
    args = parser.parse_args()

    ensure_dir(args.log_dir)
    app_log.setup_file_logging(args.log_dir)
    columns = parse_columns(args.columns)
    direct_sections = parse_sections(args.direct_sections)
    show_progress = not args.no_progress
    project_dir = (
        os.path.abspath(args.project_dir)
        if args.project_dir
        else os.path.dirname(os.path.abspath(args.package_json))
    )

    ado_versions_txt = os.path.join(args.log_dir, "ado-extracted-package-versions.txt")
    npm_versions_txt = os.path.join(args.log_dir, "npm-available-versions.txt")
    npm_errors_csv = os.path.join(args.log_dir, "npm-view-errors.csv")
    direct_changes_csv = os.path.join(args.log_dir, "direct-dependency-version-changes.csv")
    override_changes_csv = os.path.join(args.log_dir, "forced-overrides-changes.csv")
    skipped_csv = os.path.join(args.log_dir, "forced-overrides-skipped.csv")

    original_package_json_text = Path(args.package_json).read_text(encoding="utf-8")
    package_json = json.loads(original_package_json_text)

    direct_entries = collect_direct_entries(package_json, direct_sections)
    known_packages = collect_known_packages(package_json)
    package_versions, _, package_constraints = extract_ado_package_versions(
        args.csv,
        columns,
        known_packages,
        show_progress,
        package_json=package_json,
        claude_model=args.claude_model,
        claude_effort=args.claude_effort,
        claude_timeout=args.claude_timeout,
        claude_workers=args.claude_workers,
        claude_batch_size=args.claude_batch_size,
        npm_cmd=args.npm_cmd,
        project_dir=project_dir,
    )
    criteria = highest_ado_criteria_by_major(package_versions)
    write_package_versions_txt(ado_versions_txt, package_versions, criteria)

    packages = sorted(criteria.keys(), key=str.lower)
    versions_by_package, npm_errors = parallel_npm_versions(
        packages=packages,
        registry=args.registry,
        npm_cmd=args.npm_cmd,
        timeout=args.npm_timeout,
        workers=args.workers,
        show_progress=show_progress,
        cwd=project_dir,
    )
    write_npm_available_versions_txt(npm_versions_txt, packages, versions_by_package)
    write_csv_rows(npm_errors_csv, npm_errors, ["package", "error"])

    direct_changes, override_changes, skipped = apply_updates(
        package_json=package_json,
        direct_entries=direct_entries,
        criteria=criteria,
        package_versions=package_versions,
        versions_by_package=versions_by_package,
        package_constraints=package_constraints,
        allow_ambiguous_highest_major=args.allow_ambiguous_highest_major,
        keep_nested_overrides=args.keep_nested_overrides,
        npm_cmd=args.npm_cmd,
        npm_timeout=args.npm_timeout,
        package_json_dir=project_dir,
        registry=args.registry,
    )

    write_csv_rows(
        direct_changes_csv,
        direct_changes,
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
        override_changes_csv,
        override_changes,
        [
            "package",
            "old_override",
            "new_override",
            "minimum_required",
            "removed_nested_override_paths",
        ],
    )
    write_csv_rows(skipped_csv, skipped, ["package", "reason", "details"])

    block_changes = []
    block_errors = []
    if not args.skip_block_check:
        print("\nChecking selected versions against Artifactory for 403 blocks...")
        block_changes, block_errors = check_and_fix_blocked_versions(
            package_json=package_json,
            direct_sections=direct_sections,
            versions_by_package=versions_by_package,
            registry=args.registry,
            npm_cmd=args.npm_cmd,
            timeout=args.npm_timeout,
            workers=args.workers,
            show_progress=show_progress,
            project_dir=project_dir,
        )
        block_changes_csv = os.path.join(args.log_dir, "block-check-changes.csv")
        block_errors_csv = os.path.join(args.log_dir, "block-check-errors.csv")
        write_csv_rows(
            block_changes_csv,
            block_changes,
            ["package", "blocked_version", "unblocked_version"],
        )
        write_csv_rows(
            block_errors_csv,
            block_errors,
            ["package", "blocked_version", "status", "error"],
        )
        if block_changes:
            print(f"  Bumped {len(block_changes)} blocked version(s):")
            for ch in block_changes:
                print(f"    {ch['package']}: {ch['blocked_version']} -> {ch['unblocked_version']}")
        if block_errors:
            print(
                f"  {len(block_errors)} package(s) could not be unblocked — see {block_errors_csv}"
            )

    if args.dry_run:
        print("Dry run complete. No package.json file written.")
    else:
        output_path = args.package_json if args.in_place else args.out
        write_package_json(package_json, output_path, args.package_json, args.in_place)
        if args.skip_build_validation:
            print("Build validation skipped.")
        elif args.in_place:
            validate_node_project_or_rollback(
                args.package_json,
                original_package_json_text,
                npm_cmd=args.npm_cmd,
                timeout=args.build_timeout,
                direct_changes=direct_changes,
                override_changes=override_changes,
                log_dir=args.log_dir,
            )
        else:
            print(
                "Build validation skipped because updates were written to --out, not applied in place."
            )

    print("\nLogs written:")
    print(f"- ADO extracted package versions: {ado_versions_txt}")
    print(f"- npm/JFrog available versions: {npm_versions_txt}")
    print(f"- npm view errors: {npm_errors_csv}")
    print(f"- direct dependency changes: {direct_changes_csv}")
    print(f"- forced overrides changes: {override_changes_csv}")
    print(f"- skipped: {skipped_csv}")

    print("\nCounts:")
    print(f"- ADO packages extracted: {len(package_versions)}")
    print(f"- packages queried via npm/JFrog: {len(packages)}")
    print(f"- direct dependency changes: {len(direct_changes)}")
    print(f"- forced override changes: {len(override_changes)}")
    print(f"- skipped: {len(skipped)}")
    if not args.skip_block_check:
        print(f"- block-check bumps: {len(block_changes)}")
        print(f"- block-check unresolvable: {len(block_errors)}")

    if override_changes:
        print("\nFirst 30 forced overrides:")
        for change in override_changes[:30]:
            print(
                f"- {change['package']}: {change['old_override'] or '(none)'} -> {change['new_override']}"
            )

    print(
        "\nNext step: run `npm install --production` and check logs/npm-view-errors.csv if packages were missed."
    )


if __name__ == "__main__":
    main()
