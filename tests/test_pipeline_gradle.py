import sys
import types
from pathlib import Path

import pytest

import pipeline.gradle as pipeline_gradle


def install_gradle_modules(
    monkeypatch,
    *,
    tree_output="tree",
    tree_err="",
    bumped=None,
    csv_versions=None,
    csv_constraints=None,
    installed=None,
    parents_of=None,
    osv_packages=None,
    apply_result=None,
    fetch_errs=None,
    deps_override=None,
):
    out_gradle = types.ModuleType("output.gradle")
    parsers_gradle = types.ModuleType("parsers.gradle")
    parsers_tree = types.ModuleType("parsers.gradle_tree")
    utils = types.ModuleType("shared.utils")
    ado_tags = types.ModuleType("shared.ado_tags")
    loguru = types.ModuleType("loguru")

    calls = {"csv": [], "tagged": [], "normalized": [], "tree_kwargs": [], "fetch_calls": []}

    class Logger:
        def warning(self, message):
            calls.setdefault("warnings", []).append(message)

    loguru.logger = Logger()

    deps = deps_override or [
        types.SimpleNamespace(group="org.example", artifact="lib", version="1.0.0"),
        types.SimpleNamespace(group="org.example", artifact="parent", version="1.0.0"),
    ]

    def ensure_dir(path):
        Path(path).mkdir(parents=True, exist_ok=True)

    def write_csv_rows(path, rows, columns):
        calls["csv"].append((path, rows, columns))

    utils.ensure_dir = ensure_dir
    utils.write_csv_rows = write_csv_rows

    parsers_gradle._fuzzy_keywords = lambda key: {"lib", "example"}
    parsers_gradle.parse_gradle_deps = lambda build_text: deps

    def parallel_fetch_versions(deps_arg, base_url, auth, timeout, workers, show_progress):
        keys = [f"{d.group}:{d.artifact}" for d in deps_arg]
        calls["fetch_calls"].append(keys)
        if len(calls["fetch_calls"]) == 1:
            return (
                {"org.example:lib": ["1.0.1"]},
                fetch_errs if fetch_errs is not None else [],
            )
        return ({key: ["1.0.1"] for key in keys}, [])

    parsers_gradle.parallel_fetch_versions = parallel_fetch_versions
    parsers_gradle.collect_known_packages = lambda deps, dep_tree_installed=None: {
        "org.example:lib"
    }
    parsers_gradle.extract_ado_versions = lambda csv_path, columns, known, show_progress: (
        csv_versions if csv_versions is not None else {"org.example:lib": {"1.0.1"}},
        {"org.example:lib": {101}},
        csv_constraints if csv_constraints is not None else {"org.example:lib": ">="},
        osv_packages if osv_packages is not None else {"org.example:osv"},
    )

    parsers_tree.get_gradle_cmd = lambda project_dir: "gradle"

    def run_gradle_dependencies_with_fallback(**kwargs):
        calls["tree_kwargs"].append(kwargs)
        return (
            tree_output,
            tree_err,
            bumped if bumped is not None else ["org.example:parent"],
        )

    parsers_tree.run_gradle_dependencies_with_fallback = run_gradle_dependencies_with_fallback
    parsers_tree.parse_gradle_dep_tree = lambda output: (
        installed if installed is not None else {"org.example:lib": "1.0.0"},
        parents_of if parents_of is not None else {"org.example:lib": {"org.example:parent"}},
    )

    out_gradle.apply_updates = lambda **kwargs: (
        apply_result
        if apply_result is not None
        else (
            [
                {
                    "dependency": "org.example:lib",
                    "old_version": "1.0.0",
                    "new_version": "1.0.1",
                    "ado_guided": "yes",
                }
            ],
            [
                {
                    "dependency": "org.example:skip",
                    "reason": "already ok",
                    "current": "1.0.1",
                    "target": "1.0.0",
                }
            ],
            [
                {
                    "dependency": "org.example:force",
                    "old_version": "1.0.0",
                    "new_version": "1.0.2",
                    "minimum_required": "1.0.2",
                }
            ],
        )
    )

    def normalize_task_ids(task_ids, deps, installed):
        calls["normalized"].append((task_ids, installed))
        return task_ids

    def tag_display_changes(records, task_ids):
        calls["tagged"].append((records, task_ids))
        for record in records:
            record["task_ids"] = sorted(task_ids.get(record.get("package", ""), set()))

    ado_tags.normalize_task_ids = normalize_task_ids
    ado_tags.tag_display_changes = tag_display_changes

    monkeypatch.setitem(sys.modules, "output.gradle", out_gradle)
    monkeypatch.setitem(sys.modules, "parsers.gradle", parsers_gradle)
    monkeypatch.setitem(sys.modules, "parsers.gradle_tree", parsers_tree)
    monkeypatch.setitem(sys.modules, "shared.utils", utils)
    monkeypatch.setitem(sys.modules, "shared.ado_tags", ado_tags)
    monkeypatch.setitem(sys.modules, "loguru", loguru)

    return calls


def test_analyze_gradle_full_success(tmp_path, monkeypatch):
    build = tmp_path / "build.gradle"
    build.write_text("dependencies { implementation 'org.example:lib:1.0.0' }")
    calls = install_gradle_modules(
        monkeypatch, fetch_errs=[{"dependency": "bad", "error": "denied"}]
    )

    result = pipeline_gradle.analyze_gradle(
        str(tmp_path / "tasks.csv"),
        str(build),
        str(tmp_path / "logs"),
        ["title"],
        "https://repo/",
        "libs-release/",
        artifactory_username="user",
        artifactory_password="pass",
        workers=2,
        gradle_timeout=5,
        skip_block_check=True,
    )

    assert result["build_text"].startswith("dependencies")
    assert result["changes"][0]["dependency"] == "org.example:lib"
    assert result["force_entries"][0]["dependency"] == "org.example:force"
    assert {r["change_type"] for r in result["display_changes"]} == {
        "gradle",
        "gradle-force",
    }
    assert result["skipped_display"][0]["reason"] == "already ok"
    assert any(path.endswith("gradle-fetch-errors.csv") for path, _, _ in calls["csv"])
    assert calls["tree_kwargs"][0]["timeout"] == 180
    assert calls["normalized"]


def test_analyze_gradle_requires_artifactory_source(tmp_path, monkeypatch):
    build = tmp_path / "build.gradle"
    build.write_text("dependencies {}")
    install_gradle_modules(monkeypatch)

    with pytest.raises(RuntimeError, match="Artifactory Source URL is required"):
        pipeline_gradle.analyze_gradle("", str(build), str(tmp_path / "logs"), [], "", "repo")


def test_analyze_gradle_tree_error_without_output(tmp_path, monkeypatch, capsys):
    build = tmp_path / "build.gradle"
    build.write_text("dependencies {}")
    calls = install_gradle_modules(
        monkeypatch,
        tree_output="",
        tree_err="line1\nline2\nline3\nline4\nline5\nline6\nline7",
        apply_result=([], [], []),
    )

    result = pipeline_gradle.analyze_gradle(
        "",
        str(build),
        str(tmp_path / "logs"),
        [],
        "https://repo",
        "repo",
    )

    assert result["display_changes"] == []
    assert (tmp_path / "logs" / "gradle-dependency-tree-error.txt").exists()
    out = capsys.readouterr().out
    assert "transitive analysis skipped" in out
    assert "line6" in out
    assert calls["normalized"] == []


def test_analyze_gradle_without_csv_skips_ado_extraction(tmp_path, monkeypatch):
    build = tmp_path / "build.gradle"
    build.write_text("dependencies {}")
    calls = install_gradle_modules(monkeypatch, apply_result=([], [], []))

    result = pipeline_gradle.analyze_gradle(
        "",
        str(build),
        str(tmp_path / "logs"),
        [],
        "https://repo",
        "repo",
    )
    assert result["display_changes"] == []
    assert calls["normalized"] == []


def test_analyze_gradle_fetches_versions_for_transitive_ado_packages(tmp_path, monkeypatch):
    build = tmp_path / "build.gradle"
    build.write_text("dependencies { implementation 'org.example:lib:1.0.0' }")
    calls = install_gradle_modules(
        monkeypatch,
        csv_versions={"org.apache.neethi:neethi": {"3.2.2"}},
        apply_result=([], [], []),
    )

    pipeline_gradle.analyze_gradle(
        str(tmp_path / "tasks.csv"),
        str(build),
        str(tmp_path / "logs"),
        ["title"],
        "https://repo",
        "repo",
    )

    assert calls["fetch_calls"][0] == ["org.example:lib", "org.example:parent"]
    assert "org.apache.neethi:neethi" in calls["fetch_calls"][1]


def test_analyze_gradle_fetches_versions_for_constraints_only_transitive_packages(
    tmp_path, monkeypatch
):
    build = tmp_path / "build.gradle"
    build.write_text("dependencies { implementation 'org.example:lib:1.0.0' }")
    calls = install_gradle_modules(
        monkeypatch,
        csv_versions={},
        csv_constraints={"org.springframework:spring-web": ">="},
        installed={
            "org.example:lib": "1.0.0",
            "org.springframework:spring-web": "6.2.17",
        },
        parents_of={
            "org.example:lib": {"org.example:parent"},
            "org.springframework:spring-web": {"org.example:lib"},
        },
        apply_result=([], [], []),
    )

    pipeline_gradle.analyze_gradle(
        str(tmp_path / "tasks.csv"),
        str(build),
        str(tmp_path / "logs"),
        ["title"],
        "https://repo",
        "repo",
    )

    assert calls["fetch_calls"][0] == ["org.example:lib", "org.example:parent"]
    assert "org.springframework:spring-web" in calls["fetch_calls"][1]


def test_analyze_gradle_writes_constraints_only_packages_to_ado_mentions_csv(tmp_path, monkeypatch):
    build = tmp_path / "build.gradle"
    build.write_text("dependencies { implementation 'org.example:lib:1.0.0' }")
    calls = install_gradle_modules(
        monkeypatch,
        csv_versions={},
        csv_constraints={"org.codehaus.plexus:plexus-utils": ">="},
        installed={
            "org.example:lib": "1.0.0",
        },
        parents_of={
            "org.example:lib": {"org.example:parent"},
        },
        apply_result=([], [], []),
    )

    pipeline_gradle.analyze_gradle(
        str(tmp_path / "tasks.csv"),
        str(build),
        str(tmp_path / "logs"),
        ["title"],
        "https://repo",
        "repo",
    )

    ado_mentions = [
        rows for path, rows, columns in calls["csv"] if path.endswith("gradle-ado-mentions.csv")
    ]
    assert ado_mentions
    assert any(
        row["dependency"] == "org.codehaus.plexus:plexus-utils"
        and row["ado_versions"] == ""
        and row["constraint"] == ">="
        for row in ado_mentions[0]
    )


def test_analyze_gradle_tree_fallback_direct_dep_becomes_change(tmp_path, monkeypatch):
    build = tmp_path / "build.gradle"
    build.write_text(
        "dependencies {\n"
        "    implementation('com.fasterxml.jackson.core:jackson-databind') {\n"
        "        version { strictly '2.22.0' }\n"
        "    }\n"
        "}\n"
    )

    install_gradle_modules(
        monkeypatch,
        tree_output="+--- com.fasterxml.jackson.core:jackson-databind:2.22.0\n",
        apply_result=([], [], []),
        deps_override=[
            __import__("types").SimpleNamespace(
                group="com.fasterxml.jackson.core",
                artifact="jackson-databind",
                version="2.22.0",
                config="implementation",
                original=(
                    "implementation('com.fasterxml.jackson.core:jackson-databind') {\n"
                    "        version { strictly '2.22.0' }\n"
                    "    }"
                ),
            )
        ],
    )

    def fake_tree(*args, **kwargs):
        return (
            "+--- com.fasterxml.jackson.core:jackson-databind:2.21.5\n",
            None,
            {"com.fasterxml.jackson.core:jackson-databind": "2.21.5"},
        )
    monkeypatch.setitem(
        __import__("sys").modules,
        "parsers.gradle_tree",
        __import__("sys").modules["parsers.gradle_tree"],
    )
    monkeypatch.setattr(
        __import__("parsers.gradle_tree", fromlist=["run_gradle_dependencies_with_fallback"]),
        "run_gradle_dependencies_with_fallback",
        fake_tree,
    )

    result = pipeline_gradle.analyze_gradle(
        "",
        str(build),
        str(tmp_path / "logs"),
        [],
        "https://repo",
        "repo",
    )

    direct = next(
        row
        for row in result["changes"]
        if row["dependency"] == "com.fasterxml.jackson.core:jackson-databind"
    )
    assert direct["old_version"] == "2.22.0"
    assert direct["new_version"] == "2.21.5"
    assert direct["ado_guided"] == "blocked-version-fallback"
    force = next(
        row
        for row in result["force_entries"]
        if row["dependency"] == "com.fasterxml.jackson.core:jackson-databind"
    )
    assert force["old_version"] == "2.22.0"
    assert force["new_version"] == "2.21.5"


def test_analyze_gradle_checks_compile_classpath_for_blocked_transitives(tmp_path, monkeypatch):
    build = tmp_path / "build.gradle"
    build.write_text("dependencies { implementation 'org.example:lib:1.0.0' }")
    calls = install_gradle_modules(
        monkeypatch,
        tree_output="+--- org.example:lib:1.0.0\n",
        apply_result=([], [], []),
    )

    def fake_tree(**kwargs):
        calls["tree_kwargs"].append(kwargs)
        configuration = kwargs.get("configuration")
        if configuration == "compileClasspath":
            return (
                "+--- io.netty:netty-codec-http:4.1.135.Final\n",
                None,
                {"io.netty:netty-codec-http": "4.1.135.Final"},
            )
        return ("+--- org.example:lib:1.0.0\n", None, {})

    sys.modules["parsers.gradle_tree"].run_gradle_dependencies_with_fallback = fake_tree
    result = pipeline_gradle.analyze_gradle(
        "",
        str(build),
        str(tmp_path / "logs"),
        [],
        "https://repo",
        "repo",
    )

    configs = [call.get("configuration") for call in calls["tree_kwargs"]]
    assert "compileClasspath" in configs
    force = next(
        row
        for row in result["force_entries"]
        if row["dependency"] == "io.netty:netty-codec-http"
    )
    assert force["new_version"] == "4.1.135.Final"
