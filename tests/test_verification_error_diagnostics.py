from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from quick_update import QuickUpdateConfig, run_quick_update
from shared.maven_version import MavenVersion


def test_verification_exception_persists_traceback_for_diagnosis(tmp_path, monkeypatch):
    """When finalize_verification raises, str(exc) alone in the printed message
    and the in-memory result dict isn't enough to diagnose after the fact —
    seen live: a repo whose dependency updates actually succeeded was
    misreported Manual Update Required because verification blew up with no
    error persisted anywhere, and the only way to find out why was to
    re-run with a captured console. The full traceback must land in log_dir
    so a single re-run is enough.
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
        "label": "Gradle > build.gradle",
        "file_path": str(build_file),
    }

    def fake_parse(self, file_path):
        return SimpleNamespace(
            file_path=file_path,
            build_text=build_file.read_text(encoding="utf-8"),
            deps=[],
            repo_urls=[],
        )

    def fake_resolve(self, file_path, parsed_arg, cfg, tree_log_dir):
        tree_path = Path(tree_log_dir) / "gradle-dependency-tree.txt"
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text("+--- org.example:parent:1.0.0\n", encoding="utf-8")
        return SimpleNamespace(
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

    def fake_audit(**kwargs):
        return {
            "available": True,
            "returncode": 0,
            "errors": None,
            "stderr": None,
            "json_path": str(log_dir / "jfrog-audit.json"),
            "vulnerability_count": 0,
            "vulnerable_components": [],
        }

    def raise_finalize_verification(results):
        raise RuntimeError("Xray API host is unreachable: connection reset")

    monkeypatch.setattr("quick_update._dependency_managers", lambda cfg, root: [manager])
    monkeypatch.setattr("managers.gradle.GradleParser.parse", fake_parse)
    monkeypatch.setattr("managers.gradle.GradleParser.resolve_tree", fake_resolve)
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_audit)
    monkeypatch.setattr(
        "shared.verification.finalize_verification", raise_finalize_verification
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

    assert result["verification"]["classification"] == "Verification incomplete"

    error_file = log_dir / "verification-error.txt"
    assert error_file.is_file()
    content = error_file.read_text(encoding="utf-8")
    assert "Traceback" in content
    assert "Xray API host is unreachable" in content
    assert "raise_finalize_verification" in content
