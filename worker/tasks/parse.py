"""HTML and PDF parsing orchestration for Phase 2 ingestion."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
PARSER_VERSION = "phase2-parser-v4"
logger = logging.getLogger(__name__)


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
    # 시각적으로 숨긴 "본문 시작" 같은 스킵 내비 링크는 검색에 무의미한 노이즈라 제거한다.
    for skip_link in article.select("a.hide"):
        skip_link.decompose()
    return str(article)


TITLE_SELECTORS = ("header", "h1", "h2", "h3")


def extract_document_title(article_html: str) -> str | None:
    """문서 제목을 DOM에서 추출한다.

    페이지별 제목은 <header>나 상위 헤딩(h1~h3)에 들어 있다.
    공통 <title>("호남대학교 학사안내")은 페이지 구분이 안 되므로 쓰지 않는다.
    """
    soup = BeautifulSoup(article_html, "html.parser")
    for selector in TITLE_SELECTORS:
        element = soup.find(selector)
        if element is None:
            continue
        text = " ".join(element.get_text(" ", strip=True).split())
        if text:
            return text
    return None


def get_crawl4ai_components() -> tuple[type, object, type]:
    worker_settings = get_settings()
    os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", worker_settings.crawl4ai_base_directory)

    from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig

    return AsyncWebCrawler, CacheMode, CrawlerRunConfig


class ArticleMarkdownRenderer:
    def __init__(self, *, concurrency: int | None = None) -> None:
        self._concurrency = max(1, concurrency or get_settings().crawl_markdown_concurrency)
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._start_lock = asyncio.Lock()
        self._crawler: Any | None = None
        self._crawler_context: Any | None = None
        self._config: Any | None = None

    async def __aenter__(self) -> MarkdownRenderer:
        return self.render

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await self._close_crawler(exc_type, exc, tb)
        return False

    async def _close_crawler(self, exc_type=None, exc=None, tb=None) -> None:
        if self._crawler_context is not None:
            await self._crawler_context.__aexit__(exc_type, exc, tb)
            self._crawler_context = None
            self._crawler = None

    async def _ensure_crawler(self) -> None:
        if self._crawler is not None:
            return

        async with self._start_lock:
            if self._crawler is not None:
                return

            worker_settings = get_settings()
            async_web_crawler, cache_mode, crawler_run_config = get_crawl4ai_components()
            self._config = crawler_run_config(cache_mode=cache_mode.BYPASS)
            self._crawler_context = async_web_crawler(
                base_directory=worker_settings.crawl4ai_base_directory
            )
            self._crawler = await self._crawler_context.__aenter__()

    async def render(self, article_html: str) -> str:
        async with self._semaphore:
            await self._ensure_crawler()
            try:
                result = await asyncio.wait_for(
                    self._crawler.arun(url=f"raw:{article_html}", config=self._config),
                    timeout=get_settings().crawl_markdown_timeout_seconds,
                )
            except TimeoutError:
                logger.warning(
                    "crawl4ai markdown rendering timed out after %s seconds",
                    get_settings().crawl_markdown_timeout_seconds,
                )
                await self._close_crawler()
                raise
            except Exception:
                await self._close_crawler()
                raise
        markdown = result.markdown.fit_markdown or result.markdown.raw_markdown
        return markdown.strip()


def create_article_markdown_renderer(*, concurrency: int | None = None) -> ArticleMarkdownRenderer:
    return ArticleMarkdownRenderer(concurrency=concurrency)


async def render_markdown_from_article(article_html: str) -> str:
    worker_settings = get_settings()
    async with create_article_markdown_renderer(
        concurrency=worker_settings.crawl_markdown_concurrency
    ) as renderer:
        return await renderer(article_html)


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
        title=extract_document_title(article_html) or target.title_hint,
        menu_path=target.menu_path,
        category=None,
        source_scope=target.source_scope,
        page_kind=target.page_kind,
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

            normalized = normalize_markdown_table(
                block_content,
                target=target,
            )
            if normalized is None:
                continue
            normalized_content, normalized_meta = normalized
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
        source_scope=target.source_scope,
        page_kind=target.page_kind,
        source_type="pdf",
        content_hash=build_content_hash(pdf_bytes, target=target),
        crawled_at=crawled_at or datetime.now(UTC),
        chunks=chunks,
    )
