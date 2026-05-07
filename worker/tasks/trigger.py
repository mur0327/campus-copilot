import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import FastAPI

from tasks.crawl import run_crawl

logger = logging.getLogger(__name__)

RunCrawl = Callable[..., Awaitable[object]]


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
        self._total_pages = 0
        self._processed_pages = 0

    async def trigger(self) -> dict[str, str]:
        async with self._lock:
            if self._task is not None and not self._task.done():
                logger.info("manual crawl trigger ignored: already running")
                return {"status": "already_running"}

            self._start_locked()
            self._task = asyncio.create_task(self._run("manual crawl"))
            logger.info("manual crawl trigger accepted")
            return {"status": "triggered"}

    async def run_scheduled(self) -> None:
        async with self._lock:
            if self._task is not None and not self._task.done():
                logger.info("scheduled crawl skipped: already running")
                return

            self._start_locked()
            self._task = asyncio.current_task()

        await self._run("scheduled crawl")

    def _start_locked(self) -> None:
        self._status = "running"
        self._current_stage = "대상 검색 중"
        self._started_at = datetime.now(UTC)
        self._completed_at = None
        self._error = None
        self._total_pages = 0
        self._processed_pages = 0

    async def update_progress(
        self,
        current_stage: str,
        *,
        processed_pages: int | None = None,
        total_pages: int | None = None,
    ) -> None:
        async with self._lock:
            self._current_stage = current_stage
            if processed_pages is not None:
                self._processed_pages = processed_pages
            if total_pages is not None:
                self._total_pages = total_pages
        logger.info(
            "crawl progress: stage=%s processed_pages=%s total_pages=%s",
            current_stage,
            processed_pages,
            total_pages,
        )

    async def status(self) -> dict[str, str | int | None]:
        async with self._lock:
            return {
                "status": self._status,
                "current_stage": self._current_stage,
                "total_pages": self._total_pages,
                "processed_pages": self._processed_pages,
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "completed_at": self._completed_at.isoformat() if self._completed_at else None,
                "error": self._error,
            }

    async def wait_for_idle(self) -> None:
        task = self._task
        if task is not None:
            await task

    async def _run(self, label: str) -> None:
        try:
            logger.info("%s started", label)
            await self.run_crawl(progress_callback=self.update_progress)  # type: ignore[call-arg]
            async with self._lock:
                self._status = "completed"
                self._current_stage = "완료"
                self._processed_pages = self._total_pages
                self._completed_at = datetime.now(UTC)
                self._error = None
            logger.info("%s completed", label)
        except Exception:
            error = f"{label} failed"
            logger.exception("%s failed", label)
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
    async def crawl_status() -> dict[str, str | int | None]:
        return await trigger_service.status()

    @app.get("/internal/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
