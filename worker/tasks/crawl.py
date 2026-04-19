"""Crawling task stub for Honam University content ingestion."""

import logging

logger = logging.getLogger(__name__)


async def run_crawl() -> None:
    """Crawl Honam University pages and feed the indexing pipeline."""
    logger.info("Crawl started (stub)")
