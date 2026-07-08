import os

from loguru import logger

from shared import log as app_log


class TestSetupFileLogging:
    def test_creates_log_file(self, tmp_path):
        app_log._file_sink_id = None  # reset so we can re-init
        app_log.setup_file_logging(str(tmp_path))
        logger.warning("test entry")
        log_path = tmp_path / "app.log"
        assert log_path.exists()
        assert "test entry" in log_path.read_text()
        # cleanup
        logger.remove(app_log._file_sink_id)
        app_log._file_sink_id = None

    def test_idempotent(self, tmp_path):
        app_log._file_sink_id = None
        app_log.setup_file_logging(str(tmp_path))
        sink_id_first = app_log._file_sink_id
        app_log.setup_file_logging(str(tmp_path))  # second call
        assert app_log._file_sink_id == sink_id_first
        logger.remove(app_log._file_sink_id)
        app_log._file_sink_id = None

    def test_creates_log_dir_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "nested" / "logs")
        app_log._file_sink_id = None
        app_log.setup_file_logging(new_dir)
        assert os.path.isdir(new_dir)
        logger.remove(app_log._file_sink_id)
        app_log._file_sink_id = None


class TestGuiSink:
    def test_warning_routed_to_callback(self):
        received = []
        sink_id = app_log.add_gui_sink(received.append)
        logger.warning("gui warning test")
        logger.remove(sink_id)
        assert any("gui warning test" in msg for msg in received)

    def test_error_routed_to_callback(self):
        received = []
        sink_id = app_log.add_gui_sink(received.append)
        logger.error("gui error test")
        logger.remove(sink_id)
        assert any("gui error test" in msg for msg in received)

    def test_debug_not_routed(self):
        received = []
        sink_id = app_log.add_gui_sink(received.append)
        logger.debug("should not appear")
        logger.remove(sink_id)
        assert not any("should not appear" in msg for msg in received)

    def test_remove_gui_sink_stops_routing(self):
        received = []
        sink_id = app_log.add_gui_sink(received.append)
        app_log.remove_gui_sink(sink_id)
        logger.warning("after removal")
        assert not any("after removal" in msg for msg in received)

    def test_remove_nonexistent_sink_no_error(self):
        app_log.remove_gui_sink(99999)  # should not raise


class TestSetupFileLoggingAdditional:
    def teardown_method(self):
        if app_log._file_sink_id is not None:
            logger.remove(app_log._file_sink_id)
            app_log._file_sink_id = None

    def test_info_is_not_written_to_file(self, tmp_path):
        app_log._file_sink_id = None
        app_log.setup_file_logging(str(tmp_path))
        logger.info("info should not be written")
        logger.warning("warning should be written")
        content = (tmp_path / "app.log").read_text()
        assert "warning should be written" in content
        assert "info should not be written" not in content

    def test_error_is_written_to_file(self, tmp_path):
        app_log._file_sink_id = None
        app_log.setup_file_logging(str(tmp_path))
        logger.error("error file log entry")
        content = (tmp_path / "app.log").read_text()
        assert "error file log entry" in content
        assert "ERROR" in content

    def test_log_format_contains_timestamp_level_location_and_message(self, tmp_path):
        app_log._file_sink_id = None
        app_log.setup_file_logging(str(tmp_path))
        logger.warning("format check message")
        content = (tmp_path / "app.log").read_text()
        assert "WARNING" in content
        assert "format check message" in content
        assert "|" in content
        assert ":" in content

    def test_idempotent_call_does_not_switch_log_directory(self, tmp_path):
        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        app_log._file_sink_id = None
        app_log.setup_file_logging(str(first_dir))
        app_log.setup_file_logging(str(second_dir))
        logger.warning("only first sink should receive this")
        assert (first_dir / "app.log").exists()
        assert "only first sink should receive this" in (first_dir / "app.log").read_text()
        assert not (second_dir / "app.log").exists()


class TestGuiSinkAdditional:
    def test_info_not_routed_to_callback(self):
        received = []
        sink_id = app_log.add_gui_sink(received.append)
        try:
            logger.info("gui info should not appear")
        finally:
            logger.remove(sink_id)
        assert not any("gui info should not appear" in msg for msg in received)

    def test_callback_receives_formatted_level_and_message(self):
        received = []
        sink_id = app_log.add_gui_sink(received.append)
        try:
            logger.warning("formatted gui warning")
        finally:
            logger.remove(sink_id)
        assert any(msg == "[WARNING] formatted gui warning" for msg in received)

    def test_gui_sink_strips_trailing_newline(self):
        received = []
        sink_id = app_log.add_gui_sink(received.append)
        try:
            logger.error("no trailing newline")
        finally:
            logger.remove(sink_id)
        assert received
        assert all(not msg.endswith("\n") for msg in received)

    def test_multiple_gui_sinks_receive_same_warning(self):
        first = []
        second = []
        first_sink_id = app_log.add_gui_sink(first.append)
        second_sink_id = app_log.add_gui_sink(second.append)
        try:
            logger.warning("broadcast gui warning")
        finally:
            logger.remove(first_sink_id)
            logger.remove(second_sink_id)
        assert any("broadcast gui warning" in msg for msg in first)
        assert any("broadcast gui warning" in msg for msg in second)

    def test_removing_one_gui_sink_leaves_other_active(self):
        removed = []
        active = []
        removed_sink_id = app_log.add_gui_sink(removed.append)
        active_sink_id = app_log.add_gui_sink(active.append)
        try:
            app_log.remove_gui_sink(removed_sink_id)
            logger.warning("active sink only")
        finally:
            logger.remove(active_sink_id)
        assert not any("active sink only" in msg for msg in removed)
        assert any("active sink only" in msg for msg in active)

    def test_remove_gui_sink_can_be_called_twice(self):
        received = []
        sink_id = app_log.add_gui_sink(received.append)
        app_log.remove_gui_sink(sink_id)
        app_log.remove_gui_sink(sink_id)
        logger.warning("removed twice should not route")
        assert not any("removed twice should not route" in msg for msg in received)

    def test_callback_exception_propagates_through_loguru_without_raising_to_caller(
        self,
    ):
        def emit(_msg):
            raise RuntimeError("callback boom")

        sink_id = app_log.add_gui_sink(emit)
        try:
            logger.warning("callback failure should not raise")
        finally:
            logger.remove(sink_id)
