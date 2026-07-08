from dataclasses import dataclass

import output.gradle as out_gradle
from shared.maven_version import MavenVersion


@dataclass
class Dep:
    group: str
    artifact: str
    version: str
    config: str = "implementation"
    original: str = ""

    def __post_init__(self):
        if not self.original:
            self.original = f"{self.config} '{self.group}:{self.artifact}:{self.version}'"


def mv(v):
    return MavenVersion.parse(v)


def test_apply_updates_direct_success_skip_block_check():
    dep = Dep("org.example", "lib", "1.0.0")
    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.example:lib": {mv("1.0.1")}},
        {"org.example:lib": [mv("1.0.1"), mv("1.0.2")]},
        {},
        {},
        {},
        "build.gradle",
        "https://repo",
        None,
        "gradle",
        1,
        True,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.example:lib"
    assert changes[0]["new_version"] == "1.0.1"


def test_apply_updates_artifact_key_resolves_and_unparseable_direct_skips():
    dep = Dep("org.example", "lib", "not-version")
    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"lib": {mv("1.0.1")}},
        {"org.example:lib": [mv("1.0.1")]},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )

    assert changes == []
    assert forces == []
    assert skipped[0]["reason"] == "unparseable version"


def test_apply_updates_direct_already_current_and_selected_equal_skip(monkeypatch):
    dep = Dep("org.example", "lib", "1.0.1")

    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.example:lib": {mv("1.0.0")}},
        {"org.example:lib": [mv("1.0.0"), mv("1.0.1")]},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )
    assert changes == []
    assert skipped[0]["reason"] == "current version already meets ADO target"

    dep2 = Dep("org.example", "lib2", "1.0.0")
    monkeypatch.setattr(out_gradle, "find_accessible_version", lambda *a, **k: "1.0.0")
    changes, skipped, forces = out_gradle.apply_updates(
        [dep2],
        {"org.example:lib2": {mv("1.0.1")}},
        {"org.example:lib2": [mv("1.0.1")]},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        False,
        False,
    )
    assert changes == []
    assert skipped[0]["reason"] == "selected version equals current"


def test_apply_updates_direct_accessibility_failure(monkeypatch):
    dep = Dep("org.example", "lib", "1.0.0")
    monkeypatch.setattr(out_gradle, "find_accessible_version", lambda *a, **k: None)

    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.example:lib": {mv("1.0.1")}},
        {"org.example:lib": [mv("1.0.1")]},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        False,
        False,
    )

    assert changes == []
    assert forces == []
    assert skipped[0]["reason"] == "no accessible version found >= target"


def test_apply_updates_missing_installed_or_no_target_skips():
    changes, skipped, forces = out_gradle.apply_updates(
        [],
        {"org.example:missing": {mv("1.0.1")}},
        {"org.example:missing": [mv("1.0.1")]},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )
    assert skipped[0]["reason"] == "not found in build file or dependency tree"

    changes, skipped, forces = out_gradle.apply_updates(
        [],
        {"org.example:transitive": {mv("2.0.0")}},
        {"org.example:transitive": [mv("2.0.0")]},
        {},
        {"org.example:transitive": mv("1.0.0")},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )
    assert (
        skipped[0]["reason"]
        == "no ADO versions for current major and no accessible same-major update found"
    )


def test_apply_updates_transitive_parent_update(monkeypatch, tmp_path):
    dep = Dep("org.example", "parent", "1.0.0")
    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}")
    monkeypatch.setattr(out_gradle, "resolve_transitive_with_gradle", lambda *a, **k: mv("1.0.3"))

    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.example:child": {mv("1.0.2")}},
        {
            "org.example:child": [mv("1.0.2")],
            "org.example:parent": [mv("1.0.1"), mv("1.0.4")],
        },
        {},
        {"org.example:child": mv("1.0.0")},
        {"org.example:child": {"org.example:parent"}},
        str(build_file),
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.example:parent"
    assert changes[0]["new_version"] == "1.0.4"


def test_apply_updates_transitive_force_when_no_parent_fix(monkeypatch, tmp_path):
    dep = Dep("org.example", "parent", "1.0.0")
    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}")
    monkeypatch.setattr(out_gradle, "resolve_transitive_with_gradle", lambda *a, **k: None)

    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.example:child": {mv("1.0.2")}},
        {
            "org.example:child": [mv("1.0.2")],
            "org.example:parent": [mv("1.0.1")],
        },
        {},
        {"org.example:child": mv("1.0.0")},
        {"org.example:child": {"org.example:parent"}},
        str(build_file),
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )

    assert changes == []
    assert skipped == []
    assert forces == [
        {
            "dependency": "org.example:child",
            "old_version": "1.0.0",
            "new_version": "1.0.2",
            "minimum_required": "1.0.2",
        }
    ]


def test_apply_updates_transitive_no_parents_skips(tmp_path):
    build_file = tmp_path / "build.gradle"
    build_file.write_text("dependencies {}")

    changes, skipped, forces = out_gradle.apply_updates(
        [],
        {"org.example:child": {mv("1.0.2")}},
        {"org.example:child": [mv("1.0.2")]},
        {},
        {"org.example:child": mv("1.0.0")},
        {},
        str(build_file),
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )

    assert changes == []
    assert forces == []
    assert skipped[0]["reason"] == "transitive dep not found in dependency tree"


def test_write_resolution_forces_all_insertion_modes():
    forces = [{"dependency": "org.example:lib", "new_version": "1.2.3"}]

    existing = "configurations.all {\n    resolutionStrategy {\n    }\n}\n"
    assert "force 'org.example:lib:1.2.3'" in out_gradle.write_resolution_forces(existing, forces)

    before_deps = "plugins {}\n\ndependencies {\n}\n"
    result = out_gradle.write_resolution_forces(before_deps, forces)
    assert result.index("configurations.all") < result.index("dependencies")

    appended = out_gradle.write_resolution_forces("plugins {}\n", forces)
    assert appended.endswith("}\n")

    assert out_gradle.write_resolution_forces("same", []) == "same"


def test_write_gradle_file_output_and_in_place(tmp_path, capsys):
    source = tmp_path / "build.gradle"
    output = tmp_path / "build.updated.gradle"
    source.write_text("implementation 'org.example:lib:1.0.0'\n")
    out_gradle.write_gradle_file(
        source.read_text(),
        [
            {
                "original": "implementation 'org.example:lib:1.0.0'",
                "replacement": "implementation 'org.example:lib:1.0.1'",
            }
        ],
        [],
        str(output),
        str(source),
        False,
    )
    assert "1.0.1" in output.read_text()

    out_gradle.write_gradle_file(
        source.read_text(),
        [
            {
                "original": "implementation 'org.example:lib:1.0.0'",
                "replacement": "implementation 'org.example:lib:1.0.2'",
            }
        ],
        [],
        str(output),
        str(source),
        True,
    )
    assert (tmp_path / "build.gradle.bak").exists()
    assert "1.0.2" in source.read_text()

    out_gradle.write_gradle_file(source.read_text(), [], [], str(output), str(source), True)
    assert "Backup already exists" in capsys.readouterr().out


def test_apply_updates_current_major_ado_target_without_available_versions():
    dep = Dep("org.apache.neethi", "neethi", "3.2.1")
    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.apache.neethi:neethi": {mv("3.2.2")}},
        {},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.apache.neethi:neethi"
    assert changes[0]["new_version"] == "3.2.2"


def test_apply_updates_artifact_constraint_fallback_after_full_key_resolution():
    dep = Dep("org.apache.neethi", "neethi", "3.2.1")
    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"neethi": {mv("3.2.1")}},
        {"org.apache.neethi:neethi": [mv("3.2.1"), mv("3.2.2")]},
        {"neethi": ">"},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.apache.neethi:neethi"
    assert changes[0]["new_version"] == "3.2.2"


def test_apply_updates_direct_no_current_major_uses_accessible_same_major(monkeypatch):
    dep = Dep("org.example", "lib", "2.0.0")
    monkeypatch.setattr(out_gradle, "find_accessible_version", lambda *a, **k: "2.0.1")

    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.example:lib": {mv("1.0.1")}},
        {"org.example:lib": [mv("1.0.1"), mv("2.0.1"), mv("2.0.2")]},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        False,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.example:lib"
    assert changes[0]["new_version"] == "2.0.1"


def test_apply_updates_transitive_no_current_major_uses_same_major_force():
    changes, skipped, forces = out_gradle.apply_updates(
        [],
        {"org.example:child": {mv("1.0.1")}},
        {"org.example:child": [mv("1.0.1"), mv("2.0.1")]},
        {},
        {"org.example:child": mv("2.0.0")},
        {"org.example:child": {"org.example:parent"}},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )

    assert changes == []
    assert skipped == []
    assert forces == [
        {
            "dependency": "org.example:child",
            "old_version": "2.0.0",
            "new_version": "2.0.1",
            "minimum_required": "2.0.1",
        }
    ]


def test_apply_updates_direct_no_current_major_skip_block_check_uses_highest_same_major():
    dep = Dep("org.example", "lib", "2.0.0")
    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.example:lib": {mv("1.0.1")}},
        {"org.example:lib": [mv("1.0.1"), mv("2.0.1"), mv("2.0.3"), mv("2.0.2")]},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        True,
        False,
    )
    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.example:lib"
    assert changes[0]["new_version"] == "2.0.3"


def test_apply_updates_direct_no_current_major_block_check_tries_lower_unblocked(monkeypatch):
    dep = Dep("org.example", "lib", "2.0.0")

    def fake_find_accessible_version(group, artifact, start, available, base_url, auth, timeout):
        if str(start) == "2.0.3":
            return None
        if str(start) == "2.0.2":
            return "2.0.2"
        return None

    monkeypatch.setattr(out_gradle, "find_accessible_version", fake_find_accessible_version)
    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {"org.example:lib": {mv("1.0.1")}},
        {"org.example:lib": [mv("1.0.1"), mv("2.0.1"), mv("2.0.3"), mv("2.0.2")]},
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        False,
        False,
    )
    assert skipped == []
    assert forces == []
    assert changes[0]["dependency"] == "org.example:lib"
    assert changes[0]["new_version"] == "2.0.2"


def test_apply_updates_prefers_current_minor_ado_then_accessible_higher_patch(monkeypatch):
    dep = Dep("io.netty", "netty-codec-http", "4.1.132.Final")

    def fake_find_accessible_version(group, artifact, start, available, base_url, auth, timeout):
        assert str(start) == "4.1.133.Final"
        assert all(v.major == 4 for v in available)
        return "4.1.135.Final"

    monkeypatch.setattr(out_gradle, "find_accessible_version", fake_find_accessible_version)

    changes, skipped, forces = out_gradle.apply_updates(
        [dep],
        {
            "io.netty:netty-codec-http": {
                mv("4.1.133.Final"),
                mv("4.2.0.Final"),
                mv("4.2.13.Final"),
            }
        },
        {
            "io.netty:netty-codec-http": [
                mv("4.1.133.Final"),
                mv("4.1.135.Final"),
                mv("4.2.13.Final"),
            ]
        },
        {},
        {},
        {},
        "build.gradle",
        "",
        None,
        "gradle",
        1,
        False,
        False,
    )

    assert skipped == []
    assert forces == []
    assert changes[0]["new_version"] == "4.1.135.Final"


def test_apply_updates_version_managed_direct_dependency_does_not_change_spring_framework_property(
    tmp_path,
):
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        """plugins {
    id 'java'
}

ext {
    set('spring-framework.version', "6.2.17")
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-webflux'
}
"""
    )

    changes, skipped, forces = out_gradle.apply_updates(
        [],
        {"org.springframework.boot:spring-boot-starter-webflux": {mv("3.5.16")}},
        {
            "org.springframework.boot:spring-boot-starter-webflux": [
                mv("3.5.15"),
                mv("3.5.16"),
            ]
        },
        {},
        {"org.springframework.boot:spring-boot-starter-webflux": mv("3.5.15")},
        {},
        str(build_file),
        "",
        None,
        "gradle",
        1,
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


def test_apply_updates_version_managed_direct_dependency_skips_before_spring_property(tmp_path):
    build_file = tmp_path / "build.gradle"
    build_file.write_text(
        """ext {
    set('spring-framework.version', "6.2.17")
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-webflux'
}
"""
    )

    changes, skipped, forces = out_gradle.apply_updates(
        [],
        {"org.springframework.boot:spring-boot-starter-webflux": {mv("3.5.16")}},
        {"org.springframework.boot:spring-boot-starter-webflux": [mv("3.5.15"), mv("3.5.16")]},
        {},
        {"org.springframework.boot:spring-boot-starter-webflux": mv("3.5.15")},
        {},
        str(build_file),
        "",
        None,
        "gradle",
        1,
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


def test_write_resolution_forces_matches_existing_indentation():
    build_text = """configurations.all {
    resolutionStrategy {
            force 'com.fasterxml.jackson.core:jackson-core:2.22.0'
    }
}
"""
    updated = out_gradle.write_resolution_forces(
        build_text,
        [{"dependency": "org.apache.neethi:neethi", "new_version": "3.2.2"}],
    )

    assert "            force 'org.apache.neethi:neethi:3.2.2'" in updated
    assert "\n        force 'org.apache.neethi:neethi:3.2.2'" not in updated


def test_write_resolution_forces_injects_buildscript_and_project_forces():
    build_text = """plugins {
    id 'java'
}
buildscript {
    repositories { mavenCentral() }
}

dependencies {
    implementation 'org.example:lib:1.0.0'
}
"""
    updated = out_gradle.write_resolution_forces(
        build_text,
        [
            {
                "dependency": "com.fasterxml.jackson.core:jackson-databind",
                "new_version": "2.21.5",
            }
        ],
    )
    assert updated.count("force 'com.fasterxml.jackson.core:jackson-databind:2.21.5'") == 2
    assert updated.index("plugins {") < updated.index("configurations.all")
    assert "buildscript {\n    configurations.all" in updated
