from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from ado.auth import html_to_text

API_VERSION = "7.1"


def get_child_work_item_ids(org: str, project: str, story_id: int, headers: dict) -> list[int]:
    import requests

    project_encoded = quote(project, safe="")
    url = (
        f"https://dev.azure.com/{org}/{project_encoded}"
        f"/_apis/wit/workitems/{story_id}"
        f"?$expand=Relations&api-version={API_VERSION}"
    )
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()

    story = response.json()
    child_ids = []
    for relation in story.get("relations", []):
        if relation.get("rel") == "System.LinkTypes.Hierarchy-Forward":
            match = re.search(r"/workItems/(\d+)$", relation.get("url", ""), re.IGNORECASE)
            if match:
                child_ids.append(int(match.group(1)))
    return child_ids


def chunk_list(items: list, chunk_size: int = 200):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def get_work_items_batch(
    org: str, project: str, ids: list[int], headers: dict
) -> list[dict[str, Any]]:
    import requests

    project_encoded = quote(project, safe="")
    url = (
        f"https://dev.azure.com/{org}/{project_encoded}"
        f"/_apis/wit/workitemsbatch?api-version={API_VERSION}"
    )
    fields = [
        "System.Id",
        "System.WorkItemType",
        "System.Title",
        "System.State",
        "System.AssignedTo",
        "System.Description",
    ]

    all_items = []
    for id_chunk in chunk_list(ids, 200):
        body = {"ids": id_chunk, "fields": fields, "errorPolicy": "Omit"}
        response = requests.post(url, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        all_items.extend(response.json().get("value", []))
    return all_items


def extract_task_descriptions(
    org: str, project: str, work_items: list[dict[str, Any]]
) -> list[dict]:
    project_encoded = quote(project, safe="")
    tasks = []
    for item in work_items:
        fields = item.get("fields", {})
        if fields.get("System.WorkItemType") != "Task":
            continue
        assigned_to = fields.get("System.AssignedTo")
        assigned_to_name = (
            assigned_to.get("displayName", "") if isinstance(assigned_to, dict) else ""
        )
        task_id = fields.get("System.Id")
        raw_description = fields.get("System.Description", "")
        tasks.append(
            {
                "id": task_id,
                "title": fields.get("System.Title", ""),
                "state": fields.get("System.State", ""),
                "assigned_to": assigned_to_name,
                "description": html_to_text(raw_description),
                "description_html": raw_description,
                "url": f"https://dev.azure.com/{org}/{project_encoded}/_workitems/edit/{task_id}",
            }
        )
    return tasks
