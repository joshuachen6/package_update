import pytest

from parsers.node import (
    collect_direct_entries,
    collect_known_packages,
    extract_prefix_and_version,
    find_top_level_dependents_from_lockfile,
    get_lockfile_installed_version,
    parse_npm_versions_stdout,
    parse_sections,
    should_skip_spec,
)
from shared.semver import SemVer

SAMPLE_PKG = {
    "dependencies": {
        "react": "^18.2.0",
        "lodash": "4.17.21",
    },
    "devDependencies": {
        "jest": "^29.0.0",
    },
    "peerDependencies": {
        "react-dom": "^18.0.0",
    },
    "optionalDependencies": {
        "fsevents": "^2.3.2",
    },
    "overrides": {
        "minimatch": "^5.1.6",
        "nested-pkg": {
            "transitive": "^1.0.0",
        },
    },
}


class TestParseSections:
    def test_none_returns_default(self):
        result = parse_sections(None)
        assert result == ["dependencies", "devDependencies"]

    def test_empty_string_returns_default(self):
        result = parse_sections("")
        assert result == ["dependencies", "devDependencies"]

    def test_single_section(self):
        result = parse_sections("dependencies")
        assert result == ["dependencies"]

    def test_multiple_sections(self):
        result = parse_sections("dependencies,devDependencies")
        assert result == ["dependencies", "devDependencies"]

    def test_strips_whitespace(self):
        result = parse_sections(" dependencies , devDependencies ")
        assert result == ["dependencies", "devDependencies"]

    def test_filters_empty_parts(self):
        result = parse_sections("dependencies,,devDependencies")
        assert result == ["dependencies", "devDependencies"]


class TestCollectKnownPackages:
    def test_collects_from_all_standard_sections(self):
        known = collect_known_packages(SAMPLE_PKG)
        assert "react" in known
        assert "lodash" in known
        assert "jest" in known
        assert "react-dom" in known
        assert "fsevents" in known

    def test_collects_flat_override_keys(self):
        known = collect_known_packages(SAMPLE_PKG)
        assert "minimatch" in known

    def test_collects_nested_override_keys(self):
        known = collect_known_packages(SAMPLE_PKG)
        assert "nested-pkg" in known
        assert "transitive" in known

    def test_empty_package_json(self):
        known = collect_known_packages({})
        assert known == set()

    def test_missing_sections_ignored(self):
        pkg = {"dependencies": {"lodash": "4.17.21"}}
        known = collect_known_packages(pkg)
        assert "lodash" in known
        assert len(known) == 1


class TestCollectDirectEntries:
    def test_collects_from_dependencies(self):
        entries = collect_direct_entries(SAMPLE_PKG, ["dependencies"])
        packages = {e.package for e in entries}
        assert "react" in packages
        assert "lodash" in packages
        assert "jest" not in packages

    def test_collects_from_dev_dependencies(self):
        entries = collect_direct_entries(SAMPLE_PKG, ["devDependencies"])
        packages = {e.package for e in entries}
        assert "jest" in packages
        assert "react" not in packages

    def test_collects_from_both_sections(self):
        entries = collect_direct_entries(SAMPLE_PKG, ["dependencies", "devDependencies"])
        packages = {e.package for e in entries}
        assert "react" in packages
        assert "jest" in packages

    def test_entry_fields(self):
        entries = collect_direct_entries(SAMPLE_PKG, ["dependencies"])
        react_entry = next(e for e in entries if e.package == "react")
        assert react_entry.spec == "^18.2.0"
        assert react_entry.section == "dependencies"
        assert react_entry.path == "dependencies.react"
        assert react_entry.key == "react"

    def test_skips_non_string_specs(self):
        pkg = {"dependencies": {"pkg-a": "1.0.0", "pkg-b": {"version": "1.0.0"}}}
        entries = collect_direct_entries(pkg, ["dependencies"])
        packages = {e.package for e in entries}
        assert "pkg-a" in packages
        assert "pkg-b" not in packages

    def test_missing_section_returns_empty(self):
        entries = collect_direct_entries(SAMPLE_PKG, ["nonexistent"])
        assert entries == []


class TestExtractPrefixAndVersion:
    def test_caret_prefix(self):
        prefix, v = extract_prefix_and_version("^1.2.3")
        assert prefix == "^"
        assert v == SemVer.parse("1.2.3")

    def test_tilde_prefix(self):
        prefix, v = extract_prefix_and_version("~2.0.0")
        assert prefix == "~"
        assert v == SemVer.parse("2.0.0")

    def test_no_prefix(self):
        prefix, v = extract_prefix_and_version("1.2.3")
        assert prefix == ""
        assert v == SemVer.parse("1.2.3")

    def test_non_semver_returns_none(self):
        prefix, v = extract_prefix_and_version("latest")
        assert prefix == "" and v is None

    def test_file_spec_returns_none(self):
        _prefix, v = extract_prefix_and_version("file:../my-package")
        assert v is None

    def test_non_string_returns_empty(self):
        prefix, v = extract_prefix_and_version(None)  # type: ignore
        assert prefix == "" and v is None

    def test_with_prerelease_suffix(self):
        prefix, v = extract_prefix_and_version("^1.0.0-beta.1")
        assert prefix == "^"
        assert v is not None
        assert v.major == 1


class TestShouldSkipSpec:
    @pytest.mark.parametrize(
        "spec",
        [
            "file:../my-pkg",
            "git+https://github.com/org/repo.git",
            "http://registry.example.com/pkg.tgz",
            "https://registry.example.com/pkg.tgz",
            "workspace:^",
            "link:../local",
            "npm:other-pkg@1.0.0",
        ],
    )
    def test_skips_non_registry_specs(self, spec):
        assert should_skip_spec(spec) is True

    @pytest.mark.parametrize(
        "spec",
        [
            "1.2.3",
            "^1.2.3",
            "~2.0.0",
            ">=3.0.0",
            "latest",
        ],
    )
    def test_does_not_skip_registry_specs(self, spec):
        assert should_skip_spec(spec) is False


class TestParseNpmVersionsStdout:
    def test_json_array(self):
        stdout = '["1.0.0","1.1.0","2.0.0"]'
        versions = parse_npm_versions_stdout(stdout)
        assert SemVer.parse("1.0.0") in versions
        assert SemVer.parse("2.0.0") in versions

    def test_single_version_string(self):
        stdout = '"1.2.3"'
        versions = parse_npm_versions_stdout(stdout)
        assert len(versions) == 1
        assert SemVer.parse("1.2.3") in versions

    def test_empty_stdout(self):
        assert parse_npm_versions_stdout("") == []
        assert parse_npm_versions_stdout("   ") == []

    def test_deduplicates(self):
        stdout = '["1.0.0","1.0.0","2.0.0"]'
        versions = parse_npm_versions_stdout(stdout)
        count = sum(1 for v in versions if v == SemVer.parse("1.0.0"))
        assert count == 1

    def test_sorted(self):
        stdout = '["2.0.0","1.0.0","1.5.0"]'
        versions = parse_npm_versions_stdout(stdout)
        assert versions == sorted(versions)

    def test_invalid_json_fallback(self):
        # Non-JSON → treated as raw string; SemVer.parse should handle it
        versions = parse_npm_versions_stdout("not-json-at-all")
        assert versions == []

    def test_filters_unparseable_versions(self):
        stdout = '["1.0.0", "not-a-version", "2.0.0"]'
        versions = parse_npm_versions_stdout(stdout)
        version_strs = {str(v) for v in versions}
        assert "1.0.0" in version_strs
        assert "2.0.0" in version_strs
        assert "not-a-version" not in version_strs


# ---------------------------------------------------------------------------
# Lockfile helpers
# ---------------------------------------------------------------------------


def _v3_lockfile(*entries):
    """Build a minimal v3-format lockfile (packages dict)."""
    packages = {"": {}}
    for path, version in entries:
        packages[path] = {"version": version}
    return {"lockfileVersion": 3, "packages": packages}


def _v1_lockfile(deps):
    """Build a minimal v1-format lockfile (dependencies dict)."""
    return {"lockfileVersion": 1, "dependencies": deps}


class TestGetLockfileInstalledVersion:
    def test_hoisted_v3(self):
        lf = _v3_lockfile(("node_modules/lodash", "4.17.21"))
        result = get_lockfile_installed_version(lf, "lodash")
        assert result == SemVer.parse("4.17.21")

    def test_nested_v3_found(self):
        lf = _v3_lockfile(
            ("node_modules/parent/node_modules/minimatch", "3.1.5"),
        )
        result = get_lockfile_installed_version(lf, "minimatch", under_parent="parent")
        assert result == SemVer.parse("3.1.5")

    def test_nested_v3_falls_back_to_hoisted(self):
        lf = _v3_lockfile(("node_modules/minimatch", "3.1.5"))
        # No nested copy, should fall back to hoisted
        result = get_lockfile_installed_version(lf, "minimatch", under_parent="eslint")
        assert result == SemVer.parse("3.1.5")

    def test_not_present_returns_none(self):
        lf = _v3_lockfile(("node_modules/lodash", "4.17.21"))
        assert get_lockfile_installed_version(lf, "missing-pkg") is None

    def test_empty_lockfile_returns_none(self):
        assert get_lockfile_installed_version({}, "lodash") is None

    def test_hoisted_v1(self):
        lf = _v1_lockfile({"lodash": {"version": "4.17.21"}})
        result = get_lockfile_installed_version(lf, "lodash")
        assert result == SemVer.parse("4.17.21")

    def test_nested_v1_under_parent(self):
        lf = _v1_lockfile(
            {
                "parent": {
                    "version": "1.0.0",
                    "dependencies": {
                        "minimatch": {"version": "3.0.4"},
                    },
                },
            }
        )
        result = get_lockfile_installed_version(lf, "minimatch", under_parent="parent")
        assert result == SemVer.parse("3.0.4")

    def test_nested_v3_prefers_specific_path_over_hoisted(self):
        lf = _v3_lockfile(
            ("node_modules/minimatch", "9.0.0"),
            ("node_modules/eslint/node_modules/minimatch", "3.1.5"),
        )
        result = get_lockfile_installed_version(lf, "minimatch", under_parent="eslint")
        assert result == SemVer.parse("3.1.5")

    def test_bad_version_string_returns_none(self):
        lf = {"packages": {"node_modules/pkg": {"version": "not-a-semver"}}}
        assert get_lockfile_installed_version(lf, "pkg") is None


class TestFindTopLevelDependentsFromLockfile:
    def test_non_hoisted_nested_path(self):
        lf = _v3_lockfile(
            ("node_modules/eslint/node_modules/minimatch", "3.1.5"),
        )
        result = find_top_level_dependents_from_lockfile("minimatch", lf, {"eslint"})
        assert 3 in result
        assert "eslint" in result[3]

    def test_multiple_parents_different_majors(self):
        lf = _v3_lockfile(
            ("node_modules/eslint/node_modules/minimatch", "3.1.5"),
            ("node_modules/glob/node_modules/minimatch", "9.0.0"),
        )
        result = find_top_level_dependents_from_lockfile("minimatch", lf, {"eslint", "glob"})
        assert "eslint" in result[3]
        assert "glob" in result[9]

    def test_non_direct_dep_not_included(self):
        # 'transitive-parent' is not in direct_dep_names so should be excluded
        lf = _v3_lockfile(
            ("node_modules/transitive-parent/node_modules/minimatch", "3.1.5"),
        )
        result = find_top_level_dependents_from_lockfile("minimatch", lf, {"eslint"})
        assert not any("transitive-parent" in deps for deps in result.values())

    def test_empty_lockfile_returns_empty(self):
        assert find_top_level_dependents_from_lockfile("minimatch", {}, {"eslint"}) == {}

    def test_package_not_in_lockfile_returns_empty(self):
        lf = _v3_lockfile(("node_modules/lodash", "4.17.21"))
        result = find_top_level_dependents_from_lockfile("minimatch", lf, {"lodash"})
        assert result == {}

    def test_v1_lockfile_walk(self):
        lf = _v1_lockfile(
            {
                "eslint": {
                    "version": "8.0.0",
                    "dependencies": {
                        "minimatch": {"version": "3.1.2"},
                    },
                },
            }
        )
        result = find_top_level_dependents_from_lockfile("minimatch", lf, {"eslint"})
        assert 3 in result
        assert "eslint" in result[3]

    def test_multiple_parents_same_major(self):
        lf = _v3_lockfile(
            ("node_modules/eslint/node_modules/minimatch", "3.1.5"),
            ("node_modules/jest/node_modules/minimatch", "3.0.8"),
        )
        result = find_top_level_dependents_from_lockfile("minimatch", lf, {"eslint", "jest"})
        assert result[3] == {"eslint", "jest"}
