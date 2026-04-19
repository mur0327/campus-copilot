"""Parsing task stubs for HTML and PDF sources."""

import logging

logger = logging.getLogger(__name__)


async def parse_html(url: str, html: str) -> list[dict]:
    """Convert an HTML page into chunk dictionaries."""
    logger.info("parse_html stub: %s", url)
    return []


async def parse_pdf(url: str, content: bytes) -> list[dict]:
    """Convert a PDF file into chunk dictionaries."""
    logger.info("parse_pdf stub: %s", url)
    return []
