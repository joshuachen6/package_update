from dataclasses import dataclass

from shared.ado_tags import normalize_task_ids, tag_display_changes


@dataclass
class Dep:
    group: str
    artifact: str


def test_normalize_task_ids_maps_artifact_names_from_deps():
    deps = [Dep("com.example", "lib-a"), Dep("org.demo", "lib-b")]
    installed = {}

    result = normalize_task_ids({"lib-a": {2, 1}, "lib-b": {3}}, deps, installed)

    assert result == {
        "com.example:lib-a": {1, 2},
        "org.demo:lib-b": {3},
    }


def test_normalize_task_ids_uses_installed_fallback_and_keeps_full_keys():
    deps = []
    installed = {
        "com.installed:lib-a": "1.0.0",
        "org.keep:already-full": "2.0.0",
    }

    result = normalize_task_ids(
        {
            "lib-a": {10},
            "org.keep:already-full": {20},
            "unknown": {30},
        },
        deps,
        installed,
    )

    assert result["com.installed:lib-a"] == {10}
    assert result["org.keep:already-full"] == {20}
    assert result["unknown"] == {30}


def test_normalize_task_ids_merges_duplicate_normalized_keys():
    deps = [Dep("com.example", "lib")]
    installed = {}

    result = normalize_task_ids(
        {
            "lib": {1},
            "com.example:lib": {2, 3},
        },
        deps,
        installed,
    )

    assert result == {"com.example:lib": {1, 2, 3}}


def test_tag_display_changes_uses_full_key_artifact_fallback_and_empty_default():
    changes = [
        {"package": "com.example:lib-a"},
        {"package": "lib-b"},
        {"package": "missing"},
        {},
    ]
    task_ids = {
        "com.example:lib-a": {3, 1},
        "lib-b": {2},
    }

    tag_display_changes(changes, task_ids)

    assert changes[0]["task_ids"] == [1, 3]
    assert changes[1]["task_ids"] == [2]
    assert changes[2]["task_ids"] == []
    assert changes[3]["task_ids"] == []


def test_tag_display_changes_links_spring_framework_property_to_framework_module_tasks():
    from shared.ado_tags import tag_display_changes

    records = [{"package": "org.springframework:spring-framework.version"}]
    tag_display_changes(
        records,
        {
            "org.springframework:spring-web": {101},
            "org.springframework.boot:spring-boot-starter-webflux": {202},
        },
    )

    assert records[0]["task_ids"] == [101]
