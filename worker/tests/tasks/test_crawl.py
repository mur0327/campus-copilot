import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from tasks.contracts import CrawlTarget
from tasks.crawl import (
    build_graduation_pdf_targets,
    discover_html_targets,
    discover_html_targets_with_failures,
    discover_pdf_targets,
    extract_article_box_targets,
    extract_department_sites,
    extract_menu_targets,
    extract_pdf_years,
    is_honam_url,
    is_redirect_page,
)


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
    assert all(target.site_name == "호남대학교" for target in targets)
    assert all(target.site_url == "https://www.honam.ac.kr" for target in targets)


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
        site_name="호남대학교",
        site_url="https://www.honam.ac.kr",
    )

    targets = extract_article_box_targets(parent=parent, html=html)

    target_summaries = [
        (target.menu_path, target.url, target.site_name, target.site_url) for target in targets
    ]
    assert target_summaries == [
        (
            "학사일정 > 2026년",
            "https://www.honam.ac.kr/AcademicCalendar/main/2026",
            "호남대학교",
            "https://www.honam.ac.kr",
        ),
        (
            "학사일정 > 2025년",
            "https://www.honam.ac.kr/AcademicCalendar/main/2025",
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
          <a href="/img/contents/A01/hnsm_AI.zip">zip 다운로드</a>
        </article>
      </body>
    </html>
    """
    parent = CrawlTarget(
        url="https://www.honam.ac.kr/GraduateGrades",
        menu_path="졸업학점",
        source_type="html",
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


@pytest.mark.asyncio
async def test_discover_html_targets_crawls_each_configured_root_main(monkeypatch, fixture_text):
    monkeypatch.setattr("tasks.crawl.is_redirect_page", lambda html: False)
    monkeypatch.setattr(
        "tasks.crawl.settings.crawl_target_urls",
        ["https://www.honam.ac.kr", "https://enter.honam.ac.kr"],
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

    assert [(target.url, target.site_url) for target in targets] == [
        ("https://www.honam.ac.kr/RootNotice", "https://www.honam.ac.kr"),
        ("https://enter.honam.ac.kr/AdmissionGuide", "https://enter.honam.ac.kr"),
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
    assert attempts["https://www.honam.ac.kr/Flaky"] == 3


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
async def test_discover_html_targets_uses_fetcher_and_skips_redirect_pages():
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
        "tasks.crawl.settings.crawl_target_urls",
        ["https://enter.honam.ac.kr", "https://www.honam.ac.kr"],
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
