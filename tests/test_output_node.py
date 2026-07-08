import json
import os
from pathlib import Path
from typing import ClassVar

from output.node import (
    apply_updates,
    write_npm_available_versions_txt,
    write_package_json,
    write_package_versions_txt,
)
from parsers.node import collect_direct_entries, remove_nested_override_keys
from shared.semver import SemVer


class TestRemoveNestedOverrideKeys:
    def test_removes_nested_key(self):
        overrides = {
            "parent-a": {
                "transitive": "^1.0.0",
                "other": "^2.0.0",
            },
        }
        removed = remove_nested_override_keys(overrides, "transitive")
        assert "transitive" not in overrides["parent-a"]
        assert "other" in overrides["parent-a"]
        assert len(removed) == 1

    def test_does_not_remove_top_level_key(self):
        overrides = {
            "transitive": "^1.0.0",
            "parent-a": {
                "transitive": "^2.0.0",
            },
        }
        remove_nested_override_keys(overrides, "transitive")
        # Top-level "transitive" (path == "overrides") must NOT be removed
        assert "transitive" in overrides
        # Nested one should be removed
        assert "transitive" not in overrides["parent-a"]

    def test_removes_deeply_nested(self):
        overrides = {
            "parent-a": {
                "child": {
                    "transitive": "^1.0.0",
                },
            },
        }
        removed = remove_nested_override_keys(overrides, "transitive")
        assert "transitive" not in overrides["parent-a"]["child"]
        assert len(removed) == 1

    def test_no_match_returns_empty(self):
        overrides = {
            "parent-a": {
                "other-pkg": "^1.0.0",
            },
        }
        removed = remove_nested_override_keys(overrides, "transitive")
        assert removed == []

    def test_non_dict_value_ignored(self):
        overrides = {
            "parent-a": "^1.0.0",  # string value, not dict
        }
        removed = remove_nested_override_keys(overrides, "transitive")
        assert removed == []

    def test_empty_overrides(self):
        removed = remove_nested_override_keys({}, "transitive")
        assert removed == []

    def test_returns_path_strings(self):
        overrides = {
            "parent-a": {
                "transitive": "^1.0.0",
            },
        }
        removed = remove_nested_override_keys(overrides, "transitive")
        assert all(isinstance(r, str) for r in removed)
        assert "overrides.parent-a.transitive" in removed


class TestWritePackageJson:
    SAMPLE: ClassVar[dict[str, object]] = {
        "name": "my-app",
        "version": "1.0.0",
        "dependencies": {
            "lodash": "^4.17.21",
        },
    }

    def test_writes_valid_json(self, tmp_path):
        output_path = str(tmp_path / "package.json")
        source_path = str(tmp_path / "source.json")
        write_package_json(self.SAMPLE, output_path, source_path, in_place=False)
        with open(output_path) as f:
            loaded = json.load(f)
        assert loaded == self.SAMPLE

    def test_trailing_newline(self, tmp_path):
        output_path = str(tmp_path / "package.json")
        source_path = str(tmp_path / "source.json")
        write_package_json(self.SAMPLE, output_path, source_path, in_place=False)
        content = Path(output_path).read_text()
        assert content.endswith("\n")

    def test_two_space_indent(self, tmp_path):
        output_path = str(tmp_path / "package.json")
        source_path = str(tmp_path / "source.json")
        write_package_json(self.SAMPLE, output_path, source_path, in_place=False)
        content = Path(output_path).read_text()
        assert '  "name"' in content

    def test_in_place_writes_to_source(self, tmp_path):
        source_path = str(tmp_path / "package.json")
        Path(source_path).write_text(json.dumps({"old": True}))
        write_package_json(self.SAMPLE, source_path, source_path, in_place=True)
        loaded = json.loads(Path(source_path).read_text())
        assert loaded == self.SAMPLE

    def test_in_place_creates_backup(self, tmp_path):
        source_path = str(tmp_path / "package.json")
        original_content = json.dumps({"old": True})
        Path(source_path).write_text(original_content)
        write_package_json(self.SAMPLE, source_path, source_path, in_place=True)
        bak_path = source_path + ".bak"
        assert os.path.exists(bak_path)

    def test_in_place_backup_not_overwritten(self, tmp_path):
        source_path = str(tmp_path / "package.json")
        bak_path = source_path + ".bak"
        Path(source_path).write_text(json.dumps({"old": True}))
        Path(bak_path).write_text("ORIGINAL BACKUP")
        write_package_json(self.SAMPLE, source_path, source_path, in_place=True)
        assert Path(bak_path).read_text() == "ORIGINAL BACKUP"

    def test_unicode_preserved(self, tmp_path):
        pkg = {"name": "my-app", "description": "héllo wörld"}
        output_path = str(tmp_path / "package.json")
        source_path = str(tmp_path / "source.json")
        write_package_json(pkg, output_path, source_path, in_place=False)
        content = Path(output_path).read_text(encoding="utf-8")
        assert "héllo wörld" in content


def _sv(*versions):
    return {SemVer.parse(v) for v in versions}


def _svlist(*versions):
    return [SemVer.parse(v) for v in versions]


class TestWritePackageVersionsTxt:
    def test_writes_package_line(self, tmp_path):
        path = str(tmp_path / "versions.txt")
        write_package_versions_txt(
            path, {"lodash": _sv("4.17.21")}, {"lodash": {4: SemVer.parse("4.17.21")}}
        )
        content = Path(path).read_text()
        assert "lodash" in content
        assert "4.17.21" in content

    def test_writes_criteria(self, tmp_path):
        path = str(tmp_path / "versions.txt")
        write_package_versions_txt(
            path, {"lodash": _sv("4.17.21")}, {"lodash": {4: SemVer.parse("4.17.21")}}
        )
        content = Path(path).read_text()
        assert "criteria 4.x" in content

    def test_packages_sorted_case_insensitive(self, tmp_path):
        path = str(tmp_path / "versions.txt")
        pkg_versions = {"React": _sv("18.0.0"), "axios": _sv("1.5.0")}
        criteria = {
            "React": {18: SemVer.parse("18.0.0")},
            "axios": {1: SemVer.parse("1.5.0")},
        }
        write_package_versions_txt(path, pkg_versions, criteria)
        lines = Path(path).read_text().splitlines()
        names = [line.split(":")[0] for line in lines]
        assert names == sorted(names, key=str.lower)

    def test_multiple_versions_per_package(self, tmp_path):
        path = str(tmp_path / "versions.txt")
        write_package_versions_txt(path, {"lodash": _sv("4.17.20", "4.17.21")}, {})
        content = Path(path).read_text()
        assert "4.17.20" in content
        assert "4.17.21" in content

    def test_empty_input_writes_empty_file(self, tmp_path):
        path = str(tmp_path / "versions.txt")
        write_package_versions_txt(path, {}, {})
        assert Path(path).read_text() == ""


class TestWriteNpmAvailableVersionsTxt:
    def test_writes_versions_for_package(self, tmp_path):
        path = str(tmp_path / "available.txt")
        write_npm_available_versions_txt(
            path, ["lodash"], {"lodash": _svlist("4.17.20", "4.17.21")}
        )
        content = Path(path).read_text()
        assert "lodash" in content
        assert "4.17.21" in content

    def test_no_versions_writes_placeholder(self, tmp_path):
        path = str(tmp_path / "available.txt")
        write_npm_available_versions_txt(path, ["missing-pkg"], {})
        content = Path(path).read_text()
        assert "missing-pkg" in content
        assert "no versions" in content

    def test_empty_packages_writes_empty_file(self, tmp_path):
        path = str(tmp_path / "available.txt")
        write_npm_available_versions_txt(path, [], {})
        assert Path(path).read_text() == ""


# ---------------------------------------------------------------------------
# apply_updates helpers
# ---------------------------------------------------------------------------
# Use 'sv' (singular) to avoid collision with the existing _sv(*versions) helper above.


def sv(v):
    return SemVer.parse(v)


def _crit(pkg, major, version):
    return {pkg: {major: sv(version)}}


def _pv(pkg, *versions):
    return {pkg: {sv(v) for v in versions}}


def _av(pkg, *versions):
    return {pkg: [sv(v) for v in versions]}


def _run(
    pkg_json,
    criteria,
    pkg_versions=None,
    avail=None,
    constraints=None,
    lockfile=None,
    allow_ambiguous=False,
    keep_nested=False,
):
    entries = collect_direct_entries(pkg_json, ["dependencies", "devDependencies"])
    dc, oc, sk = apply_updates(
        package_json=pkg_json,
        direct_entries=entries,
        criteria=criteria,
        package_versions=pkg_versions or {},
        versions_by_package=avail or {},
        package_constraints=constraints or {},
        allow_ambiguous_highest_major=allow_ambiguous,
        keep_nested_overrides=keep_nested,
        npm_cmd="npm",
        npm_timeout=5,
        package_json_dir=".",
        registry=None,
        lockfile=lockfile if lockfile is not None else {},
    )
    return dc, oc, sk


# ---------------------------------------------------------------------------
# apply_updates tests
# ---------------------------------------------------------------------------


class TestApplyUpdatesDirect:
    def test_upgrades_direct_dep(self):
        pkg = {"dependencies": {"lodash": "^4.17.0"}, "overrides": {}}
        dc, _oc, _sk = _run(
            pkg,
            criteria=_crit("lodash", 4, "4.17.21"),
            pkg_versions=_pv("lodash", "4.17.21"),
            avail=_av("lodash", "4.17.21"),
        )
        assert len(dc) == 1
        assert dc[0]["package"] == "lodash"
        assert dc[0]["new_spec"] == "^4.17.21"
        assert pkg["dependencies"]["lodash"] == "^4.17.21"

    def test_preserves_range_prefix(self):
        pkg = {"dependencies": {"lodash": "~4.17.0"}, "overrides": {}}
        dc, _oc, _sk = _run(
            pkg,
            _crit("lodash", 4, "4.17.21"),
            _pv("lodash", "4.17.21"),
            _av("lodash", "4.17.21"),
        )
        assert dc[0]["new_spec"] == "~4.17.21"

    def test_no_prefix_exact_pin(self):
        pkg = {"dependencies": {"lodash": "4.17.0"}, "overrides": {}}
        dc, _oc, _sk = _run(
            pkg,
            _crit("lodash", 4, "4.17.21"),
            _pv("lodash", "4.17.21"),
            _av("lodash", "4.17.21"),
        )
        assert dc[0]["new_spec"] == "4.17.21"

    def test_already_meets_criteria_skipped(self):
        pkg = {"dependencies": {"lodash": "^4.17.21"}, "overrides": {}}
        dc, _oc, sk = _run(
            pkg,
            _crit("lodash", 4, "4.17.21"),
            _pv("lodash", "4.17.21"),
            _av("lodash", "4.17.21"),
        )
        assert dc == []
        assert any("already meets" in r["reason"] for r in sk)

    def test_no_criteria_for_current_major_skipped(self):
        pkg = {"dependencies": {"pkg": "^1.0.0"}, "overrides": {}}
        dc, _oc, sk = _run(pkg, {"pkg": {2: sv("2.0.0")}}, _pv("pkg", "2.0.0"), _av("pkg", "2.0.0"))
        assert dc == []
        assert any("no ADO criteria" in r["reason"] for r in sk)

    def test_non_registry_spec_skipped(self):
        pkg = {"dependencies": {"pkg": "file:../local"}, "overrides": {}}
        dc, _oc, sk = _run(pkg, _crit("pkg", 1, "1.2.0"), _pv("pkg", "1.2.0"), _av("pkg", "1.2.0"))
        assert dc == []
        assert any("non-registry" in r["reason"] for r in sk)

    def test_removes_stale_flat_override_on_adequate_direct(self):
        # direct dep at 3.4.11 satisfies criteria 3.4.0; stale override 3.4.0 < 3.4.11 → removed
        pkg = {
            "dependencies": {"dompurify": "^3.4.11"},
            "overrides": {"dompurify": "3.4.0"},
        }
        dc, oc, _sk = _run(
            pkg,
            _crit("dompurify", 3, "3.4.0"),
            _pv("dompurify", "3.4.0"),
            _av("dompurify", "3.4.11"),
        )
        assert "dompurify" not in pkg["overrides"]
        assert len(oc) == 1 and oc[0]["new_override"] == ""
        assert dc == []

    def test_stale_override_equal_to_current_not_removed(self):
        # override equals current (not a downgrade) → skip without removing override
        pkg = {"dependencies": {"pkg": "^3.4.0"}, "overrides": {"pkg": "3.4.0"}}
        _dc, _oc, _sk = _run(
            pkg, _crit("pkg", 3, "3.4.0"), _pv("pkg", "3.4.0"), _av("pkg", "3.4.0")
        )
        assert "pkg" in pkg["overrides"]

    def test_removes_flat_override_when_direct_dep_upgraded(self):
        pkg = {
            "dependencies": {"lodash": "^4.17.0"},
            "overrides": {"lodash": "4.17.10"},
        }
        dc, _oc, _sk = _run(
            pkg,
            _crit("lodash", 4, "4.17.21"),
            _pv("lodash", "4.17.21"),
            _av("lodash", "4.17.21"),
        )
        assert len(dc) == 1
        assert "lodash" not in pkg.get("overrides", {})


class TestApplyUpdatesOverrides:
    def test_flat_override_already_adequate_skipped(self):
        pkg = {"overrides": {"minimatch": "3.1.5"}}
        _dc, oc, sk = _run(
            pkg,
            _crit("minimatch", 3, "3.1.2"),
            _pv("minimatch", "3.1.2"),
            _av("minimatch", "3.1.5"),
        )
        assert oc == []
        assert any("already satisfies" in r["reason"] for r in sk)

    def test_flat_override_outdated_updated(self):
        # Existing override 3.0.4; ADO says > 3.0.4 (bad version); picks highest available above it.
        pkg = {"overrides": {"minimatch": "3.0.4"}}
        _dc, oc, _sk = _run(
            pkg,
            _crit("minimatch", 3, "3.0.4"),
            _pv("minimatch", "3.0.4"),
            _av("minimatch", "3.0.4", "3.1.2", "3.1.5"),
            constraints={"minimatch": ">"},
        )
        assert len(oc) == 1
        assert pkg["overrides"]["minimatch"] == "3.1.5"

    def test_single_major_transitive_flat_override_written(self):
        # minimatch is not a direct dep; single major; lockfile empty → writes flat override
        pkg = {"overrides": {}}
        _dc, oc, _sk = _run(
            pkg,
            _crit("minimatch", 3, "3.1.2"),
            _pv("minimatch", "3.1.2"),
            _av("minimatch", "3.1.2", "3.1.5"),
            lockfile={},
        )
        assert len(oc) == 1
        assert pkg["overrides"]["minimatch"] == "3.1.2"

    def test_installed_version_gte_selected_skips_override(self):
        # Hoisted minimatch@3.1.5 >= selected 3.1.2 → no override needed
        lf = {"packages": {"": {}, "node_modules/minimatch": {"version": "3.1.5"}}}
        pkg = {"overrides": {}}
        _dc, oc, sk = _run(
            pkg,
            _crit("minimatch", 3, "3.1.2"),
            _pv("minimatch", "3.1.2"),
            _av("minimatch", "3.1.2", "3.1.5"),
            lockfile=lf,
        )
        assert oc == []
        assert any("installed version" in r["reason"] for r in sk)

    def test_multi_major_no_dependents_ambiguous_skipped(self):
        pkg = {"overrides": {}}
        _dc, oc, sk = _run(
            pkg,
            {"minimatch": {3: sv("3.1.2"), 9: sv("9.0.1")}},
            _pv("minimatch", "3.1.2", "9.0.1"),
            {"minimatch": [sv("3.1.5"), sv("9.0.3")]},
            lockfile={},
            allow_ambiguous=False,
        )
        assert oc == []
        assert any("ambiguous" in r["reason"] for r in sk)

    def test_multi_major_nested_overrides_written(self):
        # eslint uses minimatch@3.1.5 (satisfies 3.x >= 3.1.2 → skip)
        # ts-node uses minimatch@9.0.0 (< 9.0.1 → write nested override)
        lf = {
            "packages": {
                "": {},
                "node_modules/eslint/node_modules/minimatch": {"version": "3.1.5"},
                "node_modules/ts-node/node_modules/minimatch": {"version": "9.0.0"},
            }
        }
        pkg = {
            "dependencies": {"eslint": "^8.0.0", "ts-node": "^10.0.0"},
            "overrides": {},
        }
        _dc, oc, _sk = _run(
            pkg,
            {"minimatch": {3: sv("3.1.2"), 9: sv("9.0.1")}},
            _pv("minimatch", "3.1.2", "9.0.1"),
            {"minimatch": [sv("3.1.2"), sv("3.1.5"), sv("9.0.1"), sv("9.0.3")]},
            lockfile=lf,
        )
        assert len(oc) == 1
        assert pkg["overrides"].get("ts-node", {}).get("minimatch") == "9.0.1"

    def test_multi_major_all_installed_adequate_skipped(self):
        lf = {
            "packages": {
                "": {},
                "node_modules/eslint/node_modules/minimatch": {"version": "3.1.5"},
                "node_modules/glob/node_modules/minimatch": {"version": "9.0.5"},
            }
        }
        pkg = {"dependencies": {"eslint": "^8.0.0", "glob": "^9.0.0"}, "overrides": {}}
        _dc, oc, sk = _run(
            pkg,
            {"minimatch": {3: sv("3.1.2"), 9: sv("9.0.1")}},
            _pv("minimatch", "3.1.2", "9.0.1"),
            {"minimatch": [sv("3.1.5"), sv("9.0.5")]},
            lockfile=lf,
        )
        assert oc == []
        assert any("installed version" in r["reason"] for r in sk)

    def test_overrides_not_dict_produces_skip(self):
        pkg = {"overrides": "bad-value"}
        dc, oc, sk = _run(pkg, _crit("minimatch", 3, "3.1.2"))
        assert dc == [] and oc == []
        assert any("not an object" in r["reason"] for r in sk)

    def test_keep_nested_overrides_flag(self):
        # With keep_nested=True, existing nested eslint.minimatch must NOT be removed
        pkg = {"overrides": {"eslint": {"minimatch": "3.0.0"}, "minimatch": "3.0.0"}}
        _run(
            pkg,
            _crit("minimatch", 3, "3.1.2"),
            _pv("minimatch", "3.1.2"),
            _av("minimatch", "3.1.5"),
            lockfile={},
            keep_nested=True,
        )
        assert "minimatch" in pkg["overrides"].get("eslint", {})

    def test_nested_override_removed_by_default(self):
        pkg = {"overrides": {"eslint": {"minimatch": "3.0.0"}, "minimatch": "3.0.0"}}
        _run(
            pkg,
            _crit("minimatch", 3, "3.1.2"),
            _pv("minimatch", "3.1.2"),
            _av("minimatch", "3.1.5"),
            lockfile={},
            keep_nested=False,
        )
        assert "minimatch" not in pkg["overrides"].get("eslint", {})
