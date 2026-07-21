from parsers.gradle_tree import (
    _inject_forces,
    _parse_blocked_packages,
    _replace_dep_version,
    parse_gradle_dep_tree,
)
from shared.maven_version import MavenVersion


def test_parse_gradle_dep_tree_tracks_transitive_direct_parent():
    output = """
runtimeClasspath - Runtime classpath of source set 'main'.
+--- org.example:parent-a:1.0.0
|    +--- org.example:child:1.2.0 -> 1.2.3
|    \\--- org.example:sibling:2.0.0
\\--- org.example:parent-b:3.0.0
     \\--- org.example:child:1.1.0 -> 1.2.3 (*)
"""
    installed, parents_of = parse_gradle_dep_tree(output)

    assert str(installed["org.example:parent-a"]) == "1.0.0"
    assert str(installed["org.example:parent-b"]) == "3.0.0"
    assert str(installed["org.example:child"]) == "1.2.3"
    assert str(installed["org.example:sibling"]) == "2.0.0"
    assert parents_of["org.example:child"] == {
        "org.example:parent-a",
        "org.example:parent-b",
    }
    assert parents_of["org.example:sibling"] == {"org.example:parent-a"}


def test_parse_gradle_dep_tree_records_multiple_direct_parents_for_non_duplicate_edges():
    output = """
+--- org.example:parent-a:1.0.0
|    \\--- org.example:shared:1.0.0
\\--- org.example:parent-b:1.0.0
     \\--- org.example:shared:1.0.0
"""
    installed, parents_of = parse_gradle_dep_tree(output)

    assert str(installed["org.example:shared"]) == "1.0.0"
    assert parents_of["org.example:shared"] == {
        "org.example:parent-a",
        "org.example:parent-b",
    }



def test_parse_gradle_dep_tree_records_parent_for_duplicate_after_top_level_entry():
    output = r"""+--- org.example:shared:1.0.0
\--- org.example:parent:2.0.0
     \--- org.example:shared:1.0.0 (*)"""
    installed, parents_of = parse_gradle_dep_tree(output)
    assert str(installed["org.example:shared"]) == "1.0.0"
    assert parents_of["org.example:shared"] == {"org.example:parent"}
def test_parse_gradle_dep_tree_skips_failed_dependencies():
    output = """
+--- org.example:parent:1.0.0
|    \\--- org.example:missing:9.9.9 FAILED
\\--- org.example:ok:2.0.0
"""

    installed, parents_of = parse_gradle_dep_tree(output)

    assert "org.example:missing" not in installed
    assert "org.example:missing" not in parents_of
    assert str(installed["org.example:ok"]) == "2.0.0"


def test_parse_blocked_packages_deduplicates_and_derives_repo_url():
    error = """
Could not resolve com.acme:blocked-lib:1.2.3.
> Could not GET 'https://repo.example.com/maven/com/acme/blocked-lib/1.2.3/blocked-lib-1.2.3.pom'. Received status code 403 from server: Forbidden
Could not resolve com.acme:blocked-lib:1.2.3.
> Could not GET 'https://repo.example.com/maven/com/acme/blocked-lib/1.2.3/blocked-lib-1.2.3.pom'. Received status code 403 from server: Forbidden
"""

    assert _parse_blocked_packages(error) == [
        ("com.acme", "blocked-lib", "1.2.3", "https://repo.example.com/maven")
    ]


def test_replace_dep_version_preserves_quotes_and_only_target_coordinate():
    build_text = """
dependencies {
    implementation 'com.acme:target:1.0.0'
    implementation "com.acme:other:1.0.0"
}
"""

    updated = _replace_dep_version(build_text, "com.acme", "target", "2.0.0")

    assert "implementation 'com.acme:target:2.0.0'" in updated
    assert 'implementation "com.acme:other:1.0.0"' in updated


def test_inject_forces_adds_project_and_buildscript_resolution_strategy():
    build_text = """
buildscript {
    repositories { mavenCentral() }
}

dependencies {
    implementation 'com.acme:app:1.0.0'
}
"""

    updated = _inject_forces(build_text, {"com.acme:blocked-lib": "1.2.4"})

    assert "force 'com.acme:blocked-lib:1.2.4'" in updated
    assert "buildscript {\n    configurations.all" in updated

    project_force_index = updated.rindex("configurations.all")
    assert updated.index("buildscript {") < project_force_index
    assert project_force_index < updated.index("dependencies {")


def test_inject_forces_after_plugins_block():
    from parsers.gradle_tree import _inject_forces

    build_text = """plugins {
    id 'java'
}

dependencies {
    implementation 'org.example:app:1.0.0'
}
"""
    result = _inject_forces(build_text, {"org.example:lib": "1.0.1"})

    assert result.index("plugins {") < result.index("configurations.all")
    assert result.index("configurations.all") < result.index("dependencies {")
    assert "force 'org.example:lib:1.0.1'" in result


def test_inject_forces_after_buildscript_and_plugins_blocks():
    from parsers.gradle_tree import _inject_forces

    build_text = """buildscript {
    repositories { mavenCentral() }
}

plugins {
    id 'java'
}

dependencies {
}
"""
    result = _inject_forces(build_text, {"org.example:lib": "1.0.1"})

    project_force_index = result.rindex("configurations.all")
    assert result.index("buildscript {") < result.index("plugins {")
    assert result.index("plugins {") < project_force_index
    assert project_force_index < result.index("dependencies {")
    assert "force 'org.example:lib:1.0.1'" in result


def test_parse_gradle_dep_tree_tracks_children_of_versionless_direct_parent():
    output = """runtimeClasspath - Runtime classpath of source set 'main'.
+--- org.springframework.boot:spring-boot-starter-webflux -> 3.5.15
|    +--- org.springframework:spring-web:6.2.19 -> 6.2.17
|    \\--- org.springframework:spring-webflux:6.2.19 -> 6.2.17
"""

    installed, parents_of = parse_gradle_dep_tree(output)

    assert str(installed["org.springframework.boot:spring-boot-starter-webflux"]) == "3.5.15"
    assert str(installed["org.springframework:spring-web"]) == "6.2.17"
    assert str(installed["org.springframework:spring-webflux"]) == "6.2.17"
    assert parents_of["org.springframework:spring-web"] == {
        "org.springframework.boot:spring-boot-starter-webflux"
    }
    assert parents_of["org.springframework:spring-webflux"] == {
        "org.springframework.boot:spring-boot-starter-webflux"
    }


def test_resolve_transitive_with_gradle_caches_identical_calls(monkeypatch, tmp_path):
    import subprocess

    import parsers.gradle_tree as gradle_tree

    if hasattr(gradle_tree.resolve_transitive_with_gradle, "cache_clear"):
        gradle_tree.resolve_transitive_with_gradle.cache_clear()

    project = tmp_path / "project"
    project.mkdir()
    build = project / "build.gradle"
    build.write_text("dependencies { implementation 'org.example:parent:1.0.0' }")
    calls = []

    def fake_copy_gradle_files(project_dir, tmp):
        pass

    def fake_replace_dep_version(build_text, group, artifact, version):
        return build_text.replace("1.0.0", version)

    def fake_parse_gradle_dep_tree(stdout):
        return {"org.example:child": MavenVersion.parse("1.0.2")}, {}

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, stdout="tree", stderr="")

    monkeypatch.setattr(gradle_tree, "_copy_gradle_files", fake_copy_gradle_files)
    monkeypatch.setattr(gradle_tree, "_replace_dep_version", fake_replace_dep_version)
    monkeypatch.setattr(gradle_tree, "parse_gradle_dep_tree", fake_parse_gradle_dep_tree)
    monkeypatch.setattr(gradle_tree.subprocess, "run", fake_run)

    first = gradle_tree.resolve_transitive_with_gradle(
        "org.example:parent",
        "1.0.1",
        "org.example:child",
        str(project),
        str(build),
        "gradle",
        30,
    )
    second = gradle_tree.resolve_transitive_with_gradle(
        "org.example:parent",
        "1.0.1",
        "org.example:child",
        str(project),
        str(build),
        "gradle",
        30,
    )

    assert first == MavenVersion.parse("1.0.2")
    assert second == MavenVersion.parse("1.0.2")
    assert len(calls) == 1

    if hasattr(gradle_tree.resolve_transitive_with_gradle, "cache_clear"):
        gradle_tree.resolve_transitive_with_gradle.cache_clear()


def test_gradle_repository_parser_excludes_plugin_repositories():
    from parsers.gradle import parse_gradle_repositories

    text = """
    buildscript {
        repositories {
            maven {
                url "https://repo.example/plugins-release"
            }
        }
    }

    repositories {
        maven {
            url "https://repo.example/app-virtual"
        }
    }
    """

    assert parse_gradle_repositories(text) == [
        "https://repo.example/app-virtual"
    ]


def test_gradle_repository_parser_skips_unresolved_property_urls():
    """Live bug: a repo declared as url "${ARTIFACTORY_SOURCE}/repo-name" was
    extracted verbatim and used as the sole accessibility-check URL, so
    find_accessible_version returned None for jackson-databind even though an
    accessible, non-vulnerable version existed — every HEAD request against
    the literal, unresolved "${ARTIFACTORY_SOURCE}" string failed, and there
    was no real URL left to fall back to. We don't evaluate Gradle
    expressions, so these must be dropped instead of returned as if they were
    usable URLs, letting callers fall back to the pipeline's own configured
    Artifactory base_url.
    """
    from parsers.gradle import parse_gradle_repositories

    text = """
    repositories {
        maven {
            url "${ARTIFACTORY_SOURCE}/repo-name"
        }
        maven {
            url "https://repo.example/app-virtual"
        }
    }
    """

    assert parse_gradle_repositories(text) == [
        "https://repo.example/app-virtual"
    ]


def test_extract_resolved_repo_urls_parses_marker_lines():
    from parsers.gradle_tree import extract_resolved_repo_urls

    output = (
        "PKGUPDATE_REPO_URL::https://real.example/artifactory/repo-a\n"
        "+--- org.example:lib:1.0.0\n"
        "PKGUPDATE_REPO_URL::https://real.example/artifactory/repo-b/\n"
        "PKGUPDATE_REPO_URL::https://real.example/artifactory/repo-a\n"
        "\\--- org.example:lib2:2.0.0\n"
    )

    assert extract_resolved_repo_urls(output) == [
        "https://real.example/artifactory/repo-a",
        "https://real.example/artifactory/repo-b",
    ]


def test_extract_resolved_repo_urls_empty_when_no_marker():
    from parsers.gradle_tree import extract_resolved_repo_urls

    assert extract_resolved_repo_urls("+--- org.example:lib:1.0.0\n") == []
    assert extract_resolved_repo_urls("") == []


def test_run_gradle_dependencies_injects_repo_url_init_script_when_requested(monkeypatch, tmp_path):
    """The repo-URL-resolving init script can ride along on the same
    `gradle dependencies` call already made for tree resolution, so
    discovering real repo URLs costs nothing extra beyond what's already run
    — but only when a caller actually asks for it via resolve_repo_urls=True.
    """
    import subprocess

    import parsers.gradle_tree as gradle_tree

    captured_cmd = {}

    def fake_run(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="+--- org.example:lib:1.0.0\n", stderr="")

    monkeypatch.setattr(gradle_tree.subprocess, "run", fake_run)

    gradle_tree.run_gradle_dependencies(str(tmp_path), "gradle", 30, resolve_repo_urls=True)

    cmd = captured_cmd["cmd"]
    assert "--init-script" in cmd
    script_path = cmd[cmd.index("--init-script") + 1]
    assert "PKGUPDATE_REPO_URL::" in open(script_path, encoding="utf-8").read()


def test_run_gradle_dependencies_skips_init_script_by_default(monkeypatch, tmp_path):
    """--init-script invalidates Gradle's configuration cache on every run
    (confirmed locally: "entry reused" without it, "entry stored" — i.e. a
    full reconfigure — with it), which is enough overhead to tip a marginal
    tree resolution over its timeout on a large project. Must be opt-in, not
    unconditional, so the common case (no unresolved repo URL to resolve)
    pays nothing extra.
    """
    import subprocess

    import parsers.gradle_tree as gradle_tree

    captured_cmd = {}

    def fake_run(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="+--- org.example:lib:1.0.0\n", stderr="")

    monkeypatch.setattr(gradle_tree.subprocess, "run", fake_run)

    gradle_tree.run_gradle_dependencies(str(tmp_path), "gradle", 30)

    assert "--init-script" not in captured_cmd["cmd"]


def test_has_unresolved_repo_url_detects_property_interpolation():
    from parsers.gradle import has_unresolved_repo_url

    assert has_unresolved_repo_url(
        'repositories { maven { url "${ARTIFACTORY_SOURCE}/repo" } }'
    )
    assert not has_unresolved_repo_url(
        'repositories { maven { url "https://repo.example/artifactory" } }'
    )
    assert not has_unresolved_repo_url("")


def test_gradle_probe_version_normalizes_exact_constraint():
    from parsers.gradle import (
        normalize_gradle_version_for_probe,
    )

    assert (
        normalize_gradle_version_for_probe("[4.31.1]")
        == "4.31.1"
    )
    assert (
        normalize_gradle_version_for_probe("[4.31.1,5.0)")
        is None
    )
    assert (
        normalize_gradle_version_for_probe(
            "${protobufVersion}"
        )
        is None
    )
