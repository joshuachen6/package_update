from __future__ import annotations

import csv
import os


class ProgressBar:
    # When set by the GUI worker, called instead of terminal rendering:
    #   _gui_callback(label: str, current: int, total: int) -> None
    _gui_callback = None

    def __init__(self, total: int, label: str, width: int = 30, enabled: bool = True):
        self.total = max(total, 0)
        self.label = label
        self.width = width
        self.enabled = enabled
        self.current = 0
        if enabled:
            self._emit_or_render()

    def update(self, step: int = 1) -> None:
        self.current = min(self.total, self.current + step)
        if not self.enabled:
            return
        self._emit_or_render()

    def _emit_or_render(self) -> None:
        if ProgressBar._gui_callback is not None:
            ProgressBar._gui_callback(self.label, self.current, self.total)
        else:
            self.render()

    def render(self) -> None:
        if not self.enabled:
            return
        if self.total <= 0:
            print(f"\r{self.label}: [done]", end="", flush=True)
            return
        ratio = self.current / self.total
        filled = int(self.width * ratio)
        bar = "#" * filled + "-" * (self.width - filled)
        print(
            f"\r{self.label}: [{bar}] {self.current}/{self.total} {int(ratio * 100)}%",
            end="",
            flush=True,
        )
        if self.current >= self.total:
            print(flush=True)


def write_csv_rows(path: str, rows: list[dict], columns: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def normalize_log_dir(log_dir: str | None, base_dir: str) -> str:
    """Return the only directory that may receive logs for a run.

    A configured log path can be either the logs directory itself or the run's
    base/project directory. In both cases, artifacts must land in a directory
    named ``logs`` rather than directly in the project root.
    """
    base_dir = os.path.abspath(base_dir)
    raw = (log_dir or "").strip()
    path = os.path.abspath(raw) if raw else os.path.join(base_dir, "logs")
    if os.path.basename(os.path.normpath(path)) != "logs":
        path = os.path.join(path, "logs")
    return path


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def parse_columns(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def build_display_change(
    package: str,
    old: str,
    new: str,
    change_type: str,
    remediation_guided: bool = False,
) -> dict:
    return {
        "package": package,
        "change_type": change_type,
        "old": old,
        "new": new,
        "remediation_guided": remediation_guided,
    }


def build_skipped_entry(
    package: str,
    current: str = "",
    target: str = "",
    reason: str = "",
    detail: str = "",
) -> dict:
    return {
        "package": package,
        "current": current,
        "target": target,
        "reason": reason,
        "detail": detail,
    }
