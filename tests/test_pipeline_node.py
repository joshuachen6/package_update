import json
import sys
import types

import pipeline.node as pipeline_node


def install_node_modules(
    monkeypatch,
    *,
    extra_direct=False,
    skip_apply=False,
    block_changes=None,
    osv_packages=None,
):
    out_node = types.ModuleType("output.node")
    parsers_node = types.ModuleType("parsers.node")
    resolver = types.ModuleType("resolver.resolver")
    utils = types.ModuleType("shared.utils")
    ado_tags = types.ModuleType("shared.ado_tags")
    calls = {"csv": [], "packages_queries": [], "tagged": [], "block_called": False}

    def ensure_dir(path):
        import pathlib

        pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    def write_csv_rows(path, rows, columns):
        calls["csv"].append((path, rows, columns))

    utils.ensure_dir = ensure_dir
    utils.write_csv_rows = write_csv_rows

    class Entry:
        def __init__(self, package, spec):
            self.package = package
            self.spec = spec
            self.section = "dependencies"
            self.path = f"dependencies.{package}"
            self.container = {}
            self.key = package

    entries = [Entry("direct", "^1.0.0")]
    if extra_direct:
        entries.append(Entry("extra", "^1.0.0"))

    parsers_node.parse_sections = lambda value: ["dependencies", "devDependencies"]
    parsers_node.collect_direct_entries = lambda pkg, sections: entries
    parsers_node.collect_known_packages = lambda pkg: {"direct", "trans"}
    parsers_node.extract_ado_package_versions = lambda *args, **kwargs: (
        {"direct": {"1.0.1"}, "trans": {"2.0.1"}},
        {"direct": {101}, "trans": {102}, "blockonly": {103}},
        {"direct": ">=", "trans": ">="},
        osv_packages if osv_packages is not None else {"trans"},
    )
    parsers_node._load_or_generate_lockfile = lambda *args, **kwargs: {"packages": {}}
    parsers_node.should_skip_spec = lambda spec: spec.startswith("file:")
    parsers_node.parallel_npm_versions = (
        lambda packages, registry, npm_cmd, timeout, workers, show_progress, cwd: (
            calls["packages_queries"].append(list(packages))
            or {pkg: ["9.9.9"] for pkg in packages},
            [{"package": "err", "error": "nope"}] if packages and packages[0] == "direct" else [],
        )
    )

    resolver.highest_ado_criteria_by_major = lambda pkg_versions: {
        "direct": {1: "1.0.1"},
        "trans": {2: "2.0.1"},
    }

    out_node.write_package_versions_txt = lambda path, versions, criteria: calls.setdefault(
        "version_txt", path
    )
    out_node.write_npm_available_versions_txt = lambda path, packages, versions: calls.setdefault(
        "available_txt", path
    )

    def apply_updates(**kwargs):
        if skip_apply:
            return (
                [],
                [],
                [
                    {
                        "package": "unchanged",
                        "reason": "no update",
                        "details": "why",
                        "current": "1.0.0",
                        "target": "1.0.1",
                    }
                ],
            )
        return (
            [{"package": "direct", "old_spec": "^1.0.0", "new_spec": "^1.0.1"}],
            [
                {
                    "package": "trans",
                    "old_override": "",
                    "new_override": "overrides.parent.trans=2.0.1; overrides.other.trans=2.0.2",
                }
            ],
            [
                {
                    "package": "direct",
                    "reason": "already changed",
                    "details": "",
                    "current": "1.0.0",
                    "target": "1.0.1",
                }
            ],
        )

    out_node.apply_updates = apply_updates

    def check_and_fix_blocked_versions(**kwargs):
        calls["block_called"] = True
        return (
            block_changes
            if block_changes is not None
            else [
                {
                    "package": "direct",
                    "blocked_version": "1.0.1",
                    "unblocked_version": "1.0.2",
                },
                {
                    "package": "blockonly",
                    "blocked_version": "0.1.0",
                    "unblocked_version": "0.1.1",
                },
            ],
            [
                {
                    "package": "bad",
                    "blocked_version": "1.0.0",
                    "status": "all_blocked",
                    "error": "no",
                }
            ],
        )

    out_node.check_and_fix_blocked_versions = check_and_fix_blocked_versions

    def tag_display_changes(records, task_ids):
        calls["tagged"].append((records, task_ids))
        for record in records:
            record["task_ids"] = sorted(task_ids.get(record.get("package", ""), set()))

    ado_tags.tag_display_changes = tag_display_changes

    monkeypatch.setitem(sys.modules, "output.node", out_node)
    monkeypatch.setitem(sys.modules, "parsers.node", parsers_node)
    monkeypatch.setitem(sys.modules, "resolver.resolver", resolver)
    monkeypatch.setitem(sys.modules, "shared.utils", utils)
    monkeypatch.setitem(sys.modules, "shared.ado_tags", ado_tags)
    return calls


def test_analyze_node_full_success_with_block_check_and_extra_prefetch(tmp_path, monkeypatch):
    pkg_path = tmp_path / "package.json"
    pkg_path.write_text(json.dumps({"dependencies": {"direct": "^1.0.0", "extra": "^1.0.0"}}))
    calls = install_node_modules(monkeypatch, extra_direct=True)

    result = pipeline_node.analyze_node(
        str(tmp_path / "tasks.csv"),
        str(pkg_path),
        str(tmp_path / "logs"),
        ["title"],
        npm_cmd="npm",
        npm_timeout=5,
        workers=2,
        registry="https://registry",
        skip_block_check=False,
    )

    assert calls["packages_queries"][0] == ["direct", "trans"]
    assert calls["packages_queries"][1] == ["extra"]
    assert calls["block_called"] is True
    assert [r["package"] for r in result["display_changes"]] == [
        "direct",
        "trans",
        "blockonly",
    ]
    assert result["display_changes"][0]["new"] == "1.0.2"
    assert result["display_changes"][1]["new"] == "2.0.1, 2.0.2"
    assert result["display_changes"][1]["nlp_resolved"] is False
    assert result["pkg_json_path"] == str(pkg_path)
    assert result["pkg_json_dir"] == str(tmp_path)
    assert any(path.endswith("block-check-errors.csv") for path, _, _ in calls["csv"])


def test_analyze_node_skip_block_check_and_skipped_display(tmp_path, monkeypatch):
    pkg_path = tmp_path / "package.json"
    pkg_path.write_text(json.dumps({"dependencies": {"direct": "^1.0.0"}}))
    calls = install_node_modules(monkeypatch, skip_apply=True)

    result = pipeline_node.analyze_node(
        str(tmp_path / "tasks.csv"),
        str(pkg_path),
        str(tmp_path / "logs"),
        ["title"],
        skip_block_check=True,
    )

    assert calls["block_called"] is False
    assert result["display_changes"] == []
    assert result["skipped_display"][0]["package"] == "unchanged"
    assert result["skipped_display"][0]["detail"] == "why"
    assert not any(path.endswith("block-check-changes.csv") for path, _, _ in calls["csv"])


def test_analyze_node_block_fix_does_not_lower_existing_display_version(tmp_path, monkeypatch):
    pkg_path = tmp_path / "package.json"
    pkg_path.write_text(json.dumps({"dependencies": {"direct": "^1.0.0"}}))
    install_node_modules(
        monkeypatch,
        block_changes=[
            {
                "package": "direct",
                "blocked_version": "1.0.1",
                "unblocked_version": "1.0.0",
            }
        ],
    )

    result = pipeline_node.analyze_node(
        str(tmp_path / "tasks.csv"),
        str(pkg_path),
        str(tmp_path / "logs"),
        ["title"],
        skip_block_check=False,
    )
    direct = next(r for r in result["display_changes"] if r["package"] == "direct")
    assert direct["new"] == "^1.0.1"
