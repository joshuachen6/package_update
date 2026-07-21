from __future__ import annotations

import contextlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from managers import EcosystemUpdateResult

if TYPE_CHECKING:
    from managers import WritePlan


@dataclass
class NpmParsed:
    file_path: str
    project_dir: str
    pkg: dict
    direct_entries: list
    sections: list


@dataclass
class NpmTree:
    lockfile: dict | None
    project_dir: str


@dataclass
class NpmFetchRequest:
    packages: list[str]
    project_dir: str


@dataclass
class NpmVersionSet:
    versions_by_package: dict
    fetch_errors: list = field(default_factory=list)


class NpmParser:
    def parse(self, file_path: str) -> NpmParsed:
        from parsers.node import collect_direct_entries, parse_sections

        project_dir = os.path.dirname(os.path.abspath(file_path))
        sections = parse_sections(None)
        with open(file_path, encoding="utf-8") as fh:
            pkg = json.load(fh)
        direct_entries = collect_direct_entries(pkg, sections)
        return NpmParsed(
            file_path=file_path,
            project_dir=project_dir,
            pkg=pkg,
            direct_entries=direct_entries,
            sections=sections,
        )

    def resolve_tree(self, file_path: str, parsed: NpmParsed, cfg: Any, log_dir: str) -> NpmTree:
        from parsers.node import _load_or_generate_lockfile

        lockfile = _load_or_generate_lockfile(
            parsed.project_dir, parsed.pkg, cfg.npm_cmd, max(cfg.npm_timeout, 180)
        )
        if lockfile is not None:
            with contextlib.suppress(Exception):
                Path(log_dir).joinpath("npm-dependency-tree.json").write_text(
                    json.dumps(lockfile), encoding="utf-8"
                )
        return NpmTree(lockfile=lockfile, project_dir=parsed.project_dir)


class NpmRegistry:
    def fetch_versions(self, packages: NpmFetchRequest, cfg: Any) -> NpmVersionSet:
        from parsers.node import parallel_npm_versions

        versions_by_package, fetch_errors = parallel_npm_versions(
            packages=packages.packages,
            registry=cfg.npm_registry,
            npm_cmd=cfg.npm_cmd,
            timeout=cfg.npm_timeout,
            workers=cfg.workers,
            show_progress=True,
            cwd=packages.project_dir,
        )
        return NpmVersionSet(versions_by_package=versions_by_package, fetch_errors=fetch_errors)


class NpmOutput:
    def apply_updates(
        self,
        parsed: NpmParsed,
        tree: NpmTree,
        versions: NpmVersionSet,
        cve_packages: set[str],
        cfg: Any,
        log_dir: str | None = None,
    ) -> EcosystemUpdateResult:
        from output.node import apply_updates
        from parsers.node import (
            get_lockfile_installed_version,
            parallel_npm_versions,
            should_skip_spec,
        )
        from shared.semver import SemVer
        from shared.utils import build_display_change, build_skipped_entry

        lockfile = tree.lockfile
        versions_by_pkg = dict(versions.versions_by_package)
        all_fetch_errors = list(versions.fetch_errors)

        package_versions: dict[str, set] = {}
        package_constraints: dict[str, str] = {}
        criteria: dict[str, dict] = {}

        for package in sorted(cve_packages):
            current = get_lockfile_installed_version(lockfile, package)
            if current is None:
                continue
            package_versions.setdefault(package, set()).add(current)
            package_constraints[package] = ">"
            criteria.setdefault(package, {})[current.major] = current

        extra_pkgs = [
            entry.package
            for entry in parsed.direct_entries
            if entry.package not in versions_by_pkg and not should_skip_spec(entry.spec)
        ]
        if extra_pkgs:
            print(f"Pre-fetching npm versions for {len(extra_pkgs)} direct deps...")
            extra_versions, extra_errs = parallel_npm_versions(
                packages=extra_pkgs,
                registry=cfg.npm_registry,
                npm_cmd=cfg.npm_cmd,
                timeout=cfg.npm_timeout,
                workers=cfg.workers,
                show_progress=True,
                cwd=parsed.project_dir,
            )
            versions_by_pkg.update(extra_versions)
            all_fetch_errors.extend(extra_errs)

        # Each selected version's registry accessibility is verified inline
        # inside apply_updates (matching Gradle/PyPI's write-time check) --
        # there is no separate post-write block-check pass anymore.
        direct_changes, override_changes, skipped, block_changes = apply_updates(
            package_json=parsed.pkg,
            direct_entries=parsed.direct_entries,
            criteria=criteria,
            package_versions=package_versions,
            versions_by_package=versions_by_pkg,
            package_constraints=package_constraints,
            allow_ambiguous_highest_major=False,
            keep_nested_overrides=False,
            npm_cmd=cfg.npm_cmd,
            npm_timeout=cfg.npm_timeout,
            package_json_dir=parsed.project_dir,
            registry=cfg.npm_registry,
            lockfile=lockfile,
            skip_block_check=getattr(cfg, "skip_block_check", False),
            xray_host=getattr(cfg, "xray_host", None),
        )
        block_errors: list = []

        print()
        print(
            f"Node counts: remediation_packages={len(package_versions)}, "
            f"direct={len(direct_changes)}, overrides={len(override_changes)}, skipped={len(skipped)}"
        )

        display_changes: list[dict] = []
        package_to_display_index: dict[str, int] = {}

        for row in direct_changes:
            index = len(display_changes)
            package = row["package"]
            display_changes.append(build_display_change(
                package,
                row.get("old_spec", ""),
                row.get("new_spec", ""),
                "direct",
                package in package_versions or package in cve_packages,
            ))
            package_to_display_index[package] = index

        for row in override_changes:
            index = len(display_changes)
            package = row["package"]
            new_value = row.get("new_override", "")
            if "=" in new_value:
                ov = sorted(set(p.split("=")[-1] for p in new_value.split("; ") if "=" in p))
                new_value = ", ".join(ov) if ov else new_value
            display_changes.append(build_display_change(
                package,
                row.get("old_override", ""),
                new_value,
                "override",
                package in package_versions or package in cve_packages,
            ))
            package_to_display_index[package] = index

        for row in block_changes:
            package = row["package"]
            unblocked = row.get("unblocked_version", "")
            if package in package_to_display_index:
                existing = display_changes[package_to_display_index[package]]
                unblocked_version = SemVer.parse(unblocked)
                existing_match = re.search(r"\d+\.\d+\.\d+", existing.get("new", ""))
                existing_version = SemVer.parse(existing_match.group(0)) if existing_match else None
                if unblocked_version and (
                    existing_version is None or unblocked_version > existing_version
                ):
                    existing["new"] = unblocked
            else:
                display_changes.append(build_display_change(
                    package, row.get("blocked_version", ""), unblocked, "block-fix", False
                ))

        changed_packages = {row["package"] for row in display_changes}
        skipped_display = [
            build_skipped_entry(
                row.get("package", ""),
                row.get("current", ""),
                row.get("target", ""),
                row.get("reason", ""),
                row.get("details", ""),
            )
            for row in skipped
            if row.get("package", "") not in changed_packages
        ]

        return EcosystemUpdateResult(
            display_changes=display_changes,
            skipped_display=skipped_display,
            extra={
                "pkg": parsed.pkg,
                "direct_changes": direct_changes,
                "override_changes": override_changes,
                "skipped_raw": skipped,
                "pkg_json_path": parsed.file_path,
                "pkg_json_dir": parsed.project_dir,
                "versions_by_pkg": versions_by_pkg,
                "block_changes": block_changes,
                "block_errors": block_errors,
                "fetch_errors": all_fetch_errors,
            },
        )

    def write_logs(self, log_dir: str, result: EcosystemUpdateResult) -> None:
        from output.node import write_npm_available_versions_txt
        from shared.utils import write_csv_rows

        extra = result.extra
        versions_by_pkg = extra.get("versions_by_pkg", {})
        packages = sorted(versions_by_pkg.keys())

        write_npm_available_versions_txt(
            os.path.join(log_dir, "npm-available-versions.txt"),
            packages,
            versions_by_pkg,
        )
        write_csv_rows(
            os.path.join(log_dir, "npm-view-errors.csv"),
            extra.get("fetch_errors", []),
            ["package", "error"],
        )
        write_csv_rows(
            os.path.join(log_dir, "direct-dependency-version-changes.csv"),
            extra.get("direct_changes", []),
            ["package", "section", "old_spec", "new_spec", "minimum_required", "selected_version", "path"],
        )
        write_csv_rows(
            os.path.join(log_dir, "forced-overrides-changes.csv"),
            extra.get("override_changes", []),
            ["package", "old_override", "new_override", "minimum_required", "removed_nested_override_paths"],
        )
        write_csv_rows(
            os.path.join(log_dir, "forced-overrides-skipped.csv"),
            extra.get("skipped_raw", []),
            ["package", "reason", "details"],
        )
        write_csv_rows(
            os.path.join(log_dir, "block-check-changes.csv"),
            extra.get("block_changes", []),
            ["package", "blocked_version", "unblocked_version"],
        )
        write_csv_rows(
            os.path.join(log_dir, "block-check-errors.csv"),
            extra.get("block_errors", []),
            ["package", "blocked_version", "status", "error"],
        )


class NpmManager:
    ecosystem = "npm"
    type = "node"
    label = "Node/npm"
    explicit_arg_attr = "package_jsons"
    explicit_arg_name = "--package-json"
    explicit_arg_help = "Explicit package.json file to update. Can be passed multiple times."
    total_keys = ("npm_direct", "npm_override", "skipped")

    parser = NpmParser()
    registry = NpmRegistry()
    output = NpmOutput()

    def packages_to_fetch(
        self, parsed: NpmParsed, tree: NpmTree, cve_packages: set[str]
    ) -> NpmFetchRequest:
        return NpmFetchRequest(
            packages=sorted(cve_packages, key=str.lower),
            project_dir=parsed.project_dir,
        )

    def summarize(self, result: dict) -> dict[str, int]:
        return {
            "npm_direct": sum(
                1 for row in result.get("display_changes", []) if row.get("change_type") == "direct"
            ),
            "npm_override": sum(
                1 for row in result.get("display_changes", []) if row.get("change_type") == "override"
            ),
            "skipped": len(result.get("skipped_display", [])),
        }

    def analyze(self, cfg: Any, manager: dict, log_dir: str, cve_packages: set[str]) -> dict:
        from types import SimpleNamespace

        from pipeline.runner import run_analysis

        cfg_ns = SimpleNamespace(
            npm_cmd=cfg.npm_cmd,
            npm_timeout=cfg.npm_timeout,
            workers=cfg.workers,
            npm_registry=cfg.npm_registry,
            skip_block_check=cfg.skip_block_check,
            xray_host=cfg.artifactory_source,
            skip_build_validation=getattr(cfg, "skip_build_validation", True),
        )
        return run_analysis(self, manager["file_path"], log_dir, cve_packages, cfg_ns)

    def make_write_plan(self, cfg: Any, result: dict, log_dir: str | None) -> WritePlan:
        from pathlib import Path as _Path

        from managers import WritePlan
        from output.node import write_package_json
        from shared.build_validation import validate_node_project_or_rollback

        path = result.get("pkg_json_path") or result.get("file_path", "")
        # Read original before write() is called — captured in closure.
        original_text = _Path(path).read_text(encoding="utf-8")
        pkg = result["pkg"]
        direct_changes = result.get("direct_changes", [])
        override_changes = result.get("override_changes", [])
        npm_cmd = cfg.npm_cmd
        timeout = max(cfg.npm_timeout, 600)

        return WritePlan(
            has_changes=bool(result.get("display_changes")),
            file_path=path,
            write=lambda: write_package_json(pkg, path, path, in_place=True),
            validate=lambda: validate_node_project_or_rollback(
                path, original_text,
                npm_cmd=npm_cmd, timeout=timeout,
                direct_changes=direct_changes,
                override_changes=override_changes,
                log_dir=log_dir,
                enable_failure_isolation=getattr(cfg, "enable_failure_isolation", False),
            ),
        )

    def write_result(self, cfg: Any, result: dict, log_dir: str) -> None:
        from pipeline.runner import run_write_validate
        run_write_validate(
            self.make_write_plan(cfg, result, log_dir),
            getattr(cfg, "skip_build_validation", False),
        )


