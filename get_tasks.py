#!/usr/bin/env python3
"""
get_tasks.py

Pull descriptions from all child Tasks linked to an Azure DevOps User Story,
authenticating as the currently signed-in Azure CLI user.

Prereqs:
  pip install requests azure-identity
  az login

Usage:
  python get_tasks.py \\
    --org "your-org" \\
    --project "your-project" \\
    --story-id 12345 \\
    --out task_descriptions.csv
"""

import argparse
import csv

from ado.auth import get_access_token_from_azure_cli, make_headers
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


def print_summary(tasks):
    print("\nTask descriptions pulled:\n")
    for task in tasks:
        print(f"[{task['id']}] {task['title']}")
        print(f"State: {task['state']}")
        if task["assigned_to"]:
            print(f"Assigned To: {task['assigned_to']}")
        print("Description:")
        print(task["description"] or "(No description)")
        print("-" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Pull descriptions from all child Tasks on an Azure DevOps User Story using your Azure CLI sign-in."
    )
    parser.add_argument("--org", required=True, help="Azure DevOps organization name, e.g. my-org")
    parser.add_argument("--project", required=True, help="Azure DevOps project name")
    parser.add_argument("--story-id", required=True, type=int, help="User Story work item ID")
    parser.add_argument("--out", default="task_descriptions.csv", help="Output CSV file")
    parser.add_argument(
        "--no-print",
        action="store_true",
        help="Do not print task descriptions to the console",
    )
    args = parser.parse_args()

    access_token = get_access_token_from_azure_cli()
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

    if not args.no_print:
        print_summary(tasks)

    print(f"Found {len(tasks)} child Task(s).")
    print(f"Wrote output to: {args.out}")


if __name__ == "__main__":
    main()
