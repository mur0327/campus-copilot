"""HTML and PDF parsing helpers for Phase 2 ingestion."""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from tasks.contracts import CrawlTarget, ParsedChunk, ParsedDocument

MarkdownRenderer = Callable[[str], Awaitable[str]]


def build_content_hash(raw_content: str | bytes) -> str:
    payload = raw_content if isinstance(raw_content, bytes) else raw_content.encode("utf-8")
    return hashlib.md5(payload).hexdigest()


def get_settings():
    from core.config import settings

    return settings


def extract_article_html(html: str) -> str:
    worker_settings = get_settings()
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(worker_settings.crawl_content_selector)
    if article is None:
        raise ValueError(f"{worker_settings.crawl_content_selector} not found")
    return str(article)


def get_crawl4ai_components() -> tuple[type, object, type]:
    worker_settings = get_settings()
    os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", worker_settings.crawl4ai_base_directory)

    from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

    return AsyncWebCrawler, CacheMode, CrawlerRunConfig


async def render_markdown_from_article(article_html: str) -> str:
    worker_settings = get_settings()
    async_web_crawler, cache_mode, crawler_run_config = get_crawl4ai_components()
    config = crawler_run_config(cache_mode=cache_mode.BYPASS)
    async with async_web_crawler(base_directory=worker_settings.crawl4ai_base_directory) as crawler:
        result = await crawler.arun(url=f"raw:{article_html}", config=config)
    markdown = result.markdown.fit_markdown or result.markdown.raw_markdown
    return markdown.strip()


def load_pdf_markdown_documents(pdf_path: str) -> list[Document]:
    from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader

    worker_settings = get_settings()
    loader = OpenDataLoaderPDFLoader(
        file_path=pdf_path,
        format="markdown",
        quiet=True,
        hybrid=worker_settings.pdf_hybrid_backend,
        hybrid_mode=worker_settings.pdf_hybrid_mode,
        hybrid_url=worker_settings.pdf_hybrid_url,
        hybrid_fallback=True,
    )
    return loader.load()


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


def extract_html_table_chunks(article_html: str, start_index: int) -> list[ParsedChunk]:
    soup = BeautifulSoup(article_html, "html.parser")
    table_chunks: list[ParsedChunk] = []

    for table in soup.select("table"):
        rows: list[list[str]] = []
        for row in table.select("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.select("th, td")]
            if cells:
                rows.append(cells)

        if not rows:
            continue

        headers = rows[0]
        body = rows[1:]
        content_lines = [" | ".join(headers)]
        content_lines.extend(" | ".join(row) for row in body)
        table_chunks.append(
            ParsedChunk(
                chunk_index=start_index + len(table_chunks),
                content="\n".join(content_lines),
                chunk_type="table",
                meta={"headers": headers, "rows": body},
            )
        )

    return table_chunks


async def parse_html(
    target: CrawlTarget,
    html: str,
    crawled_at: datetime | None = None,
    markdown_renderer: MarkdownRenderer = render_markdown_from_article,
) -> ParsedDocument:
    article_html = extract_article_html(html)
    markdown = await markdown_renderer(article_html)
    text_chunks = markdown_to_text_chunks(markdown)
    table_chunks = extract_html_table_chunks(article_html, start_index=len(text_chunks))

    return ParsedDocument(
        url=target.url,
        title=target.title_hint,
        menu_path=target.menu_path,
        category=None,
        source_type="html",
        content_hash=build_content_hash(article_html),
        crawled_at=crawled_at or datetime.now(UTC),
        chunks=text_chunks + table_chunks,
    )


async def parse_pdf(
    target: CrawlTarget,
    pdf_bytes: bytes,
    crawled_at: datetime | None = None,
    file_loader: Callable[[str], list[Document]] = load_pdf_markdown_documents,
) -> ParsedDocument:
    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / f"{target.year or 'document'}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        with ThreadPoolExecutor(max_workers=1) as executor:
            documents = await asyncio.get_running_loop().run_in_executor(
                executor, file_loader, str(pdf_path)
            )

    chunks: list[ParsedChunk] = []
    chunk_index = 0

    for doc in documents:
        page = doc.metadata.get("page")

        for block_type, block_content in split_markdown_ordered_blocks(doc.page_content):
            if block_type == "text":
                for text_chunk in markdown_to_text_chunks(block_content):
                    chunks.append(
                        ParsedChunk(
                            chunk_index=chunk_index,
                            content=text_chunk.content,
                            chunk_type="text",
                            meta={"page": page, **text_chunk.meta},
                        )
                    )
                    chunk_index += 1
                continue

            chunks.append(
                ParsedChunk(
                    chunk_index=chunk_index,
                    content=block_content,
                    chunk_type="table",
                    meta={"page": page},
                )
            )
            chunk_index += 1

    return ParsedDocument(
        url=target.url,
        title=target.title_hint,
        menu_path=target.menu_path,
        category=None,
        source_type="pdf",
        content_hash=build_content_hash(pdf_bytes),
        crawled_at=crawled_at or datetime.now(UTC),
        chunks=chunks,
    )
