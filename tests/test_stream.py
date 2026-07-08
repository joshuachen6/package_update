import pytest

from pipeline.stream import Stream


class MockSignal:
    def __init__(self):
        self.emitted = []

    def emit(self, text):
        self.emitted.append(text)


class TestStream:
    def setup_method(self):
        self.sig = MockSignal()
        self.stream = Stream(self.sig)

    def test_write_complete_line_emits(self):
        self.stream.write("hello\n")
        assert "hello" in self.sig.emitted

    def test_write_partial_line_buffered(self):
        self.stream.write("partial")
        assert self.sig.emitted == []

    def test_write_multiple_complete_lines(self):
        self.stream.write("line1\nline2\n")
        assert "line1" in self.sig.emitted
        assert "line2" in self.sig.emitted

    def test_write_partial_then_complete(self):
        self.stream.write("hel")
        self.stream.write("lo\n")
        assert "hello" in self.sig.emitted

    def test_blank_lines_not_emitted(self):
        self.stream.write("  \n")
        assert self.sig.emitted == []

    def test_carriage_return_normalized(self):
        self.stream.write("line\r\n")
        assert "line" in self.sig.emitted

    def test_bare_cr_normalized(self):
        self.stream.write("progress\r")
        self.stream.write("done\n")
        assert "done" in self.sig.emitted

    def test_flush_emits_remaining_buffer(self):
        self.stream.write("no newline")
        self.stream.flush()
        assert "no newline" in self.sig.emitted

    def test_flush_empty_buffer_no_emit(self):
        self.stream.flush()
        assert self.sig.emitted == []

    def test_flush_blank_buffer_no_emit(self):
        self.stream.write("   ")
        self.stream.flush()
        assert self.sig.emitted == []

    def test_isatty_returns_false(self):
        assert self.stream.isatty() is False

    def test_fileno_raises(self):
        with pytest.raises(OSError):
            self.stream.fileno()

    def test_write_returns_length(self):
        text = "hello\n"
        result = self.stream.write(text)
        assert result == len(text)
