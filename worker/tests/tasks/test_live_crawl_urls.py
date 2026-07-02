"""Live crawl URL discovery test.

Run manually with:
RUN_LIVE_CRAWL_URLS=1 uv run pytest tests/tasks/test_live_crawl_urls.py -s -v
"""

import os
import time
from collections import Counter
from urllib.parse import urlparse

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_CRAWL_URLS") != "1",
    reason="live crawl URL discovery is opt-in; set RUN_LIVE_CRAWL_URLS=1",
)


def _site_key(url: str) -> str:
    return urlparse(url).netloc


def _phase_for_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc == "www.honam.ac.kr" and parsed.path == "/main":
        return "main page"
    if parsed.path == "/main":
        return "department main"
    if parsed.path == "/GraduateGrades":
        return "pdf year page"
    return "target validation"


@pytest.mark.asyncio
async def test_live_discover_crawl_urls() -> None:
    from tasks.crawl import discover_html_targets, discover_pdf_targets, fetch_html

    started_at = time.perf_counter()
    request_count = 0
    limit = int(os.getenv("LIVE_CRAWL_URL_LIMIT", "200"))

    def logging_fetcher(url: str) -> str:
        nonlocal request_count

        request_count += 1
        phase = _phase_for_url(url)
        elapsed = time.perf_counter() - started_at
        print(f"[{elapsed:7.2f}s] fetch #{request_count:04d} {phase}: {url}", flush=True)

        html = fetch_html(url)
        elapsed = time.perf_counter() - started_at
        print(f"[{elapsed:7.2f}s] done  #{request_count:04d} bytes={len(html)}", flush=True)
        return html

    print("\n=== live crawl URL discovery ===", flush=True)
    print(f"target output limit: {limit} (set LIVE_CRAWL_URL_LIMIT=0 for all)", flush=True)
    print("step 1/2: discovering and filtering HTML targets", flush=True)
    html_targets = await discover_html_targets(fetcher=logging_fetcher)
    print(f"step 1/2 complete: html_targets={len(html_targets)}", flush=True)

    print("step 2/2: discovering PDF targets", flush=True)
    pdf_targets = await discover_pdf_targets(fetcher=logging_fetcher)
    print(f"step 2/2 complete: pdf_targets={len(pdf_targets)}", flush=True)

    all_targets = [*html_targets, *pdf_targets]
    all_urls = [target.url for target in all_targets]

    assert all_urls
    duplicate_urls = [url for url, count in Counter(all_urls).items() if count > 1]
    if duplicate_urls:
        print("\n=== duplicate urls ===")
        for duplicate_url in duplicate_urls:
            for target in all_targets:
                if target.url == duplicate_url:
                    print(
                        f"{target.source_type} | {target.site_name or '-'} | "
                        f"{target.menu_path} | {target.url}"
                    )
    assert len(all_urls) == len(set(all_urls))

    print("\n=== crawl url summary ===")
    print(f"html_targets: {len(html_targets)}")
    print(f"pdf_targets: {len(pdf_targets)}")
    print(f"total_targets: {len(all_urls)}")

    print("\n=== urls by site ===")
    for site, count in Counter(_site_key(url) for url in all_urls).most_common():
        print(f"{site}: {count}")

    displayed_html_targets = html_targets if limit <= 0 else html_targets[:limit]
    print("\n=== html urls ===")
    for index, target in enumerate(displayed_html_targets, start=1):
        print(f"{index:04d} | {target.site_name or '-'} | {target.menu_path} | {target.url}")
    if limit > 0 and len(html_targets) > limit:
        print(f"... omitted {len(html_targets) - limit} html urls; set LIVE_CRAWL_URL_LIMIT=0")

    print("\n=== pdf urls ===")
    for index, target in enumerate(pdf_targets, start=1):
        print(
            f"{index:04d} | {target.title_hint or target.menu_path} | "
            f"year={target.year or '-'} | {target.url}"
        )
