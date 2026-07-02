"""HTML table extraction and chunk reconciliation helpers."""

from __future__ import annotations

from bs4 import BeautifulSoup

from tasks.contracts import ParsedChunk
from tasks.parsers.table_core import format_records_content, is_calendar_table, table_records


def _cell_span(cell, attribute: str) -> int:
    value = cell.get(attribute)
    if value and str(value).isdigit():
        return int(value)
    return 1


def _expand_html_table(table) -> list[list[str]]:
    grid: list[list[str]] = []
    rowspans: dict[tuple[int, int], str] = {}

    for row_index, row in enumerate(table.select("tr")):
        output_row: list[str] = []
        column_index = 0

        for cell in row.select("th, td"):
            while (row_index, column_index) in rowspans:
                output_row.append(rowspans[(row_index, column_index)])
                column_index += 1

            text = cell.get_text(" ", strip=True)
            rowspan = _cell_span(cell, "rowspan")
            colspan = _cell_span(cell, "colspan")

            for offset in range(colspan):
                output_row.append(text)
                for row_offset in range(1, rowspan):
                    rowspans[(row_index + row_offset, column_index + offset)] = text
                column_index += 1

        while (row_index, column_index) in rowspans:
            output_row.append(rowspans[(row_index, column_index)])
            column_index += 1

        if any(output_row):
            grid.append(output_row)

    width = max((len(row) for row in grid), default=0)
    return [row + [""] * (width - len(row)) for row in grid]


def _header_depth(table) -> int:
    depth = 0
    for row in table.select("tr"):
        if row.select("th") and not row.select("td"):
            depth += 1
            continue
        break
    return max(depth, 1)


def _column_headers(header_rows: list[list[str]], width: int) -> list[str]:
    headers: list[str] = []
    for column_index in range(width):
        labels: list[str] = []
        for row in header_rows:
            label = row[column_index].strip()
            if label and label not in labels:
                labels.append(label)
        headers.append(" ".join(labels))
    return headers


def extract_html_table_chunks(article_html: str, start_index: int) -> list[ParsedChunk]:
    soup = BeautifulSoup(article_html, "html.parser")
    table_chunks: list[ParsedChunk] = []

    for table in soup.select("table"):
        rows = _expand_html_table(table)
        if len(rows) < 2:
            continue

        header_depth = _header_depth(table)
        headers = _column_headers(rows[:header_depth], width=len(rows[0]))
        body = rows[header_depth:]
        if is_calendar_table(headers, body):
            # 달력 그리드는 노이즈라 chunk로 만들지 않는다. 실제 학사일정은 본문 목록에서 온다.
            continue
        records = table_records(headers=headers, body=body)
        content = format_records_content(records)
        if not content:
            continue

        table_chunks.append(
            ParsedChunk(
                chunk_index=start_index + len(table_chunks),
                content=content,
                chunk_type="table",
                meta={"headers": headers, "records": records},
            )
        )

    return table_chunks


def prefer_structured_html_table_chunks(
    chunks: list[ParsedChunk],
    html_table_chunks: list[ParsedChunk],
) -> list[ParsedChunk]:
    """Replace markdown table chunks with richer HTML-derived table chunks.

    crawl4ai usually preserves source order better, while BeautifulSoup keeps
    rowspan/colspan structure better. This helper keeps the markdown text order
    and swaps table payloads for the structured HTML representation when present.
    """
    if not html_table_chunks:
        return chunks

    merged: list[ParsedChunk] = []
    html_table_index = 0
    for chunk in chunks:
        if chunk.chunk_type == "table" and html_table_index < len(html_table_chunks):
            structured_chunk = html_table_chunks[html_table_index]
            merged.append(
                ParsedChunk(
                    chunk_index=len(merged),
                    content=structured_chunk.content,
                    chunk_type="table",
                    meta=structured_chunk.meta,
                )
            )
            html_table_index += 1
            continue

        merged.append(
            ParsedChunk(
                chunk_index=len(merged),
                content=chunk.content,
                chunk_type=chunk.chunk_type,
                meta=chunk.meta,
            )
        )

    while html_table_index < len(html_table_chunks):
        structured_chunk = html_table_chunks[html_table_index]
        merged.append(
            ParsedChunk(
                chunk_index=len(merged),
                content=structured_chunk.content,
                chunk_type="table",
                meta=structured_chunk.meta,
            )
        )
        html_table_index += 1

    return merged
