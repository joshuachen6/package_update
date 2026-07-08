from __future__ import annotations

import sys
from urllib.parse import quote

from loguru import logger
from PyQt6.QtCore import QThread, pyqtSignal

from pipeline.stream import Stream
from shared import log as app_log


class PipelineWorker(QThread):
    log_line = pyqtSignal(str)
    err_line = pyqtSignal(str)
    step_done = pyqtSignal(str, bool)
    progress = pyqtSignal(str, int, int)
    results_ready = pyqtSignal(dict)
    all_done = pyqtSignal()

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        from shared.utils import ProgressBar

        ProgressBar._gui_callback = lambda label, cur, tot: self.progress.emit(label, cur, tot)
        old_stdout = sys.stdout
        sys.stdout = Stream(self.log_line)
        gui_sink_id = app_log.add_gui_sink(self.err_line.emit)
        try:
            results = self._analyze_pipeline()
            if results is not None:
                self.results_ready.emit(results)
        except Exception as exc:
            import traceback

            logger.error(f"Fatal pipeline error: {exc}")
            self.err_line.emit(traceback.format_exc())
        finally:
            sys.stdout = old_stdout
            ProgressBar._gui_callback = None
            app_log.remove_gui_sink(gui_sink_id)
        self.all_done.emit()

    def _analyze_pipeline(self) -> dict | None:
        from pipeline.ado import fetch_ado_tasks

        cfg = self._cfg
        columns = self._columns()

        self._section("STEP 1 > Fetch ADO task descriptions")
        try:
            csv_path, ado_tasks = fetch_ado_tasks(
                org=cfg["org"],
                project=cfg["project"],
                story_id=int(cfg["story_id"]),
                log_dir=cfg["log_dir"],
                csv_columns=[
                    "id",
                    "title",
                    "state",
                    "assigned_to",
                    "description",
                    "description_html",
                    "url",
                ],
                auth_method=cfg.get("auth_method", "azcli"),
                client_id=cfg.get("client_id", ""),
                tenant_id=cfg.get("tenant_id", ""),
                az_login_fallback=True,
            )
            self.step_done.emit("ado", True)
        except Exception as exc:
            import traceback

            logger.error(f"ADO fetch failed: {exc}")
            self.err_line.emit(traceback.format_exc())
            self.step_done.emit("ado", False)
            return None

        file_results = []
        for dm in cfg.get("dep_managers", []):
            if self._abort:
                break
            self._section(f"STEP > Analyze {dm['label']}")
            print(f"File: {dm['file_path']}")
            try:
                if dm["type"] == "node":
                    from pipeline.node import analyze_node

                    fr = analyze_node(
                        csv_path=csv_path,
                        pkg_json_path=dm["file_path"],
                        log_dir=cfg["log_dir"],
                        columns=columns,
                        npm_cmd=cfg.get("npm_cmd", "npm"),
                        npm_timeout=cfg.get("npm_timeout", 90),
                        workers=cfg.get("workers", 8),
                        registry=cfg.get("npm_registry"),
                        skip_block_check=cfg.get("skip_block_check", False),
                    )
                elif dm["type"] == "gradle":
                    from pipeline.gradle import analyze_gradle

                    fr = analyze_gradle(
                        csv_path=csv_path,
                        build_file=dm["file_path"],
                        log_dir=cfg["log_dir"],
                        columns=columns,
                        artifactory_source=cfg.get("artifactory_source", ""),
                        artifactory_repo=cfg.get("artifactory_repo", "ins-cp-mgmt-gradle-virtual"),
                        artifactory_username=cfg.get("artifactory_username", ""),
                        artifactory_password=cfg.get("artifactory_password", ""),
                        workers=cfg.get("workers", 8),
                        gradle_timeout=cfg.get("gradle_timeout", 30),
                        skip_block_check=cfg.get("skip_block_check", False),
                    )
                else:
                    continue
                fr["dm_type"] = dm["type"]
                fr["file_path"] = dm["file_path"]
                file_results.append(fr)
                self.step_done.emit(dm["type"], True)
            except Exception as exc:
                import traceback

                logger.error(f"{dm['type']} pipeline failed for {dm['file_path']}: {exc}")
                self.err_line.emit(traceback.format_exc())
                self.step_done.emit(dm["type"], False)

        story_url = (
            f"https://dev.azure.com/{cfg['org']}"
            f"/{quote(cfg['project'], safe='')}/_workitems/edit/{cfg['story_id']}"
        )
        return {
            "ado_tasks": ado_tasks,
            "file_results": file_results,
            "story_url": story_url,
            "cfg": cfg,
        }

    def _section(self, title: str):
        print("")
        print("━" * 60)
        print(f"  {title}")
        print("━" * 60)

    def _columns(self) -> list | None:
        raw = self._cfg.get("columns", "title,description,description_html")
        return [c.strip() for c in raw.split(",") if c.strip()] if raw else None
