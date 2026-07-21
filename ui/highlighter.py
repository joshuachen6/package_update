import re

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

_VER_RE = QRegularExpression(r"(?<!\w)[~^]?\d+\.\d+(?:\.\d+)?(?:[.\-+]\w+)*(?!\w)")

_VER_FMT = QTextCharFormat()
_VER_FMT.setForeground(QColor("#4ec9b0"))

_PKG_FMT = QTextCharFormat()
_PKG_FMT.setForeground(QColor("#9cdcfe"))
_PKG_FMT.setFontWeight(700)
class TaskHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._pkg_patterns: list[re.Pattern] = []

    def set_packages(self, names: set):
        self._pkg_patterns = [
            re.compile(r"(?<![\w@./-])" + re.escape(name) + r"(?![\w@./-])", re.IGNORECASE)
            for name in sorted((n for n in names if n), key=len, reverse=True)
        ]
        self.rehighlight()

    def highlightBlock(self, text: str):
        it = _VER_RE.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), _VER_FMT)

        for pattern in self._pkg_patterns:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), _PKG_FMT)
