"""Conflict scanning task stub for newly indexed chunks."""

import logging

logger = logging.getLogger(__name__)


async def scan_conflicts() -> None:
    """Scan recent chunks for conflicts."""
    logger.info("scan_conflicts stub")
