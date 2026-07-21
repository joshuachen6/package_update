from __future__ import annotations

import contextlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    def _ecosystem_for_type(self, dm_type: str) -> str:
        return {
            "node": "npm",
            "gradle": "maven",
            "python": "pypi",
        }[dm_type]

    def _run_analysis(self, dm: dict, cfg: dict, columns, cve_packages, audit_prep=False, prefetched_tree=None, prefetched_parsed=None):
        if dm["type"] == "node":
            from pipeline.node import analyze_node

            return analyze_node(
                csv_path="",
                pkg_json_path=dm["file_path"],
                log_dir=cfg["log_dir"],
                columns=columns,
                npm_cmd=cfg.get("npm_cmd", "npm"),
                npm_timeout=cfg.get("npm_timeout", 90),
                workers=cfg.get("workers", 8),
                registry=cfg.get("npm_registry"),
                skip_block_check=True if audit_prep else cfg.get("skip_block_check", False),
                xray_host=cfg.get("xray_url") or cfg.get("artifactory_source", ""),
                cve_packages=cve_packages,
            )

        if dm["type"] == "gradle":
            from pipeline.gradle import analyze_gradle

            return analyze_gradle(
                csv_path="",
                build_file=dm["file_path"],
                log_dir=cfg["log_dir"],
                columns=columns,
                artifactory_source=cfg.get("artifactory_source", ""),
                artifactory_repo=cfg.get("artifactory_repo", "ins-cp-mgmt-gradle-virtual"),
                artifactory_username=cfg.get("artifactory_username", ""),
                artifactory_password=cfg.get("artifactory_password", ""),
                workers=cfg.get("workers", 8),
                gradle_timeout=cfg.get("gradle_timeout", 150),
                skip_block_check=True if audit_prep else cfg.get("skip_block_check", False),
                xray_host=cfg.get("xray_url") or cfg.get("artifactory_source", ""),
                cve_packages=cve_packages,
                prefetched_tree=prefetched_tree,
                prefetched_parsed=prefetched_parsed,
            )

        if dm["type"] == "python":
            from pipeline.python import analyze_python

            return analyze_python(
                dep_file=dm["file_path"],
                log_dir=cfg["log_dir"],
                workers=cfg.get("workers", 8),
                python_cmd=cfg.get("python_cmd", "python3"),
                pip_timeout=cfg.get("pip_timeout", 90),
                pip_index_url=cfg.get("pip_index_url"),
                cve_packages=cve_packages,
                xray_host=cfg.get("xray_url") or cfg.get("artifactory_source", ""),
                skip_block_check=True if audit_prep else cfg.get("skip_block_check", False),
            )
        raise RuntimeError(f"Unsupported dependency manager: {dm['type']}")

    def _analyze_pipeline(self) -> dict | None:
        from shared.github import clone_github_repo
        from shared.jfrog_scan import (
            run_jfrog_audit_with_retry,
            vulnerable_packages_by_ecosystem,
        )
        from ui.utils import scan_for_dep_managers

        cfg = self._cfg
        columns = self._columns()

        self._section("STEP 1 > Clone GitHub repository")

        try:
            clone_kwargs = {
                "checkout_dir": cfg.get("checkout_dir") or None,
            }
            if cfg.get("branch"):
                clone_kwargs["branch"] = cfg.get("branch")
            project_dir = clone_github_repo(cfg["github_url"], **clone_kwargs)
            cfg["proj_dir"] = project_dir
            self.step_done.emit("github", True)

        except Exception as exc:
            import traceback

            logger.error(f"GitHub clone failed: {exc}")
            self.err_line.emit(traceback.format_exc())
            self.step_done.emit("github", False)
            return None

        self._section("STEP 2 > Auto-detect dependency files")

        dep_managers = scan_for_dep_managers(project_dir)

        if not dep_managers:
            self.err_line.emit(
                "No package.json, build.gradle, requirements files, or pyproject.toml found.\n"
            )
            self.step_done.emit("dependency-scan", False)
            return None


        cfg["dep_managers"] = dep_managers

        print(f"Found {len(dep_managers)} dependency file(s).")
        for dm in dep_managers:
            print(f"  {dm['label']}")

        self.step_done.emit("dependency-scan", True)

        jfrog_result = {}
        file_results = []

        if any(dm["type"] == "python" for dm in dep_managers):
            with contextlib.suppress(FileNotFoundError):
                os.remove(os.path.join(cfg["log_dir"], "python-dependency-tree.txt"))

        def _run_prep(dm):
            if self._abort:
                return None
            self._section(f"STEP > Resolve dependencies for audit: {dm['label']}")
            try:
                fr = self._run_analysis(dm, cfg, columns, set(), audit_prep=True)
                fr["dm_type"] = dm["type"]
                fr["file_path"] = dm["file_path"]
                self.step_done.emit(f"{dm['type']}-audit-prep", True)
                return fr
            except Exception as exc:
                import traceback
                logger.error(f"{dm['type']} audit prep failed for {dm['file_path']}: {exc}")
                self.err_line.emit(traceback.format_exc())
                self.step_done.emit(f"{dm['type']}-audit-prep", False)
                return None

        prep_trees: dict[str, object] = {}
        prep_parsed: dict[str, object] = {}
        with ThreadPoolExecutor(max_workers=len(dep_managers)) as executor:
            for fr in as_completed([executor.submit(_run_prep, dm) for dm in dep_managers]):
                result = fr.result()
                if result is not None:
                    file_results.append(result)
                    fp = result["file_path"]
                    if result.get("_tree") is not None:
                        prep_trees[fp] = result["_tree"]
                    if result.get("_parsed") is not None:
                        prep_parsed[fp] = result["_parsed"]

        vulnerable_by_ecosystem = {
            "npm": set(),
            "maven": set(),
            "pypi": set(),
        }

        if not self._abort:
            self._section("STEP > JFrog CVE audit")

            audit_ecosystems = {
                self._ecosystem_for_type(dm["type"])
                for dm in dep_managers
            }

            jfrog_result = run_jfrog_audit_with_retry(
                project_dir=project_dir,
                log_dir=cfg["log_dir"],
                timeout=cfg.get("jfrog_timeout", 600),
                xray_host=cfg.get("xray_url") or cfg.get("artifactory_source", ""),
                auth=(
                    cfg.get("artifactory_username", ""),
                    cfg.get("artifactory_password", ""),
                )
                if cfg.get("artifactory_username")
                else None,
                ecosystems=audit_ecosystems,
                npm_lock_paths=[
                    os.path.join(cfg["log_dir"], "npm-dependency-tree.json")
                ]
                if any(dm["type"] == "node" for dm in dep_managers)
                else [],
                gradle_tree_paths=[
                    os.path.join(cfg["log_dir"], "gradle-dependency-tree.txt")
                ]
                if any(dm["type"] == "gradle" for dm in dep_managers)
                else [],
                python_tree_paths=[
                    os.path.join(cfg["log_dir"], "python-dependency-tree.txt")
                ]
                if any(dm["type"] == "python" for dm in dep_managers)
                else [],
            )

            # A scan that errored (timeout, connection reset, DNS failure) can
            # still report vulnerability_count=0 -- indistinguishable from a
            # genuinely clean repo to anything that only reads the count.
            # Confirmed live: this silently drove zero remediation attempts on
            # real repos, whose later, working post-audit then reported the
            # same (never-touched) CVEs, making the report read as if the
            # tool had introduced new vulnerabilities rather than never having
            # attempted a fix. Mirrors the same gate finalize_verification
            # already applies to the post-audit and quick_update.py's CLI
            # path applies to this same before-audit -- an unusable scan must
            # never be silently treated as "nothing to fix."
            from shared.jfrog_scan import audit_scan_usable

            if not audit_scan_usable(jfrog_result):
                raise RuntimeError(
                    "Initial JFrog CVE audit did not complete successfully "
                    f"({'; '.join(jfrog_result.get('errors') or []) or jfrog_result.get('stderr') or 'scan unavailable'}); "
                    "refusing to proceed since remediation criteria would be built from an incomplete scan."
                )

            vulnerable_by_ecosystem = vulnerable_packages_by_ecosystem(jfrog_result)

        if not self._abort:
            final_results = []

            def _run_fix(dm):
                if self._abort:
                    return None
                ecosystem = self._ecosystem_for_type(dm["type"])
                cve_packages = vulnerable_by_ecosystem.get(ecosystem, set())
                cached_tree = prep_trees.get(dm["file_path"])
                cached_parsed = prep_parsed.get(dm["file_path"])
                fr = self._run_analysis(dm, cfg, columns, cve_packages, audit_prep=False, prefetched_tree=cached_tree, prefetched_parsed=cached_parsed)
                fr["dm_type"] = dm["type"]
                fr["file_path"] = dm["file_path"]
                return fr

            with ThreadPoolExecutor(max_workers=len(dep_managers)) as executor:
                for future in as_completed([executor.submit(_run_fix, dm) for dm in dep_managers]):
                    fr = future.result()
                    if fr is not None:
                        final_results.append(fr)

            if final_results:
                file_results = final_results

        return {
            "file_results": file_results,
            "github_url": cfg.get("github_url", ""),
            "jfrog_result": jfrog_result,
            "cfg": cfg,
        }

    def _section(self, title: str):
        print("")
        print("━" * 60)
        print(f"  {title}")
        print("━" * 60)

    def _columns(self) -> list | None:
        raw = self._cfg.get("columns", "")
        return [c.strip() for c in raw.split(",") if c.strip()] if raw else None
