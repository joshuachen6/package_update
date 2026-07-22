import csv
import os

from shared.utils import ProgressBar, ensure_dir, parse_columns, write_csv_rows


class TestParseColumns:
    def test_none_returns_none(self):
        assert parse_columns(None) is None

    def test_empty_string_returns_none(self):
        assert parse_columns("") is None

    def test_single_column(self):
        assert parse_columns("title") == ["title"]

    def test_multiple_columns(self):
        assert parse_columns("title,description") == ["title", "description"]

    def test_strips_whitespace(self):
        assert parse_columns(" title , description ") == ["title", "description"]

    def test_filters_empty_parts(self):
        assert parse_columns("title,,description") == ["title", "description"]


class TestWriteCsvRows:
    def test_writes_header_and_rows(self, tmp_path):
        path = str(tmp_path / "out.csv")
        rows = [
            {"name": "lodash", "version": "4.17.21"},
            {"name": "react", "version": "18.0.0"},
        ]
        write_csv_rows(path, rows, ["name", "version"])
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            data = list(reader)
        assert len(data) == 2
        assert data[0]["name"] == "lodash"
        assert data[1]["version"] == "18.0.0"

    def test_missing_column_written_as_empty(self, tmp_path):
        path = str(tmp_path / "out.csv")
        rows = [{"name": "lodash"}]
        write_csv_rows(path, rows, ["name", "version"])
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            data = list(reader)
        assert data[0]["version"] == ""

    def test_extra_keys_ignored(self, tmp_path):
        path = str(tmp_path / "out.csv")
        rows = [{"name": "lodash", "extra": "ignored", "version": "4.17.21"}]
        write_csv_rows(path, rows, ["name", "version"])
        with open(path, newline="") as f:
            content = f.read()
        assert "extra" not in content

    def test_empty_rows(self, tmp_path):
        path = str(tmp_path / "out.csv")
        write_csv_rows(path, [], ["name", "version"])
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            data = list(reader)
        assert data == []


class TestEnsureDir:
    def test_creates_directory(self, tmp_path):
        new_dir = str(tmp_path / "new" / "nested" / "dir")
        ensure_dir(new_dir)
        assert os.path.isdir(new_dir)

    def test_existing_directory_no_error(self, tmp_path):
        ensure_dir(str(tmp_path))  # already exists; should not raise


class TestProgressBar:
    def test_disabled_bar_does_not_render(self, capsys):
        ProgressBar(10, "test", enabled=False)
        out = capsys.readouterr().out
        assert out == ""

    def test_update_clamps_to_total(self):
        pb = ProgressBar(5, "test", enabled=False)
        pb.update(10)
        assert pb.current == 5

    def test_update_increments(self):
        pb = ProgressBar(10, "test", enabled=False)
        pb.update(3)
        assert pb.current == 3

    def test_gui_callback_called(self):
        received = []
        ProgressBar._gui_callback = lambda label, cur, tot: received.append((label, cur, tot))
        try:
            pb = ProgressBar(5, "my-label", enabled=True)
            pb.update()
            assert any(r[0] == "my-label" for r in received)
        finally:
            ProgressBar._gui_callback = None

    def test_zero_total_renders_safely(self, capsys):
        pb = ProgressBar(0, "test", enabled=True)
        pb.render()
        out = capsys.readouterr().out
        assert "done" in out.lower() or out == ""

class TestNormalizeLogDir:
    def test_default_is_base_logs(self, tmp_path):
        from shared.utils import normalize_log_dir
        assert normalize_log_dir(None, str(tmp_path)) == str(tmp_path / "logs")

    def test_project_dir_maps_to_logs_child(self, tmp_path):
        from shared.utils import normalize_log_dir

        assert normalize_log_dir(str(tmp_path), str(tmp_path)) == str(tmp_path / "logs")

    def test_existing_logs_dir_is_preserved(self, tmp_path):
        from shared.utils import normalize_log_dir

        logs = tmp_path / "logs"
        assert normalize_log_dir(str(logs), str(tmp_path)) == str(logs)

    def test_custom_parent_maps_to_logs_child(self, tmp_path):
        from shared.utils import normalize_log_dir
        custom = tmp_path / "artifacts"
        assert normalize_log_dir(str(custom), str(tmp_path)) == str(custom / "logs")


class TestSafeBranchDir:
    """Batch runs used a bare row index ("0", "1", "6") for both the checkout
    and log subdirectory, which told you nothing about which branch a
    directory actually held -- and different branches of the same repo
    sharing one batch could clobber each other's logs since branch wasn't
    part of the log path at all. safe_branch_dir replaces the index.
    """

    def test_plain_branch_name_passthrough(self):
        from shared.utils import safe_branch_dir
        assert safe_branch_dir("main") == "main"

    def test_slashes_are_sanitized(self):
        from shared.utils import safe_branch_dir
        assert safe_branch_dir("feature/foo-bar") == "feature-foo-bar"

    def test_empty_or_none_falls_back_to_default(self):
        from shared.utils import safe_branch_dir
        assert safe_branch_dir("") == "default-branch"
        assert safe_branch_dir(None) == "default-branch"

    def test_only_unsafe_characters_falls_back_to_default(self):
        from shared.utils import safe_branch_dir
        assert safe_branch_dir("///") == "default-branch"
