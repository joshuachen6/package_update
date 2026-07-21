from shared.semver import SemVer


def test_find_unblocked_version_prefers_forward_candidate(monkeypatch):
    from registry import npm as npm_registry

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )

    def fake_is_version_blocked(package, version, registry, npm_cmd, timeout, project_dir):
        return version == "1.2.0", ""

    monkeypatch.setattr(npm_registry, "is_version_blocked", fake_is_version_blocked)

    result, diagnostic = npm_registry.find_unblocked_version(
        "some-pkg",
        SemVer.parse("1.0.0"),
        [SemVer.parse("1.0.0"), SemVer.parse("1.1.0"), SemVer.parse("1.2.0")],
        registry=None,
        npm_cmd="npm",
        timeout=30,
    )

    assert str(result) == "1.1.0"
    assert diagnostic == ""


def test_find_unblocked_version_falls_back_to_backward(monkeypatch):
    from registry import npm as npm_registry

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )

    def fake_is_version_blocked(package, version, registry, npm_cmd, timeout, project_dir):
        # Everything above 1.5.0 is blocked; 1.4.0 (below, same major) is accessible.
        return version != "1.4.0", ""

    monkeypatch.setattr(npm_registry, "is_version_blocked", fake_is_version_blocked)

    result, diagnostic = npm_registry.find_unblocked_version(
        "some-pkg",
        SemVer.parse("1.5.0"),
        [SemVer.parse("1.4.0"), SemVer.parse("1.5.0"), SemVer.parse("1.6.0")],
        registry=None,
        npm_cmd="npm",
        timeout=30,
    )

    assert str(result) == "1.4.0"
    assert diagnostic == ""


def test_find_unblocked_version_reports_diagnostic_when_all_blocked(monkeypatch):
    from registry import npm as npm_registry

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )
    monkeypatch.setattr(
        npm_registry, "is_version_blocked", lambda *a, **k: (True, "403")
    )

    result, diagnostic = npm_registry.find_unblocked_version(
        "some-pkg",
        SemVer.parse("1.0.0"),
        [SemVer.parse("1.1.0")],
        registry=None,
        npm_cmd="npm",
        timeout=30,
    )

    assert result is None
    assert "inaccessible" in diagnostic
