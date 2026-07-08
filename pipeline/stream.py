class Stream:
    """Redirects write() calls to a Qt signal for GUI log output."""

    def __init__(self, signal):
        self._sig = signal
        self._buf = ""

    def write(self, text: str) -> int:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            stripped = line.strip()
            if stripped:
                self._sig.emit(stripped)
        return len(text)

    def flush(self):
        if self._buf.strip():
            self._sig.emit(self._buf.strip())
            self._buf = ""

    def isatty(self) -> bool:
        return False

    def fileno(self):
        raise OSError
