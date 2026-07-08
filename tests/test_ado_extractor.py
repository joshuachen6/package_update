import csv

from ado.extractor import (
    build_fuzzy_patterns,
    build_package_patterns,
    read_csv_text_rows,
)


def write_csv(path, rows, fieldnames=None):
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class TestReadCsvTextRows:
    def test_with_columns(self, tmp_path):
        path = str(tmp_path / "tasks.csv")
        write_csv(
            path,
            [
                {
                    "id": "42",
                    "title": "Upgrade lodash",
                    "description": "Bump to 4.17.21",
                },
                {"id": "43", "title": "Fix react", "description": "Use 18.0.0"},
            ],
        )
        rows = read_csv_text_rows(path, ["title", "description"])
        assert len(rows) == 2
        task_id, text = rows[0]
        assert task_id == 42
        assert "Upgrade lodash" in text
        assert "4.17.21" in text

    def test_without_columns_uses_row_index(self, tmp_path):
        path = str(tmp_path / "simple.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["col1", "col2"])
            writer.writerow(["value1", "value2"])
        rows = read_csv_text_rows(path, None)
        assert len(rows) == 2
        idx, _text = rows[0]
        assert idx == 1

    def test_missing_id_column_task_id_is_none(self, tmp_path):
        path = str(tmp_path / "no_id.csv")
        write_csv(path, [{"title": "Update spring", "description": "Use 5.3.27"}])
        rows = read_csv_text_rows(path, ["title", "description"])
        task_id, _text = rows[0]
        assert task_id is None

    def test_text_joins_columns_with_pipe(self, tmp_path):
        path = str(tmp_path / "tasks.csv")
        write_csv(path, [{"id": "1", "title": "A", "description": "B"}])
        rows = read_csv_text_rows(path, ["title", "description"])
        _, text = rows[0]
        assert text == "A | B"

    def test_empty_csv(self, tmp_path):
        path = str(tmp_path / "empty.csv")
        write_csv(path, [], fieldnames=["id", "title"])
        rows = read_csv_text_rows(path, ["title"])
        assert rows == []


class TestBuildPackagePatterns:
    def test_creates_pattern_per_package(self):
        patterns = build_package_patterns({"lodash", "react"})
        assert "lodash" in patterns
        assert "react" in patterns

    def test_pattern_matches_package(self):
        patterns = build_package_patterns({"lodash"})
        assert patterns["lodash"].search("Upgrade lodash to 4.17.21")

    def test_pattern_case_insensitive(self):
        patterns = build_package_patterns({"lodash"})
        assert patterns["lodash"].search("LODASH version")

    def test_pattern_no_false_positives_in_word(self):
        patterns = build_package_patterns({"react"})
        # "reactive" should not match "react" due to word-boundary guard
        assert not patterns["react"].search("reactive-programming")

    def test_empty_set(self):
        assert build_package_patterns(set()) == {}


class TestBuildFuzzyPatterns:
    STOPWORDS = frozenset({"starter", "support", "framework", "client", "server"})

    def test_creates_patterns_for_significant_keywords(self):
        patterns = build_fuzzy_patterns({"spring-boot"}, self.STOPWORDS)
        assert "spring-boot" in patterns
        assert any(p.search("spring framework") for p in patterns["spring-boot"])

    def test_excludes_stopword_tokens(self):
        patterns = build_fuzzy_patterns({"spring-starter"}, self.STOPWORDS)
        # "starter" is a stopword, "spring" is significant
        if "spring-starter" in patterns:
            pattern_texts = [p.pattern for p in patterns["spring-starter"]]
            assert not any("starter" in pt for pt in pattern_texts)

    def test_excludes_short_tokens(self):
        patterns = build_fuzzy_patterns({"my-lib"}, self.STOPWORDS)
        # "lib" (3 chars) and "my" (2 chars) both < 5 → no significant keywords → not in result
        if "my-lib" in patterns:
            for p in patterns["my-lib"]:
                assert len(p.pattern) > 5  # keyword must be >= 5 chars

    def test_empty_known_packages(self):
        assert build_fuzzy_patterns(set(), self.STOPWORDS) == {}
