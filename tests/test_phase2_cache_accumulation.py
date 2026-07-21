from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from quick_update import QuickUpdateConfig, run_quick_update
from shared.maven_version import MavenVersion


def test_phase2_cache_accumulates_every_manager_fixed_so_far(tmp_path, monkeypatch):
    """The per-manager safety-net cache must not drop earlier managers' fixes.

    quick_update.run_quick_update writes logs/phase2-results.json after each
    manager is fixed, so a crash mid-run still leaves a usable Phase-2 replay
    artifact. That write must include every manager fixed so far in this run,
    not just the one that just finished.
    """
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    build_file_a = project_dir / "a" / "build.gradle"
    build_file_b = project_dir / "b" / "build.gradle"
    build_file_a.parent.mkdir(parents=True)
    build_file_b.parent.mkdir(parents=True)
    build_file_a.write_text(
        "dependencies { implementation 'org.example:a:1.0.0' }",
        encoding="utf-8",
    )
    build_file_b.write_text(
        "dependencies { implementation 'org.example:b:1.0.0' }",
        encoding="utf-8",
    )

    managers = [
        {"type": "gradle", "label": "Gradle > a/build.gradle", "file_path": str(build_file_a)},
        {"type": "gradle", "label": "Gradle > b/build.gradle", "file_path": str(build_file_b)},
    ]

    def fake_parse(self, file_path):
        return SimpleNamespace(
            file_path=file_path,
            build_text=Path(file_path).read_text(encoding="utf-8"),
            deps=[],
            repo_urls=[],
        )

    def fake_resolve(self, file_path, parsed_arg, cfg, tree_log_dir):
        tree_path = Path(tree_log_dir) / "gradle-dependency-tree.txt"
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text("+--- org.example:x:1.0.0\n", encoding="utf-8")
        return SimpleNamespace(
            installed={"org.example:x": MavenVersion.parse("1.0.0")},
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
            "json_path": str(log_dir / "jfrog-audit.json"),
            "vulnerability_count": 2,
            "vulnerable_components": [
                {"ecosystem": "maven", "package": "org.example:a"},
                {"ecosystem": "maven", "package": "org.example:b"},
            ],
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
            "display_changes": [{"package": Path(file_path).parent.name}],
            "skipped_display": [],
            "file_path": file_path,
            "tree_failed": False,
            "_tree": prefetched_tree,
            "_parsed": prefetched_parsed,
            "build_text": "",
            "changes": [],
            "force_entries": [],
            "skipped_raw": [],
            "build_file": file_path,
            "fetch_errors": [],
            "version_inventory": {},
        }

    monkeypatch.setattr("quick_update._dependency_managers", lambda cfg, root: managers)
    monkeypatch.setattr("managers.gradle.GradleParser.parse", fake_parse)
    monkeypatch.setattr("managers.gradle.GradleParser.resolve_tree", fake_resolve)
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_audit)
    monkeypatch.setattr("pipeline.runner.run_analysis", fake_run_analysis)
    monkeypatch.setattr(
        "managers.gradle.GradleManager.write_result",
        lambda self, cfg, result, log_dir: None,
    )
    monkeypatch.setattr(
        "shared.report.generate_report",
        lambda result, log_dir: str(Path(log_dir) / "report.xlsx"),
    )
    monkeypatch.setattr(
        "shared.report.snapshot_before_dependency_tree",
        lambda *args, **kwargs: None,
    )

    seen_file_result_counts = []
    real_write_text = Path.write_text

    def spy_write_text(self, data, *args, **kwargs):
        if self.name == "phase2-results.json":
            seen_file_result_counts.append(
                len(json.loads(data).get("file_results", []))
            )
        return real_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", spy_write_text)

    run_quick_update(
        QuickUpdateConfig(
            project_dir=str(project_dir),
            log_dir=str(log_dir),
            artifactory_source="https://jfrog.example/artifactory",
            artifactory_repo="gradle",
        )
    )

    # After the first manager is fixed, the cache should have 1 entry; after
    # the second (including the final complete write), it should have 2 —
    # the count must never regress back down to 1.
    assert seen_file_result_counts[:2] == [1, 2]
    assert all(count == 2 for count in seen_file_result_counts[1:])

    final_cache = json.loads(
        (log_dir / "phase2-results.json").read_text(encoding="utf-8")
    )
    assert len(final_cache["file_results"]) == 2
    assert {fr["file_path"] for fr in final_cache["file_results"]} == {
        str(build_file_a),
        str(build_file_b),
    }
