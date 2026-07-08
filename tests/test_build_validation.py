import csv
import json

import pytest

import shared.build_validation as bv


def _csv_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def test_gradle_validation_auto_rolls_back_breaking_dependency_and_logs(tmp_path, monkeypatch):
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:bad:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:bad:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_validate(path, gradle_cmd, timeout=600):
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
    )

    assert build_file.read_text(encoding="utf-8") == original
    rows = _csv_rows(tmp_path / "build-validation-auto-fixes.csv")
    assert rows[0]["package"] == "org.example:bad"
    assert rows[0]["status"] == "auto_rolled_back"


def test_gradle_validation_marks_manual_updates_when_auto_isolation_fails(tmp_path, monkeypatch):
    build_file = tmp_path / "build.gradle"
    original = "dependencies {\n    implementation 'org.example:a:1.0.0'\n}\n"
    updated = "dependencies {\n    implementation 'org.example:a:2.0.0'\n}\n"
    build_file.write_text(updated, encoding="utf-8")

    def fake_validate(path, gradle_cmd, timeout=600):
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

    def fake_validate(path, gradle_cmd, timeout=600):
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

    def fake_validate(path, gradle_cmd, timeout=600):
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
    )

    assert calls["validate"] == 2
    assert "force \'com.fasterxml.jackson.core:jackson-databind:2.21.5\'" in build_file.read_text(encoding="utf-8")
    rows = _csv_rows(tmp_path / "build-validation-external-auto-fixes.csv")
    assert rows[0]["dependency"] == "com.fasterxml.jackson.core:jackson-databind"
    assert rows[0]["blocked_version"] == "2.22.0"
    assert rows[0]["forced_version"] == "2.21.5"

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

    def fake_validate(path, gradle_cmd, timeout=600):
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
    )

    updated = build_file.read_text(encoding="utf-8")
    assert "strictly '4.1.132.Final'" in updated
    assert "force 'io.netty:netty-handler:4.1.132.Final'" in updated
    assert calls["validate"] == 2
