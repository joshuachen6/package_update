from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from pathlib import Path

_REPOSITORY_HEADERS = {
    "url",
    "repo_url",
    "repository",
    "repo",
    "github url",
    "repository url",
    "repo url",
    "git url",
    "github repository",
    "repository name",
    "image repository",
    "image namespace",
}


def import_from_file(file_path: str) -> list:
    """Import repositories from a spreadsheet, CSV, or plain-text file."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".xlsx":
        return _parse_excel(path)
    if suffix in {".xls", ".ods"}:
        raise ValueError(
            f"{suffix} files are not supported. Save the spreadsheet as .xlsx or .csv and retry."
        )

    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    if _looks_like_jfrog_taskboard(lines[0]):
        return _parse_jfrog_csv(text)
    if "," in lines[0] and not lines[0].strip().startswith("http"):
        return _parse_generic_csv(text)
    return _parse_plain_text(text)


def _normalize_header(value: object) -> str:
    return str(value or "").strip().lower().replace("\n", " ")


def _looks_like_repository_header(values: Iterable[object]) -> bool:
    headers = {_normalize_header(value) for value in values if value is not None}
    if headers & _REPOSITORY_HEADERS:
        return True
    return any(
        token in header
        for header in headers
        for token in ("repository", "repo url", "github url", "git url")
    )


def _looks_like_jfrog_taskboard(header_line: str) -> bool:
    lower = header_line.lower()
    return "vulnerability" in lower and (
        "image repository" in lower
        or "image namespace" in lower
        or "repository" in lower
    )


def _get_csv_value(
    row: dict[str, str | None],
    norm_map: dict[str, str],
    *keys: str,
) -> str:
    for key in keys:
        column = norm_map.get(key)
        if column is not None:
            value = str(row.get(column) or "").strip()
            if value:
                return value
    return ""


def _parse_jfrog_csv(text: str) -> list:
    reader = csv.DictReader(io.StringIO(text))
    repos: dict[str, dict] = {}
    norm_map: dict[str, str] = {}

    for i, row in enumerate(reader):
        if i == 0:
            norm_map = {k.strip().lower(): k for k in row if k}

        repo_url = _get_csv_value(
            row,
            norm_map,
            "image repository",
            "image namespace",
            "repository",
            "repo",
            "github url",
        )
        if not repo_url:
            continue

        cve = _get_csv_value(
            row,
            norm_map,
            "vulnerability",
            "cve",
            "cve id",
            "cve_id",
            "vulnerability id",
        )
        if repo_url not in repos:
            repos[repo_url] = {"url": repo_url, "branch": "", "cves": set()}
        if cve:
            repos[repo_url]["cves"].add(cve)

    return [
        {
            "url": repo["url"],
            "branch": repo["branch"],
            "cves": ", ".join(sorted(repo["cves"])),
        }
        for repo in repos.values()
    ]

def _worksheet_rows(worksheet) -> list:
    rows = []
    for row in worksheet.iter_rows(values_only=True):
        values = tuple(row)
        if any(value is not None and str(value).strip() for value in values):
            rows.append(values)
    return rows


def _find_header_index(rows: list[tuple]) -> int | None:
    for index, row in enumerate(rows[:50]):
        if _looks_like_repository_header(row):
            return index
    return None

def _rows_to_csv(rows: list[tuple], header_index: int) -> str:
    headers = [str(value or "").strip() for value in rows[header_index]]
    width = len(headers)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)

    for row in rows[header_index + 1 :]:
        values = [str(value or "").strip() for value in row[:width]]
        if any(values):
            writer.writerow(values)

    return buffer.getvalue()


def _parse_excel(path: Path) -> list:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError(
            "Excel import requires openpyxl. Install the project dependencies and retry."
        ) from exc

    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"Could not read Excel workbook {path.name}: {exc}") from exc

    try:
        for worksheet in workbook.worksheets:
            rows = _worksheet_rows(worksheet)
            if not rows:
                continue

            header_index = _find_header_index(rows)
            if header_index is None:
                continue

            csv_text = _rows_to_csv(rows, header_index)
            header_line = ",".join(str(value or "").strip() for value in rows[header_index])
            if _looks_like_jfrog_taskboard(header_line):
                result = _parse_jfrog_csv(csv_text)
            else:
                result = _parse_generic_csv(csv_text)

            if result:
                return result
    finally:
        workbook.close()

    return []


def _parse_generic_csv(text: str) -> list:
    reader = csv.DictReader(io.StringIO(text))
    results = []

    for row in reader:
        norm = {
            key.strip().lower(): str(value or "").strip()
            for key, value in row.items()
            if key
        }
        url = (
            norm.get("url")
            or norm.get("repo_url")
            or norm.get("repository")
            or norm.get("repo")
            or norm.get("github url")
            or norm.get("repository url")
            or norm.get("repo url")
            or norm.get("git url")
            or norm.get("github repository")
            or norm.get("repository name")
            or ""
        )
        if not url:
            for key, value in norm.items():
                if value and any(
                    token in key for token in ("url", "repo", "repository", "github")
                ):
                    url = value
                    break

        branch = norm.get("branch") or ""
        cves = (
            norm.get("cves")
            or norm.get("cve")
            or norm.get("vulnerabilities")
            or norm.get("vulnerability")
            or ""
        )
        if url:
            results.append({"url": url, "branch": branch, "cves": cves})

    return results


def _parse_plain_text(text: str) -> list:
    results = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            results.append({"url": line, "branch": "", "cves": ""})
    return results
