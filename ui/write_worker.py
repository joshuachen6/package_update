from __future__ import annotations

import sys

from loguru import logger
from PyQt6.QtCore import QThread, pyqtSignal

from pipeline.stream import Stream
from shared import log as app_log


class WriteOutputWorker(QThread):
    log_line = pyqtSignal(str)
    err_line = pyqtSignal(str)
    progress = pyqtSignal(str, int, int)
    file_done = pyqtSignal(str, bool)
    all_done = pyqtSignal(bool)

    def __init__(self, results: dict, parent=None):
        super().__init__(parent)
        self._results = results

    def run(self):
        from shared.utils import ProgressBar

        ProgressBar._gui_callback = lambda label, cur, tot: self.progress.emit(label, cur, tot)
        old_stdout = sys.stdout
        sys.stdout = Stream(self.log_line)
        gui_sink_id = app_log.add_gui_sink(self.err_line.emit)
        any_written = False

        try:
            any_written = self._write_output()
        except Exception as exc:
            import traceback

            logger.error(f"Fatal write output error: {exc}")
            self.err_line.emit(traceback.format_exc())
        finally:
            sys.stdout = old_stdout
            ProgressBar._gui_callback = None
            app_log.remove_gui_sink(gui_sink_id)

        self.all_done.emit(any_written)

    def _write_output(self) -> bool:
        from types import SimpleNamespace

        from managers import get_manager_spec
        from pipeline.runner import run_write_validate

        file_results = self._results.get("file_results", [])
        total = len(file_results)
        any_written = False
        cfg_dict = self._results.get("cfg", {})
        skip_validation = cfg_dict.get("skip_build_validation", False)

        for index, fr in enumerate(file_results, start=1):
            dm_type = fr["dm_type"]
            fpath = fr.get("file_path") or fr.get("build_file") or fr.get("pkg_json_path") or dm_type
            self.progress.emit(f"Writing {index}/{total}", index - 1, total)

            try:
                manager = get_manager_spec(dm_type)
                cfg = SimpleNamespace(**cfg_dict)
                log_dir = cfg_dict.get("log_dir")
                plan = manager.make_write_plan(cfg, fr, log_dir)
                written = run_write_validate(plan, skip_validation)
                if written:
                    any_written = True
                fr["write_status"] = (
                    "Written" if written else "No changes"
                )
                fr["validation_status"] = (
                    "Skipped" if skip_validation else "Passed"
                )
                self.file_done.emit(plan.file_path, True)

            except Exception as exc:
                fr["write_status"] = "Failed"
                fr["validation_status"] = "Failed"
                fr["validation_message"] = str(exc)
                self.err_line.emit(f"Write failed for {fpath}: {exc}")
                self.file_done.emit(fpath, False)

            finally:
                self.progress.emit(f"Writing {index}/{total}", index, total)

        if any_written:
            try:
                from shared.verification import finalize_verification

                verification = finalize_verification(self._results)
                print(
                    "Post-update verification: "
                    + verification["classification"]
                )
                from shared.remediation_evidence import (
                    write_remediation_evidence,
                )

                evidence_path = write_remediation_evidence(
                    self._results,
                    log_dir=cfg_dict.get("log_dir"),
                )
                self._results[
                    "remediation_evidence_path"
                ] = evidence_path
                print(
                    f"Remediation evidence -> {evidence_path}"
                )
            except Exception as exc:
                self._results["verification"] = {
                    "classification": "Verification incomplete",
                    "security_status": "incomplete",
                    "test_status": "not_run",
                    "error": str(exc),
                }
                self.err_line.emit(
                    f"Post-update verification failed: {exc}"
                )

        return any_written
