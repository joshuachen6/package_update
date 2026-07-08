import json

import output.node as node
import output.node as out_node
from parsers.node import DirectEntry
from shared.semver import SemVer


def sv(v):
    return SemVer.parse(v)


def direct(pkg, spec, section="dependencies", container=None):
    container = container if container is not None else {pkg: spec}
    return DirectEntry(pkg, spec, section, f"{section}.{pkg}", container, pkg)


def test_write_package_versions_and_available_versions_txt(tmp_path):
    versions_path = tmp_path / "versions.txt"
    out_node.write_package_versions_txt(
        str(versions_path),
        {"b": {sv("2.0.0")}, "a": {sv("1.0.1"), sv("1.0.0")}},
        {"a": {1: sv("1.0.1")}},
    )
    text = versions_path.read_text()
    assert text.splitlines()[0].startswith("a: 1.0.0, 1.0.1 | criteria 1.x >= 1.0.1")
    assert "b: 2.0.0 |" in text

    available_path = tmp_path / "available.txt"
    out_node.write_npm_available_versions_txt(
        str(available_path),
        ["a", "missing"],
        {"a": [sv("1.0.0"), sv("1.0.1")]},
    )
    assert "a: 1.0.0, 1.0.1" in available_path.read_text()
    assert "missing: (no versions returned by npm view)" in available_path.read_text()


def test_apply_updates_rejects_non_object_overrides():
    pkg = {"overrides": "bad"}
    changes, overrides, skipped = out_node.apply_updates(pkg, [], {}, {}, {}, {}, False, False)
    assert changes == []
    assert overrides == []
    assert skipped[0]["reason"] == "package.json overrides exists but is not an object"


def test_apply_updates_direct_success_removes_flat_override():
    deps = {"lodash": "^4.17.0"}
    pkg = {"dependencies": deps, "overrides": {"lodash": "4.16.0"}}
    entry = direct("lodash", "^4.17.0", container=deps)

    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        [entry],
        {"lodash": {4: sv("4.17.21")}},
        {"lodash": {sv("4.17.21")}},
        {"lodash": [sv("4.17.21")]},
        {},
        False,
        False,
    )

    assert skipped == []
    assert override_changes == []
    assert pkg["dependencies"]["lodash"] == "^4.17.21"
    assert "lodash" not in pkg["overrides"]
    assert changes[0]["selected_version"] == "4.17.21"


def test_apply_updates_direct_skip_paths_and_remove_stale_override():
    deps = {"local": "file:../local", "bad": "latest", "ok": "^1.2.3"}
    pkg = {"dependencies": deps, "overrides": {"ok": "1.0.0"}}
    entries = [
        direct("local", "file:../local", container=deps),
        direct("bad", "latest", container=deps),
        direct("ok", "^1.2.3", container=deps),
    ]

    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        entries,
        {
            "local": {1: sv("1.0.1")},
            "bad": {1: sv("1.0.1")},
            "ok": {1: sv("1.2.0")},
        },
        {
            "local": {sv("1.0.1")},
            "bad": {sv("1.0.1")},
            "ok": {sv("1.2.0")},
        },
        {
            "local": [sv("1.0.1")],
            "bad": [sv("1.0.1")],
            "ok": [sv("1.2.0")],
        },
        {},
        False,
        False,
    )

    assert changes == []
    assert "ok" not in pkg["overrides"]
    assert override_changes[0]["package"] == "ok"
    reasons = {s["package"]: s["reason"] for s in skipped}
    assert reasons["local"] == "direct dependency uses non-registry spec"
    assert reasons["bad"] == "direct dependency has no semver current version"


def test_apply_updates_direct_no_current_major_skips_when_no_unblocked_same_major():
    deps = {"pkg": "^2.0.0"}
    entry = direct("pkg", "^2.0.0", container=deps)

    changes, override_changes, skipped = out_node.apply_updates(
        {"dependencies": deps},
        [entry],
        {"pkg": {1: sv("1.0.1")}},
        {"pkg": {sv("1.0.1")}},
        {"pkg": [sv("1.0.1")]},
        {},
        False,
        False,
    )

    assert changes == []
    assert override_changes == []
    assert (
        skipped[0]["reason"]
        == "no ADO criteria for direct dependency current major and no unblocked same-major update found"
    )


def test_apply_updates_existing_flat_override_paths():
    pkg = {"overrides": {"trans": "1.0.0", "parent": {"trans": "1.0.0"}}}

    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        [],
        {"trans": {1: sv("1.0.2")}},
        {"trans": {sv("1.0.2")}},
        {"trans": [sv("1.0.1"), sv("1.0.2")]},
        {},
        False,
        False,
    )

    assert changes == []
    assert skipped == []
    assert pkg["overrides"]["trans"] == "1.0.2"
    assert override_changes[0]["removed_nested_override_paths"] == "overrides.parent.trans"
    pkg2 = {"overrides": {"trans": "1.0.3"}}
    changes, override_changes, skipped = out_node.apply_updates(
        pkg2,
        [],
        {"trans": {1: sv("1.0.2")}},
        {"trans": {sv("1.0.2")}},
        {"trans": [sv("1.0.2"), sv("1.0.3")]},
        {},
        False,
        False,
    )
    assert skipped[0]["reason"] == "flat override already satisfies ADO criteria"

    pkg3 = {"overrides": {"trans": "1.0.1"}}
    changes, override_changes, skipped = out_node.apply_updates(
        pkg3,
        [],
        {"trans": {1: sv("1.0.2")}},
        {"trans": {sv("1.0.2")}},
        {"trans": [sv("1.0.1")]},
        {},
        False,
        False,
    )
    assert skipped == []
    assert override_changes[0]["old_override"] == "1.0.1"
    assert pkg3["overrides"]["trans"] == "1.0.2"


def test_apply_updates_multiple_majors_nested_overrides(monkeypatch):
    deps = {"top1": "^1.0.0", "top2": "^1.0.0"}
    entries = [
        direct("top1", "^1.0.0", container=deps),
        direct("top2", "^1.0.0", container=deps),
    ]
    lock = {
        "packages": {
            "": {},
            "node_modules/top1/node_modules/trans": {"version": "1.0.0"},
            "node_modules/top2/node_modules/trans": {"version": "2.0.0"},
        }
    }

    pkg = {"dependencies": deps, "overrides": {}}
    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        entries,
        {"trans": {1: sv("1.0.1"), 2: sv("2.0.1")}},
        {"trans": {sv("1.0.1"), sv("2.0.1")}},
        {"trans": [sv("1.0.1"), sv("2.0.1")]},
        {},
        False,
        False,
        lockfile=lock,
    )

    assert skipped == []
    assert changes == []
    assert pkg["overrides"]["top1"]["trans"] == "1.0.1"
    assert pkg["overrides"]["top2"]["trans"] == "2.0.1"
    assert "overrides.top1.trans=1.0.1" in override_changes[0]["new_override"]


def test_apply_updates_multiple_majors_ambiguous_and_highest_fallback():
    pkg = {"overrides": {}}
    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        [],
        {"trans": {1: sv("1.0.1"), 2: sv("2.0.1")}},
        {"trans": {sv("1.0.1"), sv("2.0.1")}},
        {"trans": [sv("1.0.1"), sv("2.0.1")]},
        {},
        False,
        False,
        lockfile={},
    )
    assert (
        skipped[0]["reason"]
        == "multiple ADO majors; lockfile returned no dependents, global override would be ambiguous"
    )
    pkg2 = {"overrides": {}}
    changes, override_changes, skipped = out_node.apply_updates(
        pkg2,
        [],
        {"trans": {1: sv("1.0.1"), 2: sv("2.0.1")}},
        {"trans": {sv("1.0.1"), sv("2.0.1")}},
        {"trans": [sv("1.0.1"), sv("2.0.1")]},
        {},
        True,
        False,
        lockfile={},
    )
    assert skipped == []
    assert pkg2["overrides"]["trans"] == "2.0.1"


def test_apply_updates_single_major_parent_update(monkeypatch):
    deps = {"parent": "^1.0.0"}
    entry = direct("parent", "^1.0.0", container=deps)
    lock = {
        "packages": {
            "": {},
            "node_modules/parent/node_modules/trans": {"version": "1.0.0"},
        }
    }
    monkeypatch.setattr(out_node, "resolve_transitive_with_parent", lambda *a, **k: [sv("1.0.2")])

    changes, override_changes, skipped = out_node.apply_updates(
        {"dependencies": deps, "overrides": {}},
        [entry],
        {"trans": {1: sv("1.0.1")}},
        {"trans": {sv("1.0.1")}},
        {"trans": [sv("1.0.1")], "parent": [sv("1.0.1"), sv("1.0.3")]},
        {},
        False,
        False,
        lockfile=lock,
    )

    assert skipped == []
    assert override_changes == []
    assert deps["parent"] == "^1.0.3"
    assert changes[0]["minimum_required"] == "transitive trans>=1.0.1"


def test_apply_updates_single_major_flat_override_and_installed_skip(monkeypatch):
    pkg = {"overrides": {"parent": {"trans": "1.0.0"}}}
    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        [],
        {"trans": {1: sv("1.0.1")}},
        {"trans": {sv("1.0.1")}},
        {"trans": [sv("1.0.1")]},
        {},
        False,
        False,
        lockfile={},
    )
    assert skipped == []
    assert "trans" not in pkg["overrides"]
    assert pkg["overrides"]["parent"]["trans"] == "1.0.1"
    assert override_changes[0]["old_override"] == "overrides.parent.trans=1.0.0"

    pkg2 = {"overrides": {}}
    changes, override_changes, skipped = out_node.apply_updates(
        pkg2,
        [],
        {"trans": {1: sv("1.0.1")}},
        {"trans": {sv("1.0.1")}},
        {"trans": [sv("1.0.1")]},
        {},
        False,
        False,
        lockfile={"packages": {"node_modules/trans": {"version": "1.0.2"}}},
    )
    assert skipped[0]["reason"] == "installed version already satisfies ADO criteria"


def test_check_and_fix_blocked_versions_updates_direct_and_override(monkeypatch):
    pkg = {
        "dependencies": {"a": "^1.0.0", "local": "file:../local"},
        "overrides": {"b": "1.0.0", "nested": {"c": "1.0.0"}},
    }

    def fake_blocked(package, version, registry, npm_cmd, timeout, project_dir):
        return package in {"a", "c"}, "blocked"

    monkeypatch.setattr(out_node, "is_version_blocked", fake_blocked)
    monkeypatch.setattr(
        out_node,
        "find_unblocked_version",
        lambda package, blocked, available, registry, npm_cmd, timeout, project_dir: (
            sv("1.0.1"),
            "",
        ),
    )
    monkeypatch.setattr(out_node, "npm_view_versions", lambda *a, **k: ("c", [sv("1.0.1")], ""))

    changes, errors = out_node.check_and_fix_blocked_versions(
        pkg,
        ["dependencies"],
        {"a": [sv("1.0.1")], "b": [sv("1.0.1")]},
        None,
        "npm",
        1,
        workers=1,
        show_progress=False,
    )

    assert errors == []
    assert pkg["dependencies"]["a"] == "^1.0.1"
    assert pkg["overrides"]["b"] == "1.0.0"
    assert pkg["overrides"]["nested"]["c"] == "1.0.1"
    assert {c["package"] for c in changes} == {"a", "c"}


def test_check_and_fix_blocked_versions_empty_parse_error_and_all_blocked(monkeypatch):
    assert out_node.check_and_fix_blocked_versions(
        {}, ["dependencies"], {}, None, "npm", 1, 1, False
    ) == ([], [])

    pkg = {"dependencies": {"a": "^1.0.0", "b": "^2.0.0"}}
    monkeypatch.setattr(out_node, "is_version_blocked", lambda *a, **k: (True, "blocked"))
    monkeypatch.setattr(out_node, "find_unblocked_version", lambda *a, **k: (None, "all blocked"))

    changes, errors = out_node.check_and_fix_blocked_versions(
        pkg,
        ["dependencies"],
        {"a": [sv("1.0.1")], "b": [sv("2.0.1")]},
        None,
        "npm",
        1,
        workers=1,
        show_progress=False,
    )

    assert changes == []
    assert {e["status"] for e in errors} == {"all_blocked"}


def test_write_package_json_output_and_backup(tmp_path, capsys):
    source = tmp_path / "package.json"
    output = tmp_path / "out.json"
    source.write_text('{"name": "old"}\n')

    out_node.write_package_json({"name": "new"}, str(output), str(source), False)
    assert json.loads(output.read_text()) == {"name": "new"}

    out_node.write_package_json({"name": "inplace"}, str(source), str(source), True)
    assert (tmp_path / "package.json.bak").exists()
    assert json.loads(source.read_text()) == {"name": "inplace"}
    out_node.write_package_json({"name": "again"}, str(source), str(source), True)
    assert "Backup already exists" in capsys.readouterr().out


def test_apply_updates_nested_override_is_read_and_updated_before_flat_fallback():
    pkg = {"overrides": {"parent": {"trans": "1.0.0"}}}
    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        [],
        {"trans": {1: sv("1.0.2")}},
        {"trans": {sv("1.0.2")}},
        {"trans": [sv("1.0.1"), sv("1.0.2")]},
        {},
        False,
        True,
        lockfile={},
    )

    assert changes == []
    assert skipped == []
    assert "trans" not in pkg["overrides"]
    assert pkg["overrides"]["parent"]["trans"] == "1.0.2"
    assert "overrides.parent.trans=1.0.0" in override_changes[0]["old_override"]
    assert "overrides.parent.trans=1.0.2" in override_changes[0]["new_override"]


def test_apply_updates_nested_override_already_satisfies_skips_without_flat_override():
    pkg = {"overrides": {"parent": {"trans": "1.0.3"}}}

    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        [],
        {"trans": {1: sv("1.0.2")}},
        {"trans": {sv("1.0.2")}},
        {"trans": [sv("1.0.2"), sv("1.0.3")]},
        {},
        False,
        False,
        lockfile={},
    )

    assert changes == []
    assert override_changes == []
    assert skipped[0]["reason"] == "override already satisfies ADO criteria"
    assert "trans" not in pkg["overrides"]
    assert pkg["overrides"]["parent"]["trans"] == "1.0.3"


def test_apply_updates_direct_success_removes_nested_override():
    deps = {"lodash": "^4.17.0"}
    pkg = {"dependencies": deps, "overrides": {"parent": {"lodash": "4.16.0"}}}
    entry = direct("lodash", "^4.17.0", container=deps)

    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        [entry],
        {"lodash": {4: sv("4.17.21")}},
        {"lodash": {sv("4.17.21")}},
        {"lodash": [sv("4.17.21")]},
        {},
        False,
        False,
    )

    assert skipped == []
    assert override_changes == []
    assert pkg["dependencies"]["lodash"] == "^4.17.21"
    assert "lodash" not in pkg["overrides"]["parent"]
    assert changes[0]["selected_version"] == "4.17.21"


def test_check_and_fix_blocked_versions_dedupes_change_rows_but_updates_all_locations(
    monkeypatch,
):
    package_json = {
        "dependencies": {"pkg": "^1.0.0"},
        "overrides": {"pkg": "1.0.0"},
    }

    blocked_calls = []

    def fake_is_version_blocked(pkg, version, registry, npm_cmd, timeout, project_dir):
        blocked_calls.append((pkg, version))
        return True, "blocked"

    def fake_find_unblocked_version(
        pkg, blocked, versions, registry, npm_cmd, timeout, project_dir
    ):
        return SemVer.parse("1.0.1"), ""

    monkeypatch.setattr(node, "is_version_blocked", fake_is_version_blocked)
    monkeypatch.setattr(node, "find_unblocked_version", fake_find_unblocked_version)

    changes, errors = node.check_and_fix_blocked_versions(
        package_json,
        ["dependencies"],
        {"pkg": [SemVer.parse("1.0.1")]},
        None,
        "npm",
        10,
        2,
        False,
    )

    assert errors == []
    assert blocked_calls == [("pkg", "1.0.0")]
    assert changes == [{"package": "pkg", "blocked_version": "1.0.0", "unblocked_version": "1.0.1"}]
    assert package_json["dependencies"]["pkg"] == "^1.0.1"
    assert package_json["overrides"]["pkg"] == "1.0.1"


def test_apply_updates_direct_no_current_major_uses_unblocked_same_major(monkeypatch):
    deps = {"pkg": "^2.0.0"}
    entry = direct("pkg", "^2.0.0", container=deps)
    monkeypatch.setattr(
        out_node,
        "find_unblocked_version",
        lambda package, current, available, registry, npm_cmd, timeout, project_dir: (
            sv("2.0.1"),
            "",
        ),
    )

    changes, override_changes, skipped = out_node.apply_updates(
        {"dependencies": deps},
        [entry],
        {"pkg": {1: sv("1.0.1")}},
        {"pkg": {sv("1.0.1")}},
        {"pkg": [sv("1.0.1"), sv("2.0.1")]},
        {},
        False,
        False,
    )

    assert skipped == []
    assert override_changes == []
    assert deps["pkg"] == "^2.0.1"
    assert changes[0]["selected_version"] == "2.0.1"


def test_apply_updates_transitive_no_current_major_uses_unblocked_same_major_override(monkeypatch):
    pkg = {"overrides": {}}
    lock = {"packages": {"node_modules/trans": {"version": "2.0.0"}}}
    monkeypatch.setattr(
        out_node,
        "find_unblocked_version",
        lambda package, current, available, registry, npm_cmd, timeout, project_dir: (
            sv("2.0.1"),
            "",
        ),
    )

    changes, override_changes, skipped = out_node.apply_updates(
        pkg,
        [],
        {"trans": {1: sv("1.0.1")}},
        {"trans": {sv("1.0.1")}},
        {"trans": [sv("1.0.1"), sv("2.0.1")]},
        {},
        False,
        False,
        lockfile=lock,
    )
    assert changes == []
    assert skipped == []
    assert pkg["overrides"]["trans"] == "2.0.1"
    assert override_changes[0]["new_override"] == "2.0.1"
