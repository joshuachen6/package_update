from shared.maven_version import MavenVersion


def test_concurrent_probe_preserves_forward_preference():
    import threading
    import time

    from shared.version_search import probe_candidates_concurrently

    versions = [
        MavenVersion.parse("1.0.0"),
        MavenVersion.parse("1.1.0"),
        MavenVersion.parse("1.2.0"),
        MavenVersion.parse("1.3.0"),
    ]
    started = set()
    lock = threading.Lock()

    def accessible(version):
        raw = str(version)
        with lock:
            started.add(raw)

        delays = {
            "1.0.0": 0.04,
            "1.1.0": 0.08,
            "1.2.0": 0.01,
            "1.3.0": 0.20,
        }
        time.sleep(delays[raw])
        return raw in {"1.1.0", "1.2.0"}

    result = probe_candidates_concurrently(versions, accessible, max_workers=4)

    # 1.2.0 finishes first, but 1.1.0 is earlier in preference order and wins.
    assert str(result) == "1.1.0"


def test_concurrent_probe_uses_highest_backward_candidate():
    import time

    from shared.version_search import probe_candidates_concurrently

    # Backward candidates are supplied highest-first.
    versions = [
        MavenVersion.parse("2.9.0"),
        MavenVersion.parse("2.8.0"),
        MavenVersion.parse("2.7.0"),
        MavenVersion.parse("2.6.0"),
    ]

    def accessible(version):
        raw = str(version)
        if raw == "2.7.0":
            time.sleep(0.01)
            return True
        if raw == "2.8.0":
            time.sleep(0.05)
            return True
        time.sleep(0.02)
        return False

    result = probe_candidates_concurrently(versions, accessible, max_workers=4)

    # 2.7.0 responds first, but 2.8.0 is the preferred working downgrade.
    assert str(result) == "2.8.0"


def test_probe_candidates_concurrently_empty_list_returns_none():
    from shared.version_search import probe_candidates_concurrently

    assert probe_candidates_concurrently([], lambda v: True) is None


def test_find_safe_version_prefers_forward_and_skips_cve_versions(monkeypatch):
    """find_safe_version must CVE-filter each direction before probing, and
    must not send a single backward probe when a forward candidate succeeds
    (probing is not free -- an ecosystem's is_accessible callback may spawn a
    real subprocess or network call)."""
    from shared.version_search import find_safe_version

    forward = [
        MavenVersion.parse("2.0.0"),
        MavenVersion.parse("2.1.0"),
        MavenVersion.parse("2.2.0"),
    ]
    backward: list = []
    probed = []

    def fake_filter_versions_without_cves(ecosystem, package, versions, **kwargs):
        # 2.0.0 has a CVE and must never reach the accessibility probe.
        safe = [v for v in versions if str(v) != "2.0.0"]
        vulnerable = [v for v in versions if str(v) == "2.0.0"]
        return safe, vulnerable, ""

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        fake_filter_versions_without_cves,
    )

    def is_accessible(v):
        probed.append(str(v))
        return str(v) == "2.1.0"

    result, diagnostic = find_safe_version(
        forward, backward, is_accessible, "maven", "org.example:thing"
    )

    assert str(result) == "2.1.0"
    assert diagnostic == ""
    assert "2.0.0" not in probed


def test_find_safe_version_skips_backward_cve_lookup_when_forward_succeeds(
    monkeypatch,
):
    """Live perf bug: every package paid for a full backward-candidates Xray
    CVE lookup up front, even though the accessibility probe right below it
    was already correctly lazy ("do not send backward probes unless every
    forward candidate failed"). The Xray call is a real network round-trip
    (up to `timeout`); since most packages succeed on the forward search,
    this was an unconditional extra round-trip paid by nearly every package
    -- a real contributor to "Applying updates" taking minutes. Backward's
    CVE lookup must only happen once forward comes up empty.
    """
    from shared.version_search import find_safe_version

    forward = [MavenVersion.parse("2.1.0")]
    backward = [MavenVersion.parse("1.9.0")]
    filtered_directions = []

    def fake_filter_versions_without_cves(ecosystem, package, versions, **kwargs):
        filtered_directions.append(tuple(str(v) for v in versions))
        return versions, [], ""

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        fake_filter_versions_without_cves,
    )

    result, diagnostic = find_safe_version(
        forward, backward, lambda v: str(v) == "2.1.0", "maven", "org.example:thing"
    )

    assert str(result) == "2.1.0"
    assert diagnostic == ""
    assert filtered_directions == [("2.1.0",)]


def test_find_safe_version_falls_back_to_backward_when_forward_exhausted(monkeypatch):
    from shared.version_search import find_safe_version

    forward = [MavenVersion.parse("3.0.0")]
    backward = [MavenVersion.parse("2.9.0"), MavenVersion.parse("2.8.0")]

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )

    def is_accessible(v):
        return str(v) == "2.9.0"

    result, diagnostic = find_safe_version(
        forward, backward, is_accessible, "npm", "some-pkg"
    )

    assert str(result) == "2.9.0"
    assert diagnostic == ""


def test_find_safe_version_reports_diagnostic_when_nothing_accessible(monkeypatch):
    from shared.version_search import find_safe_version

    forward = [MavenVersion.parse("2.1.0")]
    backward = [MavenVersion.parse("1.9.0")]

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )

    result, diagnostic = find_safe_version(
        forward, backward, lambda v: False, "pypi", "some-pkg"
    )

    assert result is None
    assert "1 forward and 1 backward" in diagnostic
    assert "inaccessible" in diagnostic


def test_gradle_find_accessible_version_caps_probe_timeout_below_gradle_timeout(
    monkeypatch,
):
    """Live bug: find_accessible_version passed gradle_timeout (raised to
    150-180s this session so real builds wouldn't be mistaken for hangs)
    straight through to the Xray CVE-filter and Artifactory HEAD probes --
    lightweight metadata calls that should fail fast, not borrow a build's
    patience. Confirmed live: a single package's accessibility search took
    ~90s in a proactive-check run even with zero concurrency contention (2
    packages against 8 available slots), and a cluster of related packages
    (e.g. 8 io.netty:* artifacts flagged together) stacked that into a
    multi-minute stall. The probe timeout must be capped independently of
    whatever gradle_timeout the caller passes in.
    """
    import parsers.gradle as gradle

    seen_timeouts: list[int] = []

    def fake_version_accessible(group, artifact, version, url, auth, timeout):
        seen_timeouts.append(timeout)
        return version == "2.21.5"

    monkeypatch.setattr(gradle, "version_accessible", fake_version_accessible)
    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, timeout=30, **kwargs: (
            seen_timeouts.append(timeout) or versions,
            [],
            "",
        ),
    )

    result = gradle.find_accessible_version(
        "com.fasterxml.jackson.core",
        "jackson-databind",
        MavenVersion.parse("2.21.4"),
        [MavenVersion.parse("2.21.4"), MavenVersion.parse("2.21.5")],
        "https://repo.example",
        None,
        180,
    )

    assert result == "2.21.5"
    assert seen_timeouts
    assert all(timeout <= 20 for timeout in seen_timeouts)
