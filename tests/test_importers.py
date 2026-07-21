from __future__ import annotations

from ui.importers import import_from_file


def test_excel_import_reads_saved_changes_on_each_call(tmp_path):
    import openpyxl

    path = tmp_path / "repositories.xlsx"

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Repository URL", "Branch", "CVEs"])
    sheet.append(["https://github.example/old.git", "main", "CVE-OLD"])
    workbook.save(path)
    workbook.close()

    first = import_from_file(str(path))
    assert first == [
        {
            "url": "https://github.example/old.git",
            "branch": "main",
            "cves": "CVE-OLD",
        }
    ]

    workbook = openpyxl.load_workbook(path)
    sheet = workbook.active
    sheet.delete_rows(2, sheet.max_row)
    sheet.append(["https://github.example/new.git", "develop", "CVE-NEW"])
    workbook.save(path)
    workbook.close()

    second = import_from_file(str(path))
    assert second == [
        {
            "url": "https://github.example/new.git",
            "branch": "develop",
            "cves": "CVE-NEW",
        }
    ]
    assert second != first
