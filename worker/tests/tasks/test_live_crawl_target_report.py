"""Live crawl target CSV report.

Run manually with:
RUN_LIVE_CRAWL_TARGET_REPORT=1 uv run pytest \
    tests/tasks/test_live_crawl_target_report.py --mode=fast -s -v
"""

from __future__ import annotations

import csv
import hashlib
import os
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import get_args
from urllib.parse import urljoin, urlparse

import pytest
from bs4 import BeautifulSoup

from tasks.contracts import CrawlTarget, PageKind, SourceScope

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _cache_dir() -> Path:
    return _repo_root() / ".data" / "live-crawl-cache"


def _result_dir(pytestconfig: pytest.Config) -> Path:
    configured_dir = pytestconfig.getoption("--out-dir")
    if configured_dir:
        return Path(configured_dir)
    return _repo_root() / "eval" / "results"


def _timestamp(pytestconfig: pytest.Config) -> str:
    fixed_timestamp = pytestconfig.getoption("--timestamp")
    if fixed_timestamp:
        return fixed_timestamp
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _site_key(url: str) -> str:
    return urlparse(url).netloc or "-"


def _phase_for_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc == "www.honam.ac.kr" and parsed.path == "/main":
        return "main page"
    if parsed.path == "/main":
        return "site main"
    if parsed.path == "/GraduateGrades":
        return "pdf year page"
    return "target validation"


def _raw_link_rows(
    *,
    html: str,
    stage: str,
    source_site_name: str,
    source_site_url: str,
    source_page_url: str,
    base_url: str,
    root_selector: str,
    link_selector: str,
) -> list[dict[str, str | bool]]:
    from tasks.crawl import is_download_url, is_honam_url

    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(root_selector)
    if root is None:
        return []

    rows: list[dict[str, str | bool]] = []
    accepted_anchor_ids = {id(anchor) for anchor in root.select(link_selector)}
    for anchor in root.select("a"):
        raw_href = (anchor.get("href") or "").strip()
        absolute_url = urljoin(base_url, raw_href) if raw_href else ""
        data_link_true = anchor.get("data-link") == "true"
        honam_url = bool(absolute_url) and is_honam_url(absolute_url)
        download_url = bool(absolute_url) and is_download_url(absolute_url)
        accepted_by_selector = id(anchor) in accepted_anchor_ids
        drop_reason = _raw_link_drop_reason(
            raw_href=raw_href,
            honam_url=honam_url,
            download_url=download_url,
            accepted_by_selector=accepted_by_selector,
            data_link_true=data_link_true,
        )
        rows.append(
            {
                "stage": stage,
                "source_site_name": source_site_name,
                "source_site_url": source_site_url,
                "source_page_url": source_page_url,
                "selector": f"{root_selector} {link_selector}",
                "raw_href": raw_href,
                "absolute_url": absolute_url,
                "link_text": anchor.get_text(" ", strip=True),
                "data_link_true": data_link_true,
                "is_honam_url": honam_url,
                "is_download_url": download_url,
                "accepted_by_selector": accepted_by_selector,
                "accepted_as_target": False,
                "drop_reason": drop_reason,
            }
        )
    return rows


def _raw_link_drop_reason(
    *,
    raw_href: str,
    honam_url: bool,
    download_url: bool,
    accepted_by_selector: bool,
    data_link_true: bool,
) -> str:
    if not raw_href:
        return "empty_href"
    if data_link_true and not accepted_by_selector:
        return "data_link_excluded"
    if not accepted_by_selector:
        return "selector_excluded"
    if not honam_url:
        return "external_url"
    if download_url:
        return "download_url"
    return "accepted"


def test_raw_link_rows_marks_data_link_true_as_selector_excluded() -> None:
    rows = _raw_link_rows(
        html="""
        <html><body><ul id="mainMenu">
          <li><a href="/Normal">정상</a></li>
          <li><a href="/Redirect" data-link="true">입학 바로가기</a></li>
        </ul></body></html>
        """,
        stage="seed_main_menu",
        source_site_name="호남대학교",
        source_site_url="https://www.honam.ac.kr",
        source_page_url="https://www.honam.ac.kr/main",
        base_url="https://www.honam.ac.kr",
        root_selector="ul#mainMenu",
        link_selector='a:not([data-link="true"])',
    )

    excluded = next(row for row in rows if row["raw_href"] == "/Redirect")
    assert excluded["data_link_true"] is True
    assert excluded["accepted_by_selector"] is False
    assert excluded["drop_reason"] == "data_link_excluded"


def _build_summary_rows(targets: list[CrawlTarget]) -> list[dict[str, str | int]]:
    source_scope_counts = Counter(target.source_scope for target in targets)
    page_kind_counts = Counter(target.page_kind for target in targets)
    source_scope_page_kind_counts = Counter(
        (target.source_scope, target.page_kind) for target in targets
    )

    summary_rows: list[dict[str, str | int]] = []
    for source_scope in get_args(SourceScope):
        summary_rows.append(
            {
                "group_type": "source_scope",
                "source_scope": source_scope,
                "page_kind": "",
                "site_host": "",
                "count": source_scope_counts[source_scope],
            }
        )
    for page_kind in get_args(PageKind):
        summary_rows.append(
            {
                "group_type": "page_kind",
                "source_scope": "",
                "page_kind": page_kind,
                "site_host": "",
                "count": page_kind_counts[page_kind],
            }
        )
    for source_scope in get_args(SourceScope):
        for page_kind in get_args(PageKind):
            summary_rows.append(
                {
                    "group_type": "source_scope_page_kind",
                    "source_scope": source_scope,
                    "page_kind": page_kind,
                    "site_host": "",
                    "count": source_scope_page_kind_counts[(source_scope, page_kind)],
                }
            )

    site_counts = Counter(_site_key(target.site_url or target.url) for target in targets)
    for site_host, count in site_counts.most_common():
        summary_rows.append(
            {
                "group_type": "site_host",
                "source_scope": "",
                "page_kind": "",
                "site_host": site_host,
                "count": count,
            }
        )

    return summary_rows


def test_build_summary_rows_includes_zero_count_metadata_values() -> None:
    rows = _build_summary_rows(
        [
            CrawlTarget(
                url="https://www.honam.ac.kr/General_Rest",
                menu_path="학사안내 > 휴학",
                source_type="html",
                source_scope="general_academic",
                page_kind="academic",
                site_url="https://www.honam.ac.kr",
            )
        ]
    )

    source_scope_rows = [row for row in rows if row["group_type"] == "source_scope"]
    page_kind_rows = [row for row in rows if row["group_type"] == "page_kind"]
    pair_rows = [row for row in rows if row["group_type"] == "source_scope_page_kind"]

    assert {row["source_scope"] for row in source_scope_rows} == set(get_args(SourceScope))
    assert {row["page_kind"] for row in page_kind_rows} == set(get_args(PageKind))
    assert len(pair_rows) == len(get_args(SourceScope)) * len(get_args(PageKind))
    assert {
        (row["source_scope"], row["page_kind"], row["count"])
        for row in pair_rows
        if row["source_scope"] == "admission" and row["page_kind"] == "certificate"
    } == {("admission", "certificate", 0)}


@pytest.mark.asyncio
async def test_live_write_crawl_target_report(pytestconfig: pytest.Config) -> None:
    from tasks.crawl import (
        dedupe_targets,
        discover_html_targets_with_failures,
        discover_pdf_targets,
        extract_department_sites,
        extract_menu_targets,
        fetch_html,
        is_redirect_page,
        limit_crawl_targets,
        settings,
    )

    if os.getenv("RUN_LIVE_CRAWL_TARGET_REPORT") != "1":
        pytest.skip("live crawl target report is opt-in; set RUN_LIVE_CRAWL_TARGET_REPORT=1")

    mode = pytestconfig.getoption("--mode")
    if mode not in {"fast", "full"}:
        raise ValueError("--mode must be one of: fast, full")

    started_at = time.perf_counter()
    request_count = 0
    cache_hits = 0
    verbose_fetch = pytestconfig.getoption("--verbose-fetch")
    force = pytestconfig.getoption("--force")
    failures: list[str] = []
    raw_link_rows: list[dict[str, str | bool]] = []
    raw_link_keys: set[tuple[str, str, str, str]] = set()
    site_names_by_url: dict[str, str] = {}
    cache_dir = _cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    def elapsed() -> float:
        return time.perf_counter() - started_at

    async def progress_callback(stage: str, *, processed_pages: int, total_pages: int) -> None:
        if total_pages > 0:
            percent = processed_pages / total_pages * 100
            progress = f"{processed_pages}/{total_pages} ({percent:5.1f}%)"
        else:
            progress = f"{processed_pages}/{total_pages}"
        print(f"[{elapsed():7.2f}s] {stage}: {progress}", flush=True)

    def remember_site(site_url: str, site_name: str) -> None:
        site_names_by_url[site_url.rstrip("/")] = site_name

    def append_raw_link_rows(rows: list[dict[str, str | bool]]) -> None:
        for row in rows:
            key = (
                str(row["stage"]),
                str(row["source_page_url"]),
                str(row["raw_href"]),
                str(row["absolute_url"]),
            )
            if key in raw_link_keys:
                continue
            raw_link_rows.append(row)
            raw_link_keys.add(key)

    def source_site_for_page(url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        site_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else url
        return site_url, site_names_by_url.get(site_url.rstrip("/"), parsed.netloc or "-")

    def collect_article_raw_links(html: str, source_page_url: str) -> None:
        source_site_url, source_site_name = source_site_for_page(source_page_url)
        append_raw_link_rows(
            _raw_link_rows(
                html=html,
                stage="article_link",
                source_site_name=source_site_name,
                source_site_url=source_site_url,
                source_page_url=source_page_url,
                base_url=source_page_url,
                root_selector="article.articleBox",
                link_selector="a[href]",
            )
        )

    def collect_main_page_raw_links(html: str, source_page_url: str) -> None:
        parsed = urlparse(source_page_url)
        if parsed.path != settings.crawl_main_path:
            return

        source_site_url, source_site_name = source_site_for_page(source_page_url)
        seed_urls = {seed.url.rstrip("/") for seed in settings.crawl_seed_sites}
        seed_by_url = {seed.url.rstrip("/"): seed for seed in settings.crawl_seed_sites}
        is_seed_page = source_site_url.rstrip("/") in seed_urls
        append_raw_link_rows(
            _raw_link_rows(
                html=html,
                stage="seed_main_menu" if is_seed_page else "department_main_menu",
                source_site_name=source_site_name,
                source_site_url=source_site_url,
                source_page_url=source_page_url,
                base_url=source_site_url,
                root_selector=settings.crawl_menu_selector,
                link_selector=settings.crawl_menu_link_selector,
            )
        )

        seed = seed_by_url.get(source_site_url.rstrip("/"))
        if seed is None or not seed.discover_department_sites:
            return

        department_rows = _raw_link_rows(
            html=html,
            stage="seed_department_list",
            source_site_name=source_site_name,
            source_site_url=source_site_url,
            source_page_url=source_page_url,
            base_url=source_site_url,
            root_selector=settings.crawl_department_selector,
            link_selector=settings.crawl_department_link_selector,
        )
        for row in department_rows:
            if row["is_honam_url"] and row["absolute_url"]:
                remember_site(str(row["absolute_url"]), str(row["link_text"]))
        append_raw_link_rows(department_rows)

    for seed in settings.crawl_seed_sites:
        remember_site(seed.url, seed.name)

    def logging_fetcher(url: str) -> str:
        nonlocal cache_hits, request_count

        cache_path = cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.html"
        if cache_path.exists() and not force:
            cache_hits += 1
            if verbose_fetch:
                print(
                    f"[{elapsed():7.2f}s] cache hit #{cache_hits:04d} {_phase_for_url(url)}: {url}",
                    flush=True,
                )
            html = cache_path.read_text(encoding="utf-8")
            collect_main_page_raw_links(html, url)
            collect_article_raw_links(html, url)
            return html

        request_count += 1
        current_request = request_count
        if verbose_fetch:
            print(
                f"[{elapsed():7.2f}s] fetch #{current_request:04d} {_phase_for_url(url)}: {url}",
                flush=True,
            )

        html = fetch_html(url)
        cache_path.write_text(html, encoding="utf-8")
        collect_main_page_raw_links(html, url)
        collect_article_raw_links(html, url)

        if verbose_fetch:
            print(
                f"[{elapsed():7.2f}s] done  #{current_request:04d} bytes={len(html)}",
                flush=True,
            )
        return html

    async def discover_fast_html_targets():
        targets = []
        seed_source_scopes_by_host = {
            urlparse(seed.url).hostname or "": seed.source_scope
            for seed in settings.crawl_seed_sites
        }
        seen_department_urls: set[str] = set()
        await progress_callback(
            "홈페이지 메뉴 수집 중",
            processed_pages=0,
            total_pages=len(settings.crawl_seed_sites),
        )

        for seed_index, seed in enumerate(settings.crawl_seed_sites, start=1):
            normalized_seed_url = seed.url.rstrip("/")
            main_url = urljoin(normalized_seed_url, settings.crawl_main_path)
            try:
                html = logging_fetcher(main_url)
            except Exception as exc:
                failures.append(f"{main_url}: {exc}")
                print(
                    f"[{elapsed():7.2f}s] fetch failed: {main_url}: {exc}",
                    flush=True,
                )
                await progress_callback(
                    "홈페이지 메뉴 수집 중",
                    processed_pages=seed_index,
                    total_pages=len(settings.crawl_seed_sites),
                )
                continue
            if is_redirect_page(html):
                continue

            targets.extend(
                extract_menu_targets(
                    html=html,
                    base_url=normalized_seed_url,
                    site_name=seed.name,
                    site_url=normalized_seed_url,
                    source_scope=seed.source_scope,
                    source_scope_by_host=seed_source_scopes_by_host,
                )
            )
            targets = limit_crawl_targets(dedupe_targets(targets))
            await progress_callback(
                "홈페이지 메뉴 수집 중",
                processed_pages=seed_index,
                total_pages=len(settings.crawl_seed_sites),
            )

            if not seed.discover_department_sites:
                continue

            department_sites = [
                site
                for site in extract_department_sites(html, base_url=normalized_seed_url)
                if site.url not in seen_department_urls
            ]
            seen_department_urls.update(site.url for site in department_sites)
            await progress_callback(
                "학과 사이트 메뉴 수집 중",
                processed_pages=0,
                total_pages=len(department_sites),
            )
            for department_index, department_site in enumerate(department_sites, start=1):
                if (
                    settings.crawl_target_limit > 0
                    and len(dedupe_targets(targets)) >= settings.crawl_target_limit
                ):
                    break

                department_main_url = urljoin(department_site.url, settings.crawl_main_path)
                try:
                    department_html = logging_fetcher(department_main_url)
                except Exception as exc:
                    failures.append(f"{department_main_url}: {exc}")
                    print(
                        f"[{elapsed():7.2f}s] fetch failed: {department_main_url}: {exc}",
                        flush=True,
                    )
                    await progress_callback(
                        "학과 사이트 메뉴 수집 중",
                        processed_pages=department_index,
                        total_pages=len(department_sites),
                    )
                    continue
                if is_redirect_page(department_html):
                    continue

                targets.extend(
                    extract_menu_targets(
                        html=department_html,
                        base_url=department_site.url,
                        site_name=department_site.name,
                        site_url=department_site.url,
                        source_scope="department",
                    )
                )
                targets = limit_crawl_targets(dedupe_targets(targets))
                await progress_callback(
                    "학과 사이트 메뉴 수집 중",
                    processed_pages=department_index,
                    total_pages=len(department_sites),
                )

        return limit_crawl_targets(dedupe_targets(targets))

    print("\n=== live crawl target discovery ===", flush=True)
    print(f"mode: {mode}", flush=True)
    print(f"cache_dir: {cache_dir}", flush=True)
    print(f"force: {force}", flush=True)

    print("step 1/2: discovering HTML targets", flush=True)
    if mode == "fast":
        html_targets = await discover_fast_html_targets()
    else:
        html_discovery = await discover_html_targets_with_failures(
            fetcher=logging_fetcher,
            progress_callback=progress_callback,
        )
        html_targets = html_discovery.targets
        failures.extend(html_discovery.failures)
        if html_discovery.failures:
            print("\n=== html discovery failures ===", flush=True)
            for failure in html_discovery.failures[:20]:
                print(failure, flush=True)
            if len(html_discovery.failures) > 20:
                print(f"... omitted {len(html_discovery.failures) - 20} failures", flush=True)
    print(f"[{elapsed():7.2f}s] step 1/2 complete: html_targets={len(html_targets)}")

    print("step 2/2: discovering PDF targets", flush=True)
    try:
        pdf_targets = await discover_pdf_targets(
            fetcher=logging_fetcher,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        pdf_targets = []
        failures.append(f"PDF discovery: {exc}")
        print(f"[{elapsed():7.2f}s] PDF discovery failed: {exc}", flush=True)
    print(f"[{elapsed():7.2f}s] step 2/2 complete: pdf_targets={len(pdf_targets)}")

    targets = [*html_targets, *pdf_targets]
    assert targets

    urls = [target.url for target in targets]
    duplicate_urls = [url for url, count in Counter(urls).items() if count > 1]
    assert not duplicate_urls

    result_dir = _result_dir(pytestconfig)
    result_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp(pytestconfig)
    targets_path = result_dir / f"crawl-targets-{mode}-{timestamp}.csv"
    summary_path = result_dir / f"crawl-target-summary-{mode}-{timestamp}.csv"
    raw_links_path = result_dir / f"crawl-raw-links-{mode}-{timestamp}.csv"
    target_urls = {target.url for target in targets}
    for row in raw_link_rows:
        accepted_as_target = row["absolute_url"] in target_urls
        row["accepted_as_target"] = accepted_as_target
        if row["drop_reason"] == "accepted" and not accepted_as_target:
            row["drop_reason"] = "not_final_target"

    with targets_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "target_index",
                "source_type",
                "source_scope",
                "page_kind",
                "site_name",
                "site_url",
                "site_host",
                "menu_path",
                "title_hint",
                "year",
                "url",
            ],
        )
        writer.writeheader()
        for index, target in enumerate(targets, start=1):
            writer.writerow(
                {
                    "target_index": index,
                    "source_type": target.source_type,
                    "source_scope": target.source_scope,
                    "page_kind": target.page_kind,
                    "site_name": target.site_name or "",
                    "site_url": target.site_url or "",
                    "site_host": _site_key(target.site_url or target.url),
                    "menu_path": target.menu_path,
                    "title_hint": target.title_hint or "",
                    "year": target.year or "",
                    "url": target.url,
                }
            )

    summary_rows = _build_summary_rows(targets)

    with summary_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["group_type", "source_scope", "page_kind", "site_host", "count"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    with raw_links_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "raw_index",
                "mode",
                "stage",
                "source_site_name",
                "source_site_url",
                "source_page_url",
                "selector",
                "raw_href",
                "absolute_url",
                "link_text",
                "data_link_true",
                "is_honam_url",
                "is_download_url",
                "accepted_by_selector",
                "accepted_as_target",
                "drop_reason",
            ],
        )
        writer.writeheader()
        for index, row in enumerate(raw_link_rows, start=1):
            writer.writerow({"raw_index": index, "mode": mode, **row})

    print("\n=== live crawl target report ===", flush=True)
    print(f"html_targets: {len(html_targets)}", flush=True)
    print(f"pdf_targets: {len(pdf_targets)}", flush=True)
    print(f"total_targets: {len(targets)}", flush=True)
    print(f"requests: {request_count}", flush=True)
    print(f"cache_hits: {cache_hits}", flush=True)
    print(f"failures: {len(failures)}", flush=True)
    print(f"elapsed_seconds: {elapsed():.2f}", flush=True)
    print(f"targets_csv: {targets_path}", flush=True)
    print(f"summary_csv: {summary_path}", flush=True)
    print(f"raw_links_csv: {raw_links_path}", flush=True)

    if failures:
        print("\n=== fetch failures ===", flush=True)
        for failure in failures[:20]:
            print(failure, flush=True)
        if len(failures) > 20:
            print(f"... omitted {len(failures) - 20} failures", flush=True)

    unknown_targets = [
        target
        for target in targets
        if target.source_scope == "unknown" or target.page_kind == "unknown"
    ]
    if unknown_targets:
        print("\n=== unknown samples ===", flush=True)
        for target in unknown_targets[:20]:
            print(
                f"{target.source_type} | {target.source_scope} | {target.page_kind} | "
                f"{target.site_name or '-'} | {target.menu_path} | {target.url}",
                flush=True,
            )
