"""Regression tests for Node's write-time (inline) accessibility check.

Live bug: `output/node.py::apply_updates` wrote the CVE-remediation target
straight into package.json/overrides with zero accessibility check for the
common case -- only a handful of fallback branches (no criteria for the
current major) already probed. A separate post-write pass,
check_and_fix_blocked_versions, used to catch a blocked version afterward.
This refactor checks accessibility once, inline, right where the target
version is selected (matching Gradle/PyPI's timing), and removes the
separate pass entirely.
"""

from shared.semver import SemVer


def _patch_is_version_blocked(monkeypatch, fake):
    # output.node imports the name directly (a bound copy), while
    # find_unblocked_version's internal probe loop resolves the name live from
    # registry.npm's own module globals -- both must be patched or the two
    # call sites disagree on what's blocked.
    monkeypatch.setattr("output.node.is_version_blocked", fake)
    monkeypatch.setattr("registry.npm.is_version_blocked", fake)


def test_direct_dependency_substitutes_blocked_cve_target(monkeypatch):
    from output.node import apply_updates
    from parsers.node import DirectEntry

    package_json = {"dependencies": {"some-dep": "1.0.0"}}
    direct_entry = DirectEntry(
        package="some-dep",
        section="dependencies",
        spec="1.0.0",
        container=package_json["dependencies"],
        key="some-dep",
        path="dependencies.some-dep",
    )
    lockfile = {"packages": {"node_modules/some-dep": {"version": "1.0.0"}}}

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )

    def fake_is_version_blocked(package, version, registry, npm_cmd, timeout, project_dir):
        # The CVE-remediation target (2.0.0) is blocked; 2.1.0 is reachable.
        return version == "2.0.0", ""

    _patch_is_version_blocked(monkeypatch, fake_is_version_blocked)

    direct_changes, override_changes, skipped, block_changes = apply_updates(
        package_json=package_json,
        direct_entries=[direct_entry],
        criteria={"some-dep": {1: SemVer.parse("2.0.0")}},
        package_versions={"some-dep": {SemVer.parse("2.0.0")}},
        versions_by_package={
            "some-dep": [
                SemVer.parse("1.0.0"),
                SemVer.parse("2.0.0"),
                SemVer.parse("2.1.0"),
            ],
        },
        package_constraints={"some-dep": ">="},
        allow_ambiguous_highest_major=True,
        keep_nested_overrides=False,
        lockfile=lockfile,
    )

    assert package_json["dependencies"]["some-dep"] == "2.1.0"
    assert direct_changes and direct_changes[0]["new_spec"] == "2.1.0"
    assert block_changes == [
        {
            "package": "some-dep",
            "blocked_version": "2.0.0",
            "unblocked_version": "2.1.0",
        }
    ]
    assert not skipped
    assert override_changes == []


def test_flat_override_substitutes_blocked_cve_target(monkeypatch):
    from output.node import apply_updates

    package_json = {"dependencies": {}, "overrides": {}}
    lockfile = {"packages": {}}

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )

    def fake_is_version_blocked(package, version, registry, npm_cmd, timeout, project_dir):
        return version == "3.0.0", ""

    _patch_is_version_blocked(monkeypatch, fake_is_version_blocked)

    direct_changes, override_changes, skipped, block_changes = apply_updates(
        package_json=package_json,
        direct_entries=[],
        criteria={"transitive-dep": {3: SemVer.parse("3.0.0")}},
        package_versions={"transitive-dep": {SemVer.parse("3.0.0")}},
        versions_by_package={
            "transitive-dep": [
                SemVer.parse("2.9.0"),
                SemVer.parse("3.0.0"),
                SemVer.parse("3.1.0"),
            ],
        },
        package_constraints={"transitive-dep": ">="},
        allow_ambiguous_highest_major=True,
        keep_nested_overrides=False,
        lockfile=lockfile,
    )

    assert package_json["overrides"]["transitive-dep"] == "3.1.0"
    assert block_changes == [
        {
            "package": "transitive-dep",
            "blocked_version": "3.0.0",
            "unblocked_version": "3.1.0",
        }
    ]


def test_keeps_original_target_when_nothing_accessible(monkeypatch):
    """When no same-major substitute is reachable at all, the original (still
    blocked) target must still be written -- not dropped -- since several
    downstream branches assume every major in criteria has a selected_by_major
    entry (dropping one risks crashing on an empty dict elsewhere in the
    function for packages with no direct dependency and no override entry).
    """
    from output.node import apply_updates

    package_json = {"dependencies": {}, "overrides": {}}
    lockfile = {"packages": {}}

    monkeypatch.setattr(
        "shared.version_search.filter_versions_without_cves",
        lambda ecosystem, package, versions, **kwargs: (versions, [], ""),
    )
    _patch_is_version_blocked(monkeypatch, lambda *a, **k: (True, "403"))

    direct_changes, override_changes, skipped, block_changes = apply_updates(
        package_json=package_json,
        direct_entries=[],
        criteria={"transitive-dep": {3: SemVer.parse("3.0.0")}},
        package_versions={"transitive-dep": {SemVer.parse("3.0.0")}},
        versions_by_package={"transitive-dep": [SemVer.parse("3.0.0")]},
        package_constraints={"transitive-dep": ">"},
        allow_ambiguous_highest_major=True,
        keep_nested_overrides=False,
        lockfile=lockfile,
    )

    assert package_json["overrides"]["transitive-dep"] == "3.0.0"
    assert block_changes == []


def test_skip_block_check_bypasses_accessibility_probe(monkeypatch):
    from output.node import apply_updates

    package_json = {"dependencies": {}, "overrides": {}}
    lockfile = {"packages": {}}

    def fail_if_called(*args, **kwargs):
        raise AssertionError("is_version_blocked must not be called when skip_block_check=True")

    _patch_is_version_blocked(monkeypatch, fail_if_called)

    direct_changes, override_changes, skipped, block_changes = apply_updates(
        package_json=package_json,
        direct_entries=[],
        criteria={"transitive-dep": {3: SemVer.parse("3.0.0")}},
        package_versions={"transitive-dep": {SemVer.parse("3.0.0")}},
        versions_by_package={"transitive-dep": [SemVer.parse("3.0.0")]},
        package_constraints={"transitive-dep": ">"},
        allow_ambiguous_highest_major=True,
        keep_nested_overrides=False,
        lockfile=lockfile,
        skip_block_check=True,
    )

    assert package_json["overrides"]["transitive-dep"] == "3.0.0"
    assert block_changes == []
