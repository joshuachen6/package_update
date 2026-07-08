#!/usr/bin/env python3
"""
gui.py — PyQt6 GUI for the package update pipeline.

Run with:
  .venv/bin/python3 gui.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

from shared import log as app_log
from shared.preflight import check as preflight_check
from ui.widgets import APP_STYLESHEET, dark_palette
from ui.window import MainWindow

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def main():
    preflight_check()
    app_log.setup_file_logging(_LOG_DIR)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(APP_STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
