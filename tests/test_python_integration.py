from __future__ import annotations

from pathlib import Path

from managers import get_manager_spec, manager_total_keys
from output.python import write_python_dependency_file
from parsers.python import (
    parse_pyproject_text,
    parse_requirements_text,
    update_python_dependency_text,
    update_requirements_text,
)
from quick_update import QuickUpdateConfig, _explicit_managers
from shared.jfrog_scan import _collect_python_components
from ui.utils import scan_for_dep_managers


def test_python_requirements_parser_and_update():
    text = chr(10).join(["requests==2.31.0", "flask>=3.0.0 # keep", "# comment"]) + chr(10)
    reqs = parse_requirements_text(text)
    assert [req.name for req in reqs] == ["requests", "flask"]
    assert reqs[0].version == "2.31.0"
    updated = update_requirements_text(text, [{"line_index": 0, "new_version": "2.32.4"}])
    assert "requests==2.32.4" in updated
    assert "flask>=3.0.0 # keep" in updated


def test_pyproject_project_dependencies_parser_and_update():
    text = chr(10).join(
        [
            "[project]",
            'requires-python = ">=3.13"',
            "dependencies = [",
            '  "requests==2.31.0",',
            '  "flask>=3.0.0",',
            "]",
        ]
    ) + chr(10)
    reqs = parse_pyproject_text(text)
    assert [(req.name, req.operator, req.version) for req in reqs] == [
        ("requests", "==", "2.31.0"),
        ("flask", ">=", "3.0.0"),
    ]
    updated = update_python_dependency_text(
        text,
        [{"line_index": 3, "new_version": "2.32.4"}],
        file_type="pyproject",
    )
    assert '"requests==2.32.4",' in updated
    assert "requires-python" in updated


def test_pyproject_poetry_dependencies_parser_and_update():
    text = chr(10).join(
        [
            "[tool.poetry.dependencies]",
            'python = "^3.11"',
            'requests = "==2.31.0"',
            'flask = { version = ">=3.0.0", optional = true }',
        ]
    ) + chr(10)
    reqs = parse_pyproject_text(text)
    assert [(req.name, req.operator, req.version) for req in reqs] == [
        ("requests", "==", "2.31.0"),
        ("flask", ">=", "3.0.0"),
    ]
    updated = update_python_dependency_text(
        text,
        [{"line_index": 2, "new_version": "2.32.4"}, {"line_index": 3, "new_version": "3.1.0"}],
        file_type="pyproject",
    )
    assert 'requests = "==2.32.4"' in updated
    assert 'flask = { version = ">=3.1.0", optional = true }' in updated


def test_python_manager_registered():
    spec = get_manager_spec("python")
    assert spec.ecosystem == "pypi"
    assert "python_direct" in manager_total_keys()


def test_scan_for_python_dependency_files(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("requests==2.31.0" + chr(10), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]" + chr(10), encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    managers = scan_for_dep_managers(str(tmp_path))
    labels_by_type = {(manager["type"], Path(manager["file_path"]).name) for manager in managers}
    assert ("python", "requirements.txt") in labels_by_type
    assert ("python", "pyproject.toml") in labels_by_type
    assert ("node", "package.json") in labels_by_type


def test_jfrog_collects_pyproject_components(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        chr(10).join(
            [
                "[project]",
                'requires-python = ">=3.13"',
                "dependencies = [",
                '  "requests==2.31.0",',
                "]",
            ]
        ) + chr(10),
        encoding="utf-8",
    )
    components = _collect_python_components(str(tmp_path))
    assert [(component.ecosystem, component.package, component.version) for component in components] == [
        ("pypi", "requests", "2.31.0")
    ]


def test_explicit_python_manager(tmp_path: Path):
    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.31.0" + chr(10), encoding="utf-8")
    cfg = QuickUpdateConfig(project_dir=str(tmp_path), python_files=[str(req)])
    managers = _explicit_managers(cfg, str(tmp_path))
    assert len(managers) == 1
    assert managers[0]["type"] == "python"
    assert managers[0]["file_path"] == str(req.resolve())


def test_write_python_dependency_file(tmp_path: Path):
    req = tmp_path / "requirements.txt"
    req.write_text("old" + chr(10), encoding="utf-8")
    write_python_dependency_file("new" + chr(10), str(req), in_place=True)
    assert req.read_text(encoding="utf-8") == "new" + chr(10)


def test_python_analysis_logs_resolved_dependency_tree(tmp_path: Path, monkeypatch):
    import managers.python as python_mgr
    from pipeline.python import analyze_python
    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.31.0" + chr(10), encoding="utf-8")

    monkeypatch.setattr(python_mgr, "available_versions", lambda *args, **kwargs: ("2.31.0",))
    monkeypatch.setattr(
        python_mgr,
        "_load_installed_packages",
        lambda *args, **kwargs: {
            "requests": {
                "name": "requests",
                "version": "2.31.0",
                "requires_dist": ["urllib3<3,>=1.26", "PySocks>=1.5.6; extra == 'socks'"],
            },
            "urllib3": {"name": "urllib3", "version": "2.0.7", "requires_dist": []},
        },
    )
    analyze_python(str(req), str(tmp_path / "logs"))

    tree = (tmp_path / "logs" / "python-dependency-tree.txt").read_text(encoding="utf-8")
    assert "Python dependency tree for" in tree
    assert "+-- requests==2.31.0" in tree
    assert "    +-- urllib3==2.0.7" in tree
    assert "PySocks" not in tree


def test_python_analysis_no_changes_when_no_cve_packages(tmp_path: Path, monkeypatch):
    import managers.python as python_mgr
    from pipeline.python import analyze_python

    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.31.0\nurllib3==1.26.0\n", encoding="utf-8")

    monkeypatch.setattr(python_mgr, "available_versions", lambda *a, **kw: ("9.9.9",))
    monkeypatch.setattr(python_mgr, "_load_installed_packages", lambda *a, **kw: {})

    result = analyze_python(str(req), str(tmp_path / "logs"))

    assert result["display_changes"] == []
    assert result["updated_text"] == result["original_text"]


def test_python_analysis_no_changes_when_cve_packages_is_none(tmp_path: Path, monkeypatch):
    import managers.python as python_mgr
    from pipeline.python import analyze_python

    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.31.0\n", encoding="utf-8")

    monkeypatch.setattr(python_mgr, "available_versions", lambda *a, **kw: ("9.9.9",))
    monkeypatch.setattr(python_mgr, "_load_installed_packages", lambda *a, **kw: {})

    result = analyze_python(str(req), str(tmp_path / "logs"), cve_packages=None)

    assert result["display_changes"] == []


def test_python_analysis_only_updates_cve_packages(tmp_path: Path, monkeypatch):
    import managers.python as python_mgr
    from pipeline.python import analyze_python

    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.31.0\nurllib3==1.26.0\nflask==3.0.0\n", encoding="utf-8")

    monkeypatch.setattr(python_mgr, "available_versions", lambda *a, **kw: ("9.9.9",))
    monkeypatch.setattr(python_mgr, "_load_installed_packages", lambda *a, **kw: {})

    result = analyze_python(
        str(req), str(tmp_path / "logs"), cve_packages={"requests"}
    )

    updated_packages = [ch["package"] for ch in result["display_changes"]]
    assert updated_packages == ["requests"]
    assert "requests==9.9.9" in result["updated_text"]
    assert "urllib3==1.26.0" in result["updated_text"]
    assert "flask==3.0.0" in result["updated_text"]


def test_python_analysis_tree_still_generated_with_no_cve_packages(tmp_path: Path, monkeypatch):
    import managers.python as python_mgr
    from pipeline.python import analyze_python

    req = tmp_path / "requirements.txt"
    req.write_text("requests==2.31.0\n", encoding="utf-8")

    monkeypatch.setattr(python_mgr, "available_versions", lambda *a, **kw: ("9.9.9",))
    monkeypatch.setattr(
        python_mgr,
        "_load_installed_packages",
        lambda *a, **kw: {
            "requests": {"name": "requests", "version": "2.31.0", "requires_dist": []}
        },
    )

    analyze_python(str(req), str(tmp_path / "logs"))

    tree = (tmp_path / "logs" / "python-dependency-tree.txt").read_text(encoding="utf-8")
    assert "+-- requests==2.31.0" in tree



def test_python_range_does_not_select_version_above_upper_bound(
    tmp_path: Path,
    monkeypatch,
):
    import managers.python as python_mgr
    from pipeline.python import analyze_python

    req = tmp_path / "requirements.txt"
    req.write_text("requests>=2.28.0,<3.0.0\n", encoding="utf-8")

    monkeypatch.setattr(
        python_mgr,
        "available_versions",
        lambda *args, **kwargs: (
            "4.0.0",
            "3.1.0",
            "3.0.0",
            "2.32.4",
            "2.31.0",
            "2.28.0",
        ),
    )
    monkeypatch.setattr(python_mgr, "_load_installed_packages", lambda *a, **kw: {})

    result = analyze_python(
        str(req),
        str(tmp_path / "logs"),
        cve_packages={"requests"},
    )

    assert result["changes"][0]["new_version"] == "2.31.0"
    assert "requests>=2.31.0,<3.0.0" in result["updated_text"]


def test_python_compatible_range_excludes_next_minor(
    tmp_path: Path,
    monkeypatch,
):
    import managers.python as python_mgr
    from pipeline.python import analyze_python
    req = tmp_path / "requirements.txt"
    req.write_text("requests~=2.31.0\n", encoding="utf-8")

    monkeypatch.setattr(
        python_mgr,
        "available_versions",
        lambda *args, **kwargs: (
            "3.0.0",
            "2.32.0",
            "2.31.4",
            "2.31.0",
        ),
    )
    monkeypatch.setattr(python_mgr, "_load_installed_packages", lambda *a, **kw: {})

    result = analyze_python(
        str(req),
        str(tmp_path / "logs"),
        cve_packages={"requests"},
    )

    assert result["changes"][0]["new_version"] == "2.31.4"
