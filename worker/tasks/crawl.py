"""Crawling helpers and orchestration for Phase 2 ingestion."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests

from core.config import settings
from core.db import create_pool
from tasks.contracts import CrawlStats, CrawlTarget, ParsedDocument
from tasks.parse import parse_html, parse_pdf
from tasks.storage import (
    create_crawl_job,
    finish_crawl_job,
    load_existing_hashes,
    persist_document,
)

logger = logging.getLogger(__name__)


def fetch_html(url: str, timeout: int | None = None) -> str:
    response = requests.get(
        url=url,
        timeout=timeout or settings.crawl_timeout_seconds,
        impersonate=settings.crawl_impersonate,
    )
    response.raise_for_status()
    return response.text


def extract_menu_targets(html: str, base_url: str) -> list[CrawlTarget]:
    soup = BeautifulSoup(html, "html.parser")
    menu_root = soup.select_one(settings.crawl_menu_selector)
    if menu_root is None:
        return []

    deduped: dict[str, CrawlTarget] = {}
    for anchor in menu_root.select('a:not([data-link="true"])'):
        href = anchor.get("href")
        if not href:
            continue

        absolute_url = urljoin(base_url, href)
        if absolute_url in deduped:
            continue

        deduped[absolute_url] = CrawlTarget(
            url=absolute_url,
            menu_path=anchor.get_text(strip=True),
            source_type="html",
        )

    return list(deduped.values())


def extract_pdf_years(html: str) -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    select_tag = soup.select_one("select#selectYear")
    if select_tag is None:
        return []

    years: list[int] = []
    for option in select_tag.select("option"):
        value = option.get("value")
        if value and value.isdigit():
            years.append(int(value))

    return sorted(years, reverse=True)


def build_graduation_pdf_targets(
    years: list[int],
    base_url: str,
    graduation_path: str,
    year_limit: int,
) -> list[CrawlTarget]:
    prefix = graduation_path.strip("/")
    normalized_base_url = base_url.rstrip("/")
    return [
        CrawlTarget(
            url=f"{normalized_base_url}/{prefix}/pdfdownload/{year}",
            menu_path=f"졸업학점 {year}",
            source_type="pdf",
            title_hint=f"졸업학점 {year}",
            year=year,
        )
        for year in years[:year_limit]
    ]


def is_redirect_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    title_text = soup.title.get_text(strip=True) if soup.title else ""
    return title_text.casefold() == "page moved"


async def _fetch_html_in_thread(fetcher: Callable[[str], str], url: str) -> str:
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return await loop.run_in_executor(executor, fetcher, url)
    finally:
        executor.shutdown(wait=True)


async def discover_html_targets(fetcher: Callable[[str], str] = fetch_html) -> list[CrawlTarget]:
    main_url = urljoin(settings.crawl_target_url, settings.crawl_main_path)
    html = await _fetch_html_in_thread(fetcher, main_url)
    if is_redirect_page(html):
        return []
    return extract_menu_targets(html=html, base_url=settings.crawl_target_url)


async def discover_pdf_targets(fetcher: Callable[[str], str] = fetch_html) -> list[CrawlTarget]:
    html = await _fetch_html_in_thread(
        fetcher,
        urljoin(settings.crawl_target_url, settings.crawl_graduation_path),
    )
    if is_redirect_page(html):
        return []
    years = extract_pdf_years(html)
    return build_graduation_pdf_targets(
        years=years,
        base_url=settings.crawl_target_url,
        graduation_path=settings.crawl_graduation_path,
        year_limit=settings.crawl_pdf_year_limit,
    )


def fetch_pdf_bytes(url: str, timeout: int | None = None) -> bytes:
    response = requests.get(
        url=url,
        timeout=timeout or settings.crawl_timeout_seconds,
        impersonate=settings.crawl_impersonate,
    )
    response.raise_for_status()
    return response.content


async def _fetch_document(target: CrawlTarget) -> ParsedDocument:
    if target.source_type == "html":
        html = await asyncio.to_thread(fetch_html, target.url)
        return await parse_html(target=target, html=html)

    pdf_bytes = await asyncio.to_thread(fetch_pdf_bytes, target.url)
    return await parse_pdf(target=target, pdf_bytes=pdf_bytes)


async def execute_ingestion(
    html_targets: list[CrawlTarget],
    pdf_targets: list[CrawlTarget],
) -> CrawlStats:
    targets = [*html_targets, *pdf_targets]
    pages_crawled = 0
    pages_changed = 0
    failures: list[str] = []

    pool = await create_pool()
    try:
        async with pool.acquire() as connection:
            crawl_job_id = await create_crawl_job(connection)
            try:
                parsed_documents: list[ParsedDocument] = []

                for target in targets:
                    try:
                        parsed_documents.append(await _fetch_document(target))
                    except Exception as exc:  # pragma: no cover - exercised through integration
                        failures.append(f"{target.url}: {exc}")

                existing_hashes = await load_existing_hashes(
                    connection,
                    [document.url for document in parsed_documents],
                )

                for document in parsed_documents:
                    pages_crawled += 1
                    if existing_hashes.get(document.url) == document.content_hash:
                        continue

                    await persist_document(connection, document)
                    pages_changed += 1

                await finish_crawl_job(
                    connection,
                    crawl_job_id,
                    status="completed",
                    pages_crawled=pages_crawled,
                    pages_changed=pages_changed,
                    error="\n".join(failures) if failures else None,
                )
            except Exception as exc:
                await finish_crawl_job(
                    connection,
                    crawl_job_id,
                    status="failed",
                    pages_crawled=pages_crawled,
                    pages_changed=pages_changed,
                    error=str(exc),
                )
                raise
    finally:
        await pool.close()

    return CrawlStats(
        pages_crawled=pages_crawled,
        pages_changed=pages_changed,
        failures=failures,
    )


async def run_crawl() -> CrawlStats:
    """Crawl Honam University pages and feed the indexing pipeline."""
    html_targets, pdf_targets = await asyncio.gather(
        discover_html_targets(),
        discover_pdf_targets(),
    )
    stats = await execute_ingestion(html_targets, pdf_targets)
    logger.info(
        "crawl completed: pages_crawled=%s pages_changed=%s failures=%s",
        stats.pages_crawled,
        stats.pages_changed,
        len(stats.failures),
    )
    return stats
