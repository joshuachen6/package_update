from __future__ import annotations

import os
import subprocess


def fetch_ado_tasks(
    org: str,
    project: str,
    story_id: int,
    log_dir: str,
    csv_columns: list,
    auth_method: str = "azcli",
    client_id: str = "",
    tenant_id: str = "",
    az_login_fallback: bool = True,
) -> tuple:
    """Authenticate, fetch child tasks for *story_id*, write CSV, return (csv_path, tasks)."""
    from ado.auth import (
        AZURE_DEVOPS_SCOPE_AZCLI,
        get_access_token_from_azure_cli,
        get_access_token_interactive,
        make_headers,
    )
    from ado.client import (
        extract_task_descriptions,
        get_child_work_item_ids,
        get_work_items_batch,
    )
    from shared.utils import write_csv_rows

    if auth_method == "azcli":
        print("Authenticating via Azure CLI…")
        try:
            token = get_access_token_from_azure_cli()
        except Exception:
            if not az_login_fallback:
                raise
            print("Session expired — running `az login` (browser will open)…")
            result = subprocess.run(
                ["az", "login", "--scope", AZURE_DEVOPS_SCOPE_AZCLI],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                err = result.stderr.strip() if result.stderr else "unknown error"
                raise RuntimeError(f"`az login` failed: {err}") from None
            print("Azure CLI login succeeded.")
            token = get_access_token_from_azure_cli()
    else:
        print("Authenticating via MSAL (browser will open)…")
        token = get_access_token_interactive(
            client_id=client_id,
            tenant_id=tenant_id or None,
        )

    headers = make_headers(token)
    print(f"Fetching child work items for story {story_id}…")
    ids = get_child_work_item_ids(org, project, story_id, headers)
    if not ids:
        raise RuntimeError(f"No child work items found for story {story_id}.")

    print(f"Found {len(ids)} item(s). Fetching details…")
    items = get_work_items_batch(org, project, ids, headers)
    tasks = extract_task_descriptions(org, project, items)
    print(f"Extracted {len(tasks)} task(s).")

    os.makedirs(log_dir, exist_ok=True)
    csv_path = os.path.join(log_dir, "ado-task-descriptions.csv")
    write_csv_rows(csv_path, tasks, csv_columns)
    print(f"Saved ADO tasks → {csv_path}")
    return csv_path, tasks
