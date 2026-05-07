from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import tasks.parse as parse_module
from tasks.contracts import CrawlTarget
from tasks.parsers.graduation_credit import normalize_graduation_credit_table
from tasks.parsers.html_tables import (
    extract_html_table_chunks,
    prefer_structured_html_table_chunks,
)
from tasks.parsers.markdown import markdown_to_text_chunks, split_markdown_ordered_blocks
from tasks.parsers.roadmap import build_semester_roadmap_chunks


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


@pytest.mark.asyncio
async def test_article_markdown_renderer_reuses_crawler(monkeypatch):
    class FakeMarkdown:
        raw_markdown = "raw output"

        def __init__(self, value: str) -> None:
            self.fit_markdown = value

    class FakeResult:
        def __init__(self, value: str) -> None:
            self.markdown = FakeMarkdown(value)

    class FakeCrawlerRunConfig:
        def __init__(self, *, cache_mode):
            self.cache_mode = cache_mode

    class FakeCrawler:
        enter_count = 0
        exit_count = 0
        arun_urls: list[str] = []

        def __init__(self, *, base_directory):
            self.base_directory = base_directory

        async def __aenter__(self):
            FakeCrawler.enter_count += 1
            return self

        async def __aexit__(self, exc_type, exc, tb):
            FakeCrawler.exit_count += 1
            return False

        async def arun(self, *, url, config):
            FakeCrawler.arun_urls.append(url)
            return FakeResult(f"fit output {len(FakeCrawler.arun_urls)}")

    monkeypatch.setattr(
        parse_module,
        "get_crawl4ai_components",
        lambda: (FakeCrawler, SimpleNamespace(BYPASS="bypass"), FakeCrawlerRunConfig),
    )

    async with parse_module.create_article_markdown_renderer(concurrency=1) as renderer:
        first = await renderer("<article>첫번째</article>")
        second = await renderer("<article>두번째</article>")

    assert first == "fit output 1"
    assert second == "fit output 2"
    assert FakeCrawler.enter_count == 1
    assert FakeCrawler.exit_count == 1
    assert FakeCrawler.arun_urls == [
        "raw:<article>첫번째</article>",
        "raw:<article>두번째</article>",
    ]


def test_markdown_to_text_chunks_preserves_header_metadata():
    chunks = markdown_to_text_chunks("# 장학 안내\n\n장학금 신청 절차를 안내합니다.")

    assert [chunk.chunk_type for chunk in chunks] == ["text"]
    assert chunks[0].meta["header_1"] == "장학 안내"
    assert "장학금 신청 절차" in chunks[0].content


def test_split_markdown_ordered_blocks_keeps_table_between_text_blocks():
    blocks = split_markdown_ordered_blocks(
        "첫 문단\n\n"
        "|구분|값|\n"
        "|---|---|\n"
        "|중간표|1|\n\n"
        "## 다음 안내\n"
        "마지막 문단"
    )

    assert blocks == [
        ("text", "첫 문단"),
        ("table", "|구분|값|\n|---|---|\n|중간표|1|"),
        ("text", "## 다음 안내\n마지막 문단"),
    ]


def test_build_content_hash_changes_when_parser_version_changes():
    assert parse_module.build_content_hash("same article", parser_version="v1") != (
        parse_module.build_content_hash("same article", parser_version="v2")
    )


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
    assert document.chunks[1].meta["records"] == [{"구분": "성적장학", "금액": "100만원"}]
    assert document.chunks[1].content == "구분: 성적장학 | 금액: 100만원"


def test_prefer_structured_html_table_chunks_handles_mismatched_table_counts():
    chunks = [
        parse_module.ParsedChunk(
            chunk_index=0,
            content="앞 문단",
            chunk_type="text",
            meta={},
        ),
        parse_module.ParsedChunk(
            chunk_index=1,
            content="markdown table",
            chunk_type="table",
            meta={"headers": ["markdown"]},
        ),
        parse_module.ParsedChunk(
            chunk_index=2,
            content="뒤 문단",
            chunk_type="text",
            meta={},
        ),
    ]
    html_tables = [
        parse_module.ParsedChunk(
            chunk_index=0,
            content="structured first",
            chunk_type="table",
            meta={"headers": ["structured-first"]},
        ),
        parse_module.ParsedChunk(
            chunk_index=1,
            content="structured extra",
            chunk_type="table",
            meta={"headers": ["structured-extra"]},
        ),
    ]

    merged = prefer_structured_html_table_chunks(chunks, html_tables)

    assert [chunk.chunk_type for chunk in merged] == ["text", "table", "text", "table"]
    assert [chunk.chunk_index for chunk in merged] == [0, 1, 2, 3]
    assert merged[1].content == "structured first"
    assert merged[3].content == "structured extra"


@pytest.mark.asyncio
async def test_parse_html_uses_structured_html_table_when_markdown_table_loses_spans():
    article_html = """
    <article class="articleBox">
      <p>로드맵입니다.</p>
      <table>
        <tr>
          <th rowspan="2">학문 분야</th>
          <th rowspan="2">구분</th>
          <th colspan="2">1학년</th>
        </tr>
        <tr>
          <th>1학기</th>
          <th>2학기</th>
        </tr>
        <tr>
          <th>컴퓨터공학</th>
          <th>전공선택</th>
          <td>컴퓨터개론(3)</td>
          <td>리눅스시스템(3)</td>
        </tr>
      </table>
    </article>
    """

    async def fake_markdown_renderer(article_html: str) -> str:
        return (
            "로드맵입니다.\n\n"
            "| 학문 분야 | 구분 | 1학기 | 2학기 |\n"
            "| --- | --- | --- | --- |\n"
            "| 컴퓨터공학 | 전공선택 | 컴퓨터개론(3) | 리눅스시스템(3) |"
        )

    target = CrawlTarget(
        url="https://com.honam.ac.kr/SubjectRoadmap2026",
        menu_path="컴퓨터공학과 > 교과목로드맵 2026",
        source_type="html",
        site_name="컴퓨터공학과",
    )

    document = await parse_module.parse_html(
        target=target,
        html=f"<html><body>{article_html}</body></html>",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        markdown_renderer=fake_markdown_renderer,
    )

    table_chunks = [chunk for chunk in document.chunks if chunk.chunk_type == "table"]
    assert len(table_chunks) == 1
    assert table_chunks[0].meta["headers"] == [
        "학문 분야",
        "구분",
        "1학년 1학기",
        "1학년 2학기",
    ]


def test_extract_html_table_chunks_expands_roadmap_spans_for_llm_readability():
    article_html = """
    <article class="articleBox">
      <table>
        <tr>
          <th rowspan="2">학문 분야</th>
          <th rowspan="2">구분</th>
          <th colspan="2">1학년</th>
          <th colspan="2">2학년</th>
        </tr>
        <tr>
          <th>1학기</th>
          <th>2학기</th>
          <th>1학기</th>
          <th>2학기</th>
        </tr>
        <tr>
          <th rowspan="2">컴퓨터공학 (일반 전공)</th>
          <th>전공선택 (75학점)</th>
          <td>컴퓨터개론(3)<br>생성형AI활용(2)</td>
          <td>리눅스시스템(3)</td>
          <td>데이터구조(3)</td>
          <td>데이터베이스(3)</td>
        </tr>
        <tr>
          <th>융합전공 (6학점)</th>
          <td></td>
          <td></td>
          <td>객체지향과 데이터활용(3)</td>
          <td></td>
        </tr>
      </table>
    </article>
    """

    chunks = extract_html_table_chunks(article_html, start_index=0)

    assert len(chunks) == 1
    assert chunks[0].content.splitlines() == [
        (
            "학문 분야: 컴퓨터공학 (일반 전공) | 구분: 전공선택 (75학점) | "
            "1학년 1학기: 컴퓨터개론(3) 생성형AI활용(2) | "
            "1학년 2학기: 리눅스시스템(3) | 2학년 1학기: 데이터구조(3) | "
            "2학년 2학기: 데이터베이스(3)"
        ),
        (
            "학문 분야: 컴퓨터공학 (일반 전공) | 구분: 융합전공 (6학점) | "
            "2학년 1학기: 객체지향과 데이터활용(3)"
        ),
    ]
    assert chunks[0].meta["records"] == [
        {
            "학문 분야": "컴퓨터공학 (일반 전공)",
            "구분": "전공선택 (75학점)",
            "1학년 1학기": "컴퓨터개론(3) 생성형AI활용(2)",
            "1학년 2학기": "리눅스시스템(3)",
            "2학년 1학기": "데이터구조(3)",
            "2학년 2학기": "데이터베이스(3)",
        },
        {
            "학문 분야": "컴퓨터공학 (일반 전공)",
            "구분": "융합전공 (6학점)",
            "2학년 1학기": "객체지향과 데이터활용(3)",
        },
    ]


def test_build_semester_roadmap_chunks_groups_records_by_grade_and_semester():
    table_chunk = parse_module.ParsedChunk(
        chunk_index=0,
        content="",
        chunk_type="table",
        meta={
            "records": [
                {
                    "학문 분야": "컴퓨터공학 (일반 전공)",
                    "구분": "전공선택 (75학점)",
                    "1학년 1학기": "대학생활과전공이해(1) 컴퓨터개론(3) 생성형AI활용(2)",
                    "1학년 2학기": "인성함양과진로탐색(1)",
                },
                {
                    "학문 분야": "컴퓨터공학 (일반 전공)",
                    "구분": "소양교양 (9학점)",
                    "1학년 1학기": "파이썬 프로그래밍(융합 3) 사회봉사(봉사 1)",
                },
            ]
        },
    )
    target = CrawlTarget(
        url="https://com.honam.ac.kr/SubjectRoadmap2026",
        menu_path="컴퓨터공학과 > 교과목로드맵 2026",
        source_type="html",
        site_name="컴퓨터공학과",
    )

    chunks = build_semester_roadmap_chunks(
        target=target,
        table_chunks=[table_chunk],
        start_index=1,
    )

    assert [chunk.content for chunk in chunks] == [
        (
            "컴퓨터공학과 교과목로드맵 2026년 1학년 1학기\n"
            "전공선택: 대학생활과전공이해(1) 컴퓨터개론(3) 생성형AI활용(2)\n"
            "소양교양: 파이썬 프로그래밍(융합 3) 사회봉사(봉사 1)"
        ),
        (
            "컴퓨터공학과 교과목로드맵 2026년 1학년 2학기\n"
            "전공선택: 인성함양과진로탐색(1)"
        ),
    ]
    assert chunks[0].meta == {
        "derived_from": "table",
        "kind": "semester_roadmap",
        "department": "컴퓨터공학과",
        "year": 2026,
        "grade": 1,
        "semester": 1,
    }


def test_graduation_credit_parser_module_recombines_multi_level_headers():
    content, meta = normalize_graduation_credit_table(
        [
            ["대학", "학과(부)", "교양영역", "", "", "", "전공영역"],
            ["", "", "핵심교양", "균형교양", "소양교양", "소계", "전공선택"],
            ["사회경영대학", "호텔컨벤션학과★", "12", "9", "9", "30", "60"],
        ]
    )

    assert "학과(부): 호텔컨벤션학과★" in content
    assert meta["headers"] == [
        "대학",
        "학과(부)",
        "교양영역 핵심교양",
        "교양영역 균형교양",
        "교양영역 소양교양",
        "교양영역 소계",
        "전공영역 전공선택",
    ]


@pytest.mark.asyncio
async def test_parse_html_adds_semester_roadmap_chunks():
    async def fake_markdown_renderer(article_html: str) -> str:
        return "# 교과목로드맵\n\n표는 별도 chunk로 파싱합니다."

    html = """
    <html>
      <body>
        <article class="articleBox">
          <h1>교과목로드맵</h1>
          <table>
            <tr>
              <th rowspan="2">학문 분야</th>
              <th rowspan="2">구분</th>
              <th>1학년</th>
            </tr>
            <tr>
              <th>1학기</th>
            </tr>
            <tr>
              <th>컴퓨터공학 (일반 전공)</th>
              <th>전공선택 (75학점)</th>
              <td>컴퓨터개론(3)</td>
            </tr>
          </table>
        </article>
      </body>
    </html>
    """
    target = CrawlTarget(
        url="https://com.honam.ac.kr/SubjectRoadmap2026",
        menu_path="컴퓨터공학과 > 교과목로드맵 2026",
        source_type="html",
        site_name="컴퓨터공학과",
    )

    document = await parse_module.parse_html(
        target=target,
        html=html,
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        markdown_renderer=fake_markdown_renderer,
    )

    derived_chunks = [
        chunk for chunk in document.chunks if chunk.meta.get("kind") == "semester_roadmap"
    ]
    assert len(derived_chunks) == 1
    assert derived_chunks[0].content == (
        "컴퓨터공학과 교과목로드맵 2026년 1학년 1학기\n"
        "전공선택: 컴퓨터개론(3)"
    )


@pytest.mark.asyncio
async def test_parse_html_keeps_text_and_table_chunks_in_source_order():
    async def fake_markdown_renderer(article_html: str) -> str:
        return (
            "첫 문단입니다.\n\n"
            "|구분|값|\n"
            "|---|---|\n"
            "|중간표|1|\n\n"
            "마지막 문단입니다."
        )

    html = """
    <html>
      <body>
        <article class="articleBox">
          <p>첫 문단입니다.</p>
          <table>
            <tr><th>구분</th><th>값</th></tr>
            <tr><td>중간표</td><td>1</td></tr>
          </table>
          <p>마지막 문단입니다.</p>
        </article>
      </body>
    </html>
    """
    target = CrawlTarget(
        url="https://www.honam.ac.kr/Ordered",
        menu_path="순서",
        source_type="html",
    )

    document = await parse_module.parse_html(
        target=target,
        html=html,
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        markdown_renderer=fake_markdown_renderer,
    )

    assert [chunk.chunk_type for chunk in document.chunks] == ["text", "table", "text"]
    assert document.chunks[0].content == "첫 문단입니다."
    assert document.chunks[1].content == "구분: 중간표 | 값: 1"
    assert document.chunks[2].content == "마지막 문단입니다."
    assert [chunk.chunk_index for chunk in document.chunks] == [0, 1, 2]
