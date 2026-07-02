"""Graduation-credit PDF table normalization."""

from __future__ import annotations

import re

from tasks.contracts import CrawlTarget
from tasks.parsers.table_core import (
    format_records_content,
    normalize_table_rows,
    table_records,
)

GRADUATION_CREDIT_SUBHEADERS = {"핵심교양", "균형교양", "소양교양", "소계", "전공선택"}


def is_graduation_credit_target(target: CrawlTarget) -> bool:
    return target.source_type == "pdf" and (
        "졸업학점" in target.menu_path or "GraduateGrades" in target.url
    )


def _looks_like_graduation_subheader(row: list[str]) -> bool:
    return bool(GRADUATION_CREDIT_SUBHEADERS.intersection(row))


def _fill_right(headers: list[str]) -> list[str]:
    filled: list[str] = []
    current = ""
    for header in headers:
        if header:
            current = header
        filled.append(current)
    return filled


def _graduation_credit_headers(top_headers: list[str], subheaders: list[str]) -> list[str]:
    propagated_top_headers = _fill_right(top_headers)
    headers: list[str] = []
    for top_header, subheader in zip(propagated_top_headers, subheaders, strict=False):
        if top_header in {"대학", "학과(부)"}:
            headers.append(top_header)
            continue
        if subheader:
            headers.append(f"{top_header} {subheader}".strip())
            continue
        headers.append(top_header)
    return headers


def _fill_down_records(
    records: list[dict[str, str]],
    keys: tuple[str, ...],
) -> list[dict[str, str]]:
    last_values = {key: "" for key in keys}
    filled_records: list[dict[str, str]] = []
    for record in records:
        filled_record = dict(record)
        for key in keys:
            value = filled_record.get(key, "")
            if value:
                last_values[key] = value
            elif last_values[key]:
                filled_record[key] = last_values[key]
        filled_records.append(filled_record)
    return filled_records


def _normalize_graduation_department_values(records: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized_records: list[dict[str, str]] = []
    for record in records:
        normalized_record = dict(record)
        department_value = normalized_record.get("학과(부)")
        if department_value:
            normalized_record["학과(부)"] = re.sub(
                r"(?<=전공)\s+(?=[가-힣A-Za-z]+전공)",
                " / ",
                department_value,
            )
        normalized_records.append(normalized_record)
    return normalized_records


def normalize_graduation_credit_table(rows: list[list[str]]) -> tuple[str, dict[str, object]]:
    if len(rows) < 3 or not _looks_like_graduation_subheader(rows[1]):
        return normalize_table_rows(rows)

    headers = _graduation_credit_headers(rows[0], rows[1])
    records = _normalize_graduation_department_values(
        _fill_down_records(
            table_records(headers=headers, body=rows[2:]),
            keys=("대학",),
        )
    )
    return (
        format_records_content(records),
        {"headers": headers, "records": records},
    )
