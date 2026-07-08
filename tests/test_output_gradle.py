import os
from pathlib import Path
from unittest.mock import patch

from output.gradle import apply_updates, write_gradle_file
from parsers.gradle import GradleDep
from shared.maven_version import MavenVersion

BUILD_TEXT = """dependencies {
    implementation 'org.springframework:spring-core:5.3.10'
    api 'com.google.guava:guava:30.0-jre'
}"""


def make_change(
    old_version,
    new_version,
    artifact="spring-core",
    group="org.springframework",
    config="implementation",
):
    original = f"{config} '{group}:{artifact}:{old_version}'"
    replacement = f"{config} '{group}:{artifact}:{new_version}'"
    return {
        "dependency": f"{group}:{artifact}",
        "config": config,
        "old_version": old_version,
        "new_version": new_version,
        "ado_guided": "yes",
        "original": original,
        "replacement": replacement,
    }


class TestWriteGradleFileInPlaceFalse:
    def test_writes_to_output_path(self, tmp_path):
        output_path = str(tmp_path / "build.updated.gradle")
        source_path = str(tmp_path / "build.gradle")
        changes = [make_change("5.3.10", "5.3.27")]
        write_gradle_file(BUILD_TEXT, changes, [], output_path, source_path, in_place=False)
        assert os.path.exists(output_path)

    def test_applied_version_change(self, tmp_path):
        output_path = str(tmp_path / "out.gradle")
        source_path = str(tmp_path / "src.gradle")
        changes = [make_change("5.3.10", "5.3.27")]
        write_gradle_file(BUILD_TEXT, changes, [], output_path, source_path, in_place=False)
        content = Path(output_path).read_text()
        assert "5.3.27" in content
        assert "5.3.10" not in content

    def test_multiple_changes_applied(self, tmp_path):
        output_path = str(tmp_path / "out.gradle")
        source_path = str(tmp_path / "src.gradle")
        changes = [
            make_change("5.3.10", "5.3.27", "spring-core", "org.springframework"),
            make_change("30.0-jre", "31.1-jre", "guava", "com.google.guava", config="api"),
        ]
        write_gradle_file(BUILD_TEXT, changes, [], output_path, source_path, in_place=False)
        content = Path(output_path).read_text()
        assert "5.3.27" in content
        assert "31.1-jre" in content

    def test_no_changes_preserves_content(self, tmp_path):
        output_path = str(tmp_path / "out.gradle")
        source_path = str(tmp_path / "src.gradle")
        write_gradle_file(BUILD_TEXT, [], [], output_path, source_path, in_place=False)
        content = Path(output_path).read_text()
        assert content == BUILD_TEXT

    def test_no_backup_created(self, tmp_path):
        output_path = str(tmp_path / "out.gradle")
        source_path = str(tmp_path / "src.gradle")
        write_gradle_file(BUILD_TEXT, [], [], output_path, source_path, in_place=False)
        assert not os.path.exists(source_path + ".bak")


class TestWriteGradleFileInPlace:
    def test_writes_to_source_path(self, tmp_path):
        source_path = str(tmp_path / "build.gradle")
        Path(source_path).write_text(BUILD_TEXT)
        changes = [make_change("5.3.10", "5.3.27")]
        write_gradle_file(BUILD_TEXT, changes, [], source_path, source_path, in_place=True)
        content = Path(source_path).read_text()
        assert "5.3.27" in content

    def test_creates_backup(self, tmp_path):
        source_path = str(tmp_path / "build.gradle")
        Path(source_path).write_text(BUILD_TEXT)
        changes = [make_change("5.3.10", "5.3.27")]
        write_gradle_file(BUILD_TEXT, changes, [], source_path, source_path, in_place=True)
        assert os.path.exists(source_path + ".bak")

    def test_backup_contains_original(self, tmp_path):
        source_path = str(tmp_path / "build.gradle")
        Path(source_path).write_text(BUILD_TEXT)
        changes = [make_change("5.3.10", "5.3.27")]
        write_gradle_file(BUILD_TEXT, changes, [], source_path, source_path, in_place=True)
        backup_content = Path(source_path + ".bak").read_text()
        assert "5.3.10" in backup_content

    def test_existing_backup_not_overwritten(self, tmp_path):
        source_path = str(tmp_path / "build.gradle")
        bak_path = source_path + ".bak"
        Path(source_path).write_text(BUILD_TEXT)
        Path(bak_path).write_text("ORIGINAL BACKUP")
        changes = [make_change("5.3.10", "5.3.27")]
        write_gradle_file(BUILD_TEXT, changes, [], source_path, source_path, in_place=True)
        assert Path(bak_path).read_text() == "ORIGINAL BACKUP"


# ---------------------------------------------------------------------------
# apply_updates
# ---------------------------------------------------------------------------


def _dep(group, artifact, version, config="implementation"):
    original = f"{config} '{group}:{artifact}:{version}'"
    return GradleDep(
        config=config,
        group=group,
        artifact=artifact,
        version=version,
        original=original,
        match_start=0,
        match_end=len(original),
    )


def _mv(*vs):
    return {MavenVersion.parse(v) for v in vs}


def _mvlist(*vs):
    return [MavenVersion.parse(v) for v in vs]


BASE = "https://artifactory.example.com/repo"
COMMON_KWARGS = dict(
    installed={},
    parents_of={},
    build_file="",
    base_url=BASE,
    auth=None,
    gradle_cmd="gradle",
    timeout=10,
    skip_block_check=True,
    show_progress=False,
)


class TestApplyUpdatesSkipPaths:
    def test_unparseable_version_skipped(self):
        dep = _dep("com.example", "mylib", "not-a-version")
        ado = {"com.example:mylib": _mv("1.0.0")}
        changes, skipped, forces = apply_updates([dep], ado, {}, {}, **COMMON_KWARGS)
        assert changes == [] and forces == []
        assert any("unparseable" in r["reason"] for r in skipped)

    def test_already_meets_ado_target_skipped(self):
        dep = _dep("org.springframework", "spring-core", "5.3.27")
        ado = {"org.springframework:spring-core": _mv("5.3.10")}
        avail = {"org.springframework:spring-core": _mvlist("5.3.10", "5.3.27")}
        changes, skipped, forces = apply_updates([dep], ado, avail, {}, **COMMON_KWARGS)
        assert changes == [] and forces == []
        assert any("already meets" in r["reason"] for r in skipped)

    def test_no_ado_versions_for_major_uses_same_major_update(self):
        dep = _dep("org.springframework", "spring-core", "5.3.10")
        ado = {"org.springframework:spring-core": _mv("6.0.0")}  # major 6, dep is 5.x
        avail = {"org.springframework:spring-core": _mvlist("5.3.10", "5.3.27")}
        changes, skipped, forces = apply_updates([dep], ado, avail, {}, **COMMON_KWARGS)
        assert skipped == [] and forces == []
        assert changes[0]["dependency"] == "org.springframework:spring-core"
        assert changes[0]["new_version"] == "5.3.27"


class TestApplyUpdatesChangePaths:
    def test_ado_guided_change_recorded(self):
        dep = _dep("org.springframework", "spring-core", "5.3.10")
        ado = {"org.springframework:spring-core": _mv("5.3.27")}
        avail = {"org.springframework:spring-core": _mvlist("5.3.10", "5.3.27")}
        changes, _skipped, _forces = apply_updates([dep], ado, avail, {}, **COMMON_KWARGS)
        assert len(changes) == 1
        assert changes[0]["old_version"] == "5.3.10"
        assert changes[0]["new_version"] == "5.3.27"
        assert changes[0]["ado_guided"] == "yes"

    def test_replacement_string_updated(self):
        dep = _dep("org.springframework", "spring-core", "5.3.10")
        ado = {"org.springframework:spring-core": _mv("5.3.27")}
        avail = {"org.springframework:spring-core": _mvlist("5.3.10", "5.3.27")}
        changes, _, _f = apply_updates([dep], ado, avail, {}, **COMMON_KWARGS)
        assert "5.3.27" in changes[0]["replacement"]
        assert "5.3.10" not in changes[0]["replacement"]

    def test_artifact_key_lookup_also_works(self):
        dep = _dep("org.springframework", "spring-core", "5.3.10")
        ado = {"spring-core": _mv("5.3.27")}  # keyed by artifact only
        avail = {"org.springframework:spring-core": _mvlist("5.3.10", "5.3.27")}
        changes, _, _f = apply_updates([dep], ado, avail, {}, **COMMON_KWARGS)
        assert len(changes) == 1

    def test_no_accessible_version_skipped(self):
        dep = _dep("org.springframework", "spring-core", "5.3.10")
        ado = {"org.springframework:spring-core": _mv("5.3.27")}
        avail = {"org.springframework:spring-core": _mvlist("5.3.27")}
        with patch("output.gradle.find_accessible_version", return_value=None):
            kwargs = dict(
                installed={},
                parents_of={},
                build_file="",
                base_url=BASE,
                auth=None,
                gradle_cmd="gradle",
                timeout=10,
                skip_block_check=False,
                show_progress=False,
            )
            changes, skipped, forces = apply_updates([dep], ado, avail, {}, **kwargs)
        assert changes == [] and forces == []
        assert any("no accessible" in r["reason"] for r in skipped)


def test_gradle_processes_claude_identified_package_without_ado_versions(tmp_path, monkeypatch):
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "dependencies {\n    implementation 'org.springframework:spring-webflux:6.2.17'\n}\n"
    )

    dep = _dep("org.springframework", "spring-webflux", "6.2.17")
    available = {
        "org.springframework:spring-webflux": _mvlist("6.2.17", "6.2.18", "6.2.19"),
    }

    monkeypatch.setattr("output.gradle.find_accessible_version", lambda *args, **kwargs: "6.2.19")

    changes, skipped, forces = apply_updates(
        [dep],
        {},
        available,
        {"org.springframework:spring-webflux": ">="},
        {"org.springframework:spring-webflux": MavenVersion.parse("6.2.17")},
        {},
        str(build_file),
        "https://repo.example.com",
        None,
        "gradle",
        30,
        False,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.springframework:spring-webflux"
    assert changes[0]["old_version"] == "6.2.17"
    assert changes[0]["new_version"] == "6.2.19"
    assert changes[0]["replacement"] == "implementation 'org.springframework:spring-webflux:6.2.19'"
    write_gradle_file(
        build_file.read_text(),
        changes,
        forces,
        str(build_file),
        str(build_file),
        True,
    )
    assert "org.springframework:spring-webflux:6.2.19" in build_file.read_text()


def test_apply_updates_updates_existing_strict_dependency_block(tmp_path):
    build_file = tmp_path / "build.gradle"
    build_text = """
dependencies {
    implementation(group: 'io.netty', name: 'netty-codec') {
        version {
            strictly '4.1.132.Final'
        }
    }
}
"""
    build_file.write_text(build_text)

    from parsers.gradle import parse_gradle_deps

    deps = parse_gradle_deps(build_text)
    avail = {"io.netty:netty-codec": _mvlist("4.1.132.Final", "4.1.135.Final")}

    changes, skipped, forces = apply_updates(
        deps,
        {"io.netty:netty-codec": _mv("4.1.133.Final")},
        avail,
        {},
        {"io.netty:netty-codec": MavenVersion.parse("4.1.132.Final")},
        {},
        str(build_file),
        "https://repo.example.com",
        None,
        "gradle",
        30,
        True,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "io.netty:netty-codec"
    assert changes[0]["old_version"] == "4.1.132.Final"
    assert changes[0]["new_version"] == "4.1.135.Final"
    assert "strictly '4.1.135.Final'" in changes[0]["replacement"]


def test_apply_updates_prefers_spring_framework_property_for_transitive_modules(tmp_path):
    build_file = tmp_path / "build.gradle"
    build_text = """
ext {
    set('spring-framework.version', "6.2.17")
}
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-webflux'
}
"""
    build_file.write_text(build_text)

    changes, skipped, forces = apply_updates(
        [],
        {},
        {"org.springframework:spring-web": _mvlist("6.2.17", "6.2.19")},
        {"org.springframework:spring-web": ">="},
        {"org.springframework:spring-web": MavenVersion.parse("6.2.17")},
        {
            "org.springframework:spring-web": {
                "org.springframework.boot:spring-boot-starter-webflux"
            }
        },
        str(build_file),
        "https://repo.example.com",
        None,
        "gradle",
        30,
        True,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.springframework:spring-framework.version"
    assert changes[0]["old_version"] == "6.2.17"
    assert changes[0]["new_version"] == "6.2.19"
    assert changes[0]["replacement"] == "set('spring-framework.version', \"6.2.19\")"


def test_apply_updates_reports_version_managed_direct_dependency_not_missing(tmp_path):
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "dependencies {\n"
        "    implementation 'org.springframework.boot:spring-boot-starter-webflux'\n"
        "}\n"
    )

    changes, skipped, forces = apply_updates(
        [],
        {"org.springframework.boot:spring-boot-starter-webflux": _mv("3.5.16")},
        {"org.springframework.boot:spring-boot-starter-webflux": _mvlist("3.5.15", "3.5.16")},
        {},
        {"org.springframework.boot:spring-boot-starter-webflux": MavenVersion.parse("3.5.15")},
        {},
        str(build_file),
        "https://repo.example.com",
        None,
        "gradle",
        30,
        True,
        False,
    )

    assert changes == []
    assert forces == []
    assert skipped == [
        {
            "dependency": "org.springframework.boot:spring-boot-starter-webflux",
            "reason": "direct dependency is version-managed; no inline version to update",
            "current": "3.5.15",
            "target": "3.5.16",
        }
    ]


def test_apply_updates_resolves_artifact_only_version_managed_direct_dependency(tmp_path):
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        "dependencies {\n"
        "    implementation 'org.springframework.boot:spring-boot-starter-webflux'\n"
        "}\n"
    )

    changes, skipped, forces = apply_updates(
        [],
        {"spring-boot-starter-webflux": _mv("3.5.16")},
        {"org.springframework.boot:spring-boot-starter-webflux": _mvlist("3.5.15", "3.5.16")},
        {},
        {"org.springframework.boot:spring-boot-starter-webflux": MavenVersion.parse("3.5.15")},
        {},
        str(build_file),
        "https://repo.example.com",
        None,
        "gradle",
        30,
        True,
        False,
    )

    assert changes == []
    assert forces == []
    assert skipped[0]["dependency"] == "org.springframework.boot:spring-boot-starter-webflux"
    assert (
        skipped[0]["reason"] == "direct dependency is version-managed; no inline version to update"
    )
