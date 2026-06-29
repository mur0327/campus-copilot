"""Crawling helpers and orchestration for Phase 2 ingestion."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from core.config import settings
from core.db import create_pool
from tasks import fetch_cache
from tasks.bm25 import write_bm25_indexes
from tasks.classify import infer_page_kind, infer_source_scope
from tasks.contracts import (
    CrawlDiscoveryResult,
    CrawlStats,
    CrawlTarget,
    DepartmentSite,
    DocumentProcessingStatus,
    ParsedDocument,
    SourceScope,
)
from tasks.embed import (
    EmbedSummary,
    count_pending_chunks,
    create_chroma_collection,
    create_embedder,
    embed_pending_chunks,
    prune_orphan_vectors,
)
from tasks.parse import (
    MarkdownRenderer,
    build_content_hash,
    create_article_markdown_renderer,
    extract_article_html,
    parse_html,
    parse_pdf,
)
from tasks.storage import (
    ExistingDocumentState,
    crawl_advisory_lock,
    create_crawl_job,
    finish_crawl_job,
    load_existing_document_states,
    persist_document,
    update_crawl_job_progress,
)

logger = logging.getLogger(__name__)
ProgressCallback = Callable[..., Awaitable[None]]
DOWNLOAD_EXTENSIONS = {
    ".doc",
    ".docx",
    ".hwp",
    ".hwpx",
    ".pdf",
    ".ppt",
    ".pptx",
    ".mp3",
    ".mp4",
    ".xls",
    ".xlsx",
    ".zip",
}


@dataclass(slots=True)
class DocumentProcessingResult:
    target: CrawlTarget
    document: ParsedDocument | None = None
    failure: str | None = None

    @property
    def crawled(self) -> bool:
        return self.failure is None

    @property
    def status(self) -> DocumentProcessingStatus:
        if self.failure is not None:
            return DocumentProcessingStatus.FAILED
        if self.document is not None:
            return DocumentProcessingStatus.CHANGED
        return DocumentProcessingStatus.SKIPPED


@dataclass(slots=True)
class ArticleExpansionResult:
    parent_url: str
    targets: list[CrawlTarget]
    failure: str | None = None


def apply_crawl_target_limit(
    html_targets: list[CrawlTarget],
    pdf_targets: list[CrawlTarget],
) -> tuple[list[CrawlTarget], list[CrawlTarget]]:
    if settings.crawl_target_limit <= 0:
        return html_targets, pdf_targets

    combined_targets = [*html_targets, *pdf_targets]
    limited_targets = combined_targets[: settings.crawl_target_limit]
    limited_html_targets = [target for target in limited_targets if target.source_type == "html"]
    limited_pdf_targets = [target for target in limited_targets if target.source_type == "pdf"]
    logger.info(
        "crawl target limit applied: limit=%s original_total=%s limited_total=%s "
        "limited_html=%s limited_pdf=%s",
        settings.crawl_target_limit,
        len(combined_targets),
        len(limited_targets),
        len(limited_html_targets),
        len(limited_pdf_targets),
    )
    return limited_html_targets, limited_pdf_targets


def limit_crawl_targets(targets: list[CrawlTarget]) -> list[CrawlTarget]:
    if settings.crawl_target_limit <= 0:
        return targets
    return targets[: settings.crawl_target_limit]


def fetch_html(url: str, timeout: int | None = None) -> str:
    response = requests.get(
        url=url,
        timeout=timeout or settings.crawl_timeout_seconds,
        impersonate=settings.crawl_impersonate,
    )
    response.raise_for_status()
    return response.text


def _fetch_cache_dir() -> Path | None:
    return Path(settings.crawl_fetch_cache_dir) if settings.crawl_fetch_cache_dir else None


def cached_html(url: str) -> str | None:
    # cache_first 모드일 때만 캐시된 원본 HTML을 반환한다(네트워크 회피 재파싱용).
    cache_dir = _fetch_cache_dir()
    if cache_dir is None or settings.crawl_fetch_cache_mode != "cache_first":
        return None
    return fetch_cache.read_html(cache_dir, url)


def store_fetched_html(url: str, html: str) -> None:
    # 검증(extract_article_html)을 통과한 HTML만 캐시에 저장한다.
    cache_dir = _fetch_cache_dir()
    if cache_dir is not None:
        fetch_cache.write_html(cache_dir, url, html)


def cached_pdf_bytes(url: str) -> bytes | None:
    cache_dir = _fetch_cache_dir()
    if cache_dir is None or settings.crawl_fetch_cache_mode != "cache_first":
        return None
    return fetch_cache.read_bytes(cache_dir, url)


def store_fetched_pdf(url: str, data: bytes) -> None:
    # 파싱(parse_pdf)을 통과한 PDF만 캐시에 저장한다.
    cache_dir = _fetch_cache_dir()
    if cache_dir is not None:
        fetch_cache.write_bytes(cache_dir, url, data)


def dedupe_targets(targets: list[CrawlTarget]) -> list[CrawlTarget]:
    deduped: dict[str, CrawlTarget] = {}
    # Menus can expose the same URL through a generic label first and a better
    # contextual label later, so duplicate URLs intentionally keep the last target.
    for target in reversed(targets):
        if target.url in deduped:
            continue
        deduped[target.url] = target
    return list(reversed(list(deduped.values())))


def extract_menu_targets(
    html: str,
    base_url: str,
    site_name: str | None = None,
    site_url: str | None = None,
    source_scope: SourceScope | None = None,
    source_scope_by_host: Mapping[str, SourceScope] | None = None,
) -> list[CrawlTarget]:
    soup = BeautifulSoup(html, "html.parser")
    menu_root = soup.select_one(settings.crawl_menu_selector)
    if menu_root is None:
        return []

    normalized_site_url = site_url or base_url.rstrip("/")
    targets: list[CrawlTarget] = []
    for anchor in menu_root.select(settings.crawl_menu_link_selector):
        href = anchor.get("href")
        if not href:
            continue

        absolute_url = urljoin(base_url, href)
        if not is_honam_url(absolute_url):
            continue

        url_host = urlparse(absolute_url).hostname or ""
        target_source_scope = (
            source_scope_by_host.get(url_host)
            if source_scope_by_host is not None and url_host in source_scope_by_host
            else source_scope
        )

        targets.append(
            CrawlTarget(
                url=absolute_url,
                menu_path=anchor.get_text(strip=True),
                source_type="html",
                source_scope=target_source_scope
                or infer_source_scope(url=absolute_url, site_url=normalized_site_url),
                page_kind=infer_page_kind(
                    url=absolute_url,
                    menu_path=anchor.get_text(strip=True),
                ),
                site_name=site_name,
                site_url=normalized_site_url,
            )
        )

    return dedupe_targets(targets)


def extract_department_sites(
    html: str,
    base_url: str = "https://www.honam.ac.kr",
) -> list[DepartmentSite]:
    soup = BeautifulSoup(html, "html.parser")
    department_root = soup.select_one(settings.crawl_department_selector)
    if department_root is None:
        return []

    sites: list[DepartmentSite] = []
    seen_urls: set[str] = set()
    for anchor in department_root.select(settings.crawl_department_link_selector):
        href = anchor.get("href", "").strip()
        name = anchor.get_text(strip=True)
        if not href or not name:
            continue

        normalized_url = urljoin(base_url, href).rstrip("/")
        if normalized_url.startswith("http://"):
            normalized_url = normalized_url.replace("http://", "https://", 1)
        if not is_honam_url(normalized_url):
            continue
        if urlparse(normalized_url).hostname == "www.honam.ac.kr":
            continue
        if normalized_url in seen_urls:
            continue

        sites.append(DepartmentSite(name=name, url=normalized_url))
        seen_urls.add(normalized_url)

    return sites


def extract_article_box_targets(parent: CrawlTarget, html: str) -> list[CrawlTarget]:
    soup = BeautifulSoup(html, "html.parser")
    targets: list[CrawlTarget] = []
    for anchor in soup.select(settings.crawl_article_link_selector):
        href = anchor.get("href")
        if not href:
            continue
        absolute_url = urljoin(parent.url, href)
        if is_download_url(absolute_url) or not is_honam_url(absolute_url):
            continue

        label = anchor.get_text(strip=True)
        menu_path = parent.menu_path
        if label:
            menu_path = f"{parent.menu_path} > {label}"

        targets.append(
            CrawlTarget(
                url=absolute_url,
                menu_path=menu_path,
                source_type="html",
                source_scope=parent.source_scope,
                page_kind=infer_page_kind(url=absolute_url, menu_path=menu_path),
                title_hint=parent.title_hint,
                site_name=parent.site_name,
                site_url=parent.site_url,
            )
        )

    return dedupe_targets(targets)


def is_download_url(url: str) -> bool:
    path = urlparse(url).path.casefold()
    if "/pdfdownload/" in path or "/download/" in path:
        return True
    return any(path.endswith(extension) for extension in DOWNLOAD_EXTENSIONS)


def is_honam_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    return parsed.scheme in {"http", "https"} and (
        hostname == "honam.ac.kr" or hostname.endswith(".honam.ac.kr")
    )


def extract_pdf_years(html: str) -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    select_tag = soup.select_one(settings.crawl_pdf_year_selector)
    if select_tag is None:
        return []

    years: list[int] = []
    for option in select_tag.select("option"):
        value = option.get("value")
        if value and len(value) == 4 and value.isdigit():
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
            source_scope=infer_source_scope(
                url=f"{normalized_base_url}/{prefix}/pdfdownload/{year}",
                site_url=normalized_base_url,
            ),
            page_kind=infer_page_kind(
                url=f"{normalized_base_url}/{prefix}/pdfdownload/{year}",
                menu_path=f"졸업학점 {year}",
            ),
            title_hint=f"졸업학점 {year}",
            year=year,
        )
        for year in years[:year_limit]
    ]


def is_redirect_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    title_text = soup.title.get_text(strip=True) if soup.title else ""
    return title_text.casefold() == "page moved"


def has_crawl_content(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one(settings.crawl_content_selector) is not None


async def _fetch_html_in_thread(fetcher: Callable[[str], str], url: str) -> str:
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return await loop.run_in_executor(executor, fetcher, url)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


async def _fetch_bytes_in_thread(fetcher: Callable[[str], bytes], url: str) -> bytes:
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return await loop.run_in_executor(executor, fetcher, url)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


async def validate_targets_with_failures(
    targets: list[CrawlTarget],
    fetcher: Callable[[str], str] = fetch_html,
    concurrency: int | None = None,
    progress_callback: ProgressCallback | None = None,
    progress_stage: str = "대상 URL 검증 중",
) -> CrawlDiscoveryResult:
    semaphore = asyncio.Semaphore(concurrency or settings.crawl_validation_concurrency)
    total_targets = len(targets)
    processed_targets = 0

    async def validate(target: CrawlTarget) -> tuple[CrawlTarget | None, str | None]:
        nonlocal processed_targets
        try:
            async with semaphore:
                html = await _fetch_html_in_thread(fetcher, target.url)
        except Exception as exc:
            processed_targets += 1
            if progress_callback is not None:
                await progress_callback(
                    progress_stage,
                    processed_pages=processed_targets,
                    total_pages=total_targets,
                )
            return None, f"{target.url}: {exc}"

        if is_redirect_page(html) or not has_crawl_content(html):
            processed_targets += 1
            if progress_callback is not None:
                await progress_callback(
                    progress_stage,
                    processed_pages=processed_targets,
                    total_pages=total_targets,
                )
            return None, None

        processed_targets += 1
        if progress_callback is not None:
            await progress_callback(
                progress_stage,
                processed_pages=processed_targets,
                total_pages=total_targets,
            )
        return target, None

    results = await asyncio.gather(*(validate(target) for target in targets))
    return CrawlDiscoveryResult(
        targets=dedupe_targets([target for target, _ in results if target is not None]),
        failures=[failure for _, failure in results if failure is not None],
    )


async def expand_article_box_targets_by_parent(
    targets: list[CrawlTarget],
    fetcher: Callable[[str], str] = fetch_html,
    concurrency: int | None = None,
    progress_callback: ProgressCallback | None = None,
    progress_stage: str = "상세 페이지 후보 확인 중",
) -> list[ArticleExpansionResult]:
    semaphore = asyncio.Semaphore(concurrency or settings.crawl_validation_concurrency)
    total_targets = len(targets)
    processed_targets = 0

    async def expand(target: CrawlTarget) -> ArticleExpansionResult:
        nonlocal processed_targets
        try:
            async with semaphore:
                html = await _fetch_html_in_thread(fetcher, target.url)
        except Exception as exc:
            processed_targets += 1
            if progress_callback is not None:
                await progress_callback(
                    progress_stage,
                    processed_pages=processed_targets,
                    total_pages=total_targets,
                )
            return ArticleExpansionResult(
                parent_url=target.url,
                targets=[],
                failure=f"{target.url}: {exc}",
            )

        if is_redirect_page(html) or not has_crawl_content(html):
            processed_targets += 1
            if progress_callback is not None:
                await progress_callback(
                    progress_stage,
                    processed_pages=processed_targets,
                    total_pages=total_targets,
                )
            return ArticleExpansionResult(parent_url=target.url, targets=[])

        article_targets = extract_article_box_targets(parent=target, html=html)
        processed_targets += 1
        if progress_callback is not None:
            await progress_callback(
                progress_stage,
                processed_pages=processed_targets,
                total_pages=total_targets,
            )
        if article_targets:
            return ArticleExpansionResult(parent_url=target.url, targets=[target, *article_targets])

        return ArticleExpansionResult(parent_url=target.url, targets=[target])

    return list(await asyncio.gather(*(expand(target) for target in targets)))


def failure_url(failure: str) -> str:
    return failure.split(": ", maxsplit=1)[0]


async def discover_html_targets_with_failures(
    fetcher: Callable[[str], str] = fetch_html,
    progress_callback: ProgressCallback | None = None,
) -> CrawlDiscoveryResult:
    targets: list[CrawlTarget] = []
    failures: list[str] = []
    seed_source_scopes_by_host = {
        urlparse(seed.url).hostname or "": seed.source_scope for seed in settings.crawl_seed_sites
    }
    seen_department_urls: set[str] = set()

    if progress_callback is not None:
        await progress_callback(
            "홈페이지 메뉴 수집 중",
            processed_pages=0,
            total_pages=len(settings.crawl_seed_sites),
        )

    for seed_index, seed in enumerate(settings.crawl_seed_sites, start=1):
        normalized_seed_url = seed.url.rstrip("/")
        main_url = urljoin(normalized_seed_url, settings.crawl_main_path)
        try:
            html = await _fetch_html_in_thread(fetcher, main_url)
        except Exception as exc:
            logger.warning(
                "dropping crawl root after main page fetch failure: %s (%s)",
                main_url,
                exc,
            )
            failures.append(f"{main_url}: {exc}")
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
        if progress_callback is not None:
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
        if progress_callback is not None:
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
                logger.info(
                    "crawl target limit reached before department expansion: limit=%s",
                    settings.crawl_target_limit,
                )
                break
            department_main_url = urljoin(department_site.url, settings.crawl_main_path)
            try:
                department_html = await _fetch_html_in_thread(fetcher, department_main_url)
            except Exception as exc:
                logger.warning(
                    "dropping department site after main page fetch failure: %s (%s)",
                    department_main_url,
                    exc,
                )
                failures.append(f"{department_main_url}: {exc}")
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
            if progress_callback is not None:
                await progress_callback(
                    "학과 사이트 메뉴 수집 중",
                    processed_pages=department_index,
                    total_pages=len(department_sites),
                )

    deduped_targets = limit_crawl_targets(dedupe_targets(targets))
    if settings.crawl_target_limit > 0:
        logger.info(
            "crawl discovery target limit prepared: limit=%s discovery_parents=%s",
            settings.crawl_target_limit,
            len(deduped_targets),
        )
    first_pass_results = await expand_article_box_targets_by_parent(
        deduped_targets,
        fetcher,
        progress_callback=progress_callback,
        progress_stage="상세 페이지 후보 확인 중",
    )
    first_pass_failures = [
        result.failure for result in first_pass_results if result.failure is not None
    ]
    failed_urls = {failure_url(failure) for failure in first_pass_failures}
    retry_targets = [target for target in deduped_targets if target.url in failed_urls]
    retry_results = await expand_article_box_targets_by_parent(
        retry_targets,
        fetcher=fetcher,
        concurrency=settings.crawl_retry_validation_concurrency,
        progress_callback=progress_callback,
        progress_stage="실패 후보 재확인 중",
    )
    retry_failures = [result.failure for result in retry_results if result.failure is not None]
    recovered_urls = {result.parent_url for result in retry_results if result.targets}
    unresolved_failures = [
        failure for failure in retry_failures if failure_url(failure) not in recovered_urls
    ]
    retry_targets_by_parent = {
        result.parent_url: result.targets for result in retry_results if result.targets
    }
    ordered_targets: list[CrawlTarget] = []
    verified_urls: set[str] = set()

    def append_ordered_targets(new_targets: list[CrawlTarget]) -> None:
        if settings.crawl_target_limit <= 0:
            ordered_targets.extend(new_targets)
            return
        remaining_slots = settings.crawl_target_limit - len(dedupe_targets(ordered_targets))
        if remaining_slots <= 0:
            return
        ordered_targets.extend(new_targets[:remaining_slots])

    for result in first_pass_results:
        if result.failure is not None:
            append_ordered_targets(retry_targets_by_parent.get(result.parent_url, []))
            if result.parent_url in recovered_urls:
                verified_urls.add(result.parent_url)
            continue
        append_ordered_targets(result.targets)
        verified_urls.add(result.parent_url)

    deduped_ordered_targets = limit_crawl_targets(dedupe_targets(ordered_targets))
    final_validation_fetcher = (
        fetcher
        if fetcher is not fetch_html
        else lambda url: fetch_html(url, timeout=settings.crawl_final_validation_timeout_seconds)
    )
    final_validation = await validate_targets_with_failures(
        [target for target in deduped_ordered_targets if target.url not in verified_urls],
        fetcher=final_validation_fetcher,
        concurrency=settings.crawl_final_validation_concurrency,
        progress_callback=progress_callback,
        progress_stage="대상 URL 최종 검증 중",
    )
    final_targets_by_url = {target.url: target for target in final_validation.targets}

    return CrawlDiscoveryResult(
        targets=[
            target
            for target in deduped_ordered_targets
            if target.url in verified_urls or target.url in final_targets_by_url
        ],
        failures=[*failures, *unresolved_failures, *final_validation.failures],
    )


async def discover_html_targets(fetcher: Callable[[str], str] = fetch_html) -> list[CrawlTarget]:
    return (await discover_html_targets_with_failures(fetcher=fetcher)).targets


async def discover_pdf_targets(
    fetcher: Callable[[str], str] = fetch_html,
    progress_callback: ProgressCallback | None = None,
) -> list[CrawlTarget]:
    base_url = next(
        (
            seed.url.rstrip("/")
            for seed in settings.crawl_seed_sites
            if urlparse(seed.url).hostname == "www.honam.ac.kr"
        ),
        next(
            (
                seed.url.rstrip("/")
                for seed in settings.crawl_seed_sites
                if seed.source_scope == "general_academic"
            ),
            settings.crawl_seed_sites[0].url.rstrip("/"),
        ),
    )
    if progress_callback is not None:
        await progress_callback("PDF 대상 확인 중", processed_pages=0, total_pages=1)
    html = await _fetch_html_in_thread(
        fetcher,
        urljoin(base_url, settings.crawl_graduation_path),
    )
    if is_redirect_page(html):
        return []
    years = extract_pdf_years(html)
    targets = build_graduation_pdf_targets(
        years=years,
        base_url=base_url,
        graduation_path=settings.crawl_graduation_path,
        year_limit=settings.crawl_pdf_year_limit,
    )
    if progress_callback is not None:
        await progress_callback("PDF 대상 확인 중", processed_pages=1, total_pages=1)
    return targets


def fetch_pdf_bytes(url: str, timeout: int | None = None) -> bytes:
    response = requests.get(
        url=url,
        timeout=timeout or settings.crawl_timeout_seconds,
        impersonate=settings.crawl_impersonate,
    )
    response.raise_for_status()
    return response.content


def should_skip_existing_document(
    existing_state: ExistingDocumentState | None,
    content_hash: str,
) -> bool:
    return (
        existing_state is not None
        and existing_state.content_hash == content_hash
        and existing_state.chunk_count > 0
    )


async def fetch_and_maybe_parse_document(
    target: CrawlTarget,
    existing_state: ExistingDocumentState | None,
    markdown_renderer: MarkdownRenderer | None = None,
) -> DocumentProcessingResult:
    try:
        if target.source_type == "html":
            cached = cached_html(target.url)
            if cached is not None:
                html, from_cache = cached, True
            else:
                html, from_cache = await _fetch_html_in_thread(fetch_html, target.url), False
            try:
                article_html = extract_article_html(html)
            except ValueError:
                # 본문 selector가 없는(에러/리다이렉트 등) 응답은 무효이므로 캐시에 남기지 않는다.
                return DocumentProcessingResult(target=target)
            if not from_cache:
                store_fetched_html(target.url, html)
            content_hash = build_content_hash(article_html, target=target)
            if should_skip_existing_document(existing_state, content_hash):
                return DocumentProcessingResult(target=target)

            return DocumentProcessingResult(
                target=target,
                document=await parse_html(
                    target=target,
                    html=html,
                    markdown_renderer=markdown_renderer,
                ),
            )

        cached_bytes = cached_pdf_bytes(target.url)
        if cached_bytes is not None:
            pdf_bytes, from_cache = cached_bytes, True
        else:
            pdf_bytes, from_cache = await _fetch_bytes_in_thread(fetch_pdf_bytes, target.url), False
        content_hash = build_content_hash(pdf_bytes, target=target)
        if should_skip_existing_document(existing_state, content_hash):
            return DocumentProcessingResult(target=target)

        document = await parse_pdf(target=target, pdf_bytes=pdf_bytes)
        # parse_pdf가 성공한 유효 PDF만 캐시에 저장한다.
        if not from_cache:
            store_fetched_pdf(target.url, pdf_bytes)
        return DocumentProcessingResult(target=target, document=document)
    except Exception as exc:  # pragma: no cover - exercised through integration
        return DocumentProcessingResult(target=target, failure=f"{target.url}: {exc}")


async def fetch_and_maybe_parse_documents(
    targets: list[CrawlTarget],
    existing_states: dict[str, ExistingDocumentState],
    on_result: Callable[[DocumentProcessingResult], Awaitable[None]] | None = None,
    markdown_renderer: MarkdownRenderer | None = None,
):
    semaphore = asyncio.Semaphore(settings.crawl_ingestion_concurrency)

    async def process(index: int, target: CrawlTarget) -> tuple[int, DocumentProcessingResult]:
        async with semaphore:
            try:
                result = await asyncio.wait_for(
                    fetch_and_maybe_parse_document(
                        target=target,
                        existing_state=existing_states.get(target.url),
                        markdown_renderer=markdown_renderer,
                    ),
                    timeout=settings.crawl_document_timeout_seconds,
                )
            except TimeoutError:
                logger.warning(
                    "crawl document processing timed out: url=%s timeout_seconds=%s",
                    target.url,
                    settings.crawl_document_timeout_seconds,
                )
                result = DocumentProcessingResult(
                    target=target,
                    failure=(
                        f"{target.url}: document processing timed out after "
                        f"{settings.crawl_document_timeout_seconds} seconds"
                    ),
                )
            return index, result

    results: list[DocumentProcessingResult | None] = [None] * len(targets)
    tasks = [asyncio.create_task(process(index, target)) for index, target in enumerate(targets)]
    for task in asyncio.as_completed(tasks):
        index, result = await task
        results[index] = result
        if on_result is not None:
            await on_result(result)
        yield result


async def index_crawl_documents(connection):
    pending_before = await count_pending_chunks(connection)
    logger.info("crawl indexing starting: pending_chunks=%s", pending_before)
    collection = create_chroma_collection(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=settings.chroma_collection,
    )
    logger.info("crawl indexing chroma collection ready: collection=%s", settings.chroma_collection)
    logger.info("crawl indexing embedder loading: model=%s", settings.embedding_model)
    embedder = create_embedder(settings.embedding_model)
    logger.info("crawl indexing embedder loaded: model=%s", settings.embedding_model)
    summary = EmbedSummary(errors=[])
    batch_number = 0
    while True:
        batch_number += 1
        logger.info(
            "crawl indexing batch starting: batch=%s batch_size=%s",
            batch_number,
            settings.index_batch_size,
        )
        batch_summary = await embed_pending_chunks(
            connection=connection,
            collection=collection,
            embedder=embedder,
            batch_size=settings.index_batch_size,
        )
        logger.info(
            "crawl indexing batch completed: batch=%s chunks_seen=%s "
            "chunks_indexed=%s chunks_skipped=%s errors=%s",
            batch_number,
            batch_summary.chunks_seen,
            batch_summary.chunks_indexed,
            batch_summary.chunks_skipped,
            len(batch_summary.errors or []),
        )
        if batch_summary.chunks_seen == 0:
            break

        summary.chunks_seen += batch_summary.chunks_seen
        summary.chunks_indexed += batch_summary.chunks_indexed
        summary.chunks_skipped += batch_summary.chunks_skipped
        if batch_summary.errors:
            summary.errors = summary.errors or []
            summary.errors.extend(batch_summary.errors)

        if batch_summary.chunks_indexed == 0:
            if not batch_summary.errors:
                summary.errors = summary.errors or []
                summary.errors.append(
                    "embedding batch made no progress while pending chunks remained"
                )
            break

    logger.info("crawl indexing prune starting")
    summary.vectors_pruned = await prune_orphan_vectors(connection, collection)
    logger.info("crawl indexing prune completed: vectors_pruned=%s", summary.vectors_pruned)
    logger.info("crawl indexing bm25 writing: cache_dir=%s", settings.bm25_cache_dir)
    bm25_summary = await write_bm25_indexes(connection, settings.bm25_cache_dir)
    summary.bm25_indexes_written = bm25_summary.indexes_written
    pending_after = await count_pending_chunks(connection)
    logger.info(
        "crawl indexing completed: chunks_seen=%s chunks_indexed=%s "
        "chunks_skipped=%s vectors_pruned=%s bm25_indexes_written=%s "
        "pending_before=%s pending_after=%s",
        summary.chunks_seen,
        summary.chunks_indexed,
        summary.chunks_skipped,
        summary.vectors_pruned,
        summary.bm25_indexes_written,
        pending_before,
        pending_after,
    )
    return summary


@dataclass(slots=True)
class IngestionProgress:
    """크롤 한 회차의 진행 상태를 패스들 사이에서 공유하는 컨텍스트.

    각 패스(문서 처리·색인)는 카운터를 직접 갱신하고, 단계가 바뀔 때마다
    crawl_jobs row에 진행률을 기록한다. 카운터를 한곳에 모아 두면 패스를 따로
    호출하더라도 동일한 작업으로 묶어 진행률을 일관되게 보고할 수 있다.
    """

    connection: object
    crawl_job_id: object
    total_pages: int
    processed_pages: int = 0
    pages_crawled: int = 0
    pages_changed: int = 0

    async def update(self, current_stage: str) -> None:
        try:
            await update_crawl_job_progress(
                self.connection,
                self.crawl_job_id,
                current_stage=current_stage,
                total_pages=self.total_pages,
                processed_pages=self.processed_pages,
                pages_crawled=self.pages_crawled,
                pages_changed=self.pages_changed,
            )
        except AttributeError:
            logger.debug("crawl progress update skipped by connection fake")


@dataclass(slots=True)
class DocumentPassResult:
    pages_skipped: int = 0
    status_counts: dict[DocumentProcessingStatus, int] = field(default_factory=dict)


async def run_document_processing_pass(
    progress: IngestionProgress,
    targets: list[CrawlTarget],
    existing_states: dict[str, ExistingDocumentState],
    failures: list[str],
) -> DocumentPassResult:
    """fetch→diff→parse→save 패스.

    대상별로 원본을 가져오고(캐시/네트워크), content_hash로 변경 여부를 가린 뒤
    변경분만 파싱·저장한다. progress의 카운터를 갱신하고 실패는 failures에 누적한다.
    """
    result = DocumentPassResult()

    async def record_processing_progress(item: DocumentProcessingResult) -> None:
        progress.processed_pages += 1
        if item.crawled:
            progress.pages_crawled += 1
        if item.failure is not None:
            logger.warning(
                "crawl document result: processed=%s/%s status=%s "
                "source_type=%s pages_crawled=%s pages_changed=%s "
                "url=%s failure=%s",
                progress.processed_pages,
                progress.total_pages,
                item.status.value,
                item.target.source_type,
                progress.pages_crawled,
                progress.pages_changed,
                item.target.url,
                item.failure[:500],
            )
        else:
            logger.info(
                "crawl document result: processed=%s/%s status=%s "
                "source_type=%s pages_crawled=%s pages_changed=%s url=%s",
                progress.processed_pages,
                progress.total_pages,
                item.status.value,
                item.target.source_type,
                progress.pages_crawled,
                progress.pages_changed,
                item.target.url,
            )
        await progress.update("문서 수집 중")

    async with create_article_markdown_renderer(
        concurrency=settings.crawl_markdown_concurrency
    ) as markdown_renderer:
        document_results = fetch_and_maybe_parse_documents(
            targets,
            existing_states,
            on_result=record_processing_progress,
            markdown_renderer=markdown_renderer,
        )

        async for item in document_results:
            result.status_counts[item.status] = result.status_counts.get(item.status, 0) + 1
            if item.failure is not None:
                failures.append(item.failure)
            if item.status == DocumentProcessingStatus.SKIPPED:
                result.pages_skipped += 1
            if item.document is not None:
                await progress.update("문서 저장 중")
                await persist_document(progress.connection, item.document)
                progress.pages_changed += 1
                logger.info(
                    "crawl document persisted: changed=%s processed=%s/%s url=%s chunks=%s",
                    progress.pages_changed,
                    progress.processed_pages,
                    progress.total_pages,
                    item.document.url,
                    len(item.document.chunks),
                )
    logger.info(
        "crawl ingestion documents completed: processed=%s total=%s "
        "crawled=%s changed=%s skipped=%s failed=%s",
        progress.processed_pages,
        progress.total_pages,
        progress.pages_crawled,
        progress.pages_changed,
        result.pages_skipped,
        result.status_counts.get(DocumentProcessingStatus.FAILED, 0),
    )
    return result


async def run_index_pass(progress: IngestionProgress, failures: list[str]) -> bool:
    """색인 패스. 성공이면 True, 색인 오류/예외면 failures에 기록하고 False."""
    await progress.update("색인 생성 중")
    try:
        index_summary = await index_crawl_documents(progress.connection)
    except Exception as exc:
        failures.append(f"indexing: {exc}")
        logger.exception("crawl indexing failed")
        return False
    if index_summary and index_summary.errors:
        failures.extend(f"indexing: {error}" for error in index_summary.errors)
        return False
    return True


async def execute_ingestion(
    html_targets: list[CrawlTarget],
    pdf_targets: list[CrawlTarget],
    initial_failures: list[str] | None = None,
) -> CrawlStats:
    targets = [*html_targets, *pdf_targets]
    failures = list(initial_failures or [])
    logger.info(
        "crawl ingestion starting: total_targets=%s html_targets=%s pdf_targets=%s "
        "initial_failures=%s ingestion_concurrency=%s markdown_concurrency=%s",
        len(targets),
        len(html_targets),
        len(pdf_targets),
        len(failures),
        settings.crawl_ingestion_concurrency,
        settings.crawl_markdown_concurrency,
    )

    pool = await create_pool()
    try:
        async with pool.acquire() as connection, crawl_advisory_lock(connection) as acquired:
            if not acquired:
                # 다른 프로세스가 크롤 중이다. 작업 row를 만들지 않고 조용히 건너뛴다.
                logger.info("crawl ingestion skipped: another crawl holds the advisory lock")
                return CrawlStats(failures=failures, skipped=True)

            crawl_job_id = await create_crawl_job(connection)
            progress = IngestionProgress(
                connection=connection,
                crawl_job_id=crawl_job_id,
                total_pages=len(targets),
            )
            try:
                await progress.update("대상 확인 중")
                existing_states = await load_existing_document_states(
                    connection,
                    [target.url for target in targets],
                )

                pass_result = await run_document_processing_pass(
                    progress,
                    targets,
                    existing_states,
                    failures,
                )

                indexing_ok = await run_index_pass(progress, failures)
                await finish_crawl_job(
                    connection,
                    crawl_job_id,
                    status="completed" if indexing_ok else "failed",
                    pages_crawled=progress.pages_crawled,
                    pages_changed=progress.pages_changed,
                    error="\n".join(failures) if failures else None,
                )
                return CrawlStats(
                    pages_crawled=progress.pages_crawled,
                    pages_changed=progress.pages_changed,
                    pages_skipped=pass_result.pages_skipped,
                    status_counts=pass_result.status_counts,
                    failures=failures,
                )
            except Exception as exc:
                await finish_crawl_job(
                    connection,
                    crawl_job_id,
                    status="failed",
                    pages_crawled=progress.pages_crawled,
                    pages_changed=progress.pages_changed,
                    error=str(exc),
                )
                raise
    finally:
        await pool.close()


async def run_crawl(progress_callback: ProgressCallback | None = None) -> CrawlStats:
    """Crawl Honam University pages and feed the indexing pipeline."""
    if progress_callback is not None:
        await progress_callback("대상 검색 시작", processed_pages=0, total_pages=0)
    html_discovery, pdf_targets = await asyncio.gather(
        discover_html_targets_with_failures(progress_callback=progress_callback),
        discover_pdf_targets(progress_callback=progress_callback),
    )
    html_targets, pdf_targets = apply_crawl_target_limit(
        html_discovery.targets,
        pdf_targets,
    )
    stats = await execute_ingestion(
        html_targets,
        pdf_targets,
        initial_failures=html_discovery.failures,
    )
    logger.info(
        "crawl completed: pages_crawled=%s pages_changed=%s failures=%s",
        stats.pages_crawled,
        stats.pages_changed,
        len(stats.failures),
    )
    return stats
