"""Markdown block splitting and chunk creation."""

from __future__ import annotations

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from tasks.contracts import CrawlTarget, ParsedChunk
from tasks.parsers.graduation_credit import (
    is_graduation_credit_target,
    normalize_graduation_credit_table,
)
from tasks.parsers.table_core import (
    is_calendar_table,
    is_markdown_separator_row,
    markdown_table_row,
    normalize_table_rows,
)


def split_markdown_ordered_blocks(markdown: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    current_text: list[str] = []
    current_table: list[str] = []

    def flush_text() -> None:
        if current_text:
            blocks.append(("text", "\n".join(current_text).strip()))
            current_text.clear()

    def flush_table() -> None:
        if current_table:
            blocks.append(("table", "\n".join(current_table)))
            current_table.clear()

    for line in markdown.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("|") and stripped_line.endswith("|"):
            if current_text:
                flush_text()
            current_table.append(line.rstrip())
            continue

        if current_table:
            flush_table()

        current_text.append(line)

    flush_text()
    flush_table()
    return blocks


def normalize_markdown_table(
    block_content: str,
    target: CrawlTarget | None = None,
) -> tuple[str, dict[str, object]] | None:
    """markdown 표 블록을 정규화한다. 달력 그리드면 None을 반환해 chunk 생성을 막는다."""
    rows = [
        row
        for row in (markdown_table_row(line) for line in block_content.splitlines())
        if any(row) and not is_markdown_separator_row(row)
    ]
    if not rows:
        return block_content, {}

    if target is not None and is_graduation_credit_target(target):
        return normalize_graduation_credit_table(rows)

    if is_calendar_table(rows[0], rows[1:]):
        # crawl4ai markdown으로 넘어온 달력도 HTML 경로와 같은 기준으로 걸러야
        # 그리드 노이즈가 남지 않고 표 병합 순서도 어긋나지 않는다.
        return None

    return normalize_table_rows(rows)


def markdown_to_text_chunks(markdown: str) -> list[ParsedChunk]:
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "header_1"),
            ("##", "header_2"),
            ("###", "header_3"),
            ("####", "header_4"),
        ],
        strip_headers=False,
    )
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        add_start_index=True,
    )
    split_docs = text_splitter.split_documents(header_splitter.split_text(markdown))
    return [
        ParsedChunk(
            chunk_index=index,
            content=doc.page_content,
            chunk_type="text",
            meta=dict(doc.metadata),
        )
        for index, doc in enumerate(split_docs)
    ]


def markdown_blocks_to_chunks(markdown: str) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    for block_type, block_content in split_markdown_ordered_blocks(markdown):
        if block_type == "text":
            for text_chunk in markdown_to_text_chunks(block_content):
                text_chunk.chunk_index = len(chunks)
                chunks.append(text_chunk)
            continue

        normalized = normalize_markdown_table(block_content)
        if normalized is None:
            continue
        normalized_content, normalized_meta = normalized
        chunks.append(
            ParsedChunk(
                chunk_index=len(chunks),
                content=normalized_content,
                chunk_type="table",
                meta=normalized_meta,
            )
        )
    return chunks
