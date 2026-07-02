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


WEEKDAY_LABELS = frozenset(
    {
        "일",
        "월",
        "화",
        "수",
        "목",
        "금",
        "토",
        "sun",
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "s",
        "m",
        "t",
        "w",
        "f",
    }
)


def is_calendar_table(headers: list[str], body: list[list[str]]) -> bool:
    """달력 표 여부를 판정한다.

    달력은 헤더가 요일이고 본문이 날짜 숫자라 검색에 쓸 의미 정보가 없다.
    헤더가 대부분 요일이고 본문이 대부분 1~2자리 숫자면 달력으로 본다.
    HTML 표와 crawl4ai markdown 표 양쪽에서 같은 기준을 써야, 한쪽만 걸러져
    표 병합 순서가 어긋나거나 그리드 노이즈가 markdown 경로로 새는 일이 없다.
    """
    header_cells = [cell.strip().lower() for cell in headers if cell.strip()]
    if len(header_cells) < 5:
        return False
    weekday_hits = sum(1 for cell in header_cells if cell in WEEKDAY_LABELS)
    if weekday_hits < len(header_cells) * 0.7:
        return False

    numeric = total = 0
    for row in body:
        for cell in row:
            value = cell.strip()
            if not value:
                continue
            total += 1
            if value.isdigit() and len(value) <= 2:
                numeric += 1
    return total == 0 or numeric >= total * 0.6


def table_records(headers: list[str], body: list[list[str]]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for row in body:
        record = {
            header: value for header, value in zip(headers, row, strict=False) if header and value
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
