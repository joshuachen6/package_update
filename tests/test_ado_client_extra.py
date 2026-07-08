import sys
import types

import ado.client as client


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raised = False

    def raise_for_status(self):
        self.raised = True

    def json(self):
        return self.payload


def install_requests(monkeypatch, *, get_payload=None, post_payloads=None):
    requests = types.ModuleType("requests")
    calls = {"get": [], "post": []}
    post_payloads = list(post_payloads or [])

    def get(url, headers, timeout):
        calls["get"].append({"url": url, "headers": headers, "timeout": timeout})
        return DummyResponse(get_payload or {})

    def post(url, headers, json, timeout):
        calls["post"].append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        payload = post_payloads.pop(0) if post_payloads else {"value": []}
        return DummyResponse(payload)

    requests.get = get
    requests.post = post
    monkeypatch.setitem(sys.modules, "requests", requests)
    return calls


def test_get_child_work_item_ids_filters_hierarchy_relations_and_encodes_project(
    monkeypatch,
):
    calls = install_requests(
        monkeypatch,
        get_payload={
            "relations": [
                {
                    "rel": "System.LinkTypes.Hierarchy-Forward",
                    "url": "https://dev.azure.com/org/_apis/wit/workItems/101",
                },
                {
                    "rel": "System.LinkTypes.Related",
                    "url": "https://dev.azure.com/org/_apis/wit/workItems/202",
                },
                {"rel": "System.LinkTypes.Hierarchy-Forward", "url": "not-a-workitem"},
                {
                    "rel": "System.LinkTypes.Hierarchy-Forward",
                    "url": "https://dev.azure.com/org/_apis/wit/workItems/303",
                },
            ]
        },
    )

    ids = client.get_child_work_item_ids("org", "Project Name", 55, {"Auth": "token"})

    assert ids == [101, 303]
    assert "Project%20Name" in calls["get"][0]["url"]
    assert "$expand=Relations" in calls["get"][0]["url"]
    assert calls["get"][0]["headers"] == {"Auth": "token"}
    assert calls["get"][0]["timeout"] == 60


def test_get_child_work_item_ids_handles_missing_relations(monkeypatch):
    install_requests(monkeypatch, get_payload={})
    assert client.get_child_work_item_ids("org", "proj", 55, {}) == []


def test_chunk_list_chunks_default_and_custom_size():
    assert list(client.chunk_list([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    assert list(client.chunk_list([], 2)) == []


def test_get_work_items_batch_posts_in_chunks(monkeypatch):
    ids = list(range(1, 205))
    calls = install_requests(
        monkeypatch,
        post_payloads=[
            {"value": [{"id": 1}, {"id": 2}]},
            {"value": [{"id": 201}]},
        ],
    )

    items = client.get_work_items_batch("org", "Project Name", ids, {"Auth": "token"})
    assert items == [{"id": 1}, {"id": 2}, {"id": 201}]
    assert len(calls["post"]) == 2
    assert calls["post"][0]["json"]["ids"] == list(range(1, 201))
    assert calls["post"][1]["json"]["ids"] == list(range(201, 205))
    assert calls["post"][0]["json"]["errorPolicy"] == "Omit"
    assert "System.Description" in calls["post"][0]["json"]["fields"]
    assert "Project%20Name" in calls["post"][0]["url"]


def test_extract_task_descriptions_only_tasks_and_normalizes_description():
    work_items = [
        {
            "fields": {
                "System.Id": 10,
                "System.WorkItemType": "Task",
                "System.Title": "Upgrade package",
                "System.State": "Active",
                "System.AssignedTo": {"displayName": "Ada"},
                "System.Description": "<p>Hello<br>World</p>",
            }
        },
        {
            "fields": {
                "System.Id": 11,
                "System.WorkItemType": "Bug",
                "System.Title": "Ignored",
            }
        },
        {
            "fields": {
                "System.Id": 12,
                "System.WorkItemType": "Task",
                "System.Title": "No assignee",
                "System.State": "New",
                "System.AssignedTo": "not-a-dict",
                "System.Description": "",
            }
        },
    ]

    tasks = client.extract_task_descriptions("org", "Project Name", work_items)

    assert len(tasks) == 2
    assert tasks[0]["id"] == 10
    assert tasks[0]["assigned_to"] == "Ada"
    assert tasks[0]["description"] == "Hello\nWorld"
    assert tasks[0]["description_html"] == "<p>Hello<br>World</p>"
    assert "Project%20Name" in tasks[0]["url"]
    assert tasks[1]["assigned_to"] == ""
    assert tasks[1]["description"] == ""
