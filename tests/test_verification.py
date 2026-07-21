from __future__ import annotations

import json
from pathlib import Path


def test_secondary_audit_output_name(tmp_path):
    from shared import jfrog_scan

    result = jfrog_scan.run_jfrog_audit(
        project_dir=str(tmp_path),
        log_dir=str(tmp_path),
        xray_host="",
        output_name="jfrog-audit-after.json",
    )
    assert result["json_path"].endswith("jfrog-audit-after.json")
    assert (tmp_path / "jfrog-audit-after.json").exists()


def test_node_without_test_script_is_untested(tmp_path):
    from shared.verification import run_discovered_tests

    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps({"scripts": {"build": "echo build"}}),
        encoding="utf-8",
    )
    results = {
        "cfg": {"npm_cmd": "npm", "npm_timeout": 1},
        "file_results": [
            {
                "dm_type": "node",
                "file_path": str(package_json),
                "pkg_json_path": str(package_json),
                "display_changes": [{"package": "example"}],
                "write_status": "Written",
            }
        ],
    }

    tests = run_discovered_tests(results)

    assert tests["status"] == "not_run"
    assert tests["not_run"] == 1
    assert "no npm test script" in tests["results"][0]["reason"]


def test_verification_classifies_clean_scan_with_tests(
    monkeypatch,
    tmp_path,
):
    from shared import verification
    monkeypatch.setattr(
        verification,
        "refresh_dependency_evidence",
        lambda results: [],
    )
    monkeypatch.setattr(
        verification,
        "run_discovered_tests",
        lambda results: {
            "status": "passed",
            "results": [{"status": "passed"}],
            "passed": 1,
            "failed": 0,
            "not_run": 0,
        },
    )
    monkeypatch.setattr(
        "shared.jfrog_scan.run_jfrog_audit",
        lambda **kwargs: {
            "available": True,
            "errors": [],
            "stderr": "",
            "vulnerable_components": [],
            "vulnerability_count": 0,
            "json_path": str(
                tmp_path / "jfrog-audit-after.json"
            ),
        },
    )

    results = {
        "cfg": {
            "project_dir": str(tmp_path),
            "log_dir": str(tmp_path),
            "artifactory_source": "https://xray.example",
        },
        "jfrog_result": {
            "vulnerable_components": [
                {"cves": ["CVE-2026-0001"]}
            ],
            "json_path": str(tmp_path / "jfrog-audit.json"),
        },
        "file_results": [
            {
                "dm_type": "node",
                "file_path": str(tmp_path / "package.json"),
                "display_changes": [{"package": "example"}],
                "write_status": "Written",
            }
        ],
    }

    result = verification.finalize_verification(results)

    assert result["outcome"] == "Success"
    assert result["remaining_original_cves"] == []

def test_verification_retries_after_audit_on_transient_scan_failure(
    monkeypatch,
    tmp_path,
):
    """Live bug: a transient network blip in the post-remediation scan alone
    (same failure mode confirmed on the initial audit -- connection reset,
    timeout, DNS failure) was a single-shot check: one hiccup here stamped
    an otherwise correctly-remediated repo "Error - secondary verification
    scan incomplete" instead of its real outcome. Must retry the same,
    idempotent post-audit before giving up, exactly like the initial audit.
    """
    from shared import verification

    monkeypatch.setattr(
        verification, "refresh_dependency_evidence", lambda results: [],
    )
    monkeypatch.setattr(
        verification,
        "run_discovered_tests",
        lambda results: {
            "status": "passed", "results": [{"status": "passed"}],
            "passed": 1, "failed": 0, "not_run": 0,
        },
    )
    monkeypatch.setattr("shared.jfrog_scan.time.sleep", lambda *_: None)

    calls = {"n": 0}

    def fake_audit(**kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            return {
                "available": True,
                "errors": ["Xray CVE lookup failed: <urlopen error timed out>"],
                "stderr": "Xray CVE lookup failed: <urlopen error timed out>",
                "vulnerable_components": [],
                "vulnerability_count": 0,
                "json_path": str(tmp_path / "jfrog-audit-after.json"),
            }
        return {
            "available": True,
            "errors": [],
            "stderr": "",
            "vulnerable_components": [],
            "vulnerability_count": 0,
            "json_path": str(tmp_path / "jfrog-audit-after.json"),
        }

    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_audit)

    results = {
        "cfg": {
            "project_dir": str(tmp_path),
            "log_dir": str(tmp_path),
            "artifactory_source": "https://xray.example",
        },
        "jfrog_result": {
            "vulnerable_components": [{"cves": ["CVE-2026-0001"]}],
            "json_path": str(tmp_path / "jfrog-audit.json"),
        },
        "file_results": [
            {
                "dm_type": "node",
                "file_path": str(tmp_path / "package.json"),
                "display_changes": [{"package": "example"}],
                "write_status": "Written",
            }
        ],
    }

    result = verification.finalize_verification(results)

    assert calls["n"] == 2
    assert result["outcome"] == "Success"


def test_verification_classifies_clean_scan_without_tests(
    monkeypatch,
    tmp_path,
):
    from shared import verification

    monkeypatch.setattr(
        verification,
        "refresh_dependency_evidence",
        lambda results: [],
    )
    monkeypatch.setattr(
        verification,
        "run_discovered_tests",
        lambda results: {
            "status": "not_run",
            "results": [{"status": "not_run"}],
            "passed": 0,
            "failed": 0,
            "not_run": 1,
        },
    )
    monkeypatch.setattr(
        "shared.jfrog_scan.run_jfrog_audit",
        lambda **kwargs: {
            "available": True,
            "errors": [],
            "stderr": "",
            "vulnerable_components": [],
            "vulnerability_count": 0,
            "json_path": str(
                tmp_path / "jfrog-audit-after.json"
            ),
        },
    )

    results = {
        "cfg": {
            "project_dir": str(tmp_path),
            "log_dir": str(tmp_path),
            "artifactory_source": "https://xray.example",
        },
        "jfrog_result": {
            "vulnerable_components": [
                {"cves": ["CVE-2026-0001"]}
            ],
        },
        "file_results": [
            {
                "dm_type": "node",
                "file_path": str(tmp_path / "package.json"),
                "display_changes": [{"package": "example"}],
                "write_status": "Written",
            }
        ],
    }
    result = verification.finalize_verification(results)

    assert result["outcome"] == "Success"



def test_cli_runs_post_update_verification():
    source = Path("quick_update.py").read_text(encoding="utf-8")

    assert "finalize_verification(result)" in source
    assert 'result["write_status"]' in source
    assert 'result["validation_status"]' in source
def test_gui_runs_post_update_verification():
    source = Path("ui/write_worker.py").read_text(encoding="utf-8")

    assert "finalize_verification(self._results)" in source
    assert 'fr["write_status"]' in source
    assert 'fr["validation_status"]' in source



def test_verification_is_partial_when_secondary_scan_still_has_cves(
    monkeypatch,
    tmp_path,
):
    from shared import verification

    monkeypatch.setattr(
        verification,
        "refresh_dependency_evidence",
        lambda results: [],
    )
    monkeypatch.setattr(
        verification,
        "run_discovered_tests",
        lambda results: {
            "status": "passed",
            "results": [{"status": "passed"}],
            "passed": 1,
            "failed": 0,
            "not_run": 0,
        },
    )
    monkeypatch.setattr(
        "shared.jfrog_scan.run_jfrog_audit",
        lambda **kwargs: {
            "available": True,
            "errors": [],
            "stderr": "",
            "vulnerability_count": 1,
            "vulnerable_components": [
                {
                    "component_id": "gav://org.example:a:1.0.0",
                    "cves": ["CVE-2026-0001"],
                }
            ],
            "json_path": str(tmp_path / "jfrog-audit-after.json"),
        },
    )

    results = {
        "cfg": {
            "project_dir": str(tmp_path),
            "log_dir": str(tmp_path),
            "artifactory_source": "https://xray.example",
        },
        "jfrog_result": {
            "vulnerable_components": [
                {"cves": ["CVE-2026-0001"]}
            ],
        },
        "file_results": [
            {
                "dm_type": "gradle",
                "file_path": str(tmp_path / "build.gradle"),
                "display_changes": [{"package": "org.example:a"}],
                "write_status": "Written",
                "validation_status": "Passed",
            }
        ],
    }
    result = verification.finalize_verification(results)

    assert result["outcome"] == "Partial"
    assert result["security_status"] == "still_vulnerable"


def test_verification_is_failed_when_every_write_failed_despite_no_cves_fixed(
    monkeypatch,
    tmp_path,
):
    """Live bug: 16 real repos where isolation was off (Phase 1), the first
    build failed, and BuildValidationManualUpdatesError reverted every single
    file — write_status Failed across the board, zero CVEs actually fixed —
    still got badged "Partial - build passed but N CVE record(s) remain".
    _changed_file_results excludes write_status=Failed entries, so this looks
    identical to "nothing needed fixing" once tests are skipped; the old
    CSV-presence fallback used to catch this (manual-updates.csv -> red), but
    outcome-first reporting dropped it. Nothing here was actually validated
    as passing, so it must not read as progress.
    """
    from shared import verification

    monkeypatch.setattr(
        verification,
        "refresh_dependency_evidence",
        lambda results: [],
    )
    run_discovered_tests_calls = []
    monkeypatch.setattr(
        verification,
        "run_discovered_tests",
        lambda results: run_discovered_tests_calls.append(results) or {
            "status": "not_run",
            "results": [],
            "passed": 0,
            "failed": 0,
            "not_run": 0,
        },
    )
    monkeypatch.setattr(
        "shared.jfrog_scan.run_jfrog_audit",
        lambda **kwargs: {
            "available": True,
            "errors": [],
            "stderr": "",
            "vulnerability_count": 63,
            "vulnerable_components": [
                {
                    "component_id": "gav://org.example:a:1.0.0",
                    "cves": ["CVE-2026-0001"],
                }
            ],
            "json_path": str(tmp_path / "jfrog-audit-after.json"),
        },
    )

    results = {
        "cfg": {
            "project_dir": str(tmp_path),
            "log_dir": str(tmp_path),
            "artifactory_source": "https://xray.example",
        },
        "jfrog_result": {
            "vulnerable_components": [
                {"cves": ["CVE-2026-0001"]}
            ],
        },
        "file_results": [
            {
                "dm_type": "gradle",
                "file_path": str(tmp_path / "build.gradle"),
                "display_changes": [{"package": "org.example:a"}],
                "write_status": "Failed",
                "validation_status": "Failed",
                "validation_message": "manual update required",
            }
        ],
    }
    result = verification.finalize_verification(results)

    assert result["outcome"] == "Failed"
    assert result["security_status"] == "still_vulnerable"
    # A repo with a full write failure never got far enough to run tests —
    # run_discovered_tests would only be reached for repos with changed_results.
    assert run_discovered_tests_calls == []


def test_batch_status_codes_use_new_vocabulary():
    source = Path("ui/batch_worker.py").read_text(encoding="utf-8")

    assert 'proc.returncode == 0' in source
    assert 'row_status.emit(index, "Success")' in source
    assert 'row_status.emit(index, "Partial")' in source
    assert 'row_status.emit(index, "Failed")' in source
    assert 'row_status.emit(index, "Error")' in source
    assert "Done ✓" not in source
    assert "Needs review ✓" not in source


def test_no_changes_still_runs_secondary_scan(
    monkeypatch,
    tmp_path,
):
    from shared import verification

    monkeypatch.setattr(
        verification,
        "refresh_dependency_evidence",
        lambda results: [],
    )
    monkeypatch.setattr(
        "shared.jfrog_scan.run_jfrog_audit",
        lambda **kwargs: {
            "available": True,
            "errors": [],
            "stderr": "",
            "vulnerability_count": 0,
            "vulnerable_components": [],
            "json_path": str(
                tmp_path / "jfrog-audit-after.json"
            ),
        },
    )

    results = {
        "cfg": {
            "project_dir": str(tmp_path),
            "log_dir": str(tmp_path),
            "artifactory_source": "https://xray.example",
        },
        "jfrog_result": {
            "vulnerability_count": 2,
            "vulnerable_components": [
                {"cves": ["CVE-1", "CVE-2"]}
            ],
        },
        "file_results": [
            {
                "dm_type": "gradle",
                "file_path": str(
                    tmp_path / "build.gradle"
                ),
                "display_changes": [],
                "validation_status": "Passed",
            }
        ],
    }

    result = verification.finalize_verification(results)

    assert result["outcome"] == "Success"
    assert (
        results["jfrog_result_after"][
            "vulnerability_count"
        ]
        == 0
    )


def test_refresh_flags_silent_tree_resolution_failure(tmp_path, monkeypatch):
    """resolve_tree signals failure via tree_failed, not an exception. If it
    goes unnoticed the post-remediation audit scans the stale pre-update tree
    and re-reports the old versions' CVEs (seen live: cds-workflow's after-scan
    flagged logback-core:1.5.25 while the resolved tree shipped 1.5.38).
    """
    from types import SimpleNamespace

    from shared.verification import refresh_dependency_evidence

    failed_tree = SimpleNamespace(tree_failed=True)
    spec = SimpleNamespace(
        parser=SimpleNamespace(
            parse=lambda file_path: object(),
            resolve_tree=lambda file_path, parsed, cfg, log_dir: failed_tree,
        )
    )
    monkeypatch.setattr("managers.get_manager_spec", lambda dm_type: spec)

    errors = refresh_dependency_evidence({
        "cfg": {"log_dir": str(tmp_path)},
        "file_results": [{
            "dm_type": "gradle",
            "file_path": str(tmp_path / "build.gradle"),
            "display_changes": [{"package": "x"}],
            "write_status": "Written",
        }],
    })

    assert len(errors) == 1
    assert "stale" in errors[0]


def test_refresh_syncs_after_tree_snapshot_on_success(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from shared.verification import refresh_dependency_evidence

    (tmp_path / "gradle-dependency-tree.txt").write_text(
        "+--- ch.qos.logback:logback-core:1.5.38\n", encoding="utf-8"
    )
    (tmp_path / "gradle-dependency-tree-after.txt").write_text(
        "+--- ch.qos.logback:logback-core:1.5.25\n", encoding="utf-8"
    )

    spec = SimpleNamespace(
        parser=SimpleNamespace(
            parse=lambda file_path: object(),
            resolve_tree=lambda file_path, parsed, cfg, log_dir: SimpleNamespace(tree_failed=False),
        )
    )
    monkeypatch.setattr("managers.get_manager_spec", lambda dm_type: spec)

    errors = refresh_dependency_evidence({
        "cfg": {"log_dir": str(tmp_path)},
        "file_results": [{
            "dm_type": "gradle",
            "file_path": str(tmp_path / "build.gradle"),
            "display_changes": [{"package": "x"}],
            "write_status": "Written",
        }],
    })

    assert errors == []
    after = (tmp_path / "gradle-dependency-tree-after.txt").read_text(encoding="utf-8")
    assert "1.5.38" in after


def test_gradle_test_skips_non_executable_wrapper(tmp_path, monkeypatch):
    """Live bug: a checked-out gradlew without the executable bit (git
    doesn't always preserve it) raised PermissionError when exec'd directly,
    since the wrapper-selection here only checked wrapper.exists() and never
    checked os.access(..., X_OK) like parsers.gradle_tree.get_gradle_cmd does
    for the rest of the pipeline. It should fall back to the system `gradle`
    command instead of crashing.
    """
    from shared.verification import _gradle_test

    build_file = tmp_path / "build.gradle"
    build_file.write_text("", encoding="utf-8")
    wrapper = tmp_path / "gradlew"
    wrapper.write_text("#!/bin/sh\necho fake gradlew\n", encoding="utf-8")
    wrapper.chmod(0o644)

    captured_cmd = {}

    def fake_run(cmd, cwd, timeout, label):
        captured_cmd["cmd"] = cmd
        return {"label": label, "status": "passed", "output": "> Task :test\n"}

    monkeypatch.setattr("shared.verification._run", fake_run)

    _gradle_test({"file_path": str(build_file)}, {})

    assert captured_cmd["cmd"][0] == "gradle"


def _init_git_repo_with_package_json(tmp_path, original_text):
    import subprocess

    package_json = tmp_path / "package.json"
    package_json.write_text(original_text, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=a@b.c", "-c", "user.name=test", "add", "package.json"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.email=a@b.c", "-c", "user.name=test", "commit", "-q", "-m", "init"],
        cwd=tmp_path, check=True,
    )
    return package_json


_TIMEZONE_FAIL_OUTPUT = (
    "Summary of all failing tests\n"
    "FAIL __tests__/utils/formateUtils.test.ts\n"
    "  ● formats given date correctly\n"
)


def test_node_verification_keeps_updates_when_failure_predates_remediation(tmp_path, monkeypatch):
    """Live bug: cwih-cnp-mgmt-admin-ui's dependency updates (quill, postcss,
    ws) succeeded, but npm test failed on two timezone-sensitive
    date-formatting tests unrelated to the bump — finalize_verification still
    flipped the repo to Failed since there was no Node equivalent of Gradle's
    pre-existing-failure baseline tolerance. Rerunning the same failing suite
    against the pre-remediation package.json should show the same failure and
    downgrade the status instead of blocking an otherwise-clean remediation.
    """
    from shared.verification import run_discovered_tests

    original_text = json.dumps({"name": "x", "version": "1.0.0", "scripts": {"test": "jest"}})
    package_json = _init_git_repo_with_package_json(tmp_path, original_text)
    current_text = json.dumps({"name": "x", "version": "1.0.1", "scripts": {"test": "jest"}})
    package_json.write_text(current_text, encoding="utf-8")

    run_calls = []

    def fake_run(command, cwd, timeout, label):
        run_calls.append(list(command))
        if command[1] == "install":
            return {"label": label, "status": "passed", "output": ""}
        return {
            "label": label,
            "status": "failed",
            "output": _TIMEZONE_FAIL_OUTPUT,
        }

    monkeypatch.setattr("shared.verification._run", fake_run)

    results = {
        "cfg": {"npm_cmd": "npm", "npm_timeout": 1},
        "file_results": [
            {
                "dm_type": "node",
                "file_path": str(package_json),
                "pkg_json_path": str(package_json),
                "display_changes": [{"package": "quill"}],
                "write_status": "Written",
            }
        ],
    }

    tests = run_discovered_tests(results)

    assert tests["status"] == "not_run"
    assert "pre-existing" in tests["results"][0]["reason"]
    # package.json must end up back at the post-remediation content, not the
    # baseline snapshot used mid-check.
    assert package_json.read_text(encoding="utf-8") == current_text
    assert [c[1] for c in run_calls] == ["test", "install", "test", "install"]


def test_node_verification_reports_failure_when_baseline_passes(tmp_path, monkeypatch):
    """A genuine regression caused by the dependency bump — the baseline
    (pre-remediation) test run passes, so the failure must not be downgraded.
    """
    from shared.verification import run_discovered_tests

    original_text = json.dumps({"name": "x", "version": "1.0.0", "scripts": {"test": "jest"}})
    package_json = _init_git_repo_with_package_json(tmp_path, original_text)
    current_text = json.dumps({"name": "x", "version": "1.0.1", "scripts": {"test": "jest"}})
    package_json.write_text(current_text, encoding="utf-8")

    def fake_run(command, cwd, timeout, label):
        if command[1] == "install":
            return {"label": label, "status": "passed", "output": ""}
        current_on_disk = json.loads(
            (tmp_path / "package.json").read_text(encoding="utf-8")
        )
        if current_on_disk["version"] == "1.0.1":
            return {"label": label, "status": "failed", "output": _TIMEZONE_FAIL_OUTPUT}
        return {"label": label, "status": "passed", "output": ""}

    monkeypatch.setattr("shared.verification._run", fake_run)

    results = {
        "cfg": {"npm_cmd": "npm", "npm_timeout": 1},
        "file_results": [
            {
                "dm_type": "node",
                "file_path": str(package_json),
                "pkg_json_path": str(package_json),
                "display_changes": [{"package": "quill"}],
                "write_status": "Written",
            }
        ],
    }

    tests = run_discovered_tests(results)

    assert tests["status"] == "failed"
    assert package_json.read_text(encoding="utf-8") == current_text


def test_gradle_test_runs_without_a_reusable_daemon(tmp_path, monkeypatch):
    """Live bug: two repos with dependency updates that wrote and validated
    cleanly (write_status Written, validation_status Passed) still ended up
    Failed because this post-hoc test run used --daemon, and a persistent
    daemon got killed mid-build under batch-run parallelism ("Gradle build
    daemon disappeared unexpectedly"). shared.build_validation.validate_gradle_project
    already avoids this by using --no-daemon; this call should match.
    """
    from shared.verification import _gradle_test

    build_file = tmp_path / "build.gradle"
    build_file.write_text("", encoding="utf-8")

    captured_cmd = {}

    def fake_run(cmd, cwd, timeout, label):
        captured_cmd["cmd"] = cmd
        return {"label": label, "status": "passed", "output": "> Task :test\n"}

    monkeypatch.setattr("shared.verification._run", fake_run)

    _gradle_test({"file_path": str(build_file)}, {"gradle_cmd": "gradle"})

    assert "--no-daemon" in captured_cmd["cmd"]
    assert "--daemon" not in captured_cmd["cmd"]


_DAEMON_CRASH_OUTPUT = (
    "FAILURE: Build failed with an exception.\n\n"
    "* What went wrong:\n"
    "Gradle build daemon disappeared unexpectedly (it may have been killed "
    "or may have crashed)\n"
)


def test_gradle_test_retries_and_recovers_from_transient_daemon_crash(
    tmp_path, monkeypatch,
):
    """Live bug: cwih-cnp-mgmt-preference-api's build validation already ran
    :test successfully (BUILD SUCCESSFUL, real test output) but this separate,
    later verification re-run crashed with zero test output ("Gradle build
    daemon disappeared unexpectedly") and got reported as "tests did not
    pass" -- an infra crash, not a real test failure. Retrying once (matching
    build_validation.py's own handling of this exact crash class) should
    recover instead of failing the whole repo.
    """
    from shared.verification import _gradle_test

    build_file = tmp_path / "build.gradle"
    build_file.write_text("", encoding="utf-8")

    calls = []

    def fake_run(cmd, cwd, timeout, label):
        calls.append(timeout)
        if len(calls) == 1:
            return {"label": label, "status": "failed", "output": _DAEMON_CRASH_OUTPUT}
        return {"label": label, "status": "passed", "output": "> Task :test\n"}

    monkeypatch.setattr("shared.verification._run", fake_run)

    result = _gradle_test({"file_path": str(build_file)}, {"gradle_cmd": "gradle"})

    assert result["status"] == "passed"
    assert len(calls) == 2
    assert calls[1] > calls[0]


def test_gradle_test_reports_not_run_when_daemon_crash_persists(tmp_path, monkeypatch):
    """If the retry also crashes with zero test output, this must not be
    counted as a failed test -- it's still unrelated infra flakiness, twice.
    Reporting it as "failed" (as before this fix) marked otherwise-passing
    repos Failed for a reason that had nothing to do with the code.
    """
    from shared.verification import _gradle_test

    build_file = tmp_path / "build.gradle"
    build_file.write_text("", encoding="utf-8")

    def fake_run(cmd, cwd, timeout, label):
        return {"label": label, "status": "failed", "output": _DAEMON_CRASH_OUTPUT}

    monkeypatch.setattr("shared.verification._run", fake_run)

    result = _gradle_test({"file_path": str(build_file)}, {"gradle_cmd": "gradle"})

    assert result["status"] == "not_run"
    assert "crashed" in result["reason"]


def test_gradle_test_does_not_mask_real_failure_alongside_daemon_crash_text(
    tmp_path, monkeypatch,
):
    """Guard against over-matching: if genuine per-test failures are present
    in the output alongside daemon-crash-sounding text, this must stay
    "failed" -- only a crash with zero test evidence gets excused.
    """
    from shared.verification import _gradle_test

    build_file = tmp_path / "build.gradle"
    build_file.write_text("", encoding="utf-8")

    output = _DAEMON_CRASH_OUTPUT + "\nSomeRealTest > breaksOnNewJackson() FAILED\n"

    def fake_run(cmd, cwd, timeout, label):
        return {"label": label, "status": "failed", "output": output}

    monkeypatch.setattr("shared.verification._run", fake_run)

    result = _gradle_test({"file_path": str(build_file)}, {"gradle_cmd": "gradle"})

    assert result["status"] == "failed"


_GRADLE_VAULT_FAIL_OUTPUT = (
    "SomeConfigTest > loadsVaultContext() FAILED\n"
    "    com.example.VaultUnavailableException\n"
)


def test_gradle_verification_keeps_updates_when_failure_predates_remediation(
    tmp_path, monkeypatch,
):
    """Live bug: consent-api's dependency updates succeeded (build validation
    itself reported Passed, likely via isolation excluding whatever candidate
    would have broken the build), but this separate, later gradle test re-run
    still failed on an environment-dependent test (a Vault context load,
    which routinely fails in this sandbox with no live Vault server,
    confirmed live) -- the pipeline had no way to tell that apart from a
    genuine regression, since build_validation's own pre-existing-failure CSV
    is only written when ITS internal build-failure comparison runs, which it
    doesn't when isolation resolves the build to Passed. This must fall back
    to running its own baseline (pre-remediation build.gradle) test pass, the
    same way Node's equivalent check already does.
    """
    from shared.verification import run_discovered_tests

    build_file = tmp_path / "build.gradle"
    original_text = "dependencies { implementation 'org.example:parent:1.0.0' }\n"
    current_text = "dependencies { implementation 'org.example:parent:1.2.0' }\n"
    build_file.write_text(current_text, encoding="utf-8")

    def fake_run(cmd, cwd, timeout, label):
        return {"label": label, "status": "failed", "output": _GRADLE_VAULT_FAIL_OUTPUT}

    def fake_validate_gradle_project(build_file_path, gradle_cmd, timeout=600):
        # Baseline run happens against the pre-remediation text -- same
        # environment-dependent failure, unrelated to the version bump.
        text = Path(build_file_path).read_text(encoding="utf-8")
        assert text == original_text
        from shared.build_validation import BuildValidationError

        raise BuildValidationError(_GRADLE_VAULT_FAIL_OUTPUT)

    monkeypatch.setattr("shared.verification._run", fake_run)
    monkeypatch.setattr(
        "shared.build_validation.validate_gradle_project",
        fake_validate_gradle_project,
    )
    monkeypatch.setattr(
        "shared.verification._preexisting_failure_baseline", lambda log_dir: set()
    )

    results = {
        "cfg": {"gradle_cmd": "gradle", "gradle_timeout": 1, "log_dir": str(tmp_path)},
        "file_results": [
            {
                "dm_type": "gradle",
                "file_path": str(build_file),
                "display_changes": [{"dependency": "org.example:parent"}],
                "write_status": "Written",
                "build_text": original_text,
            }
        ],
    }

    tests = run_discovered_tests(results)

    assert tests["status"] == "not_run"
    assert "pre-existing" in tests["results"][0]["reason"]
    # build.gradle must end up back at the post-remediation content, not the
    # baseline snapshot used mid-check.
    assert build_file.read_text(encoding="utf-8") == current_text


def test_gradle_verification_reports_failure_when_baseline_passes(tmp_path, monkeypatch):
    """A genuine regression caused by the dependency bump -- the baseline
    (pre-remediation) test run passes, so the failure must not be downgraded.
    """
    from shared.verification import run_discovered_tests

    build_file = tmp_path / "build.gradle"
    original_text = "dependencies { implementation 'org.example:parent:1.0.0' }\n"
    current_text = "dependencies { implementation 'org.example:parent:1.2.0' }\n"
    build_file.write_text(current_text, encoding="utf-8")

    def fake_run(cmd, cwd, timeout, label):
        return {"label": label, "status": "failed", "output": _GRADLE_VAULT_FAIL_OUTPUT}

    def fake_validate_gradle_project(build_file_path, gradle_cmd, timeout=600):
        return None  # baseline build passes cleanly

    monkeypatch.setattr("shared.verification._run", fake_run)
    monkeypatch.setattr(
        "shared.build_validation.validate_gradle_project",
        fake_validate_gradle_project,
    )
    monkeypatch.setattr(
        "shared.verification._preexisting_failure_baseline", lambda log_dir: set()
    )

    results = {
        "cfg": {"gradle_cmd": "gradle", "gradle_timeout": 1, "log_dir": str(tmp_path)},
        "file_results": [
            {
                "dm_type": "gradle",
                "file_path": str(build_file),
                "display_changes": [{"dependency": "org.example:parent"}],
                "write_status": "Written",
                "build_text": original_text,
            }
        ],
    }

    tests = run_discovered_tests(results)

    assert tests["status"] == "failed"
    assert build_file.read_text(encoding="utf-8") == current_text
