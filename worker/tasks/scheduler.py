"""APScheduler entrypoint for the worker container."""

import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from tasks.crawl import run_crawl

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
    logger.info("Scheduler started. Waiting for jobs...")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
