from __future__ import annotations

import sys

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QHeaderView, QTableWidget, QTextEdit

APP_STYLESHEET = """
    QGroupBox {
        font-weight: bold;
        border: 1px solid #555;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 4px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 4px;
        left: 8px;
    }
    QLineEdit, QSpinBox {
        background: #1e1e1e;
        color: #d4d4d4;
        border: 1px solid #555;
        border-radius: 3px;
        padding: 3px 6px;
    }
    QLineEdit:focus, QSpinBox:focus {
        border: 1px solid #569cd6;
    }
    QPushButton {
        background: #3c3c3c;
        color: #d4d4d4;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 4px 12px;
    }
    QPushButton:hover  { background: #4a4a4a; }
    QPushButton:pressed { background: #264f78; }
    QPushButton:disabled { color: #666; }
    QCheckBox, QRadioButton { color: #d4d4d4; }
    QScrollArea { border: 1px solid #555; border-radius: 3px; }
    QScrollBar:vertical {
        background: #2d2d2d; width: 10px;
    }
    QScrollBar::handle:vertical {
        background: #555; border-radius: 4px; min-height: 20px;
    }
    QTabWidget::pane { border: none; }
    QTabBar::tab {
        background: #2d2d2d; color: #aaa;
        padding: 6px 16px; border: none;
        border-bottom: 2px solid transparent;
    }
    QTabBar::tab:selected {
        color: #d4d4d4; border-bottom: 2px solid #569cd6;
    }
    QTabBar::tab:hover { color: #d4d4d4; }
    QMenu { background: #2d2d2d; color: #d4d4d4; border: 1px solid #555; }
    QMenu::item:selected { background: #264f78; }
"""


def dark_palette() -> QPalette:
    p = QPalette()
    c = {
        QPalette.ColorRole.Window: "#2d2d2d",
        QPalette.ColorRole.WindowText: "#d4d4d4",
        QPalette.ColorRole.Base: "#1e1e1e",
        QPalette.ColorRole.AlternateBase: "#252526",
        QPalette.ColorRole.ToolTipBase: "#1e1e1e",
        QPalette.ColorRole.ToolTipText: "#d4d4d4",
        QPalette.ColorRole.Text: "#d4d4d4",
        QPalette.ColorRole.Button: "#3c3c3c",
        QPalette.ColorRole.ButtonText: "#d4d4d4",
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Link: "#569cd6",
        QPalette.ColorRole.Highlight: "#264f78",
        QPalette.ColorRole.HighlightedText: "#ffffff",
    }
    for role, hex_color in c.items():
        p.setColor(role, QColor(hex_color))
    return p


def make_table(cols: list) -> QTableWidget:
    t = QTableWidget(0, len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    hh.setStretchLastSection(True)
    t.setStyleSheet(
        "QTableWidget { border: none; background: #1e1e1e; gridline-color: #333; }"
        "QTableWidget::item { padding: 3px 8px; }"
        "QHeaderView::section { background: #2d2d2d; color: #aaa; padding: 4px 8px;"
        "  border: none; border-bottom: 1px solid #555; }"
    )
    return t


def mono_textedit(placeholder: str = "") -> QTextEdit:
    t = QTextEdit()
    t.setReadOnly(True)
    t.setFont(
        QFont(
            "Menlo"
            if sys.platform == "darwin"
            else "Courier New"
            if sys.platform == "win32"
            else "Monospace",
            11,
        )
    )
    t.setStyleSheet("background: #1e1e1e; color: #d4d4d4; border: none; padding: 6px;")
    if placeholder:
        t.setPlaceholderText(placeholder)
    return t
