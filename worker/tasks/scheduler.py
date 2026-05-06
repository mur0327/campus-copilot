"""APScheduler entrypoint for the worker container."""

import asyncio
import contextlib
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import settings
from tasks.crawl import run_crawl
from tasks.trigger import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_cron_trigger(cron_expr: str) -> CronTrigger:
    minute, hour, day, month, day_of_week = cron_expr.split()
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )


async def start_trigger_server() -> None:
    import uvicorn

    config = uvicorn.Config(
        create_app(),
        host=settings.trigger_host,
        port=settings.trigger_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    scheduler = AsyncIOScheduler()
    cron_expr = os.getenv("CRAWL_SCHEDULE", "0 3 * * *")

    scheduler.add_job(
        run_crawl,
        build_cron_trigger(cron_expr),
        id="crawl_job",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=600,
    )
    scheduler.start()
    trigger_server_task = asyncio.create_task(start_trigger_server())
    logger.info(
        "Scheduler started. Trigger server listening on %s:%s.",
        settings.trigger_host,
        settings.trigger_port,
    )

    try:
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            pass
    finally:
        scheduler.shutdown()
        trigger_server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await trigger_server_task


if __name__ == "__main__":
    asyncio.run(main())
