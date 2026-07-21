from __future__ import annotations

import csv
import json
import os
import shutil
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

_RESOLVED_REASON_FRAGMENTS = (
    "already meets remediation target",
    "already compliant",
    "already satisfies",
    "already resolved",
    "no update needed",
)

_SKIPPED_REASON_FRAGMENTS = (
    "transitive dep not found in dependency tree",
    "no fixed versions for current major and no accessible same-major update found",
    "not present",
    "not applicable",
    "unsupported dependency manager",
    "unsupported package manager",
    "unsupported ecosystem",
    "missing package",
    "missing current version",
    "no vulnerable packages",
    "no remediation target",
    "no target version",
)
_FAILURE_REASON_FRAGMENTS = (
    "no accessible version found >= target",
    "no accessible version found &gt;= target",
    "no accessible version found",
    "could not update",
    "failed to update",
    "update failed",
    "validation failed",
    "build failed",
)


def skipped_reason_status(reason: str | None) -> str:
    text = (reason or "").strip().lower()
    if any(fragment in text for fragment in _RESOLVED_REASON_FRAGMENTS):
        return "Resolved"
    if any(fragment in text for fragment in _FAILURE_REASON_FRAGMENTS):
        return "Could not update"
    if any(fragment in text for fragment in _SKIPPED_REASON_FRAGMENTS):
        return "Skipped"
    return "Skipped"


def _task_status(
    task_id: int | str,
    completed_task_ids: Iterable[int | str],
    skipped_reasons: Mapping[int | str, Iterable[str]],
) -> str:
    if task_id in set(completed_task_ids):
        return "Completed"
    reasons = list(skipped_reasons.get(task_id, ()))
    if not reasons:
        return "Could not update"
    statuses = {skipped_reason_status(reason) for reason in reasons}
    if "Could not update" in statuses:
        return "Could not update"
    if "Resolved" in statuses:
        return "Resolved"
    return "Skipped"


def _safe_rel(path: str | os.PathLike[str] | None, base: str | os.PathLike[str] | None = None) -> str:
    if not path:
        return ""
    try:
        p = Path(path)
        if base:
            return str(p.resolve().relative_to(Path(base).resolve()))
        return str(p)
    except Exception:
        return str(path)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except Exception:
        return []


def _tree_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "line_count": 0,
            "dependency_count": 0,
            "bytes": 0,
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    dependency_count = 0
    if path.suffix == ".json":
        try:
            data = json.loads(text)
            packages = data.get("packages", {}) if isinstance(data, dict) else {}
            dependency_count = len(packages) if isinstance(packages, dict) else 0
        except Exception:
            dependency_count = text.count('"version"')
    else:
        dependency_count = sum(
            1 for line in text.splitlines() if "+---" in line or "\\---" in line
        )

    return {
        "path": str(path),
        "exists": True,
        "line_count": len(text.splitlines()),
        "dependency_count": dependency_count,
        "bytes": path.stat().st_size,
    }


def _copy_if_exists(src: Path, dest: Path) -> None:
    if src.exists() and src.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)

def _gradle_tree_diff(before_path: Path, after_path: Path) -> list[dict[str, Any]]:
    if not before_path.exists() or not after_path.exists():
        return []

    try:
        from parsers.gradle_tree import parse_gradle_dep_tree
    except Exception:
        return []

    try:
        before_text = before_path.read_text(encoding="utf-8", errors="replace")
        after_text = after_path.read_text(encoding="utf-8", errors="replace")

        before_installed, _ = parse_gradle_dep_tree(before_text)
        after_installed, _ = parse_gradle_dep_tree(after_text)
    except Exception:
        return []

    before = {k: str(v) for k, v in before_installed.items()}
    after = {k: str(v) for k, v in after_installed.items()}

    rows = []
    for dep in sorted(set(before) | set(after)):
        b = before.get(dep, "")
        a = after.get(dep, "")
        if a == b:
            continue

        if b and a:
            status = "changed"
        elif a:
            status = "added"
        else:
            status = "removed"

        rows.append(
            {
                "dependency": dep,
                "before": b,
                "after": a,
                "status": status,
            }
        )

    return rows



def snapshot_before_dependency_tree(
    log_dir: str | os.PathLike[str] | None,
    ecosystem: str,
    source_path: str | os.PathLike[str] | None = None,
) -> str | None:
    """Persist the analysis-time dependency tree as an explicit before snapshot."""

    if not log_dir:
        return None

    log_path = Path(log_dir)
    if ecosystem == "gradle":
        src = Path(source_path) if source_path else log_path / "gradle-dependency-tree.txt"
        dest = log_path / "gradle-dependency-tree-before.txt"
    elif ecosystem == "node":
        src = Path(source_path) if source_path else log_path / "npm-dependency-tree.json"
        dest = log_path / "npm-dependency-tree-before.json"
    else:
        return None

    if not src.exists():
        return None

    _copy_if_exists(src, dest)
    return str(dest)
def generate_report(results: Mapping[str, Any], log_dir: str | os.PathLike[str] | None = None) -> str:
    """Generate a comprehensive post-write report.

    The preferred output is an XLSX workbook when openpyxl is available. A Markdown
    report is always generated as a readable fallback/companion and the returned
    path points to the XLSX when possible, otherwise the Markdown report.
    """

    cfg = dict(results.get("cfg", {}) or {})
    log_path = Path(log_dir or cfg.get("log_dir") or "logs")
    log_path.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now().isoformat(timespec="seconds")
    project_dir = cfg.get("proj_dir", "")
    github_url = results.get("github_url", "")
    jfrog_result = dict(results.get("jfrog_result", {}) or {})
    jfrog_result_after = dict(
        results.get("jfrog_result_after", {}) or {}
    )
    verification = dict(results.get("verification", {}) or {})
    file_results = list(results.get("file_results", []) or [])
    input_cves = list(results.get("input_cves", []) or [])
    changed_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []

    for fr in file_results:
        file_path = fr.get("file_path") or fr.get("pkg_json_path") or fr.get("build_file") or ""
        dm_type = fr.get("dm_type", "")
        display_file = _safe_rel(file_path, project_dir) if project_dir else str(file_path)
        changes = list(fr.get("display_changes", []) or [])
        skipped = list(fr.get("skipped_display", []) or [])

        file_rows.append(
            {
                "file": display_file,
                "ecosystem": dm_type,
                "changes": len(changes),
                "skipped": len(skipped),
                "write_status": fr.get("write_status", ""),
                "validation_status": fr.get("validation_status", ""),
                "validation_message": fr.get("validation_message", ""),
                "verification_status": fr.get(
                    "verification_status", ""
                ),
                "test_status": fr.get("test_status", ""),
            }
        )

        for row in changes:
            changed_rows.append(
                {
                    "file": display_file,
                    "ecosystem": dm_type,
                    "package": row.get("package", ""),
                    "type": row.get("change_type", ""),
                    "old": row.get("old", ""),
                    "new": row.get("new", ""),
                    "status": fr.get("validation_status") or fr.get("write_status") or "Planned",
                    "remediation_guided": row.get("remediation_guided", ""),
                }
            )

        for row in skipped:
            reason = row.get("reason", "")
            skipped_rows.append(
                {
                    "file": display_file,
                    "ecosystem": dm_type,
                    "package": row.get("package", ""),
                    "current": row.get("current", ""),
                    "target": row.get("target", ""),
                    "status": skipped_reason_status(reason),
                    "reason": reason,
                    "detail": row.get("detail", ""),
                }
            )

    validation_rows: list[dict[str, str]] = []
    for filename in (
        "build-validation-auto-fixes.csv",
        "build-validation-manual-updates.csv",
        "build-validation-external-blockers.csv",
        "build-validation-external-auto-fixes.csv",
    ):
        for row in _read_csv_rows(log_path / filename):
            row = dict(row)
            row.setdefault("source", filename)
            validation_rows.append(row)

    tree_rows = [
        {"ecosystem": "gradle", "snapshot": "before", **_tree_summary(log_path / "gradle-dependency-tree-before.txt")},
        {"ecosystem": "gradle", "snapshot": "after", **_tree_summary(log_path / "gradle-dependency-tree-after.txt")},
        {"ecosystem": "node", "snapshot": "before", **_tree_summary(log_path / "npm-dependency-tree-before.json")},
        {"ecosystem": "node", "snapshot": "after", **_tree_summary(log_path / "npm-dependency-tree-after.json")},
    ]

    dependency_diff_rows = _gradle_tree_diff(
        log_path / "gradle-dependency-tree-before.txt",
        log_path / "gradle-dependency-tree-after.txt",
    )

    diff_csv = log_path / "gradle-resolved-dependency-diff.csv"
    if dependency_diff_rows:
        with diff_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["dependency", "before", "after", "status"],
            )
            writer.writeheader()
            writer.writerows(dependency_diff_rows)
    taskboard_cve_rows: list[dict[str, Any]] = []
    if input_cves:
        jfrog_cves: set[str] = set()
        for comp in jfrog_result.get("vulnerable_components", []):
            for cve in comp.get("cves", []):
                jfrog_cves.add(str(cve))
        for cve in input_cves:
            in_graph = cve in jfrog_cves
            if in_graph:
                [
                    comp.get("package", "")
                    for comp in jfrog_result.get("vulnerable_components", [])
                    if cve in [str(c) for c in comp.get("cves", [])]
                ]
                remaining_after = {
                    str(post_cve)
                    for post_component in jfrog_result_after.get(
                        "vulnerable_components", []
                    )
                    for post_cve in post_component.get("cves", [])
                }
                if cve in remaining_after:
                    status = "Still present after update"
                elif (
                    verification.get("security_status")
                    == "verified_clean"
                ):
                    test_status = verification.get("test_status")
                    if test_status == "passed":
                        status = "Verified fixed - tests passed"
                    elif test_status == "partial":
                        status = "Verified fixed - partially tested"
                    else:
                        status = "Verified fixed - untested"
                else:
                    status = "Verification incomplete"
            else:
                status = "Not found in dependency graph"
            taskboard_cve_rows.append({"cve_id": cve, "status": status})

    validation_sources = {
        row.get("source", "")
        for row in validation_rows
    }

    # The verification outcome is computed from the actual end state (build
    # result + post-remediation JFrog scan) and outranks CSV presence, which
    # misclassifies in both directions: an auto_rolled_back direct declaration
    # can still ship the fixed version through a BOM property or realigned
    # pin (verified Success labeled Manual), and a run with no validation
    # rows can still leave CVEs behind (Partial labeled Success).
    outcome = verification.get("outcome")
    if outcome == "Success":
        overall_status = "🟢 Success"
    elif outcome == "Partial":
        overall_status = "🟡 Needs Review"
    elif outcome in ("Failed", "Error"):
        overall_status = "🔴 Manual Update Required"
    elif (
        "build-validation-manual-updates.csv" in validation_sources
        or "build-validation-auto-fixes.csv" in validation_sources
    ):
        overall_status = "🔴 Manual Update Required"
    elif "build-validation-external-auto-fixes.csv" in validation_sources:
        overall_status = "🟡 Needs Review"
    else:
        overall_status = "🟢 Success"

    summary_rows = [
        {"metric": "Overall Status", "value": overall_status},
        {"metric": "Generated at", "value": generated_at},
        {"metric": "GitHub URL", "value": github_url},
        {"metric": "Project directory", "value": project_dir},
        {"metric": "Dependency files", "value": len(file_rows)},
        {"metric": "Changed packages", "value": len(changed_rows)},
        {"metric": "Skipped packages", "value": len(skipped_rows)},
        {"metric": "Validation records", "value": len(validation_rows)},
        {"metric": "Taskboard CVEs tracked", "value": len(taskboard_cve_rows)},
        {"metric": "Resolved dependency changes", "value": len(dependency_diff_rows)},
        {
            "metric": "Verification classification",
            "value": verification.get("classification", ""),
        },
        {
            "metric": "Test verification",
            "value": verification.get("test_status", ""),
        },
        {
            "metric": "Original CVEs remaining",
            "value": len(
                verification.get("remaining_original_cves", [])
            ),
        },
        {
            "metric": "JFrog vulnerabilities before",
            "value": jfrog_result.get("vulnerability_count", ""),
        },
        {
            "metric": "JFrog vulnerabilities after",
            "value": jfrog_result_after.get(
                "vulnerability_count", ""
            ),
        },
        {
            "metric": "JFrog audit before JSON",
            "value": jfrog_result.get("json_path", ""),
        },
        {
            "metric": "JFrog audit after JSON",
            "value": jfrog_result_after.get("json_path", ""),
        },
    ]

    md_path = log_path / "task-completion-report.md"
    _write_markdown_report(
        md_path,
        summary_rows,
        file_rows,
        changed_rows,
        skipped_rows,
        validation_rows,
        tree_rows,
        dependency_diff_rows,
        taskboard_cve_rows,
    )

    xlsx_path = log_path / "task-completion-report.xlsx"
    try:
        _write_xlsx_report(
            xlsx_path,
            summary_rows,
            file_rows,
            changed_rows,
            skipped_rows,
            validation_rows,
            tree_rows,
            dependency_diff_rows,
            taskboard_cve_rows,
        )
        return str(xlsx_path)
    except Exception as exc:
        fallback_note = (
            "\n\n> XLSX report generation was skipped because openpyxl is unavailable "
            f"or failed: {exc}\n"
        )
        with md_path.open("a", encoding="utf-8") as handle:
            handle.write(fallback_note)
        return str(md_path)


def _write_markdown_report(
    path: Path,
    summary_rows: list[dict[str, Any]],
    file_rows: list[dict[str, Any]],
    changed_rows: list[dict[str, Any]],
    skipped_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
    tree_rows: list[dict[str, Any]],
    dependency_diff_rows: list[dict[str, Any]],
    taskboard_cve_rows: list[dict[str, Any]] | None = None,
) -> None:
    def table(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "_No rows._\n"
        headers = list(rows[0].keys())
        lines = [
            "|" + "|".join(headers) + "|",
            "|" + "|".join("---" for _ in headers) + "|",
        ]
        for row in rows:
            values = [str(row.get(header, "")).replace("\n", "<br>") for header in headers]
            lines.append("|" + "|".join(value.replace("|", "\\|") for value in values) + "|")
        return "\n".join(lines) + "\n"

    status_row = next(
        (
            row
            for row in summary_rows
            if row.get("metric") == "Overall Status"
        ),
        None,
    )

    status = status_row.get("value", "") if status_row else ""

    outcome_lines = [
        "## Remediation Outcome",
        "",
    ]

    if status.startswith("🔴"):
        outcome_lines.extend([
            "🔴 **MANUAL UPDATE REQUIRED**",
            "",
            "One or more dependency updates could not be completed automatically.",
            "",
            "Review:",
            "- build-validation-manual-updates.csv",
            "- build-validation-auto-fixes.csv",
            "",
        ])
    elif status.startswith("🟡"):
        outcome_lines.extend([
            "🟡 **REVIEW RECOMMENDED**",
            "",
            "The build passed, but some findings remain (unresolved CVE "
            "records and/or alternate versions selected during validation).",
            "",
            "Review:",
            "- the post-update JFrog audit for remaining CVE records",
            "- build-validation-external-auto-fixes.csv (if present)",
            "",
        ])
    else:
        outcome_lines.extend([
            "🟢 **SUCCESS**",
            "",
            "All remediation actions completed successfully.",
            "",
        ])

    sections = [
        "# Package Update Completion Report",
        "",
        "## Summary",
        table(summary_rows),
        *outcome_lines,
        "## Dependency Files",
        table(file_rows),
        "## Applied / Planned Changes",
        table(changed_rows),
        "## Skipped / Resolved / Could Not Update",
        table(skipped_rows),
        "## Build Validation",
        table(validation_rows),
        "## Before / After Dependency Trees",
        table(tree_rows),
        "## Resolved Dependency Changes",
        table(dependency_diff_rows),
    ]
    if taskboard_cve_rows:
        sections += ["## Taskboard CVEs", table(taskboard_cve_rows)]
    path.write_text("\n".join(sections), encoding="utf-8")


def _write_xlsx_report(
    path: Path,
    summary_rows: list[dict[str, Any]],
    file_rows: list[dict[str, Any]],
    changed_rows: list[dict[str, Any]],
    skipped_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
    tree_rows: list[dict[str, Any]],
    dependency_diff_rows: list[dict[str, Any]],
    taskboard_cve_rows: list[dict[str, Any]] | None = None,
) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    default = wb.active
    wb.remove(default)

    def add_sheet(title: str, rows: list[dict[str, Any]]) -> None:
        ws = wb.create_sheet(title[:31])
        if rows:
            headers = list(rows[0].keys())
        else:
            headers = ["message"]
            rows = [{"message": "No rows."}]
        ws.append(headers)
        fill = PatternFill("solid", fgColor="1F4E78")
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = fill
        for row in rows:
            ws.append([row.get(header, "") for header in headers])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for idx, header in enumerate(headers, start=1):
            max_len = max(
                [len(str(header))]
                + [len(str(row.get(header, ""))) for row in rows[:200]]
            )
            ws.column_dimensions[get_column_letter(idx)].width = min(max(max_len + 2, 12), 60)
    add_sheet("Summary", summary_rows)
    add_sheet("Files", file_rows)
    add_sheet("Changes", changed_rows)
    add_sheet("Skipped", skipped_rows)
    add_sheet("Build Validation", validation_rows)
    add_sheet("Dependency Trees", tree_rows)
    add_sheet("Dependency Diff", dependency_diff_rows)
    if taskboard_cve_rows:
        add_sheet("Taskboard CVEs", taskboard_cve_rows)
    wb.save(path)
