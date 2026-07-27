
import json
from types import SimpleNamespace

from shared.maven_version import MavenVersion
from shared.semver import SemVer


def test_override_added_when_nested_copy_vulnerable_despite_safe_hoisted_version():
    """Hoisted lodash is already at the safe version; a nested copy is still vulnerable.
    The remediation must add a global override rather than silently skipping."""
    from output.node import apply_updates

    package_json = {"dependencies": {"some-dep": "^1.0.0"}}
    lockfile = {
        "packages": {
            "node_modules/some-dep": {"version": "1.0.0"},
            "node_modules/lodash": {"version": "4.17.21"},
            "node_modules/some-dep/node_modules/lodash": {"version": "4.17.20"},
        }
    }

    # CVE guidance: lodash must be > 4.17.20; 4.17.21 is the fix.
    criteria = {"lodash": {4: SemVer.parse("4.17.20")}}
    versions_by_package = {"lodash": [SemVer.parse("4.17.20"), SemVer.parse("4.17.21")]}
    package_constraints = {"lodash": ">"}
    package_versions = {"lodash": {SemVer.parse("4.17.20")}}

    _, override_changes, skipped, _block_changes = apply_updates(
        package_json=package_json,
        direct_entries=[],
        criteria=criteria,
        package_versions=package_versions,
        versions_by_package=versions_by_package,
        package_constraints=package_constraints,
        allow_ambiguous_highest_major=True,
        keep_nested_overrides=False,
        lockfile=lockfile,
        skip_block_check=True,
    )

    skip_reasons = [s["reason"] for s in skipped]
    assert "installed version already satisfies guidance criteria" not in skip_reasons, (
        "Should not skip when a vulnerable nested copy still exists"
    )
    assert package_json.get("overrides", {}).get("lodash") == "4.17.21", (
        "Should add override to force nested copy to safe version"
    )
    assert any(row["package"] == "lodash" for row in override_changes)


def test_node_jfrog_cve_package_becomes_update_criteria(tmp_path, monkeypatch):
    from pipeline import node as node_pipeline

    pkg = {
        "dependencies": {
            "lodash": "4.17.20",
        }
    }
    pkg_path = tmp_path / "package.json"
    pkg_path.write_text(json.dumps(pkg), encoding="utf-8")
    lockfile = {
        "packages": {
            "node_modules/lodash": {"version": "4.17.20"},
        }
    }

    monkeypatch.setattr(
        "parsers.node._load_or_generate_lockfile",
        lambda project_dir, package_json, npm_cmd, timeout: lockfile,
    )
    monkeypatch.setattr(
        "parsers.node.parallel_npm_versions",
        lambda packages, registry, npm_cmd, timeout, workers, show_progress, cwd=".": (
            {"lodash": [SemVer.parse("4.17.20"), SemVer.parse("4.17.21")]},
            [],
        ),
    )

    result = node_pipeline.analyze_node(
        csv_path="",
        pkg_json_path=str(pkg_path),
        log_dir=str(tmp_path),
        columns=None,
        cve_packages={"lodash"},
        skip_block_check=True,
    )

    assert any(row["package"] == "lodash" for row in result["display_changes"])


def test_gradle_jfrog_cve_package_becomes_force_entry(tmp_path, monkeypatch):
    from pipeline import gradle as gradle_pipeline

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies { implementation 'org.example:parent:1.0.0' }", encoding="utf-8")

    dep = SimpleNamespace(
        config="implementation",
        group="org.example",
        artifact="parent",
        version="1.0.0",
        original="implementation 'org.example:parent:1.0.0'",
        match_start=0,
        match_end=0,
    )

    monkeypatch.setattr("parsers.gradle.parse_gradle_deps", lambda text: [dep])
    monkeypatch.setattr(
        "parsers.gradle.parallel_fetch_versions",
        lambda deps, base_url, auth, timeout, workers, show_progress: (
            {
                "org.vuln:lib": [
                    MavenVersion.parse("2.0.0"),
                    MavenVersion.parse("2.0.1"),
                ]
            },
            [],
        ),
    )
    monkeypatch.setattr("parsers.gradle_tree.get_gradle_cmd", lambda project_dir: "gradle")
    monkeypatch.setattr(
        "parsers.gradle_tree.run_gradle_dependencies_with_fallback",
        lambda **kwargs: (
            "+--- org.example:parent:1.0.0\n     \\--- org.vuln:lib:2.0.0\n",
            None,
            {},
        ),
    )

    result = gradle_pipeline.analyze_gradle(
        csv_path="",
        build_file=str(build_file),
        log_dir=str(tmp_path),
        columns=None,
        artifactory_source="https://jfrog.example.com/artifactory",
        artifactory_repo="libs-release",
        cve_packages={"org.vuln:lib"},
        skip_block_check=True,
    )

    assert any(row["package"] == "org.vuln:lib" for row in result["display_changes"])

def test_gradle_jfrog_package_absent_from_build_tree_is_ignored(tmp_path, monkeypatch):
    from pipeline import gradle as gradle_pipeline

    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "dependencies { implementation 'org.example:parent:1.0.0' }",
        encoding="utf-8",
    )

    dep = SimpleNamespace(
        config="implementation",
        group="org.example",
        artifact="parent",
        version="1.0.0",
        original="implementation 'org.example:parent:1.0.0'",
        match_start=0,
        match_end=0,
    )

    fetch_calls = []

    def fake_fetch_versions(deps, base_url, auth, timeout, workers, show_progress):
        fetch_calls.append([f"{d.group}:{d.artifact}" for d in deps])
        return {
            "org.example:parent": [
                MavenVersion.parse("1.0.0"),
                MavenVersion.parse("1.0.1"),
            ],
        }, []

    monkeypatch.setattr("parsers.gradle.parse_gradle_deps", lambda text: [dep])
    monkeypatch.setattr("parsers.gradle.parallel_fetch_versions", fake_fetch_versions)
    monkeypatch.setattr("parsers.gradle_tree.get_gradle_cmd", lambda project_dir: "gradle")
    monkeypatch.setattr(
        "parsers.gradle_tree.run_gradle_dependencies_with_fallback",
        lambda **kwargs: (
            "+--- org.example:parent:1.0.0\n",
            None,
            {},
        ),
    )

    result = gradle_pipeline.analyze_gradle(
        csv_path="",
        build_file=str(build_file),
        log_dir=str(tmp_path),
        columns=None,
        artifactory_source="https://jfrog.example.com/artifactory",
        artifactory_repo="libs-release",
        cve_packages={"org.absent:not-in-this-build"},
        skip_block_check=True,
    )

    assert not any(
        row["package"] == "org.absent:not-in-this-build"
        for row in result["display_changes"]
    )
    assert all(
        "org.absent:not-in-this-build" not in call
        for call in fetch_calls
    )


def test_range_override_not_downgraded_to_plain_pin():
    """An existing override like '>=8.20.1' satisfies guidance for min 8.20.1.
    It must not be replaced with a plain pin '8.20.1'."""
    from output.node import apply_updates

    package_json = {
        "dependencies": {},
        "overrides": {"some-pkg": ">=8.20.1"},
    }
    lockfile = {
        "packages": {
            "node_modules/some-pkg": {"version": "8.20.1"},
        }
    }

    criteria = {"some-pkg": {8: SemVer.parse("8.20.1")}}
    versions_by_package = {"some-pkg": [SemVer.parse("8.20.1")]}
    package_constraints = {"some-pkg": ">"}
    package_versions = {"some-pkg": {SemVer.parse("8.20.1")}}

    _, override_changes, skipped, _block_changes = apply_updates(
        package_json=package_json,
        direct_entries=[],
        criteria=criteria,
        package_versions=package_versions,
        versions_by_package=versions_by_package,
        package_constraints=package_constraints,
        allow_ambiguous_highest_major=True,
        keep_nested_overrides=False,
        lockfile=lockfile,
        skip_block_check=True,
    )

    assert package_json["overrides"]["some-pkg"] == ">=8.20.1", (
        "Range override should not be downgraded to a plain pin"
    )
    assert override_changes == []


def test_transitive_parent_update_tries_older_candidate_when_latest_fails(monkeypatch):
    from output.node import apply_updates
    from parsers.node import DirectEntry

    package_json = {
        "dependencies": {
            "parent-package": "^1.0.0",
        }
    }
    direct_entry = DirectEntry(
        package="parent-package",
        section="dependencies",
        spec="^1.0.0",
        container=package_json["dependencies"],
        key="parent-package",
        path="dependencies.parent-package",
    )
    lockfile = {
        "packages": {
            "node_modules/parent-package": {
                "version": "1.0.0",
                "dependencies": {"vulnerable-child": "2.0.0"},
            },
            "node_modules/parent-package/node_modules/vulnerable-child": {
                "version": "2.0.0"
            },
        }
    }

    attempted_specs = []

    def fake_resolve(
        parent,
        parent_new_spec,
        parent_section,
        transitive,
        package_json,
        npm_cmd,
        timeout,
        cwd,
        registry=None,
    ):
        attempted_specs.append(parent_new_spec)
        if parent_new_spec == "^1.3.0":
            return None
        if parent_new_spec == "^1.2.0":
            return [SemVer.parse("2.0.1")]
        raise AssertionError(f"Unexpected candidate: {parent_new_spec}")

    monkeypatch.setattr(
        "output.node.resolve_transitive_with_parent",
        fake_resolve,
    )

    direct_changes, override_changes, skipped, _block_changes = apply_updates(
        package_json=package_json,
        direct_entries=[direct_entry],
        criteria={"vulnerable-child": {2: SemVer.parse("2.0.0")}},
        package_versions={"vulnerable-child": {SemVer.parse("2.0.0")}},
        versions_by_package={
            "vulnerable-child": [
                SemVer.parse("2.0.0"),
                SemVer.parse("2.0.1"),
            ],
            "parent-package": [
                SemVer.parse("1.0.0"),
                SemVer.parse("1.2.0"),
                SemVer.parse("1.3.0"),
            ],
        },
        package_constraints={"vulnerable-child": ">"},
        allow_ambiguous_highest_major=True,
        keep_nested_overrides=False,
        lockfile=lockfile,
        skip_block_check=True,
    )

    assert attempted_specs == ["^1.3.0", "^1.2.0"]
    assert package_json["dependencies"]["parent-package"] == "^1.2.0"
    assert "vulnerable-child" not in package_json.get("overrides", {})
    assert override_changes == []
    assert not skipped
    assert direct_changes == [
        {
            "package": "parent-package",
            "section": "dependencies",
            "old_spec": "^1.0.0",
            "new_spec": "^1.2.0",
            "minimum_required": "transitive vulnerable-child>2.0.0",
            "selected_version": "1.2.0",
            "path": "dependencies.parent-package",
        }
    ]


def test_gradle_transitive_parent_update_succeeds_on_highest_candidate(
    tmp_path,
    monkeypatch,
):
    """Case 2 tries the single highest-version parent candidate and stops --
    it no longer falls back to older same-major candidates on failure (see
    test_gradle_case2_caps_total_probes_across_multiple_parents: a real batch
    showed 0/275 Case 2 searches ever succeeding regardless of how many
    candidates were tried, at ~40-60s per cold Gradle probe, so trying more
    than the first/highest candidate was pure wasted time). This still
    confirms the common, cheap-and-fast case: the parent bump resolves the
    child on the first try.
    """
    from output.gradle import apply_updates
    from parsers.gradle import GradleDep

    build_file = tmp_path / "build.gradle"
    declaration = "implementation 'org.example:parent:1.0.0'"
    build_file.write_text(
        f"dependencies {{ {declaration} }}",
        encoding="utf-8",
    )
    parent = GradleDep(
        config="implementation",
        group="org.example",
        artifact="parent",
        version="1.0.0",
        original=declaration,
        match_start=15,
        match_end=15 + len(declaration),
    )
    attempted = []

    def fake_resolve(
        parent_key,
        new_parent_version,
        transitive_key,
        project_dir,
        build_file,
        gradle_cmd,
        timeout,
        configuration="runtimeClasspath",
    ):
        attempted.append(new_parent_version)
        if new_parent_version == "1.3.0":
            return MavenVersion.parse("2.0.1")
        raise AssertionError(f"Unexpected parent candidate: {new_parent_version}")

    monkeypatch.setattr(
        "output.gradle.resolve_transitive_with_gradle",
        fake_resolve,
    )

    changes, skipped, forces = apply_updates(
        deps=[parent],
        remediation_by_key={},
        available_by_key={
            "org.example:parent": [
                MavenVersion.parse("1.0.0"),
                MavenVersion.parse("1.2.0"),
                MavenVersion.parse("1.3.0"),
            ],
            "org.vulnerable:child": [
                MavenVersion.parse("2.0.0"),
                MavenVersion.parse("2.0.1"),
            ],
        },
        package_constraints={"org.vulnerable:child": ">"},
        installed={
            "org.example:parent": MavenVersion.parse("1.0.0"),
            "org.vulnerable:child": MavenVersion.parse("2.0.0"),
        },
        parents_of={"org.vulnerable:child": {"org.example:parent"}},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    assert attempted == ["1.3.0"]
    assert skipped == []
    assert forces == []
    assert len(changes) == 1
    assert changes[0]["dependency"] == "org.example:parent"


def test_gradle_transitive_parent_gives_up_after_first_candidate_fails(
    tmp_path,
    monkeypatch,
):
    """Companion to the success case above: when the single highest candidate
    doesn't satisfy the target, Case 2 must fall through to Case 3 (force)
    immediately rather than trying older same-major candidates -- confirmed
    live that additional candidates never succeeded anyway (0/275 in a real
    batch), so trying them was pure wasted time (~40-60s per cold Gradle
    probe).
    """
    from output.gradle import apply_updates
    from parsers.gradle import GradleDep

    build_file = tmp_path / "build.gradle"
    declaration = "implementation 'org.example:parent:1.0.0'"
    build_file.write_text(
        f"dependencies {{ {declaration} }}",
        encoding="utf-8",
    )
    parent = GradleDep(
        config="implementation",
        group="org.example",
        artifact="parent",
        version="1.0.0",
        original=declaration,
        match_start=15,
        match_end=15 + len(declaration),
    )
    attempted = []

    def fake_resolve(
        parent_key,
        new_parent_version,
        transitive_key,
        project_dir,
        build_file,
        gradle_cmd,
        timeout,
        configuration="runtimeClasspath",
    ):
        attempted.append(new_parent_version)
        return None

    monkeypatch.setattr(
        "output.gradle.resolve_transitive_with_gradle",
        fake_resolve,
    )

    changes, skipped, forces = apply_updates(
        deps=[parent],
        remediation_by_key={},
        available_by_key={
            "org.example:parent": [
                MavenVersion.parse("1.0.0"),
                MavenVersion.parse("1.2.0"),
                MavenVersion.parse("1.3.0"),
            ],
            "org.vulnerable:child": [
                MavenVersion.parse("2.0.0"),
                MavenVersion.parse("2.0.1"),
            ],
        },
        package_constraints={"org.vulnerable:child": ">"},
        installed={
            "org.example:parent": MavenVersion.parse("1.0.0"),
            "org.vulnerable:child": MavenVersion.parse("2.0.0"),
        },
        parents_of={"org.vulnerable:child": {"org.example:parent"}},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    assert attempted == ["1.3.0"]
    assert changes == []
    assert forces and forces[0]["dependency"] == "org.vulnerable:child"


def test_gradle_case2_caps_parent_candidates_tried(tmp_path, monkeypatch):
    """Live perf bug: each Case 2 candidate costs a full cold `--no-daemon`
    gradle dependencies subprocess in a fresh temp-directory copy
    (resolve_transitive_with_gradle) -- nothing like an HTTP probe. The
    candidate list here had no cap at all, so a direct, non-criteria parent
    with many same-major releases (matches a real repo: reactor-netty-http is
    a direct, non-criteria dependency parenting 8 io.netty:* packages flagged
    together in one JFrog audit) could spawn dozens of full Gradle
    invocations per remediated child. Must stop trying after the single
    highest candidate (confirmed live: 0/275 real Case 2 searches ever
    succeeded regardless of candidate count, at ~40-60s per probe) and fall
    through to Case 3 (force) instead.
    """
    from output.gradle import apply_updates
    from parsers.gradle import GradleDep

    build_file = tmp_path / "build.gradle"
    declaration = "implementation 'org.example:parent:1.0.0'"
    build_file.write_text(
        f"dependencies {{ {declaration} }}",
        encoding="utf-8",
    )
    parent = GradleDep(
        config="implementation",
        group="org.example",
        artifact="parent",
        version="1.0.0",
        original=declaration,
        match_start=15,
        match_end=15 + len(declaration),
    )
    attempted = []

    def fake_resolve(
        parent_key, new_parent_version, transitive_key, project_dir,
        build_file, gradle_cmd, timeout, configuration="runtimeClasspath",
    ):
        attempted.append(new_parent_version)
        return None  # never satisfies -- forces the loop to exhaust candidates

    monkeypatch.setattr(
        "output.gradle.resolve_transitive_with_gradle", fake_resolve
    )

    # 20 same-major releases above current -- an unbounded loop would try
    # all 20 real cold Gradle subprocesses before giving up.
    many_versions = [MavenVersion.parse(f"1.{i}.0") for i in range(1, 21)]
    changes, skipped, forces = apply_updates(
        deps=[parent],
        remediation_by_key={},
        available_by_key={
            "org.example:parent": [MavenVersion.parse("1.0.0")] + many_versions,
            "org.vulnerable:child": [
                MavenVersion.parse("2.0.0"),
                MavenVersion.parse("2.0.1"),
            ],
        },
        package_constraints={"org.vulnerable:child": ">"},
        installed={
            "org.example:parent": MavenVersion.parse("1.0.0"),
            "org.vulnerable:child": MavenVersion.parse("2.0.0"),
        },
        parents_of={"org.vulnerable:child": {"org.example:parent"}},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    assert len(attempted) == 1
    assert forces and forces[0]["dependency"] == "org.vulnerable:child"


def test_gradle_case2_caps_total_probes_across_multiple_parents(tmp_path, monkeypatch):
    """Live perf bug: a per-parent candidate cap alone wasn't enough -- a
    transitive key with several direct parents (a real batch showed
    jackson-databind pulled in independently by 2-3 unrelated top-level
    dependencies) got a full candidate budget for *each* parent, reaching
    9-12 total cold Gradle subprocess invocations when capped at 5 per
    parent. Confirmed live across a real batch pull: 275 Case 2 searches
    sampled, 0 ever succeeded, ~213 minutes total, individual searches up to
    372s, ~40-60s per probe. The total probe count across every parent for
    one key must be capped to 1 (the single highest candidate overall), not
    per parent.
    """
    from output.gradle import apply_updates
    from parsers.gradle import GradleDep

    build_file = tmp_path / "build.gradle"
    parent_a_decl = "implementation 'org.example:parent-a:1.0.0'"
    parent_b_decl = "implementation 'org.example:parent-b:1.0.0'"
    parent_c_decl = "implementation 'org.example:parent-c:1.0.0'"
    build_file.write_text(
        f"dependencies {{ {parent_a_decl}\n{parent_b_decl}\n{parent_c_decl} }}",
        encoding="utf-8",
    )

    def _dep(name, decl):
        return GradleDep(
            config="implementation", group="org.example", artifact=name,
            version="1.0.0", original=decl, match_start=0, match_end=len(decl),
        )

    parent_a = _dep("parent-a", parent_a_decl)
    parent_b = _dep("parent-b", parent_b_decl)
    parent_c = _dep("parent-c", parent_c_decl)

    attempted = []

    def fake_resolve(
        parent_key, new_parent_version, transitive_key, project_dir,
        build_file, gradle_cmd, timeout, configuration="runtimeClasspath",
    ):
        attempted.append(parent_key)
        return None  # never satisfies -- every parent's whole budget gets used

    monkeypatch.setattr(
        "output.gradle.resolve_transitive_with_gradle", fake_resolve
    )

    # 3 independent direct parents, each with 5+ same-major releases above
    # current -- a per-parent-only cap of 5 would allow up to 15 total probes.
    many_versions = [MavenVersion.parse(f"1.{i}.0") for i in range(1, 8)]
    changes, skipped, forces = apply_updates(
        deps=[parent_a, parent_b, parent_c],
        remediation_by_key={},
        available_by_key={
            "org.example:parent-a": [MavenVersion.parse("1.0.0")] + many_versions,
            "org.example:parent-b": [MavenVersion.parse("1.0.0")] + many_versions,
            "org.example:parent-c": [MavenVersion.parse("1.0.0")] + many_versions,
            "org.vulnerable:child": [
                MavenVersion.parse("2.0.0"),
                MavenVersion.parse("2.0.1"),
            ],
        },
        package_constraints={"org.vulnerable:child": ">"},
        installed={
            "org.example:parent-a": MavenVersion.parse("1.0.0"),
            "org.example:parent-b": MavenVersion.parse("1.0.0"),
            "org.example:parent-c": MavenVersion.parse("1.0.0"),
            "org.vulnerable:child": MavenVersion.parse("2.0.0"),
        },
        parents_of={
            "org.vulnerable:child": {
                "org.example:parent-a",
                "org.example:parent-b",
                "org.example:parent-c",
            }
        },
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    assert len(attempted) == 1
    assert forces and forces[0]["dependency"] == "org.vulnerable:child"


def test_gradle_force_expands_to_version_locked_netty_siblings(tmp_path):
    from output.gradle import apply_updates

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}\n", encoding="utf-8")

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={},
        available_by_key={
            "io.netty:netty-transport-native-epoll": [
                MavenVersion.parse("4.1.132.Final"),
                MavenVersion.parse("4.2.16.Final"),
            ],
            "io.netty:netty-handler": [
                MavenVersion.parse("4.1.132.Final"),
                MavenVersion.parse("4.2.16.Final"),
            ],
            "io.netty:netty-codec": [
                MavenVersion.parse("4.1.132.Final"),
                MavenVersion.parse("4.2.16.Final"),
            ],
        },
        package_constraints={"io.netty:netty-transport-native-epoll": ">"},
        installed={
            "io.netty:netty-transport-native-epoll": MavenVersion.parse("4.1.132.Final"),
            "io.netty:netty-handler": MavenVersion.parse("4.1.132.Final"),
            "io.netty:netty-codec": MavenVersion.parse("4.1.132.Final"),
            "io.netty:netty-buffer": MavenVersion.parse("4.2.16.Final"),
            "org.example:unrelated": MavenVersion.parse("1.0.0"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    assert skipped == []
    assert changes == []

    forced_by_dep = {entry["dependency"]: entry for entry in forces}
    assert forced_by_dep.keys() == {
        "io.netty:netty-transport-native-epoll",
        "io.netty:netty-handler",
        "io.netty:netty-codec",
    }
    for entry in forced_by_dep.values():
        assert entry["new_version"] == "4.2.16.Final"
    # Already at a different version than the changed artifact was — not
    # currently in lockstep, so left alone rather than swept along by guess.
    assert "io.netty:netty-buffer" not in forced_by_dep
    # Different Maven group entirely — must never be touched.
    assert "org.example:unrelated" not in forced_by_dep


def test_gradle_force_does_not_group_unrelated_same_group_artifacts(tmp_path):
    """A shared Maven groupId alone must not imply a version-locked family.

    org.apache.commons bundles several independently-released artifacts
    (commons-lang3, commons-io, commons-collections4, ...) that happen to
    share a groupId but are never meant to move together. The only signal
    used to treat two artifacts as one release train is that they are
    *currently* pinned to the exact same version — here they aren't, so
    bumping one must not drag the other along.
    """
    from output.gradle import apply_updates

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}\n", encoding="utf-8")

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={},
        available_by_key={
            "org.apache.commons:commons-lang3": [
                MavenVersion.parse("3.14.0"),
                MavenVersion.parse("3.18.0"),
            ],
        },
        package_constraints={"org.apache.commons:commons-lang3": ">"},
        installed={
            "org.apache.commons:commons-lang3": MavenVersion.parse("3.14.0"),
            "org.apache.commons:commons-io": MavenVersion.parse("2.15.1"),
            "org.apache.commons:commons-collections4": MavenVersion.parse("4.4.0"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    assert skipped == []
    assert changes == []
    assert {entry["dependency"] for entry in forces} == {
        "org.apache.commons:commons-lang3",
    }


def test_gradle_sibling_force_dropped_when_direct_declaration_already_realigned(
    tmp_path,
):
    """A sibling swept up by _sibling_family_forces can also have its own
    direct declaration in build.gradle -- which _align_competing_pins
    separately realigns to the identical target version. Once every direct
    occurrence carries the correct version, the sibling's force entry pins
    nothing new; it's pure clutter. Observed live: cwih-cnp-mgmt-consent-
    publish-api's org.apache.cxf:cxf-rt-transports-http (sibling of
    cxf-core) ended up forced to 4.2.2 in both buildscript and project
    scope AND had its own strictly() blocks realigned to the identical
    4.2.2 -- three redundant pins for one already-correctly-handled change.
    """
    from output.gradle import apply_updates

    declaration = (
        "implementation(group: 'org.apache.cxf', name: 'cxf-rt-transports-http') {\n"
        "        version { strictly '4.1.3' }\n"
        "    }"
    )
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "dependencies {\n"
        f"    {declaration}\n"
        "}\n",
        encoding="utf-8",
    )

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={},
        available_by_key={
            "org.apache.cxf:cxf-core": [
                MavenVersion.parse("4.1.3"),
                MavenVersion.parse("4.2.2"),
            ],
            "org.apache.cxf:cxf-rt-transports-http": [
                MavenVersion.parse("4.1.3"),
                MavenVersion.parse("4.2.2"),
            ],
        },
        package_constraints={"org.apache.cxf:cxf-core": ">"},
        installed={
            "org.apache.cxf:cxf-core": MavenVersion.parse("4.1.3"),
            "org.apache.cxf:cxf-rt-transports-http": MavenVersion.parse("4.1.3"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    # The direct declaration got realigned...
    realigned = [
        row for row in changes
        if row["dependency"] == "org.apache.cxf:cxf-rt-transports-http"
    ]
    assert len(realigned) == 1
    assert realigned[0]["new_version"] == "4.2.2"

    # ...so the sibling force for the SAME package must not also be emitted.
    forced_keys = {entry["dependency"] for entry in forces}
    assert "org.apache.cxf:cxf-rt-transports-http" not in forced_keys
    assert "org.apache.cxf:cxf-core" in forced_keys


def test_gradle_align_competing_pins_realigns_every_duplicate_occurrence(
    tmp_path,
):
    """Real-world bug distinct from the Case 1 duplicate fix: a package that
    is only realigned via _sibling_family_forces (never a direct CVE target
    itself) can ALSO be declared twice in build.gradle. _align_competing_pins
    re-scans the whole file for such declarations, but used to mutate the
    same "already handled" set it was checking against text content -- so
    after patching the first of two byte-identical declarations, it treated
    the second as already handled purely because the TEXT matched, and left
    it at the old vulnerable version. Observed live: cwih-cnp-mgmt-consent-
    publish-api's org.apache.cxf:cxf-rt-transports-http was declared twice at
    4.1.3; only the first became 4.2.2, the second stayed at 4.1.3 right next
    to it.
    """
    from output.gradle import apply_updates

    declaration = "implementation 'org.apache.cxf:cxf-rt-transports-http:4.1.3'"
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "dependencies {\n"
        f"    {declaration}\n"
        "    implementation 'org.example:filler:1.0.0'\n"
        f"    {declaration}\n"
        "}\n",
        encoding="utf-8",
    )

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={},
        available_by_key={
            "org.apache.cxf:cxf-core": [
                MavenVersion.parse("4.1.3"),
                MavenVersion.parse("4.2.2"),
            ],
            "org.apache.cxf:cxf-rt-transports-http": [
                MavenVersion.parse("4.1.3"),
                MavenVersion.parse("4.2.2"),
            ],
        },
        package_constraints={"org.apache.cxf:cxf-core": ">"},
        installed={
            "org.apache.cxf:cxf-core": MavenVersion.parse("4.1.3"),
            "org.apache.cxf:cxf-rt-transports-http": MavenVersion.parse("4.1.3"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    realigned = [
        row for row in changes
        if row.get("dependency") == "org.apache.cxf:cxf-rt-transports-http"
        and row.get("remediation_guided") == "competing pin realigned"
    ]
    assert len(realigned) == 2
    assert all(row["new_version"] == "4.2.2" for row in realigned)

    from output.gradle import write_gradle_file

    output_path = tmp_path / "build-out.gradle"
    write_gradle_file(
        build_file.read_text(encoding="utf-8"),
        changes,
        forces,
        str(output_path),
        str(build_file),
        in_place=False,
    )
    updated_text = output_path.read_text(encoding="utf-8")
    assert updated_text.count("cxf-rt-transports-http:4.1.3") == 0
    assert (
        updated_text.count("implementation 'org.apache.cxf:cxf-rt-transports-http:4.2.2'")
        == 2
    )


def test_gradle_align_competing_pins_realigns_capabilities_resolution_select():
    """A capabilitiesResolution.withCapability { select('g:a:v') } block --
    used to resolve conflicts between two modules providing the same
    capability, e.g. org.lz4:lz4-java vs at.yawk.lz4:lz4-java -- is
    authoritative for that capability conflict and outranks both a
    version{strictly} constraint and resolutionStrategy.force on the module
    it selects. A stale select() left untouched silently keeps the old
    vulnerable version even after every other pin is realigned. Observed
    live: cwih-cnp-mgmt-consent-publish-api forced at.yawk.lz4:lz4-java to
    1.11.1, but a stale select("at.yawk.lz4:lz4-java:1.10.1") still won real
    Gradle resolution, leaving the CVE unfixed (Partial instead of Success).
    """
    from output.gradle import _align_competing_pins

    build_text = (
        "configurations.configureEach {\n"
        "    resolutionStrategy {\n"
        '        capabilitiesResolution.withCapability("org.lz4:lz4-java") {\n'
        '            select("at.yawk.lz4:lz4-java:1.10.1")\n'
        '            because("Resolve capability conflict")\n'
        "        }\n"
        "    }\n"
        "}\n"
    )

    rows = _align_competing_pins(
        build_text,
        changes=[],
        force_entries=[
            {
                "dependency": "at.yawk.lz4:lz4-java",
                "old_version": "1.10.1",
                "new_version": "1.11.1",
            }
        ],
    )

    realigned = [r for r in rows if r["dependency"] == "at.yawk.lz4:lz4-java"]
    assert len(realigned) == 1
    assert realigned[0]["new_version"] == "1.11.1"
    assert 'select("at.yawk.lz4:lz4-java:1.11.1")' in realigned[0]["replacement"]


def test_gradle_writer_rewrites_shared_each_list_strictly_block_once(tmp_path):
    """Three artifacts realigned via _align_competing_pins share the exact
    same `original` text (the whole ['a','b','c'].each {...} block) since
    parse_gradle_deps can't attribute a distinct text span to each looped
    name. write_gradle_file applies each realignment row's
    original->replacement via a plain text .replace(..., 1); confirms the
    second and third rows' replace calls become harmless no-ops (the shared
    text no longer matches after the first rewrites it) rather than
    corrupting the file or emitting three redundant copies of the block.
    """
    from output.gradle import _align_competing_pins, write_gradle_file

    build_text = (
        "dependencies {\n"
        "    ['netty-codec', 'netty-codec-http', 'netty-handler'].each {\n"
        "        implementation(group: 'io.netty', name: it) {\n"
        "            version { strictly '4.1.132.Final' }\n"
        "        }\n"
        "    }\n"
        "}\n"
    )

    force_entries = [
        {
            "dependency": f"io.netty:{name}",
            "old_version": "4.1.132.Final",
            "new_version": "4.2.16.Final",
        }
        for name in ("netty-codec", "netty-codec-http", "netty-handler")
    ]
    rows = _align_competing_pins(build_text, changes=[], force_entries=force_entries)
    assert len(rows) == 3

    output_path = tmp_path / "updated.gradle"
    write_gradle_file(
        build_text, rows, force_entries, str(output_path), str(output_path), in_place=False,
    )

    updated = output_path.read_text(encoding="utf-8")
    assert updated.count("strictly '4.2.16.Final'") == 1
    assert "4.1.132.Final" not in updated
    assert "['netty-codec', 'netty-codec-http', 'netty-handler']" in updated


def test_gradle_apply_updates_realigns_preexisting_force_pins(tmp_path):
    """Mirrors cwih-cnp-mgmt-cds-workflow: the project carries a stale
    resolutionStrategy force from an earlier manual CVE fix. Left alone it
    outranks both the BOM version property and our own force entry, so the
    flagged sibling moves but the pinned one stays behind — a guaranteed
    mixed-version classpath. The stale force line must be rewritten to the
    remediation target.
    """
    from output.gradle import apply_updates

    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "configurations.all {\n"
        "    resolutionStrategy {\n"
        "        force 'ch.qos.logback:logback-classic:1.5.25'\n"
        "    }\n"
        "}\n"
        "dependencies {}\n",
        encoding="utf-8",
    )

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={},
        available_by_key={
            "ch.qos.logback:logback-core": [
                MavenVersion.parse("1.5.25"),
                MavenVersion.parse("1.5.38"),
            ],
            "ch.qos.logback:logback-classic": [
                MavenVersion.parse("1.5.25"),
                MavenVersion.parse("1.5.38"),
            ],
        },
        package_constraints={"ch.qos.logback:logback-core": ">"},
        installed={
            "ch.qos.logback:logback-core": MavenVersion.parse("1.5.25"),
            "ch.qos.logback:logback-classic": MavenVersion.parse("1.5.25"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    realigned = [
        row for row in changes
        if row.get("remediation_guided") == "competing pin realigned"
    ]
    assert len(realigned) == 1
    assert realigned[0]["dependency"] == "ch.qos.logback:logback-classic"
    assert realigned[0]["original"] == "force 'ch.qos.logback:logback-classic:1.5.25'"
    assert realigned[0]["replacement"] == "force 'ch.qos.logback:logback-classic:1.5.38'"


def test_gradle_apply_updates_realigns_strictly_pinned_family_sibling(tmp_path):
    from output.gradle import apply_updates

    declaration = (
        "implementation('ch.qos.logback:logback-classic') {\n"
        "        version {\n"
        "            strictly '1.5.25'\n"
        "        }\n"
        "    }"
    )
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "dependencies {\n    " + declaration + "\n}\n",
        encoding="utf-8",
    )

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={},
        available_by_key={
            "ch.qos.logback:logback-core": [
                MavenVersion.parse("1.5.25"),
                MavenVersion.parse("1.5.38"),
            ],
            "ch.qos.logback:logback-classic": [
                MavenVersion.parse("1.5.25"),
                MavenVersion.parse("1.5.38"),
            ],
        },
        package_constraints={"ch.qos.logback:logback-core": ">"},
        installed={
            "ch.qos.logback:logback-core": MavenVersion.parse("1.5.25"),
            "ch.qos.logback:logback-classic": MavenVersion.parse("1.5.25"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    realigned = [
        row for row in changes
        if row.get("remediation_guided") == "competing pin realigned"
    ]
    assert len(realigned) == 1
    assert realigned[0]["dependency"] == "ch.qos.logback:logback-classic"
    assert "strictly '1.5.25'" in realigned[0]["original"]
    assert "strictly '1.5.38'" in realigned[0]["replacement"]


def test_gradle_sibling_force_skips_version_that_does_not_exist_for_sibling(
    tmp_path,
):
    """Real-world bug: jackson-databind's remediation target (2.22.1) doesn't
    exist for jackson-annotations, which releases on a coarser cadence (no
    patch digit for some minors) than databind/core. _sibling_family_forces
    used to stamp the trigger's exact version string onto every same-group,
    same-version sibling with no existence check, producing an unresolvable
    dependency (observed live: "jackson-annotations:2.22.1 FAILED" in the
    resolved Gradle tree for ins-cp-mgmt-cds-api) that broke the real build
    without ever implicating the actual cause. It must fall back to the
    highest version that actually exists for that sibling, and skip forcing
    it altogether if nothing usable exists.
    """
    from output.gradle import apply_updates

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}\n", encoding="utf-8")

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={},
        available_by_key={
            "com.fasterxml.jackson.core:jackson-databind": [
                MavenVersion.parse("2.19.0"),
                MavenVersion.parse("2.22.1"),
            ],
            # jackson-annotations never published 2.22.1 -- only a coarser
            # 2.22 exists (modeled here as 2.22.0, the closest usable version
            # below the trigger's exact target).
            "com.fasterxml.jackson.core:jackson-annotations": [
                MavenVersion.parse("2.19.0"),
                MavenVersion.parse("2.22.0"),
            ],
            # jackson-core has no matching release at all in this scenario.
            "com.fasterxml.jackson.core:jackson-core": [
                MavenVersion.parse("2.19.0"),
            ],
        },
        package_constraints={"com.fasterxml.jackson.core:jackson-databind": ">"},
        installed={
            "com.fasterxml.jackson.core:jackson-databind": MavenVersion.parse("2.19.0"),
            "com.fasterxml.jackson.core:jackson-annotations": MavenVersion.parse("2.19.0"),
            "com.fasterxml.jackson.core:jackson-core": MavenVersion.parse("2.19.0"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    forced_by_dep = {entry["dependency"]: entry for entry in forces}
    assert (
        forced_by_dep["com.fasterxml.jackson.core:jackson-annotations"]["new_version"]
        == "2.22.0"
    )
    # Nothing above 2.19.0 exists for jackson-core -- must not be forced to a
    # version that isn't real, and must not be forced at all.
    assert "com.fasterxml.jackson.core:jackson-core" not in forced_by_dep


def test_gradle_force_prefers_stable_release_over_newer_preview(tmp_path):
    from output.gradle import apply_updates

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}", encoding="utf-8")

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={},
        available_by_key={
            "io.micrometer:micrometer-core": [
                MavenVersion.parse("1.15.11"),
                MavenVersion.parse("1.15.12"),
                MavenVersion.parse("1.17.0-M1"),
            ],
        },
        package_constraints={"io.micrometer:micrometer-core": ">"},
        installed={
            "io.micrometer:micrometer-core": MavenVersion.parse("1.15.11"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    assert changes == []
    assert skipped == []
    assert forces == [
        {
            "dependency": "io.micrometer:micrometer-core",
            "old_version": "1.15.11",
            "new_version": "1.15.12",
            "minimum_required": "1.15.12",
        }
    ]


def test_gradle_writer_uses_boot_properties_for_managed_families():
    from output.gradle import write_spring_boot_managed_properties

    build_text = """plugins {
    id 'org.springframework.boot' version '3.5.14'
    id 'io.spring.dependency-management' version '1.1.7'
}

dependencies {
    implementation 'org.springframework:spring-webflux'
    implementation 'io.micrometer:micrometer-core'
    implementation 'io.netty:netty-handler'
}
"""
    forces = [
        {
            "dependency": "org.springframework:spring-webflux",
            "new_version": "6.2.19",
        },
        {
            "dependency": "io.micrometer:micrometer-core",
            "new_version": "1.15.12",
        },
        {
            "dependency": "io.netty:netty-handler",
            "new_version": "4.1.136.Final",
        },
    ]

    updated, remaining = write_spring_boot_managed_properties(
        build_text,
        forces,
    )

    assert remaining == []
    assert "set('spring-framework.version', \"6.2.19\")" in updated
    assert "set('micrometer.version', \"1.15.12\")" in updated
    assert "set('netty.version', \"4.1.136.Final\")" in updated


def test_gradle_writer_replaces_managed_property_line_with_trailing_comment():
    """Real-world bug (confirmed via a coworker's manual post-pipeline diff):
    ext { set('netty.version', "4.1.135.Final") //Fix for CVE-2026-33870 }
    -- the deletion regex anchored "\\s*\\)\\s*$" right after the closing
    paren, so a trailing "//..." comment (not whitespace) meant end-of-line
    never matched and the old line was never removed. A brand-new,
    comment-free `set('netty.version', "...")` line was still appended
    unconditionally, leaving two values for the same property: the stale
    one (with its comment, untouched) sitting right next to the current one.
    """
    from output.gradle import write_spring_boot_managed_properties

    build_text = """plugins {
    id 'org.springframework.boot' version '3.5.14'
    id 'io.spring.dependency-management' version '1.1.7'
}

ext {
    set('netty.version', "4.1.135.Final") //Fix for CVE-2026-33870
}

dependencies {
    implementation 'io.netty:netty-handler'
}
"""
    forces = [
        {
            "dependency": "io.netty:netty-handler",
            "new_version": "4.2.16.Final",
        },
    ]

    updated, remaining = write_spring_boot_managed_properties(
        build_text,
        forces,
    )

    assert remaining == []
    assert updated.count("netty.version") == 1
    assert "4.1.135.Final" not in updated
    assert "set('netty.version', \"4.2.16.Final\")" in updated


def test_gradle_writer_does_not_treat_spring_data_module_as_bom_version():
    from output.gradle import write_spring_boot_managed_properties

    build_text = """plugins {
    id 'org.springframework.boot' version '3.5.14'
    id 'io.spring.dependency-management' version '1.1.7'
}
"""
    force = {
        "dependency": "org.springframework.data:spring-data-mongodb",
        "new_version": "4.5.13",
    }

    updated, remaining = write_spring_boot_managed_properties(
        build_text,
        [force],
    )

    assert updated == build_text
    assert remaining == [force]
    assert "spring-data-bom.version" not in updated


def test_gradle_writer_rewrites_spring_boot_plugin_version_instead_of_forcing(tmp_path):
    """Live bug: forcing org.springframework.boot:spring-boot-starter-* from
    3.5.13 to 3.5.16 via resolutionStrategy.force left the resolved
    dependency tree — and the CVE it targeted — unchanged at 3.5.13. The
    platform's own version comes from the plugin declaration via the
    io.spring.dependency-management BOM import, not from force. The plugin
    version itself must be rewritten for the fix to actually take effect.
    """
    from output.gradle import write_gradle_file

    build_text = """plugins {
    id 'org.springframework.boot' version '3.5.13'
    id 'io.spring.dependency-management' version '1.1.7'
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
}
"""
    output_path = tmp_path / "updated.gradle"
    force_entries = [
        {
            "dependency": "org.springframework.boot:spring-boot",
            "old_version": "3.5.13",
            "new_version": "3.5.16",
            "minimum_required": "3.5.16",
        },
        {
            "dependency": "org.springframework.boot:spring-boot-starter-web",
            "old_version": "3.5.13",
            "new_version": "3.5.16",
            "minimum_required": "3.5.16",
        },
    ]

    write_gradle_file(
        build_text,
        changes=[],
        force_entries=force_entries,
        output_path=str(output_path),
        source_path=str(output_path),
        in_place=False,
    )

    updated = output_path.read_text(encoding="utf-8")

    assert "id 'org.springframework.boot' version '3.5.16'" in updated
    assert "id 'io.spring.dependency-management' version '1.1.7'" in updated
    assert "org.springframework.boot:spring-boot:3.5.16" not in updated
    assert "force" not in updated.lower()


def test_gradle_writer_plugin_version_falls_back_to_force_when_declaration_unrecognized(tmp_path):
    """Version pinned via a version catalog (no literal version string next
    to the plugin id) — the rewrite regex can't find anything to replace, so
    this must fall back to leaving the force entries untouched rather than
    silently dropping the fix attempt.
    """
    from output.gradle import write_spring_boot_plugin_version

    build_text = """plugins {
    id 'org.springframework.boot'
    id 'io.spring.dependency-management' version '1.1.7'
}
"""
    force = {
        "dependency": "org.springframework.boot:spring-boot",
        "new_version": "3.5.16",
    }

    updated, remaining = write_spring_boot_plugin_version(build_text, [force])

    assert updated == build_text
    assert remaining == [force]


def test_gradle_writer_substitutes_spring_data_managed_modules(tmp_path):
    from output.gradle import write_gradle_file

    build_text = """plugins {
    id 'org.springframework.boot' version '3.5.14'
    id 'io.spring.dependency-management' version '1.1.7'
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-data-mongodb'
}
"""
    output_path = tmp_path / "updated.gradle"
    force_entries = [
        {
            "dependency": "org.springframework.data:spring-data-commons",
            "old_version": "3.5.11",
            "new_version": "3.5.13",
            "minimum_required": "3.5.13",
        },
        {
            "dependency": "org.springframework.data:spring-data-mongodb",
            "old_version": "4.5.11",
            "new_version": "4.5.13",
            "minimum_required": "4.5.13",
        },
    ]

    write_gradle_file(
        build_text,
        changes=[],
        force_entries=force_entries,
        output_path=str(output_path),
        source_path=str(output_path),
        in_place=False,
    )

    updated = output_path.read_text(encoding="utf-8")

    assert (
        "force 'org.springframework.data:spring-data-commons:3.5.13'"
        in updated
    )
    assert (
        "force 'org.springframework.data:spring-data-mongodb:4.5.13'"
        in updated
    )
    assert (
        "substitute module('org.springframework.data:spring-data-commons') "
        "using module('org.springframework.data:spring-data-commons:3.5.13')"
        in updated
    )
    assert (
        "substitute module('org.springframework.data:spring-data-mongodb') "
        "using module('org.springframework.data:spring-data-mongodb:4.5.13')"
        in updated
    )


def test_gradle_writer_does_not_substitute_ordinary_force(tmp_path):
    from output.gradle import write_gradle_file

    build_text = "dependencies {}\n"
    output_path = tmp_path / "updated.gradle"

    write_gradle_file(
        build_text,
        changes=[],
        force_entries=[
            {
                "dependency": "org.example:ordinary",
                "old_version": "1.0.0",
                "new_version": "1.0.1",
                "minimum_required": "1.0.1",
            }
        ],
        output_path=str(output_path),
        source_path=str(output_path),
        in_place=False,
    )

    updated = output_path.read_text(encoding="utf-8")

    assert "force 'org.example:ordinary:1.0.1'" in updated
    assert "substitute module('org.example:ordinary')" not in updated


def test_gradle_writer_forces_buildscript_scope_even_without_explicit_buildscript_deps(
    tmp_path,
):
    """Declared plugins (Spring Boot, Sonarqube, ...) resolve their own
    transitive dependencies through buildscript's classpath configuration
    even when buildscript{} declares no explicit dependencies{} of its own --
    skipping the buildscript-scope force block in that case let a plugin's
    transitively-resolved jackson-databind fall through unforced and 403
    against Xray's download policy (confirmed live: cwih-cnp-mgmt-consent-
    publish-api regressed from Success to a full revert this exact way).
    """
    from output.gradle import write_gradle_file

    build_text = (
        "buildscript {\n"
        "    repositories { mavenLocal() }\n"
        "}\n"
        "dependencies {}\n"
    )
    output_path = tmp_path / "updated.gradle"

    write_gradle_file(
        build_text,
        changes=[],
        force_entries=[
            {
                "dependency": "org.example:ordinary",
                "old_version": "1.0.0",
                "new_version": "1.0.1",
                "minimum_required": "1.0.1",
            }
        ],
        output_path=str(output_path),
        source_path=str(output_path),
        in_place=False,
    )

    updated = output_path.read_text(encoding="utf-8")
    assert updated.count("configurations.all") == 2
    assert "force 'org.example:ordinary:1.0.1'" in updated


def test_gradle_writer_skips_buildscript_force_block_when_no_buildscript_block(
    tmp_path,
):
    """With no buildscript{} block at all, there is no classpath
    configuration to force into -- only the project-scope block is written.
    """
    from output.gradle import write_gradle_file

    build_text = "dependencies {}\n"
    output_path = tmp_path / "updated.gradle"

    write_gradle_file(
        build_text,
        changes=[],
        force_entries=[
            {
                "dependency": "org.example:ordinary",
                "old_version": "1.0.0",
                "new_version": "1.0.1",
                "minimum_required": "1.0.1",
            }
        ],
        output_path=str(output_path),
        source_path=str(output_path),
        in_place=False,
    )

    updated = output_path.read_text(encoding="utf-8")
    assert updated.count("configurations.all") == 1
    assert "force 'org.example:ordinary:1.0.1'" in updated


def test_gradle_writer_keeps_buildscript_force_block_when_buildscript_has_deps(
    tmp_path,
):
    from output.gradle import write_gradle_file

    build_text = (
        "buildscript {\n"
        "    dependencies { classpath 'org.example:plugin:1.0.0' }\n"
        "}\n"
        "dependencies {}\n"
    )
    output_path = tmp_path / "updated.gradle"

    write_gradle_file(
        build_text,
        changes=[],
        force_entries=[
            {
                "dependency": "org.example:ordinary",
                "old_version": "1.0.0",
                "new_version": "1.0.1",
                "minimum_required": "1.0.1",
            }
        ],
        output_path=str(output_path),
        source_path=str(output_path),
        in_place=False,
    )

    updated = output_path.read_text(encoding="utf-8")
    assert updated.count("configurations.all") == 2


def test_gradle_writer_merges_repeated_force_calls_into_one_block(tmp_path):
    """Real-world bug: a single pipeline run can call write_resolution_forces
    more than once (a pre-build check forces one blocked artifact, the main
    CVE write forces everything else) -- each call used to insert a brand
    new configurations.all block, so one repo could end up with several
    near-identical blocks (confirmed live: 4 blocks from 2 calls on the same
    file, none of which existed in the original build.gradle). Repeated
    calls must extend the block already written this run instead.
    """
    from output.gradle import write_resolution_forces

    build_text = "dependencies {}\n"

    once = write_resolution_forces(
        build_text,
        [{"dependency": "com.fasterxml.jackson.core:jackson-databind", "new_version": "2.21.5"}],
    )
    twice = write_resolution_forces(
        once,
        [{"dependency": "org.apache.cxf:cxf-core", "new_version": "4.2.2"}],
    )

    assert twice.count("configurations.all") == 1
    assert "force 'com.fasterxml.jackson.core:jackson-databind:2.21.5'" in twice
    assert "force 'org.apache.cxf:cxf-core:4.2.2'" in twice


def test_gradle_writer_merges_repeated_substitution_calls_into_one_block(tmp_path):
    from output.gradle import write_dependency_substitutions

    build_text = "dependencies {}\n"

    once = write_dependency_substitutions(
        build_text,
        [{"dependency": "org.springframework.data:spring-data-mongodb", "new_version": "4.5.13"}],
    )
    twice = write_dependency_substitutions(
        once,
        [{"dependency": "org.springframework.data:spring-data-commons", "new_version": "3.5.13"}],
    )

    assert twice.count("resolutionStrategy.dependencySubstitution") == 1
    assert "substitute module('org.springframework.data:spring-data-mongodb') using module('org.springframework.data:spring-data-mongodb:4.5.13')" in twice
    assert "substitute module('org.springframework.data:spring-data-commons') using module('org.springframework.data:spring-data-commons:3.5.13')" in twice


def test_gradle_writer_force_block_is_idempotent_on_repeated_full_write(tmp_path):
    """Writing the same force entries through write_gradle_file twice in a
    row must produce byte-identical output -- the direct check that repeated
    processing of the same repo doesn't keep growing the file.
    """
    from output.gradle import write_gradle_file

    build_text = "dependencies {}\n"
    force_entries = [
        {
            "dependency": "org.example:ordinary",
            "old_version": "1.0.0",
            "new_version": "1.0.1",
            "minimum_required": "1.0.1",
        }
    ]

    first_path = tmp_path / "first.gradle"
    write_gradle_file(
        build_text, [], force_entries, str(first_path), str(first_path), in_place=False
    )
    first_text = first_path.read_text(encoding="utf-8")

    second_path = tmp_path / "second.gradle"
    write_gradle_file(
        first_text, [], force_entries, str(second_path), str(second_path), in_place=False
    )
    second_text = second_path.read_text(encoding="utf-8")

    assert second_text.count("configurations.all") == 1
    assert second_text.count("force 'org.example:ordinary:1.0.1'") == 1


def test_gradle_apply_updates_checks_accessibility_before_forcing_transitive(tmp_path, monkeypatch):
    """Live bug: a transitive dependency's force entry was written straight
    from JFrog's CVE-remediation target version with no accessibility check
    at all. Case 1 (direct deps) already probed accessibility, but Case 3
    (the force fallback for transitives with no trackable direct parent) did
    not -- a blocked target was only discovered reactively, after an
    expensive full Gradle build already ran and hit a 403. Must probe
    accessibility up front and force an already-known-accessible substitute
    instead of blindly forcing the blocked CVE-minimum version.
    """
    from output.gradle import apply_updates

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}\n", encoding="utf-8")

    checked_starts = []

    def fake_find_accessible_version(
        group, artifact, start, available, base_url, auth, timeout,
        xray_host=None, repo_urls=None, log_dir=None,
    ):
        checked_starts.append(str(start))
        # The CVE-minimum (2.22.1) is blocked; only 2.22.3 is reachable.
        return "2.22.3"

    monkeypatch.setattr(
        "output.gradle.find_accessible_version", fake_find_accessible_version
    )

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={
            "com.fasterxml.jackson.core:jackson-databind": {
                MavenVersion.parse("2.22.1")
            }
        },
        available_by_key={
            "com.fasterxml.jackson.core:jackson-databind": [
                MavenVersion.parse("2.21.2"),
                MavenVersion.parse("2.22.1"),
                MavenVersion.parse("2.22.3"),
            ],
        },
        package_constraints={
            "com.fasterxml.jackson.core:jackson-databind": ">="
        },
        installed={
            "com.fasterxml.jackson.core:jackson-databind": MavenVersion.parse(
                "2.21.2"
            ),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=False,
        show_progress=False,
    )

    assert checked_starts == ["2.22.1"]
    assert skipped == []
    assert changes == []
    assert len(forces) == 1
    assert forces[0]["dependency"] == "com.fasterxml.jackson.core:jackson-databind"
    assert forces[0]["new_version"] == "2.22.3"


def test_gradle_apply_updates_skips_transitive_when_no_accessible_version(
    tmp_path, monkeypatch
):
    """When no version >= the CVE target is reachable at all, skip and report
    it rather than force a version already known to be blocked -- matches
    Case 1's existing behavior for direct dependencies.
    """
    from output.gradle import apply_updates

    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}\n", encoding="utf-8")

    monkeypatch.setattr(
        "output.gradle.find_accessible_version", lambda *a, **k: None
    )

    changes, skipped, forces = apply_updates(
        deps=[],
        remediation_by_key={
            "com.fasterxml.jackson.core:jackson-databind": {
                MavenVersion.parse("2.22.1")
            }
        },
        available_by_key={
            "com.fasterxml.jackson.core:jackson-databind": [
                MavenVersion.parse("2.21.2"),
                MavenVersion.parse("2.22.1"),
            ],
        },
        package_constraints={
            "com.fasterxml.jackson.core:jackson-databind": ">="
        },
        installed={
            "com.fasterxml.jackson.core:jackson-databind": MavenVersion.parse(
                "2.21.2"
            ),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=False,
        show_progress=False,
    )

    assert forces == []
    assert changes == []
    assert len(skipped) == 1
    assert skipped[0]["dependency"] == "com.fasterxml.jackson.core:jackson-databind"


def test_gradle_apply_updates_patches_every_occurrence_of_duplicated_declaration(
    tmp_path,
):
    """Real-world bug: a build.gradle can declare the same group:artifact
    twice with byte-identical strict-version blocks (copy/paste in two
    dependency sections). direct_by_key collapses duplicates to a single
    representative GradleDep, so Case 1 must consult every parsed occurrence
    -- otherwise only the first textual occurrence gets patched and the
    second stays at the vulnerable version even though the pipeline reports
    the package as fixed (observed live: cwih-cnp-mgmt-consent-publish-api's
    io.netty:netty-codec-compression stayed "Partial" for exactly this
    reason).
    """
    from output.gradle import apply_updates
    from parsers.gradle import parse_gradle_deps

    block = (
        "implementation(group: 'io.netty', name: 'netty-codec-compression') {\n"
        "    version { strictly '4.2.5.Final' }\n"
        "}\n"
    )
    build_text = (
        "dependencies {\n"
        f"    {block}\n"
        "    implementation 'org.example:filler:1.0.0'\n"
        f"    {block}\n"
        "}\n"
    )
    build_file = tmp_path / "build.gradle"
    build_file.write_text(build_text, encoding="utf-8")

    deps = parse_gradle_deps(build_text)
    netty_deps = [d for d in deps if d.artifact == "netty-codec-compression"]
    assert len(netty_deps) == 2, "test setup must produce two parsed occurrences"

    changes, skipped, forces = apply_updates(
        deps=deps,
        remediation_by_key={
            "io.netty:netty-codec-compression": {MavenVersion.parse("4.2.16.Final")}
        },
        available_by_key={
            "io.netty:netty-codec-compression": [
                MavenVersion.parse("4.2.5.Final"),
                MavenVersion.parse("4.2.16.Final"),
            ],
        },
        package_constraints={"io.netty:netty-codec-compression": ">="},
        installed={
            "io.netty:netty-codec-compression": MavenVersion.parse("4.2.5.Final"),
        },
        parents_of={},
        build_file=str(build_file),
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
        gradle_cmd="gradle",
        timeout=30,
        skip_block_check=True,
        show_progress=False,
    )

    assert forces == []
    assert skipped == []
    assert len(changes) == 2
    assert all(c["dependency"] == "io.netty:netty-codec-compression" for c in changes)
    assert all(c["new_version"] == "4.2.16.Final" for c in changes)

    from output.gradle import write_gradle_file

    output_path = tmp_path / "build-out.gradle"
    write_gradle_file(
        build_text, changes, forces, str(output_path), str(build_file), in_place=False
    )
    updated_text = output_path.read_text(encoding="utf-8")
    assert updated_text.count("4.2.5.Final") == 0
    assert updated_text.count("4.2.16.Final") == 2
