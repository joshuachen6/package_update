import json

from shared import jfrog_scan


def _write_lockfile(package_dir, package="lodash", version="4.17.20"):
    (package_dir / "package-lock.json").write_text(
        json.dumps({"packages": {f"node_modules/{package}": {"version": version}}}),
        encoding="utf-8",
    )


def _write_gradle_tree(log_dir, package="org.current:gradle-lib", version="1.0.0"):
    (log_dir / "gradle-dependency-tree.txt").write_text(
        f"+--- {package}:{version}" + chr(10),
        encoding="utf-8",
    )


def test_jfrog_audit_node_only_scope_ignores_gradle_components(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo"
    node_dir = project_dir / "node-app"
    log_dir = tmp_path / "logs"
    node_dir.mkdir(parents=True)
    log_dir.mkdir()

    _write_lockfile(node_dir)
    _write_gradle_tree(log_dir)
    seen = {}

    def fake_search(components, xray_host=None, auth=None, timeout=30):
        seen["components"] = [(c.ecosystem, c.package, c.version) for c in components]
        return {}, ""

    monkeypatch.setattr(jfrog_scan, "search_cves_by_components", fake_search)
    result = jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="https://jfrog.example.com",
        ecosystems={"npm"},
        npm_package_dirs=[str(node_dir)],
        gradle_tree_paths=[str(log_dir / "gradle-dependency-tree.txt")],
    )

    assert result["returncode"] == 0
    assert seen["components"] == [("npm", "lodash", "4.17.20")]


def test_jfrog_audit_gradle_only_scope_ignores_npm_components(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo"
    node_dir = project_dir / "node-app"
    log_dir = tmp_path / "logs"
    node_dir.mkdir(parents=True)
    log_dir.mkdir()

    _write_lockfile(node_dir)
    _write_gradle_tree(log_dir)
    seen = {}

    def fake_search(components, xray_host=None, auth=None, timeout=30):
        seen["components"] = [(c.ecosystem, c.package, c.version) for c in components]
        return {}, ""

    monkeypatch.setattr(jfrog_scan, "search_cves_by_components", fake_search)
    result = jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="https://jfrog.example.com",
        ecosystems={"maven"},
        npm_package_dirs=[str(node_dir)],
        gradle_tree_paths=[str(log_dir / "gradle-dependency-tree.txt")],
    )

    assert result["returncode"] == 0
    assert seen["components"] == [("maven", "org.current:gradle-lib", "1.0.0")]


def test_jfrog_audit_mixed_scope_collects_node_and_gradle_components(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo"
    node_dir = project_dir / "node-app"
    ignored_node_dir = project_dir / "ignored-node-app"
    log_dir = tmp_path / "logs"
    node_dir.mkdir(parents=True)
    ignored_node_dir.mkdir(parents=True)
    log_dir.mkdir()

    _write_lockfile(node_dir, package="lodash", version="4.17.20")
    _write_lockfile(ignored_node_dir, package="ignored", version="1.0.0")
    _write_gradle_tree(log_dir)
    seen = {}
    def fake_search(components, xray_host=None, auth=None, timeout=30):
        seen["components"] = sorted((c.ecosystem, c.package, c.version) for c in components)
        return {}, ""

    monkeypatch.setattr(jfrog_scan, "search_cves_by_components", fake_search)
    result = jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="https://jfrog.example.com",
        ecosystems={"npm", "maven"},
        npm_package_dirs=[str(node_dir)],
        gradle_tree_paths=[str(log_dir / "gradle-dependency-tree.txt")],
    )

    assert result["returncode"] == 0
    assert seen["components"] == [
        ("maven", "org.current:gradle-lib", "1.0.0"),
        ("npm", "lodash", "4.17.20"),
    ]


def test_jfrog_audit_writes_fresh_json_when_no_components(tmp_path):
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    log_dir.mkdir()

    stale_path = log_dir / "jfrog-audit.json"
    stale_path.write_text(
        json.dumps(
            {
                "component_count": 999,
                "vulnerability_count": 999,
                "vulnerable_components": [{"ecosystem": "maven", "package": "stale"}],
            }
        ),
        encoding="utf-8",
    )

    result = jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="https://jfrog.example.com",
        ecosystems={"npm"},
        npm_package_dirs=[str(project_dir)],
        gradle_tree_paths=[],
    )

    report = json.loads(stale_path.read_text(encoding="utf-8"))

    assert result["json_path"] == str(stale_path)
    assert report["component_count"] == 0
    assert report["vulnerability_count"] == 0
    assert report["vulnerable_components"] == []
    assert "No resolved dependency components found" in report["skipped_reason"]
def test_jfrog_audit_writes_fresh_json_when_xray_host_missing(tmp_path):
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    log_dir.mkdir()
    _write_lockfile(project_dir)

    result = jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="",
        ecosystems={"npm"},
        npm_package_dirs=[str(project_dir)],
    )

    report = json.loads((log_dir / "jfrog-audit.json").read_text(encoding="utf-8"))
    assert result["json_path"] == str(log_dir / "jfrog-audit.json")
    assert report["component_count"] == 1
    assert report["vulnerability_count"] == 0
    assert report["vulnerable_components"] == []
    assert "Xray API host is not configured" in report["skipped_reason"]


def test_node_only_worker_passes_npm_scope_to_jfrog_audit(monkeypatch, tmp_path):
    from ui.worker import PipelineWorker

    project_dir = tmp_path / "repo"
    node_dir = project_dir / "node-app"
    node_dir.mkdir(parents=True)
    pkg_path = node_dir / "package.json"
    pkg_path.write_text("{}", encoding="utf-8")
    seen = {}

    monkeypatch.setattr(
        "shared.github.clone_github_repo",
        lambda github_url, checkout_dir=None: str(project_dir),
    )
    monkeypatch.setattr(
        "ui.utils.scan_for_dep_managers",
        lambda root: [{"type": "node", "file_path": str(pkg_path), "label": "node-app/package.json"}],
    )

    def fake_analyze_node(**kwargs):
        return {
            "display_changes": [],
            "skipped_display": [],
            "pkg": {},
            "direct_changes": [],
            "override_changes": [],
            "pkg_json_path": kwargs["pkg_json_path"],
            "pkg_json_dir": str(node_dir),
        }
    def fake_run_jfrog_audit(**kwargs):
        seen.update(kwargs)
        return {
            "json_path": str(tmp_path / "jfrog-audit.json"),
            "returncode": 0,
            "vulnerable_components": [],
            "vulnerability_count": 0,
        }

    monkeypatch.setattr("pipeline.node.analyze_node", fake_analyze_node)
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_run_jfrog_audit)

    worker = PipelineWorker(
        {
            "github_url": "https://example.invalid/repo.git",
            "checkout_dir": str(tmp_path / "checkout"),
            "log_dir": str(tmp_path / "logs"),
            "skip_block_check": False,
            "xray_url": "https://jfrog.example.com/xray",
        }
    )

    assert worker._analyze_pipeline() is not None
    assert seen["ecosystems"] == {"npm"}
    assert seen["npm_lock_paths"] == [str(tmp_path / "logs" / "npm-dependency-tree.json")]
    assert seen["gradle_tree_paths"] == []


def test_mixed_worker_passes_node_and_gradle_scopes_to_jfrog_audit(monkeypatch, tmp_path):
    from ui.worker import PipelineWorker

    project_dir = tmp_path / "repo"
    node_dir = project_dir / "node-app"
    gradle_dir = project_dir / "gradle-app"
    node_dir.mkdir(parents=True)
    gradle_dir.mkdir(parents=True)
    pkg_path = node_dir / "package.json"
    build_file = gradle_dir / "build.gradle"
    pkg_path.write_text("{}", encoding="utf-8")
    build_file.write_text("", encoding="utf-8")
    seen = {}

    monkeypatch.setattr(
        "shared.github.clone_github_repo",
        lambda github_url, checkout_dir=None: str(project_dir),
    )
    monkeypatch.setattr(
        "ui.utils.scan_for_dep_managers",
        lambda root: [
            {"type": "node", "file_path": str(pkg_path), "label": "node-app/package.json"},
            {"type": "gradle", "file_path": str(build_file), "label": "gradle-app/build.gradle"},
        ],
    )

    def fake_analyze_node(**kwargs):
        return {
            "display_changes": [],
            "skipped_display": [],
            "pkg": {},
            "direct_changes": [],
            "override_changes": [],
            "pkg_json_path": kwargs["pkg_json_path"],
            "pkg_json_dir": str(node_dir),
        }

    def fake_analyze_gradle(**kwargs):
        return {
            "display_changes": [],
            "skipped_display": [],
            "build_file": kwargs["build_file"],
            "build_text": "",
            "changes": [],
            "force_entries": [],
        }
    def fake_run_jfrog_audit(**kwargs):
        seen.update(kwargs)
        return {
            "json_path": str(tmp_path / "jfrog-audit.json"),
            "returncode": 0,
            "vulnerable_components": [],
            "vulnerability_count": 0,
        }

    monkeypatch.setattr("pipeline.node.analyze_node", fake_analyze_node)
    monkeypatch.setattr("pipeline.gradle.analyze_gradle", fake_analyze_gradle)
    monkeypatch.setattr("shared.jfrog_scan.run_jfrog_audit", fake_run_jfrog_audit)

    worker = PipelineWorker(
        {
            "github_url": "https://example.invalid/repo.git",
            "checkout_dir": str(tmp_path / "checkout"),
            "log_dir": str(tmp_path / "logs"),
            "skip_block_check": False,
            "xray_url": "https://jfrog.example.com/xray",
        }
    )

    assert worker._analyze_pipeline() is not None
    assert seen["ecosystems"] == {"npm", "maven"}
    assert seen["npm_lock_paths"] == [str(tmp_path / "logs" / "npm-dependency-tree.json")]
    assert seen["gradle_tree_paths"] == [str(tmp_path / "logs" / "gradle-dependency-tree.txt")]
