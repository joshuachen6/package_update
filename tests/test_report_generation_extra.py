exec("""
import csv
import json
from pathlib import Path
from shared import report

def test_report_helpers_cover_edge_cases(tmp_path):
    base = tmp_path / "repo"
    pkg = base / "app" / "package.json"
    pkg.parent.mkdir(parents=True)
    pkg.write_text("{}", encoding="utf-8")
    assert report._safe_rel(None) == ""
    assert report._safe_rel(pkg, base) == "app/package.json"
    assert report._safe_rel(tmp_path / "outside.txt", base).endswith("outside.txt")
    assert report._read_csv_rows(tmp_path / "missing.csv") == []\n    bad_csv = tmp_path / "bad.csv"
    bad_csv.mkdir()
    assert report._read_csv_rows(bad_csv) == []
    good_csv = tmp_path / "build-validation-auto-fixes.csv"
    with good_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["package", "status"])
        writer.writeheader()
        writer.writerow({"package": "lodash", "status": "auto_rolled_back"})
    assert report._read_csv_rows(good_csv) == [{"package": "lodash", "status": "auto_rolled_back"}]
    assert report._tree_summary(tmp_path / "missing-tree.txt")["exists"] is False
    npm_tree = tmp_path / "npm-dependency-tree.json"
    npm_tree.write_text(json.dumps({"packages": {"": {}, "node_modules/a": {"version": "1.0.0"}}}), encoding="utf-8")
    assert report._tree_summary(npm_tree)["dependency_count"] == 2
    invalid_json_tree = tmp_path / "npm-dependency-tree-after.json"
    invalid_json_tree.write_text("{\\"version\\":\\"1.0.0\\"}" + chr(10) + "{\\"version\\":\\"2.0.0\\"}", encoding="utf-8")
    assert report._tree_summary(invalid_json_tree)["dependency_count"] == 2\n    gradle_tree = tmp_path / "gradle-dependency-tree.txt"
    gradle_tree.write_text("runtimeClasspath" + chr(10) + "+--- g:a:1.0" + chr(10) + "\\\\--- g:b:2.0" + chr(10), encoding="utf-8")
    assert report._tree_summary(gradle_tree)["dependency_count"] == 2
    assert report.snapshot_before_dependency_tree(None, "node") is None
    assert report.snapshot_before_dependency_tree(tmp_path, "bad") is None
    assert report.snapshot_before_dependency_tree(tmp_path, "node") == str(tmp_path / "npm-dependency-tree-before.json")
    assert report.snapshot_before_dependency_tree(tmp_path, "gradle") == str(tmp_path / "gradle-dependency-tree-before.txt")

def test_generate_report_markdown_fallback_and_contents(tmp_path, monkeypatch):
    project = tmp_path / "repo"
    project.mkdir()
    package_json = project / "package.json"
    package_json.write_text("{}", encoding="utf-8")
    (tmp_path / "npm-dependency-tree-before.json").write_text(json.dumps({"packages": {"node_modules/a": {"version": "1.0.0"}}}), encoding="utf-8")\n    (tmp_path / "npm-dependency-tree-after.json").write_text(json.dumps({"packages": {"node_modules/a": {"version": "1.0.1"}}}), encoding="utf-8")
    (tmp_path / "gradle-dependency-tree-before.txt").write_text("+--- g:a:1.0" + chr(10), encoding="utf-8")
    (tmp_path / "gradle-dependency-tree-after.txt").write_text("+--- g:a:1.1" + chr(10), encoding="utf-8")
    with (tmp_path / "build-validation-auto-fixes.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["package", "change_type", "old", "new", "status", "reason"])
        writer.writeheader()
        writer.writerow({"package": "left-pad", "change_type": "direct", "old": "1.0.0", "new": "1.0.1", "status": "auto_rolled_back", "reason": "project build passed"})
    monkeypatch.setattr(report, "_write_xlsx_report", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no workbook")))
    output = report.generate_report({
        "github_url": "https://github.com/example/repo",
        "cfg": {"log_dir": str(tmp_path), "proj_dir": str(project)},
        "jfrog_result": {"vulnerability_count": 1, "json_path": str(tmp_path / "jfrog-audit.json")},
        "file_results": [{\n            "file_path": str(package_json),
            "dm_type": "node",
            "display_changes": [{"package": "lodash", "change_type": "direct", "old": "^4.17.20", "new": "^4.17.21", "remediation_guided": True}],
            "skipped_display": [{"package": "debug", "current": "2.0.0", "target": "4.0.0", "reason": "build failed", "detail": "manual"}],
            "write_status": "written",
            "validation_status": "passed",
            "validation_message": "",
        }],
    }, log_dir=tmp_path)
    assert output == str(tmp_path / "task-completion-report.md")
    text = Path(output).read_text(encoding="utf-8")
    assert "Package Update Completion Report" in text
    assert "lodash" in text
    assert "Could not update" in text
    assert "build-validation-auto-fixes.csv" in text
    assert "XLSX report generation was skipped" in text\ndef test_markdown_writer_escapes_table_values(tmp_path):
    md = tmp_path / "report.md"
    report._write_markdown_report(
        md,
        [{"metric": "GitHub URL", "value": "https://example/repo|pipe"}],
        [{"file": "a" + chr(10) + "b", "ecosystem": "node"}],
        [{"package": "x|y", "status": "passed"}],
        [],
        [],
        [],
        [],
    )
    text = md.read_text(encoding="utf-8")
    assert "https://example/repo\\\\|pipe" in text
    assert "a<br>b" in text
    assert "x\\\\|y" in text
    assert "_No rows._" in text

def test_generate_report_writes_output_file(tmp_path):
    output = report.generate_report({\n        "github_url": "",
        "cfg": {"log_dir": str(tmp_path), "proj_dir": ""},
        "jfrog_result": {},
        "file_results": [],
    }, log_dir=tmp_path)
    assert Path(output).exists()
    assert (tmp_path / "task-completion-report.md").exists()
    assert Path(output).name in {"task-completion-report.xlsx", "task-completion-report.md"}
""")
