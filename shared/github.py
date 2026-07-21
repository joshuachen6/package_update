from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse


def repo_name_from_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return "repo"
    if url.startswith("git@"):
        name = url.rsplit(":", 1)[-1].rsplit("/", 1)[-1]
    else:
        parsed = urlparse(url if "://" in url else "https://" + url)
        name = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    name = re.sub(r"\.git$", "", name)
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip(".-")
    return name or "repo"


def normalize_github_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("GitHub URL is required.")
    if url.startswith("git@"):
        return url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if "github.com" not in parsed.netloc.lower():
        raise ValueError("Repository URL must be a GitHub URL.")
    return url


def list_github_branches(url: str):
    repo_url = normalize_github_url(url)
    proc = subprocess.run(
        ["git", "ls-remote", "--heads", repo_url],
        check=True,
        text=True,
        capture_output=True,
    )
    branches = []
    for line in proc.stdout.splitlines():
        if "refs/heads/" not in line:
            continue
        branch = line.rsplit("refs/heads/", 1)[-1].strip()
        if branch:
            branches.append(branch)
    return sorted(set(branches), key=str.lower)
def _make_writable_and_retry(func, path: str, exc_info) -> None:
    try:
        os.chmod(path, stat.S_IRWXU)
        func(path)
    except Exception as retry_exc:
        exc = exc_info[1] if isinstance(exc_info, tuple) else exc_info
        raise exc from retry_exc


def _remove_checkout_dir(dest: Path) -> None:
    """Remove an existing checkout before cloning.

    Gradle/build output can leave large trees, read-only files, or paths that
    briefly remain visible on macOS. Retry a few times so clone startup does not
    fail with transient "Directory not empty" errors.
    """
    if not dest.exists():
        return

    last_exc: Exception | None = None
    for _ in range(5):
        try:
            shutil.rmtree(dest, onerror=_make_writable_and_retry)
            return
        except OSError as exc:
            last_exc = exc
            time.sleep(0.25)

    if dest.exists():
        raise RuntimeError(f"Could not remove existing checkout directory: {dest}") from last_exc


def clone_github_repo(url: str, checkout_dir: str | None = None, branch: str | None = None) -> str:
    repo_url = normalize_github_url(url)
    branch = (branch or "").strip() or None
    base = Path(checkout_dir or Path.home() / ".package_update_gui" / "repos").expanduser()
    base.mkdir(parents=True, exist_ok=True)
    dest = base / repo_name_from_url(repo_url)

    _remove_checkout_dir(dest)

    branch_msg = f" branch '{branch}'" if branch else ""
    print(f"Cloning {repo_url}{branch_msg} -> {dest}")
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([repo_url, str(dest)])
    subprocess.run(cmd, check=True, text=True)
    return str(dest)
