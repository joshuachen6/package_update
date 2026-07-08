from __future__ import annotations

import contextlib
import os
from collections.abc import Callable

from loguru import logger

_file_sink_id: int | None = None


def setup_file_logging(log_dir: str) -> None:
    """Add a rotating file sink for WARNING+ messages. Safe to call multiple times."""
    global _file_sink_id
    if _file_sink_id is not None:
        return
    os.makedirs(log_dir, exist_ok=True)
    _file_sink_id = logger.add(
        os.path.join(log_dir, "app.log"),
        level="WARNING",
        rotation="1 day",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
        encoding="utf-8",
    )


def add_gui_sink(emit_fn: Callable[[str], None]) -> int:
    """Add a loguru sink that routes WARNING+ to a GUI callback. Returns sink ID."""
    return logger.add(
        lambda msg: emit_fn(str(msg).rstrip()),
        level="WARNING",
        format="[{level}] {message}",
        colorize=False,
    )


def remove_gui_sink(sink_id: int) -> None:
    with contextlib.suppress(Exception):
        logger.remove(sink_id)
