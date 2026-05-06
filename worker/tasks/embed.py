"""Embedding and ChromaDB indexing helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ACTIVE_CHROMA_IDS_SQL = """
SELECT c.chroma_id
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.is_active = TRUE
  AND c.chroma_id IS NOT NULL
"""

PENDING_CHUNKS_SQL = """
SELECT
    c.id,
    c.document_id,
    c.content,
    c.chunk_type,
    c.chunk_index,
    d.url,
    d.title,
    d.menu_path,
    d.category,
    d.source_type,
    d.crawled_at
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.is_active = TRUE
  AND c.content <> ''
  AND c.chroma_id IS NULL
ORDER BY d.crawled_at DESC NULLS LAST, c.created_at ASC
LIMIT $1
"""


@dataclass(slots=True)
class EmbedSummary:
    chunks_seen: int = 0
    chunks_indexed: int = 0
    chunks_skipped: int = 0
    vectors_pruned: int = 0
    errors: list[str] | None = None


def build_chroma_id(chunk_id: str) -> str:
    return f"chunk:{chunk_id}"


def _metadata_text(value: object) -> str:
    return "" if value is None else str(value)


async def embed_pending_chunks(connection, collection, embedder, batch_size: int) -> EmbedSummary:
    rows = await connection.fetch(PENDING_CHUNKS_SQL, batch_size)
    summary = EmbedSummary(chunks_seen=len(rows), errors=[])
    if not rows:
        return summary

    texts = [row["content"] for row in rows]
    embeddings = embedder.encode(texts)
    ids = [build_chroma_id(str(row["id"])) for row in rows]
    metadatas = [
        {
            "chunk_id": str(row["id"]),
            "document_id": str(row["document_id"]),
            "url": _metadata_text(row["url"]),
            "title": _metadata_text(row["title"]),
            "menu_path": _metadata_text(row["menu_path"]),
            "category": _metadata_text(row["category"]),
            "source_type": _metadata_text(row["source_type"]),
            "chunk_type": _metadata_text(row["chunk_type"]),
            "chunk_index": row["chunk_index"],
            "crawled_at": row["crawled_at"].isoformat() if row["crawled_at"] else "",
        }
        for row in rows
    ]

    collection.upsert(
        ids=ids,
        embeddings=[list(vector) for vector in embeddings],
        documents=texts,
        metadatas=metadatas,
    )

    for chroma_id, row in zip(ids, rows, strict=True):
        await connection.execute(
            "UPDATE document_chunks SET chroma_id = $1 WHERE id = $2",
            chroma_id,
            str(row["id"]),
        )
        summary.chunks_indexed += 1

    return summary


def create_embedder(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def create_chroma_collection(host: str, port: int, collection_name: str):
    import chromadb

    client = chromadb.HttpClient(host=host, port=port)
    return client.get_or_create_collection(name=collection_name, embedding_function=None)


async def prune_orphan_vectors(connection, collection) -> int:
    rows = await connection.fetch(ACTIVE_CHROMA_IDS_SQL)
    active_ids = {row["chroma_id"] for row in rows}
    existing = collection.get(include=[])
    orphan_ids = [
        chroma_id
        for chroma_id in existing.get("ids", [])
        if chroma_id not in active_ids
    ]
    if orphan_ids:
        collection.delete(ids=orphan_ids)
    return len(orphan_ids)


async def embed_chunks(chunks: list[dict]) -> None:
    """Embed parsed chunks into the vector store."""
    logger.info("embed_chunks stub: %d chunks", len(chunks))
