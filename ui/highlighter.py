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
        self._pkg_patterns: list = []
        self._kw_patterns: list = []

    def set_packages(self, names: set):
        from ado.extractor import build_fuzzy_patterns, build_package_patterns
        from parsers.gradle import _FUZZY_STOPWORDS

        self._pkg_patterns = list(build_package_patterns(names).values())
        self._kw_patterns = [
            pat for pats in build_fuzzy_patterns(names, _FUZZY_STOPWORDS).values() for pat in pats
        ]
        self.rehighlight()

    def highlightBlock(self, text: str):
        it = _VER_RE.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), _VER_FMT)

        for pat in self._pkg_patterns:
            for m in pat.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), _PKG_FMT)

        for pat in self._kw_patterns:
            for m in pat.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), _PKG_FMT)
