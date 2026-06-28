from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import asyncpg

from tasks.contracts import ParsedDocument


@dataclass(slots=True)
class ExistingDocumentState:
    content_hash: str | None
    chunk_count: int


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
            id, status, pages_crawled, pages_changed, total_pages,
            processed_pages, current_stage, conflicts_found, started_at
        )
        VALUES ($1, 'running', 0, 0, 0, 0, '준비 중', 0, $2)
        """,
        crawl_job_id,
        datetime.now(UTC),
    )
    return crawl_job_id


async def update_crawl_job_progress(
    connection: asyncpg.Connection,
    crawl_job_id: str,
    *,
    current_stage: str,
    total_pages: int,
    processed_pages: int,
    pages_crawled: int,
    pages_changed: int,
) -> None:
    await connection.execute(
        """
        UPDATE crawl_jobs
        SET current_stage = $2,
            total_pages = $3,
            processed_pages = $4,
            pages_crawled = $5,
            pages_changed = $6
        WHERE id = $1
        """,
        crawl_job_id,
        current_stage,
        total_pages,
        processed_pages,
        pages_crawled,
        pages_changed,
    )


async def load_existing_document_states(
    connection: asyncpg.Connection,
    urls: Sequence[str],
) -> dict[str, ExistingDocumentState]:
    if not urls:
        return {}
    rows = await connection.fetch(
        """
        SELECT d.url, d.content_hash, count(c.id)::int AS chunk_count
        FROM documents d
        LEFT JOIN document_chunks c ON c.document_id = d.id
        WHERE d.url = ANY($1::text[])
        GROUP BY d.id
        """,
        list(urls),
    )
    return {
        row["url"]: ExistingDocumentState(
            content_hash=row["content_hash"],
            chunk_count=row["chunk_count"],
        )
        for row in rows
    }


async def upsert_document(connection: asyncpg.Connection, document: ParsedDocument) -> str:
    return await connection.fetchval(
        """
        INSERT INTO documents (
            id, url, title, menu_path, category, source_scope, page_kind, source_type,
            content_hash, crawled_at, is_active
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, TRUE)
        ON CONFLICT (url) DO UPDATE SET
            title = EXCLUDED.title,
            menu_path = EXCLUDED.menu_path,
            category = EXCLUDED.category,
            source_scope = EXCLUDED.source_scope,
            page_kind = EXCLUDED.page_kind,
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
        document.source_scope,
        document.page_kind,
        document.source_type,
        document.content_hash,
        document.crawled_at,
    )


async def invalidate_conflicts_for_document(
    connection: asyncpg.Connection,
    document_id: str,
) -> None:
    await connection.execute(
        """
        DELETE FROM conflict_pairs
        WHERE chunk_a_id IN (
            SELECT id FROM document_chunks WHERE document_id = $1
        )
        OR chunk_b_id IN (
            SELECT id FROM document_chunks WHERE document_id = $1
        )
        """,
        document_id,
    )


async def replace_document_chunks(
    connection: asyncpg.Connection,
    document_id: str,
    document: ParsedDocument,
) -> None:
    await invalidate_conflicts_for_document(connection, document_id)
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
                json.dumps(row["meta"], ensure_ascii=False),
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
            processed_pages = GREATEST(processed_pages, $3),
            current_stage = $5,
            completed_at = $6,
            error = $7
        WHERE id = $1
        """,
        crawl_job_id,
        status,
        pages_crawled,
        pages_changed,
        "완료" if status == "completed" else "실패",
        datetime.now(UTC),
        error,
    )
