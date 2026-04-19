from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import tasks.parse as parse_module
from tasks.contracts import CrawlTarget


@pytest.fixture(autouse=True)
def phase_two_parse_env(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
    )
    monkeypatch.setenv("CRAWL4_AI_BASE_DIRECTORY", "/tmp/crawl4ai")


@pytest.mark.asyncio
async def test_render_markdown_from_article_uses_fit_markdown(monkeypatch):
    class FakeMarkdown:
        fit_markdown = "fit output"
        raw_markdown = "raw output"

    class FakeResult:
        markdown = FakeMarkdown()

    class FakeCrawlerRunConfig:
        def __init__(self, *, cache_mode):
            assert cache_mode == "bypass"
            self.cache_mode = cache_mode

    class FakeCrawler:
        init_base_directory: str | None = None
        arun_url: str | None = None
        arun_config: object | None = None

        def __init__(self, *, base_directory):
            FakeCrawler.init_base_directory = base_directory

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def arun(self, *, url, config):
            FakeCrawler.arun_url = url
            FakeCrawler.arun_config = config
            return FakeResult()

    monkeypatch.setattr(
        parse_module,
        "get_crawl4ai_components",
        lambda: (FakeCrawler, SimpleNamespace(BYPASS="bypass"), FakeCrawlerRunConfig),
    )

    markdown = await parse_module.render_markdown_from_article("<article>내용</article>")

    assert markdown == "fit output"
    assert FakeCrawler.init_base_directory == "/tmp/crawl4ai"
    assert FakeCrawler.arun_url == "raw:<article>내용</article>"
    assert isinstance(FakeCrawler.arun_config, FakeCrawlerRunConfig)


def test_markdown_to_text_chunks_preserves_header_metadata():
    chunks = parse_module.markdown_to_text_chunks(
        "# 장학 안내\n\n장학금 신청 절차를 안내합니다."
    )

    assert [chunk.chunk_type for chunk in chunks] == ["text"]
    assert chunks[0].meta["header_1"] == "장학 안내"
    assert "장학금 신청 절차" in chunks[0].content


@pytest.mark.asyncio
async def test_parse_html_creates_text_chunks(fixture_text):
    async def fake_markdown_renderer(article_html: str) -> str:
        return "# 장학 안내\n\n장학금 신청 절차를 안내합니다."

    target = CrawlTarget(
        url="https://www.honam.ac.kr/Scholarship/list",
        menu_path="장학",
        source_type="html",
    )

    document = await parse_module.parse_html(
        target=target,
        html=fixture_text("article_page.html"),
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        markdown_renderer=fake_markdown_renderer,
    )

    assert document.source_type == "html"
    assert document.content_hash
    assert [chunk.chunk_type for chunk in document.chunks] == ["text"]
    assert document.chunks[0].meta["header_1"] == "장학 안내"
    assert "장학금 신청 절차" in document.chunks[0].content


@pytest.mark.asyncio
async def test_parse_html_creates_table_chunks(fixture_text):
    async def fake_markdown_renderer(article_html: str) -> str:
        return "# 장학 기준\n\n대상과 금액은 아래 표를 참고하세요."

    target = CrawlTarget(
        url="https://www.honam.ac.kr/Scholarship/table",
        menu_path="장학",
        source_type="html",
    )

    document = await parse_module.parse_html(
        target=target,
        html=fixture_text("article_page_with_table.html"),
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        markdown_renderer=fake_markdown_renderer,
    )

    assert [chunk.chunk_type for chunk in document.chunks] == ["text", "table"]
    assert document.chunks[1].meta["headers"] == ["구분", "금액"]
