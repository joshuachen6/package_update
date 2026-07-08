from __future__ import annotations

import os
import platform
import subprocess

# ── status classification ─────────────────────────────────────────────────────

_ALREADY_COMPLIANT_REASONS = {
    # Gradle
    "current version already meets ADO target",
    "selected version equals current",
    "spring-framework.version already meets ADO target",
    # Node
    "direct dependency already meets selected version",
    "flat override already satisfies ADO criteria",
    "flat override already at best available version",
    "installed version already satisfies ADO criteria",
}

# Reasons that mean the tool attempted a real update path but could not produce
# one. These remain red/actionable in the task report.
_FAILED_REASON_PREFIXES = (
    "no accessible version found",
    "unparseable version",
)

# Reasons that mean the package was intentionally not applicable/remediable for
# this project. These should be yellow "Skipped", not red "Could not update".
_SKIPPED_REASON_PREFIXES = (
    "not found in build file or dependency tree",
    "transitive dep not found in dependency tree",
    "direct dependency is version-managed",
    "no ADO versions for current major and no accessible same-major update found",
)


def _matches_prefix(reason: str, prefixes: tuple[str, ...]) -> bool:
    return any(reason.startswith(prefix) for prefix in prefixes)


def skipped_reason_status(reason: str) -> str:
    """Return the UI/report status for one skipped package reason."""
    if reason in _ALREADY_COMPLIANT_REASONS:
        return "Resolved"
    if _matches_prefix(reason, _FAILED_REASON_PREFIXES):
        return "Could not update"
    return "Skipped"


def _task_status(
    task_id: int,
    changed_ids: set[int],
    skipped_by_id: dict[int, list[str]],
) -> str:
    if task_id in changed_ids:
        return "Completed"
    reasons = skipped_by_id.get(task_id, [])
    if not reasons:
        return "No package matched"
    reason_statuses = [skipped_reason_status(r) for r in reasons]
    if all(s == "Resolved" for s in reason_statuses):
        return "Resolved"
    if any(s == "Could not update" for s in reason_statuses):
        return "Could not update"
    return "Skipped"


# ── report generation ─────────────────────────────────────────────────────────


def generate_task_report(
    ado_tasks: list[dict],
    file_results: list[dict],
    output_path: str,
    auto_open: bool = True,
) -> str:
    """Build a per-task status report from pipeline results and write to xlsx.

    Sheets:
      Task Summary  — one row per ADO task with Completed / Already compliant /
                      Could not update / Skipped / No package matched status
      Changes       — every package update, with linked task IDs and titles
      Skipped       — every skipped package, with linked task IDs and reasons

    Returns the output path.
    """
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    # Collect data across all file results
    all_changes: list[dict] = []
    all_skipped: list[dict] = []
    for fr in file_results:
        all_changes.extend(fr.get("display_changes", []))
        all_skipped.extend(fr.get("skipped_display", []))

    task_map: dict[int, dict] = {t["id"]: t for t in ado_tasks}

    # Build lookup sets / dicts
    changed_ids: set[int] = set()
    for ch in all_changes:
        changed_ids.update(ch.get("task_ids", []))

    skipped_by_id: dict[int, list[str]] = {}
    for sk in all_skipped:
        reason = sk.get("reason", "")
        for tid in sk.get("task_ids", []):
            skipped_by_id.setdefault(tid, []).append(reason)

    # ── workbook setup ────────────────────────────────────────────────────────
    wb = openpyxl.Workbook()

    _HEADER_FILL = PatternFill("solid", fgColor="1F3864")
    _HEADER_FONT = Font(bold=True, color="FFFFFF")

    _STATUS_FILLS = {
        "Completed": PatternFill("solid", fgColor="C6EFCE"),
        "Resolved": PatternFill("solid", fgColor="E2EFDA"),
        "Could not update": PatternFill("solid", fgColor="FFCCCC"),
        "Skipped": PatternFill("solid", fgColor="FFEB9C"),
        "No package matched": PatternFill("solid", fgColor="EDEDED"),
    }
    _STATUS_FONTS = {
        "Completed": Font(color="276221"),
        "Resolved": Font(color="375623"),
        "Could not update": Font(color="9C0006"),
        "Skipped": Font(color="7D6608"),
        "No package matched": Font(color="595959"),
    }

    def _header_row(ws, headers: list[str]) -> None:
        ws.append(headers)
        for cell in ws[1]:
            cell.fill = _HEADER_FILL
            cell.font = _HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def _autofit(ws, min_w: int = 10, max_w: int = 60) -> None:
        for col in ws.columns:
            length = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = max(
                min_w, min(length + 2, max_w)
            )

    def _task_label(tid: int) -> str:
        t = task_map.get(tid)
        return t["title"] if t else str(tid)

    def _task_ids_str(record: dict) -> str:
        return ", ".join(str(t) for t in record.get("task_ids", []))

    def _task_titles_str(record: dict) -> str:
        return " | ".join(_task_label(t) for t in record.get("task_ids", []))

    # ── Sheet 1: Task Summary ─────────────────────────────────────────────────
    ws_tasks = wb.active
    ws_tasks.title = "Task Summary"
    ws_tasks.row_dimensions[1].height = 30

    _header_row(
        ws_tasks,
        ["Task ID", "Title", "State", "Status", "Package", "Original", "Target", "URL"],
    )

    for task in ado_tasks:
        tid = task["id"]
        status = _task_status(tid, changed_ids, skipped_by_id)

        # Collect package + version info from changes (Completed) and skipped
        # (Resolved / Could not update / Skipped). Deduplicate by package name.
        seen: dict[str, dict[str, str]] = {}
        for ch in all_changes:
            if tid in ch.get("task_ids", []):
                pkg = ch["package"]
                if pkg not in seen:
                    seen[pkg] = {"old": ch.get("old", ""), "new": ch.get("new", "")}
        for sk in all_skipped:
            if tid in sk.get("task_ids", []):
                pkg = sk["package"]
                if pkg not in seen:
                    seen[pkg] = {
                        "old": sk.get("current", ""),
                        "new": sk.get("target", ""),
                    }

        pkgs = "\n".join(seen.keys()) if seen else "—"
        originals = "\n".join(v["old"] if v["old"] else "—" for v in seen.values()) if seen else "—"
        targets = "\n".join(v["new"] if v["new"] else "—" for v in seen.values()) if seen else "—"

        row = ws_tasks.max_row + 1
        ws_tasks.cell(row, 1, tid)
        ws_tasks.cell(row, 2, task.get("title", ""))
        ws_tasks.cell(row, 3, task.get("state", ""))

        status_cell = ws_tasks.cell(row, 4, status)
        status_cell.fill = _STATUS_FILLS.get(status, PatternFill())
        status_cell.font = _STATUS_FONTS.get(status, Font())

        for col, val in [(5, pkgs), (6, originals), (7, targets)]:
            c = ws_tasks.cell(row, col, val)
            c.alignment = Alignment(wrap_text=True, vertical="top")

        url = task.get("url", "")
        if url:
            url_cell = ws_tasks.cell(row, 8, url)
            url_cell.hyperlink = url
            url_cell.font = Font(color="0563C1", underline="single")
        else:
            ws_tasks.cell(row, 8, "")

    _autofit(ws_tasks)
    ws_tasks.freeze_panes = "A2"

    # ── Sheet 2: Changes ──────────────────────────────────────────────────────
    ws_changes = wb.create_sheet("Changes")
    _header_row(
        ws_changes,
        ["Package", "Type", "Old", "New", "ADO Guided", "Task IDs", "Task Titles"],
    )

    has_nlp = False
    for ch in all_changes:
        nlp = ch.get("nlp_resolved", False)
        if nlp:
            has_nlp = True
        ws_changes.append(
            [
                ch.get("package", "") + ("*" if nlp else ""),
                ch.get("change_type", ""),
                ch.get("old", ""),
                ch.get("new", ""),
                "Yes" if ch.get("ado_guided") else "No",
                _task_ids_str(ch),
                _task_titles_str(ch),
            ]
        )

    if has_nlp:
        ws_changes.append([])
        note_cell = ws_changes.cell(
            ws_changes.max_row + 1,
            1,
            "* Package identified via NLP text analysis (not a direct CVE/GHSA database lookup)",
        )
        note_cell.font = Font(italic=True, color="888888")

    _autofit(ws_changes)
    ws_changes.freeze_panes = "A2"

    # ── Split skipped into resolved (already at target) vs truly skipped ────────
    resolved_entries = [
        sk for sk in all_skipped if sk.get("reason", "") in _ALREADY_COMPLIANT_REASONS
    ]
    skipped_entries = [
        sk for sk in all_skipped if sk.get("reason", "") not in _ALREADY_COMPLIANT_REASONS
    ]

    # ── Sheet 3: Resolved (already at target version) ─────────────────────────
    ws_resolved = wb.create_sheet("Resolved")
    _header_row(ws_resolved, ["Package", "Current Version", "Target", "Task IDs", "Task Titles"])

    for sk in resolved_entries:
        ws_resolved.append(
            [
                sk.get("package", ""),
                sk.get("current", ""),
                sk.get("target", ""),
                _task_ids_str(sk),
                _task_titles_str(sk),
            ]
        )

    _autofit(ws_resolved)
    ws_resolved.freeze_panes = "A2"

    # ── Sheet 4: Skipped ──────────────────────────────────────────────────────
    ws_skipped = wb.create_sheet("Skipped")
    _header_row(
        ws_skipped,
        ["Package", "Reason", "Current", "Target", "Task IDs", "Task Titles"],
    )

    for sk in skipped_entries:
        ws_skipped.append(
            [
                sk.get("package", ""),
                sk.get("reason", ""),
                sk.get("current", ""),
                sk.get("target", ""),
                _task_ids_str(sk),
                _task_titles_str(sk),
            ]
        )

    _autofit(ws_skipped)
    ws_skipped.freeze_panes = "A2"

    # ── write and open ────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)

    if auto_open:
        _open_file(output_path)

    return output_path


def _open_file(path: str) -> None:
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", path])
        elif system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass  # best-effort; don't crash the pipeline over a file-open failure
