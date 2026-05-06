"""Course-roadmap derived chunk generation."""

from __future__ import annotations

import re

from tasks.contracts import CrawlTarget, ParsedChunk

SEMESTER_HEADER_PATTERN = re.compile(r"^(?P<grade>[1-4])학년 (?P<semester>[1-2])학기$")
ROADMAP_YEAR_PATTERN = re.compile(r"(20\d{2})")


def _roadmap_year(target: CrawlTarget) -> int | None:
    match = ROADMAP_YEAR_PATTERN.search(f"{target.menu_path} {target.url}")
    return int(match.group(1)) if match else None


def _roadmap_department(target: CrawlTarget) -> str | None:
    if target.site_name:
        return target.site_name
    if ">" in target.menu_path:
        return target.menu_path.split(">", maxsplit=1)[0].strip()
    return None


def _category_label(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", value).strip() or value


def build_semester_roadmap_chunks(
    target: CrawlTarget,
    table_chunks: list[ParsedChunk],
    start_index: int,
) -> list[ParsedChunk]:
    year = _roadmap_year(target)
    department = _roadmap_department(target)
    if year is None or department is None or "교과목로드맵" not in target.menu_path:
        return []

    grouped: dict[tuple[int, int], list[tuple[str, str]]] = {}
    for table_chunk in table_chunks:
        records = table_chunk.meta.get("records", [])
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            category = record.get("구분")
            if not isinstance(category, str) or not category:
                continue
            for header, value in record.items():
                if not isinstance(header, str) or not isinstance(value, str) or not value:
                    continue
                match = SEMESTER_HEADER_PATTERN.match(header)
                if match is None:
                    continue
                key = (int(match.group("grade")), int(match.group("semester")))
                grouped.setdefault(key, []).append((_category_label(category), value))

    chunks: list[ParsedChunk] = []
    for (grade, semester), entries in sorted(grouped.items()):
        lines = [f"{department} 교과목로드맵 {year}년 {grade}학년 {semester}학기"]
        lines.extend(f"{category}: {value}" for category, value in entries)
        chunks.append(
            ParsedChunk(
                chunk_index=start_index + len(chunks),
                content="\n".join(lines),
                chunk_type="text",
                meta={
                    "derived_from": "table",
                    "kind": "semester_roadmap",
                    "department": department,
                    "year": year,
                    "grade": grade,
                    "semester": semester,
                },
            )
        )

    return chunks
