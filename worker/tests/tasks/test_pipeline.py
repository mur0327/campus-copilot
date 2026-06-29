from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot"
)

import pytest  # noqa: E402

import tasks.crawl as crawl  # noqa: E402
import tasks.pipeline as pipeline  # noqa: E402
from tasks.contracts import CrawlDiscoveryResult, CrawlStats, CrawlTarget  # noqa: E402


def _target(url: str, source_type: str = "html") -> CrawlTarget:
    return CrawlTarget(
        url=url,
        menu_path="학사",
        source_type=source_type,
        source_scope="general_academic",
        page_kind="academic",
    )


class _FakeConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def acquire(self):
        return _FakeConnection()

    async def close(self):
        return None


async def _fake_create_pool():
    return _FakePool()


def test_parse_phase_maps_names_and_rejects_unknown():
    assert pipeline.parse_phase("discover") is pipeline.Phase.DISCOVER
    assert pipeline.parse_phase("PARSE") is pipeline.Phase.PARSE
    with pytest.raises(ValueError):
        pipeline.parse_phase("nope")


@pytest.mark.asyncio
async def test_run_pipeline_rejects_start_after_end():
    with pytest.raises(ValueError):
        await pipeline.run_pipeline(start=pipeline.Phase.INDEX, end=pipeline.Phase.DISCOVER)


@pytest.mark.asyncio
async def test_full_run_discovers_and_ingests_in_network_mode(monkeypatch):
    recorded: dict[str, object] = {}

    async def fake_html(progress_callback=None):
        return CrawlDiscoveryResult(targets=[_target("https://h")], failures=["boom"])

    async def fake_pdf(progress_callback=None):
        return [_target("https://p.pdf", "pdf")]

    async def fake_exec(
        html_targets,
        pdf_targets,
        initial_failures=None,
        *,
        process_documents,
        index_documents,
        force,
        fetch_cache_mode,
    ):
        recorded.update(
            process=process_documents,
            index=index_documents,
            force=force,
            failures=initial_failures,
            fetch_cache_mode=fetch_cache_mode,
        )
        return CrawlStats(pages_crawled=1)

    monkeypatch.setattr(crawl, "discover_html_targets_with_failures", fake_html)
    monkeypatch.setattr(crawl, "discover_pdf_targets", fake_pdf)
    monkeypatch.setattr(crawl, "execute_ingestion", fake_exec)
    monkeypatch.setattr(pipeline.crawl.settings, "crawl_target_limit", 0)

    await pipeline.run_pipeline()

    assert recorded["process"] is True
    assert recorded["index"] is True
    assert recorded["force"] is False
    assert recorded["failures"] == ["boom"]
    # full 크롤은 캐시 모드를 건드리지 않는다(네트워크 그대로).
    assert recorded["fetch_cache_mode"] is None


@pytest.mark.asyncio
async def test_reparse_uses_db_targets_and_cache_first_and_force(monkeypatch):
    recorded: dict[str, object] = {}

    async def fail_discover(progress_callback=None):
        raise AssertionError("reparse must not run network discovery")

    async def fake_load(connection):
        return [_target("https://h"), _target("https://h2")]

    async def fake_exec(
        html_targets,
        pdf_targets,
        initial_failures=None,
        *,
        process_documents,
        index_documents,
        force,
        fetch_cache_mode,
    ):
        recorded.update(
            html=len(html_targets),
            pdf=len(pdf_targets),
            process=process_documents,
            index=index_documents,
            force=force,
            fetch_cache_mode=fetch_cache_mode,
        )
        return CrawlStats()

    monkeypatch.setattr(crawl, "discover_html_targets_with_failures", fail_discover)
    monkeypatch.setattr(pipeline, "create_pool", _fake_create_pool)
    monkeypatch.setattr(pipeline, "load_reparse_html_targets", fake_load)
    monkeypatch.setattr(crawl, "execute_ingestion", fake_exec)

    await pipeline.run_pipeline(start=pipeline.Phase.PARSE)

    assert recorded["html"] == 2
    assert recorded["pdf"] == 0
    assert recorded["process"] is True
    assert recorded["index"] is True
    # 재파싱은 캐시 우선으로 읽되, 강제는 명시 --force일 때만(여기선 force 없음).
    assert recorded["fetch_cache_mode"] == "cache_first"
    assert recorded["force"] is False


@pytest.mark.asyncio
async def test_index_only_skips_document_processing_and_target_loading(monkeypatch):
    recorded: dict[str, object] = {}

    async def fail_load(connection):
        raise AssertionError("index-only must not load reparse targets")

    async def fake_exec(
        html_targets,
        pdf_targets,
        initial_failures=None,
        *,
        process_documents,
        index_documents,
        force,
        fetch_cache_mode,
    ):
        recorded.update(
            process=process_documents,
            index=index_documents,
            html=len(html_targets),
            fetch_cache_mode=fetch_cache_mode,
        )
        return CrawlStats()

    monkeypatch.setattr(pipeline, "load_reparse_html_targets", fail_load)
    monkeypatch.setattr(crawl, "execute_ingestion", fake_exec)

    await pipeline.run_pipeline(start=pipeline.Phase.INDEX)

    assert recorded["process"] is False
    assert recorded["index"] is True
    # 색인만 돌릴 땐 대상이 없어야 한다(불필요한 DB 적재 방지).
    assert recorded["html"] == 0
    assert recorded["fetch_cache_mode"] is None


@pytest.mark.asyncio
async def test_dry_run_reports_targets_without_ingesting(monkeypatch):
    async def fake_html(progress_callback=None):
        return CrawlDiscoveryResult(
            targets=[_target("https://a"), _target("https://b")], failures=[]
        )

    async def fake_pdf(progress_callback=None):
        return [_target("https://c.pdf", "pdf")]

    async def fail_exec(*args, **kwargs):
        raise AssertionError("dry run must not ingest")

    monkeypatch.setattr(crawl, "discover_html_targets_with_failures", fake_html)
    monkeypatch.setattr(crawl, "discover_pdf_targets", fake_pdf)
    monkeypatch.setattr(crawl, "execute_ingestion", fail_exec)
    monkeypatch.setattr(pipeline.crawl.settings, "crawl_target_limit", 0)

    stats = await pipeline.run_pipeline(dry_run=True)

    assert stats.pages_crawled == 3
