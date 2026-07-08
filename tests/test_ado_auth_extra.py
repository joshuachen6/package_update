import sys
import types

import pytest

import ado.auth as auth


def test_html_text_extractor_adds_newlines_and_collapses_spaces():
    html = "<div>Hello   <b>there</b></div><p>Next<br>Line</p><ul><li>Item</li></ul>"
    text = auth.html_to_text(html)

    assert text == "Hello there\nNext\nLine\nItem"


def test_html_to_text_empty_returns_empty():
    assert auth.html_to_text("") == ""
    assert auth.html_to_text(None) == ""


def test_make_headers():
    assert auth.make_headers("abc") == {
        "Authorization": "Bearer abc",
        "Content-Type": "application/json",
    }


def test_get_access_token_interactive_uses_silent_account(monkeypatch):
    msal = types.ModuleType("msal")

    class App:
        def __init__(self, client_id, authority):
            self.client_id = client_id
            self.authority = authority

        def get_accounts(self):
            return [{"home": "account"}]

        def acquire_token_silent(self, scopes, account):
            assert scopes == auth.AZURE_DEVOPS_SCOPE_MSAL
            assert account == {"home": "account"}
            return {"access_token": "silent-token"}

        def acquire_token_interactive(self, scopes, prompt):
            raise AssertionError("interactive should not be used")

    msal.PublicClientApplication = App
    monkeypatch.setitem(sys.modules, "msal", msal)

    assert auth.get_access_token_interactive("client", "tenant") == "silent-token"


def test_get_access_token_interactive_falls_back_to_browser_common_authority(
    monkeypatch,
):
    msal = types.ModuleType("msal")
    seen = {}

    class App:
        def __init__(self, client_id, authority):
            seen["client_id"] = client_id
            seen["authority"] = authority

        def get_accounts(self):
            return []

        def acquire_token_interactive(self, scopes, prompt):
            seen["scopes"] = scopes
            seen["prompt"] = prompt
            return {"access_token": "browser-token"}

    msal.PublicClientApplication = App
    monkeypatch.setitem(sys.modules, "msal", msal)

    assert auth.get_access_token_interactive("client") == "browser-token"
    assert seen["authority"] == "https://login.microsoftonline.com/common"
    assert seen["prompt"] == "select_account"


def test_get_access_token_interactive_raises_on_error(monkeypatch):
    msal = types.ModuleType("msal")

    class App:
        def __init__(self, client_id, authority):
            pass

        def get_accounts(self):
            return []

        def acquire_token_interactive(self, scopes, prompt):
            return {
                "error": "bad",
                "error_description": "denied",
                "correlation_id": "corr",
            }

    msal.PublicClientApplication = App
    monkeypatch.setitem(sys.modules, "msal", msal)

    with pytest.raises(RuntimeError, match="Could not acquire access token"):
        auth.get_access_token_interactive("client")


def test_get_access_token_from_azure_cli(monkeypatch):
    azure = types.ModuleType("azure")
    identity = types.ModuleType("azure.identity")
    seen = {}

    class Token:
        token = "cli-token"

    class AzureCliCredential:
        def get_token(self, scope):
            seen["scope"] = scope
            return Token()

    identity.AzureCliCredential = AzureCliCredential
    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.identity", identity)

    assert auth.get_access_token_from_azure_cli() == "cli-token"
    assert seen["scope"] == auth.AZURE_DEVOPS_SCOPE_AZCLI
