# Phase 2 Crawling And Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 호남대학교 사이트의 HTML/PDF 문서를 수집·파싱·청킹하고 PostgreSQL에 적재하는 Phase 2 워커 파이프라인을 구현한다.

**Architecture:** `worker` 서비스 안에 설정, 크롤링 대상 수집, HTML/PDF 파싱, 청킹, 적재 책임을 분리한다. DOM 구조는 `hnu-ai` 기준선을 재사용하되 구현은 Campus Copilot 문서 기준으로 새로 작성하고, 적재 대상 스키마는 `backend` Alembic 마이그레이션으로 고정한다.

**Tech Stack:** Python 3.12, APScheduler, curl-cffi, BeautifulSoup4, Crawl4AI, langchain-opendataloader-pdf, LangChain text splitters, asyncpg, Alembic, pytest, pytest-asyncio

---

## 2026-05-06 중간 상태

현재 Phase 2는 실제 Honam URL discovery, HTML/PDF 파싱, PostgreSQL 적재까지 연결된 상태다.

구현 결정:

- `CRAWL_TARGET_URLS`는 CSV 문자열 환경변수로 받으며 기본값은 `https://www.honam.ac.kr`이다.
- 운영 예시는 `https://www.honam.ac.kr,https://enter.honam.ac.kr`를 사용한다.
- 각 루트는 동일하게 `/main`에서 메뉴를 수집한다.
- `*.honam.ac.kr` 서브도메인 URL은 수집 대상에 포함하고, 외부 도메인은 article link 확장 단계에서 제외한다.
- target validation은 2-pass로 수행한다.
- 1차 validation concurrency는 `CRAWL_VALIDATION_CONCURRENCY=12`, retry validation concurrency는 `CRAWL_RETRY_VALIDATION_CONCURRENCY=3`이다.
- 2-pass 후에도 실패한 URL은 `CrawlDiscoveryResult.failures`에 남기고, `run_crawl()`에서 `execute_ingestion(initial_failures=...)`로 넘겨 최종 `crawl_jobs.error`에도 기록한다.
- ingestion fetch/parse는 `CRAWL_INGESTION_CONCURRENCY=6` 제한 병렬로 수행한다.
- HTML은 fetch 후 `article.articleBox`를 먼저 추출하고 기존 DB의 `content_hash`, `chunk_count`와 비교한다. hash가 같고 chunk가 있으면 Crawl4AI 파싱과 재적재를 건너뛴다.
- PDF도 다운로드 바이트 hash가 기존 DB 상태와 같고 chunk가 있으면 opendataloader-pdf 파싱과 재적재를 건너뛴다.
- PDF 졸업학점 표는 전용 정규화 규칙을 사용한다. 다단 헤더는 `교양영역 핵심교양`, `교양영역 균형교양`, `교양영역 소양교양`, `교양영역 소계`처럼 결합하고, 병합셀은 행 단위로 채운다.
- 기존 문서의 `content_hash`가 같더라도 DB에 저장된 chunk 수가 0이면 stale parse 결과로 보고 다시 적재한다.

실측 결과:

- live discovery: `html_targets=878`, `pdf_targets=5`, `total_targets=883`, `external_targets=0`
- live discovery 시간: HTML `258.19s`, PDF `0.41s`, 총 `258.59s`
- 해당 discovery run의 최종 실패 URL: `https://airline.honam.ac.kr/main`
- full `run_crawl()` E2E 시간: `2249.83s` 약 37.5분
- full `run_crawl()` 결과: `pages_crawled=848`, `pages_changed=791`, `failures=43`
- 최신 crawl job 확인: `status=completed`, `error_lines=43`
- 2025 졸업학점 PDF targeted ingestion 후 DB 확인: `chunk_count=8`, `호텔컨벤션학과★` 행 포함
- 병렬 ingestion + hash precheck 적용 후 재실행: `run_crawl_seconds=250.10s` 약 4.2분
- 최적화 후 재실행 결과: `pages_crawled=875`, `pages_changed=35`, `failures=8`

남은 주의점:

- full E2E 병목은 이제 ingestion보다 live discovery와 네트워크 timeout 쪽 비중이 크다.
- 30초 timeout URL은 네트워크 상태에 따라 run마다 달라진다.
- DB에 기존 hash와 chunk가 충분히 쌓인 이후에는 precheck 효과가 크지만, 최초 적재나 parser rule 변경 후에는 변경 문서 파싱 비용이 다시 발생한다.
- 2025 PDF 1페이지는 원하는 형태로 정규화됐지만, 2페이지 이후 일부 표 헤더는 아직 완전한 전용 정규화 대상이 아니다.

---

## 파일 맵

```
campus-copilot/
├── .env.example                                           # Phase 2 worker 환경변수 추가
├── backend/
│   └── alembic/
│       └── versions/
│           └── 20260419_01_create_ingestion_tables.py     # documents, document_chunks, crawl_jobs 등 생성
└── worker/
    ├── core/
    │   ├── __init__.py
    │   ├── config.py                                      # WorkerSettings
    │   └── db.py                                          # asyncpg pool 및 DB URL 정규화
    ├── tasks/
    │   ├── contracts.py                                   # CrawlTarget, ParsedDocument, ParsedChunk, CrawlStats
    │   ├── crawl.py                                       # 메뉴/PDF 대상 수집, 리다이렉트 필터, run_crawl
    │   ├── parse.py                                       # HTML/PDF 파싱, 청킹, content_hash 계산
    │   ├── storage.py                                     # crawl_jobs / documents / document_chunks 적재
    │   └── scheduler.py                                   # 스케줄 진입점
    └── tests/
        ├── conftest.py
        ├── fixtures/
        │   ├── menu_main.html
        │   ├── page_moved.html
        │   ├── article_page.html
        │   └── article_page_with_table.html
        └── tasks/
            ├── test_config.py
            ├── test_crawl.py
            ├── test_parse_html.py
            ├── test_parse_pdf.py
            ├── test_storage.py
            └── test_scheduler.py
```

---

### Task 1: Worker Settings And Shared Contracts

**Files:**
- Modify: `.env.example`
- Create: `worker/core/__init__.py`
- Create: `worker/core/config.py`
- Create: `worker/tasks/contracts.py`
- Create: `worker/tests/conftest.py`
- Test: `worker/tests/tasks/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# worker/tests/tasks/test_config.py
from core.config import WorkerSettings


def test_worker_settings_phase_two_defaults(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
    )
    monkeypatch.setenv("CRAWL_TARGET_URL", "https://www.honam.ac.kr")

    settings = WorkerSettings(_env_file=None)

    assert settings.crawl_target_url == "https://www.honam.ac.kr"
    assert settings.crawl_main_path == "/main"
    assert settings.crawl_graduation_path == "/GraduateGrades"
    assert settings.crawl_pdf_year_limit == 5
    assert settings.crawl_impersonate == "chrome120"
    assert settings.crawl4ai_base_directory == "/tmp/crawl4ai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd worker && uv run pytest tests/tasks/test_config.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'core'`

- [ ] **Step 3: Write minimal implementation**

```python
# worker/core/__init__.py
"""Worker core package."""
```

```python
# worker/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    crawl_target_url: str = "https://www.honam.ac.kr"
    crawl_main_path: str = "/main"
    crawl_content_selector: str = "article.articleBox"
    crawl_menu_selector: str = "ul#mainMenu"
    crawl_graduation_path: str = "/GraduateGrades"
    crawl_pdf_year_limit: int = 5
    crawl_timeout_seconds: int = 30
    crawl_impersonate: str = "chrome120"
    crawl_schedule: str = "0 3 * * *"
    crawl4ai_base_directory: str = "/tmp/crawl4ai"
    pdf_hybrid_backend: str | None = None
    pdf_hybrid_mode: str = "auto"
    pdf_hybrid_url: str = "http://localhost:5002"


settings = WorkerSettings()
```

```python
# worker/tasks/contracts.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

SourceType = Literal["html", "pdf"]
ChunkType = Literal["text", "table"]


@dataclass(slots=True)
class CrawlTarget:
    url: str
    menu_path: str
    source_type: SourceType
    title_hint: str | None = None
    year: int | None = None


@dataclass(slots=True)
class ParsedChunk:
    chunk_index: int
    content: str
    chunk_type: ChunkType
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedDocument:
    url: str
    title: str | None
    menu_path: str | None
    category: str | None
    source_type: SourceType
    content_hash: str
    crawled_at: datetime
    chunks: list[ParsedChunk] = field(default_factory=list)


@dataclass(slots=True)
class CrawlStats:
    pages_crawled: int = 0
    pages_changed: int = 0
    failures: list[str] = field(default_factory=list)
```

```python
# worker/tests/conftest.py
from pathlib import Path

import pytest


@pytest.fixture
def fixture_text() -> callable:
    base_dir = Path(__file__).parent / "fixtures"

    def _read(name: str) -> str:
        return (base_dir / name).read_text(encoding="utf-8")

    return _read
```

```bash
# .env.example
CRAWL_TARGET_URL=https://www.honam.ac.kr
CRAWL_MAIN_PATH=/main
CRAWL_CONTENT_SELECTOR=article.articleBox
CRAWL_MENU_SELECTOR=ul#mainMenu
CRAWL_GRADUATION_PATH=/GraduateGrades
CRAWL_PDF_YEAR_LIMIT=5
CRAWL_TIMEOUT_SECONDS=30
CRAWL_IMPERSONATE=chrome120
CRAWL4AI_BASE_DIRECTORY=/tmp/crawl4ai
PDF_HYBRID_BACKEND=
PDF_HYBRID_MODE=auto
PDF_HYBRID_URL=http://localhost:5002
CRAWL_SCHEDULE=0 3 * * *
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd worker && uv run pytest tests/tasks/test_config.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .env.example worker/core/__init__.py worker/core/config.py worker/tasks/contracts.py worker/tests/conftest.py worker/tests/tasks/test_config.py
git commit -m "feat(worker): add phase two worker settings"
```

### Task 2: Menu Crawling And PDF Target Discovery

**Files:**
- Modify: `worker/tasks/crawl.py`
- Create: `worker/tests/fixtures/menu_main.html`
- Create: `worker/tests/fixtures/page_moved.html`
- Test: `worker/tests/tasks/test_crawl.py`

- [ ] **Step 1: Write the failing tests**

```python
# worker/tests/tasks/test_crawl.py
from tasks.crawl import (
    build_graduation_pdf_targets,
    extract_menu_targets,
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


def test_is_redirect_page_detects_page_moved_title(fixture_text):
    assert is_redirect_page(fixture_text("page_moved.html")) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker && uv run pytest tests/tasks/test_crawl.py -v`  
Expected: FAIL with `ImportError` or missing function errors from `tasks.crawl`

- [ ] **Step 3: Write minimal implementation**

```html
<!-- worker/tests/fixtures/menu_main.html -->
<html>
  <body>
    <ul id="mainMenu">
      <li><a href="/Admissions/notice">입학</a></li>
      <li><a href="/Scholarship/list">장학</a></li>
      <li><a href="/Admissions/notice">입학</a></li>
      <li><a href="/main" data-link="true">메인</a></li>
    </ul>
  </body>
</html>
```

```html
<!-- worker/tests/fixtures/page_moved.html -->
<html>
  <head><title>Page Moved</title></head>
  <body>moved</body>
</html>
```

```python
# worker/tasks/crawl.py
"""Crawling helpers and orchestration for Phase 2 ingestion."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests

from core.config import settings
from tasks.contracts import CrawlTarget


def fetch_html(url: str, timeout: int | None = None) -> str:
    response = requests.get(
        url=url,
        timeout=timeout or settings.crawl_timeout_seconds,
        impersonate=settings.crawl_impersonate,
    )
    response.raise_for_status()
    return response.text


def extract_menu_targets(html: str, base_url: str) -> list[CrawlTarget]:
    soup = BeautifulSoup(html, "html.parser")
    menu_root = soup.select_one(settings.crawl_menu_selector)
    if menu_root is None:
        return []

    deduped: dict[str, CrawlTarget] = {}
    for anchor in menu_root.select('a:not([data-link="true"])'):
        href = anchor.get("href")
        if not href:
            continue
        absolute_url = urljoin(base_url, href)
        if absolute_url in deduped:
            continue
        deduped[absolute_url] = CrawlTarget(
            url=absolute_url,
            menu_path=anchor.get_text(strip=True),
            source_type="html",
        )

    return list(deduped.values())


def extract_pdf_years(html: str) -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    select_tag = soup.select_one("select#selectYear")
    if select_tag is None:
        return []

    years: list[int] = []
    for option in select_tag.select("option"):
        value = option.get("value")
        if value and value.isdigit():
            years.append(int(value))

    return sorted(years, reverse=True)


def build_graduation_pdf_targets(
    years: list[int],
    base_url: str,
    graduation_path: str,
    year_limit: int,
) -> list[CrawlTarget]:
    prefix = graduation_path.rstrip("/")
    return [
        CrawlTarget(
            url=f"{base_url}{prefix}/pdfdownload/{year}",
            menu_path=f"졸업학점 {year}",
            source_type="pdf",
            title_hint=f"졸업학점 {year}",
            year=year,
        )
        for year in years[:year_limit]
    ]


def is_redirect_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    title_text = soup.title.get_text(strip=True) if soup.title else ""
    return title_text == "Page Moved"


async def discover_html_targets(fetcher: Callable[[str], str] = fetch_html) -> list[CrawlTarget]:
    main_url = urljoin(settings.crawl_target_url, settings.crawl_main_path)
    html = fetcher(main_url)
    return extract_menu_targets(html=html, base_url=settings.crawl_target_url)


async def discover_pdf_targets(fetcher: Callable[[str], str] = fetch_html) -> list[CrawlTarget]:
    html = fetcher(urljoin(settings.crawl_target_url, settings.crawl_graduation_path))
    years = extract_pdf_years(html)
    return build_graduation_pdf_targets(
        years=years,
        base_url=settings.crawl_target_url,
        graduation_path=settings.crawl_graduation_path,
        year_limit=settings.crawl_pdf_year_limit,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd worker && uv run pytest tests/tasks/test_crawl.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add worker/tasks/crawl.py worker/tests/fixtures/menu_main.html worker/tests/fixtures/page_moved.html worker/tests/tasks/test_crawl.py
git commit -m "feat(worker): add crawl target discovery"
```

### Task 3: HTML Parsing And Chunk Normalization

**Files:**
- Modify: `worker/tasks/parse.py`
- Create: `worker/tests/fixtures/article_page.html`
- Create: `worker/tests/fixtures/article_page_with_table.html`
- Test: `worker/tests/tasks/test_parse_html.py`

- [ ] **Step 1: Write the failing tests**

```python
# worker/tests/tasks/test_parse_html.py
from datetime import UTC, datetime

import pytest

from tasks.contracts import CrawlTarget
from tasks.parse import parse_html


@pytest.mark.asyncio
async def test_parse_html_creates_text_chunks(monkeypatch, fixture_text):
    async def fake_markdown_renderer(article_html: str) -> str:
        return "# 장학 안내\n\n장학금 신청 절차를 안내합니다."

    target = CrawlTarget(
        url="https://www.honam.ac.kr/Scholarship/list",
        menu_path="장학",
        source_type="html",
    )

    document = await parse_html(
        target=target,
        html=fixture_text("article_page.html"),
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        markdown_renderer=fake_markdown_renderer,
    )

    assert document.source_type == "html"
    assert document.content_hash
    assert [chunk.chunk_type for chunk in document.chunks] == ["text"]
    assert "장학금 신청 절차" in document.chunks[0].content


@pytest.mark.asyncio
async def test_parse_html_creates_table_chunks(monkeypatch, fixture_text):
    async def fake_markdown_renderer(article_html: str) -> str:
        return "# 장학 기준\n\n대상과 금액은 아래 표를 참고하세요."

    target = CrawlTarget(
        url="https://www.honam.ac.kr/Scholarship/table",
        menu_path="장학",
        source_type="html",
    )

    document = await parse_html(
        target=target,
        html=fixture_text("article_page_with_table.html"),
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        markdown_renderer=fake_markdown_renderer,
    )

    assert [chunk.chunk_type for chunk in document.chunks] == ["text", "table"]
    assert document.chunks[1].meta["headers"] == ["구분", "금액"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker && uv run pytest tests/tasks/test_parse_html.py -v`  
Expected: FAIL with `TypeError` or missing keyword arguments in `parse_html`

- [ ] **Step 3: Write minimal implementation**

```html
<!-- worker/tests/fixtures/article_page.html -->
<html>
  <body>
    <article class="articleBox">
      <h3>장학 안내</h3>
      <p>장학금 신청 절차를 안내합니다.</p>
    </article>
  </body>
</html>
```

```html
<!-- worker/tests/fixtures/article_page_with_table.html -->
<html>
  <body>
    <article class="articleBox">
      <h3>장학 기준</h3>
      <p>대상과 금액은 아래 표를 참고하세요.</p>
      <table>
        <tr><th>구분</th><th>금액</th></tr>
        <tr><td>성적장학</td><td>100만원</td></tr>
      </table>
    </article>
  </body>
</html>
```

```python
# worker/tasks/parse.py
"""HTML and PDF parsing helpers for Phase 2 ingestion."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from core.config import settings
from tasks.contracts import CrawlTarget, ParsedChunk, ParsedDocument

MarkdownRenderer = Callable[[str], Awaitable[str]]


def build_content_hash(raw_content: str | bytes) -> str:
    payload = raw_content if isinstance(raw_content, bytes) else raw_content.encode("utf-8")
    return hashlib.md5(payload).hexdigest()


def extract_article_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(settings.crawl_content_selector)
    if article is None:
        raise ValueError(f"{settings.crawl_content_selector} not found")
    return str(article)


async def render_markdown_from_article(article_html: str) -> str:
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
    async with AsyncWebCrawler(base_directory=settings.crawl4ai_base_directory) as crawler:
        result = await crawler.arun(url=f"raw:{article_html}", config=config)
    markdown = result.markdown.fit_markdown or result.markdown.raw_markdown
    return markdown.strip()


def markdown_to_text_chunks(markdown: str) -> list[ParsedChunk]:
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "header_1"),
            ("##", "header_2"),
            ("###", "header_3"),
            ("####", "header_4"),
        ],
        strip_headers=False,
    )
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        add_start_index=True,
    )
    split_docs = text_splitter.split_documents(header_splitter.split_text(markdown))
    return [
        ParsedChunk(
            chunk_index=index,
            content=doc.page_content,
            chunk_type="text",
            meta=dict(doc.metadata),
        )
        for index, doc in enumerate(split_docs)
    ]


def extract_html_table_chunks(article_html: str, start_index: int) -> list[ParsedChunk]:
    soup = BeautifulSoup(article_html, "html.parser")
    table_chunks: list[ParsedChunk] = []

    for offset, table in enumerate(soup.select("table")):
        rows = [
            [cell.get_text(" ", strip=True) for cell in row.select("th, td")]
            for row in table.select("tr")
        ]
        if not rows:
            continue
        headers = rows[0]
        body = rows[1:]
        content_lines = [" | ".join(headers)] + [" | ".join(row) for row in body]
        table_chunks.append(
            ParsedChunk(
                chunk_index=start_index + offset,
                content="\n".join(content_lines),
                chunk_type="table",
                meta={"headers": headers, "rows": body},
            )
        )

    return table_chunks


async def parse_html(
    target: CrawlTarget,
    html: str,
    crawled_at: datetime | None = None,
    markdown_renderer: MarkdownRenderer = render_markdown_from_article,
) -> ParsedDocument:
    article_html = extract_article_html(html)
    markdown = await markdown_renderer(article_html)
    text_chunks = markdown_to_text_chunks(markdown)
    table_chunks = extract_html_table_chunks(article_html, start_index=len(text_chunks))
    return ParsedDocument(
        url=target.url,
        title=target.title_hint,
        menu_path=target.menu_path,
        category=None,
        source_type="html",
        content_hash=build_content_hash(article_html),
        crawled_at=crawled_at or datetime.now(UTC),
        chunks=text_chunks + table_chunks,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd worker && uv run pytest tests/tasks/test_parse_html.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add worker/tasks/parse.py worker/tests/fixtures/article_page.html worker/tests/fixtures/article_page_with_table.html worker/tests/tasks/test_parse_html.py
git commit -m "feat(worker): add html parsing pipeline"
```

### Task 4: PDF Parsing And Markdown Table Extraction

**Files:**
- Modify: `worker/tasks/parse.py`
- Test: `worker/tests/tasks/test_parse_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
# worker/tests/tasks/test_parse_pdf.py
from datetime import UTC, datetime

import pytest
from langchain_core.documents import Document

from tasks.contracts import CrawlTarget
from tasks.parse import parse_pdf


@pytest.mark.asyncio
async def test_parse_pdf_creates_text_and_table_chunks(monkeypatch):
    def fake_loader(pdf_path: str) -> list[Document]:
        return [
            Document(
                page_content="# 졸업학점\n\n총 졸업학점은 130학점입니다.\n\n|구분|학점|\n|---|---|\n|총계|130|",
                metadata={"page": 1},
            )
        ]

    target = CrawlTarget(
        url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2024",
        menu_path="졸업학점 2024",
        source_type="pdf",
        year=2024,
    )

    document = await parse_pdf(
        target=target,
        pdf_bytes=b"%PDF-1.4 sample",
        file_loader=fake_loader,
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    assert document.source_type == "pdf"
    assert document.content_hash
    assert [chunk.chunk_type for chunk in document.chunks] == ["text", "table"]
    assert document.chunks[1].meta["page"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd worker && uv run pytest tests/tasks/test_parse_pdf.py -v`  
Expected: FAIL with missing `parse_pdf` keyword arguments or incorrect return shape

- [ ] **Step 3: Write minimal implementation**

```python
# worker/tasks/parse.py
import tempfile
from pathlib import Path

from langchain_core.documents import Document
from langchain_opendataloader_pdf import OpenDataLoaderPDFLoader


def load_pdf_markdown_documents(pdf_path: str) -> list[Document]:
    loader = OpenDataLoaderPDFLoader(
        file_path=pdf_path,
        format="markdown",
        quiet=True,
        hybrid=settings.pdf_hybrid_backend,
        hybrid_mode=settings.pdf_hybrid_mode,
        hybrid_url=settings.pdf_hybrid_url,
        hybrid_fallback=True,
    )
    return loader.load()


def split_markdown_table_blocks(markdown: str) -> tuple[str, list[str]]:
    table_blocks: list[str] = []
    text_lines: list[str] = []
    current_table: list[str] = []

    for line in markdown.splitlines():
        if line.strip().startswith("|") and line.strip().endswith("|"):
            current_table.append(line.rstrip())
            continue
        if current_table:
            table_blocks.append("\n".join(current_table))
            current_table = []
        text_lines.append(line)

    if current_table:
        table_blocks.append("\n".join(current_table))

    return "\n".join(text_lines).strip(), table_blocks


async def parse_pdf(
    target: CrawlTarget,
    pdf_bytes: bytes,
    crawled_at: datetime | None = None,
    file_loader: Callable[[str], list[Document]] = load_pdf_markdown_documents,
) -> ParsedDocument:
    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / f"{target.year or 'document'}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        documents = file_loader(str(pdf_path))

    text_chunks: list[ParsedChunk] = []
    table_chunks: list[ParsedChunk] = []
    chunk_index = 0

    for doc in documents:
        text_markdown, table_blocks = split_markdown_table_blocks(doc.page_content)
        for chunk in markdown_to_text_chunks(text_markdown):
            text_chunks.append(
                ParsedChunk(
                    chunk_index=chunk_index,
                    content=chunk.content,
                    chunk_type="text",
                    meta={"page": doc.metadata.get("page"), **chunk.meta},
                )
            )
            chunk_index += 1

        for table_block in table_blocks:
            table_chunks.append(
                ParsedChunk(
                    chunk_index=chunk_index,
                    content=table_block,
                    chunk_type="table",
                    meta={"page": doc.metadata.get("page")},
                )
            )
            chunk_index += 1

    return ParsedDocument(
        url=target.url,
        title=target.title_hint,
        menu_path=target.menu_path,
        category=None,
        source_type="pdf",
        content_hash=build_content_hash(pdf_bytes),
        crawled_at=crawled_at or datetime.now(UTC),
        chunks=text_chunks + table_chunks,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd worker && uv run pytest tests/tasks/test_parse_pdf.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add worker/tasks/parse.py worker/tests/tasks/test_parse_pdf.py
git commit -m "feat(worker): add pdf parsing pipeline"
```

### Task 5: Persistence Layer And Schema Migration

**Files:**
- Create: `worker/core/db.py`
- Create: `worker/tasks/storage.py`
- Create: `backend/alembic/versions/20260419_01_create_ingestion_tables.py`
- Test: `worker/tests/tasks/test_storage.py`

- [ ] **Step 1: Write the failing tests**

```python
# worker/tests/tasks/test_storage.py
from datetime import UTC, datetime

from tasks.contracts import ParsedChunk, ParsedDocument
from tasks.storage import build_chunk_rows, diff_documents_by_hash


def test_diff_documents_by_hash_splits_changed_and_unchanged():
    unchanged = ParsedDocument(
        url="https://example.com/a",
        title="A",
        menu_path="입학",
        category=None,
        source_type="html",
        content_hash="same",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        chunks=[],
    )
    changed = ParsedDocument(
        url="https://example.com/b",
        title="B",
        menu_path="장학",
        category=None,
        source_type="html",
        content_hash="new-hash",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        chunks=[],
    )

    changed_docs, unchanged_docs = diff_documents_by_hash(
        documents=[unchanged, changed],
        existing_hashes={
            "https://example.com/a": "same",
            "https://example.com/b": "old-hash",
        },
    )

    assert [document.url for document in changed_docs] == ["https://example.com/b"]
    assert [document.url for document in unchanged_docs] == ["https://example.com/a"]


def test_build_chunk_rows_preserves_order():
    document = ParsedDocument(
        url="https://example.com",
        title="Example",
        menu_path="입학",
        category=None,
        source_type="html",
        content_hash="hash",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        chunks=[
            ParsedChunk(chunk_index=0, content="first", chunk_type="text", meta={}),
            ParsedChunk(chunk_index=1, content="second", chunk_type="table", meta={"page": 1}),
        ],
    )

    rows = build_chunk_rows(document_id="document-1", document=document)

    assert rows[0]["chunk_index"] == 0
    assert rows[1]["chunk_type"] == "table"
    assert rows[1]["meta"]["page"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker && uv run pytest tests/tasks/test_storage.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'tasks.storage'`

- [ ] **Step 3: Write minimal implementation**

```python
# worker/core/db.py
import asyncpg

from core.config import settings


def normalize_asyncpg_dsn(database_url: str) -> str:
    return database_url.replace("+asyncpg", "")


async def create_pool(database_url: str | None = None) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=normalize_asyncpg_dsn(database_url or settings.database_url))
```

```python
# worker/tasks/storage.py
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import uuid

import asyncpg

from tasks.contracts import ParsedDocument


def diff_documents_by_hash(
    documents: Sequence[ParsedDocument],
    existing_hashes: dict[str, str],
) -> tuple[list[ParsedDocument], list[ParsedDocument]]:
    changed: list[ParsedDocument] = []
    unchanged: list[ParsedDocument] = []
    for document in documents:
        if existing_hashes.get(document.url) == document.content_hash:
            unchanged.append(document)
        else:
            changed.append(document)
    return changed, unchanged


def build_chunk_rows(document_id: str, document: ParsedDocument) -> list[dict]:
    return [
        {
            "document_id": document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "chunk_type": chunk.chunk_type,
            "meta": chunk.meta,
        }
        for chunk in document.chunks
    ]


async def create_crawl_job(connection: asyncpg.Connection) -> str:
    crawl_job_id = str(uuid.uuid4())
    await connection.execute(
        """
        INSERT INTO crawl_jobs (id, status, pages_crawled, pages_changed, conflicts_found, started_at)
        VALUES ($1, 'running', 0, 0, 0, $2)
        """,
        crawl_job_id,
        datetime.now(UTC),
    )
    return crawl_job_id


async def load_existing_hashes(connection: asyncpg.Connection, urls: Sequence[str]) -> dict[str, str]:
    if not urls:
        return {}
    rows = await connection.fetch(
        "SELECT url, content_hash FROM documents WHERE url = ANY($1::text[])",
        list(urls),
    )
    return {row["url"]: row["content_hash"] for row in rows}


async def upsert_document(connection: asyncpg.Connection, document: ParsedDocument) -> str:
    return await connection.fetchval(
        """
        INSERT INTO documents (id, url, title, menu_path, category, source_type, content_hash, crawled_at, is_active)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE)
        ON CONFLICT (url) DO UPDATE SET
            title = EXCLUDED.title,
            menu_path = EXCLUDED.menu_path,
            category = EXCLUDED.category,
            source_type = EXCLUDED.source_type,
            content_hash = EXCLUDED.content_hash,
            crawled_at = EXCLUDED.crawled_at,
            is_active = TRUE
        RETURNING id
        """,
        str(uuid.uuid4()),
        document.url,
        document.title,
        document.menu_path,
        document.category,
        document.source_type,
        document.content_hash,
        document.crawled_at,
    )


async def replace_document_chunks(connection: asyncpg.Connection, document_id: str, document: ParsedDocument) -> None:
    await connection.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
    rows = build_chunk_rows(document_id=document_id, document=document)
    if not rows:
        return
    await connection.executemany(
        """
        INSERT INTO document_chunks (id, document_id, chunk_index, content, chunk_type, meta, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        [
            (
                str(uuid.uuid4()),
                row["document_id"],
                row["chunk_index"],
                row["content"],
                row["chunk_type"],
                row["meta"],
                datetime.now(UTC),
            )
            for row in rows
        ],
    )


async def finish_crawl_job(
    connection: asyncpg.Connection,
    crawl_job_id: str,
    *,
    status: str,
    pages_crawled: int,
    pages_changed: int,
    error: str | None,
) -> None:
    await connection.execute(
        """
        UPDATE crawl_jobs
        SET status = $2,
            pages_crawled = $3,
            pages_changed = $4,
            completed_at = $5,
            error = $6
        WHERE id = $1
        """,
        crawl_job_id,
        status,
        pages_crawled,
        pages_changed,
        datetime.now(UTC),
        error,
    )
```

```python
# backend/alembic/versions/20260419_01_create_ingestion_tables.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260419_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("menu_path", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_type", sa.Text(), nullable=False),
        sa.Column("chroma_id", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("pages_crawled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages_changed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflicts_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "conflict_pairs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("chunk_a_id", sa.UUID(), nullable=False),
        sa.Column("chunk_b_id", sa.UUID(), nullable=False),
        sa.Column("conflict_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=False, server_default="warning"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["chunk_a_id"], ["document_chunks.id"]),
        sa.ForeignKeyConstraint(["chunk_b_id"], ["document_chunks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "query_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("has_conflict", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("query_logs")
    op.drop_table("conflict_pairs")
    op.drop_table("crawl_jobs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
```

- [ ] **Step 4: Run tests and schema verification**

Run: `cd worker && uv run pytest tests/tasks/test_storage.py -v`  
Expected: PASS

Run: `cd backend && uv run alembic upgrade head`  
Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> 20260419_01`

- [ ] **Step 5: Commit**

```bash
git add worker/core/db.py worker/tasks/storage.py worker/tests/tasks/test_storage.py backend/alembic/versions/20260419_01_create_ingestion_tables.py
git commit -m "feat(worker): add persistence layer for crawled documents"
```

### Task 6: Orchestrate Crawl Jobs And Scheduler Integration

**Files:**
- Modify: `worker/tasks/crawl.py`
- Modify: `worker/tasks/scheduler.py`
- Test: `worker/tests/tasks/test_scheduler.py`

- [ ] **Step 1: Write the failing tests**

```python
# worker/tests/tasks/test_scheduler.py
from datetime import UTC, datetime

import pytest

from tasks.contracts import CrawlStats
from tasks.crawl import run_crawl
from tasks.scheduler import build_cron_trigger


def test_build_cron_trigger_maps_five_part_expression():
    trigger = build_cron_trigger("0 3 * * *")
    assert "hour='3'" in str(trigger)
    assert "minute='0'" in str(trigger)


@pytest.mark.asyncio
async def test_run_crawl_returns_counts(monkeypatch):
    async def fake_discover_html_targets():
        return []

    async def fake_discover_pdf_targets():
        return []

    async def fake_execute_ingestion(html_targets, pdf_targets):
        return CrawlStats(pages_crawled=3, pages_changed=2, failures=[])

    monkeypatch.setattr("tasks.crawl.discover_html_targets", fake_discover_html_targets)
    monkeypatch.setattr("tasks.crawl.discover_pdf_targets", fake_discover_pdf_targets)
    monkeypatch.setattr("tasks.crawl.execute_ingestion", fake_execute_ingestion)

    stats = await run_crawl()

    assert stats.pages_crawled == 3
    assert stats.pages_changed == 2
    assert stats.failures == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker && uv run pytest tests/tasks/test_scheduler.py -v`  
Expected: FAIL because `run_crawl` still logs a stub and returns `None`

- [ ] **Step 3: Write minimal implementation**

```python
# worker/tasks/crawl.py
import logging

from core.db import create_pool
from tasks.contracts import CrawlStats, ParsedDocument
from tasks.parse import parse_html, parse_pdf
from tasks.storage import (
    create_crawl_job,
    finish_crawl_job,
    load_existing_hashes,
    replace_document_chunks,
    upsert_document,
)

logger = logging.getLogger(__name__)


async def execute_ingestion(
    html_targets: list[CrawlTarget],
    pdf_targets: list[CrawlTarget],
) -> CrawlStats:
    stats = CrawlStats()
    pool = await create_pool()

    async with pool.acquire() as connection:
        crawl_job_id = await create_crawl_job(connection)

        try:
            html_urls = [target.url for target in html_targets]
            pdf_urls = [target.url for target in pdf_targets]
            existing_hashes = await load_existing_hashes(connection, html_urls + pdf_urls)

            for target in html_targets:
                html = fetch_html(target.url)
                document = await parse_html(target=target, html=html)
                stats.pages_crawled += 1
                if existing_hashes.get(document.url) != document.content_hash:
                    stats.pages_changed += 1
                    document_id = await upsert_document(connection, document)
                    await replace_document_chunks(connection, document_id, document)

            for target in pdf_targets:
                response = requests.get(
                    url=target.url,
                    timeout=settings.crawl_timeout_seconds,
                    impersonate=settings.crawl_impersonate,
                )
                response.raise_for_status()
                document = await parse_pdf(target=target, pdf_bytes=response.content)
                stats.pages_crawled += 1
                if existing_hashes.get(document.url) != document.content_hash:
                    stats.pages_changed += 1
                    document_id = await upsert_document(connection, document)
                    await replace_document_chunks(connection, document_id, document)

            await finish_crawl_job(
                connection,
                crawl_job_id,
                status="completed",
                pages_crawled=stats.pages_crawled,
                pages_changed=stats.pages_changed,
                error=None,
            )
        except Exception as exc:
            stats.failures.append(str(exc))
            await finish_crawl_job(
                connection,
                crawl_job_id,
                status="failed",
                pages_crawled=stats.pages_crawled,
                pages_changed=stats.pages_changed,
                error=str(exc),
            )
            raise

    await pool.close()
    return stats


async def run_crawl() -> CrawlStats:
    logger.info("Phase 2 crawl started")
    html_targets = await discover_html_targets()
    pdf_targets = await discover_pdf_targets()
    stats = await execute_ingestion(html_targets=html_targets, pdf_targets=pdf_targets)
    logger.info(
        "Phase 2 crawl finished: crawled=%s changed=%s failures=%s",
        stats.pages_crawled,
        stats.pages_changed,
        len(stats.failures),
    )
    return stats
```

```python
# worker/tasks/scheduler.py
async def main() -> None:
    scheduler = AsyncIOScheduler()
    cron_expr = os.getenv("CRAWL_SCHEDULE", "0 3 * * *")

    scheduler.add_job(
        run_crawl,
        build_cron_trigger(cron_expr),
        id="crawl_job",
        max_instances=1,
        misfire_grace_time=600,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler started. Waiting for jobs...")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd worker && uv run pytest tests/tasks/test_scheduler.py -v`  
Expected: PASS

Run: `cd worker && uv run pytest tests/tasks -v`  
Expected: PASS for `test_config.py`, `test_crawl.py`, `test_parse_html.py`, `test_parse_pdf.py`, `test_storage.py`, `test_scheduler.py`

- [ ] **Step 5: Commit**

```bash
git add worker/tasks/crawl.py worker/tasks/scheduler.py worker/tests/tasks/test_scheduler.py
git commit -m "feat(worker): wire crawl orchestration into scheduler"
```

### Task 7: End-To-End Smoke Verification And Doc Sync

**Files:**
- Modify: `docs/superpowers/plans/2026-04-08-phase-roadmap.md`

- [ ] **Step 1: Run the worker test suite**

Run: `cd worker && uv run pytest tests/tasks -v`  
Expected: all task-level tests PASS

- [ ] **Step 2: Run migration and compose config verification**

Run: `cd backend && uv run alembic upgrade head`  
Expected: latest revision applied without error

Run: `docker compose config --services`  
Expected: `postgres`, `chromadb`, `redis`, `backend`, `worker`, `frontend`

- [ ] **Step 3: Update roadmap document status**

```markdown
### Phase 2. 수집 + 파싱 파이프라인

- 문서 상태: spec + implementation plan 작성됨
- 관련 문서:
  - [2026-04-19-phase-2-crawling-parsing-design.md](../specs/2026-04-19-phase-2-crawling-parsing-design.md)
  - [2026-04-19-phase-2-crawling-parsing-implementation.md](2026-04-19-phase-2-crawling-parsing-implementation.md)
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-04-08-phase-roadmap.md
git commit -m "docs(phase-2): mark implementation plan ready"
```

---

## 구현 순서 요약

1. 설정과 공용 타입을 먼저 고정한다.
2. 메뉴/연도 대상 수집을 구현한다.
3. HTML 파싱과 청킹을 구현한다.
4. PDF 파싱과 표 분리를 구현한다.
5. PostgreSQL 적재와 마이그레이션을 구현한다.
6. `run_crawl` 오케스트레이션과 스케줄 연결을 마무리한다.
7. 전체 테스트와 문서 상태를 검증한다.
