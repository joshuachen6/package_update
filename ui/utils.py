from __future__ import annotations

import os
import re
from urllib.parse import unquote

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

_SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    "build",
    "dist",
    ".gradle",
    ".idea",
    "target",
    "out",
    ".tox",
    "venv",
    ".venv",
    ".next",
    ".nuxt",
    ".svelte-kit",
}


def parse_ado_url(url: str):
    """Return (org, project, story_id_str) from an ADO work-item URL, or None."""
    url = url.strip()
    m = re.match(
        r"https://dev\.azure\.com/([^/?#]+)/([^/?#]+)/_workitems/\S*?/(\d+)",
        url,
        re.IGNORECASE,
    )
    if m:
        return m.group(1), unquote(m.group(2)), m.group(3)
    m = re.match(
        r"https://([^.]+)\.visualstudio\.com/([^/?#]+)/_workitems/\S*?/(\d+)",
        url,
        re.IGNORECASE,
    )
    if m:
        return m.group(1), unquote(m.group(2)), m.group(3)
    return None


def scan_for_dep_managers(project_dir: str) -> list:
    found = []
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        rel_root = os.path.relpath(root, project_dir)
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel = os.path.join(rel_root, fname) if rel_root != "." else fname
            if fname == "package.json":
                found.append({"type": "node", "label": f"Node/npm  >  {rel}", "file_path": fpath})
            elif fname == "build.gradle":
                found.append(
                    {
                        "type": "gradle",
                        "label": f"Gradle    >  {rel}",
                        "file_path": fpath,
                    }
                )
    return found


def open_url(url: str):
    QDesktopServices.openUrl(QUrl(url))
