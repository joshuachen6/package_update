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


def parse_work_item_url(url: str):
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


def scan_for_dep_managers(root_dir: str) -> list:
    from pathlib import Path

    from parsers.python import is_supported_python_dependency_file
    root_path = Path(root_dir).resolve()
    found = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in _SKIP_DIRS and not name.startswith(".")
        )
        current = Path(dirpath)
        for filename in sorted(filenames):
            path = current / filename
            rel = path.relative_to(root_path)
            if filename == "package.json":
                found.append({"type": "node", "label": f"Node/npm  >  {rel}", "file_path": str(path)})
            elif filename == "build.gradle":
                found.append({"type": "gradle", "label": f"Gradle    >  {rel}", "file_path": str(path)})
            elif filename == "pom.xml":
                found.append({"type": "maven", "label": f"Maven     >  {rel}", "file_path": str(path)})
            elif is_supported_python_dependency_file(path):
                found.append({"type": "python", "label": f"Python    >  {rel}", "file_path": str(path)})
    return found


def open_url(url: str):
    QDesktopServices.openUrl(QUrl(url))
