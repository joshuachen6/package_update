from __future__ import annotations

from pathlib import Path


def test_main_window_buffers_worker_log_lines():
    source = Path("ui/window.py").read_text(encoding="utf-8")

    assert "_pending_log_lines" in source
    assert "_flush_pending_log_lines" in source
    assert "setInterval(50)" in source
    assert "self._pending_log_lines[:250]" in source

def test_batch_tab_buffers_concurrent_repo_logs():
    source = Path("ui/batch_tab.py").read_text(encoding="utf-8")

    assert "_pending_row_logs" in source
    assert "_flush_pending_row_logs" in source
    assert "setInterval(75)" in source
    assert "self._pending_row_logs[:500]" in source


def test_log_widget_has_bounded_document_history():
    source = Path("ui/widgets.py").read_text(encoding="utf-8")

    assert "setMaximumBlockCount(5000)" in source
    assert "setUndoRedoEnabled(False)" in source
