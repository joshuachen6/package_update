import csv

import ado.extractor as extractor


def test_read_csv_text_rows_dict_mode_id_variants_and_invalid(tmp_path):
    path = tmp_path / "tasks.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ID", "title", "description"])
        writer.writeheader()
        writer.writerow({"ID": "123", "title": "T", "description": "D"})
        writer.writerow({"ID": "bad", "title": "T2", "description": ""})

    rows = extractor.read_csv_text_rows(str(path), ["title", "description"])

    assert rows == [(123, "T | D"), (None, "T2 | ")]


def test_read_csv_text_rows_reader_mode(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("a,b,c\n1,,3\n", encoding="utf-8")

    rows = extractor.read_csv_text_rows(str(path), None)
    assert rows == [(1, "a | b | c"), (2, "1 |  | 3")]


def test_read_csv_full_rows_dict_mode_title_variants_and_invalid_id(tmp_path):
    path = tmp_path / "tasks.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Id", "Title", "description"])
        writer.writeheader()
        writer.writerow({"Id": "456", "Title": "Task title", "description": "Body"})
        writer.writerow({"Id": "", "Title": "No id", "description": "Body2"})

    rows = extractor.read_csv_full_rows(str(path), ["Title", "description"])

    assert rows == [
        (456, "Task title", "Task title | Body"),
        (None, "No id", "No id | Body2"),
    ]


def test_read_csv_full_rows_reader_mode(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("x,y\n", encoding="utf-8")

    assert extractor.read_csv_full_rows(str(path), None) == [(1, "", "x | y")]


def test_build_package_patterns_respects_boundaries():
    patterns = extractor.build_package_patterns({"lodash", "@scope/pkg"})

    assert patterns["lodash"].search("upgrade lodash now")
    assert not patterns["lodash"].search("notlodash")
    assert patterns["@scope/pkg"].search("fix @scope/pkg vulnerability")
    assert not patterns["@scope/pkg"].search("@scope/pkg-extra")


def test_build_fuzzy_patterns_filters_stopwords_digits_and_short_parts():
    patterns = extractor.build_fuzzy_patterns(
        {"spring-core", "left-pad", "abc-12345", "one-two"},
        frozenset({"spring"}),
        min_keyword_len=4,
    )

    assert "left-pad" in patterns
    assert len(patterns["left-pad"]) == 1
    assert patterns["left-pad"][0].search("left issue")
    assert "spring-core" in patterns
    assert patterns["spring-core"][0].search("core issue")
    assert "abc-12345" not in patterns
    assert "one-two" not in patterns
