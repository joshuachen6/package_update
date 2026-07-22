import csv
import json
import os
import subprocess

import pytest

import shared.build_validation as bv


def _csv_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_candidate_ranking_prefers_a_group_named_in_the_error_over_incidental_stack_frames():
    """Reproduces the real cwih-cnp-mgmt-cds-workflow ordering failure.

    The exception type itself names ch.qos.logback.core (dotted — Java error
    text never uses the hyphenated Maven artifact id "logback-core"), while
    Spring's own test-context machinery shows up in the surrounding stack
    trace purely as an innocent bystander. Every org.springframework:*
    candidate shares that group, so without a literal group-in-message check
    they all tied for the generic stack-frame boost and outranked the actual
    culprit — logback-core was tried dead last out of 15 candidates in the
    real run this reproduces.
    """
    failure = (
        "java.lang.NoSuchMethodError: 'void ch.qos.logback.core.util.VersionUtil"
        ".checkForVersionEquality(ch.qos.logback.core.Context, java.lang.Class, "
        "java.lang.Class, java.lang.String, java.lang.String)'\n"
        "\tat org.apache.commons.logging.LogAdapter$Slf4jAdapter.createLocationAwareLog"
        "(LogAdapter.java:121)\n"
        "\tat org.springframework.test.context.TestContextManager.<clinit>"
        "(TestContextManager.java:93)\n"
        "\tat org.springframework.test.context.junit.jupiter.SpringExtension.beforeAll"
        "(SpringExtension.java:128)\n"
    )
    candidates = [
        {"package": "org.springframework:spring-context", "change_type": "gradle-force", "old": "6.2.17", "new": "6.2.19"},
        {"package": "org.springframework:spring-webmvc", "change_type": "gradle-force", "old": "6.2.17", "new": "6.2.19"},
        {"package": "org.springframework:spring-web", "change_type": "gradle-force", "old": "6.2.17", "new": "6.2.19"},
        {"package": "ch.qos.logback:logback-core", "change_type": "gradle", "old": "1.5.25", "new": "1.5.38"},
    ]

    ordered = bv._ordered_candidates(candidates, failure)

    assert ordered[0]["package"] == "ch.qos.logback:logback-core"


def test_candidate_ranking_direct_message_match_outscores_incidental_stack_frame_match():
    failure = "NoSuchMethodError: ch.qos.logback.core.util.VersionUtil.checkForVersionEquality"
    incidental = "at org.springframework.test.context.TestContextManager.<clinit>(TestContextManager.java:93)"

    culprit_score = bv._candidate_rank(failure, "ch.qos.logback:logback-core")
    bystander_score = bv._candidate_rank(incidental, "org.springframework:spring-context")

    assert culprit_score > bystander_score


def test_node_validation_auto_rolls_back_breaking_package_and_logs(tmp_path, monkeypatch):
    package_json = tmp_path / "package.json"
    original = {
        "dependencies": {
            "safe": "^1.0.0",
            "breaking-pkg": "^1.0.0",
        }
    }
    updated = {
        "dependencies": {
            "safe": "^1.0.1",
            "breaking-pkg": "^2.0.0",
        }
    }
    package_json.write_text(json.dumps(updated), encoding="utf-8")

    calls = {"count": 0}

    def fake_validate(path, npm_cmd="npm", timeout=600):
        calls["count"] += 1
        data = json.loads(package_json.read_text(encoding="utf-8"))
        if data["dependencies"].get("breaking-pkg") == "^2.0.0":
            raise bv.BuildValidationError("build failed in breaking-pkg")

    monkeypatch.setattr(bv, "validate_node_project", fake_validate)

    bv.validate_node_project_or_rollback(
        str(package_json),
        json.dumps(original),
        direct_changes=[
            {
                "package": "safe",
                "old_spec": "^1.0.0",
                "new_spec": "^1.0.1",
            },
            {
                "package": "breaking-pkg",
                "old_spec": "^1.0.0",
                "new_spec": "^2.0.0",
            },
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
    )

    final = json.loads(package_json.read_text(encoding="utf-8"))
    assert final["dependencies"]["safe"] == "^1.0.1"
    assert final["dependencies"]["breaking-pkg"] == "^1.0.0"
    assert calls["count"] == 2

    rows = _csv_rows(tmp_path / "build-validation-auto-fixes.csv")
    assert rows[0]["package"] == "breaking-pkg"
    assert rows[0]["status"] == "auto_rolled_back"


def test_node_validation_marks_manual_updates_when_auto_isolation_fails(tmp_path, monkeypatch):
    package_json = tmp_path / "package.json"
    original = {"dependencies": {"a": "^1.0.0", "b": "^1.0.0"}}
    updated = {"dependencies": {"a": "^2.0.0", "b": "^2.0.0"}}
    package_json.write_text(json.dumps(updated), encoding="utf-8")

    def fake_validate(path, npm_cmd="npm", timeout=600):
        raise bv.BuildValidationError("build still failed")

    monkeypatch.setattr(bv, "validate_node_project", fake_validate)
    with pytest.raises(bv.BuildValidationManualUpdatesError):
        bv.validate_node_project_or_rollback(
            str(package_json),
            json.dumps(original),
            direct_changes=[
                {"package": "a", "old_spec": "^1.0.0", "new_spec": "^2.0.0"},
                {"package": "b", "old_spec": "^1.0.0", "new_spec": "^2.0.0"},
            ],
            log_dir=str(tmp_path),
        )

    assert json.loads(package_json.read_text(encoding="utf-8")) == original
    rows = _csv_rows(tmp_path / "build-validation-manual-updates.csv")
    assert {row["package"] for row in rows} == {"a", "b"}
    assert {row["status"] for row in rows} == {"manual_update_required"}


def test_node_validation_first_try_success_clears_stale_manual_updates_csv(tmp_path, monkeypatch):
    """A prior failed run's manual-updates.csv must not linger after a later run succeeds outright."""
    package_json = tmp_path / "package.json"
    original = {"dependencies": {"safe": "^1.0.0"}}
    package_json.write_text(json.dumps(original), encoding="utf-8")

    stale_csv = tmp_path / "build-validation-manual-updates.csv"
    stale_csv.write_text(
        "package,change_type,old,new,status,reason\n"
        "leftover,gradle,1.0.0,2.0.0,manual_update_required,stale from a previous failed run\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(bv, "validate_node_project", lambda path, npm_cmd="npm", timeout=600: None)

    bv.validate_node_project_or_rollback(
        str(package_json),
        json.dumps(original),
        log_dir=str(tmp_path),
    )

    assert not stale_csv.exists()


def test_node_validation_first_try_success_clears_stale_auto_fixes_csv(tmp_path, monkeypatch):
    """Seen live: a repo whose build passed clean on the first try was still
    reported Manual Update Required, because an auto-fixes.csv left behind by
    an unrelated earlier run was still sitting in the same log_dir and
    report.py's CSV-presence fallback read it as this run needing attention.
    A clean first-try success never rewrites auto-fixes.csv itself, so it must
    actively clear a stale one rather than leaving it for the report to find.
    """
    package_json = tmp_path / "package.json"
    original = {"dependencies": {"safe": "^1.0.0"}}
    package_json.write_text(json.dumps(original), encoding="utf-8")

    stale_csv = tmp_path / "build-validation-auto-fixes.csv"
    stale_csv.write_text(
        "package,change_type,old,new,status,reason\n"
        "old-pkg,gradle,1.0.0,2.0.0,auto_rolled_back,from an unrelated earlier run\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(bv, "validate_node_project", lambda path, npm_cmd="npm", timeout=600: None)

    bv.validate_node_project_or_rollback(
        str(package_json),
        json.dumps(original),
        log_dir=str(tmp_path),
    )

    assert not stale_csv.exists()


def test_node_validation_isolation_success_clears_stale_manual_updates_csv(tmp_path, monkeypatch):
    """Same as above, but for a success reached via single-package rollback rather than the first try."""
    package_json = tmp_path / "package.json"
    original = {"dependencies": {"safe": "^1.0.0", "breaking-pkg": "^1.0.0"}}
    updated = {"dependencies": {"safe": "^1.0.1", "breaking-pkg": "^2.0.0"}}
    package_json.write_text(json.dumps(updated), encoding="utf-8")

    stale_csv = tmp_path / "build-validation-manual-updates.csv"
    stale_csv.write_text(
        "package,change_type,old,new,status,reason\n"
        "leftover,gradle,1.0.0,2.0.0,manual_update_required,stale from a previous failed run\n",
        encoding="utf-8",
    )

    def fake_validate(path, npm_cmd="npm", timeout=600):
        data = json.loads(package_json.read_text(encoding="utf-8"))
        if data["dependencies"].get("breaking-pkg") == "^2.0.0":
            raise bv.BuildValidationError("build failed in breaking-pkg")

    monkeypatch.setattr(bv, "validate_node_project", fake_validate)

    bv.validate_node_project_or_rollback(
        str(package_json),
        json.dumps(original),
        direct_changes=[
            {"package": "safe", "old_spec": "^1.0.0", "new_spec": "^1.0.1"},
            {"package": "breaking-pkg", "old_spec": "^1.0.0", "new_spec": "^2.0.0"},
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
    )

    assert not stale_csv.exists()


def test_gradle_validation_auto_rolls_back_breaking_dependency_and_logs(tmp_path, monkeypatch):
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:bad:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:bad:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        if "org.example:bad:2.0.0" in build_file.read_text(encoding="utf-8"):
            raise bv.BuildValidationError("compile failed org.example:bad")

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        changes=[
            {
                "dependency": "org.example:bad",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "original": "implementation 'org.example:bad:1.0.0'",
                "replacement": "implementation 'org.example:bad:2.0.0'",
            }
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
    )

    assert build_file.read_text(encoding="utf-8") == original
    rows = _csv_rows(tmp_path / "build-validation-auto-fixes.csv")
    assert rows[0]["package"] == "org.example:bad"
    assert rows[0]["status"] == "auto_rolled_back"


def test_gradle_validation_steps_down_to_intermediate_safe_version_before_full_revert(
    tmp_path, monkeypatch
):
    """Mirrors the real cwih-cnp-mgmt-cds-workflow failure: a direct dependency
    breaks the build at its chosen target version, but an intermediate version
    (still non-vulnerable, still accessible) fixes it — that must be preferred
    over fully reverting to the original vulnerable version.
    """
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'ch.qos.logback:logback-core:1.5.25'\n}\n"
    updated = "dependencies {\n    implementation 'ch.qos.logback:logback-core:1.5.38'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        text = build_file.read_text(encoding="utf-8")
        if "logback-core:1.5.38" in text:
            raise bv.BuildValidationError(
                "NoSuchMethodError: VersionUtil.checkForVersionEquality"
            )

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    import parsers.gradle as gradle

    monkeypatch.setattr(
        gradle,
        "get_available_versions",
        lambda *args, **kwargs: (
            [
                bv.MavenVersion.parse("1.5.25"),
                bv.MavenVersion.parse("1.5.32"),
                bv.MavenVersion.parse("1.5.38"),
            ],
            "",
        ),
    )
    monkeypatch.setattr(gradle, "find_accessible_version", lambda *args, **kwargs: "1.5.32")
    monkeypatch.setattr("registry.maven.version_accessible", lambda *args, **kwargs: True)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        changes=[
            {
                "dependency": "ch.qos.logback:logback-core",
                "old_version": "1.5.25",
                "new_version": "1.5.38",
                "original": "implementation 'ch.qos.logback:logback-core:1.5.25'",
                "replacement": "implementation 'ch.qos.logback:logback-core:1.5.38'",
            }
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
        base_url="https://repo.example",
    )

    updated_text = build_file.read_text(encoding="utf-8")
    assert "logback-core:1.5.32" in updated_text
    assert "logback-core:1.5.38" not in updated_text
    # Must NOT have fully surrendered the CVE fix by reverting to the original.
    assert "logback-core:1.5.25" not in updated_text

    rows = _csv_rows(tmp_path / "build-validation-auto-fixes.csv")
    assert rows[0]["package"] == "ch.qos.logback:logback-core"
    assert rows[0]["status"] == "stepped_down"
    assert rows[0]["new"] == "1.5.32"


def test_failed_validation_clears_stale_auto_fixes_csv(tmp_path, monkeypatch):
    """A failed run must not leave auto_rolled_back rows from an earlier
    successful pass — everything was just restored to the original text, so
    those rows no longer describe reality (seen live in cds-workflow's report:
    a stale 'build passed after single-package rollback' row shown alongside
    fresh manual_update_required rows).
    """
    package_json = tmp_path / "package.json"
    original = {"dependencies": {"a": "^1.0.0"}}
    updated = {"dependencies": {"a": "^2.0.0"}}
    package_json.write_text(json.dumps(updated), encoding="utf-8")

    stale = tmp_path / "build-validation-auto-fixes.csv"
    stale.write_text(
        "package,change_type,old,new,status,reason\n"
        "old-pkg,gradle,1,2,auto_rolled_back,from a previous run\n",
        encoding="utf-8",
    )

    def fake_validate(path, npm_cmd="npm", timeout=600):
        raise bv.BuildValidationError("build still failed")

    monkeypatch.setattr(bv, "validate_node_project", fake_validate)

    with pytest.raises(bv.BuildValidationManualUpdatesError):
        bv.validate_node_project_or_rollback(
            str(package_json),
            json.dumps(original),
            direct_changes=[{"package": "a", "old_spec": "^1.0.0", "new_spec": "^2.0.0"}],
            log_dir=str(tmp_path),
        )

    assert not stale.exists()


def test_gradle_validation_keeps_updates_when_failure_predates_remediation(
    tmp_path, monkeypatch
):
    """A build that fails with the exact same failing tests before AND after
    the dependency updates is a pre-existing environment/test problem, not a
    remediation regression — the updates must be kept, not rolled back.
    """
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:lib:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:lib:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        # Fails identically no matter which file content is on disk — the
        # classic infra-dependent context-load test.
        raise bv.BuildValidationError(
            "Execution failed for task ':test'.\n"
            "IngestionServiceApplicationTest > initializationError FAILED\n"
        )

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        changes=[
            {
                "dependency": "org.example:lib",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "original": "implementation 'org.example:lib:1.0.0'",
                "replacement": "implementation 'org.example:lib:2.0.0'",
            }
        ],
        log_dir=str(tmp_path),
    )

    # Updates kept — not rolled back to the original.
    assert build_file.read_text(encoding="utf-8") == updated
    rows = _csv_rows(tmp_path / "build-validation-preexisting-failures.csv")
    assert rows[0]["task"] == ":test"
    assert rows[0]["test"] == "IngestionServiceApplicationTest > initializationError"
    assert rows[0]["status"] == "preexisting_test_failure"


def test_gradle_validation_rolls_back_when_a_new_test_failure_appears(
    tmp_path, monkeypatch
):
    """A failing test NOT present at baseline is a real regression — the
    pre-existing shortcut must not swallow it.
    """
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:lib:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:lib:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        failing = "FlakyInfraTest > contextLoads() FAILED\n"
        if "2.0.0" in build_file.read_text(encoding="utf-8"):
            failing += "SerializationTest > roundTrip() FAILED\n"
        raise bv.BuildValidationError(
            "Execution failed for task ':test'.\n" + failing
        )

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    with pytest.raises(bv.BuildValidationManualUpdatesError):
        bv.validate_gradle_project_or_rollback(
            str(build_file),
            original,
            "gradle",
            changes=[
                {
                    "dependency": "org.example:lib",
                    "old_version": "1.0.0",
                    "new_version": "2.0.0",
                    "original": "implementation 'org.example:lib:1.0.0'",
                    "replacement": "implementation 'org.example:lib:2.0.0'",
                }
            ],
            log_dir=str(tmp_path),
        )

    assert build_file.read_text(encoding="utf-8") == original
    assert not (tmp_path / "build-validation-preexisting-failures.csv").exists()


def test_extract_failing_tests_ignores_task_lines():
    output = (
        "> Task :test FAILED\n"
        "IngestionServiceApplicationTest > initializationError FAILED\n"
        "SomeTest > method() FAILED\n"
        "BUILD FAILED in 13s\n"
    )
    assert bv._extract_failing_tests(output) == {
        "IngestionServiceApplicationTest > initializationError",
        "SomeTest > method()",
    }


def test_verification_downgrades_preexisting_test_failures(tmp_path, monkeypatch):
    import shared.verification as sv

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}\n", encoding="utf-8")
    (tmp_path / "build-validation-preexisting-failures.csv").write_text(
        "task,test,status,reason\n"
        ':test,IngestionServiceApplicationTest > initializationError,preexisting_test_failure,recorded\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sv,
        "_gradle_test",
        lambda file_result, cfg: {
            "label": "Gradle tests",
            "status": "failed",
            "output": "IngestionServiceApplicationTest > initializationError FAILED\n",
        },
    )

    results = {
        "cfg": {"log_dir": str(tmp_path)},
        "file_results": [
            {
                "dm_type": "gradle",
                "file_path": str(build_file),
                "display_changes": [{"package": "x"}],
                "write_status": "Written",
            }
        ],
    }

    tests = sv.run_discovered_tests(results)

    assert tests["status"] != "failed"
    assert tests["results"][0]["status"] == "not_run"
    assert "pre-existing" in tests["results"][0]["reason"]


def test_verification_keeps_failure_when_no_baseline_recorded(tmp_path, monkeypatch):
    import shared.verification as sv

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}\n", encoding="utf-8")

    monkeypatch.setattr(
        sv,
        "_gradle_test",
        lambda file_result, cfg: {
            "label": "Gradle tests",
            "status": "failed",
            "output": "SomeTest > method() FAILED\n",
        },
    )

    results = {
        "cfg": {"log_dir": str(tmp_path)},
        "file_results": [
            {
                "dm_type": "gradle",
                "file_path": str(build_file),
                "display_changes": [{"package": "x"}],
                "write_status": "Written",
            }
        ],
    }

    tests = sv.run_discovered_tests(results)

    assert tests["status"] == "failed"


def test_gradle_validation_marks_manual_updates_when_auto_isolation_fails(tmp_path, monkeypatch):
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:a:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:a:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        raise bv.BuildValidationError("gradle build failed")

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    with pytest.raises(bv.BuildValidationManualUpdatesError):
        bv.validate_gradle_project_or_rollback(
            str(build_file),
            original,
            "gradle",
            changes=[
                {
                    "dependency": "org.example:a",
                    "old_version": "1.0.0",
                    "new_version": "2.0.0",
                    "original": "implementation 'org.example:a:1.0.0'",
                    "replacement": "implementation 'org.example:a:2.0.0'",
                }
            ],
            log_dir=str(tmp_path),
        )

    assert build_file.read_text(encoding="utf-8") == original
    rows = _csv_rows(tmp_path / "build-validation-manual-updates.csv")
    assert rows[0]["package"] == "org.example:a"
    assert rows[0]["status"] == "manual_update_required"


def test_gradle_validation_logs_external_blocker_when_failure_does_not_match_candidates(
    tmp_path, monkeypatch
):
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:a:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:a:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        raise bv.BuildValidationError(
            "Could not download jackson-databind-2.22.0.jar "
            "(com.fasterxml.jackson.core:jackson-databind:2.22.0)"
        )

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    with pytest.raises(bv.BuildValidationManualUpdatesError):
        bv.validate_gradle_project_or_rollback(
            str(build_file),
            original,
            "gradle",
            changes=[
                {
                    "dependency": "org.example:a",
                    "old_version": "1.0.0",
                    "new_version": "2.0.0",
                    "original": "implementation 'org.example:a:1.0.0'",
                    "replacement": "implementation 'org.example:a:2.0.0'",
                }
            ],
            log_dir=str(tmp_path),
        )

    assert build_file.read_text(encoding="utf-8") == original
    rows = _csv_rows(tmp_path / "build-validation-external-blockers.csv")
    assert rows[0]["ecosystem"] == "gradle"
    assert rows[0]["blocker"] == "jackson-databind:2.22.0"
    assert rows[0]["status"] == "external_build_blocker"

def test_gradle_validation_auto_forces_external_blocker_when_build_passes(
    tmp_path, monkeypatch
):
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:a:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:a:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    calls = {"validate": 0}

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        calls["validate"] += 1
        if calls["validate"] == 1:
            raise bv.BuildValidationError(
                "Could not download jackson-databind-2.22.0.jar "
                "(com.fasterxml.jackson.core:jackson-databind:2.22.0)\n"
                "Could not GET "
                "'https://repo.example/maven/com/fasterxml/jackson/core/"
                "jackson-databind/2.22.0/jackson-databind-2.22.0.jar'. "
                "Received status code 403"
            )
    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    import parsers.gradle as gradle
    import parsers.gradle_tree as gradle_tree

    monkeypatch.setattr(
        gradle,
        "get_available_versions",
        lambda *args, **kwargs: (
            [bv.MavenVersion.parse("2.22.0"), bv.MavenVersion.parse("2.21.5")],
            "",
        ),
    )
    monkeypatch.setattr(
        gradle,
        "find_accessible_version",
        lambda *args, **kwargs: "2.21.5",
    )
    def fake_inject_forces(build_text, forces):
        assert forces == {"com.fasterxml.jackson.core:jackson-databind": "2.21.5"}
        return build_text + "\\n// forced jackson-databind 2.21.5\\n"

    monkeypatch.setattr(gradle_tree, "_inject_forces", fake_inject_forces)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        changes=[
            {
                "dependency": "org.example:a",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "original": "implementation 'org.example:a:1.0.0'",
                "replacement": "implementation 'org.example:a:2.0.0'",
            }
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
        base_url="https://repo.example",
    )

    assert calls["validate"] == 2
    assert "force \'com.fasterxml.jackson.core:jackson-databind:2.21.5\'" in build_file.read_text(encoding="utf-8")
    rows = _csv_rows(tmp_path / "build-validation-external-auto-fixes.csv")
    assert rows[0]["dependency"] == "com.fasterxml.jackson.core:jackson-databind"
    assert rows[0]["blocked_version"] == "2.22.0"
    assert rows[0]["forced_version"] == "2.21.5"

def test_gradle_external_blocker_fix_retries_transient_daemon_crash(
    tmp_path, monkeypatch
):
    """Live bug: the accessible-version replacement for a 403-blocked
    jackson-databind was found and forced successfully, but the round's
    verification build hit "Gradle build daemon disappeared unexpectedly" —
    unrelated to the fix — and the whole thing was thrown away as if the fix
    itself had failed. Must retry once before giving up on this round.
    """
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:a:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:a:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    calls = {"validate": 0}
    seen_timeouts = []

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        calls["validate"] += 1
        seen_timeouts.append(timeout)
        if calls["validate"] == 1:
            raise bv.BuildValidationError(
                "Could not download jackson-databind-2.22.0.jar "
                "(com.fasterxml.jackson.core:jackson-databind:2.22.0)\n"
                "Could not GET "
                "'https://repo.example/maven/com/fasterxml/jackson/core/"
                "jackson-databind/2.22.0/jackson-databind-2.22.0.jar'. "
                "Received status code 403"
            )
        if calls["validate"] == 2:
            raise bv.BuildValidationError(
                "Gradle build daemon disappeared unexpectedly "
                "(it may have been killed or may have crashed)"
            )

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    import parsers.gradle as gradle
    import parsers.gradle_tree as gradle_tree

    monkeypatch.setattr(
        gradle,
        "get_available_versions",
        lambda *args, **kwargs: (
            [bv.MavenVersion.parse("2.22.0"), bv.MavenVersion.parse("2.21.5")],
            "",
        ),
    )
    monkeypatch.setattr(
        gradle,
        "find_accessible_version",
        lambda *args, **kwargs: "2.21.5",
    )

    def fake_inject_forces(build_text, forces):
        return build_text + "\\n// forced jackson-databind 2.21.5\\n"

    monkeypatch.setattr(gradle_tree, "_inject_forces", fake_inject_forces)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        changes=[
            {
                "dependency": "org.example:a",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "original": "implementation 'org.example:a:1.0.0'",
                "replacement": "implementation 'org.example:a:2.0.0'",
            }
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
        base_url="https://repo.example",
    )

    assert calls["validate"] == 3
    assert (
        "force 'com.fasterxml.jackson.core:jackson-databind:2.21.5'"
        in build_file.read_text(encoding="utf-8")
    )
    rows = _csv_rows(tmp_path / "build-validation-external-auto-fixes.csv")
    assert rows[0]["dependency"] == "com.fasterxml.jackson.core:jackson-databind"
    assert rows[0]["forced_version"] == "2.21.5"
    # Live bug: the post-crash retry reused the same tight timeout as the
    # original attempt, so a cold daemon (no warm JIT/config cache) under the
    # same host contention that caused the crash just timed out instead of
    # recovering. The retry (3rd validate call) must get a wider timeout than
    # the round's normal attempt (2nd call).
    assert seen_timeouts[2] > seen_timeouts[1]


def test_gradle_validation_fixes_candidate_related_blocker_before_rollback(
    tmp_path, monkeypatch
):
    build_file = tmp_path / "build.gradle"
    original = (
        "dependencies {\n"
        "    implementation('io.netty:netty-handler') {\n"
        "        version { strictly '4.1.133.Final' }\n"
        "    }\n"
        "}\n"
    )
    build_file.write_text(original, encoding="utf-8")

    calls = {"validate": 0}

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        calls["validate"] += 1
        if calls["validate"] == 1:
            raise bv.BuildValidationError(
                "Execution failed for task ':compileJava'.\n"
                "> Could not resolve all files for configuration ':compileClasspath'.\n"
                "> Could not download netty-handler-4.1.133.Final.jar "
                "(io.netty:netty-handler:4.1.133.Final)\n"
                "> Could not GET "
                "'https://repo.example/maven/io/netty/netty-handler/4.1.133.Final/"
                "netty-handler-4.1.133.Final.jar'. Received status code 403"
            )
    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    import output.gradle as out_gradle
    import parsers.gradle as gradle

    monkeypatch.setattr(
        gradle,
        "get_available_versions",
        lambda *args, **kwargs: (
            [
                bv.MavenVersion.parse("4.1.133.Final"),
                bv.MavenVersion.parse("4.1.132.Final"),
            ],
            "",
        ),
    )
    monkeypatch.setattr(
        gradle,
        "find_accessible_version",
        lambda *args, **kwargs: "4.1.132.Final",
    )

    real_write_resolution_forces = out_gradle.write_resolution_forces
    monkeypatch.setattr(out_gradle, "write_resolution_forces", real_write_resolution_forces)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        changes=[
            {
                "dependency": "io.netty:netty-handler",
                "old_version": "4.1.132.Final",
                "new_version": "4.1.133.Final",
                "original": "",
                "replacement": "",
            }
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
        base_url="https://repo.example",
    )

    updated = build_file.read_text(encoding="utf-8")
    assert "strictly '4.1.132.Final'" in updated
    assert "force 'io.netty:netty-handler:4.1.132.Final'" in updated
    assert calls["validate"] == 2
def test_gradle_validation_allows_secondary_scan_to_classify_unresolved_blocker(
    tmp_path,
    monkeypatch,
    capsys,
):
    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}\n", encoding="utf-8")

    monkeypatch.setattr(
        bv,
        "_proactive_check_and_fix",
        lambda *args, **kwargs: [
            {
                "package": "com.fasterxml.jackson:jackson-bom",
                "old": "2.21.2",
                "reason": "no accessible replacement",
            }
        ],
    )
    monkeypatch.setattr(
        bv,
        "validate_gradle_project",
        lambda *args, **kwargs: None,
    )

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        build_file.read_text(encoding="utf-8"),
        "gradle",
        base_url="https://repo.example",
    )

    output = capsys.readouterr().out
    assert "build passed" in output
    assert "jackson-bom:2.21.2" in output


def test_exhaustive_isolation_finds_interacting_two_package_subset(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "deps.txt"
    original = "A=old\nB=old\nC=old\n"
    current = "A=new\nB=new\nC=new\n"
    file_path.write_text(current, encoding="utf-8")

    candidates = [
        {
            "package": "A",
            "change_type": "test",
            "old": "old",
            "new": "new",
        },
        {
            "package": "B",
            "change_type": "test",
            "old": "old",
            "new": "new",
        },
        {
            "package": "C",
            "change_type": "test",
            "old": "old",
            "new": "new",
        },
    ]

    def revert(text, candidate):
        return text.replace(
            f"{candidate['package']}=new",
            f"{candidate['package']}=old",
        )

    def validate():
        state = file_path.read_text(encoding="utf-8")
        # Neither rollback works alone. Reverting A and C together passes,
        # while the greedy A+B path does not.
        if "A=old" in state and "C=old" in state:
            return
        raise bv.BuildValidationError("interacting dependency failure")

    bv._run_candidate_trials(
        str(file_path),
        original,
        candidates,
        current,
        validate,
        revert,
        str(tmp_path),
        {},
        enable_failure_isolation=True,
    )

    final = file_path.read_text(encoding="utf-8")
    assert "A=old" in final
    assert "B=new" in final
    assert "C=old" in final


def test_batch_run_all_disables_failure_isolation_by_default():
    from pathlib import Path

    source = Path("ui/batch_tab.py").read_text(encoding="utf-8")
    assert 'settings["enable_failure_isolation"] = bool(enable_phase2)' in source


def test_batch_phase2_button_remains_visible():
    from pathlib import Path

    source = Path("ui/batch_tab.py").read_text(encoding="utf-8")
    assert 'QPushButton("⚠  Run Phase 2")' in source
    assert "self._phase2_btn.hide()" not in source
    assert "self._phase2_btn.setVisible(needs_phase2)" not in source


def test_run_phase2_enables_failure_isolation_without_undefined_name():
    from pathlib import Path

    source = Path("ui/batch_tab.py").read_text(encoding="utf-8")
    phase2_start = source.index("def _run_phase2")
    phase2_body = source[phase2_start : source.index("def _on_all_done")]
    assert "enable_phase2" not in phase2_body
    assert 'settings["enable_failure_isolation"] = True' in phase2_body


def test_needs_phase2_matches_actual_failed_row_status():
    from pathlib import Path

    source = Path("ui/batch_tab.py").read_text(encoding="utf-8")
    assert '"Manual fix"' not in source
    assert 'item.text() == "Failed"' in source
    assert 'self._table.item(r, _COL_STATUS).text() == "Failed"' in source


def test_repeated_unrelated_blocker_stops_exhaustive_search(
    tmp_path,
):
    file_path = tmp_path / "deps.txt"
    original = "A=old\nB=old\nC=old\nD=old\n"
    current = "A=new\nB=new\nC=new\nD=new\n"
    file_path.write_text(current, encoding="utf-8")

    candidates = [
        {
            "package": package,
            "change_type": "test",
            "old": "old",
            "new": "new",
        }
        for package in ("A", "B", "C", "D")
    ]
    calls = {"count": 0}

    def revert(text, candidate):
        return text.replace(
            f"{candidate['package']}=new",
            f"{candidate['package']}=old",
        )

    def validate():
        calls["count"] += 1
        raise bv.BuildValidationError(
            "Accessibility pre-check failed - blocked: "
            "com.example:unrelated-internal:1.0.0"
        )

    with pytest.raises(
        bv.BuildValidationManualUpdatesError
    ):
        bv._run_candidate_trials(
            str(file_path),
            original,
            candidates,
            current,
            validate,
            revert,
            str(tmp_path),
            {},
            enable_failure_isolation=True,
        )

    assert calls["count"] <= 3


def test_gradle_pre_check_ignores_unchanged_baseline_blocker(
    tmp_path,
    monkeypatch,
):
    build_file = tmp_path / "build.gradle"
    baseline = """
dependencies {
    implementation 'com.example:baseline:1.0.0'
    implementation 'com.example:changed:1.0.0'
}
"""
    updated = """
dependencies {
    implementation 'com.example:baseline:1.0.0'
    implementation 'com.example:changed:2.0.0'
}
"""
    build_file.write_text(updated, encoding="utf-8")
    checked = []

    def inaccessible(group, artifact, version, url, auth, timeout):
        checked.append(f"{group}:{artifact}:{version}")
        return False

    monkeypatch.setattr(
        "registry.maven.version_accessible",
        inaccessible,
    )

    pre_check = bv._make_gradle_pre_check_fn(
        str(build_file),
        ["https://repo.example"],
        None,
        None,
        30,
        baseline_text=baseline,
    )

    with pytest.raises(
        bv.BuildValidationError,
        match=r"com\.example:changed:2\.0\.0",
    ) as exc_info:
        pre_check()

    assert "com.example:baseline:1.0.0" not in str(exc_info.value)
    assert checked == ["com.example:changed:2.0.0"]


def test_gradle_pre_check_allows_only_unchanged_baseline_blockers(
    tmp_path,
    monkeypatch,
):
    build_file = tmp_path / "build.gradle"
    baseline = """
dependencies {
    implementation 'com.example:baseline:1.0.0'
}
"""
    build_file.write_text(baseline, encoding="utf-8")

    def should_not_probe(*args, **kwargs):
        raise AssertionError("unchanged baseline dependency was probed")

    monkeypatch.setattr(
        "registry.maven.version_accessible",
        should_not_probe,
    )

    pre_check = bv._make_gradle_pre_check_fn(
        str(build_file),
        ["https://repo.example"],
        None,
        None,
        30,
        baseline_text=baseline,
    )

    pre_check()


def test_gradle_write_plan_honors_configured_validation_timeout(
    tmp_path,
    monkeypatch,
):
    from types import SimpleNamespace

    from managers.gradle import GradleManager

    build_file = tmp_path / "build.gradle"
    build_text = """
dependencies {
    implementation 'com.example:library:1.0.0'
}
"""
    build_file.write_text(build_text, encoding="utf-8")

    captured = {}

    monkeypatch.setattr(
        "parsers.gradle_tree.get_gradle_cmd",
        lambda project_dir: "gradle",
    )

    def capture_validation(
        build_file,
        original_build_text,
        gradle_cmd,
        timeout=600,
        **kwargs,
    ):
        captured["timeout"] = timeout

    monkeypatch.setattr(
        "shared.build_validation.validate_gradle_project_or_rollback",
        capture_validation,
    )

    cfg = SimpleNamespace(
        artifactory_username="",
        artifactory_password="",
        artifactory_source="",
        artifactory_repo="",
        gradle_timeout=30,
        enable_failure_isolation=True,
    )
    result = {
        "build_file": str(build_file),
        "build_text": build_text,
        "changes": [
            {
                "package": "com.example:library",
                "old_version": "1.0.0",
                "new_version": "1.0.1",
            }
        ],
        "force_entries": [],
    }

    plan = GradleManager().make_write_plan(
        cfg,
        result,
        str(tmp_path),
    )
    plan.validate()

    assert captured["timeout"] == 30


def test_run_build_command_timeout_terminates_process_group(
    tmp_path,
):
    import time

    pid_file = tmp_path / "child.pid"
    command = [
        "sh",
        "-c",
        f"sleep 300 & echo $! > {pid_file}; wait",
    ]

    with pytest.raises(
        bv.BuildValidationError,
        match="timed out after 1s",
    ):
        bv._run_build_command(
            command,
            str(tmp_path),
            1,
            "test build",
        )

    child_pid = int(
        pid_file.read_text(encoding="utf-8").strip()
    )
    deadline = time.monotonic() + 3

    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break

        try:
            output = subprocess.run(
                ["ps", "-o", "stat=", "-p", str(child_pid)],
                text=True,
                capture_output=True,
                check=False,
            ).stdout.strip()
        except Exception:
            output = ""
        if not output or output.startswith("Z"):
            break

        time.sleep(0.05)
    else:
        pytest.fail(
            f"child process {child_pid} survived build timeout"
        )


def test_gradle_validation_uses_disposable_daemon(
    tmp_path,
    monkeypatch,
):
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "dependencies {}\n",
        encoding="utf-8",
    )
    captured = {}

    def capture_command(cmd, cwd, timeout, label, **kwargs):

        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            "",
            "",
        )

    monkeypatch.setattr(
        bv,
        "_run_build_command",
        capture_command,
    )

    bv.validate_gradle_project(
        str(build_file),
        "gradle",
        timeout=30,
    )
    assert "--no-daemon" in captured["cmd"]
    assert "--daemon" not in captured["cmd"]
    assert not any(
        arg.startswith("-Dorg.gradle.daemon.idletimeout=")
        for arg in captured["cmd"]
    )


def test_gradle_validation_probes_with_lighter_task_and_confirms_with_full_build(
    tmp_path, monkeypatch
):
    """The isolation search should probe with "test" (cheap), then re-validate
    the winning revert with the full "build" before accepting it as a success
    — so a lighter probe target can never produce a false-positive success.
    """
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:bad:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:bad:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    build_calls = []

    def fake_run_build_command(cmd, cwd, timeout, label):
        build_calls.append(cmd)
        if "2.0.0" in build_file.read_text(encoding="utf-8"):
            raise bv.BuildValidationError("compile failed org.example:bad")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(bv, "_run_build_command", fake_run_build_command)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        changes=[
            {
                "dependency": "org.example:bad",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "original": "implementation 'org.example:bad:1.0.0'",
                "replacement": "implementation 'org.example:bad:2.0.0'",
            }
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
    )

    tasks_used = [cmd[1] for cmd in build_calls]
    assert tasks_used == ["build", "test", "build"]
    # Daemon reuse (--gradle-user-home) was reverted — a fresh, isolated
    # gradle-user-home has none of the real ~/.gradle setup (cached
    # dependency artifacts, Artifactory credentials, wrapper distribution),
    # so every invocation must keep using the caller's normal setup.
    assert all("--gradle-user-home" not in cmd for cmd in build_calls)
    assert all("--no-daemon" in cmd for cmd in build_calls)


def test_gradle_validation_rejects_probe_pass_when_full_build_confirm_fails(
    tmp_path, monkeypatch
):
    """A candidate whose light "test" probe passes but whose full "build"
    confirm still fails must not be accepted — the search must continue.
    """
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:bad:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:bad:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_run_build_command(cmd, cwd, timeout, label, gradle_daemon_scope=None):
        tasks = cmd[1]
        if tasks == "test":
            # The lighter probe always looks fine...
            return subprocess.CompletedProcess(cmd, 0, "", "")
        # ...but the full build never actually passes.
        raise bv.BuildValidationError("packaging task failed")

    monkeypatch.setattr(bv, "_run_build_command", fake_run_build_command)

    with pytest.raises(bv.BuildValidationManualUpdatesError):
        bv.validate_gradle_project_or_rollback(
            str(build_file),
            original,
            "gradle",
            changes=[
                {
                    "dependency": "org.example:bad",
                    "old_version": "1.0.0",
                    "new_version": "2.0.0",
                    "original": "implementation 'org.example:bad:1.0.0'",
                    "replacement": "implementation 'org.example:bad:2.0.0'",
                }
            ],
            log_dir=str(tmp_path),
            enable_failure_isolation=True,
        )

    assert build_file.read_text(encoding="utf-8") == original


def test_descendant_pids_includes_complete_process_tree():
    processes = {
        10: (1, "gradle daemon"),
        11: (10, "gradle worker"),
        12: (11, "test executor"),
        20: (1, "unrelated process"),
    }

    assert bv._descendant_pids({10}, processes) == {
        10,
        11,
        12,
    }
def test_build_timeout_cleans_only_new_gradle_daemons(
    tmp_path,
    monkeypatch,
):
    daemon_snapshots = iter([
        {100},
        {100, 200},
    ])
    terminated = []

    monkeypatch.setattr(
        bv,
        "_gradle_daemon_pids",
        lambda: next(daemon_snapshots),
    )
    monkeypatch.setattr(
        bv,
        "_terminate_process_trees",
        lambda roots: terminated.append(set(roots)),
    )

    gradle_stub = tmp_path / "gradle-stub"
    gradle_stub.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
    gradle_stub.chmod(0o755)

    with pytest.raises(
        bv.BuildValidationError,
        match="timed out after 1s",
    ):
        bv._run_build_command(
            [str(gradle_stub), "build"],
            str(tmp_path),
            1,
            "Gradle build validation",
        )

    assert terminated == [{200}]


def test_gradle_validation_retries_timeout_before_failure_isolation(
    tmp_path,
    monkeypatch,
):
    build_file = tmp_path / "build.gradle"
    original = "dependencies {}\n"
    build_file.write_text(original, encoding="utf-8")
    timeouts = []

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        timeouts.append(timeout)
        if len(timeouts) == 1:
            raise bv.BuildValidationError(
                f"Gradle build validation timed out after {timeout}s"
            )

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        timeout=120,
        changes=[
            {
                "dependency": "org.example:safe",
                "old_version": "1.0.0",
                "new_version": "1.0.1",
                "original": "implementation 'org.example:safe:1.0.0'",
                "replacement": "implementation 'org.example:safe:1.0.1'",
            }
        ],
        log_dir=str(tmp_path),
    )

    assert timeouts == [120, 360]
    assert build_file.read_text(encoding="utf-8") == original

def test_gradle_validation_retries_transient_daemon_crash_before_isolation(
    tmp_path,
    monkeypatch,
):
    """Live bug: a repo whose fix would otherwise have passed got fully
    reverted because "Gradle build daemon disappeared unexpectedly" (a
    single-use worker process getting killed under parallel batch load,
    unrelated to the dependency change) was treated the same as a real build
    failure. Must retry once, same as the existing timeout-retry path.
    """
    build_file = tmp_path / "build.gradle"
    original = "dependencies {}\n"
    build_file.write_text(original, encoding="utf-8")
    attempts = []

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        attempts.append(timeout)
        if len(attempts) == 1:
            raise bv.BuildValidationError(
                "Gradle build daemon disappeared unexpectedly "
                "(it may have been killed or may have crashed)"
            )

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        timeout=120,
        changes=[
            {
                "dependency": "org.example:safe",
                "old_version": "1.0.0",
                "new_version": "1.0.1",
                "original": "implementation 'org.example:safe:1.0.0'",
                "replacement": "implementation 'org.example:safe:1.0.1'",
            }
        ],
        log_dir=str(tmp_path),
    )

    assert len(attempts) == 2
    assert build_file.read_text(encoding="utf-8") == original


def test_gradle_validation_does_not_retry_non_timeout_failure(
    tmp_path,
    monkeypatch,
):
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:bad:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:bad:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")
    timeouts = []

    def fake_validate(path, gradle_cmd, timeout=600, **kwargs):
        timeouts.append(timeout)
        if "2.0.0" in build_file.read_text(encoding="utf-8"):
            raise bv.BuildValidationError("compile failed org.example:bad")

    monkeypatch.setattr(bv, "validate_gradle_project", fake_validate)

    bv.validate_gradle_project_or_rollback(
        str(build_file),
        original,
        "gradle",
        timeout=120,
        changes=[
            {
                "dependency": "org.example:bad",
                "old_version": "1.0.0",
                "new_version": "2.0.0",
                "original": "implementation 'org.example:bad:1.0.0'",
                "replacement": "implementation 'org.example:bad:2.0.0'",
            }
        ],
        log_dir=str(tmp_path),
        enable_failure_isolation=True,
    )
    # 1st = initial full-target attempt, 2nd = single-package isolation probe,
    # 3rd = confirm_fn re-validating the winning revert with the full build.
    assert timeouts == [120, 120, 120]
    assert build_file.read_text(encoding="utf-8") == original



def test_proactive_gradle_check_skips_when_entire_cohort_is_inaccessible(
    tmp_path,
    monkeypatch,
):
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "repositories { maven { url 'https://repo.example' } }\n"
        "dependencies {}\n",
        encoding="utf-8",
    )
    installed = {
        f"org.example:library-{index}": f"1.0.{index}"
        for index in range(10)
    }

    import parsers.gradle as gradle
    import parsers.gradle_tree as gradle_tree
    import registry.maven as maven

    monkeypatch.setattr(
        gradle_tree,
        "run_gradle_dependencies",
        lambda *args, **kwargs: ("resolved tree", ""),
    )
    monkeypatch.setattr(
        gradle_tree,
        "parse_gradle_dep_tree",
        lambda output: (installed, {}),
    )
    monkeypatch.setattr(
        gradle,
        "parse_gradle_repositories",
        lambda text: ["https://repo.example"],
    )
    monkeypatch.setattr(
        maven,
        "version_accessible",
        lambda *args, **kwargs: False,
    )

    def fail_get_available_versions(*args, **kwargs):
        raise AssertionError(
            "A cohort-wide repository failure must not trigger replacement searches"
        )

    monkeypatch.setattr(
        gradle,
        "get_available_versions",
        fail_get_available_versions,
    )

    bv._proactive_check_and_fix(
        str(build_file),
        "./gradlew",
        30,
        str(tmp_path),
        None,
        None,
        "https://repo.example",
    )
    debug = (tmp_path / "build-validation-debug.txt").read_text(
        encoding="utf-8"
    )
    assert "all resolved artifacts were reported inaccessible" in debug
    assert "skipping pre-flight forces" in debug


def test_proactive_gradle_check_prefers_passed_in_repo_urls_over_regex_parse(
    tmp_path,
    monkeypatch,
):
    """Live bug: a repo declared as url "${ARTIFACTORY_SOURCE}/repo-name" was
    regex-parsed verbatim and used as the sole accessibility-check URL,
    breaking every probe. resolve_tree now resolves the real URL via Gradle
    itself and threads it in as `repo_urls`; this must win over re-parsing
    the (potentially unresolved) literal from the build file text, and the
    broken literal must never reach an accessibility check.
    """
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "repositories { maven { url '${ARTIFACTORY_SOURCE}/repo-name' } }\n"
        "dependencies {}\n",
        encoding="utf-8",
    )
    installed = {"org.example:library-0": "1.0.0"}

    import parsers.gradle as gradle
    import parsers.gradle_tree as gradle_tree
    import registry.maven as maven

    monkeypatch.setattr(
        gradle_tree,
        "run_gradle_dependencies",
        lambda *args, **kwargs: ("resolved tree", ""),
    )
    monkeypatch.setattr(
        gradle_tree,
        "parse_gradle_dep_tree",
        lambda output: (installed, {}),
    )

    def fail_parse_gradle_repositories(text):
        raise AssertionError(
            "should not fall back to regex parsing when repo_urls is provided"
        )

    monkeypatch.setattr(
        gradle,
        "parse_gradle_repositories",
        fail_parse_gradle_repositories,
    )

    checked_urls = []

    def fake_version_accessible(group, artifact, version, url, auth, timeout):
        checked_urls.append(url)
        return url == "https://real.example/artifactory/repo-name"

    monkeypatch.setattr(maven, "version_accessible", fake_version_accessible)

    bv._proactive_check_and_fix(
        str(build_file),
        "./gradlew",
        30,
        str(tmp_path),
        None,
        None,
        "https://repo.example",
        repo_urls=["https://real.example/artifactory/repo-name"],
    )

    assert "https://real.example/artifactory/repo-name" in checked_urls
    assert not any("${ARTIFACTORY_SOURCE}" in url for url in checked_urls)


def test_proactive_gradle_check_floors_tree_resolution_timeout(tmp_path, monkeypatch):
    """Live bug: the proactive check passed the raw gradle_timeout (default 30s)
    straight through to `gradle dependencies`, while resolve_tree floors the
    same operation at 180s (managers/gradle.py) because large projects routinely
    need longer than 30s just to resolve the tree. Without the same floor here,
    the proactive check timed out on every single batch run for slow-resolving
    repos, e.g. ins-cp-mgmt-admin-api's dependency tree never finished inside
    30s across any of its runs — pure wasted time, zero benefit.
    """
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "repositories { maven { url 'https://repo.example' } }\ndependencies {}\n",
        encoding="utf-8",
    )

    import parsers.gradle as gradle
    import parsers.gradle_tree as gradle_tree

    seen_timeouts = []

    def fake_run_gradle_dependencies(
        project_dir, gradle_cmd, timeout, configuration=None, resolve_repo_urls=False
    ):
        seen_timeouts.append(timeout)
        return None, "did not finish"

    monkeypatch.setattr(
        gradle_tree, "run_gradle_dependencies", fake_run_gradle_dependencies
    )
    monkeypatch.setattr(
        gradle, "parse_gradle_repositories", lambda text: ["https://repo.example"]
    )

    bv._proactive_check_and_fix(
        str(build_file),
        "./gradlew",
        30,
        str(tmp_path),
        None,
        None,
        "https://repo.example",
    )

    assert seen_timeouts and all(timeout >= 180 for timeout in seen_timeouts)


def test_proactive_gradle_check_fixes_blocks_that_break_tree_resolution_itself(
    tmp_path, monkeypatch
):
    """Live bug: when a package is blocked severely enough that `gradle
    dependencies` itself can't resolve (not just the final build), the
    proactive check used to give up silently ("could not resolve dependency
    tree, skipping") — there was no resolved tree to scan for accessibility.
    The pipeline then fell through to the real, expensive build, which failed
    for the identical reason, and only got fixed reactively
    (_try_fix_external_gradle_blockers) after that failure — the exact
    "build failed, then it says blocked, then it updates" sequence reported
    from a real batch run (cwih-cnp-mgmt-preference-workflow, jackson-databind
    2.21.4). run_gradle_dependencies_with_fallback already implements
    "detect blocked from a failed scan, force a replacement, retry the scan"
    for the pre-change tree (managers/gradle.py); this reuses it here so the
    scan fixes the block before the real build ever runs.
    """
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "repositories { maven { url 'https://repo.example' } }\n"
        "dependencies {\n"
        "    implementation 'com.fasterxml.jackson.core:jackson-databind:2.21.4'\n"
        "}\n",
        encoding="utf-8",
    )

    import parsers.gradle as gradle
    import parsers.gradle_tree as gradle_tree
    from shared.maven_version import MavenVersion

    scan_failure = (
        "FAILURE: Build failed with an exception.\n\n"
        "* What went wrong:\n"
        "Could not resolve com.fasterxml.jackson.core:jackson-databind:2.21.4.\n"
        "Required by:\n"
        "    project :\n"
        "Could not GET 'https://repo.example/com/fasterxml/jackson/core/"
        "jackson-databind/2.21.4/jackson-databind-2.21.4.pom'. "
        "Received status code 403 from server: Forbidden\n"
    )

    call_count = {"n": 0}

    def fake_run_gradle_dependencies(
        project_dir, gradle_cmd, timeout, configuration=None, resolve_repo_urls=False
    ):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None, scan_failure
        return "resolved tree after force", None

    monkeypatch.setattr(
        gradle_tree, "run_gradle_dependencies", fake_run_gradle_dependencies
    )
    # Bypass real tree-text parsing (matches the other proactive-check tests) —
    # an empty installed dict short-circuits the resolved-tree accessibility
    # scan below via `if not installed: return`, isolating this test to the
    # new "scan itself failed" path.
    monkeypatch.setattr(gradle_tree, "parse_gradle_dep_tree", lambda output: ({}, {}))

    monkeypatch.setattr(
        gradle,
        "get_available_versions",
        lambda group, artifact, url, auth, timeout: (
            [MavenVersion.parse("2.21.4"), MavenVersion.parse("2.21.5")],
            None,
        ),
    )
    monkeypatch.setattr(
        gradle,
        "version_accessible",
        lambda group, artifact, version, url, auth, timeout: version == "2.21.5",
    )

    bv._proactive_check_and_fix(
        str(build_file),
        "./gradlew",
        30,
        str(tmp_path),
        None,
        None,
        "https://repo.example",
    )

    written = build_file.read_text(encoding="utf-8")
    assert "2.21.5" in written
    assert call_count["n"] == 2

    debug = (tmp_path / "build-validation-debug.txt").read_text(encoding="utf-8")
    assert "forced 1 artifact(s) just to make the dependency tree resolve" in debug
    assert "jackson-databind:2.21.5" in debug


def _spring_boot_plugin_build_text():
    return """plugins {
    id 'org.springframework.boot' version '3.5.16'
    id 'io.spring.dependency-management' version '1.1.7'
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
}
"""


def test_revert_gradle_package_restores_original_plugin_version_when_last_boot_entry(tmp_path):
    """Live bug: forcing org.springframework.boot:* family members is a no-op
    (write_gradle_file rewrites the plugin version instead of a force line),
    so isolation's single-candidate revert — which looks for a 'force ...'
    line to undo — used to silently leave the bumped plugin version in place
    even when this candidate was chosen for a full revert.
    """
    text = _spring_boot_plugin_build_text()
    force_entries = [
        {
            "dependency": "org.springframework.boot:spring-boot",
            "old_version": "3.5.13",
            "new_version": "3.5.16",
        },
    ]

    reverted = bv._revert_gradle_package(
        text,
        [],
        force_entries,
        "org.springframework.boot:spring-boot",
    )

    assert "id 'org.springframework.boot' version '3.5.13'" in reverted
    assert "3.5.16" not in reverted


def test_revert_gradle_package_keeps_other_boot_family_members_versioned(tmp_path):
    """Reverting one org.springframework.boot:* candidate while a sibling is
    still being kept must regenerate the plugin version from what remains,
    not just drop back to the pre-remediation version (that would silently
    undo the sibling's fix too, since they share one plugin version line).
    """
    text = _spring_boot_plugin_build_text()
    force_entries = [
        {
            "dependency": "org.springframework.boot:spring-boot",
            "old_version": "3.5.13",
            "new_version": "3.5.16",
        },
        {
            "dependency": "org.springframework.boot:spring-boot-starter-web",
            "old_version": "3.5.13",
            "new_version": "3.5.16",
        },
    ]

    reverted = bv._revert_gradle_package(
        text,
        [],
        force_entries,
        "org.springframework.boot:spring-boot",
    )

    # spring-boot-starter-web is still an active (unreverted) force entry, so
    # the plugin version must stay at the version it requires.
    assert "id 'org.springframework.boot' version '3.5.16'" in reverted


def test_revert_gradle_package_to_version_refuses_to_step_boot_platform():
    """org.springframework.boot:* shares one plugin-version line across the
    whole family, same as the ext-property-managed families — partial
    stepping isn't representable, so this must return None (falls through to
    a full revert) instead of calling _step_down_gradle_force, which finds no
    force line to edit and would silently no-op.
    """
    text = _spring_boot_plugin_build_text()
    force_entries = [
        {
            "dependency": "org.springframework.boot:spring-boot",
            "old_version": "3.5.13",
            "new_version": "3.5.16",
        },
    ]

    result = bv._revert_gradle_package_to_version(
        text,
        [],
        force_entries,
        "org.springframework.boot:spring-boot",
        "3.5.14",
    )

    assert result is None


def test_capture_gradle_build_logs_writes_both_before_and_after(tmp_path, monkeypatch):
    """cfg.capture_build_logs opt-in: an extra build against the
    pre-remediation file, plus the already-written post-remediation file,
    purely to leave clean log artifacts distinct from the append-forever
    debug log.
    """
    build_file = tmp_path / "build.gradle"
    original = "dependencies { implementation 'org.example:parent:1.0.0' }\n"
    current = "dependencies { implementation 'org.example:parent:2.0.0' }\n"
    build_file.write_text(current, encoding="utf-8")

    seen_versions = []

    def fake_run_build_command(cmd, cwd, timeout, label):
        text = build_file.read_text(encoding="utf-8")
        seen_versions.append(text)
        return subprocess.CompletedProcess(cmd, 0, f"BUILD SUCCESSFUL ({text})", "")

    monkeypatch.setattr(bv, "_run_build_command", fake_run_build_command)

    bv.capture_gradle_build_logs(
        build_file, original, current, "gradle", 30, str(tmp_path)
    )

    before = (tmp_path / "build-log-before.txt").read_text(encoding="utf-8")
    after = (tmp_path / "build-log-after.txt").read_text(encoding="utf-8")
    assert "1.0.0" in before
    assert "2.0.0" in after
    # The file must end up back at the post-remediation content, not left on
    # the baseline snapshot used mid-capture.
    assert build_file.read_text(encoding="utf-8") == current


def test_capture_gradle_build_logs_skips_before_when_text_unchanged(tmp_path, monkeypatch):
    build_file = tmp_path / "build.gradle"
    text = "dependencies { implementation 'org.example:parent:1.0.0' }\n"
    build_file.write_text(text, encoding="utf-8")

    def fake_run_build_command(cmd, cwd, timeout, label):
        return subprocess.CompletedProcess(cmd, 0, "BUILD SUCCESSFUL", "")

    monkeypatch.setattr(bv, "_run_build_command", fake_run_build_command)

    bv.capture_gradle_build_logs(build_file, text, text, "gradle", 30, str(tmp_path))

    assert not (tmp_path / "build-log-before.txt").exists()
    assert (tmp_path / "build-log-after.txt").exists()


def test_capture_gradle_build_logs_retries_transient_daemon_crash(tmp_path, monkeypatch):
    """A crashed single-use build worker (OOM/contention, not a real
    problem with the file) must not silently poison this diagnostic build --
    same retry _run_candidate_trials already applies elsewhere.
    """
    build_file = tmp_path / "build.gradle"
    text = "dependencies { implementation 'org.example:parent:1.0.0' }\n"
    build_file.write_text(text, encoding="utf-8")

    calls = []

    def fake_run_build_command(cmd, cwd, timeout, label):
        calls.append(timeout)
        if len(calls) == 1:
            raise bv.BuildValidationError(
                "Gradle build daemon disappeared unexpectedly (it may have "
                "been killed or may have crashed)"
            )
        return subprocess.CompletedProcess(cmd, 0, "BUILD SUCCESSFUL", "")

    monkeypatch.setattr(bv, "_run_build_command", fake_run_build_command)

    bv.capture_gradle_build_logs(build_file, text, text, "gradle", 30, str(tmp_path))

    after = (tmp_path / "build-log-after.txt").read_text(encoding="utf-8")
    assert "BUILD SUCCESSFUL" in after
    assert len(calls) == 2
    assert calls[1] > calls[0]
