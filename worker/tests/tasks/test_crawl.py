import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from tasks.crawl import (
    build_graduation_pdf_targets,
    discover_html_targets,
    discover_pdf_targets,
    extract_menu_targets,
    extract_pdf_years,
    is_redirect_page,
)


def test_extract_menu_targets_skips_data_link_and_dedupes(fixture_text):
    targets = extract_menu_targets(
        html=fixture_text("menu_main.html"),
        base_url="https://www.honam.ac.kr",
    )

    assert [(target.menu_path, target.url, target.source_type) for target in targets] == [
        ("입학", "https://www.honam.ac.kr/Admissions/notice", "html"),
        ("장학", "https://www.honam.ac.kr/Scholarship/list", "html"),
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
          <option value="2022">2022</option>
          <option value="2024">2024</option>
          <option value="2023">2023</option>
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


def test_is_redirect_page_detects_page_moved_title(fixture_text):
    assert is_redirect_page(fixture_text("page_moved.html")) is True
