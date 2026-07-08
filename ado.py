#!/usr/bin/env python3
"""
ado.py

Pull descriptions from all child Tasks linked to an Azure DevOps User Story,
authenticating via browser-based MSAL sign-in.

Usage:
  python ado.py \\
    --org "your-org" \\
    --project "your-project" \\
    --story-id 12345 \\
    --client-id "<entra-app-client-id>" \\
    --out task_descriptions.csv
"""

import argparse
import csv

from ado.auth import get_access_token_interactive, make_headers
from ado.client import (
    extract_task_descriptions,
    get_child_work_item_ids,
    get_work_items_batch,
)


def write_csv(tasks, output_file):
    columns = [
        "id",
        "title",
        "state",
        "assigned_to",
        "description",
        "description_html",
        "url",
    ]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(tasks)


def main():
    parser = argparse.ArgumentParser(
        description="Pull descriptions from all child Tasks on an Azure DevOps User Story using SSO sign-in."
    )
    parser.add_argument("--org", required=True, help="Azure DevOps organization name")
    parser.add_argument("--project", required=True, help="Azure DevOps project name")
    parser.add_argument("--story-id", required=True, type=int, help="User Story work item ID")
    parser.add_argument("--client-id", required=True, help="Entra ID app registration client ID")
    parser.add_argument("--tenant-id", required=False, help="Optional Entra tenant ID")
    parser.add_argument("--out", default="task_descriptions.csv", help="Output CSV file")
    args = parser.parse_args()

    access_token = get_access_token_interactive(client_id=args.client_id, tenant_id=args.tenant_id)
    headers = make_headers(access_token)

    child_ids = get_child_work_item_ids(
        org=args.org, project=args.project, story_id=args.story_id, headers=headers
    )
    if not child_ids:
        print(f"No child work items found for User Story {args.story_id}.")
        return

    work_items = get_work_items_batch(
        org=args.org, project=args.project, ids=child_ids, headers=headers
    )
    tasks = extract_task_descriptions(org=args.org, project=args.project, work_items=work_items)

    write_csv(tasks, args.out)
    print(f"Found {len(tasks)} child Task(s).")
    print(f"Wrote output to: {args.out}")


if __name__ == "__main__":
    main()
