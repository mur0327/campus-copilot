"""HTML and PDF parsing orchestration for Phase 2 ingestion."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from langchain_core.documents import Document

from tasks.contracts import CrawlTarget, ParsedChunk, ParsedDocument
from tasks.parsers.html_tables import (
    extract_html_table_chunks,
    prefer_structured_html_table_chunks,
)
from tasks.parsers.markdown import (
    markdown_blocks_to_chunks,
    markdown_to_text_chunks,
    normalize_markdown_table,
    split_markdown_ordered_blocks,
)
from tasks.parsers.roadmap import build_semester_roadmap_chunks

MarkdownRenderer = Callable[[str], Awaitable[str]]
PARSER_VERSION = "phase2-parser-v2"


def _target_hash_payload(target: CrawlTarget | None) -> dict[str, object]:
    if target is None:
        return {}
    return {
        "menu_path": target.menu_path,
        "site_name": target.site_name,
        "site_url": target.site_url,
        "source_type": target.source_type,
        "title_hint": target.title_hint,
        "url": target.url,
        "year": target.year,
    }


def build_content_hash(
    raw_content: str | bytes,
    parser_version: str = PARSER_VERSION,
    target: CrawlTarget | None = None,
) -> str:
    payload = raw_content if isinstance(raw_content, bytes) else raw_content.encode("utf-8")
    target_payload = json.dumps(
        _target_hash_payload(target),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    versioned_payload = parser_version.encode("utf-8") + b"\0" + target_payload + b"\0" + payload
    return hashlib.md5(versioned_payload).hexdigest()


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


async def parse_html(
    target: CrawlTarget,
    html: str,
    crawled_at: datetime | None = None,
    markdown_renderer: MarkdownRenderer = render_markdown_from_article,
) -> ParsedDocument:
    article_html = extract_article_html(html)
    markdown = await markdown_renderer(article_html)
    chunks = markdown_blocks_to_chunks(markdown)
    html_table_chunks = extract_html_table_chunks(article_html, start_index=0)
    chunks = prefer_structured_html_table_chunks(chunks, html_table_chunks)
    table_chunks = [chunk for chunk in chunks if chunk.chunk_type == "table"]
    derived_chunks = build_semester_roadmap_chunks(
        target=target,
        table_chunks=table_chunks,
        start_index=len(chunks),
    )

    return ParsedDocument(
        url=target.url,
        title=target.title_hint,
        menu_path=target.menu_path,
        category=None,
        source_type="html",
        content_hash=build_content_hash(article_html, target=target),
        crawled_at=crawled_at or datetime.now(UTC),
        chunks=chunks + derived_chunks,
    )


async def parse_pdf(
    target: CrawlTarget,
    pdf_bytes: bytes,
    crawled_at: datetime | None = None,
    file_loader: Callable[[str], list[Document]] = load_pdf_markdown_documents,
) -> ParsedDocument:
    source_filename = f"{target.year or 'document'}.pdf"
    source_meta = {
        "source_filename": source_filename,
        "year": target.year,
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / source_filename
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
                            meta={**source_meta, "page": page, **text_chunk.meta},
                        )
                    )
                    chunk_index += 1
                continue

            normalized_content, normalized_meta = normalize_markdown_table(
                block_content,
                target=target,
            )
            chunks.append(
                ParsedChunk(
                    chunk_index=chunk_index,
                    content=normalized_content,
                    chunk_type="table",
                    meta={**source_meta, "page": page, **normalized_meta},
                )
            )
            chunk_index += 1

    return ParsedDocument(
        url=target.url,
        title=target.title_hint,
        menu_path=target.menu_path,
        category=None,
        source_type="pdf",
        content_hash=build_content_hash(pdf_bytes, target=target),
        crawled_at=crawled_at or datetime.now(UTC),
        chunks=chunks,
    )
