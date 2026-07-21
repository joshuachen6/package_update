from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def _cves(audit: dict[str, Any]) -> set:
    return {
        str(cve)
        for component in audit.get("vulnerable_components", []) or []
        for cve in component.get("cves", []) or []
    }

def _changed_file_results(results: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        file_result
        for file_result in results.get("file_results", []) or []
        if file_result.get("display_changes")
        and file_result.get("write_status") != "Failed"
    ]


def _preexisting_failure_baseline(log_dir: str | None) -> set[str]:
    """Failing tests recorded by build validation as predating remediation.

    Written by shared.build_validation when the post-change build failure was
    fully explained by an identical baseline failure and the updates were
    therefore kept. Verification uses it to avoid re-classifying those same
    pre-existing test failures as a remediation failure.
    """
    if not log_dir:
        return set()
    import csv

    path = Path(log_dir) / "build-validation-preexisting-failures.csv"
    if not path.is_file():
        return set()
    try:
        with path.open(encoding="utf-8", newline="") as f:
            return {row.get("test", "") for row in csv.DictReader(f)} - {""}
    except Exception:
        return set()


def _run(
    command: list[str],
    cwd: Path,
    timeout: int,
    label: str,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return {
            "label": label,
            "status": "not_run",
            "command": command,
            "reason": f"command not found: {exc.filename}",
            "output": "",
        }
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(
            part
            for part in (
                exc.stdout if isinstance(exc.stdout, str) else "",
                exc.stderr if isinstance(exc.stderr, str) else "",
            )
            if part
        )
        return {
            "label": label,
            "status": "failed",
            "command": command,
            "reason": f"timed out after {timeout}s",
            "output": output[-4000:],
        }

    output = "\n".join(
        part for part in (completed.stdout, completed.stderr) if part
    )
    return {
        "label": label,
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": command,
        "returncode": completed.returncode,
        "reason": "" if completed.returncode == 0 else "test command failed",
        "output": output[-4000:],
    }


def _node_test(
    file_result: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    package_path = Path(
        file_result.get("pkg_json_path")
        or file_result.get("file_path")
        or ""
    )
    try:
        package_json = json.loads(package_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "label": "npm tests",
            "status": "not_run",
            "reason": f"could not inspect package.json: {exc}",
        }

    scripts = package_json.get("scripts") or {}
    test_script = scripts.get("test") if isinstance(scripts, dict) else None
    if not isinstance(test_script, str) or not test_script.strip():
        return {
            "label": "npm tests",
            "status": "not_run",
            "reason": "no npm test script declared",
        }

    normalized = test_script.lower().replace(" ", "")
    if "error:notestspecified" in normalized and "exit1" in normalized:
        return {
            "label": "npm tests",
            "status": "not_run",
            "reason": "package.json contains only the default no-test placeholder",
        }

    return _run(
        [cfg.get("npm_cmd", "npm"), "test"],
        package_path.resolve().parent,
        max(int(cfg.get("npm_timeout", 90)), 600),
        "npm tests",
    )


_FAILING_NODE_SUITE_RE = re.compile(r"(?m)^FAIL\s+(\S.*)$")


def _extract_failing_node_suites(output: str) -> set[str]:
    """Jest/Vitest print `FAIL <path>` per failing suite — a coarser, more
    portable signal than per-test names, which vary a lot across runners.
    """
    return {line.strip() for line in _FAILING_NODE_SUITE_RE.findall(output or "")}


def _git_show(project_dir: Path, rel_path: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_dir), "show", f"HEAD:{rel_path}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    return completed.stdout if completed.returncode == 0 else None


def _node_baseline_failure(
    project_dir: Path,
    npm_cmd: str,
    timeout: int,
) -> str | None:
    """Rerun npm test against the pre-remediation package.json/lockfile to tell
    whether currently-failing tests already failed before the dependency
    updates (seen live: timezone-dependent date-formatting tests unrelated to
    the actual package bumps). Unlike Gradle, node_modules content — not just
    package.json text — determines what runs, so this needs a real reinstall;
    the original text comes from git HEAD since nothing commits mid-pipeline.
    Best-effort: returns None (no verdict) on any git/install hiccup, leaving
    the caller's existing "failed" classification untouched.
    """
    pkg_path = project_dir / "package.json"
    lock_paths = [
        project_dir / "package-lock.json",
        project_dir / "npm-shrinkwrap.json",
    ]

    original_pkg_text = _git_show(project_dir, "package.json")
    if original_pkg_text is None:
        return None
    current_pkg_text = pkg_path.read_text(encoding="utf-8")
    if original_pkg_text == current_pkg_text:
        return None

    snapshots: dict[Path, tuple[str, str]] = {}
    for lock_path in lock_paths:
        if not lock_path.is_file():
            continue
        original_lock_text = _git_show(project_dir, lock_path.name)
        if original_lock_text is None:
            continue
        snapshots[lock_path] = (lock_path.read_text(encoding="utf-8"), original_lock_text)

    try:
        pkg_path.write_text(original_pkg_text, encoding="utf-8")
        for lock_path, (_current, original_text) in snapshots.items():
            lock_path.write_text(original_text, encoding="utf-8")

        install = _run(
            [npm_cmd, "install", "--no-audit", "--no-fund"],
            project_dir,
            timeout,
            "npm baseline install",
        )
        if install["status"] != "passed":
            return None

        test = _run([npm_cmd, "test"], project_dir, timeout, "npm baseline test")
        return test.get("output", "") if test["status"] == "failed" else None
    finally:
        pkg_path.write_text(current_pkg_text, encoding="utf-8")
        for lock_path, (current_text, _original) in snapshots.items():
            lock_path.write_text(current_text, encoding="utf-8")
        _run(
            [npm_cmd, "install", "--no-audit", "--no-fund"],
            project_dir,
            timeout,
            "npm restore install",
        )


def _gradle_test(
    file_result: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    build_file = Path(file_result.get("file_path") or "")
    gradle_cmd = cfg.get("gradle_cmd")
    if not gradle_cmd:
        from parsers.gradle_tree import get_gradle_cmd

        # A wrapper that exists but lacks +x (common on a fresh clone/tarball,
        # since git doesn't always preserve the executable bit) raises
        # PermissionError if exec'd directly rather than falling back to the
        # system `gradle` — get_gradle_cmd checks os.access(..., X_OK) too.
        gradle_cmd = get_gradle_cmd(str(build_file.resolve().parent))

    result = _run(
        [
            gradle_cmd,
            "test",
            "--rerun-tasks",
            "--console=plain",
            # Batch runs execute many repos in parallel, each spawning its own
            # background daemon under --daemon; live data showed daemons
            # getting killed mid-build ("daemon disappeared unexpectedly")
            # under that contention, misreporting an otherwise-passing repo
            # as Failed. shared.build_validation.validate_gradle_project
            # already uses --no-daemon for the same reason (see its comment)
            # — match that here so this one-shot test run doesn't leave a
            # persistent daemon competing with everything else in the batch.
            "--no-daemon",
        ],
        build_file.resolve().parent,
        max(int(cfg.get("gradle_timeout", 30)), 600),
        "Gradle tests",
    )
    if result["status"] != "passed":
        return result
    output = result.get("output", "")
    executed = re.search(r"(?im)^> Task .*:test(?:\s|$)", output)
    skipped = re.search(
        r"(?im)^> Task .*:test\s+(?:NO-SOURCE|SKIPPED)",
        output,
    )
    if skipped:
        result["status"] = "not_run"
        result["reason"] = "Gradle test task had no test source or was skipped"
    elif not executed:
        result["status"] = "not_run"
        result["reason"] = "Gradle reported no executed test task"
    return result


def _python_test(
    file_result: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    dependency_file = Path(file_result.get("file_path") or "")
    project_dir = dependency_file.resolve().parent
    test_files = {
        candidate
        for pattern in ("test_*.py", "*_test.py")
        for candidate in project_dir.rglob(pattern)
        if not any(
            part.startswith(".") or part == ".venv"
            for part in candidate.parts
        )
    }
    if not test_files:
        return {
            "label": "Python tests",
            "status": "not_run",
            "reason": "no Python test files discovered",
        }

    python_cmd = cfg.get("python_cmd", "python3")
    try:
        probe = subprocess.run(
            [python_cmd, "-c", "import pytest"],
            cwd=str(project_dir),
            text=True,
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        probe = None

    if probe is None or probe.returncode != 0:
        return {
            "label": "Python tests",
            "status": "not_run",
            "reason": "pytest is not installed in the validation environment",
        }

    return _run(
        [python_cmd, "-m", "pytest", "-q"],
        project_dir,
        max(int(cfg.get("pip_timeout", 90)), 600),
        "Python tests",
    )


def run_discovered_tests(
    results: dict[str, Any],
) -> dict[str, Any]:
    cfg = dict(results.get("cfg", {}) or {})
    test_results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for file_result in _changed_file_results(results):
        dm_type = file_result.get("dm_type", "")
        file_path = str(file_result.get("file_path") or "")
        project_dir = str(Path(file_path).resolve().parent)
        key = (dm_type, project_dir)
        if key in seen:
            continue
        seen.add(key)

        if dm_type == "node":
            test_result = _node_test(file_result, cfg)
            if test_result.get("status") == "failed":
                baseline_output = _node_baseline_failure(
                    Path(project_dir),
                    cfg.get("npm_cmd", "npm"),
                    max(int(cfg.get("npm_timeout", 90)), 600),
                )
                if baseline_output is not None:
                    failing_now = _extract_failing_node_suites(
                        test_result.get("output", "")
                    )
                    failing_baseline = _extract_failing_node_suites(baseline_output)
                    if failing_now and failing_now <= failing_baseline:
                        test_result["status"] = "not_run"
                        test_result["reason"] = (
                            "every failing test suite also failed before "
                            "remediation; treated as pre-existing, not caused "
                            "by dependency updates"
                        )
        elif dm_type == "gradle":
            test_result = _gradle_test(file_result, cfg)
            if test_result.get("status") == "failed":
                from shared.build_validation import _extract_failing_tests

                baseline = _preexisting_failure_baseline(
                    cfg.get("log_dir") or results.get("log_dir")
                )
                failing_now = _extract_failing_tests(
                    test_result.get("output", "")
                )
                excused = bool(baseline and failing_now and failing_now <= baseline)

                # The CSV read above is a side effect of build_validation's OWN
                # internal build-failure-vs-baseline comparison, which only
                # runs when the FIRST build attempt fails outright. When
                # isolation instead resolves the build to "Passed" (excluding
                # whichever candidate broke it), that comparison never runs,
                # so no CSV exists here at all -- even though this SEPARATE,
                # later test re-run can still hit an environment-dependent
                # failure (Vault/Kafka/Mongo context loads routinely fail in
                # this sandbox regardless of any dependency change, confirmed
                # live) with nothing to excuse it. Node's baseline check
                # (_node_baseline_failure, above) is already self-contained
                # for exactly this reason -- mirror that here instead of
                # depending on a side effect of an unrelated, sometimes-skipped
                # code path.
                if not excused and failing_now:
                    from shared.build_validation import _gradle_baseline_failure

                    gradle_cmd = cfg.get("gradle_cmd")
                    if not gradle_cmd:
                        from parsers.gradle_tree import get_gradle_cmd

                        gradle_cmd = get_gradle_cmd(project_dir)

                    build_path = Path(file_path)
                    current_text = build_path.read_text(encoding="utf-8")
                    original_text = file_result.get("build_text", "")
                    if original_text and original_text != current_text:
                        baseline_failure = _gradle_baseline_failure(
                            build_path,
                            original_text,
                            current_text,
                            gradle_cmd,
                            max(int(cfg.get("gradle_timeout", 30)), 600),
                        )
                        if baseline_failure is not None:
                            failing_baseline = _extract_failing_tests(
                                baseline_failure
                            )
                            excused = bool(failing_now <= failing_baseline)

                if excused:
                    test_result["status"] = "not_run"
                    test_result["reason"] = (
                        "every failing test also failed before remediation; "
                        "treated as pre-existing, not caused by dependency updates"
                    )
        elif dm_type == "python":
            test_result = _python_test(file_result, cfg)
        else:
            test_result = {
                "label": f"{dm_type} tests",
                "status": "not_run",
                "reason": "unsupported dependency manager",
            }

        test_result["ecosystem"] = dm_type
        test_result["project_dir"] = project_dir
        test_results.append(test_result)

    statuses = {row.get("status") for row in test_results}
    if "failed" in statuses:
        overall = "failed"
    elif test_results and statuses == {"passed"}:
        overall = "passed"
    elif "passed" in statuses:
        overall = "partial"
    else:
        overall = "not_run"

    return {
        "status": overall,
        "results": test_results,
        "passed": sum(
            row.get("status") == "passed" for row in test_results
        ),
        "failed": sum(
            row.get("status") == "failed" for row in test_results
        ),
        "not_run": sum(
            row.get("status") == "not_run" for row in test_results
        ),
    }


def refresh_dependency_evidence(
    results: dict[str, Any],
) -> list:
    from managers import get_manager_spec

    cfg_dict = dict(results.get("cfg", {}) or {})
    cfg_dict.setdefault(
        "artifactory_source",
        cfg_dict.get("xray_url", ""),
    )
    cfg_dict.setdefault("npm_cmd", "npm")
    cfg_dict.setdefault("npm_timeout", 90)
    cfg_dict.setdefault("gradle_timeout", 150)
    cfg_dict.setdefault("python_cmd", "python3")
    cfg_dict.setdefault("pip_timeout", 90)
    cfg_dict.setdefault("workers", 8)
    cfg = SimpleNamespace(**cfg_dict)
    log_dir = (
        cfg_dict.get("log_dir")
        or results.get("log_dir")
        or "logs"
    )
    errors: list[str] = []

    for file_result in _changed_file_results(results):
        try:
            manager = get_manager_spec(file_result["dm_type"])
            file_path = file_result.get("file_path")
            parsed = manager.parser.parse(file_path)
            tree = manager.parser.resolve_tree(file_path, parsed, cfg, log_dir)
            # resolve_tree reports failure via a flag, not an exception. Left
            # unchecked, the stale pre-update tree from the analysis phase
            # stays in log_dir and the post-remediation audit re-reports the
            # OLD versions' CVEs — repos that were fully fixed get classified
            # Partial forever. Surface it so the scan is marked incomplete
            # instead of silently wrong.
            if getattr(tree, "tree_failed", False):
                errors.append(
                    f"{file_path}: post-remediation dependency tree resolution "
                    "failed; verification scan would read a stale pre-update tree"
                )
                continue
            if file_result.get("dm_type") == "gradle":
                # Keep the report's after-snapshot describing the FINAL state
                # (the proactive check writes it before any rollback edits).
                fresh = Path(log_dir) / "gradle-dependency-tree.txt"
                if fresh.is_file():
                    (Path(log_dir) / "gradle-dependency-tree-after.txt").write_text(
                        fresh.read_text(encoding="utf-8"),
                        encoding="utf-8",
                    )
        except Exception as exc:
            errors.append(
                f"{file_result.get('file_path', '')}: {exc}"
            )

    return errors


def finalize_verification(
    results: dict[str, Any],
) -> dict[str, Any]:
    from shared.jfrog_scan import run_jfrog_audit_with_retry

    cfg = dict(results.get("cfg", {}) or {})
    changed_results = _changed_file_results(results)
    initial_audit = dict(results.get("jfrog_result", {}) or {})

    # Always perform post-update verification when an initial audit exists.
    # A repository whose proposed changes were all rolled back still needs a
    # secondary scan so its final status reflects the actual workspace rather
    # than being inferred from the original findings.
    tests = (
        run_discovered_tests(results)
        if changed_results
        else {
            "status": "not_run",
            "results": [],
            "passed": 0,
            "failed": 0,
            "not_run": 0,
        }
    )
    refresh_errors = refresh_dependency_evidence(results)

    ecosystem_map = {
        "node": "npm",
        "gradle": "maven",
        "python": "pypi",
    }
    ecosystems = {
        ecosystem_map[file_result["dm_type"]]
        for file_result in results.get("file_results", []) or []
        if file_result.get("dm_type") in ecosystem_map
    }

    username = cfg.get("artifactory_username", "")
    auth = (
        (username, cfg.get("artifactory_password", ""))
        if username
        else None
    )
    project_dir = (
        cfg.get("proj_dir")
        or cfg.get("project_dir")
        or results.get("project_dir")
        or "."
    )
    log_dir = (
        cfg.get("log_dir")
        or results.get("log_dir")
        or "logs"
    )

    # A transient network blip in this verification scan alone (same failure
    # mode confirmed live on the initial audit -- see run_jfrog_audit_with_retry)
    # used to be a single-shot check: one hiccup here stamped an otherwise
    # correctly-remediated repo "Error - secondary verification scan
    # incomplete" instead of its real Success/Partial outcome. Retrying here
    # matches the same retry already applied to the initial audit, closing
    # the asymmetry rather than only fixing one side of it.
    post_audit = run_jfrog_audit_with_retry(
        project_dir=project_dir,
        log_dir=log_dir,
        timeout=int(cfg.get("jfrog_timeout", 600)),
        xray_host=(
            cfg.get("xray_url")
            or cfg.get("artifactory_source", "")
        ),
        auth=auth,
        ecosystems=ecosystems,
        output_name="jfrog-audit-after.json",
    )
    results["jfrog_result_after"] = post_audit

    from shared.jfrog_scan import audit_scan_usable

    original_cves = _cves(initial_audit)
    remaining_original_cves = sorted(
        original_cves & _cves(post_audit)
    )
    scan_usable = audit_scan_usable(post_audit) and not refresh_errors

    post_vulnerability_count = int(
        post_audit.get("vulnerability_count") or 0
    )

    # changed_results excludes files whose write failed, so a repo where
    # every proposed change hit BuildValidationManualUpdatesError (isolation
    # off, first build failed, everything reverted) also ends up with an
    # empty changed_results — indistinguishable, downstream, from a repo that
    # had nothing to fix in the first place. Without this check that full
    # write failure fell through to the same "no tests to fail" path as a
    # clean repo and, since post_vulnerability_count was still > 0, got
    # labeled "Partial - build passed" — seen live on 16 real repos where
    # write_status was Failed for every file. Nothing was actually validated
    # as passing there; it needs the same red flag a write failure always
    # got before verification.outcome started driving the report badge.
    attempted_but_all_writes_failed = not changed_results and any(
        file_result.get("display_changes")
        for file_result in results.get("file_results", []) or []
    )

    if not scan_usable:
        outcome = "Error"
        security_status = "incomplete"
        classification = "Error - secondary verification scan incomplete"
    elif attempted_but_all_writes_failed:
        outcome = "Failed"
        security_status = (
            "still_vulnerable" if post_vulnerability_count else "verified_clean"
        )
        classification = (
            "Failed - dependency updates could not be validated; "
            "manual review required"
        )
    elif tests["status"] == "failed":
        outcome = "Failed"
        security_status = (
            "still_vulnerable"
            if post_vulnerability_count
            else "verified_clean"
        )
        classification = "Failed - tests did not pass"
    elif post_vulnerability_count > 0:
        outcome = "Partial"
        security_status = "still_vulnerable"
        classification = (
            f"Partial - build passed but "
            f"{post_vulnerability_count} CVE record(s) remain"
        )
    else:
        outcome = "Success"
        security_status = "verified_clean"
        if tests["status"] == "passed":
            classification = "Success - build and tests passed; no CVEs remain"
        elif tests["status"] == "partial":
            classification = "Success - build passed; partially tested; no CVEs remain"
        else:
            classification = "Success - build passed; no CVEs remain"

    verification = {
        "outcome": outcome,
        "classification": classification,
        "security_status": security_status,
        "test_status": tests["status"],
        "original_cves": sorted(original_cves),
        "remaining_original_cves": remaining_original_cves,
        "refresh_errors": refresh_errors,
        "tests": tests,
        "initial_audit_json": initial_audit.get("json_path", ""),
        "post_audit_json": post_audit.get("json_path", ""),
    }
    results["verification"] = verification

    for file_result in results.get("file_results", []) or []:
        if file_result.get("display_changes"):
            file_result["verification_status"] = classification
            file_result["test_status"] = tests["status"]

    return verification
