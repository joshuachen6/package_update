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
