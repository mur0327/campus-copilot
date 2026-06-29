from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot"
)

import pytest  # noqa: E402

import tasks.crawl as crawl  # noqa: E402
import tasks.pipeline as pipeline  # noqa: E402
from tasks import target_artifact  # noqa: E402
from tasks.contracts import CrawlDiscoveryResult, CrawlStats, CrawlTarget  # noqa: E402


def _target(url: str, source_type: str = "html") -> CrawlTarget:
    return CrawlTarget(
        url=url,
        menu_path="학사",
        source_type=source_type,
        source_scope="general_academic",
        page_kind="academic",
    )


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
async def test_full_run_discovers_and_ingests_in_network_mode(monkeypatch, tmp_path):
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

    artifact = tmp_path / "targets.json"
    monkeypatch.setattr(crawl, "discover_html_targets_with_failures", fake_html)
    monkeypatch.setattr(crawl, "discover_pdf_targets", fake_pdf)
    monkeypatch.setattr(crawl, "execute_ingestion", fake_exec)
    monkeypatch.setattr(pipeline.settings, "crawl_target_limit", 0)
    monkeypatch.setattr(pipeline.settings, "crawl_target_artifact_path", str(artifact))

    await pipeline.run_pipeline()

    assert recorded["process"] is True
    assert recorded["index"] is True
    assert recorded["force"] is False
    assert recorded["failures"] == ["boom"]
    # full 크롤은 캐시 모드를 건드리지 않는다(네트워크 그대로).
    assert recorded["fetch_cache_mode"] is None
    # 검증된 타깃(html+pdf)이 artifact로 저장돼 이후 재파싱이 재사용한다.
    saved = {target.url for target in target_artifact.read_targets(artifact)}
    assert saved == {"https://h", "https://p.pdf"}


@pytest.mark.asyncio
async def test_reparse_reads_artifact_and_uses_cache_first(monkeypatch, tmp_path):
    recorded: dict[str, object] = {}

    async def fail_discover(progress_callback=None):
        raise AssertionError("reparse must not run network discovery")

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

    # DISCOVER가 저장했을 artifact를 미리 만들어 둔다(html 2 + pdf 1).
    artifact = tmp_path / "targets.json"
    target_artifact.write_targets(
        artifact,
        [_target("https://h"), _target("https://h2"), _target("https://p.pdf", "pdf")],
    )

    monkeypatch.setattr(crawl, "discover_html_targets_with_failures", fail_discover)
    monkeypatch.setattr(crawl, "execute_ingestion", fake_exec)
    monkeypatch.setattr(pipeline.settings, "crawl_target_artifact_path", str(artifact))

    await pipeline.run_pipeline(start=pipeline.Phase.PARSE)

    # artifact를 source_type으로 갈라 html/pdf 모두 재파싱 대상에 들어간다.
    assert recorded["html"] == 2
    assert recorded["pdf"] == 1
    assert recorded["process"] is True
    assert recorded["index"] is True
    # 재파싱은 캐시 우선으로 읽되, 강제는 명시 --force일 때만(여기선 force 없음).
    assert recorded["fetch_cache_mode"] == "cache_first"
    assert recorded["force"] is False


@pytest.mark.asyncio
async def test_skipped_full_run_does_not_overwrite_artifact(monkeypatch, tmp_path):
    # 기존 artifact를 미리 둔다.
    artifact = tmp_path / "targets.json"
    target_artifact.write_targets(artifact, [_target("https://kept")])

    async def fake_html(progress_callback=None):
        return CrawlDiscoveryResult(targets=[_target("https://new")], failures=[])

    async def fake_pdf(progress_callback=None):
        return []

    async def fake_exec(*args, **kwargs):
        # 잠금 경합 등으로 ingestion이 스킵된 경우.
        return CrawlStats(skipped=True)

    monkeypatch.setattr(crawl, "discover_html_targets_with_failures", fake_html)
    monkeypatch.setattr(crawl, "discover_pdf_targets", fake_pdf)
    monkeypatch.setattr(crawl, "execute_ingestion", fake_exec)
    monkeypatch.setattr(pipeline.settings, "crawl_target_limit", 0)
    monkeypatch.setattr(pipeline.settings, "crawl_target_artifact_path", str(artifact))

    await pipeline.run_pipeline()

    # 스킵된 크롤은 남의 스냅샷을 덮어쓰지 않는다.
    kept = {target.url for target in target_artifact.read_targets(artifact)}
    assert kept == {"https://kept"}


@pytest.mark.asyncio
async def test_reparse_without_artifact_raises(monkeypatch, tmp_path):
    async def fail_exec(*args, **kwargs):
        raise AssertionError("reparse must not ingest without an artifact")

    monkeypatch.setattr(crawl, "execute_ingestion", fail_exec)
    monkeypatch.setattr(
        pipeline.settings, "crawl_target_artifact_path", str(tmp_path / "missing.json")
    )

    with pytest.raises(ValueError, match="no target artifact"):
        await pipeline.run_pipeline(start=pipeline.Phase.PARSE)


@pytest.mark.asyncio
async def test_index_only_skips_document_processing_and_target_loading(monkeypatch, tmp_path):
    recorded: dict[str, object] = {}

    def fail_read(path):
        raise AssertionError("index-only must not read the target artifact")

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

    # 아티팩트 경로가 설정돼 있어도 index-only는 읽지 않아야 한다.
    monkeypatch.setattr(pipeline.settings, "crawl_target_artifact_path", str(tmp_path / "t.json"))
    monkeypatch.setattr(target_artifact, "read_targets", fail_read)
    monkeypatch.setattr(crawl, "execute_ingestion", fake_exec)

    await pipeline.run_pipeline(start=pipeline.Phase.INDEX)

    assert recorded["process"] is False
    assert recorded["index"] is True
    # 색인만 돌릴 땐 대상이 없어야 한다(불필요한 적재 방지).
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
