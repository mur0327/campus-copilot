import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from tasks import scheduler as scheduler_module
from tasks.contracts import CrawlStats, CrawlTarget, ParsedDocument
from tasks.crawl import execute_ingestion, run_crawl
from tasks.scheduler import build_cron_trigger


def test_build_cron_trigger_maps_five_part_expression():
    trigger = build_cron_trigger("0 3 * * *")
    assert "hour='3'" in str(trigger)
    assert "minute='0'" in str(trigger)


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
    assert recorded["kwargs"]["coalesce"] is True


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

    async def fake_load_existing_hashes(connection, urls):
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

    async def fake_fetch_document(target):
        if target.url.endswith("/bad"):
            raise RuntimeError("boom")
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
    monkeypatch.setattr("tasks.crawl.load_existing_hashes", fake_load_existing_hashes)
    monkeypatch.setattr("tasks.crawl.persist_document", fake_persist_document)
    monkeypatch.setattr("tasks.crawl.finish_crawl_job", fake_finish_crawl_job)
    monkeypatch.setattr("tasks.crawl._fetch_document", fake_fetch_document)

    stats = await execute_ingestion(targets, [])

    assert stats.pages_crawled == 1
    assert stats.pages_changed == 1
    assert stats.failures == ["https://example.com/bad: boom"]
    assert recorded["finished"]["status"] == "completed"
