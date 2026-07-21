#!/usr/bin/env python3
"""Scan ~/.package_update_gui/repos for uncommitted changes and dump the diffs
into this repo's logs/diffs folder, so they're visible without cd-ing into
each individually cloned target repo.
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPOS_DIR = Path.home() / ".package_update_gui" / "repos"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "logs" / "diffs"
MAX_DIFF_BYTES = 500_000
_SKIP_DIRS = {"node_modules", ".gradle", "build", "target", ".git", "dist", ".venv", "venv"}
_MAX_DEPTH = 6


def _find_git_repos(root: Path) -> list[Path]:
    if not root.is_dir():
        return []

    repos: list[Path] = []

    def _walk(path: Path, depth: int) -> None:
        if depth > _MAX_DEPTH:
            return
        if (path / ".git").exists():
            repos.append(path)
            return
        try:
            children = [p for p in path.iterdir() if p.is_dir() and p.name not in _SKIP_DIRS]
        except PermissionError:
            return
        for child in sorted(children):
            _walk(child, depth + 1)

    _walk(root, 0)
    return repos


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    return (result.stdout or "") + (result.stderr or "")


def _diff_for_repo(repo: Path) -> tuple[str, bool]:
    status = _run(["git", "status", "--porcelain=v1"], repo)
    diff = _run(["git", "diff", "HEAD"], repo)
    has_changes = bool(status.strip())

    parts = [f"```\n$ git status --porcelain\n{status or '(clean)'}```\n"]
    if diff.strip():
        encoded = diff.encode("utf-8", "replace")
        if len(encoded) > MAX_DIFF_BYTES:
            diff = encoded[:MAX_DIFF_BYTES].decode("utf-8", "ignore") + "\n... [diff truncated] ...\n"
        parts.append(f"```diff\n{diff}```\n")
    return "\n".join(parts), has_changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos-dir", type=Path, default=DEFAULT_REPOS_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    repos = _find_git_repos(args.repos_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = [f"# Diff scan of `{args.repos_dir}`", "", f"Generated: {timestamp}", ""]

    if not repos:
        summary.append(f"No git repos found under `{args.repos_dir}`.")
        (args.out_dir / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
        print(f"No git repos found under {args.repos_dir}.")
        return

    for repo in repos:
        rel_name = repo.relative_to(args.repos_dir)
        safe_name = str(rel_name).replace("/", "__")
        body, has_changes = _diff_for_repo(repo)

        out_file = args.out_dir / f"{safe_name}.diff.md"
        out_file.write_text(f"# {rel_name}\n\nGenerated: {timestamp}\n\n{body}", encoding="utf-8")

        marker = "CHANGED" if has_changes else "clean"
        summary.append(f"- [{marker}] `{rel_name}` -> [{out_file.name}]({out_file.name})")
        print(f"[{marker}] {rel_name}")

    (args.out_dir / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"\nWrote {len(repos)} diff file(s) to {args.out_dir}")


if __name__ == "__main__":
    main()
