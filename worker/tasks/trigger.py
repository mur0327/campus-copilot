import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import FastAPI

from tasks.crawl import run_crawl

logger = logging.getLogger(__name__)

RunCrawl = Callable[[], Awaitable[object]]


class CrawlTriggerService:
    def __init__(self, *, run_crawl: RunCrawl = run_crawl) -> None:
        self.run_crawl = run_crawl
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._status = "idle"
        self._current_stage: str | None = None
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None
        self._error: str | None = None

    async def trigger(self) -> dict[str, str]:
        async with self._lock:
            if self._task is not None and not self._task.done():
                logger.info("manual crawl trigger ignored: already running")
                return {"status": "already_running"}

            self._status = "running"
            self._current_stage = "대상 검색 중"
            self._started_at = datetime.now(UTC)
            self._completed_at = None
            self._error = None
            self._task = asyncio.create_task(self._run())
            logger.info("manual crawl trigger accepted")
            return {"status": "triggered"}

    async def status(self) -> dict[str, str | None]:
        async with self._lock:
            return {
                "status": self._status,
                "current_stage": self._current_stage,
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "completed_at": self._completed_at.isoformat() if self._completed_at else None,
                "error": self._error,
            }

    async def wait_for_idle(self) -> None:
        task = self._task
        if task is not None:
            await task

    async def _run(self) -> None:
        try:
            logger.info("manual crawl started")
            await self.run_crawl()
            async with self._lock:
                self._status = "completed"
                self._current_stage = "완료"
                self._completed_at = datetime.now(UTC)
                self._error = None
            logger.info("manual crawl completed")
        except Exception:
            error = "manual crawl trigger failed"
            logger.exception("manual crawl trigger failed")
            async with self._lock:
                self._status = "failed"
                self._current_stage = "실패"
                self._completed_at = datetime.now(UTC)
                self._error = error
        finally:
            async with self._lock:
                if self._task is asyncio.current_task():
                    self._task = None


def create_app(service: CrawlTriggerService | None = None) -> FastAPI:
    app = FastAPI(title="Campus Copilot Worker Trigger", version="1.0.0")
    trigger_service = service or CrawlTriggerService()

    @app.post("/internal/crawl")
    async def trigger_crawl() -> dict[str, str]:
        return await trigger_service.trigger()

    @app.get("/internal/crawl/status")
    async def crawl_status() -> dict[str, str | None]:
        return await trigger_service.status()

    @app.get("/internal/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
