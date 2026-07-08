from unittest.mock import patch

import pytest


class TestPreflight:
    def test_passes_when_both_tools_present(self):
        with patch("shutil.which", return_value="/usr/bin/tool"):
            from shared.preflight import check

            check()  # should not raise

    def test_exits_when_az_missing(self):
        def which(name):
            return None if name == "az" else "/usr/bin/tool"

        with patch("shutil.which", side_effect=which):
            from shared import preflight

            with pytest.raises(SystemExit) as exc_info:
                preflight.check()
        assert exc_info.value.code == 1

    def test_exits_when_claude_missing(self):
        def which(name):
            return None if name == "claude" else "/usr/bin/tool"

        with patch("shutil.which", side_effect=which):
            from shared import preflight

            with pytest.raises(SystemExit) as exc_info:
                preflight.check()
        assert exc_info.value.code == 1

    def test_exits_when_both_missing(self):
        with patch("shutil.which", return_value=None):
            from shared import preflight

            with pytest.raises(SystemExit) as exc_info:
                preflight.check()
        assert exc_info.value.code == 1

    def test_error_message_names_missing_tool(self, capsys):
        def which(name):
            return None if name == "claude" else "/usr/bin/tool"

        with patch("shutil.which", side_effect=which):
            from shared import preflight

            with pytest.raises(SystemExit):
                preflight.check()
        err = capsys.readouterr().err
        assert "claude" in err

    def test_error_message_mentions_install_location(self, capsys):
        with patch("shutil.which", return_value=None):
            from shared import preflight

            with pytest.raises(SystemExit):
                preflight.check()
        err = capsys.readouterr().err
        assert "go/shopping" in err or "self-service" in err
