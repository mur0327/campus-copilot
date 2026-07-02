from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot"
)

from datetime import UTC, datetime  # noqa: E402

import pytest  # noqa: E402

import tasks.crawl as crawl  # noqa: E402
import tasks.fetch_cache as fetch_cache  # noqa: E402
from tasks.contracts import CrawlTarget, ParsedDocument  # noqa: E402
from tasks.storage import ExistingDocumentState  # noqa: E402


def _html_target(url: str) -> CrawlTarget:
    return CrawlTarget(
        url=url,
        menu_path="학사",
        source_type="html",
        source_scope="general_academic",
        page_kind="academic",
    )


def _pdf_target(url: str) -> CrawlTarget:
    return CrawlTarget(
        url=url,
        menu_path="졸업",
        source_type="pdf",
        source_scope="general_academic",
        page_kind="academic",
    )


def test_fetch_cache_html_and_bytes_roundtrip(tmp_path):
    fetch_cache.write_html(tmp_path, "https://www.honam.ac.kr/General_Rest", "<p>휴학</p>")
    assert fetch_cache.read_html(tmp_path, "https://www.honam.ac.kr/General_Rest") == "<p>휴학</p>"
    assert fetch_cache.read_html(tmp_path, "https://www.honam.ac.kr/missing") is None

    fetch_cache.write_bytes(tmp_path, "https://www.honam.ac.kr/doc.pdf", b"%PDF-1.4")
    assert fetch_cache.read_bytes(tmp_path, "https://www.honam.ac.kr/doc.pdf") == b"%PDF-1.4"
    assert fetch_cache.read_bytes(tmp_path, "https://www.honam.ac.kr/missing.pdf") is None


def test_fetch_cache_write_is_atomic_without_temp_residue(tmp_path):
    fetch_cache.write_html(tmp_path, "https://www.honam.ac.kr/A", "<p>x</p>")
    # 원자적 쓰기는 .tmp 잔여 파일을 남기지 않아야 한다.
    assert list(tmp_path.glob("*.tmp")) == []


def test_cached_html_only_returns_in_cache_first_mode(tmp_path, monkeypatch):
    fetch_cache.write_html(tmp_path, "https://www.honam.ac.kr/A", "<p>캐시</p>")
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_dir", str(tmp_path))

    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_mode", "network")
    assert crawl.cached_html("https://www.honam.ac.kr/A") is None

    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_mode", "cache_first")
    assert crawl.cached_html("https://www.honam.ac.kr/A") == "<p>캐시</p>"


def test_cached_pdf_bytes_and_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_dir", str(tmp_path))
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_mode", "cache_first")

    assert crawl.cached_pdf_bytes("https://www.honam.ac.kr/x.pdf") is None
    crawl.store_fetched_pdf("https://www.honam.ac.kr/x.pdf", b"%PDF-1.4")
    assert crawl.cached_pdf_bytes("https://www.honam.ac.kr/x.pdf") == b"%PDF-1.4"


def test_store_helpers_no_op_without_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_dir", None)
    # cache_dir이 없으면 저장은 조용히 no-op이고 예외를 던지지 않는다.
    crawl.store_fetched_html("https://www.honam.ac.kr/A", "<p>x</p>")
    crawl.store_fetched_pdf("https://www.honam.ac.kr/A.pdf", b"x")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_invalid_html_response_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_dir", str(tmp_path))
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_mode", "network")
    # article.articleBox가 없는(에러/리다이렉트) 200 응답.
    monkeypatch.setattr(crawl, "fetch_html", lambda url: "<html><body>error</body></html>")

    result = await crawl.fetch_and_maybe_parse_document(
        _html_target("https://www.honam.ac.kr/bad"), None
    )

    assert result.document is None
    # 무효 본문은 캐시에 남지 않아야 한다(cache_first 재사용 고착 방지).
    assert fetch_cache.read_html(tmp_path, "https://www.honam.ac.kr/bad") is None


@pytest.mark.asyncio
async def test_valid_html_is_cached_after_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_dir", str(tmp_path))
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_mode", "network")
    valid_html = '<article class="articleBox"><h2>휴학</h2><p>내용</p></article>'
    monkeypatch.setattr(crawl, "fetch_html", lambda url: valid_html)

    async def fake_parse_html(target, html, markdown_renderer=None):
        return ParsedDocument(
            url=target.url,
            title="휴학",
            menu_path=target.menu_path,
            category=None,
            source_scope=target.source_scope,
            page_kind=target.page_kind,
            source_type="html",
            content_hash="hash",
            crawled_at=datetime.now(UTC),
            chunks=[],
        )

    monkeypatch.setattr(crawl, "parse_html", fake_parse_html)

    target = _html_target("https://www.honam.ac.kr/General_Rest")
    result = await crawl.fetch_and_maybe_parse_document(target, None)

    assert result.document is not None
    assert fetch_cache.read_html(tmp_path, target.url) == valid_html


@pytest.mark.asyncio
async def test_board_list_page_is_not_indexed(monkeypatch):
    # 게시판 목록 페이지(번호/제목/조회수)는 자식 링크 발견용일 뿐, 문서로 색인하지 않는다.
    board_html = """
    <html><body><article class="articleBox">
      <table>
        <tr><th>번호</th><th>제목</th><th>조회수</th></tr>
        <tr><td>30</td><td>Q: 증명서 발급은 어떻게 하나요?</td><td>306</td></tr>
      </table>
    </article></body></html>
    """
    monkeypatch.setattr(crawl, "fetch_html", lambda url: board_html)

    async def fail_parse_html(*args, **kwargs):
        raise AssertionError("board list pages must be skipped before parse")

    monkeypatch.setattr(crawl, "parse_html", fail_parse_html)

    result = await crawl.fetch_and_maybe_parse_document(
        _html_target("https://dreamlife.honam.ac.kr/FrequentlyQuestions"), None
    )

    assert result.document is None
    assert result.failure is None


@pytest.mark.asyncio
async def test_unchanged_pdf_is_cached_even_when_parse_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_dir", str(tmp_path))
    monkeypatch.setattr(crawl.settings, "crawl_fetch_cache_mode", "network")
    pdf_bytes = b"%PDF-1.4 unchanged"
    monkeypatch.setattr(crawl, "fetch_pdf_bytes", lambda url: pdf_bytes)
    monkeypatch.setattr(crawl, "build_content_hash", lambda raw, target=None: "same-hash")

    async def fail_parse_pdf(*args, **kwargs):
        raise AssertionError("unchanged pdf should skip parse_pdf")

    monkeypatch.setattr(crawl, "parse_pdf", fail_parse_pdf)

    target = _pdf_target("https://www.honam.ac.kr/grad.pdf")
    existing = ExistingDocumentState(content_hash="same-hash", chunk_count=3)
    result = await crawl.fetch_and_maybe_parse_document(target, existing)

    # 변경 없음이라 parse/저장은 건너뛰지만(write-through), cold 캐시는 채워야 한다.
    assert result.document is None
    assert fetch_cache.read_bytes(tmp_path, target.url) == pdf_bytes
