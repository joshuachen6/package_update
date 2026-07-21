from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import quick_update
from managers import WritePlan
from shared.build_validation import BuildValidationManualUpdatesError


def _write_payload(tmp_path, file_results):
    results_file = tmp_path / "phase2-results.json"
    results_file.write_text(
        json.dumps({"cfg": {"log_dir": str(tmp_path)}, "file_results": file_results}),
        encoding="utf-8",
    )
    return str(results_file)


def test_run_phase2_results_reports_failure_instead_of_crashing(tmp_path, monkeypatch):
    def fake_get_manager_spec(dm_type):
        return SimpleNamespace(
            make_write_plan=lambda cfg, fr, log_dir: WritePlan(
                has_changes=True,
                file_path=fr["file_path"],
                write=lambda: None,
                validate=_raise_manual_updates_required,
            )
        )

    monkeypatch.setattr("managers.get_manager_spec", fake_get_manager_spec)

    results_file = _write_payload(
        tmp_path,
        [{"dm_type": "gradle", "file_path": str(tmp_path / "build.gradle")}],
    )

    succeeded = quick_update.run_phase2_results(results_file)

    assert succeeded is False


def test_run_phase2_results_continues_past_a_failing_file(tmp_path, monkeypatch):
    calls = []

    def fake_get_manager_spec(dm_type):
        def make_write_plan(cfg, fr, log_dir):
            calls.append(fr["file_path"])
            should_fail = fr["file_path"].endswith("build.gradle")
            return WritePlan(
                has_changes=True,
                file_path=fr["file_path"],
                write=lambda: None,
                validate=_raise_manual_updates_required if should_fail else (lambda: None),
            )

        return SimpleNamespace(make_write_plan=make_write_plan)

    monkeypatch.setattr("managers.get_manager_spec", fake_get_manager_spec)

    results_file = _write_payload(
        tmp_path,
        [
            {"dm_type": "gradle", "file_path": str(tmp_path / "build.gradle")},
            {"dm_type": "node", "file_path": str(tmp_path / "package.json")},
        ],
    )

    succeeded = quick_update.run_phase2_results(results_file)

    assert succeeded is False
    assert calls == [str(tmp_path / "build.gradle"), str(tmp_path / "package.json")]


def test_main_exits_3_when_phase2_replay_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(quick_update, "run_phase2_results", lambda path: False)

    results_file = _write_payload(tmp_path, [])

    with pytest.raises(SystemExit) as exc_info:
        quick_update.main(["--phase2-results", results_file])

    assert exc_info.value.code == 3


def _raise_manual_updates_required():
    raise BuildValidationManualUpdatesError("build validation failed and failure isolation disabled")


def test_run_phase2_results_reclones_when_checkout_is_gone(tmp_path, monkeypatch):
    """Live bug: a Phase 1 checkout lives at a batch-row-indexed directory
    (e.g. .../batch_repos/<repo>/3/<repo>/build.gradle). By the time Phase 2
    replays — a later session, or a batch rerun that reused/removed that
    indexed dir — the recorded build_file path can be gone. write_gradle_file
    then fails writing build.gradle.bak with ENOENT because the whole parent
    directory no longer exists. Phase 2 should re-clone to the same
    checkout_dir (which reproduces the identical path) instead of crashing.
    """
    stale_project_dir = tmp_path / "gone" / "myrepo"
    build_file = stale_project_dir / "build.gradle"

    recloned_dir = tmp_path / "recloned" / "myrepo"

    clone_calls = []

    def fake_clone(url, **kwargs):
        clone_calls.append((url, kwargs))
        recloned_dir.mkdir(parents=True, exist_ok=True)
        (recloned_dir / "build.gradle").write_text("ok", encoding="utf-8")
        return str(recloned_dir)

    monkeypatch.setattr("shared.github.clone_github_repo", fake_clone)

    write_calls = []

    def fake_get_manager_spec(dm_type):
        return SimpleNamespace(
            make_write_plan=lambda cfg, fr, log_dir: WritePlan(
                has_changes=True,
                file_path=fr["file_path"],
                write=lambda: write_calls.append(fr["file_path"]),
                validate=lambda: None,
            )
        )

    monkeypatch.setattr("managers.get_manager_spec", fake_get_manager_spec)

    results_file = tmp_path / "phase2-results.json"
    results_file.write_text(
        json.dumps(
            {
                "cfg": {
                    "log_dir": str(tmp_path),
                    "checkout_dir": str(tmp_path / "checkout-root"),
                    "branch": "main",
                    "github_url": "https://github.com/example/myrepo.git",
                },
                "github_url": "https://github.com/example/myrepo.git",
                "file_results": [
                    {"dm_type": "gradle", "file_path": str(build_file)},
                ],
            }
        ),
        encoding="utf-8",
    )

    succeeded = quick_update.run_phase2_results(str(results_file))

    assert succeeded is True
    assert clone_calls == [
        (
            "https://github.com/example/myrepo.git",
            {"checkout_dir": str(tmp_path / "checkout-root"), "branch": "main"},
        )
    ]
    assert write_calls == [str(build_file)]


def test_run_phase2_results_skips_reclone_when_checkout_still_exists(tmp_path, monkeypatch):
    build_file = tmp_path / "build.gradle"
    build_file.write_text("ok", encoding="utf-8")

    clone_calls = []
    monkeypatch.setattr(
        "shared.github.clone_github_repo",
        lambda url, **kwargs: clone_calls.append((url, kwargs)),
    )

    def fake_get_manager_spec(dm_type):
        return SimpleNamespace(
            make_write_plan=lambda cfg, fr, log_dir: WritePlan(
                has_changes=True,
                file_path=fr["file_path"],
                write=lambda: None,
                validate=lambda: None,
            )
        )

    monkeypatch.setattr("managers.get_manager_spec", fake_get_manager_spec)

    results_file = _write_payload(
        tmp_path,
        [{"dm_type": "gradle", "file_path": str(build_file)}],
    )
    payload = json.loads((tmp_path / "phase2-results.json").read_text(encoding="utf-8"))
    payload["github_url"] = "https://github.com/example/myrepo.git"
    (tmp_path / "phase2-results.json").write_text(json.dumps(payload), encoding="utf-8")

    succeeded = quick_update.run_phase2_results(results_file)

    assert succeeded is True
    assert clone_calls == []
