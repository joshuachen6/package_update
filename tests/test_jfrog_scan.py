import json
from pathlib import Path

from shared import jfrog_scan


def test_collects_npm_and_gradle_components_and_calls_xray_api(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    log_dir.mkdir()

    (project_dir / "package-lock.json").write_text(
        json.dumps(
            {
                "packages": {
                    "": {"name": "demo"},
                    "node_modules/lodash": {"version": "4.17.20"},
                    "node_modules/@scope/pkg": {"version": "1.2.3"},
                },
                "dependencies": {
                    "minimist": {"version": "1.2.5"},
                },
            }
        ),
        encoding="utf-8",
    )

    (log_dir / "gradle-dependency-tree.txt").write_text(
        """
runtimeClasspath - Runtime classpath
+--- org.springframework:spring-core:5.3.0 -> 5.3.39
\\--- com.fasterxml.jackson.core:jackson-databind:2.13.0
""",
        encoding="utf-8",
    )

    seen = {}

    def fake_search(components, xray_host=None, auth=None, timeout=30):
        seen["host"] = xray_host
        seen["auth"] = auth
        seen["components"] = components
        return {
            "npm://lodash:4.17.20": ["CVE-0000-0001"],
            "gav://org.springframework:spring-core:5.3.39": ["CVE-0000-0002"],
        }, ""

    monkeypatch.setattr(jfrog_scan, "search_cves_by_components", fake_search)

    result = jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="company.jfrog.io",
        auth=("user", "token"),
    )

    component_ids = {jfrog_scan._component_id(component) for component in seen["components"]}
    assert seen["host"] == "https://company.jfrog.io"
    assert seen["auth"] == ("user", "token")
    assert "npm://lodash:4.17.20" in component_ids
    assert "npm://@scope/pkg:1.2.3" in component_ids
    assert "npm://minimist:1.2.5" in component_ids
    assert "gav://org.springframework:spring-core:5.3.39" in component_ids
    assert "gav://com.fasterxml.jackson.core:jackson-databind:2.13.0" in component_ids
    assert result["returncode"] == 0
    assert result["vulnerability_count"] == 2
    assert result["vulnerable_component_count"] == 2
    assert Path(result["json_path"]).is_file()


def test_jfrog_api_scan_skips_without_host(tmp_path):
    result = jfrog_scan.run_jfrog_audit(str(tmp_path), str(tmp_path), xray_host="")
    assert result["available"] is False
    assert result["returncode"] is None
    assert "host is not configured" in result["stderr"]
def test_jfrog_scan_writes_json_report_even_when_api_errors(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    log_dir.mkdir()

    (project_dir / "package-lock.json").write_text(
        json.dumps(
            {
                "packages": {
                    "node_modules/lodash": {"version": "4.17.20"},
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_search(components, xray_host=None, auth=None, timeout=30):
        return {}, "Xray CVE lookup HTTP 401"

    monkeypatch.setattr(jfrog_scan, "search_cves_by_components", fake_search)

    result = jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="https://jfrog.example.com",
    )

    assert result["returncode"] == 1
    assert result["json_path"]
    assert Path(result["json_path"]).is_file()
    report = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert report["component_count"] == 1
    assert report["errors"] == ["Xray CVE lookup HTTP 401"]

    # Live bug: this exact result -- vulnerability_count=0 because no batch
    # happened to find anything vulnerable -- was previously trusted by
    # callers as "scan succeeded, repo is clean" despite the populated
    # errors list. audit_scan_usable is the one shared check that must
    # catch this.
    assert jfrog_scan.audit_scan_usable(result) is False


def test_audit_scan_usable_true_for_clean_successful_scan():
    assert jfrog_scan.audit_scan_usable(
        {"available": True, "errors": [], "stderr": ""}
    ) is True


def test_audit_scan_usable_false_when_host_not_configured():
    assert jfrog_scan.audit_scan_usable(
        {"available": False, "errors": [], "stderr": "Xray API host is not configured."}
    ) is False


def test_run_jfrog_audit_with_retry_recovers_after_transient_failure(monkeypatch):
    """A real batch run showed 5 of 28+ repos hit a transient per-request
    network error (connection reset, timeout, DNS failure) while every other
    repo scanned fine against the same endpoint/credentials in the same run
    -- a blip, not an outage. The retry wrapper must retry the same,
    idempotent scan call rather than giving up on the first failure."""
    calls = {"n": 0}

    def fake_audit(**kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            return {
                "available": True,
                "vulnerability_count": 0,
                "vulnerable_components": [],
                "errors": ["Xray CVE lookup failed: <urlopen error timed out>"],
                "stderr": "Xray CVE lookup failed: <urlopen error timed out>",
            }
        return {
            "available": True,
            "vulnerability_count": 3,
            "vulnerable_components": [{"package": "some-pkg"}],
            "errors": [],
            "stderr": "",
        }

    monkeypatch.setattr(jfrog_scan, "run_jfrog_audit", fake_audit)
    monkeypatch.setattr(jfrog_scan.time, "sleep", lambda *_: None)

    result = jfrog_scan.run_jfrog_audit_with_retry(project_dir=".", log_dir=".")

    assert calls["n"] == 2
    assert jfrog_scan.audit_scan_usable(result) is True
    assert result["vulnerability_count"] == 3


def test_run_jfrog_audit_with_retry_gives_up_after_max_attempts(monkeypatch):
    calls = {"n": 0}

    def fake_audit(**kwargs):
        calls["n"] += 1
        return {
            "available": True,
            "vulnerability_count": 0,
            "vulnerable_components": [],
            "errors": ["Xray CVE lookup failed: <urlopen error timed out>"],
            "stderr": "Xray CVE lookup failed: <urlopen error timed out>",
        }

    monkeypatch.setattr(jfrog_scan, "run_jfrog_audit", fake_audit)
    monkeypatch.setattr(jfrog_scan.time, "sleep", lambda *_: None)

    result = jfrog_scan.run_jfrog_audit_with_retry(
        project_dir=".", log_dir=".", max_attempts=3,
    )

    assert calls["n"] == 3
    assert jfrog_scan.audit_scan_usable(result) is False


def test_audit_scan_usable_false_with_partial_results_and_errors():
    """A scan that returned SOME vulnerable components (from batches that
    succeeded) but also recorded errors (from batches that didn't) is still
    untrustworthy -- packages hidden in the failed batch could be
    incorrectly treated as clean. Confirmed live: a real repo's before-scan
    reported 21 vulnerabilities alongside a timeout error; the true count
    (found by a later, fully-successful scan) was 50."""
    assert jfrog_scan.audit_scan_usable(
        {
            "available": True,
            "vulnerability_count": 21,
            "errors": ["Xray CVE lookup failed: <urlopen error timed out>"],
            "stderr": "Xray CVE lookup failed: <urlopen error timed out>",
        }
    ) is False


def test_jfrog_scan_strips_artifactory_path_from_xray_host(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    log_dir.mkdir()

    (project_dir / "package-lock.json").write_text(
        json.dumps(
            {
                "packages": {
                    "node_modules/lodash": {"version": "4.17.20"},
                }
            }
        ),
        encoding="utf-8",
    )
    seen = {}

    def fake_search(components, xray_host=None, auth=None, timeout=30):
        seen["xray_host"] = xray_host
        return {}, ""

    monkeypatch.setattr(jfrog_scan, "search_cves_by_components", fake_search)

    result = jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="https://humana.jfrog.io/artifactory",
    )

    assert seen["xray_host"] == "https://humana.jfrog.io"
    assert result["returncode"] == 0

def test_python_tree_component_collection_parses_pinned_deps(tmp_path):
    from shared.jfrog_scan import _collect_python_tree_components

    (tmp_path / "python-dependency-tree.txt").write_text(
        "\nPython dependency tree for /repo/pyproject.toml\n"
        "=============================================\n"
        "+-- requests==2.28.0\n"
        "    +-- charset-normalizer==3.1.0\n"
        "    +-- idna==3.4\n"
        "+-- loguru>=0.7\n",
        encoding="utf-8",
    )

    components = _collect_python_tree_components(str(tmp_path))

    assert [(c.ecosystem, c.package, c.version) for c in components] == [
        ("pypi", "requests", "2.28.0"),
        ("pypi", "charset-normalizer", "3.1.0"),
        ("pypi", "idna", "3.4"),
    ]


def test_python_tree_component_collection_normalizes_package_names(tmp_path):
    from shared.jfrog_scan import _collect_python_tree_components

    (tmp_path / "python-dependency-tree.txt").write_text(
        "+-- PyJWT==2.8.0\n"
        "    +-- typing_extensions==4.7.0\n",
        encoding="utf-8",
    )

    components = _collect_python_tree_components(str(tmp_path))

    assert [(c.package, c.version) for c in components] == [
        ("pyjwt", "2.8.0"),
        ("typing-extensions", "4.7.0"),
    ]


def test_python_tree_collection_returns_empty_when_no_tree_file(tmp_path):
    from shared.jfrog_scan import _collect_python_tree_components

    components = _collect_python_tree_components(str(tmp_path))

    assert components == []


def test_run_jfrog_audit_uses_python_tree_when_available(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    (log_dir / "python-dependency-tree.txt").write_text(
        "+-- requests==2.28.0\n"
        "    +-- urllib3==1.26.14\n",
        encoding="utf-8",
    )

    seen = {}

    def fake_search(components, xray_host=None, auth=None, timeout=30):
        seen["components"] = components
        return {}, ""

    monkeypatch.setattr(jfrog_scan, "search_cves_by_components", fake_search)

    jfrog_scan.run_jfrog_audit(
        str(tmp_path),
        str(log_dir),
        xray_host="https://jfrog.example.com",
        ecosystems={"pypi"},
    )

    ids = {jfrog_scan._component_id(c) for c in seen["components"]}
    assert "pypi://requests:2.28.0" in ids
    assert "pypi://urllib3:1.26.14" in ids


def test_run_jfrog_audit_falls_back_to_requirements_when_no_tree(tmp_path, monkeypatch):
    project_dir = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    project_dir.mkdir()
    log_dir.mkdir()

    (project_dir / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")

    seen = {}

    def fake_search(components, xray_host=None, auth=None, timeout=30):
        seen["components"] = components
        return {}, ""

    monkeypatch.setattr(jfrog_scan, "search_cves_by_components", fake_search)

    jfrog_scan.run_jfrog_audit(
        str(project_dir),
        str(log_dir),
        xray_host="https://jfrog.example.com",
        ecosystems={"pypi"},
    )

    ids = {jfrog_scan._component_id(c) for c in seen["components"]}
    assert "pypi://requests:2.31.0" in ids


def test_gradle_component_collection_ignores_stale_nested_log_dirs(tmp_path):
    from shared.jfrog_scan import _collect_gradle_components

    stale_dir = tmp_path / "old-run"
    stale_dir.mkdir()
    (stale_dir / "gradle-dependency-tree.txt").write_text(
        "+--- org.old:stale-lib:1.0.0\n",
        encoding="utf-8",
    )

    components = _collect_gradle_components(str(tmp_path))

    assert components == []


def test_gradle_component_collection_reads_current_run_log_only(tmp_path):
    from shared.jfrog_scan import _collect_gradle_components

    stale_dir = tmp_path / "old-run"
    stale_dir.mkdir()
    (stale_dir / "gradle-dependency-tree.txt").write_text(
        "+--- org.old:stale-lib:1.0.0\n",
        encoding="utf-8",
    )
    (tmp_path / "gradle-dependency-tree.txt").write_text(
        "+--- org.current:fresh-lib:2.0.0\n",
        encoding="utf-8",
    )

    components = _collect_gradle_components(str(tmp_path))

    assert [(c.ecosystem, c.package, c.version) for c in components] == [
        ("maven", "org.current:fresh-lib", "2.0.0")
    ]
