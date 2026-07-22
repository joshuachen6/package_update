#!/usr/bin/env python3
"""JFrog-driven package remediation CLI."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from pipeline.runner import run_write_validate

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@dataclass
class QuickUpdateConfig:
    project_dir: str = "."
    log_dir: str | None = None
    workers: int = 8
    npm_cmd: str = "npm"
    npm_timeout: int = 90
    npm_registry: str | None = None
    gradle_timeout: int = 150
    python_cmd: str = "python3"
    pip_timeout: int = 90
    pip_index_url: str | None = None
    skip_block_check: bool = False
    skip_build_validation: bool = False
    enable_failure_isolation: bool = False
    # Runs an extra full build against the pre-remediation file (on top of
    # the build remediation already runs) purely to leave clean
    # build-log-before.txt/build-log-after.txt artifacts. Meaningfully slower
    # per repo -- intended for one-off verification runs, not routine
    # production batches.
    capture_build_logs: bool = False
    artifactory_source: str = ""
    artifactory_repo: str = "ins-cp-mgmt-gradle-virtual"
    artifactory_username: str = ""
    artifactory_password: str = ""
    package_jsons: list[str] | None = None
    build_files: list[str] | None = None
    python_files: list[str] | None = None
    github_url: str | None = None
    checkout_dir: str | None = None
    branch: str | None = None
    input_cves: list[str] | None = None


def _explicit_managers(cfg: QuickUpdateConfig, project_dir: str) -> list:
    from managers import MANAGER_SPECS

    managers: list[dict] = []
    for spec in MANAGER_SPECS.values():
        for raw_path in getattr(cfg, spec.explicit_arg_attr) or []:
            path = os.path.abspath(raw_path)
            if not os.path.isfile(path):
                raise RuntimeError(f"{spec.explicit_arg_name} file not found: {raw_path}")
            managers.append(
                {
                    "type": spec.type,
                    "label": f"{spec.label:<9} >  {os.path.relpath(path, project_dir)}",
                    "file_path": path,
                }
            )
    return managers


def _dependency_managers(cfg: QuickUpdateConfig, project_dir: str) -> list:
    from ui.utils import scan_for_dep_managers

    return _explicit_managers(cfg, project_dir) or scan_for_dep_managers(project_dir)


def _analyze_file(
    cfg: QuickUpdateConfig,
    manager: dict,
    log_dir: str,
    vulnerable_packages: set[str],
    prefetched: tuple[object, object] | None = None,
) -> dict:
    from managers import get_manager_spec

    spec = get_manager_spec(manager["type"])
    if prefetched is None:
        result = spec.analyze(cfg, manager, log_dir, vulnerable_packages)
    else:
        from pipeline.runner import run_analysis

        parsed, tree = prefetched
        result = run_analysis(
            spec,
            manager["file_path"],
            log_dir,
            vulnerable_packages,
            cfg,
            prefetched_tree=tree,
            prefetched_parsed=parsed,
        )
    result["dm_type"] = manager["type"]
    result["file_path"] = manager["file_path"]
    return result


def _tracked_dependency_paths(manager: dict) -> list[str]:
    """Files to snapshot before/after remediation for one manager. Node's
    lockfile carries the actual resolved-version delta -- package.json alone
    often only shows an `overrides` entry -- so both are tracked when the
    lockfile exists.
    """
    file_path = manager["file_path"]
    paths = [file_path]
    if manager["type"] == "node":
        project_dir = os.path.dirname(file_path)
        for lock_name in ("package-lock.json", "npm-shrinkwrap.json"):
            lock_path = os.path.join(project_dir, lock_name)
            if os.path.isfile(lock_path):
                paths.append(lock_path)
    return paths


def _save_before_after_dependency_file(
    file_path: str,
    project_dir: str,
    before_text: str,
    after_text: str,
    log_dir: str,
) -> None:
    """Copy the actual dependency file's pre/post-remediation content into
    log_dir -- so the whole log_dir can be zipped and handed to someone else
    as a self-contained debugging bundle, without them needing repo access to
    see what build.gradle/package.json/pyproject.toml actually looked like
    before and after.
    """
    try:
        rel = os.path.relpath(file_path, project_dir)
    except ValueError:
        rel = os.path.basename(file_path)
    flat = rel.replace(os.sep, "__")
    stem, ext = os.path.splitext(flat)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    Path(log_dir, f"{stem}-before{ext}").write_text(before_text, encoding="utf-8")
    Path(log_dir, f"{stem}-after{ext}").write_text(after_text, encoding="utf-8")


def _capture_build_logs(
    cfg: QuickUpdateConfig,
    manager: dict,
    result: dict,
    log_dir: str,
) -> None:
    """cfg.capture_build_logs opt-in: run an extra build against the
    pre-remediation file solely to leave clean before/after log artifacts.
    Best-effort -- called from inside a try/except at the call site.
    """
    file_path = manager["file_path"]

    if manager["type"] == "gradle":
        from parsers.gradle_tree import get_gradle_cmd
        from shared.build_validation import capture_gradle_build_logs

        build_path = Path(file_path)
        capture_gradle_build_logs(
            build_path,
            result.get("build_text", ""),
            build_path.read_text(encoding="utf-8"),
            get_gradle_cmd(str(build_path.resolve().parent)),
            max(cfg.gradle_timeout, 600),
            log_dir,
        )
    elif manager["type"] == "node":
        from shared.verification import capture_node_build_logs

        capture_node_build_logs(
            Path(file_path).resolve().parent,
            cfg.npm_cmd,
            max(cfg.npm_timeout, 600),
            log_dir,
        )


def _pre_resolve_gradle_managers(
    cfg: QuickUpdateConfig,
    managers: list[dict],
    log_dir: str,
) -> tuple[dict[str, tuple[object, object]], list[str], dict[str, str]]:
    """Resolve Gradle trees before Xray so fresh CLI runs have Maven components.

    This preaudit resolution is the only pre-remediation Gradle tree Gradle
    ever produces -- the flat log_dir/gradle-dependency-tree.txt only gets
    written later, post-remediation (for the after-audit). The returned
    tree_by_file map lets callers snapshot a genuine "before" tree per file
    instead of accidentally reading the (not-yet-written) flat path.
    """
    from managers import get_manager_spec

    cache: dict[str, tuple[object, object]] = {}
    tree_paths: list[str] = []
    tree_by_file: dict[str, str] = {}
    gradle_index = 0

    for manager in managers:
        if manager.get("type") != "gradle":
            continue

        gradle_index += 1
        spec = get_manager_spec("gradle")
        file_path = manager["file_path"]
        preaudit_log_dir = os.path.join(
            log_dir,
            "preaudit-gradle",
            str(gradle_index),
        )
        os.makedirs(preaudit_log_dir, exist_ok=True)

        print()
        print(f"Pre-resolving Gradle dependencies for {manager['label']}...")
        parsed = spec.parser.parse(file_path)
        tree = spec.parser.resolve_tree(
            file_path,
            parsed,
            cfg,
            preaudit_log_dir,
        )
        cache[file_path] = (parsed, tree)

        tree_path = os.path.join(
            preaudit_log_dir,
            "gradle-dependency-tree.txt",
        )
        if os.path.isfile(tree_path):
            tree_paths.append(tree_path)
            tree_by_file[file_path] = tree_path

    return cache, tree_paths, tree_by_file


def _enabled_ecosystems(managers: list[dict]) -> set:
    from managers import get_manager_spec

    return {get_manager_spec(manager["type"]).ecosystem for manager in managers}
def _format_totals(totals: dict[str, int]) -> str:
    labels = {
        "npm_direct": "npm direct",
        "npm_override": "npm override(s)",
        "gradle_direct": "Gradle direct",
        "gradle_force": "Gradle force(s)",
        "python_direct": "Python direct",
        "skipped": "skipped",
    }
    return ", ".join(f"{totals.get(key, 0)} {label}" for key, label in labels.items())


def run_quick_update(cfg: QuickUpdateConfig) -> dict:
    from managers import get_manager_spec, manager_total_keys
    from shared.jfrog_scan import (
        run_jfrog_audit_with_retry,
        vulnerable_packages_by_ecosystem,
    )
    from shared.utils import normalize_log_dir

    if cfg.github_url:
        from shared.github import clone_github_repo

        clone_kwargs: dict = {}
        if cfg.checkout_dir:
            clone_kwargs["checkout_dir"] = cfg.checkout_dir
        if cfg.branch:
            clone_kwargs["branch"] = cfg.branch
        print(f"Cloning {cfg.github_url}...")
        cfg.project_dir = clone_github_repo(cfg.github_url, **clone_kwargs)

    project_dir = os.path.abspath(cfg.project_dir)
    log_dir = normalize_log_dir(cfg.log_dir, project_dir)
    managers = _dependency_managers(cfg, project_dir)
    if any(manager.get("type") == "python" for manager in managers):
        with contextlib.suppress(FileNotFoundError):
            os.remove(os.path.join(log_dir, "python-dependency-tree.txt"))

    if not managers:
        raise RuntimeError(
            f"No supported dependency files found under {project_dir}. "
            "Use --package-json, --build-file, or --python-file to target explicit files."
        )

    print(f"Found {len(managers)} dependency file(s):")
    for manager in managers:
        print(f"  - {manager['label']}")

    auth = (cfg.artifactory_username, cfg.artifactory_password) if cfg.artifactory_username else None

    prefetched_gradle, gradle_tree_paths, gradle_tree_by_file = _pre_resolve_gradle_managers(
        cfg,
        managers,
        log_dir,
    )

    print()
    print("-" * 60)
    print("JFrog CVE audit")
    print("-" * 60)

    # A scan that errored (timeout, connection reset, DNS failure) can still
    # report vulnerability_count=0 -- indistinguishable from a genuinely
    # clean repo to anything that only reads the count. Confirmed live: this
    # silently drove zero remediation attempts on real repos, whose later,
    # working post-audit then reported the same (never-touched) CVEs,
    # making the report read as if the tool had introduced new
    # vulnerabilities rather than never having attempted a fix.
    # run_jfrog_audit_with_retry retries the same idempotent scan a couple
    # times first (confirmed live: these are transient per-request blips --
    # the same endpoint/credentials succeeded for every other repo in the
    # same batch run); audit_scan_usable is the backstop for when retries
    # are exhausted, mirroring the same gate finalize_verification already
    # applies to the post-audit -- an unusable scan must never be silently
    # treated as "nothing to fix."
    jfrog_result = run_jfrog_audit_with_retry(
        project_dir=project_dir,
        log_dir=log_dir,
        timeout=600,
        xray_host=cfg.artifactory_source,
        auth=auth,
        ecosystems=_enabled_ecosystems(managers),
        gradle_tree_paths=gradle_tree_paths,
    )

    from shared.jfrog_scan import audit_scan_usable

    if not audit_scan_usable(jfrog_result):
        raise RuntimeError(
            "Initial JFrog CVE audit did not complete successfully after retrying "
            f"({'; '.join(jfrog_result.get('errors') or []) or jfrog_result.get('stderr') or 'scan unavailable'}); "
            "refusing to proceed since remediation criteria would be built from an incomplete scan."
        )

    vulnerable_by_ecosystem = vulnerable_packages_by_ecosystem(jfrog_result)

    totals = {key: 0 for key in manager_total_keys()}
    fixed_results = []
    initial_results = []

    print()
    print("-" * 60)
    print("Fix JFrog CVEs")
    print("-" * 60)

    from shared.report import snapshot_before_dependency_tree

    def _snapshot_before(manager: dict) -> None:
        # Must run right after this manager's own pre-remediation analysis and
        # before spec.write_result() touches anything -- Gradle's flat
        # gradle-dependency-tree.txt only ever holds the POST-remediation tree
        # (written later, for the after-audit), so its "before" snapshot has to
        # come from the preaudit resolution instead of the default flat path.
        # Node has no such split: its flat npm-dependency-tree.json is
        # genuinely pre-remediation at this exact point, before any write.
        if manager["type"] == "gradle":
            snapshot_before_dependency_tree(
                log_dir, "gradle", source_path=gradle_tree_by_file.get(manager["file_path"])
            )
        elif manager["type"] == "node":
            snapshot_before_dependency_tree(log_dir, "node")

    for manager in managers:
        spec = get_manager_spec(manager["type"])
        vulnerable_packages = vulnerable_by_ecosystem.get(spec.ecosystem, set())

        if vulnerable_packages:
            print()
            print(f"Fixing {len(vulnerable_packages)} JFrog package(s) in {manager['label']}")
            result = _analyze_file(
                cfg,
                manager,
                log_dir,
                vulnerable_packages,
                prefetched_gradle.get(manager["file_path"]),
            )
            if manager["type"] == "gradle":
                result["preaudit_gradle_tree_path"] = gradle_tree_by_file.get(
                    manager["file_path"], ""
                )
            _snapshot_before(manager)
            fixed_results.append(result)

            summary = spec.summarize(result)
            for key, value in summary.items():
                totals[key] = totals.get(key, 0) + value

            print("Changes: " + ", ".join(f"{key}={value}" for key, value in summary.items()))

            # Persist replay cache BEFORE write/validation so manual-fix failures
            # still leave a usable Phase-2 artifact behind.
            try:
                from pathlib import Path

                cache_results = []
                for fr in fixed_results:
                    cache_result = dict(fr)
                    cache_result.pop("_tree", None)
                    cache_result.pop("_parsed", None)
                    cache_results.append(cache_result)

                phase2_payload = {
                    "file_results": cache_results,
                    "cfg": {
                        **vars(cfg),
                        "log_dir": log_dir,
                        "proj_dir": project_dir,
                    },
                    "github_url": cfg.github_url or "",
                    "input_cves": list(cfg.input_cves or []),
                }

                (Path(log_dir) / "phase2-results.json").write_text(
                    json.dumps(phase2_payload, indent=2, default=str),
                    encoding="utf-8",
                )
                print(f"Phase2 cache generated → {Path(log_dir) / 'phase2-results.json'}")
            except Exception as exc:
                print(f"Phase2 cache generation skipped: {exc}")

            tracked_paths = _tracked_dependency_paths(manager)
            before_file_texts = {
                p: Path(p).read_text(encoding="utf-8") if os.path.isfile(p) else ""
                for p in tracked_paths
            }

            try:
                spec.write_result(cfg, result, log_dir)
                result["write_status"] = (
                    "Written"
                    if result.get("display_changes")
                    else "No changes"
                )
                result["validation_status"] = (
                    "Skipped"
                    if cfg.skip_build_validation
                    else "Passed"
                )
            except Exception as exc:
                result["write_status"] = "Failed"
                result["validation_status"] = "Failed"
                result["validation_message"] = str(exc)
                print(f"Write/validation failed: {exc}")

            # Always on (unlike capture_build_logs) -- these are just the two
            # states of a file already on disk, not an extra build, so there's
            # no cost reason to gate this behind a flag. The whole point is a
            # self-contained debugging bundle: zip up log_dir and you have the
            # actual dependency file(s) before/after, not just their diff
            # summary. For npm this includes package-lock.json alongside
            # package.json -- the manifest alone often only shows an
            # `overrides` entry; the lockfile carries the actual resolved-
            # version delta.
            if result.get("display_changes"):
                for p, before_text in before_file_texts.items():
                    try:
                        after_text = (
                            Path(p).read_text(encoding="utf-8")
                            if os.path.isfile(p)
                            else ""
                        )
                        _save_before_after_dependency_file(
                            p, project_dir, before_text, after_text, log_dir,
                        )
                    except Exception as exc:
                        print(f"Dependency file before/after capture skipped ({p}): {exc}")

            # Runs regardless of write/validation outcome -- capture_gradle_
            # build_logs/capture_node_build_logs run their own independent
            # builds and don't depend on write_result having succeeded. A
            # "for verification" feature that went silent exactly on the
            # repos that failed (isolation off, validation raised) would be
            # backwards -- those are the ones this exists to explain.
            if cfg.capture_build_logs and result.get("display_changes"):
                try:
                    _capture_build_logs(cfg, manager, result, log_dir)
                except Exception as exc:
                    print(f"Build log capture skipped: {exc}")
        else:
            print()
            print(f"No JFrog CVEs for {manager['label']} — baseline analysis")
            initial_results.append(
                _analyze_file(
                    cfg,
                    manager,
                    log_dir,
                    set(),
                    prefetched_gradle.get(manager["file_path"]),
                )
            )
            _snapshot_before(manager)

    print()
    print(f"Totals: {_format_totals(totals)}")
    print(f"Logs:   {log_dir}")

    all_results = fixed_results or initial_results

    clean_results = []

    for fr in all_results:
        clean = dict(fr)
        clean.pop("_tree", None)
        clean.pop("_parsed", None)
        clean_results.append(clean)

    result = {
        "file_results": clean_results,
        "jfrog_result": jfrog_result,
        "log_dir": log_dir,
        "totals": totals,
        "github_url": cfg.github_url or "",
        "input_cves": list(cfg.input_cves or []),
        "cfg": {
            **vars(cfg),
            "log_dir": log_dir,
            "proj_dir": project_dir,
        },
        "tree_failed": any(r.get("tree_failed") for r in all_results),
    }

    # Always verify, even when no manager had a CVE to fix — an already-compliant
    # repo still needs a final classification, otherwise it falls through to the
    # "no verification result" catch-all in main() and is misreported as an Error.
    try:
        from shared.verification import finalize_verification

        verification = finalize_verification(result)
        print(
            "Post-update verification: "
            + verification["classification"]
        )
        from shared.remediation_evidence import (
            write_remediation_evidence,
        )

        evidence_path = write_remediation_evidence(
            result,
            log_dir=log_dir,
        )
        result["remediation_evidence_path"] = evidence_path
        print(f"Remediation evidence -> {evidence_path}")
    except Exception as exc:
        import traceback
        from pathlib import Path

        tb = traceback.format_exc()
        result["verification"] = {
            "classification": "Verification incomplete",
            "security_status": "incomplete",
            "test_status": "not_run",
            "error": str(exc),
        }
        print(f"Post-update verification failed: {exc}")
        # A repo whose dependency updates succeeded still ends up misreported
        # Manual Update Required whenever this happens, since finalize_verification
        # never got to write a fresh verification/report.py falls back to CSV
        # presence, which can be stale. str(exc) alone is rarely enough to tell
        # whether that's what happened here without re-running with a captured
        # console; persist the traceback so it's not a one-shot diagnosis.
        if log_dir:
            with contextlib.suppress(Exception):
                Path(log_dir, "verification-error.txt").write_text(
                    tb, encoding="utf-8",
                )

    try:
        from pathlib import Path

        phase2_payload = {
            "file_results": clean_results,
            "cfg": result["cfg"],
            "github_url": result["github_url"],
            "input_cves": result["input_cves"],
        }

        (Path(log_dir) / "phase2-results.json").write_text(
            json.dumps(
                phase2_payload,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        print(f"Phase2 cache generated → {Path(log_dir) / 'phase2-results.json'}")

    except Exception as exc:
        print(f"Phase2 cache generation skipped: {exc}")

    try:
        from shared.report import generate_report

        # Before-snapshots are already captured per-manager, right after each
        # file's own pre-remediation analysis (see _snapshot_before above) --
        # doing it here instead, after write/validate/verify have all already
        # run, was copying the POST-remediation tree into the "before" file
        # (confirmed live: before/after ended up byte-identical).
        report_path = generate_report(result, log_dir=log_dir)
        print(f"Report generated → {report_path}")
    except Exception as exc:
        print(f"Report generation skipped: {exc}")

    return result



def run_phase2_results(results_file: str) -> bool:
    """Replay a cached Phase 2 write/validate plan. Returns True iff every file succeeded."""
    print(f"[phase2] replay starting: {results_file}")
    import json
    from pathlib import Path
    from types import SimpleNamespace

    from managers import get_manager_spec
    from shared.build_validation import BuildValidationManualUpdatesError

    payload = json.loads(
        Path(results_file).read_text(encoding="utf-8")
    )

    cfg_dict = dict(payload.get("cfg", {}))
    cfg_dict["enable_failure_isolation"] = True

    cfg = SimpleNamespace(**cfg_dict)

    file_results = payload.get("file_results", [])
    github_url = payload.get("github_url") or cfg_dict.get("github_url")
    missing = [
        fr for fr in file_results
        if not os.path.isfile(fr.get("build_file") or fr.get("file_path") or "")
    ]
    if missing and github_url:
        # Phase 1's checkout can be gone by the time Phase 2 replays (a later
        # batch run reused the same indexed checkout dir, or it was cleaned
        # up between sessions) — the recorded file_path/build_file paths are
        # only valid while that clone still exists on disk. Re-cloning to the
        # same checkout_dir reproduces the identical destination path, so the
        # cached build_text/changes/force_entries can still be replayed
        # against it without needing a fresh Phase 1 analysis.
        from shared.github import clone_github_repo

        clone_kwargs: dict = {}
        if cfg_dict.get("checkout_dir"):
            clone_kwargs["checkout_dir"] = cfg_dict["checkout_dir"]
        if cfg_dict.get("branch"):
            clone_kwargs["branch"] = cfg_dict["branch"]
        print(f"[phase2] checkout missing, re-cloning {github_url}...")
        clone_github_repo(github_url, **clone_kwargs)

    all_succeeded = True
    for fr in payload.get("file_results", []):
        manager = get_manager_spec(fr["dm_type"])
        log_dir = cfg_dict.get("log_dir")

        print(f"[phase2] write-only replay for {fr.get('file_path')}")
        plan = manager.make_write_plan(
            cfg,
            fr,
            log_dir,
        )

        try:
            run_write_validate(
                plan,
                cfg_dict.get("skip_build_validation", False),
            )
        except BuildValidationManualUpdatesError as exc:
            print(f"[phase2] manual intervention required for {fr.get('file_path')}: {exc}")
            all_succeeded = False

    return all_succeeded


def _add_cli_args(parser: argparse.ArgumentParser) -> None:
    from managers import MANAGER_SPECS, _ensure_specs

    _ensure_specs()

    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root to scan for supported dependency files. Default: current directory",
    )
    for spec in MANAGER_SPECS.values():
        parser.add_argument(
            spec.explicit_arg_name,
            action="append",
            default=[],
            dest=spec.explicit_arg_attr,
            help=spec.explicit_arg_help,
        )
    parser.add_argument("--log-dir", help="Log directory. Default: <project-dir>/logs")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers. Default: 8")
    parser.add_argument("--npm-cmd", default="npm", help="npm command path/name. Default: npm")
    parser.add_argument("--npm-timeout", type=int, default=90, help="npm timeout seconds")
    parser.add_argument("--npm-registry", default=None, help="Optional npm registry URL")
    parser.add_argument("--gradle-timeout", type=int, default=150, help="Gradle timeout seconds")
    parser.add_argument("--python-cmd", default="python3", help="Python command path/name. Default: python3")
    parser.add_argument("--pip-timeout", type=int, default=90, help="pip/Python timeout seconds")
    parser.add_argument("--pip-index-url", default=None, help="Optional Python package index URL")
    parser.add_argument("--skip-block-check", action="store_true", help="Skip block checks")
    parser.add_argument(
        "--enable-failure-isolation",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Run single-package and exhaustive rollback isolation after build "
            "failures. Disabled by default; Phase 2 enables it explicitly."
        ),
    )
    parser.add_argument(
        "--skip-build-validation",
        action="store_true",
        help="Do not run npm/Gradle/Python validation after writing updates",
    )
    parser.add_argument(
        "--capture-build-logs",
        action="store_true",
        help=(
            "Run an extra full build against the pre-remediation file to "
            "leave clean build-log-before.txt/build-log-after.txt artifacts. "
            "An extra build per repo -- intended for verification runs, not "
            "routine production batches."
        ),
    )
    parser.add_argument(
        "--artifactory-source",
        default=os.environ.get("ARTIFACTORY_SOURCE", ""),
        help="JFrog base URL used for Artifactory and Xray API calls",
    )
    parser.add_argument(
        "--artifactory-repo",
        default=os.environ.get("ARTIFACTORY_REPO", "ins-cp-mgmt-gradle-virtual"),
        help="Artifactory Maven repository for Gradle metadata lookups",
    )
    parser.add_argument("--artifactory-username", default=os.environ.get("ARTIFACTORY_USERNAME", ""))
    parser.add_argument("--artifactory-password", default=os.environ.get("ARTIFACTORY_PASSWORD", ""))
    parser.add_argument("--github-url", default=None, help="GitHub repo URL to clone before analyzing")
    parser.add_argument("--checkout-dir", default=None, help="Parent directory for cloned repos")
    parser.add_argument("--branch", default=None, help="Git branch to checkout")
    parser.add_argument(
        "--phase2-results",
        default=None,
        help="Replay previously analyzed results using failure isolation",
    )

    parser.add_argument(
        "--input-cves",
        default=None,
        help="Comma-separated CVE IDs from taskboard to track in the report",
    )


def _config_from_args(args: argparse.Namespace) -> QuickUpdateConfig:
    return QuickUpdateConfig(
        project_dir=args.project_dir,
        log_dir=args.log_dir,
        workers=args.workers,
        npm_cmd=args.npm_cmd,
        npm_timeout=args.npm_timeout,
        npm_registry=args.npm_registry,
        gradle_timeout=args.gradle_timeout,
        python_cmd=args.python_cmd,
        pip_timeout=args.pip_timeout,
        pip_index_url=args.pip_index_url,
        skip_block_check=args.skip_block_check,
        skip_build_validation=args.skip_build_validation,
        capture_build_logs=args.capture_build_logs,
        enable_failure_isolation=args.enable_failure_isolation,
        artifactory_source=args.artifactory_source,
        artifactory_repo=args.artifactory_repo,
        artifactory_username=args.artifactory_username,
        artifactory_password=args.artifactory_password,
        package_jsons=args.package_jsons,
        build_files=args.build_files,
        python_files=args.python_files,
        github_url=args.github_url,
        checkout_dir=args.checkout_dir,
        branch=args.branch,
        input_cves=(
            [c.strip() for c in args.input_cves.split(",") if c.strip()]
            if args.input_cves
            else None
        ),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="JFrog-driven package remediation")
    _add_cli_args(parser)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if getattr(args, "phase2_results", None):
        if not run_phase2_results(args.phase2_results):
            sys.exit(3)
        return

    cfg = _config_from_args(args)
    if sys.stdout.isatty():
        try:
            from ui.quick_window import run_with_gui
            run_with_gui(cfg)
            return
        except ImportError:
            pass

    from shared.build_validation import BuildValidationManualUpdatesError

    try:
        result = run_quick_update(cfg)
    except BuildValidationManualUpdatesError as exc:
        print(f"Manual intervention required: {exc}")
        sys.exit(3)
    except RuntimeError as exc:
        raise SystemExit(f"ERROR: {exc}") from None

    file_results = result.get("file_results", []) or []
    if any(
        file_result.get("validation_status") == "Failed"
        for file_result in file_results
    ):
        print("STATUS: Failed - build validation did not pass.")
        sys.exit(3)

    verification = dict(result.get("verification", {}) or {})
    outcome = verification.get("outcome")

    if result.get("tree_failed"):
        print(
            "STATUS: Error - dependency tree resolution failed; "
            "verification is incomplete."
        )
        sys.exit(1)

    if outcome == "Success":
        print("STATUS: Success")
        return
    if outcome == "Partial":
        print("STATUS: Partial")
        sys.exit(2)
    if outcome == "Failed":
        print("STATUS: Failed")
        sys.exit(3)
    if outcome == "Error":
        print("STATUS: Error")
        sys.exit(1)

    # A run without a structured verification result is operationally
    # incomplete and must not be shown as successful.
    print("STATUS: Error - no final verification result was produced.")
    sys.exit(1)

if __name__ == "__main__":
    main()
