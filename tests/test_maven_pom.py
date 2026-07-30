"""Tests for the Maven POM pipeline: parser, writer, settings generation, and version selection."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from managers.maven import _is_stable
from output.maven_pom import apply_pom_changes
from parsers.pom import (
    _extract_repo_ids,
    _write_temp_settings,
    parse_maven_dep_tree,
    parse_pom_text,
)
from shared.maven_version import MavenVersion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mv(s: str) -> MavenVersion:
    v = MavenVersion.parse(s)
    assert v is not None, f"MavenVersion.parse({s!r}) returned None"
    return v


# ---------------------------------------------------------------------------
# parse_pom_text
# ---------------------------------------------------------------------------

_SIMPLE_POM = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>6.2.11</version>
    </dependency>
    <dependency>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
      <version>2.17.0</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
"""


class TestParsePomText:
    def test_parses_direct_deps(self):
        parsed = parse_pom_text(_SIMPLE_POM)
        by_artifact = {d.artifact: d for d in parsed.deps}
        assert "spring-core" in by_artifact
        assert "jackson-databind" in by_artifact

    def test_direct_dep_fields(self):
        parsed = parse_pom_text(_SIMPLE_POM)
        dep = next(d for d in parsed.deps if d.artifact == "spring-core")
        assert dep.group == "org.springframework"
        assert dep.version == "6.2.11"
        assert dep.scope == "compile"
        assert not dep.is_managed

    def test_scope_preserved(self):
        parsed = parse_pom_text(_SIMPLE_POM)
        dep = next(d for d in parsed.deps if d.artifact == "jackson-databind")
        assert dep.scope == "test"

    def test_version_span_points_to_correct_text(self):
        parsed = parse_pom_text(_SIMPLE_POM)
        dep = next(d for d in parsed.deps if d.artifact == "spring-core")
        assert dep.version_span is not None
        start, end = dep.version_span
        assert parsed.pom_text[start:end] == "6.2.11"

    def test_managed_deps_flagged(self):
        pom = """\
<project>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-dependencies</artifactId>
        <version>3.3.0</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter</artifactId>
    </dependency>
  </dependencies>
</project>
"""
        parsed = parse_pom_text(pom)
        managed = [d for d in parsed.deps if d.is_managed]
        direct = [d for d in parsed.deps if not d.is_managed]
        assert len(managed) == 1
        assert managed[0].artifact == "spring-boot-dependencies"
        assert managed[0].version == "3.3.0"
        # spring-boot-starter has no version declared — still parsed
        assert any(d.artifact == "spring-boot-starter" for d in direct)

    def test_property_substitution(self):
        pom = """\
<project>
  <properties>
    <spring.version>6.1.5</spring.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>${spring.version}</version>
    </dependency>
  </dependencies>
</project>
"""
        parsed = parse_pom_text(pom)
        dep = next(d for d in parsed.deps if d.artifact == "spring-core")
        assert dep.version == "6.1.5"
        assert dep.version_raw == "${spring.version}"
        assert dep.property_key == "spring.version"
        # property_span must point at "6.1.5" in pom_text
        assert dep.property_span is not None
        s, e = dep.property_span
        assert parsed.pom_text[s:e] == "6.1.5"

    def test_no_deps(self):
        pom = "<project><modelVersion>4.0.0</modelVersion></project>"
        parsed = parse_pom_text(pom)
        assert parsed.deps == []

    def test_dm_inner_deps_not_double_counted_as_direct(self):
        """The <dependencies> inside <dependencyManagement> must not be parsed
        a second time as direct dependencies."""
        pom = """\
<project>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.example</groupId>
        <artifactId>managed-lib</artifactId>
        <version>1.0.0</version>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
"""
        parsed = parse_pom_text(pom)
        matches = [d for d in parsed.deps if d.artifact == "managed-lib"]
        assert len(matches) == 1
        assert matches[0].is_managed


# ---------------------------------------------------------------------------
# _extract_repo_ids
# ---------------------------------------------------------------------------

class TestExtractRepoIds:
    def test_no_repos(self):
        assert _extract_repo_ids("<project></project>") == []

    def test_single_repo(self):
        pom = """\
<project>
  <repositories>
    <repository>
      <id>confluent</id>
      <url>https://packages.confluent.io/maven/</url>
    </repository>
  </repositories>
</project>
"""
        ids = _extract_repo_ids(pom)
        assert ids == ["confluent"]

    def test_multiple_repos_and_plugin_repos(self):
        pom = """\
<project>
  <repositories>
    <repository><id>repo-a</id></repository>
    <repository><id>repo-b</id></repository>
  </repositories>
  <pluginRepositories>
    <pluginRepository><id>plugin-repo</id></pluginRepository>
  </pluginRepositories>
</project>
"""
        ids = _extract_repo_ids(pom)
        assert set(ids) == {"repo-a", "repo-b", "plugin-repo"}

    def test_no_duplicates(self):
        pom = """\
<project>
  <repositories>
    <repository><id>my-repo</id></repository>
    <repository><id>my-repo</id></repository>
  </repositories>
</project>
"""
        ids = _extract_repo_ids(pom)
        assert ids.count("my-repo") == 1


# ---------------------------------------------------------------------------
# _write_temp_settings — XML validity (the leading-whitespace bug)
# ---------------------------------------------------------------------------

class TestWriteTempSettings:
    def _read_and_delete(self, path: str) -> str:
        import os
        try:
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_xml_declaration_is_flush_left(self):
        """<?xml must start at column 0 — leading whitespace causes Maven to
        reject the settings file with 'processing instruction can not have
        PITarget with reserved xml name'."""
        path = _write_temp_settings("https://repo.example/maven", ("user", "pass"))
        content = self._read_and_delete(path)
        first_line = content.splitlines()[0]
        assert first_line.startswith("<?xml"), (
            f"First line has leading whitespace: {first_line!r}"
        )

    def test_valid_xml(self):
        """The generated file must be parseable as XML."""
        path = _write_temp_settings("https://repo.example/maven", ("user", "pass"))
        content = self._read_and_delete(path)
        ET.fromstring(content)  # raises if invalid

    def test_mirror_url_present(self):
        path = _write_temp_settings("https://artifactory.example.com/libs", ("u", "p"))
        content = self._read_and_delete(path)
        assert "https://artifactory.example.com/libs" in content

    def test_extra_server_ids_included(self):
        path = _write_temp_settings(
            "https://repo.example/maven",
            ("user", "pass"),
            extra_server_ids=["confluent", "spring-milestones"],
        )
        content = self._read_and_delete(path)
        assert "<id>confluent</id>" in content
        assert "<id>spring-milestones</id>" in content

    def test_credentials_xml_escaped(self):
        """Special XML characters in credentials must be escaped."""
        path = _write_temp_settings(
            "https://repo.example/maven",
            ("user<name>", "p&ss\"word"),
        )
        content = self._read_and_delete(path)
        ET.fromstring(content)  # must parse without error
        assert "&lt;" in content or "user" in content  # escaped or safe
        assert "&amp;" in content or "pass" in content

    def test_mirrorof_star(self):
        """The mirror must have mirrorOf=* so all repos route through Artifactory."""
        path = _write_temp_settings("https://repo.example/maven", ("u", "p"))
        content = self._read_and_delete(path)
        assert "<mirrorOf>*</mirrorOf>" in content

    def test_artifactory_proxy_server_always_present(self):
        path = _write_temp_settings("https://repo.example/maven", ("u", "p"))
        content = self._read_and_delete(path)
        assert "<id>artifactory-proxy</id>" in content

    def test_extra_server_id_not_duplicated_if_already_proxy(self):
        """Passing 'artifactory-proxy' in extra_server_ids must not create a
        duplicate server entry."""
        path = _write_temp_settings(
            "https://repo.example/maven",
            ("u", "p"),
            extra_server_ids=["artifactory-proxy"],
        )
        content = self._read_and_delete(path)
        assert content.count("<id>artifactory-proxy</id>") == 1


# ---------------------------------------------------------------------------
# parse_maven_dep_tree
# ---------------------------------------------------------------------------

_TREE_OUTPUT = """\
[INFO] com.example:my-app:jar:1.0-SNAPSHOT
[INFO] +- org.springframework:spring-core:jar:6.2.11:compile
[INFO] +- com.fasterxml.jackson.core:jackson-databind:jar:2.17.0:compile
[INFO] |  +- com.fasterxml.jackson.core:jackson-annotations:jar:2.17.0:compile
[INFO] |  \\- com.fasterxml.jackson.core:jackson-core:jar:2.17.0:compile
[INFO] \\- ch.qos.logback:logback-classic:jar:1.5.6:runtime
"""


class TestParseMavenDepTree:
    def test_direct_deps_in_installed(self):
        installed, _ = parse_maven_dep_tree(_TREE_OUTPUT)
        assert "org.springframework:spring-core" in installed
        assert "com.fasterxml.jackson.core:jackson-databind" in installed
        assert "ch.qos.logback:logback-classic" in installed

    def test_transitive_deps_in_installed(self):
        installed, _ = parse_maven_dep_tree(_TREE_OUTPUT)
        assert "com.fasterxml.jackson.core:jackson-annotations" in installed
        assert "com.fasterxml.jackson.core:jackson-core" in installed

    def test_version_parsed(self):
        installed, _ = parse_maven_dep_tree(_TREE_OUTPUT)
        v = installed["org.springframework:spring-core"]
        assert str(v) == "6.2.11"

    def test_parents_of_transitives(self):
        _, parents_of = parse_maven_dep_tree(_TREE_OUTPUT)
        parents = parents_of.get("com.fasterxml.jackson.core:jackson-annotations", set())
        assert "com.fasterxml.jackson.core:jackson-databind" in parents

    def test_empty_output(self):
        installed, parents_of = parse_maven_dep_tree("")
        assert installed == {}
        assert parents_of == {}

    def test_no_info_prefix_lines(self):
        """Lines without [INFO] prefix must also be parsed."""
        tree = (
            "+- org.example:lib-a:jar:1.0.0:compile\n"
            "\\- org.example:lib-b:jar:2.0.0:runtime\n"
        )
        installed, _ = parse_maven_dep_tree(tree)
        assert "org.example:lib-a" in installed
        assert "org.example:lib-b" in installed


# ---------------------------------------------------------------------------
# _is_stable (managers/maven.py)
# ---------------------------------------------------------------------------

class TestIsStable:
    @pytest.mark.parametrize("version", [
        "6.2.11",
        "2.17.0",
        "1.5.25",
        "5.3.27.RELEASE",
        "1.3.0.RELEASE",
        "4.2.16.Final",
        "11.0.18",
        "0.2.5",
    ])
    def test_stable_versions_pass(self, version: str):
        mv = _mv(version)
        assert _is_stable(mv), f"{version!r} should be stable"

    @pytest.mark.parametrize("version", [
        "1.0-rc1",
        "2.0.0-RC1",
        "3.0.0-M1",
        "3.0.0-M2",
        "2.1.0-SNAPSHOT",
        "1.0.0-alpha",
        "1.0.0-beta",
        "1.0.0-beta2",
        "2.0.0.CR2",
        "3.0.0-milestone1",
    ])
    def test_prerelease_versions_filtered(self, version: str):
        mv = _mv(version)
        assert not _is_stable(mv), f"{version!r} should be filtered as prerelease"


# ---------------------------------------------------------------------------
# apply_pom_changes (output/maven_pom.py)
# ---------------------------------------------------------------------------

class TestApplyPomChanges:
    def _make_pom(self) -> str:
        return """\
<project>
  <properties>
    <spring.version>6.2.10</spring.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>${spring.version}</version>
    </dependency>
    <dependency>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
      <version>2.17.0</version>
    </dependency>
  </dependencies>
</project>
"""

    def test_direct_version_span_update(self):
        pom = self._make_pom()
        parsed = parse_pom_text(pom)
        dep = next(d for d in parsed.deps if d.artifact == "jackson-databind")
        change = {
            "dependency": "com.fasterxml.jackson.core:jackson-databind",
            "old_version": "2.17.0",
            "new_version": "2.17.3",
            "version_span": dep.version_span,
            "property_span": dep.property_span,
        }
        result = apply_pom_changes(pom, [change], [])
        assert "2.17.3" in result
        assert "2.17.0" not in result

    def test_property_span_update(self):
        pom = self._make_pom()
        parsed = parse_pom_text(pom)
        dep = next(d for d in parsed.deps if d.artifact == "spring-core")
        change = {
            "dependency": "org.springframework:spring-core",
            "old_version": "6.2.10",
            "new_version": "6.2.15",
            "version_span": dep.version_span,
            "property_span": dep.property_span,
        }
        result = apply_pom_changes(pom, [change], [])
        # The property value should be updated, not the ${...} reference
        assert "<spring.version>6.2.15</spring.version>" in result
        assert "6.2.10" not in result
        assert "${spring.version}" in result  # reference unchanged

    def test_dm_override_adds_new_dep_management_section(self):
        """When there is no <dependencyManagement>, it should be created."""
        pom = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.example</groupId>
      <artifactId>lib</artifactId>
      <version>1.0</version>
    </dependency>
  </dependencies>
</project>
"""
        override = {
            "dependency": "org.apache.commons:commons-lang3",
            "old_version": "3.12.0",
            "new_version": "3.14.0",
            "version_span": None,
            "property_span": None,
        }
        result = apply_pom_changes(pom, [], [override])
        assert "<dependencyManagement>" in result
        assert "commons-lang3" in result
        assert "3.14.0" in result

    def test_dm_override_inserts_into_existing_section(self):
        pom = """\
<project>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.example</groupId>
        <artifactId>existing</artifactId>
        <version>1.0.0</version>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.example</groupId>
      <artifactId>lib</artifactId>
      <version>2.0.0</version>
    </dependency>
  </dependencies>
</project>
"""
        override = {
            "dependency": "org.apache.commons:commons-text",
            "old_version": "",
            "new_version": "1.12.0",
            "version_span": None,
            "property_span": None,
        }
        result = apply_pom_changes(pom, [], [override])
        assert "commons-text" in result
        assert "1.12.0" in result
        assert "existing" in result  # original entry preserved

    def test_dm_override_updates_existing_entry(self):
        pom = """\
<project>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.apache.commons</groupId>
        <artifactId>commons-text</artifactId>
        <version>1.10.0</version>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
"""
        override = {
            "dependency": "org.apache.commons:commons-text",
            "old_version": "1.10.0",
            "new_version": "1.12.0",
            "version_span": None,
            "property_span": None,
        }
        result = apply_pom_changes(pom, [], [override])
        assert "1.12.0" in result
        assert "1.10.0" not in result

    def test_no_changes_returns_original(self):
        pom = self._make_pom()
        result = apply_pom_changes(pom, [], [])
        assert result == pom

    def test_multiple_span_changes_applied_correctly(self):
        """Two direct version updates must both be applied without offset errors."""
        pom = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>6.2.10</version>
    </dependency>
    <dependency>
      <groupId>ch.qos.logback</groupId>
      <artifactId>logback-classic</artifactId>
      <version>1.5.12</version>
    </dependency>
  </dependencies>
</project>
"""
        parsed = parse_pom_text(pom)
        by_artifact = {d.artifact: d for d in parsed.deps}
        changes = [
            {
                "dependency": "org.springframework:spring-core",
                "old_version": "6.2.10",
                "new_version": "6.2.15",
                "version_span": by_artifact["spring-core"].version_span,
                "property_span": None,
            },
            {
                "dependency": "ch.qos.logback:logback-classic",
                "old_version": "1.5.12",
                "new_version": "1.5.18",
                "version_span": by_artifact["logback-classic"].version_span,
                "property_span": None,
            },
        ]
        result = apply_pom_changes(pom, changes, [])
        assert "6.2.15" in result
        assert "1.5.18" in result
        assert "6.2.10" not in result
        assert "1.5.12" not in result


# ---------------------------------------------------------------------------
# Version selection — tree-failure fallback (regression for ancient-version bug)
# ---------------------------------------------------------------------------

class TestMavenVersionSelection:
    """Verify that apply_updates picks sensible candidates when the dependency
    tree failed (tree.installed is empty) and falls back to pom-declared versions."""

    def _run_apply_updates(
        self,
        pom_text: str,
        installed: dict,
        all_versions: dict,
        cve_packages: set,
        tree_failed: bool = False,
    ) -> dict:
        """Drive MavenPomOutput.apply_updates with fake tree/version data."""
        from types import SimpleNamespace

        from managers.maven import MavenPomOutput, MavenPomTree, MavenPomVersionSet

        parsed = parse_pom_text(pom_text)

        tree = MavenPomTree(
            installed=installed,
            parents_of={},
            project_dir="/tmp/fake",
            maven_cmd="mvn",
            base_url="https://repo.example",
            auth=("u", "p"),
            prefetched_versions={},
            tree_failed=tree_failed,
        )

        # Convert string lists to MavenVersion lists
        versions_by_key = {
            ga: [v for v in (_mv(s) for s in strs) if v is not None]
            for ga, strs in all_versions.items()
        }
        version_set = MavenPomVersionSet(versions_by_key=versions_by_key)

        cfg = SimpleNamespace(
            maven_timeout=30,
            workers=1,
            skip_block_check=True,
            xray_host=None,
            skip_build_validation=True,
        )

        output = MavenPomOutput()
        result = output.apply_updates(parsed, tree, version_set, cve_packages, cfg, log_dir=None)
        return result

    def test_tree_failure_uses_pom_declared_version_as_baseline(self):
        """When the dependency tree failed, apply_updates must fall back to the
        pom-declared version — not pick the oldest available version."""
        pom = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>6.2.11</version>
    </dependency>
  </dependencies>
</project>
"""
        # Tree failed → no installed versions
        # Artifactory has versions from ancient 1.0-rc1 through 6.2.13
        all_versions = {
            "org.springframework:spring-core": [
                "1.0-rc1", "2.0.0-RC1", "5.3.0", "6.0.0", "6.2.11", "6.2.12", "6.2.13",
            ]
        }
        result = self._run_apply_updates(
            pom,
            installed={},
            all_versions=all_versions,
            cve_packages={"org.springframework:spring-core"},
            tree_failed=True,
        )
        changes = result.extra["changes"]
        assert len(changes) == 1, "Expected one version change"
        ch = changes[0]
        # Must NOT pick 1.0-rc1 or 2.0.0-RC1 — must pick a 6.x.x above 6.2.11
        assert ch["new_version"] not in ("1.0-rc1", "2.0.0-RC1", "5.3.0", "6.0.0", "6.2.11")
        assert ch["new_version"] in ("6.2.12", "6.2.13")

    def test_prerelease_versions_excluded_from_candidates(self):
        """RC, alpha, beta, SNAPSHOT, Mx versions must never be selected."""
        pom = """\
<project>
  <dependencies>
    <dependency>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
      <version>2.17.0</version>
    </dependency>
  </dependencies>
</project>
"""
        all_versions = {
            "com.fasterxml.jackson.core:jackson-databind": [
                "2.17.0",
                "2.17.1-SNAPSHOT",
                "2.17.1-rc1",
                "2.17.2",
                "2.18.0-M1",
                "2.18.0",
            ]
        }
        result = self._run_apply_updates(
            pom,
            installed={_mv("2.17.0") and "com.fasterxml.jackson.core:jackson-databind": _mv("2.17.0")},
            all_versions=all_versions,
            cve_packages={"com.fasterxml.jackson.core:jackson-databind"},
        )
        changes = result.extra["changes"]
        assert len(changes) == 1
        # Should pick 2.17.2, not any prerelease
        assert changes[0]["new_version"] in ("2.17.2", "2.18.0")
        assert "SNAPSHOT" not in changes[0]["new_version"]
        assert "rc" not in changes[0]["new_version"].lower()
        assert "M1" not in changes[0]["new_version"]

    def test_no_baseline_skips_package(self):
        """Purely transitive dep + tree failed → skipped, not random pick."""
        pom = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.example</groupId>
      <artifactId>lib</artifactId>
      <version>1.0</version>
    </dependency>
  </dependencies>
</project>
"""
        # CVE on a package not in pom.xml at all, and tree failed
        all_versions = {
            "org.apache.commons:commons-text": [
                "1.9", "1.10.0", "1.11.0", "1.12.0",
            ]
        }
        result = self._run_apply_updates(
            pom,
            installed={},
            all_versions=all_versions,
            cve_packages={"org.apache.commons:commons-text"},
            tree_failed=True,
        )
        changes = result.extra["changes"]
        dm_overrides = result.extra["dm_overrides"]
        skipped = result.extra["skipped_raw"]
        # Package absent from both pom and tree → should be skipped or not updated
        # (it may be skipped as "not in known_full_keys", which is also correct)
        assert len(changes) == 0
        assert len(dm_overrides) == 0

    def test_already_at_target_not_changed(self):
        """If dep is already at the target version, no change should be emitted."""
        pom = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>6.2.13</version>
    </dependency>
  </dependencies>
</project>
"""
        all_versions = {
            "org.springframework:spring-core": ["6.2.11", "6.2.12", "6.2.13"],
        }
        installed = {"org.springframework:spring-core": _mv("6.2.13")}
        result = self._run_apply_updates(
            pom,
            installed=installed,
            all_versions=all_versions,
            cve_packages={"org.springframework:spring-core"},
        )
        assert result.extra["changes"] == []

    def test_no_forward_candidates_skips_package(self):
        """If all available versions are <= current, package is skipped."""
        pom = """\
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-core</artifactId>
      <version>6.2.13</version>
    </dependency>
  </dependencies>
</project>
"""
        all_versions = {
            "org.springframework:spring-core": ["6.0.0", "6.1.0", "6.2.12", "6.2.13"],
        }
        installed = {"org.springframework:spring-core": _mv("6.2.13")}
        result = self._run_apply_updates(
            pom,
            installed=installed,
            all_versions=all_versions,
            cve_packages={"org.springframework:spring-core"},
        )
        assert result.extra["changes"] == []
        assert len(result.extra["skipped_raw"]) == 1
