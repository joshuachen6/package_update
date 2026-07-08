from __future__ import annotations

import re
from html.parser import HTMLParser

AZURE_DEVOPS_SCOPE_MSAL = ["499b84ac-1321-427f-aa17-267ca6975798/user_impersonation"]
AZURE_DEVOPS_SCOPE_AZCLI = "499b84ac-1321-427f-aa17-267ca6975798/.default"


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ["br", "p", "div", "li"]:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self):
        text = "".join(self.parts)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


def html_to_text(html_value: str) -> str:
    if not html_value:
        return ""
    parser = HTMLTextExtractor()
    parser.feed(html_value)
    return parser.get_text()


def get_access_token_interactive(client_id: str, tenant_id: str | None = None) -> str:
    """Browser-based Microsoft sign-in via MSAL. Returns an Azure DevOps access token."""
    import msal

    authority = (
        f"https://login.microsoftonline.com/{tenant_id}"
        if tenant_id
        else "https://login.microsoftonline.com/common"
    )
    app = msal.PublicClientApplication(client_id=client_id, authority=authority)

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(scopes=AZURE_DEVOPS_SCOPE_MSAL, account=accounts[0])

    if not result:
        result = app.acquire_token_interactive(
            scopes=AZURE_DEVOPS_SCOPE_MSAL, prompt="select_account"
        )

    if "access_token" not in result:
        raise RuntimeError(
            "Could not acquire access token.\n"
            f"Error: {result.get('error')}\n"
            f"Description: {result.get('error_description')}\n"
            f"Correlation ID: {result.get('correlation_id')}"
        )

    return result["access_token"]


def get_access_token_from_azure_cli() -> str:
    """Uses the signed-in Azure CLI identity. Run `az login` first."""
    from azure.identity import AzureCliCredential

    credential = AzureCliCredential()
    token = credential.get_token(AZURE_DEVOPS_SCOPE_AZCLI)
    return token.token


def make_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
