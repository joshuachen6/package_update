from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

GRADLE_BLOCK_CHECK_CONFIGURATIONS = (
    "runtimeClasspath",
    "compileClasspath",
    "testRuntimeClasspath",
    "testCompileClasspath",
)


def analyze_gradle(
    csv_path: str,
    build_file: str,
    log_dir: str,
    columns,
    artifactory_source: str,
    artifactory_repo: str,
    artifactory_username: str = "",
    artifactory_password: str = "",
    workers: int = 8,
    gradle_timeout: int = 30,
    skip_block_check: bool = False,
    xray_host: str | None = None,
) -> dict:
    """Run the full Gradle update pipeline and return display-ready results."""
    from output.gradle import apply_updates
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
    from shared.utils import ensure_dir, write_csv_rows

    ensure_dir(log_dir)
    art_src = artifactory_source.rstrip("/")
    if not art_src:
        raise RuntimeError("Artifactory Source URL is required for Gradle updates.")

    base_url = f"{art_src}/{artifactory_repo}".rstrip("/")
    auth: tuple | None = (
        (artifactory_username, artifactory_password) if artifactory_username else None
    )

    build_text = Path(build_file).read_text(encoding="utf-8")
    deps = parse_gradle_deps(build_text)
    print(f"Found {len(deps)} dependency declarations in {build_file}")

    # Fetch available versions first — needed to find accessible alternatives for 403'd packages
    avail, fetch_errs = parallel_fetch_versions(deps, base_url, auth, gradle_timeout, workers, True)
    if fetch_errs:
        print(f"  WARNING: {len(fetch_errs)} fetch error(s)")
        from loguru import logger

        for row in fetch_errs:
            logger.warning(
                f"Gradle fetch failed for {row.get('dependency', '?')}: {row.get('error', '')}"
            )
    write_csv_rows(
        os.path.join(log_dir, "gradle-fetch-errors.csv"),
        fetch_errs,
        ["dependency", "error"],
    )

    project_dir = os.path.dirname(os.path.abspath(build_file))
    gradle_cmd = get_gradle_cmd(project_dir)
    dependency_tree_timeout = max(gradle_timeout, 180)
    print(f"Resolving Gradle dependency tree… timeout={dependency_tree_timeout}s")
    tree_output = None
    tree_err = None
    bumped: dict[str, str] = {}
    for configuration in GRADLE_BLOCK_CHECK_CONFIGURATIONS:
        cfg_tree_output, cfg_tree_err, cfg_bumped = run_gradle_dependencies_with_fallback(
            project_dir=project_dir,
            build_file=build_file,
            deps=deps,
            available_by_key=avail,
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
        err_log = os.path.join(log_dir, "gradle-dependency-tree-error.txt")
        Path(err_log).write_text(tree_err, encoding="utf-8")
        if not tree_output:
            first_lines = "\n".join(tree_err.splitlines()[:6])
            print(f"  WARNING: gradle dependencies failed — see {err_log}")
            print(f"  {first_lines}")
    if tree_output:
        tree_log = os.path.join(log_dir, "gradle-dependency-tree.txt")
        Path(tree_log).write_text(tree_output, encoding="utf-8")
        print(f"  Dependency tree → {tree_log}")
        installed, parents_of = parse_gradle_dep_tree(tree_output)
        bumped_note = f" (bumped: {', '.join(bumped)})" if bumped else ""
        print(f"  {len(installed)} packages in dependency tree{bumped_note}")
    else:
        print("  WARNING: no dependency tree output — transitive analysis skipped")

    ado_by_key: dict = {}
    ado_task_ids: dict = {}
    ado_constraints: dict = {}
    osv_packages: set = set()
    if csv_path:
        from shared.ado_tags import normalize_task_ids

        known = collect_known_packages(deps, dep_tree_installed=installed)
        ado_by_key, ado_task_ids, ado_constraints, osv_packages = extract_ado_versions(
            csv_path, columns, known, True
        )
        ado_task_ids = normalize_task_ids(ado_task_ids, deps, installed)

        ado_mention_keys = set(ado_by_key) | set(ado_constraints)
        print(f"ADO mentions found for {len(ado_mention_keys)} package(s)")
        ado_rows = [
            {
                "dependency": k,
                "ado_versions": ", ".join(str(v) for v in sorted(ado_by_key.get(k, set()))),
                "constraint": ado_constraints.get(k, ""),
                "fuzzy_keywords": ", ".join(sorted(_fuzzy_keywords(k))),
            }
            for k in sorted(ado_mention_keys)
        ]
        write_csv_rows(
            os.path.join(log_dir, "gradle-ado-mentions.csv"),
            ado_rows,
            ["dependency", "ado_versions", "constraint", "fuzzy_keywords"],
        )

        # Initial Artifactory version fetch only covers direct build.gradle deps.
        # ADO/Claude can identify transitive Maven coordinates, so fetch versions
        # for any identified package not already in available_by_key before
        # apply_updates selects targets. Include ado_constraints because some CVE
        # tasks name packages without explicit fixed versions; those constraints-only
        # packages still need version metadata for the same-major JFrog fallback.
        known_full_keys = {f"{d.group}:{d.artifact}" for d in deps} | set(installed.keys())
        extra_fetch_deps = []
        extra_seen = set()
        for raw_key in sorted(set(ado_by_key) | set(ado_constraints)):
            candidate_keys = []
            if ":" in raw_key:
                candidate_keys.append(raw_key)
            else:
                candidate_keys.extend(
                    sorted(k for k in known_full_keys if k.split(":")[-1] == raw_key)
                )

            for full_key in candidate_keys:
                if full_key in avail or full_key in extra_seen or ":" not in full_key:
                    continue
                group, artifact = full_key.split(":", 1)
                extra_fetch_deps.append(
                    SimpleNamespace(
                        config="",
                        group=group,
                        artifact=artifact,
                        version="",
                        original="",
                        match_start=0,
                        match_end=0,
                    )
                )
                extra_seen.add(full_key)

        if extra_fetch_deps:
            print(
                f"Fetching Artifactory versions for {len(extra_fetch_deps)} ADO/transitive package(s)…"
            )
            extra_avail, extra_fetch_errs = parallel_fetch_versions(
                extra_fetch_deps,
                base_url,
                auth,
                gradle_timeout,
                workers,
                True,
            )
            avail.update(extra_avail)
            if extra_fetch_errs:
                fetch_errs.extend(extra_fetch_errs)
                write_csv_rows(
                    os.path.join(log_dir, "gradle-fetch-errors.csv"),
                    fetch_errs,
                    ["dependency", "error"],
                )

    changes, skipped, force_entries = apply_updates(
        deps=deps,
        ado_by_key=ado_by_key,
        available_by_key=avail,
        package_constraints=ado_constraints,
        installed=installed,
        parents_of=parents_of,
        build_file=build_file,
        base_url=base_url,
        auth=auth,
        gradle_cmd=gradle_cmd,
        timeout=gradle_timeout,
        skip_block_check=skip_block_check,
        show_progress=True,
        xray_host=xray_host or art_src,
    )

    bumped_items = sorted(bumped.items()) if isinstance(bumped, dict) else []
    direct_by_key = {f"{dep.group}:{dep.artifact}": dep for dep in deps}
    existing_changes = {row.get("dependency") for row in changes}
    existing_forces = {row.get("dependency") for row in force_entries}

    for dependency, forced_version in bumped_items:
        if dependency in existing_changes or dependency in existing_forces:
            continue

        direct_dep = direct_by_key.get(dependency)
        if direct_dep is not None:
            replacement = direct_dep.original.replace(direct_dep.version, forced_version, 1)
            changes.append(
                {
                    "dependency": dependency,
                    "config": direct_dep.config,
                    "old_version": direct_dep.version,
                    "new_version": forced_version,
                    "ado_guided": "blocked-version-fallback",
                    "original": direct_dep.original,
                    "replacement": replacement,
                }
            )
            existing_changes.add(dependency)

        old_version = (
            direct_dep.version
            if direct_dep is not None
            else str(installed.get(dependency, ""))
        )
        force_entries.append(
            {
                "dependency": dependency,
                "old_version": old_version,
                "new_version": forced_version,
                "minimum_required": forced_version,
            }
        )
        existing_forces.add(dependency)
    write_csv_rows(
        os.path.join(log_dir, "gradle-version-changes.csv"),
        changes,
        ["dependency", "config", "old_version", "new_version", "ado_guided"],
    )
    write_csv_rows(
        os.path.join(log_dir, "gradle-skipped.csv"),
        skipped,
        ["dependency", "reason", "current", "target"],
    )
    write_csv_rows(
        os.path.join(log_dir, "gradle-force-overrides.csv"),
        force_entries,
        ["dependency", "old_version", "new_version", "minimum_required"],
    )

    print(
        f"\nGradle counts: deps={len(deps)}, updated={len(changes)}, forced={len(force_entries)}, skipped={len(skipped)}"
    )

    from shared.ado_tags import tag_display_changes

    display_changes = []
    for r in changes:
        pkg = r.get("dependency", "")
        display_changes.append(
            {
                "package": pkg,
                "change_type": "gradle",
                "old": r.get("old_version", ""),
                "new": r.get("new_version", ""),
                "ado_guided": bool(r.get("ado_guided")),
                "nlp_resolved": pkg not in osv_packages,
            }
        )
    for r in force_entries:
        pkg = r.get("dependency", "")
        display_changes.append(
            {
                "package": pkg,
                "change_type": "gradle-force",
                "old": r.get("old_version", ""),
                "new": r.get("new_version", ""),
                "ado_guided": True,
                "nlp_resolved": pkg not in osv_packages,
            }
        )
    tag_display_changes(display_changes, ado_task_ids)

    skipped_display = []
    for r in skipped:
        skipped_display.append(
            {
                "package": r.get("dependency", ""),
                "current": r.get("current", ""),
                "target": r.get("target", ""),
                "reason": r.get("reason", ""),
                "detail": "",
            }
        )
    tag_display_changes(skipped_display, ado_task_ids)

    return {
        "display_changes": display_changes,
        "skipped_display": skipped_display,
        "build_text": build_text,
        "changes": changes,
        "force_entries": force_entries,
        "build_file": build_file,
    }
