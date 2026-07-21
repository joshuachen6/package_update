def test_node_jfrog_audit_runs_before_block_check(monkeypatch, tmp_path):
    from ui.worker import PipelineWorker

    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    pkg_path = project_dir / "package.json"
    pkg_path.write_text("{}", encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        "shared.github.clone_github_repo",
        lambda github_url, checkout_dir=None: str(project_dir),
    )
    monkeypatch.setattr(
        "ui.utils.scan_for_dep_managers",
        lambda root: [
            {
                "type": "node",
                "file_path": str(pkg_path),
                "label": "package.json",
            }
        ],
    )

    def fake_analyze_node(**kwargs):
        calls.append(
            (
                "analyze_node",
                kwargs["skip_block_check"],
                set(kwargs["cve_packages"]),
            )
        )
        return {
            "display_changes": [],
            "skipped_display": [],
            "pkg": {},
            "direct_changes": [],
            "override_changes": [],
            "pkg_json_path": kwargs["pkg_json_path"],
            "pkg_json_dir": str(project_dir),
        }

    def fake_run_jfrog_audit(**kwargs):
        calls.append(("audit", kwargs["project_dir"]))
        return {
            "json_path": str(tmp_path / "jfrog-audit.json"),
            "returncode": 0,
            "vulnerable_components": [
                {
                    "ecosystem": "npm",
                    "package": "lodash",
                    "version": "4.17.20",
                    "cves": ["CVE-0000-0001"],
                }
            ],
            "vulnerability_count": 1,
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

    result = worker._analyze_pipeline()

    assert result is not None
    assert calls == [
        ("analyze_node", True, set()),
        ("audit", str(project_dir)),
        ("analyze_node", False, {"lodash"}),
    ]


def test_node_skip_block_check_setting_applies_only_after_jfrog_audit(monkeypatch, tmp_path):
    from ui.worker import PipelineWorker

    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    pkg_path = project_dir / "package.json"
    pkg_path.write_text("{}", encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        "shared.github.clone_github_repo",
        lambda github_url, checkout_dir=None: str(project_dir),
    )
    monkeypatch.setattr(
        "ui.utils.scan_for_dep_managers",
        lambda root: [
            {
                "type": "node",
                "file_path": str(pkg_path),
                "label": "package.json",
            }
        ],
    )

    def fake_analyze_node(**kwargs):
        calls.append(("analyze_node", kwargs["skip_block_check"]))
        return {
            "display_changes": [],
            "skipped_display": [],
            "pkg": {},
            "direct_changes": [],
            "override_changes": [],
            "pkg_json_path": kwargs["pkg_json_path"],
            "pkg_json_dir": str(project_dir),
        }

    monkeypatch.setattr("pipeline.node.analyze_node", fake_analyze_node)
    monkeypatch.setattr(
        "shared.jfrog_scan.run_jfrog_audit",
        lambda **kwargs: {
            "json_path": str(tmp_path / "jfrog-audit.json"),
            "returncode": 0,
            "vulnerable_components": [],
            "vulnerability_count": 0,
        },
    )

    worker = PipelineWorker(
        {
            "github_url": "https://example.invalid/repo.git",
            "checkout_dir": str(tmp_path / "checkout"),
            "log_dir": str(tmp_path / "logs"),
            "skip_block_check": True,
            "xray_url": "https://jfrog.example.com/xray",
        }
    )

    result = worker._analyze_pipeline()

    assert result is not None
    assert calls == [("analyze_node", True), ("analyze_node", True)]
