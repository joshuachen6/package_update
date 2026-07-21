"""Regression tests for PyPI's new write-time accessibility check.

Live gap: managers/python.py::PythonOutput.apply_updates only CVE-filtered
candidates and trusted whatever `pip index versions` listed -- unlike Maven
(HTTP HEAD probe) and npm (`npm pack` probe), PyPI never verified a candidate
was actually downloadable before writing it. This wires in the new
registry.pypi.is_version_blocked probe via the same shared find_safe_version
orchestration Maven and npm use.
"""

from types import SimpleNamespace

from managers.python import PythonOutput, PythonParsed, PythonVersionSet
from parsers.python import PythonRequirement


def _cfg(skip_block_check=False):
    return SimpleNamespace(
        xray_host=None,
        skip_block_check=skip_block_check,
        pip_index_url=None,
        python_cmd="python3",
        pip_timeout=30,
    )


def _parsed(requirement):
    return PythonParsed(
        file_path="requirements.txt",
        file_type="requirements",
        original_text="",
        requirements=[requirement],
    )


def test_substitutes_blocked_cve_target(monkeypatch):
    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )

    def fake_is_version_blocked(package, version, index_url, python_cmd, timeout):
        return version == "2.0.0", ""

    monkeypatch.setattr("registry.pypi.is_version_blocked", fake_is_version_blocked)

    req = PythonRequirement(
        name="some-pkg",
        version="1.0.0",
        operator="==",
        line_index=0,
        raw_line="some-pkg==1.0.0",
        normalized_name="some-pkg",
        constraint="",
    )
    versions = PythonVersionSet(
        versions_by_package={"some-pkg": ("1.0.0", "2.0.0", "2.1.0")}
    )

    result = PythonOutput().apply_updates(
        _parsed(req), None, versions, {"some-pkg"}, _cfg()
    )

    changes = result.extra["changes"]
    assert len(changes) == 1
    assert changes[0]["new_version"] == "2.1.0"
    assert not result.extra["skipped_raw"]


def test_skips_when_nothing_accessible(monkeypatch):
    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )
    monkeypatch.setattr(
        "registry.pypi.is_version_blocked", lambda *a, **k: (True, "403")
    )

    req = PythonRequirement(
        name="some-pkg",
        version="1.0.0",
        operator="==",
        line_index=0,
        raw_line="some-pkg==1.0.0",
        normalized_name="some-pkg",
        constraint="",
    )
    versions = PythonVersionSet(versions_by_package={"some-pkg": ("1.0.0", "2.0.0")})

    result = PythonOutput().apply_updates(
        _parsed(req), None, versions, {"some-pkg"}, _cfg()
    )

    assert result.extra["changes"] == []
    assert result.extra["skipped_raw"]
    assert result.extra["skipped_raw"][0]["reason"] == "no safe version found in registry"


def test_skip_block_check_bypasses_accessibility_probe(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("is_version_blocked must not be called when skip_block_check=True")

    monkeypatch.setattr("registry.pypi.is_version_blocked", fail_if_called)

    req = PythonRequirement(
        name="some-pkg",
        version="1.0.0",
        operator="==",
        line_index=0,
        raw_line="some-pkg==1.0.0",
        normalized_name="some-pkg",
        constraint="",
    )
    versions = PythonVersionSet(versions_by_package={"some-pkg": ("1.0.0", "2.0.0")})

    result = PythonOutput().apply_updates(
        _parsed(req), None, versions, {"some-pkg"}, _cfg(skip_block_check=True)
    )

    assert result.extra["changes"][0]["new_version"] == "2.0.0"
