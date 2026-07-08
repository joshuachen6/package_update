import json
import subprocess as real_subprocess
from pathlib import Path

import parsers.node as node
from shared.semver import SemVer


class DummyCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_remove_nested_override_keys_removes_nested_but_not_top_level():
    overrides = {
        "target": "1.0.0",
        "parent": {
            "target": "2.0.0",
            "child": {"target": "3.0.0", "keep": "x"},
        },
        "other": "ok",
    }

    removed = node.remove_nested_override_keys(overrides, "target")
    assert removed == ["overrides.parent.target", "overrides.parent.child.target"]
    assert overrides["target"] == "1.0.0"
    assert "target" not in overrides["parent"]
    assert "target" not in overrides["parent"]["child"]
    assert overrides["other"] == "ok"


def test_remove_nested_override_keys_ignores_non_dict():
    assert node.remove_nested_override_keys(["not", "dict"], "target") == []


def test_npm_view_versions_success_with_registry(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text, shell, timeout, cwd):
        calls.append(cmd)
        return DummyCompleted(stdout='["1.0.0", "1.2.0"]')

    monkeypatch.setattr(node.subprocess, "run", fake_run)

    package, versions, error = node.npm_view_versions(
        "pkg", "https://registry.example", "npm", 5, cwd="."
    )

    assert package == "pkg"
    assert versions == [SemVer.parse("1.0.0"), SemVer.parse("1.2.0")]
    assert error == ""
    assert "--registry" in calls[0]


def test_npm_view_versions_timeout_and_failure(monkeypatch):
    def timeout_run(*args, **kwargs):
        raise real_subprocess.TimeoutExpired("npm", 2)

    monkeypatch.setattr(node.subprocess, "run", timeout_run)
    assert node.npm_view_versions("pkg", None, "npm", 2)[2] == "timeout after 2s"

    def failing_run(*args, **kwargs):
        return DummyCompleted(returncode=1, stderr="registry denied")

    monkeypatch.setattr(node.subprocess, "run", failing_run)
    package, versions, error = node.npm_view_versions("pkg", None, "npm", 2)
    assert package == "pkg"
    assert versions == []
    assert error == "registry denied"


def test_npm_view_versions_parse_exception(monkeypatch):
    def ok_run(*args, **kwargs):
        return DummyCompleted(stdout="[]")

    def boom(stdout):
        raise ValueError("bad json")

    monkeypatch.setattr(node.subprocess, "run", ok_run)
    monkeypatch.setattr(node, "parse_npm_versions_stdout", boom)

    assert "failed to parse npm view output" in node.npm_view_versions("pkg", None, "npm", 1)[2]


def test_parallel_npm_versions_collects_errors(monkeypatch):
    def fake_view(pkg, registry, npm_cmd, timeout, cwd):
        if pkg == "bad":
            return pkg, [], "nope"
        return pkg, [SemVer.parse("1.0.0")], ""

    monkeypatch.setattr(node, "npm_view_versions", fake_view)

    versions, errors = node.parallel_npm_versions(
        ["good", "bad"], None, "npm", 1, workers=2, show_progress=False
    )

    assert versions["good"] == [SemVer.parse("1.0.0")]
    assert versions["bad"] == []
    assert errors == [{"package": "bad", "error": "nope"}]


def test_is_version_blocked_for_success_forbidden_timeout_and_other_error(monkeypatch):
    def success_run(*args, **kwargs):
        return DummyCompleted(returncode=0)

    monkeypatch.setattr(node.subprocess, "run", success_run)
    assert node.is_version_blocked("pkg", "1.0.0", None, "npm", 1) == (False, "")

    def forbidden_run(*args, **kwargs):
        return DummyCompleted(returncode=1, stderr="403 Forbidden")

    monkeypatch.setattr(node.subprocess, "run", forbidden_run)
    blocked, snippet = node.is_version_blocked("pkg", "1.0.1", None, "npm", 1)
    assert blocked is True
    assert "403" in snippet

    def timeout_run(*args, **kwargs):
        raise real_subprocess.TimeoutExpired("npm", 7)

    monkeypatch.setattr(node.subprocess, "run", timeout_run)
    assert node.is_version_blocked("pkg", "1.0.2", None, "npm", 7)[0] is False
    assert "timeout after 7s" in node.is_version_blocked("pkg", "1.0.2", None, "npm", 7)[1]

    def other_failure(*args, **kwargs):
        return DummyCompleted(returncode=2, stdout="network broke")

    monkeypatch.setattr(node.subprocess, "run", other_failure)
    blocked, snippet = node.is_version_blocked("pkg", "1.0.3", None, "npm", 1)
    assert blocked is False
    assert snippet == "network broke"


def test_find_unblocked_version_uses_lowest_same_major(monkeypatch):
    checked = []

    def fake_blocked(package, version, registry, npm_cmd, timeout, project_dir):
        checked.append(version)
        return version == "1.0.1", "blocked"

    monkeypatch.setattr(node, "is_version_blocked", fake_blocked)

    result, reason = node.find_unblocked_version(
        "pkg",
        SemVer.parse("1.0.0"),
        [SemVer.parse("1.0.2"), SemVer.parse("2.0.0"), SemVer.parse("1.0.1")],
        None,
        "npm",
        1,
    )
    assert result == SemVer.parse("1.0.2")
    assert reason == ""
    assert checked == ["1.0.1", "1.0.2"]


def test_find_unblocked_version_tries_lower_same_major_after_forward_blocked(monkeypatch):
    checked = []

    def fake_blocked(package, version, registry, npm_cmd, timeout, project_dir):
        checked.append(version)
        return version != "1.0.4", "blocked"

    monkeypatch.setattr(node, "is_version_blocked", fake_blocked)
    result, reason = node.find_unblocked_version(
        "pkg",
        SemVer.parse("1.0.5"),
        [
            SemVer.parse("1.0.7"),
            SemVer.parse("1.0.4"),
            SemVer.parse("1.0.3"),
            SemVer.parse("2.0.0"),
            SemVer.parse("0.9.9"),
        ],
        None,
        "npm",
        1,
    )

    assert result == SemVer.parse("1.0.4")
    assert reason == ""
    assert checked == ["1.0.7", "1.0.4"]
def test_find_unblocked_version_reports_all_blocked(monkeypatch):
    monkeypatch.setattr(node, "is_version_blocked", lambda *args, **kwargs: (True, "blocked"))
    result, reason = node.find_unblocked_version(
        "pkg",
        SemVer.parse("1.0.1"),
        [SemVer.parse("1.0.0"), SemVer.parse("1.0.2")],
        None,
        "npm",
        1,
    )
    assert result is None
    assert "all 1 candidates above 1.0.1 and 1 candidates below 1.0.1" in reason


def test_find_top_level_dependents_by_major_success_and_bad_outputs(monkeypatch):
    tree = {
        "dependencies": {
            "direct-a": {
                "version": "1.0.0",
                "dependencies": {"target": {"version": "2.1.0"}},
            },
            "target": {"version": "2.2.0"},
            "direct-b": {
                "version": "1.0.0",
                "dependencies": {
                    "middle": {
                        "version": "1.0.0",
                        "dependencies": {"target": {"version": "3.0.0"}},
                    }
                },
            },
        }
    }
    monkeypatch.setattr(
        node.subprocess,
        "run",
        lambda *args, **kwargs: DummyCompleted(stdout=json.dumps(tree)),
    )

    result = node.find_top_level_dependents_by_major("target", "npm", 1, ".")
    assert result == {2: {"direct-a"}, 3: {"direct-b"}}

    monkeypatch.setattr(node.subprocess, "run", lambda *args, **kwargs: DummyCompleted(stdout=""))
    assert node.find_top_level_dependents_by_major("target", "npm", 1, ".") == {}

    monkeypatch.setattr(
        node.subprocess, "run", lambda *args, **kwargs: DummyCompleted(stdout="{bad")
    )
    assert node.find_top_level_dependents_by_major("target", "npm", 1, ".") == {}

    def raises(*args, **kwargs):
        raise OSError("missing npm")

    monkeypatch.setattr(node.subprocess, "run", raises)
    assert node.find_top_level_dependents_by_major("target", "npm", 1, ".") == {}


def test_load_or_generate_lockfile_existing_and_generated(tmp_path, monkeypatch):
    existing = tmp_path / "package-lock.json"
    existing.write_text(json.dumps({"packages": {"node_modules/pkg": {"version": "1.0.0"}}}))

    assert node._load_or_generate_lockfile(str(tmp_path), {}, "npm", 1)["packages"]

    existing.write_text("{bad")
    generated_locks = []

    def fake_run(cmd, capture_output, text, timeout, cwd, shell):
        generated = Path(cwd) / "package-lock.json"
        generated.write_text(json.dumps({"dependencies": {"pkg": {"version": "1.0.0"}}}))
        generated_locks.append(generated)
        return DummyCompleted(returncode=0)

    monkeypatch.setattr(node.subprocess, "run", fake_run)

    loaded = node._load_or_generate_lockfile(
        str(tmp_path), {"dependencies": {"pkg": "1.0.0"}}, "npm", 1
    )
    assert loaded["dependencies"]["pkg"]["version"] == "1.0.0"
    assert generated_locks


def test_load_or_generate_lockfile_returns_none_on_generation_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        node.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("boom")),
    )

    assert node._load_or_generate_lockfile(str(tmp_path), {}, "npm", 1) is None


def test_package_names_from_lockfile_v3_and_v1():
    v3 = {
        "packages": {
            "": {},
            "node_modules/a": {"version": "1.0.0"},
            "node_modules/parent/node_modules/b": {"version": "2.0.0"},
        }
    }
    assert node._package_names_from_lockfile(v3) == {"a", "b"}

    v1 = {"dependencies": {"a": {"version": "1.0.0", "dependencies": {"b": {"version": "2.0.0"}}}}}
    assert node._package_names_from_lockfile(v1) == {"a", "b"}


def test_collect_lockfile_packages_existing_and_generated(tmp_path, monkeypatch):
    lock = tmp_path / "package-lock.json"
    lock.write_text(json.dumps({"packages": {"node_modules/a": {"version": "1.0.0"}}}))

    assert node.collect_lockfile_packages({}, "npm", 1, str(tmp_path)) == {"a"}

    lock.write_text("{bad")

    def fake_run(cmd, capture_output, text, timeout, cwd, shell):
        Path(cwd, "package-lock.json").write_text(
            json.dumps({"packages": {"node_modules/b": {"version": "2.0.0"}}})
        )
        return DummyCompleted(returncode=0)

    monkeypatch.setattr(node.subprocess, "run", fake_run)
    assert node.collect_lockfile_packages(
        {"dependencies": {"b": "2.0.0"}}, "npm", 1, str(tmp_path)
    ) == {"b"}


def test_collect_lockfile_packages_returns_empty_on_generation_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(
        node.subprocess, "run", lambda *args, **kwargs: DummyCompleted(returncode=1)
    )
    assert node.collect_lockfile_packages({}, "npm", 1, str(tmp_path)) == set()

    monkeypatch.setattr(
        node.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("boom")),
    )
    assert node.collect_lockfile_packages({}, "npm", 1, str(tmp_path)) == set()


def test_resolve_transitive_with_parent_success_v3_and_v1(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".npmrc").write_text("registry=https://registry.example")

    calls = []

    def fake_run_v3(cmd, capture_output, text, timeout, cwd, shell):
        calls.append(cmd)
        Path(cwd, "package-lock.json").write_text(
            json.dumps(
                {
                    "packages": {
                        "node_modules/transitive": {"version": "2.0.0"},
                        "node_modules/other": {"version": "1.0.0"},
                    }
                }
            )
        )
        return DummyCompleted(returncode=0)

    monkeypatch.setattr(node.subprocess, "run", fake_run_v3)

    versions = node.resolve_transitive_with_parent(
        "parent",
        "^2.0.0",
        "dependencies",
        "transitive",
        {
            "dependencies": {"parent": "^1.0.0"},
            "overrides": {"transitive": "1.0.0", "parent": {"transitive": "1.0.0"}},
        },
        "npm",
        1,
        str(project),
        registry="https://registry.example",
    )

    assert versions == [SemVer.parse("2.0.0")]
    assert "--registry" in calls[0]

    def fake_run_v1(cmd, capture_output, text, timeout, cwd, shell):
        Path(cwd, "package-lock.json").write_text(
            json.dumps(
                {
                    "dependencies": {
                        "parent": {
                            "version": "2.0.0",
                            "dependencies": {"transitive": {"version": "3.0.0"}},
                        }
                    }
                }
            )
        )
        return DummyCompleted(returncode=0)

    monkeypatch.setattr(node.subprocess, "run", fake_run_v1)

    versions = node.resolve_transitive_with_parent(
        "parent",
        "^2.0.0",
        "dependencies",
        "transitive",
        {"dependencies": {"parent": "^1.0.0"}},
        "npm",
        1,
        str(project),
    )

    assert versions == [SemVer.parse("3.0.0")]


def test_resolve_transitive_with_parent_failure_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(
        node.subprocess, "run", lambda *args, **kwargs: DummyCompleted(returncode=1)
    )
    assert (
        node.resolve_transitive_with_parent(
            "p",
            "1.0.0",
            "dependencies",
            "t",
            {"dependencies": {"p": "0.1.0"}},
            "npm",
            1,
            str(tmp_path),
        )
        is None
    )

    def timeout(*args, **kwargs):
        raise real_subprocess.TimeoutExpired("npm", 1)

    monkeypatch.setattr(node.subprocess, "run", timeout)
    assert (
        node.resolve_transitive_with_parent(
            "p",
            "1.0.0",
            "dependencies",
            "t",
            {"dependencies": {"p": "0.1.0"}},
            "npm",
            1,
            str(tmp_path),
        )
        is None
    )


def test_find_top_level_dependents_from_lockfile_hoisted_requires_graph():
    lockfile = {
        "packages": {
            "": {},
            "node_modules/target": {"version": "4.0.0"},
            "node_modules/top": {"version": "1.0.0"},
        },
        "dependencies": {
            "top": {"version": "1.0.0", "requires": {"middle": "^1"}},
            "middle": {"version": "1.0.0", "requires": {"target": "^4"}},
            "target": {"version": "4.0.0"},
        },
    }

    result = node.find_top_level_dependents_from_lockfile("target", lockfile, {"top", "target"})
    assert result == {4: {"top"}}


def test_extract_ado_package_versions_osv_and_claude(monkeypatch, tmp_path):
    csv_path = tmp_path / "tasks.csv"
    csv_path.write_text("unused")

    rows = [
        (101, "CVE-2026-0001 vulnerable package", "CVE fixed in 1.2.3"),
        (102, "Manual package mention", "upgrade lodash to 4.17.21"),
        (103, "No version", "nothing useful here"),
    ]

    monkeypatch.setattr(node, "read_csv_full_rows", lambda path, columns: rows)
    monkeypatch.setattr(
        node,
        "collect_lockfile_packages",
        lambda *args, **kwargs: {"lodash", "transitive"},
    )

    import resolver.claude_resolver as claude_resolver
    import shared.cve_lookup as cve_lookup

    monkeypatch.setattr(
        cve_lookup,
        "extract_advisory_id",
        lambda title: "CVE-2026-0001" if "CVE" in title else None,
    )
    monkeypatch.setattr(
        cve_lookup,
        "prefetch_advisories",
        lambda rows, ecosystem: {"CVE-2026-0001": {"transitive": ["1.2.3"]}},
    )

    def fake_batch(tasks, all_packages, **kwargs):
        assert tasks == [(102, "upgrade lodash to 4.17.21")]
        assert "transitive" in all_packages
        return {0: {"lodash": ">="}}, []

    monkeypatch.setattr(claude_resolver, "batch_resolve", fake_batch)

    versions, task_ids, constraints, osv_packages = node.extract_ado_package_versions(
        str(csv_path),
        None,
        {"lodash"},
        show_progress=False,
        package_json={"dependencies": {"lodash": "4.17.0"}},
        npm_cmd="npm",
        project_dir=str(tmp_path),
    )

    assert versions["transitive"] == {SemVer.parse("1.2.3")}
    assert versions["lodash"] == {SemVer.parse("4.17.21")}
    assert task_ids["transitive"] == {101}
    assert task_ids["lodash"] == {102}
    assert constraints == {"transitive": ">=", "lodash": ">="}
    assert osv_packages == {"transitive"}


def test_collect_override_entries_reads_full_hierarchy():
    pkg = {
        "overrides": {
            "flat": "1.0.0",
            "parent": {
                "nested": "2.0.0",
                "child": {"deep": "3.0.0"},
            },
        }
    }

    entries = node.collect_override_entries(pkg)
    by_path = {entry.path: (entry.package, entry.spec) for entry in entries}

    assert by_path["overrides.flat"] == ("flat", "1.0.0")
    assert by_path["overrides.parent.nested"] == ("nested", "2.0.0")
    assert by_path["overrides.parent.child.deep"] == ("deep", "3.0.0")


def test_find_override_entries_reads_nested_matches():
    overrides = {
        "target": "1.0.0",
        "parent": {"target": "2.0.0", "child": {"target": "3.0.0"}},
    }
    entries = node.find_override_entries(overrides, "target")

    assert [entry.path for entry in entries] == [
        "overrides.target",
        "overrides.parent.target",
        "overrides.parent.child.target",
    ]
def test_find_unblocked_version_filters_cve_versions_before_block_check(monkeypatch):
    checked = []

    def fake_filter(ecosystem, package, versions, xray_host=None, auth=None, timeout=30):
        assert ecosystem == "npm"
        assert package == "pkg"
        return [v for v in versions if str(v) != "1.0.1"], {"npm://pkg:1.0.1": ["CVE-1"]}, ""

    def fake_blocked(package, version, registry, npm_cmd, timeout, project_dir):
        checked.append(version)
        return False, ""

    monkeypatch.setattr(node, "filter_versions_without_cves", fake_filter)
    monkeypatch.setattr(node, "is_version_blocked", fake_blocked)
    result, reason = node.find_unblocked_version(
        "pkg",
        SemVer.parse("1.0.0"),
        [SemVer.parse("1.0.1"), SemVer.parse("1.0.2")],
        None,
        "npm",
        1,
    )

    assert result == SemVer.parse("1.0.2")
    assert reason == ""
    assert checked == ["1.0.2"]
