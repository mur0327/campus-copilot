"""Shared table normalization helpers."""

from __future__ import annotations

import re


def clean_table_cell(value: str) -> str:
    cleaned = re.sub(r"<br\s*/?>", " / ", value)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*/\s*", " / ", cleaned)
    cleaned = re.sub(r"(?:/\s*){2,}", "/ ", cleaned)
    cleaned = cleaned.replace("핵심 교양", "핵심교양")
    cleaned = cleaned.replace("균형 교양", "균형교양")
    cleaned = cleaned.replace("소양 교양", "소양교양")
    return cleaned.strip()


def markdown_table_row(line: str) -> list[str]:
    stripped_line = line.strip()
    if stripped_line.startswith("|"):
        stripped_line = stripped_line[1:]
    if stripped_line.endswith("|"):
        stripped_line = stripped_line[:-1]
    return [clean_table_cell(cell) for cell in stripped_line.split("|")]


def is_markdown_separator_row(row: list[str]) -> bool:
    return bool(row) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in row)


def table_records(headers: list[str], body: list[list[str]]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for row in body:
        record = {
            header: value
            for header, value in zip(headers, row, strict=False)
            if header and value
        }
        if record:
            records.append(record)
    return records


def format_records_content(records: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for record in records:
        parts = [f"{header}: {value}" for header, value in record.items()]
        if parts:
            lines.append(" | ".join(parts))
    return "\n".join(lines)


def normalize_table_rows(rows: list[list[str]]) -> tuple[str, dict[str, object]]:
    if not rows:
        return "", {}

    headers = rows[0]
    body = rows[1:]
    records = table_records(headers=headers, body=body)
    if not records:
        return " | ".join(headers), {"headers": headers, "records": []}

    return (
        format_records_content(records),
        {"headers": headers, "records": records},
    )
