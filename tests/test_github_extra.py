exec("""
import subprocess
from pathlib import Path
import pytest
from shared.github import clone_github_repo, list_github_branches, normalize_github_url, repo_name_from_url\n@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("", "repo"),
        ("git@github.com:Org/Repo.git", "Repo"),
        ("https://github.com/Org/Repo.git", "Repo"),
        ("github.com/Org/repo-name/", "repo-name"),
        ("https://github.com/Org/re po!.git", "re-po"),
        ("https://github.com/Org/...", "repo"),
    ],
)
def test_repo_name_from_url_variants_extra(url, expected):
    assert repo_name_from_url(url) == expected

def test_normalize_github_url_variants_and_errors_extra():
    assert normalize_github_url("git@github.com:Org/Repo.git") == "git@github.com:Org/Repo.git"
    assert normalize_github_url("github.com/Org/Repo") == "https://github.com/Org/Repo"
    assert normalize_github_url("https://github.com/Org/Repo") == "https://github.com/Org/Repo"\n    with pytest.raises(ValueError, match="required"):
        normalize_github_url("")
    with pytest.raises(ValueError, match="GitHub"):
        normalize_github_url("https://example.com/Org/Repo")

def test_list_github_branches_parses_unique_sorted_extra(monkeypatch):
    def fake_run(cmd, check, text, capture_output):
        assert cmd == ["git", "ls-remote", "--heads", "https://github.com/Org/Repo"]
        assert check is True
        assert text is True
        assert capture_output is True
        stdout = (
            "aaa\\trefs/heads/main"
            + chr(10)
            + "bbb\\trefs/heads/Feature"
            + chr(10)
            + "ccc\\trefs/heads/main"
            + chr(10)\n            + "ddd\\trefs/tags/v1"
            + chr(10)
        )
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout)
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert list_github_branches("github.com/Org/Repo") == ["Feature", "main"]

def test_clone_github_repo_builds_command_and_replaces_existing_dest_extra(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    existing = checkout / "Repo"
    existing.mkdir(parents=True)
    (existing / "old.txt").write_text("old", encoding="utf-8")
    calls = []
    def fake_run(cmd, check, text):
        calls.append((cmd, check, text))
        dest = Path(cmd[-1])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "new.txt").write_text("new", encoding="utf-8")\n        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = clone_github_repo("https://github.com/Org/Repo.git", checkout_dir=str(checkout), branch="release/1.0")
    assert result == str(existing)
    assert not (existing / "old.txt").exists()
    assert (existing / "new.txt").exists()
    assert calls == [(
        ["git", "clone", "--depth", "1", "--branch", "release/1.0", "https://github.com/Org/Repo.git", str(existing)],
        True,
        True,
    )]
""")
