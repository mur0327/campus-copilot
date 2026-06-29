import asyncio
import os
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from core.config import CrawlSeedSite
from core.types import SourceScope
from tasks.contracts import CrawlTarget, DocumentProcessingStatus, ParsedChunk, ParsedDocument
from tasks.crawl import (
    DocumentProcessingResult,
    _fetch_html_in_thread,
    apply_crawl_target_limit,
    build_graduation_pdf_targets,
    discover_html_targets,
    discover_html_targets_with_failures,
    discover_pdf_targets,
    execute_ingestion,
    extract_article_box_targets,
    extract_department_sites,
    extract_menu_targets,
    extract_pdf_years,
    fetch_and_maybe_parse_documents,
    index_crawl_documents,
    is_honam_url,
    is_redirect_page,
)
from tasks.embed import EmbedSummary


def crawl_seed(
    *,
    name: str = "호남대학교",
    url: str = "https://www.honam.ac.kr",
    source_scope: SourceScope = "general_academic",
    discover_department_sites: bool = True,
) -> CrawlSeedSite:
    return CrawlSeedSite(
        name=name,
        url=url,
        source_scope=source_scope,
        discover_department_sites=discover_department_sites,
    )


def test_apply_crawl_target_limit_keeps_discovery_order(monkeypatch):
    html_targets = [
        CrawlTarget(
            url=f"https://www.honam.ac.kr/html-{index}",
            menu_path="메뉴",
            source_type="html",
            source_scope="general_academic",
            page_kind="academic",
        )
        for index in range(3)
    ]
    pdf_targets = [
        CrawlTarget(
            url=f"https://www.honam.ac.kr/pdf-{index}",
            menu_path="PDF",
            source_type="pdf",
            source_scope="general_academic",
            page_kind="academic",
        )
        for index in range(2)
    ]

    monkeypatch.setattr("tasks.crawl.settings.crawl_target_limit", 4)

    limited_html, limited_pdf = apply_crawl_target_limit(html_targets, pdf_targets)

    assert [target.url for target in limited_html] == [
        "https://www.honam.ac.kr/html-0",
        "https://www.honam.ac.kr/html-1",
        "https://www.honam.ac.kr/html-2",
    ]
    assert [target.url for target in limited_pdf] == ["https://www.honam.ac.kr/pdf-0"]


def test_extract_menu_targets_skips_data_link_and_dedupes(fixture_text):
    targets = extract_menu_targets(
        html=fixture_text("menu_main.html"),
        base_url="https://www.honam.ac.kr",
        site_name="호남대학교",
        site_url="https://www.honam.ac.kr",
    )

    assert [(target.menu_path, target.url, target.source_type) for target in targets] == [
        ("장학", "https://www.honam.ac.kr/Scholarship/list", "html"),
        ("입학", "https://www.honam.ac.kr/Admissions/notice", "html"),
    ]
    assert [target.source_scope for target in targets] == [
        "general_academic",
        "general_academic",
    ]
    assert [target.page_kind for target in targets] == [
        "academic",
        "admission",
    ]
    assert all(target.site_name == "호남대학교" for target in targets)
    assert all(target.site_url == "https://www.honam.ac.kr" for target in targets)


def test_extract_menu_targets_uses_explicit_source_scope_before_url_inference():
    html = """
    <html><body><ul id="mainMenu">
      <li><a href="https://www.honam.ac.kr/AdmissionRedirect">입학 바로가기</a></li>
    </ul></body></html>
    """

    targets = extract_menu_targets(
        html=html,
        base_url="https://enter.honam.ac.kr",
        site_name="입학안내",
        site_url="https://enter.honam.ac.kr",
        source_scope="admission",
    )

    assert targets[0].source_scope == "admission"


def test_extract_menu_targets_prefers_matching_seed_host_source_scope():
    html = """
    <html><body><ul id="mainMenu">
      <li><a href="https://enter.honam.ac.kr/AdmissionGuide">입학안내</a></li>
    </ul></body></html>
    """

    targets = extract_menu_targets(
        html=html,
        base_url="https://www.honam.ac.kr",
        site_name="호남대학교",
        site_url="https://www.honam.ac.kr",
        source_scope="general_academic",
        source_scope_by_host={
            "www.honam.ac.kr": "general_academic",
            "enter.honam.ac.kr": "admission",
        },
    )

    assert targets[0].source_scope == "admission"


def test_extract_menu_targets_keeps_last_label_for_duplicate_url():
    html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/ChGreeting">대학소개</a></li>
          <li><a href="/ChGreeting">이사장 인사말</a></li>
          <li><a href="/PreGreeting">열린 총장실</a></li>
          <li><a href="/PreGreeting">총장 인사말</a></li>
        </ul>
      </body>
    </html>
    """

    targets = extract_menu_targets(html=html, base_url="https://www.honam.ac.kr")

    assert [(target.menu_path, target.url) for target in targets] == [
        ("이사장 인사말", "https://www.honam.ac.kr/ChGreeting"),
        ("총장 인사말", "https://www.honam.ac.kr/PreGreeting"),
    ]


def test_extract_menu_targets_keeps_last_metadata_for_duplicate_url():
    first_html = """
    <html><body><ul id="mainMenu"><li><a href="/Shared">초기 라벨</a></li></ul></body></html>
    """
    second_html = """
    <html><body><ul id="mainMenu"><li><a href="/Shared">최종 라벨</a></li></ul></body></html>
    """

    targets = [
        *extract_menu_targets(
            html=first_html,
            base_url="https://www.honam.ac.kr",
            site_name="호남대학교",
            site_url="https://www.honam.ac.kr",
        ),
        *extract_menu_targets(
            html=second_html,
            base_url="https://www.honam.ac.kr",
            site_name="입학안내",
            site_url="https://enter.honam.ac.kr",
        ),
    ]

    deduped = extract_menu_targets(
        html="""
        <html><body><ul id="mainMenu">
          <li><a href="/Shared">초기 라벨</a></li>
          <li><a href="/Shared">최종 라벨</a></li>
        </ul></body></html>
        """,
        base_url="https://www.honam.ac.kr",
        site_name="입학안내",
        site_url="https://enter.honam.ac.kr",
    )

    assert [(target.menu_path, target.site_name, target.site_url) for target in targets][-1] == (
        "최종 라벨",
        "입학안내",
        "https://enter.honam.ac.kr",
    )
    assert [(target.menu_path, target.site_name, target.site_url) for target in deduped] == [
        ("최종 라벨", "입학안내", "https://enter.honam.ac.kr")
    ]


@pytest.mark.asyncio
async def test_fetch_and_maybe_parse_documents_serializes_result_callbacks(monkeypatch):
    targets = [
        CrawlTarget(
            url=f"https://www.honam.ac.kr/{index}",
            menu_path="메뉴",
            source_type="html",
            source_scope="general_academic",
            page_kind="academic",
        )
        for index in range(3)
    ]
    all_started = asyncio.Event()
    started = 0
    active_callbacks = 0

    async def fake_fetch_and_maybe_parse_document(
        *, target, existing_state, markdown_renderer=None
    ):
        nonlocal started
        started += 1
        if started == len(targets):
            all_started.set()
        await all_started.wait()
        return DocumentProcessingResult(target=target)

    async def on_result(result):
        nonlocal active_callbacks
        assert active_callbacks == 0
        active_callbacks += 1
        await asyncio.sleep(0.01)
        active_callbacks -= 1

    monkeypatch.setattr(
        "tasks.crawl.fetch_and_maybe_parse_document",
        fake_fetch_and_maybe_parse_document,
    )

    results = [
        result async for result in fetch_and_maybe_parse_documents(targets, {}, on_result=on_result)
    ]

    assert {result.target.url for result in results} == {target.url for target in targets}


@pytest.mark.asyncio
async def test_fetch_and_maybe_parse_documents_records_document_timeout(monkeypatch):
    target = CrawlTarget(
        url="https://www.honam.ac.kr/Slow",
        menu_path="느린 페이지",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
    )

    async def fake_fetch_and_maybe_parse_document(
        *, target, existing_state, markdown_renderer=None
    ):
        await asyncio.sleep(0.05)
        return DocumentProcessingResult(target=target)

    monkeypatch.setattr("tasks.crawl.settings.crawl_document_timeout_seconds", 0.01)
    monkeypatch.setattr(
        "tasks.crawl.fetch_and_maybe_parse_document",
        fake_fetch_and_maybe_parse_document,
    )

    results = [result async for result in fetch_and_maybe_parse_documents([target], {})]

    assert len(results) == 1
    assert results[0].target == target
    assert results[0].status == DocumentProcessingStatus.FAILED
    assert results[0].failure == (
        "https://www.honam.ac.kr/Slow: document processing timed out after 0.01 seconds"
    )


@pytest.mark.asyncio
async def test_fetch_html_in_thread_timeout_does_not_wait_for_blocked_fetcher():
    def slow_fetcher(url: str) -> str:
        time.sleep(0.2)
        return "<html></html>"

    started_at = time.perf_counter()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            _fetch_html_in_thread(slow_fetcher, "https://www.honam.ac.kr/Slow"),
            timeout=0.01,
        )

    assert time.perf_counter() - started_at < 0.1


def test_is_honam_url_requires_exact_domain_or_subdomain():
    assert is_honam_url("https://honam.ac.kr") is True
    assert is_honam_url("https://www.honam.ac.kr/main") is True
    assert is_honam_url("https://enter.honam.ac.kr/main") is True
    assert is_honam_url("https://not-honam.ac.kr/main") is False
    assert is_honam_url("https://honam.ac.kr.evil.test/main") is False


def test_extract_menu_targets_skips_external_absolute_links():
    html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/Local">내부</a></li>
          <li><a href="https://www.work.go.kr/job">외부</a></li>
          <li><a href="https://not-honam.ac.kr/page">가짜 호남</a></li>
        </ul>
      </body>
    </html>
    """

    targets = extract_menu_targets(html=html, base_url="https://www.honam.ac.kr")

    assert [target.url for target in targets] == ["https://www.honam.ac.kr/Local"]


def test_extract_department_sites_normalizes_reference_nav_links():
    html = """
    <html>
      <body>
        <ul id="universityTop">
          <li><a href="http://com.honam.ac.kr/">컴퓨터공학과</a></li>
          <li><a href="https://nursing.honam.ac.kr/">간호학과</a></li>
          <li><a href="">빈 링크</a></li>
        </ul>
      </body>
    </html>
    """

    sites = extract_department_sites(html)

    assert [(site.name, site.url) for site in sites] == [
        ("컴퓨터공학과", "https://com.honam.ac.kr"),
        ("간호학과", "https://nursing.honam.ac.kr"),
    ]


def test_extract_department_sites_skips_external_and_normalizes_relative_links():
    html = """
    <html>
      <body>
        <ul id="universityTop">
          <li><a href="//com.honam.ac.kr/">컴퓨터공학과</a></li>
          <li><a href="/department">잘못된 상대학과</a></li>
          <li><a href="https://not-honam.ac.kr/">가짜학과</a></li>
        </ul>
      </body>
    </html>
    """

    sites = extract_department_sites(html)

    assert [(site.name, site.url) for site in sites] == [
        ("컴퓨터공학과", "https://com.honam.ac.kr")
    ]


def test_extract_article_box_targets_uses_article_links_as_child_targets():
    html = """
    <html>
      <body>
        <article class="articleBox">
          <a href="/AcademicCalendar/main/2026">2026년</a>
          <a href="/AcademicCalendar/main/2025">2025년</a>
        </article>
      </body>
    </html>
    """
    parent = CrawlTarget(
        url="https://www.honam.ac.kr/AcademicCalendar",
        menu_path="학사일정",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
        site_name="호남대학교",
        site_url="https://www.honam.ac.kr",
    )

    targets = extract_article_box_targets(parent=parent, html=html)

    target_summaries = [
        (
            target.menu_path,
            target.url,
            target.source_scope,
            target.site_name,
            target.site_url,
        )
        for target in targets
    ]
    assert target_summaries == [
        (
            "학사일정 > 2026년",
            "https://www.honam.ac.kr/AcademicCalendar/main/2026",
            "general_academic",
            "호남대학교",
            "https://www.honam.ac.kr",
        ),
        (
            "학사일정 > 2025년",
            "https://www.honam.ac.kr/AcademicCalendar/main/2025",
            "general_academic",
            "호남대학교",
            "https://www.honam.ac.kr",
        ),
    ]


def test_extract_article_box_targets_skips_download_links():
    html = """
    <html>
      <body>
        <article class="articleBox">
          <a href="/AcademicCalendar/main/2026">2026년</a>
          <a href="/GraduateGrades/pdfdownload/2025">PDF 다운로드</a>
          <a href="/BudgetAnnounce/download/865">파일 다운로드</a>
          <a href="/attach/schoolsong/SchoolSong_20260223.mp4">교가 영상</a>
          <a href="/img/contents/A01/hnsm_AI.zip">zip 다운로드</a>
        </article>
      </body>
    </html>
    """
    parent = CrawlTarget(
        url="https://www.honam.ac.kr/GraduateGrades",
        menu_path="졸업학점",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
    )

    targets = extract_article_box_targets(parent=parent, html=html)

    assert [target.url for target in targets] == [
        "https://www.honam.ac.kr/AcademicCalendar/main/2026"
    ]


def test_extract_article_box_targets_skips_external_links():
    html = """
    <html>
      <body>
        <article class="articleBox">
          <a href="/AcademicCalendar/main/2026">2026년</a>
          <a href="https://www.work.go.kr/job">외부 취업사이트</a>
          <a href="https://com.honam.ac.kr/DepartmentOverview">학과 소개</a>
        </article>
      </body>
    </html>
    """
    parent = CrawlTarget(
        url="https://www.honam.ac.kr/AcademicCalendar",
        menu_path="학사일정",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
    )

    targets = extract_article_box_targets(parent=parent, html=html)

    assert [target.url for target in targets] == [
        "https://www.honam.ac.kr/AcademicCalendar/main/2026",
        "https://com.honam.ac.kr/DepartmentOverview",
    ]


@pytest.mark.asyncio
async def test_discover_html_targets_includes_department_site_menus(monkeypatch, fixture_text):
    monkeypatch.setattr("tasks.crawl.is_redirect_page", lambda html: False)

    main_html = """
    <html>
      <body>
        <ul id="universityTop">
          <li><a href="http://com.honam.ac.kr/">컴퓨터공학과</a></li>
        </ul>
        <ul id="mainMenu">
          <li><a href="/Admissions/notice">입학</a></li>
        </ul>
      </body>
    </html>
    """
    department_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/Department/intro">학과소개</a></li>
        </ul>
      </body>
    </html>
    """
    fallback_html = fixture_text("article_page.html")

    def fetcher(url: str) -> str:
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url == "https://com.honam.ac.kr/main":
            return department_html
        return fallback_html

    targets = await discover_html_targets(fetcher=fetcher)

    assert [target.url for target in targets] == [
        "https://www.honam.ac.kr/Admissions/notice",
        "https://com.honam.ac.kr/Department/intro",
    ]
    assert targets[1].site_name == "컴퓨터공학과"
    assert targets[1].site_url == "https://com.honam.ac.kr"
    assert targets[1].source_scope == "department"


@pytest.mark.asyncio
async def test_discover_html_targets_crawls_each_configured_root_main(monkeypatch, fixture_text):
    monkeypatch.setattr("tasks.crawl.is_redirect_page", lambda html: False)
    monkeypatch.setattr(
        "tasks.crawl.settings.crawl_seed_sites",
        [
            crawl_seed(),
            crawl_seed(
                name="입학안내",
                url="https://enter.honam.ac.kr",
                source_scope="admission",
                discover_department_sites=False,
            ),
        ],
    )
    fallback_html = fixture_text("article_page.html")

    def fetcher(url: str) -> str:
        if url == "https://www.honam.ac.kr/main":
            return """
            <html>
              <body>
                <ul id="mainMenu">
                  <li><a href="/RootNotice">본교공지</a></li>
                </ul>
              </body>
            </html>
            """
        if url == "https://enter.honam.ac.kr/main":
            return """
            <html>
              <body>
                <ul id="mainMenu">
                  <li><a href="/AdmissionGuide">입학안내</a></li>
                </ul>
              </body>
            </html>
            """
        return fallback_html

    targets = await discover_html_targets(fetcher=fetcher)

    assert [(target.url, target.site_url, target.source_scope) for target in targets] == [
        (
            "https://www.honam.ac.kr/RootNotice",
            "https://www.honam.ac.kr",
            "general_academic",
        ),
        (
            "https://enter.honam.ac.kr/AdmissionGuide",
            "https://enter.honam.ac.kr",
            "admission",
        ),
    ]


@pytest.mark.asyncio
async def test_discover_html_targets_filters_page_moved_target_pages(fixture_text):
    main_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/Valid">유효</a></li>
          <li><a href="/Moved">이동됨</a></li>
        </ul>
      </body>
    </html>
    """
    moved_html = "<html><head><title>Page Moved</title></head><body>moved</body></html>"
    valid_html = fixture_text("article_page.html")

    def fetcher(url: str) -> str:
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url == "https://www.honam.ac.kr/Valid":
            return valid_html
        if url == "https://www.honam.ac.kr/Moved":
            return moved_html
        raise AssertionError(f"unexpected url: {url}")

    targets = await discover_html_targets(fetcher=fetcher)

    assert [target.url for target in targets] == ["https://www.honam.ac.kr/Valid"]


@pytest.mark.asyncio
async def test_discover_html_targets_applies_limit_before_article_expansion(monkeypatch):
    monkeypatch.setattr("tasks.crawl.settings.crawl_target_limit", 2)
    monkeypatch.setattr("tasks.crawl.settings.crawl_seed_sites", [crawl_seed()])
    main_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/First">첫번째</a></li>
          <li><a href="/Second">두번째</a></li>
          <li><a href="/Third">세번째</a></li>
          <li><a href="/Fourth">네번째</a></li>
        </ul>
      </body>
    </html>
    """
    called_urls: list[str] = []

    def fetcher(url: str) -> str:
        called_urls.append(url)
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url in {
            "https://www.honam.ac.kr/First",
            "https://www.honam.ac.kr/Second",
        }:
            return "<html><body><article class='articleBox'>limited</article></body></html>"
        raise AssertionError(f"limit should prevent fetching: {url}")

    targets = await discover_html_targets(fetcher=fetcher)

    assert [target.url for target in targets] == [
        "https://www.honam.ac.kr/First",
        "https://www.honam.ac.kr/Second",
    ]
    assert called_urls[0] == "https://www.honam.ac.kr/main"
    assert set(called_urls[1:]) == {
        "https://www.honam.ac.kr/First",
        "https://www.honam.ac.kr/Second",
    }


@pytest.mark.asyncio
async def test_discover_html_targets_keeps_article_child_targets(monkeypatch):
    monkeypatch.setattr("tasks.crawl.is_redirect_page", lambda html: False)
    main_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/AcademicCalendar">학사일정</a></li>
        </ul>
      </body>
    </html>
    """
    calendar_html = """
    <html>
      <body>
        <article class="articleBox">
          <a href="/AcademicCalendar/main/2026">2026년</a>
          <a href="/AcademicCalendar/main/2025">2025년</a>
        </article>
      </body>
    </html>
    """

    def fetcher(url: str) -> str:
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url == "https://www.honam.ac.kr/AcademicCalendar":
            return calendar_html
        if url in {
            "https://www.honam.ac.kr/AcademicCalendar/main/2026",
            "https://www.honam.ac.kr/AcademicCalendar/main/2025",
        }:
            return "<html><body><article class='articleBox'>child</article></body></html>"
        raise AssertionError(f"unexpected url: {url}")

    targets = await discover_html_targets(fetcher=fetcher)

    assert [(target.menu_path, target.url) for target in targets] == [
        ("학사일정", "https://www.honam.ac.kr/AcademicCalendar"),
        ("학사일정 > 2026년", "https://www.honam.ac.kr/AcademicCalendar/main/2026"),
        ("학사일정 > 2025년", "https://www.honam.ac.kr/AcademicCalendar/main/2025"),
    ]


@pytest.mark.asyncio
async def test_discover_html_targets_validates_article_child_targets(monkeypatch, fixture_text):
    monkeypatch.setattr("tasks.crawl.is_redirect_page", lambda html: "Page Moved" in html)
    main_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/AcademicCalendar">학사일정</a></li>
        </ul>
      </body>
    </html>
    """
    calendar_html = """
    <html>
      <body>
        <article class="articleBox">
          <a href="/AcademicCalendar/main/2026">2026년</a>
          <a href="/AcademicCalendar/main/2025">2025년</a>
        </article>
      </body>
    </html>
    """
    moved_html = "<html><head><title>Page Moved</title></head><body>moved</body></html>"
    fallback_html = fixture_text("article_page.html")

    def fetcher(url: str) -> str:
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url == "https://www.honam.ac.kr/AcademicCalendar":
            return calendar_html
        if url == "https://www.honam.ac.kr/AcademicCalendar/main/2025":
            return moved_html
        if url == "https://www.honam.ac.kr/AcademicCalendar/main/2026":
            return fallback_html
        raise AssertionError(f"unexpected url: {url}")

    targets = await discover_html_targets(fetcher=fetcher)

    assert [target.url for target in targets] == [
        "https://www.honam.ac.kr/AcademicCalendar",
        "https://www.honam.ac.kr/AcademicCalendar/main/2026",
    ]


@pytest.mark.asyncio
async def test_discover_html_targets_skips_pages_without_article_content(monkeypatch):
    monkeypatch.setattr("tasks.crawl.is_redirect_page", lambda html: False)
    monkeypatch.setattr("tasks.crawl.settings.crawl_seed_sites", [crawl_seed()])
    main_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/NoContent">본문없음</a></li>
          <li><a href="/Stable">정상</a></li>
        </ul>
      </body>
    </html>
    """

    def fetcher(url: str) -> str:
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url == "https://www.honam.ac.kr/NoContent":
            return "<html><body><main>navigation only</main></body></html>"
        if url == "https://www.honam.ac.kr/Stable":
            return "<html><body><article class='articleBox'>stable</article></body></html>"
        raise AssertionError(f"unexpected url: {url}")

    result = await discover_html_targets_with_failures(fetcher=fetcher)

    assert [target.url for target in result.targets] == ["https://www.honam.ac.kr/Stable"]
    assert result.failures == []


@pytest.mark.asyncio
async def test_discover_html_targets_skips_department_main_fetch_failures(fixture_text):
    main_html = """
    <html>
      <body>
        <ul id="universityTop">
          <li><a href="https://timeout.honam.ac.kr/">타임아웃학과</a></li>
          <li><a href="https://ok.honam.ac.kr/">정상학과</a></li>
        </ul>
        <ul id="mainMenu">
          <li><a href="/Root">본교</a></li>
        </ul>
      </body>
    </html>
    """
    department_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/DepartmentOverview">학과개요</a></li>
        </ul>
      </body>
    </html>
    """
    fallback_html = fixture_text("article_page.html")

    def fetcher(url: str) -> str:
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url == "https://timeout.honam.ac.kr/main":
            raise TimeoutError("simulated timeout")
        if url == "https://ok.honam.ac.kr/main":
            return department_html
        return fallback_html

    targets = await discover_html_targets(fetcher=fetcher)

    assert [target.url for target in targets] == [
        "https://www.honam.ac.kr/Root",
        "https://ok.honam.ac.kr/DepartmentOverview",
    ]


@pytest.mark.asyncio
async def test_discover_html_targets_retries_failed_target_validation(fixture_text):
    main_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/Flaky">불안정</a></li>
          <li><a href="/Stable">정상</a></li>
        </ul>
      </body>
    </html>
    """
    fallback_html = fixture_text("article_page.html")
    attempts: dict[str, int] = {}

    def fetcher(url: str) -> str:
        attempts[url] = attempts.get(url, 0) + 1
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url == "https://www.honam.ac.kr/Flaky" and attempts[url] == 1:
            raise TimeoutError("first pass timeout")
        return fallback_html

    result = await discover_html_targets_with_failures(fetcher=fetcher)

    assert [target.url for target in result.targets] == [
        "https://www.honam.ac.kr/Flaky",
        "https://www.honam.ac.kr/Stable",
    ]
    assert result.failures == []
    assert attempts["https://www.honam.ac.kr/Flaky"] == 2


@pytest.mark.asyncio
async def test_discover_html_targets_records_final_validation_failures(fixture_text):
    main_html = """
    <html>
      <body>
        <ul id="mainMenu">
          <li><a href="/AlwaysTimeout">항상 타임아웃</a></li>
          <li><a href="/Stable">정상</a></li>
        </ul>
      </body>
    </html>
    """
    fallback_html = fixture_text("article_page.html")

    def fetcher(url: str) -> str:
        if url == "https://www.honam.ac.kr/main":
            return main_html
        if url == "https://www.honam.ac.kr/AlwaysTimeout":
            raise TimeoutError("simulated timeout")
        return fallback_html

    result = await discover_html_targets_with_failures(fetcher=fetcher)

    assert [target.url for target in result.targets] == ["https://www.honam.ac.kr/Stable"]
    assert result.failures == [
        "https://www.honam.ac.kr/AlwaysTimeout: simulated timeout",
    ]


def test_build_graduation_pdf_targets_uses_recent_years_descending():
    targets = build_graduation_pdf_targets(
        years=[2024, 2023, 2022, 2021, 2020, 2019],
        base_url="https://www.honam.ac.kr",
        graduation_path="/GraduateGrades",
        year_limit=5,
    )

    assert [target.year for target in targets] == [2024, 2023, 2022, 2021, 2020]
    assert targets[0].url == "https://www.honam.ac.kr/GraduateGrades/pdfdownload/2024"
    assert all(target.source_type == "pdf" for target in targets)


def test_build_graduation_pdf_targets_normalizes_base_url_and_path():
    targets = build_graduation_pdf_targets(
        years=[2024],
        base_url="https://www.honam.ac.kr/",
        graduation_path="/GraduateGrades/",
        year_limit=5,
    )

    assert targets[0].url == "https://www.honam.ac.kr/GraduateGrades/pdfdownload/2024"


def test_extract_pdf_years_sorts_values_descending():
    html = """
    <html>
      <body>
        <select id="selectYear">
          <option value="20122013">2012 ~ 2013학년도</option>
          <option value="2022">2022</option>
          <option value="2024">2024</option>
          <option value="2023">2023</option>
          <option value="20092010">2009 ~ 2010학년도</option>
          <option value="abc">abc</option>
        </select>
      </body>
    </html>
    """

    assert extract_pdf_years(html) == [2024, 2023, 2022]


@pytest.mark.asyncio
async def test_discover_html_targets_uses_fetcher_and_skips_redirect_pages(monkeypatch):
    monkeypatch.setattr("tasks.crawl.settings.crawl_seed_sites", [crawl_seed()])
    called_urls: list[str] = []

    def fetcher(url: str) -> str:
        called_urls.append(url)
        if url.endswith("/main"):
            return "<html><head><title>Page Moved</title></head><body></body></html>"
        raise AssertionError("unexpected url")

    targets = await discover_html_targets(fetcher=fetcher)

    assert called_urls == ["https://www.honam.ac.kr/main"]
    assert targets == []


@pytest.mark.asyncio
async def test_discover_pdf_targets_uses_fetcher_and_skips_redirect_pages():
    called_urls: list[str] = []

    def fetcher(url: str) -> str:
        called_urls.append(url)
        if url.endswith("/GraduateGrades"):
            return "<html><head><title>Page Moved</title></head><body></body></html>"
        raise AssertionError("unexpected url")

    targets = await discover_pdf_targets(fetcher=fetcher)

    assert called_urls == ["https://www.honam.ac.kr/GraduateGrades"]
    assert targets == []


@pytest.mark.asyncio
async def test_discover_pdf_targets_uses_www_root_even_when_config_order_changes(monkeypatch):
    monkeypatch.setattr(
        "tasks.crawl.settings.crawl_seed_sites",
        [
            crawl_seed(
                name="입학안내",
                url="https://enter.honam.ac.kr",
                source_scope="admission",
                discover_department_sites=False,
            ),
            crawl_seed(),
        ],
    )
    called_urls: list[str] = []

    def fetcher(url: str) -> str:
        called_urls.append(url)
        return """
        <html>
          <body>
            <select id="selectYear"><option value="2025">2025</option></select>
          </body>
        </html>
        """

    targets = await discover_pdf_targets(fetcher=fetcher)

    assert called_urls == ["https://www.honam.ac.kr/GraduateGrades"]
    assert [target.url for target in targets] == [
        "https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025"
    ]


def test_is_redirect_page_detects_page_moved_title(fixture_text):
    assert is_redirect_page(fixture_text("page_moved.html")) is True


@pytest.mark.asyncio
async def test_index_crawl_documents_repeats_batches_and_accumulates_summary(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("tasks.crawl.settings.bm25_cache_dir", ".data/bm25")

    class FakeCollection:
        pass

    class FakeEmbedder:
        pass

    async def fake_embed_pending_chunks(*, connection, collection, embedder, batch_size):
        calls.append("embed")
        assert collection.__class__ is FakeCollection
        assert embedder.__class__ is FakeEmbedder
        assert batch_size == 64
        if len(calls) == 1:
            return EmbedSummary(chunks_seen=64, chunks_indexed=64, chunks_skipped=0, errors=[])
        if len(calls) == 2:
            return EmbedSummary(
                chunks_seen=6,
                chunks_indexed=5,
                chunks_skipped=1,
                errors=["skipped malformed row"],
            )
        return EmbedSummary(chunks_seen=0, chunks_indexed=0, chunks_skipped=0, errors=[])

    async def fake_prune_orphan_vectors(connection, collection):
        calls.append("prune")
        return 3

    async def fake_write_bm25_indexes(connection, cache_dir):
        calls.append(f"bm25:{cache_dir}")
        return SimpleNamespace(indexes_written=2)

    async def fake_count_pending_chunks(connection):
        return 70

    monkeypatch.setattr("tasks.crawl.create_chroma_collection", lambda **kwargs: FakeCollection())
    monkeypatch.setattr("tasks.crawl.create_embedder", lambda model_name: FakeEmbedder())
    monkeypatch.setattr("tasks.crawl.count_pending_chunks", fake_count_pending_chunks)
    monkeypatch.setattr("tasks.crawl.embed_pending_chunks", fake_embed_pending_chunks)
    monkeypatch.setattr("tasks.crawl.prune_orphan_vectors", fake_prune_orphan_vectors)
    monkeypatch.setattr("tasks.crawl.write_bm25_indexes", fake_write_bm25_indexes)

    summary = await index_crawl_documents(connection=object())

    assert calls == ["embed", "embed", "embed", "prune", "bm25:.data/bm25"]
    assert summary.chunks_seen == 70
    assert summary.chunks_indexed == 69
    assert summary.chunks_skipped == 1
    assert summary.vectors_pruned == 3
    assert summary.bm25_indexes_written == 2
    assert summary.errors == ["skipped malformed row"]


@pytest.mark.asyncio
async def test_execute_ingestion_skips_when_advisory_lock_unavailable(monkeypatch):
    target = CrawlTarget(
        url="https://example.com/locked",
        menu_path="공지",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
    )
    events: list[str] = []

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def fetchval(self, query, *args):
            events.append(query)
            return False  # pg_try_advisory_lock 실패 = 다른 프로세스가 크롤 중

    class FakePool:
        def acquire(self):
            return FakeConnection()

        async def close(self):
            events.append("close")

    async def fake_create_pool():
        return FakePool()

    async def fake_create_crawl_job(connection):
        raise AssertionError("skipped run must not create a crawl job")

    monkeypatch.setattr("tasks.crawl.create_pool", fake_create_pool)
    monkeypatch.setattr("tasks.crawl.create_crawl_job", fake_create_crawl_job)

    stats = await execute_ingestion([target], [])

    assert stats.skipped is True
    # 잠금 시도(try)만 하고, 못 잡았으니 unlock 없이 연결을 반납한다.
    assert events == ["SELECT pg_try_advisory_lock($1)", "close"]


@pytest.mark.asyncio
async def test_execute_ingestion_runs_indexing_after_persistence_before_finish(monkeypatch):
    target = CrawlTarget(
        url="https://example.com/changed",
        menu_path="공지",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
    )
    events: list[str] = []

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeConnection()

        async def close(self):
            events.append("close")

    async def fake_create_pool():
        return FakePool()

    async def fake_create_crawl_job(connection):
        return "job-1"

    async def fake_load_existing_document_states(connection, urls):
        return {}

    def fake_fetch_html(url):
        return "<html><body><article class='articleBox'><p>changed</p></article></body></html>"

    async def fake_parse_html(target, html, markdown_renderer=None):
        return ParsedDocument(
            url=target.url,
            title="Example",
            menu_path=target.menu_path,
            category=None,
            source_scope="unknown",
            page_kind="unknown",
            source_type=target.source_type,
            content_hash="hash-1",
            crawled_at=datetime(2026, 5, 6, tzinfo=UTC),
            chunks=[],
        )

    async def fake_persist_document(connection, document):
        events.append("persist")
        return "document-1"

    async def fake_index_crawl_documents(connection):
        events.append("index")

    async def fake_finish_crawl_job(*args, **kwargs):
        events.append("finish")

    monkeypatch.setattr("tasks.crawl.create_pool", fake_create_pool)
    monkeypatch.setattr("tasks.crawl.create_crawl_job", fake_create_crawl_job)
    monkeypatch.setattr(
        "tasks.crawl.load_existing_document_states",
        fake_load_existing_document_states,
    )
    monkeypatch.setattr("tasks.crawl.fetch_html", fake_fetch_html)
    monkeypatch.setattr("tasks.crawl.parse_html", fake_parse_html)
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.index_crawl_documents", fake_index_crawl_documents)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)

    stats = await execute_ingestion([target], [])

    assert stats.status_counts == {DocumentProcessingStatus.CHANGED: 1}
    assert events == ["persist", "index", "finish", "close"]


@pytest.mark.asyncio
async def test_execute_ingestion_persists_each_document_before_next_result(monkeypatch):
    targets = [
        CrawlTarget(
            url=f"https://example.com/changed-{index}",
            menu_path="공지",
            source_type="html",
            source_scope="general_academic",
            page_kind="academic",
        )
        for index in range(2)
    ]
    events: list[str] = []

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeConnection()

        async def close(self):
            pass

    async def fake_create_pool():
        return FakePool()

    async def fake_create_crawl_job(connection):
        return "job-1"

    async def fake_load_existing_document_states(connection, urls):
        return {}

    async def fake_fetch_and_maybe_parse_documents(
        targets,
        existing_states,
        on_result=None,
        markdown_renderer=None,
    ):
        for target in targets:
            events.append(f"result:{target.url}")
            result = DocumentProcessingResult(
                target=target,
                document=ParsedDocument(
                    url=target.url,
                    title="Example",
                    menu_path=target.menu_path,
                    category=None,
                    source_scope="unknown",
                    page_kind="unknown",
                    source_type=target.source_type,
                    content_hash="hash-1",
                    crawled_at=datetime(2026, 5, 6, tzinfo=UTC),
                    chunks=[],
                ),
            )
            if on_result is not None:
                await on_result(result)
            yield result

    async def fake_persist_document(connection, document):
        events.append(f"persist:{document.url}")
        return "document-1"

    async def fake_index_crawl_documents(connection):
        events.append("index")

    async def fake_finish_crawl_job(*args, **kwargs):
        events.append("finish")

    monkeypatch.setattr("tasks.crawl.create_pool", fake_create_pool)
    monkeypatch.setattr("tasks.crawl.create_crawl_job", fake_create_crawl_job)
    monkeypatch.setattr(
        "tasks.crawl.load_existing_document_states",
        fake_load_existing_document_states,
    )
    monkeypatch.setattr(
        "tasks.crawl.fetch_and_maybe_parse_documents",
        fake_fetch_and_maybe_parse_documents,
    )
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.index_crawl_documents", fake_index_crawl_documents)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)

    stats = await execute_ingestion(targets, [])

    assert stats.pages_changed == 2
    assert events == [
        "result:https://example.com/changed-0",
        "persist:https://example.com/changed-0",
        "result:https://example.com/changed-1",
        "persist:https://example.com/changed-1",
        "index",
        "finish",
    ]


@pytest.mark.asyncio
async def test_execute_ingestion_runs_indexing_when_all_documents_are_skipped(monkeypatch):
    target = CrawlTarget(
        url="https://example.com/unchanged",
        menu_path="공지",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
    )
    article_html = '<article class="articleBox"><p>same content</p></article>'
    events: list[str] = []

    class ExistingState:
        content_hash = "same-hash"
        chunk_count = 1

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeConnection()

        async def close(self):
            events.append("close")

    async def fake_create_pool():
        return FakePool()

    async def fake_create_crawl_job(connection):
        return "job-1"

    async def fake_load_existing_document_states(connection, urls):
        assert urls == [target.url]
        return {target.url: ExistingState()}

    def fake_build_content_hash(raw_content, target=None):
        assert raw_content == article_html
        return "same-hash"

    def fake_fetch_html(url):
        assert url == target.url
        return f"<html><body>{article_html}</body></html>"

    async def fake_parse_html(*args, **kwargs):
        raise AssertionError("unchanged document should skip parse_html")

    async def fake_persist_document(connection, document):
        raise AssertionError("unchanged document should not be persisted")

    async def fake_index_crawl_documents(connection):
        events.append("index")

    async def fake_finish_crawl_job(*args, **kwargs):
        events.append("finish")

    monkeypatch.setattr("tasks.crawl.create_pool", fake_create_pool)
    monkeypatch.setattr("tasks.crawl.create_crawl_job", fake_create_crawl_job)
    monkeypatch.setattr(
        "tasks.crawl.load_existing_document_states",
        fake_load_existing_document_states,
    )
    monkeypatch.setattr("tasks.crawl.build_content_hash", fake_build_content_hash)
    monkeypatch.setattr("tasks.crawl.fetch_html", fake_fetch_html)
    monkeypatch.setattr("tasks.crawl.parse_html", fake_parse_html)
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.index_crawl_documents", fake_index_crawl_documents)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)

    stats = await execute_ingestion([target], [])

    assert stats.status_counts == {DocumentProcessingStatus.SKIPPED: 1}
    assert events == ["index", "finish", "close"]


@pytest.mark.asyncio
async def test_execute_ingestion_marks_job_failed_when_indexing_fails(monkeypatch):
    target = CrawlTarget(
        url="https://example.com/changed",
        menu_path="공지",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
    )
    recorded: dict[str, object] = {}

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePool:
        def acquire(self):
            return FakeConnection()

        async def close(self):
            pass

    async def fake_create_pool():
        return FakePool()

    async def fake_create_crawl_job(connection):
        return "job-1"

    async def fake_load_existing_document_states(connection, urls):
        return {}

    def fake_fetch_html(url):
        return "<html><body><article class='articleBox'><p>changed</p></article></body></html>"

    async def fake_parse_html(target, html, markdown_renderer=None):
        return ParsedDocument(
            url=target.url,
            title="Example",
            menu_path=target.menu_path,
            category=None,
            source_scope="unknown",
            page_kind="unknown",
            source_type=target.source_type,
            content_hash="hash-1",
            crawled_at=datetime(2026, 5, 6, tzinfo=UTC),
            chunks=[ParsedChunk(chunk_index=0, content="changed", chunk_type="text")],
        )

    async def fake_persist_document(connection, document):
        return "document-1"

    async def fake_index_crawl_documents(connection):
        raise RuntimeError("chroma unavailable")

    async def fake_finish_crawl_job(
        connection,
        crawl_job_id,
        *,
        status,
        pages_crawled,
        pages_changed,
        error,
    ):
        recorded["finished"] = {
            "status": status,
            "pages_crawled": pages_crawled,
            "pages_changed": pages_changed,
            "error": error,
        }

    monkeypatch.setattr("tasks.crawl.create_pool", fake_create_pool)
    monkeypatch.setattr("tasks.crawl.create_crawl_job", fake_create_crawl_job)
    monkeypatch.setattr(
        "tasks.crawl.load_existing_document_states",
        fake_load_existing_document_states,
    )
    monkeypatch.setattr("tasks.crawl.fetch_html", fake_fetch_html)
    monkeypatch.setattr("tasks.crawl.parse_html", fake_parse_html)
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.index_crawl_documents", fake_index_crawl_documents)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)

    stats = await execute_ingestion(
        [target],
        [],
        initial_failures=["https://timeout.honam.ac.kr/main: simulated timeout"],
    )

    assert stats.pages_changed == 1
    assert stats.failures == [
        "https://timeout.honam.ac.kr/main: simulated timeout",
        "indexing: chroma unavailable",
    ]
    assert recorded["finished"] == {
        "status": "failed",
        "pages_crawled": 1,
        "pages_changed": 1,
        "error": (
            "https://timeout.honam.ac.kr/main: simulated timeout\nindexing: chroma unavailable"
        ),
    }
