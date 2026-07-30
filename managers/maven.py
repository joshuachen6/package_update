"""Maven POM pipeline manager — pom.xml equivalent of GradleManager.

Reuses:
  registry/maven.py        — Artifactory maven-metadata.xml fetching (unchanged)
  parsers/gradle.py        — parallel_fetch_versions (same Artifactory protocol)
  resolver/resolver.py     — select_best_version (same logic)
  registry/maven.py        — version_accessible block-check probing (same probing)
  shared/build_validation/maven.py — validate_maven_project_or_rollback
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from managers import EcosystemUpdateResult

if TYPE_CHECKING:
    from managers import WritePlan


# Prerelease qualifier pattern — these suffixes mark unstable builds.
# Versions matching this are excluded from the candidate pool so we never
# "downgrade" to an RC / alpha / beta even if it has a higher numeric key.
_PRERELEASE_RE = re.compile(
    r'(?i)[.\-_](?:alpha|beta|rc\d*|snapshot|m\d+|milestone|cr\d*)'
    r'(?:[.\-_]?\d*)?(?:[.\-_]|$)'
)


def _is_stable(mv) -> bool:
    """Return True if the version has no known prerelease qualifier."""
    return not _PRERELEASE_RE.search(mv.raw)


@dataclass
class MavenPomTree:
    installed: dict        # {group:artifact -> MavenVersion}
    parents_of: dict       # {child_key -> {parent_key, ...}}
    project_dir: str
    maven_cmd: str
    base_url: str
    auth: tuple | None
    prefetched_versions: dict = field(default_factory=dict)
    tree_failed: bool = False


@dataclass
class MavenPomVersionSet:
    versions_by_key: dict
    fetch_errors: list = field(default_factory=list)


class MavenPomParser:
    def parse(self, file_path: str):
        from parsers.pom import parse_pom_file
        parsed = parse_pom_file(file_path)
        return parsed

    def resolve_tree(self, file_path: str, parsed: Any, cfg: Any, log_dir: str) -> MavenPomTree:
        from parsers.gradle import parallel_fetch_versions
        from parsers.pom import _extract_repo_ids, get_maven_cmd, parse_maven_dep_tree, run_maven_dependency_tree

        art_src = (getattr(cfg, 'artifactory_source', '') or '').rstrip('/')
        if not art_src:
            raise RuntimeError('Artifactory Source URL is required for Maven POM updates.')
        art_repo = getattr(cfg, 'artifactory_repo', '') or ''
        base_url = f'{art_src}/{art_repo}'.rstrip('/')
        auth: tuple | None = (
            (cfg.artifactory_username, cfg.artifactory_password)
            if getattr(cfg, 'artifactory_username', None) else None
        )

        # Prefetch all known dep versions in parallel (reuse Gradle's parallel fetch)
        avail, _ = parallel_fetch_versions(
            parsed.deps, base_url, auth,
            getattr(cfg, 'maven_timeout', 150),
            getattr(cfg, 'workers', 8),
            True,
        )

        project_dir = os.path.dirname(os.path.abspath(file_path))
        maven_cmd = getattr(cfg, 'maven_cmd', None) or get_maven_cmd(project_dir)
        timeout = max(getattr(cfg, 'maven_timeout', 150), 180)
        print(f'Resolving Maven dependency tree... timeout={timeout}s')

        repo_ids = _extract_repo_ids(parsed.pom_text)
        if repo_ids:
            print(f'  Found repository IDs in pom.xml: {", ".join(repo_ids)}')

        tree_output, tree_err, verbose_log = run_maven_dependency_tree(
            project_dir, file_path, maven_cmd, timeout,
            base_url=base_url,
            auth=auth,
            extra_server_ids=repo_ids,
        )

        installed: dict = {}
        parents_of: dict = {}

        if tree_err:
            err_log = os.path.join(log_dir, 'maven-dependency-tree-error.txt')
            # Write the verbose log (includes -e run output) so the user can
            # see the full Maven error — not just the exit code.
            Path(err_log).write_text(verbose_log or tree_err, encoding='utf-8')
            if not tree_output:
                first_lines = '\n'.join(tree_err.splitlines()[:6])
                print(f'  WARNING: mvn dependency:tree failed — see {err_log}')
                print(f'  {first_lines}')

        if tree_output:
            tree_log = os.path.join(log_dir, 'maven-dependency-tree.txt')
            Path(tree_log).write_text(tree_output, encoding='utf-8')
            print(f'  Dependency tree -> {tree_log}')
            installed, parents_of = parse_maven_dep_tree(tree_output)
            print(f'  {len(installed)} packages in dependency tree')
        else:
            print('  WARNING: no dependency tree output — transitive analysis skipped')

        return MavenPomTree(
            installed=installed,
            parents_of=parents_of,
            project_dir=project_dir,
            maven_cmd=maven_cmd,
            base_url=base_url,
            auth=auth,
            prefetched_versions=avail,
            tree_failed=tree_output is None,
        )


class MavenPomRegistry:
    def fetch_versions(self, packages: list, cfg: Any, prefetched: dict | None = None) -> MavenPomVersionSet:
        from parsers.gradle import parallel_fetch_versions

        if prefetched:
            needed = {f'{dep.group}:{dep.artifact}' for dep in packages}
            versions_by_key = {k: v for k, v in prefetched.items() if k in needed}
            missing = [dep for dep in packages if f'{dep.group}:{dep.artifact}' not in versions_by_key]
            if not missing:
                return MavenPomVersionSet(versions_by_key=versions_by_key)
            packages = missing

        art_src = (getattr(cfg, 'artifactory_source', '') or '').rstrip('/')
        art_repo = getattr(cfg, 'artifactory_repo', '') or ''
        base_url = f'{art_src}/{art_repo}'.rstrip('/')
        auth: tuple | None = (
            (cfg.artifactory_username, cfg.artifactory_password)
            if getattr(cfg, 'artifactory_username', None) else None
        )

        fetched, fetch_errors = parallel_fetch_versions(
            packages, base_url, auth,
            getattr(cfg, 'maven_timeout', 150),
            getattr(cfg, 'workers', 8),
            True,
        )
        if prefetched:
            fetched.update(versions_by_key)
        return MavenPomVersionSet(versions_by_key=fetched, fetch_errors=fetch_errors)


class MavenPomOutput:
    def apply_updates(
        self,
        parsed: Any,
        tree: MavenPomTree,
        versions: MavenPomVersionSet,
        cve_packages: set[str],
        cfg: Any,
        log_dir: str | None = None,
    ) -> EcosystemUpdateResult:
        from shared.maven_version import MavenVersion
        from shared.utils import build_display_change, build_skipped_entry

        avail = dict(versions.versions_by_key)
        fetch_errs = list(versions.fetch_errors)
        base_url = tree.base_url
        auth = tree.auth
        timeout = getattr(cfg, 'maven_timeout', 150)
        skip_block_check = getattr(cfg, 'skip_block_check', False)
        xray_host = getattr(cfg, 'xray_host', None)

        known_full_keys = (
            {f'{d.group}:{d.artifact}' for d in parsed.deps}
            | set(tree.installed.keys())
        )

        # Normalize CVE packages → group:artifact keys
        package_constraints: dict[str, str] = {}
        skipped_absent: list[str] = []
        for raw_pkg in sorted(cve_packages):
            if ':' in raw_pkg:
                if raw_pkg in known_full_keys:
                    package_constraints[raw_pkg] = '>'
                else:
                    skipped_absent.append(raw_pkg)
                continue
            matches = sorted(k for k in known_full_keys if k.split(':')[-1] == raw_pkg)
            if matches:
                for match in matches:
                    package_constraints[match] = '>'
            else:
                skipped_absent.append(raw_pkg)

        if skipped_absent:
            print(
                'Skipping JFrog package(s) not present in this pom.xml or its resolved '
                'dependency tree: ' + ', '.join(skipped_absent)
            )

        # Fetch any CVE packages not yet in version cache
        extra_fetch_deps = []
        extra_seen: set[str] = set()
        for raw_key in sorted(package_constraints):
            if raw_key in avail or raw_key in extra_seen:
                continue
            group, artifact = raw_key.split(':', 1)
            extra_fetch_deps.append(SimpleNamespace(
                group=group, artifact=artifact,
                config='', version='', original='', match_start=0, match_end=0,
            ))
            extra_seen.add(raw_key)
        if extra_fetch_deps:
            from parsers.gradle import parallel_fetch_versions
            extra_avail, extra_errs = parallel_fetch_versions(
                extra_fetch_deps, base_url, auth, timeout,
                getattr(cfg, 'workers', 8), True,
            )
            avail.update(extra_avail)
            if extra_errs:
                fetch_errs.extend(extra_errs)

        # Build a lookup from group:artifact to the best PomDep for this GA
        dep_by_key: dict[str, list] = {}
        for dep in parsed.deps:
            dep_by_key.setdefault(f'{dep.group}:{dep.artifact}', []).append(dep)

        changes: list[dict] = []
        dm_overrides: list[dict] = []
        skipped: list[dict] = []

        for ga_key in sorted(package_constraints):
            group, artifact = ga_key.split(':', 1)
            all_versions = avail.get(ga_key, [])
            if not all_versions:
                skipped.append({
                    'dependency': ga_key,
                    'reason': 'no versions found in Artifactory',
                    'current': str(tree.installed.get(ga_key, '')),
                    'target': '',
                })
                continue

            current_mv = tree.installed.get(ga_key)
            if current_mv is None:
                # Tree failed or package absent from tree — fall back to the
                # pom-declared version so we can compute a meaningful baseline.
                dep_list_for_bl = dep_by_key.get(ga_key, [])
                pom_ver = next((d.version for d in dep_list_for_bl if d.version), None)
                if pom_ver:
                    current_mv = MavenVersion.parse(pom_ver)

            if current_mv is None:
                # No baseline available (purely transitive dep + tree failed).
                # Cannot determine what's "forward" — skip to avoid a random pick.
                skipped.append({
                    'dependency': ga_key,
                    'reason': 'dependency tree failed and no version declared in pom.xml — cannot determine current version',
                    'current': '',
                    'target': '',
                })
                continue

            current_ver_str = str(current_mv)

            # Only consider stable (non-prerelease) versions as candidates.
            stable_versions = [v for v in all_versions if _is_stable(v)]

            # Build candidate lists: same-major above current (forward), higher-major (backward)
            forward_mvs = sorted([v for v in stable_versions if v.major == current_mv.major and v > current_mv])
            backward_mvs = sorted([v for v in stable_versions if v.major > current_mv.major])

            forward = [str(v) for v in forward_mvs[:10]]
            backward = [str(v) for v in backward_mvs[:5]]

            if not forward and not backward:
                skipped.append({
                    'dependency': ga_key,
                    'reason': 'no newer versions found in Artifactory',
                    'current': current_ver_str,
                    'target': '',
                })
                continue

            if skip_block_check:
                target_str = next(iter(forward or backward), None)
                if target_str is None:
                    skipped.append({
                        'dependency': ga_key,
                        'reason': 'no candidate version available',
                        'current': current_ver_str,
                        'target': '',
                    })
                    continue
            else:
                from registry.maven import version_accessible
                from shared.version_search import find_safe_version

                def _accessible(v_str: str, _g: str = group, _a: str = artifact) -> bool:
                    return version_accessible(_g, _a, v_str, base_url, auth, timeout)

                target_str, diag = find_safe_version(
                    forward,
                    backward,
                    _accessible,
                    'maven',
                    f'{group}:{artifact}',
                    xray_host=xray_host,
                    xray_auth=auth,
                    timeout=timeout,
                )
                if target_str is None:
                    skipped.append({
                        'dependency': ga_key,
                        'reason': diag or 'no safe accessible version found',
                        'current': current_ver_str,
                        'target': '',
                    })
                    continue

            # Find the dep in the parsed pom to determine the update strategy
            dep_list = dep_by_key.get(ga_key, [])
            updated = False

            for dep in dep_list:
                if not dep.version:
                    continue  # managed dep with no version here
                if dep.version == target_str:
                    continue  # already at target

                change: dict = {
                    'dependency': ga_key,
                    'old_version': dep.version,
                    'new_version': target_str,
                    'change_type': 'maven-managed' if dep.is_managed else 'maven',
                    'version_span': dep.version_span,
                    'property_span': dep.property_span,
                    'property_key': dep.property_key,
                }
                changes.append(change)
                updated = True
                break  # update first occurrence only (managed takes priority if listed first)

            if not updated:
                # Dep is purely transitive — add a dependencyManagement override
                dm_overrides.append({
                    'dependency': ga_key,
                    'old_version': current_ver_str,
                    'new_version': target_str,
                    'change_type': 'maven-managed',
                    'version_span': None,
                    'property_span': None,
                })

        # Apply changes to the pom text
        from output.maven_pom import apply_pom_changes
        updated_text = apply_pom_changes(parsed.pom_text, changes, dm_overrides)

        print()
        print(
            f'Maven counts: deps={len(parsed.deps)}, updated={len(changes)}, '
            f'dm_overrides={len(dm_overrides)}, skipped={len(skipped)}'
        )

        display_changes = [
            build_display_change(
                row.get('dependency', ''),
                row.get('old_version', ''),
                row.get('new_version', ''),
                row.get('change_type', 'maven'),
                True,
            )
            for row in changes + dm_overrides
        ]
        skipped_display = [
            build_skipped_entry(
                row.get('dependency', ''),
                row.get('current', ''),
                row.get('target', ''),
                row.get('reason', ''),
            )
            for row in skipped
        ]

        return EcosystemUpdateResult(
            display_changes=display_changes,
            skipped_display=skipped_display,
            extra={
                'pom_text': parsed.pom_text,
                'updated_text': updated_text,
                'changes': changes,
                'dm_overrides': dm_overrides,
                'skipped_raw': skipped,
                'pom_file': parsed.file_path,
                'fetch_errors': fetch_errs,
            },
        )

    def write_logs(self, log_dir: str, result: EcosystemUpdateResult) -> None:
        from shared.utils import write_csv_rows

        extra = result.extra
        write_csv_rows(
            os.path.join(log_dir, 'maven-fetch-errors.csv'),
            extra.get('fetch_errors', []),
            ['dependency', 'error'],
        )
        write_csv_rows(
            os.path.join(log_dir, 'maven-version-changes.csv'),
            extra.get('changes', []),
            ['dependency', 'old_version', 'new_version', 'change_type'],
        )
        write_csv_rows(
            os.path.join(log_dir, 'maven-dm-overrides.csv'),
            extra.get('dm_overrides', []),
            ['dependency', 'old_version', 'new_version'],
        )
        write_csv_rows(
            os.path.join(log_dir, 'maven-skipped.csv'),
            extra.get('skipped_raw', []),
            ['dependency', 'reason', 'current', 'target'],
        )


class MavenPomManager:
    ecosystem = 'maven'
    type = 'maven'
    label = 'Maven'
    explicit_arg_attr = 'pom_files'
    explicit_arg_name = '--pom-file'
    explicit_arg_help = 'Explicit pom.xml file to update. Can be passed multiple times.'
    total_keys = ('maven_direct', 'maven_managed', 'skipped')

    parser = MavenPomParser()
    registry = MavenPomRegistry()
    output = MavenPomOutput()

    def packages_to_fetch(self, parsed: Any, tree: MavenPomTree, cve_packages: set[str]) -> list:
        return parsed.deps

    def summarize(self, result: dict) -> dict[str, int]:
        return {
            'maven_direct': sum(
                1 for row in result.get('display_changes', [])
                if row.get('change_type') == 'maven'
            ),
            'maven_managed': sum(
                1 for row in result.get('display_changes', [])
                if row.get('change_type') == 'maven-managed'
            ),
            'skipped': len(result.get('skipped_display', [])),
        }

    def analyze(self, cfg: Any, manager: dict, log_dir: str, cve_packages: set[str]) -> dict:
        from pipeline.runner import run_analysis

        cfg_ns = SimpleNamespace(
            artifactory_source=cfg.artifactory_source,
            artifactory_repo=cfg.artifactory_repo,
            artifactory_username=cfg.artifactory_username,
            artifactory_password=cfg.artifactory_password,
            workers=cfg.workers,
            maven_timeout=getattr(cfg, 'maven_timeout', 150),
            maven_cmd=getattr(cfg, 'maven_cmd', 'mvn'),
            skip_block_check=cfg.skip_block_check,
            xray_host=cfg.artifactory_source,
            skip_build_validation=getattr(cfg, 'skip_build_validation', True),
        )
        return run_analysis(self, manager['file_path'], log_dir, cve_packages, cfg_ns)

    def make_write_plan(self, cfg: Any, result: dict, log_dir: str | None) -> 'WritePlan':
        from managers import WritePlan
        from output.maven_pom import write_pom_file
        from parsers.pom import get_maven_cmd
        from shared.build_validation.maven import validate_maven_project_or_rollback

        path = result.get('pom_file') or result.get('file_path', '')
        pom_text = result.get('pom_text', '')
        updated_text = result.get('updated_text', '')
        changes = result.get('changes', [])
        dm_overrides = result.get('dm_overrides', [])
        project_dir = str(Path(path).resolve().parent)
        maven_cmd = getattr(cfg, 'maven_cmd', None) or get_maven_cmd(project_dir)
        timeout = max(getattr(cfg, 'maven_timeout', 150), 300)

        return WritePlan(
            has_changes=bool(changes or dm_overrides),
            file_path=path,
            write=lambda: write_pom_file(updated_text, path, path, in_place=True),
            validate=lambda: validate_maven_project_or_rollback(
                pom_file=path,
                original_text=pom_text,
                mvn_cmd=maven_cmd,
                timeout=timeout,
                changes=changes,
                dm_overrides=dm_overrides,
                log_dir=log_dir,
                enable_failure_isolation=getattr(cfg, 'enable_failure_isolation', False),
            ),
        )

    def write_result(self, cfg: Any, result: dict, log_dir: str) -> None:
        from pipeline.runner import run_write_validate
        run_write_validate(
            self.make_write_plan(cfg, result, log_dir),
            getattr(cfg, 'skip_build_validation', False),
        )
