import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from tasks.crawl import run_crawl

logger = logging.getLogger(__name__)

RunCrawl = Callable[[], Awaitable[object]]


class CrawlTriggerService:
    def __init__(self, *, run_crawl: RunCrawl = run_crawl) -> None:
        self.run_crawl = run_crawl
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

    async def trigger(self) -> dict[str, str]:
        async with self._lock:
            if self._task is not None and not self._task.done():
                return {"status": "already_running"}

            self._task = asyncio.create_task(self._run())
            return {"status": "triggered"}

    async def wait_for_idle(self) -> None:
        task = self._task
        if task is not None:
            await task

    async def _run(self) -> None:
        try:
            await self.run_crawl()
        except Exception:
            logger.exception("manual crawl trigger failed")
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

    @app.get("/internal/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
