"""Embedding task stub for ChromaDB indexing."""

import logging

logger = logging.getLogger(__name__)


async def embed_chunks(chunks: list[dict]) -> None:
    """Embed parsed chunks into the vector store."""
    logger.info("embed_chunks stub: %d chunks", len(chunks))
