from __future__ import annotations

import os
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shared.batch_summary import format_summary_log, format_summary_popup
from ui.widgets import mono_textedit

_COL_URL = 0
_COL_BRANCH = 1
_COL_CVES = 2
_COL_STATUS = 3


class BatchTab(QWidget):
    def __init__(self, get_settings, parent=None):
        super().__init__(parent)
        self._get_settings = get_settings
        self._worker = None
        self._row_logs: dict[int, list[str]] = {}
        self._pending_row_logs: list[tuple[int, str]] = []
        self._row_log_flush_timer = QTimer(self)
        self._row_log_flush_timer.setInterval(75)
        self._row_log_flush_timer.timeout.connect(
            self._flush_pending_row_logs
        )
        self._row_log_flush_timer.start()
        self._run_start: float | None = None
        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick_timer)
        self._last_batch_result: dict | None = None
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        btn_bar = QHBoxLayout()
        self._add_btn = QPushButton("+ Add Row")
        self._remove_btn = QPushButton("- Remove")
        self._import_btn = QPushButton("⇡ Import...")
        self._run_btn = QPushButton("▶  Run All")
        self._run_remaining_btn = QPushButton("▶▶  Run Remaining")
        self._phase2_btn = QPushButton("⚠  Run Phase 2")
        self._stop_btn = QPushButton("■  Stop")
        for b in (self._add_btn, self._remove_btn, self._import_btn, self._run_btn, self._run_remaining_btn, self._phase2_btn, self._stop_btn):
            b.setFixedHeight(30)
        self._run_btn.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._phase2_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)

        self._add_btn.clicked.connect(self._add_row)
        self._remove_btn.clicked.connect(self._remove_row)
        self._import_btn.clicked.connect(self._import_file)
        self._run_btn.clicked.connect(self._run_all)
        self._run_remaining_btn.clicked.connect(self._run_remaining)
        self._phase2_btn.clicked.connect(self._run_phase2)
        self._stop_btn.clicked.connect(self._stop_all)

        self._timer_label = QLabel("")
        self._timer_label.setStyleSheet("color: #888; font-family: monospace; padding: 0 6px;")

        btn_bar.addWidget(self._add_btn)
        btn_bar.addWidget(self._remove_btn)
        btn_bar.addWidget(self._import_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(self._timer_label)
        btn_bar.addWidget(self._run_btn)
        btn_bar.addWidget(self._run_remaining_btn)
        btn_bar.addWidget(self._phase2_btn)
        btn_bar.addWidget(self._stop_btn)
        lay.addLayout(btn_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Repository URL", "Branch", "CVEs", "Status"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(_COL_URL, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_BRANCH, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_BRANCH, 110)
        hh.setSectionResizeMode(_COL_CVES, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_STATUS, 150)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self._table.currentCellChanged.connect(lambda row, *_: self._on_row_selected(row))
        splitter.addWidget(self._table)

        log_wrap = QWidget()
        log_lay = QVBoxLayout(log_wrap)
        log_lay.setContentsMargins(0, 4, 0, 0)
        log_lay.setSpacing(2)
        self._log_label = QLabel("Log — select a row to view output")
        self._log_label.setStyleSheet("color: #888; font-style: italic; padding: 2px 4px;")
        log_lay.addWidget(self._log_label)
        self._log = mono_textedit()
        self._log.setReadOnly(True)
        log_lay.addWidget(self._log)
        splitter.addWidget(log_wrap)

        splitter.setSizes([340, 220])
        lay.addWidget(splitter, stretch=1)

    # ── row management ────────────────────────────────────────────────────────

    def _add_row(self):
        row = self._table.rowCount()
        self._table.insertRow(row)
        url_item = QTableWidgetItem("")
        self._table.setItem(row, _COL_URL, url_item)
        self._table.setItem(row, _COL_BRANCH, QTableWidgetItem(""))
        self._table.setItem(row, _COL_CVES, QTableWidgetItem(""))
        self._table.setItem(row, _COL_STATUS, _status_item("Idle"))
        self._row_logs[row] = []
        self._table.setCurrentCell(row, _COL_URL)
        self._table.editItem(url_item)

    def _remove_row(self):
        row = self._table.currentRow()
        if row < 0:
            return
        self._table.removeRow(row)
        old = self._row_logs
        self._row_logs = {
            i: old.get(i if i < row else i + 1, [])
            for i in range(self._table.rowCount())
        }

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Repositories",
            "",
            "Spreadsheets & CSV (*.xlsx *.xls *.csv *.txt);;All Files (*)",
        )
        if not path:
            return
        try:


            from ui.importers import import_from_file






            imported = import_from_file(path)







        except Exception as exc:
            self._log_label.setText(f"Import failed: {exc}")
            return
        if not imported:
            self._log_label.setText("Import: no rows found in file.")
            return
        # An import represents the current contents of the selected file.
        # Replace any previously imported/manual rows instead of appending and
        # leaving stale spreadsheet data visible in the batch table.
        self._table.setRowCount(0)
        self._row_logs.clear()
        self._log.clear()
        self._log_label.setText("Importing repositories...")

        for r in imported:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(
                row,
                _COL_URL,
                QTableWidgetItem(r.get("url", "")),
            )
            self._table.setItem(
                row,
                _COL_BRANCH,
                QTableWidgetItem(r.get("branch", "")),
            )
            self._table.setItem(
                row,
                _COL_CVES,
                QTableWidgetItem(r.get("cves", "")),
            )
            self._table.setItem(
                row,
                _COL_STATUS,
                _status_item("Idle"),
            )
            self._row_logs[row] = []

        if imported:
            self._table.setCurrentCell(0, _COL_URL)
        self._log_label.setText(
            f"Imported {len(imported)} repo(s); previous rows replaced."
        )

    # ── run / stop ────────────────────────────────────────────────────────────

    def _run_all(self, enable_phase2: bool = False):
        if self._worker and self._worker.isRunning():
            return
        rows = self._collect_rows()
        if not rows:
            return
        settings = self._get_settings()
        settings["enable_failure_isolation"] = bool(enable_phase2)
        if settings is None:
            return

        for i in range(self._table.rowCount()):
            url_item = self._table.item(i, _COL_URL)
            has_url = bool(url_item and url_item.text().strip())
            item = self._table.item(i, _COL_STATUS)
            if item:
                item.setText("Queued" if has_url else "Skipped")
                item.setForeground(QColor("#888"))
            self._row_logs[i] = []

        self._run_btn.setEnabled(False)
        self._phase2_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._run_start = time.monotonic()
        self._timer_label.setText("0:00:00")
        self._ticker.start()

        from ui.batch_worker import BatchWorker

        self._worker = BatchWorker(rows, settings, parent=self)
        self._worker.row_status.connect(self._on_row_status)
        self._worker.row_log.connect(self._on_row_log)
        self._worker.batch_summary.connect(self._on_batch_summary)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _stop_all(self):
        if self._worker:
            self._worker.abort()
        self._stop_btn.setEnabled(False)


    def _collect_remaining_rows(self):
        runnable = ("Idle", "Queued", "Aborted", "Timed out", "Error", "Failed")

        rows = []

        for idx in range(self._table.rowCount()):
            status_item = self._table.item(idx, _COL_STATUS)
            status = status_item.text() if status_item else ""

            if not status.startswith(runnable):
                continue

            url_item = self._table.item(idx, _COL_URL)
            if not url_item or not url_item.text().strip():
                continue

            branch_item = self._table.item(idx, _COL_BRANCH)
            cves_item = self._table.item(idx, _COL_CVES)

            rows.append({
                "url": url_item.text().strip(),
                "branch": branch_item.text().strip() if branch_item else "",
                "cves": cves_item.text().strip() if cves_item else "",
                "_row_index": idx,
            })

        return rows

    def _run_remaining(self):
        if self._worker and self._worker.isRunning():
            return

        rows = self._collect_remaining_rows()
        if not rows:
            return

        settings = self._get_settings()
        if settings is None:
            return

        for row in rows:
            item = self._table.item(row["_row_index"], _COL_STATUS)
            if item:
                item.setText("Queued")
                item.setForeground(QColor("#888"))

        from ui.batch_worker import BatchWorker

        self._run_btn.setEnabled(False)
        self._run_remaining_btn.setEnabled(False)
        self._phase2_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        self._run_start = time.monotonic()
        self._timer_label.setText("0:00:00")
        self._ticker.start()

        self._worker = BatchWorker(rows, settings, parent=self)
        self._worker.row_status.connect(self._on_row_status)
        self._worker.row_log.connect(self._on_row_log)
        self._worker.batch_summary.connect(self._on_batch_summary)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _collect_rows(self) -> list[dict]:
        rows = []
        for i in range(self._table.rowCount()):
            url_item = self._table.item(i, _COL_URL)
            url = url_item.text().strip() if url_item else ""
            if not url:
                continue
            branch_item = self._table.item(i, _COL_BRANCH)
            cves_item = self._table.item(i, _COL_CVES)
            rows.append({
                "url": url,
                "branch": branch_item.text().strip() if branch_item else "",
                "cves": cves_item.text().strip() if cves_item else "",
                "_row_index": i,
            })
        return rows

    # ── signals ───────────────────────────────────────────────────────────────

    def _on_row_selected(self, row: int):
        self._drain_pending_row_logs()
        if row < 0:
            self._log.clear()
            self._log_label.setText("Log — select a row to view output")
            return
        url_item = self._table.item(row, _COL_URL)
        label = url_item.text() if url_item and url_item.text() else f"Row {row + 1}"
        self._log_label.setText(f"Log — {label}")
        self._log.setPlainText("\n".join(self._row_logs.get(row, [])))
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def _on_row_status(self, row: int, status: str):
        item = self._table.item(row, _COL_STATUS)
        if item is None:
            item = _status_item("")
            self._table.setItem(row, _COL_STATUS, item)
        item.setText(status)
        if status == "Success":
            item.setForeground(QColor("#4ec9b0"))
        elif status == "Partial":
            item.setForeground(QColor("#e5c07b"))
        elif status == "Failed":
            item.setForeground(QColor("#f44747"))
        elif status == "Error":
            item.setForeground(QColor("#ce9178"))
        elif "Running" in status:
            item.setForeground(QColor("#dcdcaa"))
        elif "Aborted" in status:
            item.setForeground(QColor("#ce9178"))
        else:
            item.setForeground(QColor("#888"))

    def _on_row_log(self, row: int, line: str):
        self._pending_row_logs.append((row, line))

    def _flush_pending_row_logs(self):
        if not self._pending_row_logs:
            return

        visible_row = self._table.currentRow()
        visible_lines: list[str] = []
        batch = self._pending_row_logs[:500]
        del self._pending_row_logs[:500]

        for row, line in batch:
            row_log = self._row_logs.setdefault(row, [])
            row_log.append(line)

            if len(row_log) > 5000:
                del row_log[: len(row_log) - 5000]

            if line.startswith("[phase2]"):
                print(line)
            if row == visible_row:
                visible_lines.append(line)

        if not visible_lines:
            return

        scrollbar = self._log.verticalScrollBar()
        was_near_bottom = (
            scrollbar.maximum() - scrollbar.value() < 80
        )

        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n".join(visible_lines) + "\n")
        self._log.setTextCursor(cursor)

        if was_near_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def _drain_pending_row_logs(self):
        while self._pending_row_logs:
            self._flush_pending_row_logs()

    def _tick_timer(self):
        if self._run_start is None:
            return
        elapsed = int(time.monotonic() - self._run_start)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._timer_label.setText(f"{h}:{m:02d}:{s:02d}")

    def _run_phase2(self):
        manual_rows = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _COL_STATUS)
            if item and item.text() == "Failed":
                manual_rows.append(row)

        if not manual_rows:
            return

        selected = []
        for row in manual_rows:
            url_item = self._table.item(row, _COL_URL)
            branch_item = self._table.item(row, _COL_BRANCH)
            cves_item = self._table.item(row, _COL_CVES)

            selected.append({
                "url": url_item.text().strip() if url_item else "",
                "branch": branch_item.text().strip() if branch_item else "",
                "cves": cves_item.text().strip() if cves_item else "",
                "_row_index": row,
            })

        if self._worker and self._worker.isRunning():
            return

        settings = self._get_settings()
        settings["enable_failure_isolation"] = True
        settings["phase2_only_replay"] = True

        self._run_btn.setEnabled(False)
        self._phase2_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        from ui.batch_worker import BatchWorker
        self._worker = BatchWorker(selected, settings, parent=self)
        self._worker.row_status.connect(self._on_row_status)
        self._worker.row_log.connect(self._on_row_log)
        self._worker.batch_summary.connect(self._on_batch_summary)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_all_done(self):
        self._drain_pending_row_logs()
        self._ticker.stop()
        self._tick_timer()  # final update
        self._run_btn.setEnabled(True)
        self._run_remaining_btn.setEnabled(True)
        needs_phase2 = any(
            self._table.item(r, _COL_STATUS)
            and self._table.item(r, _COL_STATUS).text() == "Failed"
            for r in range(self._table.rowCount())
        )
        self._phase2_btn.setEnabled(needs_phase2)
        self._stop_btn.setEnabled(False)

        if self._last_batch_result is not None:
            summary = self._last_batch_result["summary"]
            repos = self._last_batch_result["repos"]
            if summary["processed"]:
                self._write_batch_summary_log(summary, repos)
                QMessageBox.information(
                    self,
                    "Batch complete",
                    format_summary_popup(summary),
                )
            self._last_batch_result = None

    def _on_batch_summary(self, result: dict):
        self._last_batch_result = result

    def _write_batch_summary_log(self, summary: dict, repos: list[dict]) -> None:
        settings = self._get_settings() or {}
        base = settings.get("log_dir") or "logs"
        log_path = os.path.join(base, "batch", "batch-summary.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(format_summary_log(summary, repos))
                f.write("\n")
        except OSError as exc:
            self._log_label.setText(f"Could not write batch summary log: {exc}")


def _status_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setForeground(QColor("#888"))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item
