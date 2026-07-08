import types

import pytest

import pipeline.ado as pipeline_ado


class DummyCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def install_fake_ado_modules(
    monkeypatch,
    *,
    cli_token="cli-token",
    cli_raises=False,
    interactive_token="interactive-token",
    ids=None,
    items=None,
    tasks=None,
):
    auth = types.ModuleType("ado.auth")
    auth.AZURE_DEVOPS_SCOPE_AZCLI = "499b84ac-1321-427f-aa17-267ca6975798/.default"

    cli_calls = {"count": 0}
    interactive_calls = []

    def get_access_token_from_azure_cli():
        cli_calls["count"] += 1
        if cli_raises and cli_calls["count"] == 1:
            raise RuntimeError("expired")
        return cli_token

    def get_access_token_interactive(client_id="", tenant_id=None):
        interactive_calls.append((client_id, tenant_id))
        return interactive_token

    def make_headers(token):
        return {"Authorization": f"Bearer {token}"}

    auth.get_access_token_from_azure_cli = get_access_token_from_azure_cli
    auth.get_access_token_interactive = get_access_token_interactive
    auth.make_headers = make_headers
    client = types.ModuleType("ado.client")
    calls = {"headers": []}

    def get_child_work_item_ids(org, project, story_id, headers):
        calls["headers"].append(headers)
        return ids if ids is not None else [11, 12]

    def get_work_items_batch(org, project, work_item_ids, headers):
        calls["headers"].append(headers)
        return items if items is not None else [{"id": work_item_ids[0]}]

    def extract_task_descriptions(org, project, work_items):
        return tasks if tasks is not None else [{"id": 11, "title": "Task", "description": "Desc"}]

    client.get_child_work_item_ids = get_child_work_item_ids
    client.get_work_items_batch = get_work_items_batch
    client.extract_task_descriptions = extract_task_descriptions
    utils = types.ModuleType("shared.utils")
    written = {}

    def write_csv_rows(path, rows, columns):
        written["path"] = path
        written["rows"] = rows
        written["columns"] = columns

    utils.write_csv_rows = write_csv_rows

    monkeypatch.setitem(__import__("sys").modules, "ado.auth", auth)
    monkeypatch.setitem(__import__("sys").modules, "ado.client", client)

    # Preserve the real shared package but override the imported submodule.
    monkeypatch.setitem(__import__("sys").modules, "shared.utils", utils)

    return cli_calls, interactive_calls, calls, written


def test_fetch_ado_tasks_azcli_success(tmp_path, monkeypatch):
    cli_calls, interactive_calls, calls, written = install_fake_ado_modules(monkeypatch)

    csv_path, tasks = pipeline_ado.fetch_ado_tasks(
        "org",
        "project",
        123,
        str(tmp_path),
        ["id", "title", "description"],
        auth_method="azcli",
    )

    assert cli_calls["count"] == 1
    assert interactive_calls == []
    assert tasks == [{"id": 11, "title": "Task", "description": "Desc"}]
    assert csv_path.endswith("ado-task-descriptions.csv")
    assert written["path"] == csv_path
    assert written["rows"] == tasks
    assert written["columns"] == ["id", "title", "description"]
    assert calls["headers"][0] == {"Authorization": "Bearer cli-token"}


def test_fetch_ado_tasks_azcli_fallback_login_success(tmp_path, monkeypatch):
    cli_calls, _, _, written = install_fake_ado_modules(monkeypatch, cli_raises=True)

    run_calls = []

    def fake_run(cmd, capture_output, text, timeout):
        run_calls.append(cmd)
        return DummyCompleted(returncode=0)

    monkeypatch.setattr(pipeline_ado.subprocess, "run", fake_run)
    csv_path, tasks = pipeline_ado.fetch_ado_tasks(
        "org",
        "project",
        123,
        str(tmp_path),
        ["id"],
        auth_method="azcli",
        az_login_fallback=True,
    )

    assert cli_calls["count"] == 2
    assert run_calls == [
        ["az", "login", "--scope", "499b84ac-1321-427f-aa17-267ca6975798/.default"]
    ]
    assert written["path"] == csv_path
    assert tasks


def test_fetch_ado_tasks_azcli_no_fallback_reraises(tmp_path, monkeypatch):
    install_fake_ado_modules(monkeypatch, cli_raises=True)
    with pytest.raises(RuntimeError, match="expired"):
        pipeline_ado.fetch_ado_tasks(
            "org",
            "project",
            123,
            str(tmp_path),
            ["id"],
            auth_method="azcli",
            az_login_fallback=False,
        )


def test_fetch_ado_tasks_az_login_failure_raises(tmp_path, monkeypatch):
    install_fake_ado_modules(monkeypatch, cli_raises=True)

    monkeypatch.setattr(
        pipeline_ado.subprocess,
        "run",
        lambda *args, **kwargs: DummyCompleted(returncode=1, stderr="login failed"),
    )

    with pytest.raises(RuntimeError, match="`az login` failed: login failed"):
        pipeline_ado.fetch_ado_tasks("org", "project", 123, str(tmp_path), ["id"])


def test_fetch_ado_tasks_interactive_auth(tmp_path, monkeypatch):
    _, interactive_calls, calls, written = install_fake_ado_modules(monkeypatch)

    csv_path, tasks = pipeline_ado.fetch_ado_tasks(
        "org",
        "project",
        123,
        str(tmp_path),
        ["id"],
        auth_method="interactive",
        client_id="client",
        tenant_id="tenant",
    )

    assert interactive_calls == [("client", "tenant")]
    assert calls["headers"][0] == {"Authorization": "Bearer interactive-token"}
    assert written["path"] == csv_path
    assert tasks


def test_fetch_ado_tasks_interactive_empty_tenant_becomes_none(tmp_path, monkeypatch):
    _, interactive_calls, _, _ = install_fake_ado_modules(monkeypatch)

    pipeline_ado.fetch_ado_tasks(
        "org",
        "project",
        123,
        str(tmp_path),
        ["id"],
        auth_method="interactive",
        client_id="client",
        tenant_id="",
    )

    assert interactive_calls == [("client", None)]


def test_fetch_ado_tasks_no_child_items_raises(tmp_path, monkeypatch):
    install_fake_ado_modules(monkeypatch, ids=[])

    with pytest.raises(RuntimeError, match="No child work items found for story 123"):
        pipeline_ado.fetch_ado_tasks("org", "project", 123, str(tmp_path), ["id"])
