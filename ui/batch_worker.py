from __future__ import annotations

import contextlib
import os
import queue
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from PyQt6.QtCore import QThread, pyqtSignal


class BatchWorker(QThread):
    row_status = pyqtSignal(int, str)
    row_log = pyqtSignal(int, str)
    all_done = pyqtSignal()

    def __init__(self, rows: list[dict], settings: dict, parent=None):
        super().__init__(parent)
        self._rows = rows
        self._settings = settings
        self._abort = False
        self._procs: list[subprocess.Popen] = []

    def abort(self):
        self._abort = True
        for proc in list(self._procs):
            with contextlib.suppress(Exception):
                proc.terminate()

    def run(self):
        max_workers = max(1, min(len(self._rows), self._settings.get("parallel_repos", 4)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._run_repo, row["_row_index"], row): row["_row_index"]
                for row in self._rows
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    self.row_log.emit(idx, f"[error] {exc}")
                    self.row_status.emit(idx, "Error")
        self.all_done.emit()

    def _expand_url(self, url: str) -> str:
        if not url:
            return url
        prefix = self._settings.get("github_prefix", "").strip().rstrip("/")
        if prefix and "://" not in url:
            url = f"{prefix}/{url}"
        if url and not url.endswith(".git"):
            url = url + ".git"
        return url

    def _repo_log_dir(self, url: str) -> str:
        base = self._settings.get("log_dir") or "logs"
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2:
            dir_name = f"{parts[-2]}_{parts[-1].replace('.git', '')}"
        elif parts:
            dir_name = parts[-1].replace(".git", "")
        else:
            dir_name = "repo"
        return os.path.join(base, "batch", dir_name)

    def _run_repo(self, index: int, row: dict):
        if self._abort:
            self.row_status.emit(index, "Aborted")
            return

        url = self._expand_url(row.get("url", "").strip())
        if not url:
            self.row_status.emit(index, "Skipped")
            return

        self.row_status.emit(index, "Running...")
        branch = row.get("branch", "").strip()
        cves = row.get("cves", "").strip()
        log_dir = self._repo_log_dir(url)
        s = self._settings

        script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quick_update.py"
        )
        phase2_results = os.path.join(
            log_dir,
            "logs",
            "phase2-results.json",
        )

        self.row_log.emit(
            index,
            f"[phase2] replay={s.get('phase2_only_replay')} "
            f"log_dir={log_dir} "
            f"cache={phase2_results} "
            f"exists={os.path.exists(phase2_results)}"
        )

        if s.get("phase2_only_replay") and os.path.exists(phase2_results):
            cmd = [
                sys.executable,
                "-u",
                script,
                "--phase2-results",
                phase2_results,
            ]
            self.row_log.emit(index, f"[phase2] USING REPLAY {' '.join(cmd)}")
        else:
            # Isolate checkouts by batch row. clone_github_repo derives the
            # destination from only the repository name, so parallel rows
            # sharing a checkout root can otherwise remove or clone into
            # one another's directories.
            checkout_root = (
                os.path.abspath(os.path.expanduser(s["checkout_dir"]))
                if s.get("checkout_dir")
                else os.path.join(
                    os.path.expanduser("~"),
                    ".package_update_gui",
                    "batch_repos",
                )
            )
            checkout_dir = os.path.join(
                checkout_root,
                os.path.basename(os.path.normpath(log_dir)),
                str(index),
            )
            cmd = [
                sys.executable,
                "-u",
                script,
                "--github-url",
                url,
                "--checkout-dir",
                checkout_dir,
                "--log-dir",
                log_dir,
            ]
            self.row_log.emit(
                index,
                f"[phase2] FALLBACK FULL RUN {' '.join(cmd)}",
            )

        if branch:
            cmd += ["--branch", branch]
        if cves:
            cmd += ["--input-cves", cves]
        if s.get("artifactory_source"):
            cmd += ["--artifactory-source", s["artifactory_source"]]
        if s.get("artifactory_repo"):
            cmd += ["--artifactory-repo", s["artifactory_repo"]]
        if s.get("artifactory_username"):
            cmd += ["--artifactory-username", s["artifactory_username"]]
        if s.get("artifactory_password"):
            cmd += ["--artifactory-password", s["artifactory_password"]]
        if s.get("npm_cmd") and s["npm_cmd"] != "npm":
            cmd += ["--npm-cmd", s["npm_cmd"]]
        if s.get("npm_registry"):
            cmd += ["--npm-registry", s["npm_registry"]]
        if s.get("skip_block_check"):
            cmd += ["--skip-block-check"]
        if s.get("workers"):
            cmd += ["--workers", str(s["workers"])]
        if s.get("npm_timeout"):
            cmd += ["--npm-timeout", str(s["npm_timeout"])]
        if s.get("gradle_timeout"):
            cmd += ["--gradle-timeout", str(s["gradle_timeout"])]

        if s.get("enable_failure_isolation"):
            cmd += ["--enable-failure-isolation"]

        inactivity_secs = self._settings.get("repo_timeout_min", 20) * 60

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
            )
            self._procs.append(proc)

            # Read in a daemon thread so a stuck \r-terminated progress line
            # (no trailing \n) doesn't block this thread indefinitely.
            q: queue.Queue[str | None] = queue.Queue()

            def _reader():
                try:
                    for raw in proc.stdout:
                        q.put(raw)
                finally:
                    q.put(None)

            threading.Thread(target=_reader, daemon=True).start()

            timed_out = False
            while True:
                if self._abort:
                    proc.terminate()
                    break
                try:
                    raw = q.get(timeout=inactivity_secs)
                except queue.Empty:
                    proc.terminate()
                    timed_out = True
                    self.row_log.emit(
                        index,
                        f"[timeout] No output for {inactivity_secs // 60} min — process terminated.",
                    )
                    break
                if raw is None:
                    break
                self.row_log.emit(index, raw.rstrip("\r\n"))

            proc.wait()
            with suppress_exc():
                self._procs.remove(proc)

            if timed_out:
                self.row_status.emit(index, "Error")
            elif self._abort:
                self.row_status.emit(index, "Aborted")
            elif proc.returncode == 0:
                self.row_status.emit(index, "Success")
            elif proc.returncode == 2:
                self.row_status.emit(index, "Partial")
            elif proc.returncode == 3:
                self.row_status.emit(index, "Failed")
            else:
                self.row_status.emit(index, "Error")
        except Exception as exc:
            self.row_log.emit(index, f"[error] {exc}")
            self.row_status.emit(index, "Error")


class suppress_exc:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return True
