from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import asyncpg

from tasks.contracts import ParsedDocument


def diff_documents_by_hash(
    documents: Sequence[ParsedDocument],
    existing_hashes: dict[str, str],
) -> tuple[list[ParsedDocument], list[ParsedDocument]]:
    changed: list[ParsedDocument] = []
    unchanged: list[ParsedDocument] = []
    for document in documents:
        if existing_hashes.get(document.url) == document.content_hash:
            unchanged.append(document)
        else:
            changed.append(document)
    return changed, unchanged


def build_chunk_rows(document_id: str, document: ParsedDocument) -> list[dict]:
    return [
        {
            "document_id": document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "chunk_type": chunk.chunk_type,
            "meta": chunk.meta,
        }
        for chunk in document.chunks
    ]


async def create_crawl_job(connection: asyncpg.Connection) -> str:
    crawl_job_id = str(uuid.uuid4())
    await connection.execute(
        """
        INSERT INTO crawl_jobs (
            id, status, pages_crawled, pages_changed, conflicts_found, started_at
        )
        VALUES ($1, 'running', 0, 0, 0, $2)
        """,
        crawl_job_id,
        datetime.now(UTC),
    )
    return crawl_job_id


async def load_existing_hashes(
    connection: asyncpg.Connection,
    urls: Sequence[str],
) -> dict[str, str]:
    if not urls:
        return {}
    rows = await connection.fetch(
        "SELECT url, content_hash FROM documents WHERE url = ANY($1::text[])",
        list(urls),
    )
    return {row["url"]: row["content_hash"] for row in rows}


async def upsert_document(connection: asyncpg.Connection, document: ParsedDocument) -> str:
    return await connection.fetchval(
        """
        INSERT INTO documents (
            id, url, title, menu_path, category, source_type, content_hash, crawled_at, is_active
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE)
        ON CONFLICT (url) DO UPDATE SET
            title = EXCLUDED.title,
            menu_path = EXCLUDED.menu_path,
            category = EXCLUDED.category,
            source_type = EXCLUDED.source_type,
            content_hash = EXCLUDED.content_hash,
            crawled_at = EXCLUDED.crawled_at,
            is_active = TRUE
        RETURNING id
        """,
        str(uuid.uuid4()),
        document.url,
        document.title,
        document.menu_path,
        document.category,
        document.source_type,
        document.content_hash,
        document.crawled_at,
    )


async def replace_document_chunks(
    connection: asyncpg.Connection,
    document_id: str,
    document: ParsedDocument,
) -> None:
    await connection.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
    rows = build_chunk_rows(document_id=document_id, document=document)
    if not rows:
        return
    await connection.executemany(
        """
        INSERT INTO document_chunks (
            id, document_id, chunk_index, content, chunk_type, meta, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        [
            (
                str(uuid.uuid4()),
                row["document_id"],
                row["chunk_index"],
                row["content"],
                row["chunk_type"],
                row["meta"],
                datetime.now(UTC),
            )
            for row in rows
        ],
    )


async def persist_document(connection: asyncpg.Connection, document: ParsedDocument) -> str:
    async with connection.transaction():
        document_id = await upsert_document(connection, document)
        await replace_document_chunks(connection, document_id, document)
        return document_id


async def finish_crawl_job(
    connection: asyncpg.Connection,
    crawl_job_id: str,
    *,
    status: str,
    pages_crawled: int,
    pages_changed: int,
    error: str | None,
) -> None:
    await connection.execute(
        """
        UPDATE crawl_jobs
        SET status = $2,
            pages_crawled = $3,
            pages_changed = $4,
            completed_at = $5,
            error = $6
        WHERE id = $1
        """,
        crawl_job_id,
        status,
        pages_crawled,
        pages_changed,
        datetime.now(UTC),
        error,
    )
