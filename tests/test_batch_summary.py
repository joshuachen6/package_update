from __future__ import annotations

import json
from pathlib import Path

from shared.batch_summary import (
    aggregate_batch_summary,
    format_duration,
    format_summary_log,
    format_summary_popup,
    read_repo_evidence,
)


def _write_evidence(log_dir: Path, original_cves, remaining_cves, before, after):
    (log_dir / "logs").mkdir(parents=True, exist_ok=True)
    payload = {
        "original_cves": original_cves,
        "remaining_original_cves": remaining_cves,
        "before_scan": {"components": [{"component_id": f"c{i}"} for i in range(before)]},
        "after_scan": {"components": [{"component_id": f"c{i}"} for i in range(after)]},
    }
    (log_dir / "logs" / "remediation-evidence.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_read_repo_evidence_computes_cleared_cves_and_package_counts(tmp_path):
    _write_evidence(
        tmp_path,
        original_cves=["CVE-2026-1", "CVE-2026-2", "CVE-2026-3"],
        remaining_cves=["CVE-2026-3"],
        before=5,
        after=2,
    )

    evidence = read_repo_evidence(str(tmp_path))

    assert evidence["original_cves"] == {"CVE-2026-1", "CVE-2026-2", "CVE-2026-3"}
    assert evidence["remaining_cves"] == {"CVE-2026-3"}
    assert evidence["vulnerable_packages_before"] == 5
    assert evidence["vulnerable_packages_after"] == 2


def test_read_repo_evidence_returns_none_when_file_missing(tmp_path):
    assert read_repo_evidence(str(tmp_path)) is None


def test_read_repo_evidence_returns_none_on_malformed_json(tmp_path):
    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "logs" / "remediation-evidence.json").write_text("{not json", encoding="utf-8")
    assert read_repo_evidence(str(tmp_path)) is None


def test_aggregate_counts_statuses_and_rates():
    repo_results = [
        {"status": "Success"},
        {"status": "Success"},
        {"status": "Partial"},
        {"status": "Failed"},
        {"status": "Error"},
    ]

    summary = aggregate_batch_summary(repo_results)

    assert summary["processed"] == 5
    assert summary["successful"] == 2
    assert summary["partial"] == 1
    assert summary["failed"] == 1
    assert summary["other"] == 1
    assert summary["full_remediation_rate"] == 2 / 5
    assert summary["useful_remediation_rate"] == 3 / 5


def test_aggregate_deduplicates_unique_cves_but_not_total_cves_across_repos():
    """A CVE cleared in three different repos counts once in
    unique_cves_cleared but three times in total_cves_cleared -- this is the
    explicit distinction the user asked for.
    """
    repo_results = [
        {
            "status": "Success",
            "evidence": {
                "original_cves": {"CVE-2026-1", "CVE-2026-2"},
                "remaining_cves": set(),
                "vulnerable_packages_before": 2,
                "vulnerable_packages_after": 0,
            },
        },
        {
            "status": "Success",
            "evidence": {
                "original_cves": {"CVE-2026-1"},
                "remaining_cves": set(),
                "vulnerable_packages_before": 1,
                "vulnerable_packages_after": 0,
            },
        },
        {
            "status": "Partial",
            "evidence": {
                "original_cves": {"CVE-2026-1", "CVE-2026-3"},
                "remaining_cves": {"CVE-2026-3"},
                "vulnerable_packages_before": 2,
                "vulnerable_packages_after": 1,
            },
        },
    ]

    summary = aggregate_batch_summary(repo_results)

    # CVE-2026-1 cleared in all three repos, CVE-2026-2 in one -- 2 distinct.
    assert summary["unique_cves_cleared"] == 2
    # 2 + 1 + 1 = 4 total clears counting repeats across repos.
    assert summary["total_cves_cleared"] == 4
    assert summary["vulnerable_packages_before"] == 5
    assert summary["vulnerable_packages_after"] == 1
    assert summary["instances_cleared"] == 4
    assert summary["clearance_rate"] == 4 / 5


def test_aggregate_tracks_which_repos_cleared_each_cve():
    repo_results = [
        {
            "status": "Success",
            "url": "org/repo-a",
            "evidence": {
                "original_cves": {"CVE-2026-1", "CVE-2026-2"},
                "remaining_cves": set(),
                "vulnerable_packages_before": 2,
                "vulnerable_packages_after": 0,
            },
        },
        {
            "status": "Success",
            "url": "org/repo-b",
            "evidence": {
                "original_cves": {"CVE-2026-1"},
                "remaining_cves": set(),
                "vulnerable_packages_before": 1,
                "vulnerable_packages_after": 0,
            },
        },
    ]

    summary = aggregate_batch_summary(repo_results)

    assert summary["cves_cleared_by_repo"] == {
        "CVE-2026-1": ["org/repo-a", "org/repo-b"],
        "CVE-2026-2": ["org/repo-a"],
    }


def test_aggregate_repo_with_no_evidence_still_counts_toward_processed_but_not_cve_stats():
    repo_results = [
        {"status": "Error"},  # crashed before writing remediation-evidence.json
        {
            "status": "Success",
            "evidence": {
                "original_cves": {"CVE-2026-1"},
                "remaining_cves": set(),
                "vulnerable_packages_before": 1,
                "vulnerable_packages_after": 0,
            },
        },
    ]

    summary = aggregate_batch_summary(repo_results)

    assert summary["processed"] == 2
    assert summary["other"] == 1
    assert summary["unique_cves_cleared"] == 1
    assert summary["vulnerable_packages_before"] == 1


def test_aggregate_handles_zero_processed_without_dividing_by_zero():
    summary = aggregate_batch_summary([])

    assert summary["processed"] == 0
    assert summary["full_remediation_rate"] == 0.0
    assert summary["useful_remediation_rate"] == 0.0
    assert summary["clearance_rate"] == 0.0


def test_aggregate_computes_average_duration_but_not_a_misleading_total():
    """Repos run concurrently (parallel_repos), so summing per-repo
    durations would double-count overlapping work rather than reflect how
    long the batch actually took -- no total/wall-clock figure is reported.
    """
    repo_results = [
        {"status": "Success", "duration_seconds": 30.0},
        {"status": "Success", "duration_seconds": 90.0},
        {"status": "Failed", "duration_seconds": 60.0},
    ]

    summary = aggregate_batch_summary(repo_results)

    assert summary["average_repo_seconds"] == 60.0
    assert "total_seconds" not in summary


def test_format_duration_uses_hours_only_when_an_hour_or_more():
    assert format_duration(45) == "0:45"
    assert format_duration(125) == "2:05"
    assert format_duration(3725) == "1:02:05"


def test_format_summary_popup_includes_every_requested_statistic():
    summary = aggregate_batch_summary(
        [
            {
                "status": "Success",
                "duration_seconds": 60.0,
                "evidence": {
                    "original_cves": {"CVE-2026-1"},
                    "remaining_cves": set(),
                    "vulnerable_packages_before": 3,
                    "vulnerable_packages_after": 1,
                },
            },
        ]
    )

    text = format_summary_popup(summary)

    for expected in (
        "Repos processed: 1",
        "Successful: 1",
        "Partial: 0",
        "Failed: 0",
        "Full remediation rate:",
        "Useful remediation rate",
        "Unique CVEs cleared: 1",
        "Total CVEs cleared",
        "Vulnerable packages before: 3",
        "Vulnerable packages after: 1",
        "Instances cleared: 2",
        "Clearance rate:",
        "Average repo fix time:",
    ):
        assert expected in text


def test_format_summary_log_lists_each_repo_with_its_own_duration():
    repo_results = [
        {"status": "Success", "url": "org/repo-a", "branch": "main", "duration_seconds": 42.0},
        {"status": "Failed", "url": "org/repo-b", "branch": "", "duration_seconds": 17.0},
    ]
    summary = aggregate_batch_summary(repo_results)

    text = format_summary_log(summary, repo_results)

    assert "org/repo-a@main" in text
    assert "0:42" in text
    assert "org/repo-b" in text
    assert "0:17" in text
    assert "[Success]" in text
    assert "[Failed]" in text


def test_format_summary_log_lists_every_resolved_cve_with_its_repos():
    repo_results = [
        {
            "status": "Success",
            "url": "org/repo-a",
            "evidence": {
                "original_cves": {"CVE-2026-1", "CVE-2026-2"},
                "remaining_cves": set(),
                "vulnerable_packages_before": 2,
                "vulnerable_packages_after": 0,
            },
        },
        {
            "status": "Success",
            "url": "org/repo-b",
            "evidence": {
                "original_cves": {"CVE-2026-1"},
                "remaining_cves": set(),
                "vulnerable_packages_before": 1,
                "vulnerable_packages_after": 0,
            },
        },
    ]
    summary = aggregate_batch_summary(repo_results)

    text = format_summary_log(summary, repo_results)

    assert "CVEs resolved (2):" in text
    assert "CVE-2026-1 — org/repo-a, org/repo-b" in text
    assert "CVE-2026-2 — org/repo-a" in text


def test_format_summary_popup_does_not_list_individual_cves():
    """The user asked for the full CVE list to live in the log file only --
    the popup should stay a high-level summary, not grow a long per-CVE list.
    """
    repo_results = [
        {
            "status": "Success",
            "url": "org/repo-a",
            "evidence": {
                "original_cves": {"CVE-2026-1"},
                "remaining_cves": set(),
                "vulnerable_packages_before": 1,
                "vulnerable_packages_after": 0,
            },
        },
    ]
    summary = aggregate_batch_summary(repo_results)

    text = format_summary_popup(summary)

    assert "CVE-2026-1" not in text
    assert "CVEs resolved" not in text


def test_batch_worker_records_result_and_emits_summary_after_all_repos():
    """Source-shape check (PyQt6 isn't importable in this environment, so
    ui/batch_worker.py can't be instantiated directly here): confirms the
    per-repo result recording and the final batch_summary emission are wired
    up, without duplicating the PyQt6-free aggregation logic tested above.
    """
    source = Path("ui/batch_worker.py").read_text(encoding="utf-8")

    assert "batch_summary = pyqtSignal(dict)" in source
    assert "from shared.batch_summary import aggregate_batch_summary, read_repo_evidence" in source
    assert "self._record_repo_result(index, url, branch, log_dir, status, started_at)" in source
    assert '"evidence": read_repo_evidence(log_dir)' in source
    assert "self.batch_summary.emit(" in source
    # Skipped (no URL) and pre-start Aborted repos must not be recorded --
    # both early-return before started_at/log_dir are ever computed.
    assert 'self.row_status.emit(index, "Skipped")\n            return' in source


def test_batch_tab_shows_popup_and_writes_log_on_completion():
    source = Path("ui/batch_tab.py").read_text(encoding="utf-8")

    assert "from shared.batch_summary import format_summary_log, format_summary_popup" in source
    assert "self._worker.batch_summary.connect(self._on_batch_summary)" in source
    assert source.count("self._worker.batch_summary.connect(self._on_batch_summary)") == 3
    assert "QMessageBox.information(" in source
    assert "batch-summary.log" in source
    assert "def _on_batch_summary(self, result: dict):" in source


def test_batch_worker_persists_subprocess_output_even_on_instant_crash():
    """A repo whose subprocess dies before quick_update.py ever gets far
    enough to create its own log_dir (e.g. the checkout/clone step raising)
    previously left no trace anywhere once the GUI's in-memory row log was
    gone -- undiagnosable after the fact. _write_subprocess_output must run
    unconditionally (outside the try/except around Popen) and capture the
    exception's full traceback, not just str(exc), so a fast, silent crash
    is diagnosable from a single git-tracked file instead of requiring a
    live GUI session or a manual re-run.
    """
    source = Path("ui/batch_worker.py").read_text(encoding="utf-8")

    assert "def _write_subprocess_output(self, log_dir: str, captured: list[str]) -> None:" in source
    assert "self._write_subprocess_output(log_dir, captured)" in source
    # Called unconditionally after the try/except, not inside it -- must run
    # whether the subprocess succeeded, errored, or the outer try raised.
    write_call_pos = source.index("self._write_subprocess_output(log_dir, captured)")
    except_pos = source.index("except Exception as exc:")
    assert write_call_pos > except_pos
    assert "_emit(traceback.format_exc())" in source
    assert '"batch-subprocess-output.txt"' in source
