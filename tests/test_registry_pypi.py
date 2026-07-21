"""Tests for the new PyPI accessibility probe (registry/pypi.py).

PyPI previously had no reachability/registry-block check at all -- pip index
versions listing a version was trusted outright, unlike Maven (HTTP HEAD probe)
and npm (`npm pack` probe). These tests only exercise mocked subprocess calls;
this cannot be validated against a real Artifactory PyPI index in this
environment, and should be confirmed against the user's next real batch run.
"""

from unittest.mock import MagicMock

from shared.semver import SemVer


def test_is_version_blocked_detects_403(monkeypatch):
    from registry import pypi

    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stderr = "ERROR: 403 Client Error: Forbidden for url: https://example/simple/some-pkg/"
    fake_result.stdout = ""
    monkeypatch.setattr(pypi.subprocess, "run", lambda *a, **k: fake_result)

    blocked, snippet = pypi.is_version_blocked(
        "some-pkg", "1.2.3", "https://example/simple", "python3", 30
    )

    assert blocked is True
    assert "403" in snippet


def test_is_version_blocked_detects_no_matching_distribution(monkeypatch):
    from registry import pypi

    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stderr = "ERROR: No matching distribution found for some-pkg==9.9.9"
    fake_result.stdout = ""
    monkeypatch.setattr(pypi.subprocess, "run", lambda *a, **k: fake_result)

    blocked, snippet = pypi.is_version_blocked(
        "some-pkg", "9.9.9", None, "python3", 30
    )

    assert blocked is True


def test_is_version_blocked_false_on_success(monkeypatch):
    from registry import pypi

    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stderr = ""
    fake_result.stdout = ""
    monkeypatch.setattr(pypi.subprocess, "run", lambda *a, **k: fake_result)

    blocked, snippet = pypi.is_version_blocked(
        "some-pkg", "1.2.3", None, "python3", 30
    )

    assert blocked is False
    assert snippet == ""


def test_is_version_blocked_treats_unrecognized_failure_as_not_blocked(monkeypatch):
    """A failure that isn't a recognized block marker (e.g. a transient
    network error) must not be reported as blocked -- matches npm's
    is_version_blocked, which only classifies known 403/404-style markers."""
    from registry import pypi

    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stderr = "ERROR: Could not find a version that satisfies some other constraint"
    fake_result.stdout = ""
    monkeypatch.setattr(pypi.subprocess, "run", lambda *a, **k: fake_result)

    blocked, snippet = pypi.is_version_blocked(
        "some-pkg", "1.2.3", None, "python3", 30
    )

    assert blocked is False


def test_find_unblocked_version_prefers_forward_candidate(monkeypatch):
    from registry import pypi

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )

    def fake_is_version_blocked(package, version, index_url, python_cmd, timeout):
        return version == "1.2.0", ""

    monkeypatch.setattr(pypi, "is_version_blocked", fake_is_version_blocked)

    result, diagnostic = pypi.find_unblocked_version(
        "some-pkg",
        SemVer.parse("1.0.0"),
        [SemVer.parse("1.0.0"), SemVer.parse("1.1.0"), SemVer.parse("1.2.0")],
        index_url=None,
        python_cmd="python3",
        timeout=30,
    )

    assert str(result) == "1.1.0"
    assert diagnostic == ""


def test_find_unblocked_version_reports_diagnostic_when_all_blocked(monkeypatch):
    from registry import pypi

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )
    monkeypatch.setattr(pypi, "is_version_blocked", lambda *a, **k: (True, "403"))

    result, diagnostic = pypi.find_unblocked_version(
        "some-pkg",
        SemVer.parse("1.0.0"),
        [SemVer.parse("1.1.0")],
        index_url=None,
        python_cmd="python3",
        timeout=30,
    )

    assert result is None
    assert "inaccessible" in diagnostic
