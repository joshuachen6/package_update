from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from managers import EcosystemUpdateResult

if TYPE_CHECKING:
    from managers import WritePlan

GRADLE_BLOCK_CHECK_CONFIGURATIONS = (
    "runtimeClasspath",
    "compileClasspath",
    "testRuntimeClasspath",
    "testCompileClasspath",
)


@dataclass
class GradleParsed:
    file_path: str
    build_text: str
    deps: list
    repo_urls: list = field(default_factory=list)


@dataclass
class GradleTree:
    installed: dict
    parents_of: dict
    bumped: dict
    project_dir: str
    gradle_cmd: str
    base_url: str
    auth: tuple | None
    prefetched_versions: dict = field(default_factory=dict)
    tree_failed: bool = False
    repo_urls: list = field(default_factory=list)


@dataclass
class GradleVersionSet:
    versions_by_key: dict
    fetch_errors: list = field(default_factory=list)


class GradleParser:
    def parse(self, file_path: str) -> GradleParsed:
        from parsers.gradle import parse_gradle_deps, parse_gradle_repositories

        build_text = Path(file_path).read_text(encoding="utf-8")
        deps = parse_gradle_deps(build_text)
        print(f"Found {len(deps)} dependency declarations in {file_path}")

        repo_urls = parse_gradle_repositories(build_text)
        # Also check settings.gradle / settings.gradle.kts for dependencyResolutionManagement repos
        project_dir = Path(file_path).parent
        for settings_name in ("settings.gradle", "settings.gradle.kts"):
            settings_path = project_dir / settings_name
            if settings_path.exists():
                settings_text = settings_path.read_text(encoding="utf-8")
                for url in parse_gradle_repositories(settings_text):
                    if url not in repo_urls:
                        repo_urls.append(url)
                break

        if repo_urls:
            print(f"  Detected {len(repo_urls)} maven repo(s): {', '.join(repo_urls)}")

        return GradleParsed(file_path=file_path, build_text=build_text, deps=deps, repo_urls=repo_urls)

    def resolve_tree(self, file_path: str, parsed: GradleParsed, cfg: Any, log_dir: str) -> GradleTree:
        from parsers.gradle import has_unresolved_repo_url, parallel_fetch_versions
        from parsers.gradle_tree import (
            _REPO_URL_MARKER,
            extract_resolved_repo_urls,
            get_gradle_cmd,
            parse_gradle_dep_tree,
            run_gradle_dependencies_with_fallback,
        )

        art_src = cfg.artifactory_source.rstrip("/")
        if not art_src:
            raise RuntimeError("Artifactory Source URL is required for Gradle updates.")
        base_url = f"{art_src}/{cfg.artifactory_repo}".rstrip("/")
        auth: tuple | None = (
            (cfg.artifactory_username, cfg.artifactory_password)
            if cfg.artifactory_username else None
        )

        avail, _ = parallel_fetch_versions(
            parsed.deps, base_url, auth, cfg.gradle_timeout, cfg.workers, True
        )

        project_dir = os.path.dirname(os.path.abspath(file_path))
        gradle_cmd = get_gradle_cmd(project_dir)
        dependency_tree_timeout = max(cfg.gradle_timeout, 180)
        print(f"Resolving Gradle dependency tree... timeout={dependency_tree_timeout}s")

        # Only pay for --init-script (invalidates Gradle's configuration
        # cache on every run) when this build actually has something worth
        # resolving via Gradle itself — most repos declare literal repo URLs
        # that the regex parse already handles fine.
        resolve_repo_urls = has_unresolved_repo_url(parsed.build_text)

        tree_outputs: list[str] = []
        tree_err = None
        bumped: dict[str, str] = {}

        def _run_config(configuration: str):
            return run_gradle_dependencies_with_fallback(
                project_dir=project_dir,
                build_file=file_path,
                deps=parsed.deps,
                available_by_key=avail,
                base_url=base_url,
                auth=auth,
                gradle_cmd=gradle_cmd,
                timeout=dependency_tree_timeout,
                configuration=configuration,
                resolve_repo_urls=resolve_repo_urls,
            )

        # Run Gradle configurations sequentially. Concurrent wrapper
        # processes in the same checkout contend over Gradle state and can
        # terminate one another's single-use daemons.
        config_errors: list[str] = []
        for configuration in GRADLE_BLOCK_CHECK_CONFIGURATIONS:
            cfg_tree_output, cfg_tree_err, cfg_bumped = _run_config(
                configuration
            )
            if isinstance(cfg_bumped, dict):
                bumped.update(cfg_bumped)
            if cfg_tree_output:
                tree_outputs.append(cfg_tree_output)
            elif cfg_tree_err:
                config_errors.append(
                    f"[{configuration}]\n{cfg_tree_err}"
                )
        # Missing configurations are expected in some Gradle projects and
        # must not invalidate trees resolved from supported configurations.
        if not tree_outputs and config_errors:
            tree_err = "\n\n".join(config_errors)
        tree_output = "\n".join(tree_outputs) if tree_outputs else None

        installed: dict = {}
        parents_of: dict = {}

        if tree_err:
            err_log = os.path.join(log_dir, "gradle-dependency-tree-error.txt")
            Path(err_log).write_text(tree_err, encoding="utf-8")
            if not tree_output:
                first_lines = chr(10).join(tree_err.splitlines()[:6])
                print(f"  WARNING: gradle dependencies failed - see {err_log}")
                print(f"  {first_lines}")
        resolved_repo_urls: list[str] = []
        if tree_output:
            resolved_repo_urls = extract_resolved_repo_urls(tree_output)
            # Strip the init script's marker lines before writing/parsing so
            # the tree file stays a clean artifact for the JFrog audit and
            # for human review — parse_gradle_dep_tree already ignores them,
            # but there's no reason to let them linger in the log.
            tree_output = "\n".join(
                line
                for line in tree_output.splitlines()
                if not line.strip().startswith(_REPO_URL_MARKER)
            )
            tree_log = os.path.join(log_dir, "gradle-dependency-tree.txt")
            Path(tree_log).write_text(tree_output, encoding="utf-8")
            print(f"  Dependency tree -> {tree_log}")
            installed, parents_of = parse_gradle_dep_tree(tree_output)
            bumped_note = f" (bumped: {', '.join(bumped)})" if bumped else ""
            print(f"  {len(installed)} packages in dependency tree{bumped_note}")
        else:
            print("  WARNING: no dependency tree output - transitive analysis skipped")

        # Prefer URLs Gradle itself resolved (env vars, gradle.properties, -P
        # flags all evaluated) over the regex-based parse from GradleParser.parse,
        # which returns unresolved property references like "${ARTIFACTORY_SOURCE}"
        # verbatim when a repo declaration uses one. Falls back to the regex parse
        # when the tree failed entirely (nothing to extract from).
        repo_urls = resolved_repo_urls or parsed.repo_urls

        return GradleTree(
            installed=installed,
            parents_of=parents_of,
            bumped=bumped,
            project_dir=project_dir,
            gradle_cmd=gradle_cmd,
            base_url=base_url,
            auth=auth,
            prefetched_versions=avail,
            tree_failed=tree_output is None,
            repo_urls=repo_urls,
        )


class GradleRegistry:
    def fetch_versions(self, packages: list, cfg: Any, prefetched: dict | None = None) -> GradleVersionSet:
        from parsers.gradle import parallel_fetch_versions

        if prefetched:
            needed = {f"{dep.group}:{dep.artifact}" for dep in packages}
            versions_by_key = {k: v for k, v in prefetched.items() if k in needed}
            missing = [dep for dep in packages if f"{dep.group}:{dep.artifact}" not in versions_by_key]
            if not missing:
                return GradleVersionSet(versions_by_key=versions_by_key)
            packages = missing

        art_src = cfg.artifactory_source.rstrip("/")
        base_url = f"{art_src}/{cfg.artifactory_repo}".rstrip("/")
        auth: tuple | None = (
            (cfg.artifactory_username, cfg.artifactory_password)
            if cfg.artifactory_username else None
        )

        fetched, fetch_errors = parallel_fetch_versions(
            packages, base_url, auth, cfg.gradle_timeout, cfg.workers, True
        )
        if prefetched:
            fetched.update(versions_by_key)
        return GradleVersionSet(versions_by_key=fetched, fetch_errors=fetch_errors)


class GradleOutput:
    def apply_updates(
        self,
        parsed: GradleParsed,
        tree: GradleTree,
        versions: GradleVersionSet,
        cve_packages: set[str],
        cfg: Any,
        log_dir: str | None = None,
    ) -> EcosystemUpdateResult:
        from output.gradle import apply_updates
        from parsers.gradle import parallel_fetch_versions
        from shared.utils import build_display_change, build_skipped_entry

        avail = dict(versions.versions_by_key)
        fetch_errs = list(versions.fetch_errors)

        base_url = tree.base_url
        auth = tree.auth

        known_full_keys = (
            {f"{d.group}:{d.artifact}" for d in parsed.deps}
            | set(tree.installed.keys())
        )

        package_constraints: dict[str, str] = {}
        skipped_absent: list[str] = []
        for raw_pkg in sorted(cve_packages):
            if ":" in raw_pkg:
                if raw_pkg in known_full_keys:
                    package_constraints[raw_pkg] = ">"
                else:
                    skipped_absent.append(raw_pkg)
                continue
            matches = sorted(k for k in known_full_keys if k.split(":")[-1] == raw_pkg)
            if matches:
                for match in matches:
                    package_constraints[match] = ">"
            else:
                skipped_absent.append(raw_pkg)

        if skipped_absent:
            print(
                "Skipping JFrog package(s) not present in this Gradle build file or "
                "its resolved dependency tree: " + ", ".join(skipped_absent)
            )

        vulnerable_packages = set(package_constraints.keys())

        extra_fetch_deps = []
        extra_seen: set[str] = set()
        for raw_key in sorted(package_constraints):
            if ":" not in raw_key:
                continue
            if raw_key in avail or raw_key in extra_seen:
                continue
            group, artifact = raw_key.split(":", 1)
            extra_fetch_deps.append(SimpleNamespace(
                config="", group=group, artifact=artifact,
                version="", original="", match_start=0, match_end=0,
            ))
            extra_seen.add(raw_key)

        if extra_fetch_deps:
            print(f"Fetching Artifactory versions for {len(extra_fetch_deps)} JFrog package(s)...")
            extra_avail, extra_fetch_errs = parallel_fetch_versions(
                extra_fetch_deps, base_url, auth, cfg.gradle_timeout, cfg.workers, True
            )
            avail.update(extra_avail)
            if extra_fetch_errs:
                fetch_errs.extend(extra_fetch_errs)

        changes, skipped, force_entries = apply_updates(
            deps=parsed.deps,
            remediation_by_key={},
            available_by_key=avail,
            package_constraints=package_constraints,
            installed=tree.installed,
            parents_of=tree.parents_of,
            build_file=parsed.file_path,
            base_url=base_url,
            auth=auth,
            gradle_cmd=tree.gradle_cmd,
            timeout=cfg.gradle_timeout,
            skip_block_check=getattr(cfg, "skip_block_check", False),
            show_progress=True,
            xray_host=getattr(cfg, "xray_host", None) or base_url,
            workers=getattr(cfg, "workers", 8),
            repo_urls=tree.repo_urls or None,
            log_dir=log_dir,
        )

        bumped_items = sorted(tree.bumped.items()) if isinstance(tree.bumped, dict) else []
        direct_by_key = {f"{dep.group}:{dep.artifact}": dep for dep in parsed.deps}
        existing_changes = {row.get("dependency") for row in changes}
        existing_forces = {row.get("dependency") for row in force_entries}

        for dependency, forced_version in bumped_items:
            if dependency in existing_changes or dependency in existing_forces:
                continue
            direct_dep = direct_by_key.get(dependency)
            if direct_dep is not None:
                replacement = direct_dep.original.replace(direct_dep.version, forced_version, 1)
                changes.append({
                    "dependency": dependency,
                    "config": direct_dep.config,
                    "old_version": direct_dep.version,
                    "new_version": forced_version,
                    "remediation_guided": "blocked-version-fallback",
                    "original": direct_dep.original,
                    "replacement": replacement,
                })
                existing_changes.add(dependency)
            old_version = (
                direct_dep.version if direct_dep is not None
                else str(tree.installed.get(dependency, ""))
            )
            force_entries.append({
                "dependency": dependency,
                "old_version": old_version,
                "new_version": forced_version,
                "minimum_required": forced_version,
            })
            existing_forces.add(dependency)

        print()
        print(
            f"Gradle counts: deps={len(parsed.deps)}, updated={len(changes)}, "
            f"forced={len(force_entries)}, skipped={len(skipped)}"
        )

        display_changes = [
            build_display_change(
                row.get("dependency", ""),
                row.get("old_version", ""),
                row.get("new_version", ""),
                "gradle",
                bool(row.get("remediation_guided")) or row.get("dependency", "") in vulnerable_packages,
            )
            for row in changes
        ] + [
            build_display_change(
                row.get("dependency", ""),
                row.get("old_version", ""),
                row.get("new_version", ""),
                "gradle-force",
                True,
            )
            for row in force_entries
        ]

        skipped_display = [
            build_skipped_entry(
                row.get("dependency", ""),
                row.get("current", ""),
                row.get("target", ""),
                row.get("reason", ""),
            )
            for row in skipped
        ]

        return EcosystemUpdateResult(
            display_changes=display_changes,
            skipped_display=skipped_display,
            extra={
                "build_text": parsed.build_text,
                "changes": changes,
                "force_entries": force_entries,
                "skipped_raw": skipped,
                "build_file": parsed.file_path,
                "fetch_errors": fetch_errs,
                "version_inventory": {
                    dependency: [
                        str(version)
                        for version in avail.get(dependency, [])
                    ]
                    for dependency in sorted(vulnerable_packages)
                },
            },
        )

    def write_logs(self, log_dir: str, result: EcosystemUpdateResult) -> None:
        from shared.utils import write_csv_rows

        extra = result.extra
        write_csv_rows(
            os.path.join(log_dir, "gradle-fetch-errors.csv"),
            extra.get("fetch_errors", []),
            ["dependency", "error"],
        )
        write_csv_rows(
            os.path.join(log_dir, "gradle-version-changes.csv"),
            extra.get("changes", []),
            ["dependency", "config", "old_version", "new_version", "remediation_guided"],
        )
        write_csv_rows(
            os.path.join(log_dir, "gradle-skipped.csv"),
            extra.get("skipped_raw", []),
            ["dependency", "reason", "current", "target"],
        )
        write_csv_rows(
            os.path.join(log_dir, "gradle-force-overrides.csv"),
            extra.get("force_entries", []),
            ["dependency", "old_version", "new_version", "minimum_required"],
        )


class GradleManager:
    ecosystem = "maven"
    type = "gradle"
    label = "Gradle"
    explicit_arg_attr = "build_files"
    explicit_arg_name = "--build-file"
    explicit_arg_help = "Explicit build.gradle file to update. Can be passed multiple times."
    total_keys = ("gradle_direct", "gradle_force", "skipped")

    parser = GradleParser()
    registry = GradleRegistry()
    output = GradleOutput()

    def packages_to_fetch(
        self, parsed: GradleParsed, tree: GradleTree, cve_packages: set[str]
    ) -> list:
        return parsed.deps

    def summarize(self, result: dict) -> dict[str, int]:
        return {
            "gradle_direct": sum(
                1 for row in result.get("display_changes", []) if row.get("change_type") == "gradle"
            ),
            "gradle_force": sum(
                1 for row in result.get("display_changes", []) if row.get("change_type") == "gradle-force"
            ),
            "skipped": len(result.get("skipped_display", [])),
        }

    def analyze(self, cfg: Any, manager: dict, log_dir: str, cve_packages: set[str]) -> dict:
        from pipeline.runner import run_analysis

        cfg_ns = SimpleNamespace(
            artifactory_source=cfg.artifactory_source,
            artifactory_repo=cfg.artifactory_repo,
            artifactory_username=cfg.artifactory_username,
            artifactory_password=cfg.artifactory_password,
            workers=cfg.workers,
            gradle_timeout=cfg.gradle_timeout,
            skip_block_check=cfg.skip_block_check,
            xray_host=cfg.artifactory_source,
            skip_build_validation=getattr(cfg, "skip_build_validation", True),
        )
        return run_analysis(self, manager["file_path"], log_dir, cve_packages, cfg_ns)

    def make_write_plan(self, cfg: Any, result: dict, log_dir: str | None) -> WritePlan:
        from managers import WritePlan
        from output.gradle import write_gradle_file
        from parsers.gradle_tree import get_gradle_cmd
        from shared.build_validation import validate_gradle_project_or_rollback

        path = result.get("build_file") or result.get("file_path", "")
        build_text = result.get("build_text", "")
        changes = result.get("changes", [])
        force_entries = result.get("force_entries", [])

        # The gradle-evaluated repo URLs live on the GradleTree from resolve_tree
        # (result["_tree"]). Phase 2 replay reloads `result` from a JSON cache that
        # strips _tree (it isn't serializable), so this is None there — validation
        # falls back to a regex parse of the build file in that case.
        tree = result.get("_tree")
        repo_urls = list(getattr(tree, "repo_urls", None) or []) or None

        auth = (
            (cfg.artifactory_username, cfg.artifactory_password)
            if getattr(cfg, "artifactory_username", None) else None
        )
        art_src = getattr(cfg, "artifactory_source", "").rstrip("/")
        art_repo = getattr(cfg, "artifactory_repo", "")
        base_url = f"{art_src}/{art_repo}".rstrip("/") if art_src else None
        gradle_cmd = get_gradle_cmd(str(Path(path).resolve().parent))
        timeout = max(1, int(getattr(cfg, "gradle_timeout", 150)))
        xray_host = getattr(cfg, "xray_host", None)

        return WritePlan(
            has_changes=bool(changes or force_entries),
            file_path=path,
            write=lambda: write_gradle_file(
                build_text, changes, force_entries, path, path, in_place=True,
            ),
            validate=lambda: validate_gradle_project_or_rollback(
                path, build_text,
                gradle_cmd=gradle_cmd, timeout=timeout,
                changes=changes, force_entries=force_entries,
                log_dir=log_dir, auth=auth,
                xray_host=xray_host, base_url=base_url,
                enable_failure_isolation=getattr(cfg, "enable_failure_isolation", False),
                repo_urls=repo_urls,
            ),
        )

    def write_result(self, cfg: Any, result: dict, log_dir: str) -> None:
        from pipeline.runner import run_write_validate
        run_write_validate(
            self.make_write_plan(cfg, result, log_dir),
            getattr(cfg, "skip_build_validation", False),
        )
