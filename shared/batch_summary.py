"""Aggregate per-repo batch-run results into the end-of-batch summary
statistics (popup + log): success/partial/failed counts and rates, CVE
clearance counts, vulnerable-package clearance counts, and timing.

Kept ecosystem/UI-agnostic and PyQt6-free so it can be unit tested directly;
ui/batch_worker.py and ui/batch_tab.py only wire this to the GUI.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_repo_evidence(log_dir: str) -> dict[str, Any] | None:
    """Read one repo's remediation-evidence.json and extract the fields
    needed for batch aggregation. Returns None if the file is missing or
    unreadable (e.g. the repo errored/timed out before writing it) -- the
    repo still counts toward the processed/status totals, it just
    contributes nothing to the CVE/package aggregates.
    """
    path = Path(log_dir) / "logs" / "remediation-evidence.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    before_components = (data.get("before_scan") or {}).get("components", []) or []
    after_components = (data.get("after_scan") or {}).get("components", []) or []

    return {
        "original_cves": {str(c) for c in (data.get("original_cves") or [])},
        "remaining_cves": {str(c) for c in (data.get("remaining_original_cves") or [])},
        "vulnerable_packages_before": len(before_components),
        "vulnerable_packages_after": len(after_components),
    }


def aggregate_batch_summary(repo_results: list[dict[str, Any]]) -> dict[str, Any]:
    """repo_results: one dict per repo actually run (not skipped), each with
    at least {"status": str}, and optionally {"duration_seconds": float,
    "evidence": read_repo_evidence(...) result}.
    """
    processed = len(repo_results)
    successful = sum(1 for r in repo_results if r.get("status") == "Success")
    partial = sum(1 for r in repo_results if r.get("status") == "Partial")
    failed = sum(1 for r in repo_results if r.get("status") == "Failed")
    other = processed - successful - partial - failed

    full_remediation_rate = successful / processed if processed else 0.0
    useful_remediation_rate = (successful + partial) / processed if processed else 0.0

    unique_cves_cleared: set[str] = set()
    cves_cleared_by_repo: dict[str, list[str]] = {}
    total_cves_cleared = 0
    vulnerable_packages_before = 0
    vulnerable_packages_after = 0
    durations: list[float] = []

    for r in repo_results:
        duration = r.get("duration_seconds")
        if duration is not None:
            durations.append(float(duration))

        evidence = r.get("evidence")
        if not evidence:
            continue
        cleared = evidence["original_cves"] - evidence["remaining_cves"]
        unique_cves_cleared |= cleared
        total_cves_cleared += len(cleared)
        for cve in cleared:
            cves_cleared_by_repo.setdefault(cve, []).append(r.get("url", ""))
        vulnerable_packages_before += evidence["vulnerable_packages_before"]
        vulnerable_packages_after += evidence["vulnerable_packages_after"]

    instances_cleared = vulnerable_packages_before - vulnerable_packages_after
    clearance_rate = (
        instances_cleared / vulnerable_packages_before if vulnerable_packages_before else 0.0
    )
    average_repo_seconds = sum(durations) / len(durations) if durations else 0.0

    return {
        "processed": processed,
        "successful": successful,
        "partial": partial,
        "failed": failed,
        "other": other,
        "full_remediation_rate": full_remediation_rate,
        "useful_remediation_rate": useful_remediation_rate,
        "unique_cves_cleared": len(unique_cves_cleared),
        "total_cves_cleared": total_cves_cleared,
        "cves_cleared_by_repo": cves_cleared_by_repo,
        "vulnerable_packages_before": vulnerable_packages_before,
        "vulnerable_packages_after": vulnerable_packages_after,
        "instances_cleared": instances_cleared,
        "clearance_rate": clearance_rate,
        # No total/wall-clock time here: repos run concurrently (parallel_repos),
        # so summing per-repo durations would double-count overlapping work
        # rather than reflect how long the batch actually took.
        "average_repo_seconds": average_repo_seconds,
    }


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_summary_popup(summary: dict[str, Any]) -> str:
    return (
        "Batch remediation complete\n\n"
        f"Repos processed: {summary['processed']}\n"
        f"  Successful: {summary['successful']}\n"
        f"  Partial: {summary['partial']}\n"
        f"  Failed: {summary['failed']}\n"
        f"  Other (error/aborted): {summary['other']}\n\n"
        f"Full remediation rate: {summary['full_remediation_rate']:.1%}\n"
        f"Useful remediation rate (full + partial): {summary['useful_remediation_rate']:.1%}\n\n"
        f"Unique CVEs cleared: {summary['unique_cves_cleared']}\n"
        f"Total CVEs cleared (counts duplicates across repos): {summary['total_cves_cleared']}\n\n"
        f"Vulnerable packages before: {summary['vulnerable_packages_before']}\n"
        f"Vulnerable packages after: {summary['vulnerable_packages_after']}\n"
        f"Instances cleared: {summary['instances_cleared']}\n"
        f"Clearance rate: {summary['clearance_rate']:.1%}\n\n"
        f"Average repo fix time: {format_duration(summary['average_repo_seconds'])}"
    )


def format_summary_log(summary: dict[str, Any], repo_results: list[dict[str, Any]]) -> str:
    lines = [
        f"=== Batch summary: {datetime.now().isoformat(timespec='seconds')} ===",
        format_summary_popup(summary),
        "",
        "Per-repo:",
    ]
    for r in repo_results:
        label = r.get("url", "")
        if r.get("branch"):
            label = f"{label}@{r['branch']}"
        duration = r.get("duration_seconds")
        duration_text = format_duration(duration) if duration is not None else "n/a"
        lines.append(f"  [{r.get('status', '')}] {label} — {duration_text}")

    cves_cleared_by_repo = summary.get("cves_cleared_by_repo") or {}
    lines.append("")
    lines.append(f"CVEs resolved ({len(cves_cleared_by_repo)}):")
    for cve in sorted(cves_cleared_by_repo):
        repos = ", ".join(sorted(cves_cleared_by_repo[cve]))
        lines.append(f"  {cve} — {repos}")
    lines.append("")
    return "\n".join(lines)
