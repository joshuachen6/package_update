from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from quick_update import QuickUpdateConfig, run_quick_update
from shared.maven_version import MavenVersion


def test_quick_update_resolves_gradle_before_jfrog_audit_and_reuses_tree(
    tmp_path,
    monkeypatch,
):
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    build_file = project_dir / "build.gradle"
    build_file.write_text(
        "dependencies { implementation 'org.example:parent:1.0.0' }",
        encoding="utf-8",
    )

    manager = {
        "type": "gradle",
        "label": "Gradle    >  build.gradle",
        "file_path": str(build_file),
    }
    tree_calls = []
    audit_seen = {}

    parsed = SimpleNamespace(
        file_path=str(build_file),
        build_text=build_file.read_text(encoding="utf-8"),
        deps=[],
        repo_urls=[],
    )
    tree = SimpleNamespace(
        installed={
            "org.example:parent": MavenVersion.parse("1.0.0"),
        },
        parents_of={},
        bumped={},
        project_dir=str(project_dir),
        gradle_cmd="gradle",
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        prefetched_versions={},
        tree_failed=False,
        repo_urls=[],
    )

    def fake_parse(self, file_path):
        return parsed

    def fake_resolve(self, file_path, parsed_arg, cfg, tree_log_dir):
        tree_calls.append(tree_log_dir)
        tree_path = Path(tree_log_dir) / "gradle-dependency-tree.txt"
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text(
            "+--- org.example:parent:1.0.0\n",
            encoding="utf-8",
        )
        return tree

    def fake_audit(**kwargs):
        tree_paths = kwargs["gradle_tree_paths"]
        audit_seen["tree_paths"] = tree_paths
        audit_seen["tree_text"] = Path(tree_paths[0]).read_text(
            encoding="utf-8"
        )
        return {
            "available": True,
            "returncode": 0,
            "json_path": str(log_dir / "jfrog-audit.json"),
            "vulnerability_count": 0,
            "vulnerable_components": [],
        }

    def fake_run_analysis(
        manager_spec,
        file_path,
        analysis_log_dir,
        cve_packages,
        cfg,
        prefetched_tree=None,
        prefetched_parsed=None,
    ):
        assert prefetched_tree is tree
        assert prefetched_parsed is parsed
        return {
            "display_changes": [],
            "skipped_display": [],
            "file_path": file_path,
            "tree_failed": False,
            "_tree": prefetched_tree,
            "_parsed": prefetched_parsed,
            "build_text": parsed.build_text,
            "changes": [],
            "force_entries": [],
            "skipped_raw": [],
            "build_file": file_path,
            "fetch_errors": [],
            "version_inventory": {},
        }

    monkeypatch.setattr(
        "quick_update._dependency_managers",
        lambda cfg, root: [manager],
    )
    monkeypatch.setattr(
        "managers.gradle.GradleParser.parse",
        fake_parse,
    )
    monkeypatch.setattr(
        "managers.gradle.GradleParser.resolve_tree",
        fake_resolve,
    )
    monkeypatch.setattr(
        "shared.jfrog_scan.run_jfrog_audit",
        fake_audit,
    )
    monkeypatch.setattr(
        "pipeline.runner.run_analysis",
        fake_run_analysis,
    )
    monkeypatch.setattr(
        "shared.report.generate_report",
        lambda result, log_dir: str(Path(log_dir) / "report.xlsx"),
    )
    monkeypatch.setattr(
        "shared.report.snapshot_before_dependency_tree",
        lambda *args, **kwargs: None,
    )

    result = run_quick_update(
        QuickUpdateConfig(
            project_dir=str(project_dir),
            log_dir=str(log_dir),
            artifactory_source="https://jfrog.example/artifactory",
            artifactory_repo="gradle",
        )
    )

    assert len(tree_calls) == 1
    assert len(audit_seen["tree_paths"]) == 1
    assert "org.example:parent:1.0.0" in audit_seen["tree_text"]
    assert result["file_results"][0]["tree_failed"] is False


def _run_capture_build_logs_wiring_test(
    tmp_path, monkeypatch, capture_build_logs: bool, write_result_raises: bool = False,
):
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    build_file = project_dir / "build.gradle"
    build_file.write_text(
        "dependencies { implementation 'org.example:parent:1.0.0' }",
        encoding="utf-8",
    )

    manager = {
        "type": "gradle",
        "label": "Gradle    >  build.gradle",
        "file_path": str(build_file),
    }
    parsed = SimpleNamespace(
        file_path=str(build_file),
        build_text=build_file.read_text(encoding="utf-8"),
        deps=[],
        repo_urls=[],
    )
    tree = SimpleNamespace(
        installed={"org.example:parent": MavenVersion.parse("1.0.0")},
        parents_of={},
        bumped={},
        project_dir=str(project_dir),
        gradle_cmd="gradle",
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        prefetched_versions={},
        tree_failed=False,
        repo_urls=[],
    )

    def fake_parse(self, file_path):
        return parsed

    def fake_resolve(self, file_path, parsed_arg, cfg, tree_log_dir):
        tree_path = Path(tree_log_dir) / "gradle-dependency-tree.txt"
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text("+--- org.example:parent:1.0.0\n", encoding="utf-8")
        return tree

    def fake_audit(**kwargs):
        return {
            "available": True,
            "returncode": 0,
            "json_path": str(log_dir / "jfrog-audit.json"),
            "vulnerability_count": 1,
            "vulnerable_components": [
                {
                    "ecosystem": "maven",
                    "package": "org.example:parent",
                    "cves": ["CVE-2024-0001"],
                }
            ],
        }

    def fake_run_analysis(
        manager_spec, file_path, analysis_log_dir, cve_packages, cfg,
        prefetched_tree=None, prefetched_parsed=None,
    ):
        return {
            "display_changes": [{"package": "org.example:parent"}],
            "skipped_display": [],
            "file_path": file_path,
            "tree_failed": False,
            "_tree": prefetched_tree,
            "_parsed": prefetched_parsed,
            "build_text": parsed.build_text,
            "changes": [],
            "force_entries": [],
            "skipped_raw": [],
            "build_file": file_path,
            "fetch_errors": [],
            "version_inventory": {},
        }

    capture_calls = []

    monkeypatch.setattr("quick_update._dependency_managers", lambda cfg, root: [manager])
    monkeypatch.setattr("managers.gradle.GradleParser.parse", fake_parse)
    monkeypatch.setattr("managers.gradle.GradleParser.resolve_tree", fake_resolve)
    def fake_write_result(self, cfg, result, log_dir):
        if write_result_raises:
            raise RuntimeError("simulated write/validation failure")
        build_file.write_text(
            "dependencies { implementation 'org.example:parent:2.0.0' }",
            encoding="utf-8",
        )

    monkeypatch.setattr("managers.gradle.GradleManager.write_result", fake_write_result)
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_audit)
    monkeypatch.setattr("pipeline.runner.run_analysis", fake_run_analysis)
    monkeypatch.setattr(
        "quick_update._capture_build_logs",
        lambda cfg, manager, result, log_dir: capture_calls.append(manager["file_path"]),
    )
    monkeypatch.setattr(
        "shared.report.generate_report",
        lambda result, log_dir: str(Path(log_dir) / "report.xlsx"),
    )
    monkeypatch.setattr("shared.report.snapshot_before_dependency_tree", lambda *a, **k: None)
    # finalize_verification's own post-remediation test run (_gradle_test)
    # would otherwise invoke a REAL gradle process against this fake
    # build.gradle -- irrelevant to what this test checks (whether
    # _capture_build_logs gets wired up) and slow/environment-dependent.
    monkeypatch.setattr(
        "shared.verification._run",
        lambda command, cwd, timeout, label: {"label": label, "status": "not_run", "output": ""},
    )

    run_quick_update(
        QuickUpdateConfig(
            project_dir=str(project_dir),
            log_dir=str(log_dir),
            artifactory_source="https://jfrog.example/artifactory",
            artifactory_repo="gradle",
            capture_build_logs=capture_build_logs,
        )
    )
    return capture_calls, log_dir


def test_quick_update_calls_capture_build_logs_when_enabled(tmp_path, monkeypatch):
    calls, _log_dir = _run_capture_build_logs_wiring_test(tmp_path, monkeypatch, capture_build_logs=True)
    assert len(calls) == 1


def test_quick_update_skips_capture_build_logs_by_default(tmp_path, monkeypatch):
    """capture_build_logs defaults to False -- an extra full build per repo
    is expensive and meant for one-off verification runs, not routine
    production batches, so it must never fire unless explicitly enabled.
    """
    calls, _log_dir = _run_capture_build_logs_wiring_test(tmp_path, monkeypatch, capture_build_logs=False)
    assert calls == []


def test_quick_update_captures_build_logs_even_when_write_result_fails(tmp_path, monkeypatch):
    """capture_gradle_build_logs/capture_node_build_logs run their own
    independent builds and don't need write_result to have succeeded -- the
    call used to sit inside the same try block as write_result, so it never
    ran for exactly the repos this feature exists to explain (isolation off,
    validation raised, write_status Failed).
    """
    calls, _log_dir = _run_capture_build_logs_wiring_test(
        tmp_path, monkeypatch, capture_build_logs=True, write_result_raises=True,
    )
    assert len(calls) == 1


def test_quick_update_saves_before_after_dependency_file_for_zip_bundle(tmp_path, monkeypatch):
    """The whole point: log_dir should be a self-contained debugging bundle
    you can zip and hand to someone else -- including the actual dependency
    file's pre/post-remediation content, not just its diff summary.
    """
    _calls, log_dir = _run_capture_build_logs_wiring_test(
        tmp_path, monkeypatch, capture_build_logs=False,
    )

    before = (log_dir / "build-before.gradle").read_text(encoding="utf-8")
    after = (log_dir / "build-after.gradle").read_text(encoding="utf-8")
    assert "1.0.0" in before
    assert "2.0.0" in after


def test_quick_update_saves_before_after_dependency_file_even_when_write_result_fails(
    tmp_path, monkeypatch,
):
    """A write/validation failure must still leave the pre-remediation file
    content behind -- these are the repos someone most needs to debug. What
    "after" ends up containing depends on where write_result actually failed
    (this test's fake raises before writing at all, so it's still the
    original text here) -- real gradle could leave attempted or rolled-back
    content instead; either way this only asserts the file exists with the
    genuine pre-remediation content, not a specific failure-path outcome.
    """
    _calls, log_dir = _run_capture_build_logs_wiring_test(
        tmp_path, monkeypatch, capture_build_logs=False, write_result_raises=True,
    )

    before = (log_dir / "build-before.gradle").read_text(encoding="utf-8")
    assert "1.0.0" in before
    assert (log_dir / "build-after.gradle").is_file()


def test_quick_update_saves_before_after_dependency_file_for_npm(tmp_path, monkeypatch):
    """Same before/after dependency-file capture, for the npm manifest --
    "do the same for npm, pyproject.toml etc." was explicit in the request,
    so this needs its own real exercise, not an assumption that the
    gradle-only test generalizes.
    """
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    package_json = project_dir / "package.json"
    package_json.write_text('{"name": "x", "version": "1.0.0"}', encoding="utf-8")
    package_lock = project_dir / "package-lock.json"
    package_lock.write_text('{"lockfileVersion": 3, "ws": "8.20.0"}', encoding="utf-8")

    manager = {
        "type": "node",
        "label": "npm       >  package.json",
        "file_path": str(package_json),
    }

    def fake_analyze(self, cfg, manager, log_dir, cve_packages):
        return {
            "display_changes": [{"package": "ws"}],
            "skipped_display": [],
        }

    def fake_write_result(self, cfg, result, log_dir):
        package_json.write_text('{"name": "x", "version": "1.0.1"}', encoding="utf-8")
        package_lock.write_text('{"lockfileVersion": 3, "ws": "8.21.0"}', encoding="utf-8")

    def fake_audit(**kwargs):
        return {
            "available": True,
            "returncode": 0,
            "json_path": str(log_dir / "jfrog-audit.json"),
            "vulnerability_count": 1,
            "vulnerable_components": [
                {"ecosystem": "npm", "package": "ws", "cves": ["CVE-2024-0002"]}
            ],
        }

    monkeypatch.setattr("quick_update._dependency_managers", lambda cfg, root: [manager])
    monkeypatch.setattr("managers.npm.NpmManager.analyze", fake_analyze)
    monkeypatch.setattr("managers.npm.NpmManager.write_result", fake_write_result)
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_audit)
    monkeypatch.setattr(
        "shared.report.generate_report",
        lambda result, log_dir: str(Path(log_dir) / "report.xlsx"),
    )
    monkeypatch.setattr("shared.report.snapshot_before_dependency_tree", lambda *a, **k: None)
    monkeypatch.setattr(
        "shared.verification._run",
        lambda command, cwd, timeout, label: {"label": label, "status": "not_run", "output": ""},
    )

    run_quick_update(
        QuickUpdateConfig(
            project_dir=str(project_dir),
            log_dir=str(log_dir),
            artifactory_source="https://jfrog.example/artifactory",
        )
    )

    before = (log_dir / "package-before.json").read_text(encoding="utf-8")
    after = (log_dir / "package-after.json").read_text(encoding="utf-8")
    assert "1.0.0" in before
    assert "1.0.1" in after

    # package.json alone often only shows an `overrides` entry -- the
    # lockfile is where the real resolved-version delta lives.
    lock_before = (log_dir / "package-lock-before.json").read_text(encoding="utf-8")
    lock_after = (log_dir / "package-lock-after.json").read_text(encoding="utf-8")
    assert "8.20.0" in lock_before
    assert "8.21.0" in lock_after


def test_quick_update_saves_before_after_dependency_file_for_python(tmp_path, monkeypatch):
    """Same before/after dependency-file capture, for pyproject.toml."""
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text('requests==2.30.0\n', encoding="utf-8")

    manager = {
        "type": "python",
        "label": "python    >  pyproject.toml",
        "file_path": str(pyproject),
    }

    def fake_analyze(self, cfg, manager, log_dir, cve_packages):
        return {
            "display_changes": [{"package": "requests"}],
            "skipped_display": [],
        }

    def fake_write_result(self, cfg, result, log_dir):
        pyproject.write_text('requests==2.31.0\n', encoding="utf-8")

    def fake_audit(**kwargs):
        return {
            "available": True,
            "returncode": 0,
            "json_path": str(log_dir / "jfrog-audit.json"),
            "vulnerability_count": 1,
            "vulnerable_components": [
                {"ecosystem": "pypi", "package": "requests", "cves": ["CVE-2024-0003"]}
            ],
        }

    monkeypatch.setattr("quick_update._dependency_managers", lambda cfg, root: [manager])
    monkeypatch.setattr("managers.python.PythonManager.analyze", fake_analyze)
    monkeypatch.setattr("managers.python.PythonManager.write_result", fake_write_result)
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_audit)
    monkeypatch.setattr(
        "shared.report.generate_report",
        lambda result, log_dir: str(Path(log_dir) / "report.xlsx"),
    )
    monkeypatch.setattr("shared.report.snapshot_before_dependency_tree", lambda *a, **k: None)
    monkeypatch.setattr(
        "shared.verification._run",
        lambda command, cwd, timeout, label: {"label": label, "status": "not_run", "output": ""},
    )

    run_quick_update(
        QuickUpdateConfig(
            project_dir=str(project_dir),
            log_dir=str(log_dir),
            artifactory_source="https://jfrog.example/artifactory",
        )
    )

    before = (log_dir / "pyproject-before.toml").read_text(encoding="utf-8")
    after = (log_dir / "pyproject-after.toml").read_text(encoding="utf-8")
    assert "2.30.0" in before
    assert "2.31.0" in after


def test_quick_update_gradle_before_snapshot_uses_preaudit_tree(
    tmp_path,
    monkeypatch,
):
    """Live bug: gradle-dependency-tree-before.txt and -after.txt ended up
    byte-identical in real batch runs. Root cause: the flat
    log_dir/gradle-dependency-tree.txt is NEVER written pre-remediation --
    Gradle's only pre-remediation resolution goes to the nested
    preaudit-gradle/<n>/ directory (see _pre_resolve_gradle_managers) -- yet
    the before-snapshot call used to run at the very end of run_quick_update,
    copying from that (by-then post-remediation) flat path by default. The
    fix moves the snapshot to right after each file's own pre-remediation
    analysis, sourcing Gradle's from the preaudit tree explicitly.
    """
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    build_file = project_dir / "build.gradle"
    build_file.write_text(
        "dependencies { implementation 'org.example:parent:1.0.0' }",
        encoding="utf-8",
    )

    manager = {
        "type": "gradle",
        "label": "Gradle    >  build.gradle",
        "file_path": str(build_file),
    }

    parsed = SimpleNamespace(
        file_path=str(build_file),
        build_text=build_file.read_text(encoding="utf-8"),
        deps=[],
        repo_urls=[],
    )
    tree = SimpleNamespace(
        installed={"org.example:parent": MavenVersion.parse("1.0.0")},
        parents_of={},
        bumped={},
        project_dir=str(project_dir),
        gradle_cmd="gradle",
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        prefetched_versions={},
        tree_failed=False,
        repo_urls=[],
    )

    def fake_parse(self, file_path):
        return parsed

    def fake_resolve(self, file_path, parsed_arg, cfg, tree_log_dir):
        tree_path = Path(tree_log_dir) / "gradle-dependency-tree.txt"
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text(
            "+--- org.example:parent:1.0.0 (preaudit)\n",
            encoding="utf-8",
        )
        return tree

    def fake_audit(**kwargs):
        return {
            "available": True,
            "returncode": 0,
            "json_path": str(log_dir / "jfrog-audit.json"),
            "vulnerability_count": 0,
            "vulnerable_components": [],
        }

    def fake_run_analysis(
        manager_spec,
        file_path,
        analysis_log_dir,
        cve_packages,
        cfg,
        prefetched_tree=None,
        prefetched_parsed=None,
    ):
        return {
            "display_changes": [],
            "skipped_display": [],
            "file_path": file_path,
            "tree_failed": False,
            "_tree": prefetched_tree,
            "_parsed": prefetched_parsed,
            "build_text": parsed.build_text,
            "changes": [],
            "force_entries": [],
            "skipped_raw": [],
            "build_file": file_path,
            "fetch_errors": [],
            "version_inventory": {},
        }

    monkeypatch.setattr("quick_update._dependency_managers", lambda cfg, root: [manager])
    monkeypatch.setattr("managers.gradle.GradleParser.parse", fake_parse)
    monkeypatch.setattr("managers.gradle.GradleParser.resolve_tree", fake_resolve)
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_audit)
    monkeypatch.setattr("pipeline.runner.run_analysis", fake_run_analysis)
    monkeypatch.setattr(
        "shared.report.generate_report",
        lambda result, log_dir: str(Path(log_dir) / "report.xlsx"),
    )
    # snapshot_before_dependency_tree is NOT mocked here -- unlike the other
    # test in this file, this one specifically verifies its real behavior.

    run_quick_update(
        QuickUpdateConfig(
            project_dir=str(project_dir),
            log_dir=str(log_dir),
            artifactory_source="https://jfrog.example/artifactory",
            artifactory_repo="gradle",
        )
    )

    before_path = log_dir / "gradle-dependency-tree-before.txt"
    assert before_path.is_file()
    assert "preaudit" in before_path.read_text(encoding="utf-8")


def test_quick_update_refuses_to_proceed_when_initial_audit_errored(
    tmp_path,
    monkeypatch,
):
    """Live bug: a JFrog/Xray scan that errored (timeout, connection reset,
    DNS failure) could still report vulnerability_count=0, which was
    silently treated as "repo is clean, nothing to remediate" -- zero
    packages ever got fixed, and the report showed a misleading
    before=0/after=N result that looked like the tool introduced CVEs,
    when in fact the initial scan simply never ran successfully. Confirmed
    across multiple real batch runs. run_quick_update must refuse to build
    remediation criteria from an audit result that didn't complete cleanly.
    """
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    build_file = project_dir / "build.gradle"
    build_file.write_text(
        "dependencies { implementation 'org.example:parent:1.0.0' }",
        encoding="utf-8",
    )

    manager = {
        "type": "gradle",
        "label": "Gradle    >  build.gradle",
        "file_path": str(build_file),
    }
    audit_calls = []

    def fake_audit(**kwargs):
        audit_calls.append(1)
        return {
            "available": True,
            "returncode": 1,
            "json_path": str(log_dir / "jfrog-audit.json"),
            "vulnerability_count": 0,
            "vulnerable_components": [],
            "errors": ["Xray CVE lookup failed: <urlopen error [Errno 54] Connection reset by peer>"],
            "stderr": "Xray CVE lookup failed: <urlopen error [Errno 54] Connection reset by peer>",
        }

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "run_analysis must not be reached when the initial audit is unusable"
        )

    monkeypatch.setattr("shared.jfrog_scan.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        "quick_update._dependency_managers",
        lambda cfg, root: [manager],
    )
    monkeypatch.setattr(
        "managers.gradle.GradleParser.parse",
        lambda self, file_path: SimpleNamespace(
            file_path=file_path, build_text="", deps=[], repo_urls=[],
        ),
    )
    monkeypatch.setattr(
        "managers.gradle.GradleParser.resolve_tree",
        lambda self, file_path, parsed_arg, cfg, tree_log_dir: SimpleNamespace(
            installed={}, parents_of={}, bumped={}, project_dir=str(project_dir),
            gradle_cmd="gradle", base_url="https://jfrog.example/artifactory/gradle",
            auth=None, prefetched_versions={}, tree_failed=False, repo_urls=[],
        ),
    )
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_audit)
    monkeypatch.setattr("pipeline.runner.run_analysis", fail_if_called)

    with pytest.raises(RuntimeError, match="Initial JFrog CVE audit did not complete"):
        run_quick_update(
            QuickUpdateConfig(
                project_dir=str(project_dir),
                log_dir=str(log_dir),
                artifactory_source="https://jfrog.example/artifactory",
                artifactory_repo="gradle",
            )
        )

    # Retried (not just checked once) before giving up -- the whole point of
    # retrying a transient failure instead of aborting immediately.
    assert len(audit_calls) == 3
