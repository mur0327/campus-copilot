"""Live crawl sampling tests.

Run manually with:
RUN_LIVE_CRAWL=1 uv run pytest tests/tasks/test_live_crawl_sample.py -s -v
"""

import os
from urllib.parse import urljoin

import pytest
from bs4 import BeautifulSoup

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from core.config import settings
from tasks.crawl import fetch_html

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_CRAWL") != "1",
    reason="live crawl sampling is opt-in; set RUN_LIVE_CRAWL=1",
)


def _sample_text(value: str, limit: int = 500) -> str:
    return " ".join(value.split())[:limit]


def _attr_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _print_page_sample(url: str, indent: str = "    ") -> None:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    article = soup.select_one(settings.crawl_content_selector)
    sample_source = str(article) if article else html

    print(f"{indent}url: {url}")
    print(f"{indent}title: {title}")
    print(f"{indent}html_len: {len(html)}")
    print(f"{indent}article_found: {article is not None}")
    print(f"{indent}sample: {_sample_text(sample_source)}")


def test_live_sample_main_menu_and_department_pages() -> None:
    base_url = settings.crawl_target_urls[0]
    main_url = urljoin(base_url, settings.crawl_main_path)
    main_html = fetch_html(main_url)
    main_soup = BeautifulSoup(main_html, "html.parser")

    print("\n=== /main ===")
    print(f"url: {main_url}")
    print(f"html_len: {len(main_html)}")
    print(f"sample: {_sample_text(main_html, 1000)}")

    main_menu = main_soup.select_one(settings.crawl_menu_selector)
    assert main_menu is not None

    print("\n=== mainMenu first 10 ===")
    main_links = main_menu.select(settings.crawl_menu_link_selector)[:10]
    assert main_links

    for index, anchor in enumerate(main_links, start=1):
        href = _attr_text(anchor.get("href"))
        assert href
        url = urljoin(base_url, href)
        label = anchor.get_text(" ", strip=True)
        print(f"\n[{index}] {label}")
        _print_page_sample(url)

    department_nav = main_soup.select_one(settings.crawl_department_selector)
    assert department_nav is not None

    department_links = department_nav.select(settings.crawl_department_link_selector)[:10]
    assert department_links

    print("\n=== department sites first 10, menu first 10 each ===")
    for department_index, department_anchor in enumerate(department_links, start=1):
        department_href = _attr_text(department_anchor.get("href"))
        assert department_href

        department_url = department_href.replace("http://", "https://", 1).rstrip("/")
        department_name = department_anchor.get_text(" ", strip=True)
        department_main_url = urljoin(department_url, settings.crawl_main_path)
        department_html = fetch_html(department_main_url)
        department_soup = BeautifulSoup(department_html, "html.parser")
        department_menu = department_soup.select_one(settings.crawl_menu_selector)

        print(f"\nDEPT[{department_index}] {department_name}")
        print(f"  site_url: {department_url}")
        print(f"  main_url: {department_main_url}")
        print(f"  main_html_len: {len(department_html)}")
        print(f"  main_menu_found: {department_menu is not None}")

        if department_menu is None:
            continue

        department_menu_links = department_menu.select(settings.crawl_menu_link_selector)[:10]
        for menu_index, menu_anchor in enumerate(department_menu_links, start=1):
            href = _attr_text(menu_anchor.get("href"))
            assert href
            url = urljoin(department_url, href)
            label = menu_anchor.get_text(" ", strip=True)
            print(f"\n  [{menu_index}] {label}")
            _print_page_sample(url, indent="      ")
