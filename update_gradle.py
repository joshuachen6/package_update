#!/usr/bin/env python3
"""
update_gradle.py

Updates build.gradle dependency versions guided by ADO task descriptions and
Artifactory availability checks.

Credentials are read from environment variables:
  ARTIFACTORY_USERNAME, ARTIFACTORY_PASSWORD, ARTIFACTORY_SOURCE
  ARTIFACTORY_REPO  (default: ins-cp-mgmt-gradle-virtual)

Example:
  python update_gradle.py \\
    --build-file build.gradle \\
    --csv userstory_tasks.csv \\
    --columns title,description \\
    --workers 8 \\
    --dry-run
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from output.gradle import apply_updates, write_gradle_file
from parsers.gradle import (
    _fuzzy_keywords,
    collect_known_packages,
    extract_ado_versions,
    parallel_fetch_versions,
    parse_gradle_deps,
)
from parsers.gradle_tree import (
    get_gradle_cmd,
    parse_gradle_dep_tree,
    run_gradle_dependencies_with_fallback,
)
from shared import log as app_log
from shared.build_validation import validate_gradle_project_or_rollback
from shared.preflight import check as preflight_check
from shared.utils import ensure_dir, parse_columns, write_csv_rows

ARTIFACTORY_USERNAME = os.environ.get("ARTIFACTORY_USERNAME", "")
ARTIFACTORY_PASSWORD = os.environ.get("ARTIFACTORY_PASSWORD", "")
ARTIFACTORY_BASE = os.environ.get("ARTIFACTORY_SOURCE", "").rstrip("/")
ARTIFACTORY_REPO = os.environ.get("ARTIFACTORY_REPO", "ins-cp-mgmt-gradle-virtual")

GRADLE_BLOCK_CHECK_CONFIGURATIONS = (
    "runtimeClasspath",
    "compileClasspath",
    "testRuntimeClasspath",
    "testCompileClasspath",
)


def _auth(username: str, password: str):
    return (username, password) if username else None


def main() -> None:
    preflight_check()
    parser = argparse.ArgumentParser(
        description="Update build.gradle dependency versions using ADO CSV criteria and Artifactory availability."
    )
    parser.add_argument(
        "--build-file",
        default="build.gradle",
        help="Path to build.gradle. Default: build.gradle",
    )
    parser.add_argument("--csv", default=None, help="ADO CSV with package/version mentions")
    parser.add_argument(
        "--columns", default=None, help="CSV columns to scan, e.g. title,description"
    )
    parser.add_argument(
        "--out",
        default="build.gradle.updated",
        help="Output path. Default: build.gradle.updated",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite build.gradle in place (creates .bak)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write output file")
    parser.add_argument("--log-dir", default="logs", help="Log directory. Default: logs")
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Parallel workers for version fetching. Default: 8",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP request timeout seconds. Default: 30",
    )
    parser.add_argument(
        "--skip-block-check",
        action="store_true",
        help="Skip Artifactory accessibility check",
    )
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bars")
    parser.add_argument(
        "--skip-build-validation",
        action="store_true",
        help="Do not run gradle build after writing updates",
    )
    parser.add_argument(
        "--build-timeout",
        type=int,
        default=600,
        help="Timeout seconds for post-update Gradle build validation. Default: 600",
    )
    parser.add_argument("--use-claude", action="store_true", help=argparse.SUPPRESS)
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

    if not ARTIFACTORY_BASE:
        parser.error(
            "ARTIFACTORY_SOURCE environment variable is not set.\n"
            "  export ARTIFACTORY_SOURCE=https://yourcompany.jfrog.io/artifactory"
        )

    base_url = f"{ARTIFACTORY_BASE}/{ARTIFACTORY_REPO}".rstrip("/")
    auth = _auth(ARTIFACTORY_USERNAME, ARTIFACTORY_PASSWORD)
    show_progress = not args.no_progress
    ensure_dir(args.log_dir)
    app_log.setup_file_logging(args.log_dir)
    columns = parse_columns(args.columns)

    ensure_dir(args.log_dir)
    changes_csv = os.path.join(args.log_dir, "gradle-version-changes.csv")
    skipped_csv = os.path.join(args.log_dir, "gradle-skipped.csv")
    fetch_errors_csv = os.path.join(args.log_dir, "gradle-fetch-errors.csv")
    ado_mentions_csv = os.path.join(args.log_dir, "gradle-ado-mentions.csv")

    build_text = Path(args.build_file).read_text(encoding="utf-8")
    deps = parse_gradle_deps(build_text)
    print(f"Found {len(deps)} dependency declarations in {args.build_file}")

    available_by_key, fetch_errors = parallel_fetch_versions(
        deps, base_url, auth, args.timeout, args.workers, show_progress
    )
    if fetch_errors:
        print(f"  WARNING: {len(fetch_errors)} fetch error(s) — see {fetch_errors_csv}")

    project_dir = os.path.dirname(os.path.abspath(args.build_file))
    gradle_cmd = get_gradle_cmd(project_dir)
    dependency_tree_timeout = max(args.timeout, 180)
    print(f"Resolving Gradle dependency tree… timeout={dependency_tree_timeout}s")
    tree_output = None
    tree_err = None
    bumped: dict[str, str] = {}

    for configuration in GRADLE_BLOCK_CHECK_CONFIGURATIONS:
        cfg_tree_output, cfg_tree_err, cfg_bumped = run_gradle_dependencies_with_fallback(
            project_dir=project_dir,
            build_file=args.build_file,
            deps=deps,
            available_by_key=available_by_key,
            base_url=base_url,
            auth=auth,
            gradle_cmd=gradle_cmd,
            timeout=dependency_tree_timeout,
            configuration=configuration,
        )
        if isinstance(cfg_bumped, dict):
            bumped.update(cfg_bumped)
        if cfg_tree_output and tree_output is None:
            tree_output = cfg_tree_output
            tree_err = cfg_tree_err
        elif tree_output is None:
            tree_err = cfg_tree_err
    installed: dict = {}
    parents_of: dict = {}
    if tree_err:
        err_log = os.path.join(args.log_dir, "gradle-dependency-tree-error.txt")
        Path(err_log).write_text(tree_err, encoding="utf-8")
        if not tree_output:
            first_lines = "\n".join(tree_err.splitlines()[:6])
            print(f"  WARNING: gradle dependencies failed — see {err_log}")
            print(f"  {first_lines}")
    if tree_output:
        tree_log = os.path.join(args.log_dir, "gradle-dependency-tree.txt")
        Path(tree_log).write_text(tree_output, encoding="utf-8")
        print(f"  Dependency tree → {tree_log}")
        installed, parents_of = parse_gradle_dep_tree(tree_output)
        bumped_note = f" (bumped: {', '.join(bumped)})" if bumped else ""
        print(f"  {len(installed)} packages in dependency tree{bumped_note}")
    else:
        print("  WARNING: no dependency tree output — transitive analysis skipped")

    ado_by_key = {}
    ado_constraints: dict = {}
    if args.csv:
        known_packages = collect_known_packages(deps, dep_tree_installed=installed)
        ado_by_key, _, ado_constraints = extract_ado_versions(
            args.csv,
            columns,
            known_packages,
            show_progress,
            claude_model=args.claude_model,
            claude_effort=args.claude_effort,
            claude_timeout=args.claude_timeout,
            claude_workers=args.claude_workers,
            claude_batch_size=args.claude_batch_size,
        )
        print(f"ADO versions found for {len(ado_by_key)} package(s)")
        ado_mention_rows = [
            {
                "dependency": key,
                "ado_versions": ", ".join(str(v) for v in sorted(versions)),
                "fuzzy_keywords": ", ".join(sorted(_fuzzy_keywords(key))),
            }
            for key, versions in sorted(ado_by_key.items())
        ]
        write_csv_rows(
            ado_mentions_csv,
            ado_mention_rows,
            ["dependency", "ado_versions", "fuzzy_keywords"],
        )
        print(f"  ADO mentions log: {ado_mentions_csv}")

    changes, skipped, force_entries = apply_updates(
        deps=deps,
        ado_by_key=ado_by_key,
        available_by_key=available_by_key,
        package_constraints=ado_constraints,
        installed=installed,
        parents_of=parents_of,
        build_file=args.build_file,
        base_url=base_url,
        auth=auth,
        gradle_cmd=gradle_cmd,
        timeout=args.timeout,
        skip_block_check=args.skip_block_check,
        show_progress=show_progress,
    )

    write_csv_rows(
        changes_csv,
        changes,
        ["dependency", "config", "old_version", "new_version", "ado_guided"],
    )
    write_csv_rows(skipped_csv, skipped, ["dependency", "reason", "current", "target"])
    write_csv_rows(fetch_errors_csv, fetch_errors, ["dependency", "error"])
    force_csv = os.path.join(args.log_dir, "gradle-force-overrides.csv")
    write_csv_rows(
        force_csv,
        force_entries,
        ["dependency", "old_version", "new_version", "minimum_required"],
    )

    if args.dry_run:
        print("Dry run — no file written.")
    else:
        write_gradle_file(
            build_text, changes, force_entries, args.out, args.build_file, args.in_place
        )
        if args.skip_build_validation:
            print("Build validation skipped.")
        elif args.in_place:
            validate_gradle_project_or_rollback(
                args.build_file,
                build_text,
                gradle_cmd=gradle_cmd,
                timeout=args.build_timeout,
                changes=changes,
                force_entries=force_entries,
                log_dir=args.log_dir,
            )
        else:
            print(
                "Build validation skipped because updates were written to --out, not applied in place."
            )

    print("\nLogs:")
    print(f"  changes:      {changes_csv}")
    print(f"  skipped:      {skipped_csv}")
    if args.csv:
        print(f"  ado mentions: {ado_mentions_csv}")
    print("\nCounts:")
    print(f"  dependencies found:   {len(deps)}")
    print(f"  versions updated:     {len(changes)}")
    print(f"  force overrides:      {len(force_entries)}")
    print(f"  skipped:              {len(skipped)}")

    if changes:
        print("\nChanges:")
        for ch in changes:
            guided = " (ADO)" if ch["ado_guided"] == "yes" else ""
            print(f"  {ch['dependency']}: {ch['old_version']} -> {ch['new_version']}{guided}")


if __name__ == "__main__":
    main()
