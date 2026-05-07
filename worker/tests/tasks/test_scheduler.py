import asyncio
import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from tasks import scheduler as scheduler_module
from tasks.contracts import (
    CrawlDiscoveryResult,
    CrawlStats,
    CrawlTarget,
    DocumentProcessingStatus,
    ParsedDocument,
)
from tasks.crawl import execute_ingestion, run_crawl, should_skip_existing_document
from tasks.scheduler import build_cron_trigger
from tasks.storage import ExistingDocumentState


@pytest.fixture(autouse=True)
def no_op_crawl_indexing(monkeypatch):
    async def fake_index_crawl_documents(connection):
        return None

    monkeypatch.setattr("tasks.crawl.index_crawl_documents", fake_index_crawl_documents)


def test_build_cron_trigger_maps_five_part_expression():
    trigger = build_cron_trigger("0 3 * * *")
    assert "hour='3'" in str(trigger)
    assert "minute='0'" in str(trigger)


def test_should_skip_existing_document_requires_same_hash_and_existing_chunks():
    assert should_skip_existing_document(None, "hash") is False
    assert (
        should_skip_existing_document(
            ExistingDocumentState(content_hash="hash", chunk_count=0),
            "hash",
        )
        is False
    )
    assert (
        should_skip_existing_document(
            ExistingDocumentState(content_hash="old-hash", chunk_count=1),
            "hash",
        )
        is False
    )
    assert (
        should_skip_existing_document(
            ExistingDocumentState(content_hash="hash", chunk_count=1),
            "hash",
        )
        is True
    )


def test_target_metadata_changes_document_hash():
    from tasks.parse import build_content_hash

    raw_content = '<article class="articleBox"><p>same</p></article>'
    first_target = CrawlTarget(
        url="https://www.honam.ac.kr/Same",
        menu_path="공지",
        source_type="html",
        site_name="호남대학교",
    )
    second_target = CrawlTarget(
        url="https://www.honam.ac.kr/Same",
        menu_path="공지 > 세부",
        source_type="html",
        site_name="호남대학교",
    )

    assert build_content_hash(raw_content, target=first_target) != build_content_hash(
        raw_content,
        target=second_target,
    )


@pytest.mark.asyncio
async def test_main_sets_coalesce_for_crawl_job(monkeypatch):
    recorded: dict[str, object] = {}

    class FakeScheduler:
        def add_job(self, func, trigger, **kwargs):
            recorded["func"] = func
            recorded["trigger"] = trigger
            recorded["kwargs"] = kwargs

        def start(self):
            recorded["started"] = True

        def shutdown(self):
            recorded["shutdown"] = True

    class FakeEvent:
        async def wait(self):
            return None

    monkeypatch.setattr(scheduler_module, "AsyncIOScheduler", FakeScheduler)
    monkeypatch.setattr(scheduler_module.asyncio, "Event", lambda: FakeEvent())
    monkeypatch.setenv("CRAWL_SCHEDULE", "0 3 * * *")

    await scheduler_module.main()

    assert recorded["started"] is True
    assert recorded["func"].__name__ == "run_scheduled"
    assert recorded["kwargs"]["coalesce"] is True


@pytest.mark.asyncio
async def test_run_crawl_returns_counts(monkeypatch):
    async def fake_discover_html_targets_with_failures(progress_callback=None):
        return CrawlDiscoveryResult(
            targets=[],
            failures=["https://timeout.honam.ac.kr/main: simulated timeout"],
        )

    async def fake_discover_pdf_targets(progress_callback=None):
        return []

    async def fake_execute_ingestion(html_targets, pdf_targets, initial_failures=None):
        assert initial_failures == ["https://timeout.honam.ac.kr/main: simulated timeout"]
        return CrawlStats(
            pages_crawled=3,
            pages_changed=2,
            failures=list(initial_failures or []),
        )

    monkeypatch.setattr(
        "tasks.crawl.discover_html_targets_with_failures",
        fake_discover_html_targets_with_failures,
    )
    monkeypatch.setattr("tasks.crawl.discover_pdf_targets", fake_discover_pdf_targets)
    monkeypatch.setattr("tasks.crawl.execute_ingestion", fake_execute_ingestion)

    stats = await run_crawl()

    assert stats.pages_crawled == 3
    assert stats.pages_changed == 2
    assert stats.failures == ["https://timeout.honam.ac.kr/main: simulated timeout"]


@pytest.mark.asyncio
async def test_execute_ingestion_records_partial_failure_without_failing_job(monkeypatch):
    targets = [
        CrawlTarget(
            url="https://example.com/ok",
            menu_path="OK",
            source_type="html",
        ),
        CrawlTarget(
            url="https://example.com/bad",
            menu_path="BAD",
            source_type="html",
        ),
    ]
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
            recorded["closed"] = True

    async def fake_create_pool():
        return FakePool()

    async def fake_create_crawl_job(connection):
        recorded["created"] = True
        return "job-1"

    async def fake_load_existing_document_states(connection, urls):
        recorded["urls"] = list(urls)
        return {}

    async def fake_persist_document(connection, document):
        recorded.setdefault("documents", []).append(document.url)
        return "document-1"

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
            "crawl_job_id": crawl_job_id,
            "status": status,
            "pages_crawled": pages_crawled,
            "pages_changed": pages_changed,
            "error": error,
        }

    def fake_fetch_html(url):
        if url.endswith("/bad"):
            raise RuntimeError("boom")
        return f'<html><body><article class="articleBox"><p>{url}</p></article></body></html>'

    async def fake_parse_html(target, html, markdown_renderer=None):
        return ParsedDocument(
            url=target.url,
            title="Example",
            menu_path=target.menu_path,
            category=None,
            source_type=target.source_type,
            content_hash="hash-1",
            crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
            chunks=[],
        )

    monkeypatch.setattr("tasks.crawl.create_pool", fake_create_pool)
    monkeypatch.setattr("tasks.crawl.create_crawl_job", fake_create_crawl_job)
    monkeypatch.setattr(
        "tasks.crawl.load_existing_document_states",
        fake_load_existing_document_states,
    )
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)
    monkeypatch.setattr("tasks.crawl.fetch_html", fake_fetch_html)
    monkeypatch.setattr("tasks.crawl.parse_html", fake_parse_html)

    stats = await execute_ingestion(
        targets,
        [],
        initial_failures=["https://timeout.honam.ac.kr/main: simulated timeout"],
    )

    assert stats.pages_crawled == 1
    assert stats.pages_changed == 1
    assert stats.pages_skipped == 0
    assert stats.status_counts == {
        DocumentProcessingStatus.CHANGED: 1,
        DocumentProcessingStatus.FAILED: 1,
    }
    assert stats.failures == [
        "https://timeout.honam.ac.kr/main: simulated timeout",
        "https://example.com/bad: boom",
    ]
    assert recorded["finished"]["status"] == "completed"
    assert recorded["finished"]["error"] == (
        "https://timeout.honam.ac.kr/main: simulated timeout\n"
        "https://example.com/bad: boom"
    )


@pytest.mark.asyncio
async def test_execute_ingestion_repairs_existing_document_with_missing_chunks(monkeypatch):
    target = CrawlTarget(
        url="https://example.com/pdf",
        menu_path="졸업학점 2025",
        source_type="pdf",
    )
    recorded: dict[str, object] = {}

    class ExistingState:
        content_hash = "same-hash"
        chunk_count = 0

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
        assert urls == ["https://example.com/pdf"]
        return {"https://example.com/pdf": ExistingState()}

    async def fake_persist_document(connection, document):
        recorded["persisted"] = document.url
        return "document-1"

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

    def fake_fetch_pdf_bytes(url):
        assert url == target.url
        return b"same-pdf"

    def fake_build_content_hash(raw_content, target=None):
        assert raw_content == b"same-pdf"
        assert target is not None
        return "same-hash"

    async def fake_parse_pdf(target, pdf_bytes):
        assert pdf_bytes == b"same-pdf"
        return ParsedDocument(
            url=target.url,
            title="졸업학점 2025",
            menu_path=target.menu_path,
            category=None,
            source_type=target.source_type,
            content_hash="same-hash",
            crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
            chunks=[],
        )

    monkeypatch.setattr("tasks.crawl.create_pool", fake_create_pool)
    monkeypatch.setattr("tasks.crawl.create_crawl_job", fake_create_crawl_job)
    monkeypatch.setattr(
        "tasks.crawl.load_existing_document_states",
        fake_load_existing_document_states,
    )
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)
    monkeypatch.setattr("tasks.crawl.fetch_pdf_bytes", fake_fetch_pdf_bytes)
    monkeypatch.setattr("tasks.crawl.build_content_hash", fake_build_content_hash)
    monkeypatch.setattr("tasks.crawl.parse_pdf", fake_parse_pdf)

    stats = await execute_ingestion([], [target])

    assert stats.pages_crawled == 1
    assert stats.pages_changed == 1
    assert recorded["persisted"] == "https://example.com/pdf"


@pytest.mark.asyncio
async def test_execute_ingestion_skips_unchanged_html_before_parse(monkeypatch):
    target = CrawlTarget(
        url="https://example.com/unchanged",
        menu_path="공지",
        source_type="html",
    )
    article_html = '<article class="articleBox"><p>same content</p></article>'
    recorded: dict[str, object] = {}

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
            pass

    async def fake_create_pool():
        return FakePool()

    async def fake_create_crawl_job(connection):
        return "job-1"

    async def fake_load_existing_document_states(connection, urls):
        assert urls == ["https://example.com/unchanged"]
        return {"https://example.com/unchanged": ExistingState()}

    def fake_build_content_hash(raw_content, target=None):
        assert raw_content == article_html
        assert target is not None
        return "same-hash"

    def fake_fetch_html(url):
        assert url == target.url
        return f"<html><body>{article_html}</body></html>"

    async def fake_parse_html(*args, **kwargs):
        raise AssertionError("unchanged HTML should skip parse_html")

    async def fake_persist_document(connection, document):
        raise AssertionError("unchanged HTML should not be persisted")

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
    monkeypatch.setattr("tasks.crawl.build_content_hash", fake_build_content_hash)
    monkeypatch.setattr("tasks.crawl.fetch_html", fake_fetch_html)
    monkeypatch.setattr("tasks.crawl.parse_html", fake_parse_html)
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)

    stats = await execute_ingestion([target], [])

    assert stats.pages_crawled == 1
    assert stats.pages_changed == 0
    assert stats.pages_skipped == 1
    assert stats.status_counts == {DocumentProcessingStatus.SKIPPED: 1}
    assert recorded["finished"] == {
        "status": "completed",
        "pages_crawled": 1,
        "pages_changed": 0,
        "error": None,
    }


@pytest.mark.asyncio
async def test_execute_ingestion_processes_changed_html_with_limited_parallelism(monkeypatch):
    targets = [
        CrawlTarget(
            url=f"https://example.com/page-{index}",
            menu_path=f"Page {index}",
            source_type="html",
        )
        for index in range(3)
    ]
    active = 0
    max_active = 0
    persisted: list[str] = []

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
        return f'<html><body><article class="articleBox"><p>{url}</p></article></body></html>'

    async def fake_parse_html(target, html, markdown_renderer=None):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return ParsedDocument(
            url=target.url,
            title="Example",
            menu_path=target.menu_path,
            category=None,
            source_type=target.source_type,
            content_hash=f"hash-{target.url}",
            crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
            chunks=[],
        )

    async def fake_persist_document(connection, document):
        persisted.append(document.url)
        return "document-1"

    async def fake_finish_crawl_job(*args, **kwargs):
        pass

    monkeypatch.setattr("tasks.crawl.settings.crawl_ingestion_concurrency", 2, raising=False)
    monkeypatch.setattr("tasks.crawl.create_pool", fake_create_pool)
    monkeypatch.setattr("tasks.crawl.create_crawl_job", fake_create_crawl_job)
    monkeypatch.setattr(
        "tasks.crawl.load_existing_document_states",
        fake_load_existing_document_states,
    )
    monkeypatch.setattr("tasks.crawl.fetch_html", fake_fetch_html)
    monkeypatch.setattr("tasks.crawl.parse_html", fake_parse_html)
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)

    stats = await execute_ingestion(targets, [])

    assert stats.pages_crawled == 3
    assert stats.pages_changed == 3
    assert stats.pages_skipped == 0
    assert stats.status_counts == {DocumentProcessingStatus.CHANGED: 3}
    assert max_active == 2
    assert persisted == [target.url for target in targets]
