"""HTML and PDF parsing helpers for Phase 2 ingestion."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from bs4 import BeautifulSoup
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


async def parse_pdf(url: str, content: bytes) -> list[dict]:
    """Convert a PDF file into chunk dictionaries."""
    return []
