from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from managers.gradle import GradleParser
from shared.maven_version import MavenVersion


def make_cfg():
    return SimpleNamespace(
        artifactory_source="https://jfrog.example/artifactory",
        artifactory_repo="gradle",
        artifactory_username="",
        artifactory_password="",
        gradle_timeout=30,
        workers=4,
    )


def make_parsed(build_file):
    return SimpleNamespace(
        file_path=str(build_file),
        build_text=build_file.read_text(encoding="utf-8"),
        deps=[],
        repo_urls=[],
    )


class GradleManagerTreeResolutionTests(TestCase):
    def test_configurations_run_sequentially_and_keep_successful_trees(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "repo"
            logs = root / "logs"
            project.mkdir()
            logs.mkdir()
            build_file = project / "build.gradle"
            build_file.write_text(
                "plugins { id 'java' }",
                encoding="utf-8",
            )

            active = 0
            max_active = 0
            calls = []

            def fake_run(**kwargs):
                nonlocal active, max_active
                configuration = kwargs["configuration"]
                calls.append(configuration)
                active += 1
                max_active = max(max_active, active)
                try:
                    if configuration == "runtimeClasspath":
                        return (
                            "+--- org.example:runtime:1.0.0\n",
                            None,
                            {},
                        )
                    if configuration == "testRuntimeClasspath":
                        return (
                            "\\--- org.example:test:2.0.0\n",
                            None,
                            {},
                        )
                    return (
                        None,
                        f"configuration '{configuration}' not found",
                        {},
                    )
                finally:
                    active -= 1
            with (
                patch(
                    "parsers.gradle.parallel_fetch_versions",
                    return_value=({}, []),
                ),
                patch(
                    "parsers.gradle_tree.get_gradle_cmd",
                    return_value="gradle",
                ),
                patch(
                    "parsers.gradle_tree.run_gradle_dependencies_with_fallback",
                    side_effect=fake_run,
                ),
            ):
                tree = GradleParser().resolve_tree(
                    str(build_file),
                    make_parsed(build_file),
                    make_cfg(),
                    str(logs),
                )

            self.assertEqual(
                calls,
                [
                    "runtimeClasspath",
                    "compileClasspath",
                    "testRuntimeClasspath",
                    "testCompileClasspath",
                ],
            )
            self.assertEqual(max_active, 1)
            self.assertFalse(tree.tree_failed)
            self.assertEqual(
                tree.installed["org.example:runtime"],
                MavenVersion.parse("1.0.0"),
            )
            self.assertEqual(
                tree.installed["org.example:test"],
                MavenVersion.parse("2.0.0"),
            )
            self.assertTrue(
                (logs / "gradle-dependency-tree.txt").is_file()
            )
            self.assertFalse(
                (logs / "gradle-dependency-tree-error.txt").exists()
            )

    def test_repo_urls_prefer_gradle_evaluated_over_regex_parse(self):
        """Live bug: a repo declared as url "${ARTIFACTORY_SOURCE}/repo-name"
        is extracted verbatim by the regex-based parser (parsed.repo_urls),
        breaking every accessibility probe run against that literal string.
        run_gradle_dependencies now injects an init script that has Gradle
        itself print each project's resolved repository URLs; resolve_tree
        must prefer that evaluated list over the regex parse when Gradle
        actually resolved something.
        """
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "repo"
            logs = root / "logs"
            project.mkdir()
            logs.mkdir()
            build_file = project / "build.gradle"
            build_file.write_text(
                "plugins { id 'java' }",
                encoding="utf-8",
            )

            def fake_run(**kwargs):
                configuration = kwargs["configuration"]
                if configuration == "runtimeClasspath":
                    return (
                        "PKGUPDATE_REPO_URL::https://real.example/artifactory/repo\n"
                        "+--- org.example:runtime:1.0.0\n",
                        None,
                        {},
                    )
                return (None, f"configuration '{configuration}' not found", {})

            parsed = make_parsed(build_file)
            parsed.repo_urls = ["${ARTIFACTORY_SOURCE}/repo-name"]

            with (
                patch(
                    "parsers.gradle.parallel_fetch_versions",
                    return_value=({}, []),
                ),
                patch(
                    "parsers.gradle_tree.get_gradle_cmd",
                    return_value="gradle",
                ),
                patch(
                    "parsers.gradle_tree.run_gradle_dependencies_with_fallback",
                    side_effect=fake_run,
                ),
            ):
                tree = GradleParser().resolve_tree(
                    str(build_file),
                    parsed,
                    make_cfg(),
                    str(logs),
                )

            self.assertEqual(
                tree.repo_urls,
                ["https://real.example/artifactory/repo"],
            )

    def test_repo_urls_fall_back_to_regex_parse_when_tree_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "repo"
            logs = root / "logs"
            project.mkdir()
            logs.mkdir()
            build_file = project / "build.gradle"
            build_file.write_text(
                "plugins { id 'java' }",
                encoding="utf-8",
            )

            def fake_run(**kwargs):
                configuration = kwargs["configuration"]
                return (None, f"configuration '{configuration}' not found", {})

            parsed = make_parsed(build_file)
            parsed.repo_urls = ["https://fallback.example/artifactory/repo"]

            with (
                patch(
                    "parsers.gradle.parallel_fetch_versions",
                    return_value=({}, []),
                ),
                patch(
                    "parsers.gradle_tree.get_gradle_cmd",
                    return_value="gradle",
                ),
                patch(
                    "parsers.gradle_tree.run_gradle_dependencies_with_fallback",
                    side_effect=fake_run,
                ),
            ):
                tree = GradleParser().resolve_tree(
                    str(build_file),
                    parsed,
                    make_cfg(),
                    str(logs),
                )

            self.assertEqual(
                tree.repo_urls,
                ["https://fallback.example/artifactory/repo"],
            )

    def test_resolve_repo_urls_only_requested_when_build_has_unresolved_property(self):
        """--init-script invalidates Gradle's configuration cache on every
        run — confirmed locally to add enough overhead to tip a marginal
        tree resolution over its timeout on a large project. resolve_tree
        must only ask for it (resolve_repo_urls=True) when the build file
        actually has something worth resolving.
        """
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "repo"
            logs = root / "logs"
            project.mkdir()
            logs.mkdir()
            build_file = project / "build.gradle"
            build_file.write_text(
                "repositories { maven { url \"${ARTIFACTORY_SOURCE}/repo\" } }",
                encoding="utf-8",
            )

            captured = {}

            def fake_run(**kwargs):
                captured[kwargs["configuration"]] = kwargs.get("resolve_repo_urls")
                return (None, f"configuration '{kwargs['configuration']}' not found", {})

            with (
                patch(
                    "parsers.gradle.parallel_fetch_versions",
                    return_value=({}, []),
                ),
                patch(
                    "parsers.gradle_tree.get_gradle_cmd",
                    return_value="gradle",
                ),
                patch(
                    "parsers.gradle_tree.run_gradle_dependencies_with_fallback",
                    side_effect=fake_run,
                ),
            ):
                GradleParser().resolve_tree(
                    str(build_file),
                    make_parsed(build_file),
                    make_cfg(),
                    str(logs),
                )

            assert captured == {
                "runtimeClasspath": True,
                "compileClasspath": True,
                "testRuntimeClasspath": True,
                "testCompileClasspath": True,
            }

    def test_resolve_repo_urls_not_requested_for_ordinary_build(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "repo"
            logs = root / "logs"
            project.mkdir()
            logs.mkdir()
            build_file = project / "build.gradle"
            build_file.write_text(
                "repositories { maven { url \"https://repo.example/artifactory\" } }",
                encoding="utf-8",
            )

            captured = {}

            def fake_run(**kwargs):
                captured[kwargs["configuration"]] = kwargs.get("resolve_repo_urls")
                return (None, f"configuration '{kwargs['configuration']}' not found", {})

            with (
                patch(
                    "parsers.gradle.parallel_fetch_versions",
                    return_value=({}, []),
                ),
                patch(
                    "parsers.gradle_tree.get_gradle_cmd",
                    return_value="gradle",
                ),
                patch(
                    "parsers.gradle_tree.run_gradle_dependencies_with_fallback",
                    side_effect=fake_run,
                ),
            ):
                GradleParser().resolve_tree(
                    str(build_file),
                    make_parsed(build_file),
                    make_cfg(),
                    str(logs),
                )

            assert not any(captured.values())

    def test_all_configuration_errors_are_recorded_when_none_resolve(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "repo"
            logs = root / "logs"
            project.mkdir()
            logs.mkdir()
            build_file = project / "build.gradle"
            build_file.write_text(
                "plugins { id 'base' }",
                encoding="utf-8",
            )

            def fake_run(**kwargs):
                configuration = kwargs["configuration"]
                return (
                    None,
                    f"configuration '{configuration}' not found",
                    {},
                )

            with (
                patch(
                    "parsers.gradle.parallel_fetch_versions",
                    return_value=({}, []),
                ),
                patch(
                    "parsers.gradle_tree.get_gradle_cmd",
                    return_value="gradle",
                ),
                patch(
                    "parsers.gradle_tree.run_gradle_dependencies_with_fallback",
                    side_effect=fake_run,
                ),
            ):
                tree = GradleParser().resolve_tree(
                    str(build_file),
                    make_parsed(build_file),
                    make_cfg(),
                    str(logs),
                )

            error_text = (
                logs / "gradle-dependency-tree-error.txt"
            ).read_text(encoding="utf-8")
            self.assertTrue(tree.tree_failed)
            for configuration in (
                "runtimeClasspath",
                "compileClasspath",
                "testRuntimeClasspath",
                "testCompileClasspath",
            ):
                self.assertIn(f"[{configuration}]", error_text)


if __name__ == "__main__":
    import unittest

    unittest.main()
