from __future__ import annotations

from types import SimpleNamespace

from managers.gradle import GradleOutput, GradleParsed, GradleTree, GradleVersionSet
from parsers.gradle import parse_gradle_deps
from shared.maven_version import MavenVersion


def test_gradle_manager_force_fallback_patches_every_occurrence_of_bumped_dependency(
    tmp_path,
):
    """Companion to output/gradle.py's Case 1 duplicate-declaration fix:
    managers/gradle.py's bumped-dependency force-fallback loop had the same
    direct_by_key collapse bug. A dependency bumped via tree.bumped (e.g. a
    Spring Boot managed-version resolution) that's also directly declared
    twice in build.gradle must get both declarations patched, not just the
    first.
    """
    build_text = (
        "dependencies {\n"
        "    implementation 'org.example:shared-lib:1.0.0'\n"
        "    implementation 'org.example:shared-lib:1.0.0'\n"
        "}\n"
    )
    build_file = tmp_path / "build.gradle"
    build_file.write_text(build_text, encoding="utf-8")

    deps = parse_gradle_deps(build_text)
    assert len(deps) == 2, "test setup must produce two parsed occurrences"

    parsed = GradleParsed(
        file_path=str(build_file), build_text=build_text, deps=deps, repo_urls=[]
    )
    tree = GradleTree(
        installed={"org.example:shared-lib": MavenVersion.parse("1.0.0")},
        parents_of={},
        bumped={"org.example:shared-lib": "2.0.0"},
        project_dir=str(tmp_path),
        gradle_cmd="gradle",
        base_url="https://jfrog.example/artifactory/gradle",
        auth=None,
    )
    versions = GradleVersionSet(versions_by_key={})
    cfg = SimpleNamespace(
        gradle_timeout=30, workers=8, skip_block_check=True, xray_host=None
    )

    result = GradleOutput().apply_updates(
        parsed=parsed,
        tree=tree,
        versions=versions,
        cve_packages=set(),
        cfg=cfg,
        log_dir=str(tmp_path),
    )

    changes = result.extra["changes"]
    matching = [c for c in changes if c["dependency"] == "org.example:shared-lib"]
    assert len(matching) == 2, matching
    assert all(c["new_version"] == "2.0.0" for c in matching)
