"""Crawling helpers and orchestration for Phase 2 ingestion."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests

from core.config import settings
from tasks.contracts import CrawlTarget


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


async def run_crawl() -> None:
    """Crawl Honam University pages and feed the indexing pipeline."""
    # Phase 2 wiring is still incremental; target discovery is the first step.
    _ = await discover_html_targets()
    _ = await discover_pdf_targets()
