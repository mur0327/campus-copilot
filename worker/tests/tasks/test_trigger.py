import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from tasks.trigger import CrawlTriggerService, create_app


@pytest.mark.asyncio
async def test_trigger_starts_crawl_in_background():
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_run_crawl(progress_callback=None):
        started.set()
        await release.wait()

    service = CrawlTriggerService(run_crawl=fake_run_crawl)
    app = create_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/internal/crawl")
        await asyncio.wait_for(started.wait(), timeout=1)

    assert response.status_code == 200
    assert response.json() == {"status": "triggered"}
    release.set()
    await service.wait_for_idle()


@pytest.mark.asyncio
async def test_trigger_rejects_duplicate_while_crawl_is_running():
    release = asyncio.Event()

    async def fake_run_crawl(progress_callback=None):
        await release.wait()

    service = CrawlTriggerService(run_crawl=fake_run_crawl)
    app = create_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/internal/crawl")
        second = await client.post("/internal/crawl")

    assert first.status_code == 200
    assert first.json() == {"status": "triggered"}
    assert second.status_code == 200
    assert second.json() == {"status": "already_running"}
    release.set()
    await service.wait_for_idle()


@pytest.mark.asyncio
async def test_status_reports_running_before_crawl_job_exists():
    release = asyncio.Event()
    updated = asyncio.Event()

    async def fake_run_crawl(progress_callback=None):
        if progress_callback is not None:
            await progress_callback("상세 페이지 후보 확인 중", processed_pages=1, total_pages=3)
            updated.set()
        await release.wait()

    service = CrawlTriggerService(run_crawl=fake_run_crawl)
    app = create_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        trigger_response = await client.post("/internal/crawl")
        await asyncio.wait_for(updated.wait(), timeout=1)
        status_response = await client.get("/internal/crawl/status")

    assert trigger_response.json() == {"status": "triggered"}
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "running"
    assert status_response.json()["current_stage"] == "상세 페이지 후보 확인 중"
    assert status_response.json()["processed_pages"] == 1
    assert status_response.json()["total_pages"] == 3
    assert status_response.json()["started_at"] is not None
    assert status_response.json()["completed_at"] is None
    assert status_response.json()["error"] is None
    release.set()
    await service.wait_for_idle()


@pytest.mark.asyncio
async def test_scheduled_crawl_updates_shared_status():
    release = asyncio.Event()
    updated = asyncio.Event()

    async def fake_run_crawl(progress_callback=None):
        if progress_callback is not None:
            await progress_callback("예약 수집 중", processed_pages=2, total_pages=5)
            updated.set()
        await release.wait()

    service = CrawlTriggerService(run_crawl=fake_run_crawl)
    task = asyncio.create_task(service.run_scheduled())
    await asyncio.wait_for(updated.wait(), timeout=1)

    status = await service.status()

    assert status["status"] == "running"
    assert status["current_stage"] == "예약 수집 중"
    assert status["processed_pages"] == 2
    assert status["total_pages"] == 5

    release.set()
    await task


@pytest.mark.asyncio
async def test_trigger_allows_new_crawl_after_previous_finishes():
    calls = 0

    async def fake_run_crawl(progress_callback=None):
        nonlocal calls
        calls += 1

    service = CrawlTriggerService(run_crawl=fake_run_crawl)
    app = create_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/internal/crawl")
        await service.wait_for_idle()
        second = await client.post("/internal/crawl")
        await service.wait_for_idle()

    assert first.json() == {"status": "triggered"}
    assert second.json() == {"status": "triggered"}
    assert calls == 2
