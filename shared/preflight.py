from __future__ import annotations

import shutil
import sys

_REQUIRED_TOOLS = {
    "az": "Azure CLI — install from go/shopping or self-service",
    "claude": "Claude CLI — install from go/shopping or self-service",
}


def check() -> None:
    """Verify required external tools are on PATH. Exits with a clear message if any are missing."""
    missing = [name for name in _REQUIRED_TOOLS if shutil.which(name) is None]
    if not missing:
        return

    lines = ["ERROR: Required tools not found on PATH:"]
    for name in missing:
        lines.append(f"  {name} — {_REQUIRED_TOOLS[name]}")
    lines.append("")
    lines.append("Install the missing tool(s) and re-run.")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(1)
