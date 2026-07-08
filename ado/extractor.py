from __future__ import annotations

import csv
import re


def read_csv_text_rows(csv_path: str, columns: list[str] | None) -> list[tuple[int | None, str]]:
    """
    Returns (task_id, text) pairs. task_id is the integer value of the 'id' column
    when available (DictReader mode), otherwise the 1-based row index.
    """
    rows: list[tuple[int | None, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        if columns:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id") or row.get("Id") or row.get("ID")
                try:
                    task_id: int | None = int(raw_id)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    task_id = None
                text = " | ".join((row.get(col, "") or "") for col in columns)
                rows.append((task_id, text))
        else:
            reader = csv.reader(f)
            for idx, row in enumerate(reader, start=1):
                rows.append((idx, " | ".join(cell for cell in row if cell is not None)))
    return rows


def read_csv_full_rows(
    csv_path: str, columns: list[str] | None
) -> list[tuple[int | None, str, str]]:
    """Returns (task_id, title, text) triples.

    title is the raw value of the 'title' column (used for advisory ID extraction).
    text is the same concatenated columns string as read_csv_text_rows.
    """
    rows: list[tuple[int | None, str, str]] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        if columns:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id = row.get("id") or row.get("Id") or row.get("ID")
                try:
                    task_id: int | None = int(raw_id)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    task_id = None
                title = row.get("title") or row.get("Title") or ""
                text = " | ".join((row.get(col, "") or "") for col in columns)
                rows.append((task_id, title, text))
        else:
            reader = csv.reader(f)
            for idx, row in enumerate(reader, start=1):
                rows.append((idx, "", " | ".join(cell for cell in row if cell is not None)))
    return rows


def build_package_patterns(known_packages: set[str]) -> dict[str, re.Pattern[str]]:
    patterns: dict[str, re.Pattern[str]] = {}
    for pkg in known_packages:
        escaped = re.escape(pkg)
        patterns[pkg] = re.compile(
            rf"(?<![A-Za-z0-9_@/.-]){escaped}(?![A-Za-z0-9_@/.-])",
            re.IGNORECASE,
        )
    return patterns


def build_fuzzy_patterns(
    known_packages: set[str], stopwords: frozenset, min_keyword_len: int = 5
) -> dict[str, list[re.Pattern[str]]]:
    """
    For each package, compiles one word-boundary pattern per fuzzy keyword.
    A row fuzzy-matches a package if ANY keyword pattern matches.
    Packages with no significant keywords are excluded.
    """
    result: dict[str, list[re.Pattern[str]]] = {}
    for pkg in known_packages:
        parts = re.split(r"[-._:]", pkg.lower())
        keywords = list(
            {
                p
                for p in parts
                if len(p) >= min_keyword_len and p not in stopwords and not p.isdigit()
            }
        )
        if keywords:
            result[pkg] = [
                re.compile(rf"(?<![A-Za-z0-9_]){re.escape(kw)}(?![A-Za-z0-9_])", re.IGNORECASE)
                for kw in keywords
            ]
    return result
