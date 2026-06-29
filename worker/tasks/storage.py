from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import asyncpg

from core.config import settings
from tasks.contracts import CrawlTarget, ParsedDocument

logger = logging.getLogger(__name__)

# 크롤 작업 전체에 대한 전역 잠금 키. 값 자체는 의미가 없고 충돌만 피하면 된다.
# Postgres advisory lock은 세션(연결) 단위라, 프로세스가 죽어 연결이 끊기면
# 자동으로 해제된다(별도 크래시 복구 로직이 필요 없음).
CRAWL_ADVISORY_LOCK_KEY = 0x43505F4352_41574C  # 'CP_CRAWL' 비트 패턴 → 고정 키


@dataclass(slots=True)
class ExistingDocumentState:
    content_hash: str | None
    chunk_count: int


@asynccontextmanager
async def crawl_advisory_lock(connection: asyncpg.Connection) -> AsyncIterator[bool]:
    """크롤 한 회차에 대한 크로스 프로세스 상호배제.

    pg_try_advisory_lock으로 비차단 획득한다. 이미 다른 프로세스(예: 스케줄 크롤과
    별도 phase CLI)가 쥐고 있으면 False를 내고, 그쪽이 끝날 때까지 기다리지 않는다.
    잠금은 같은 연결로 pg_advisory_unlock하거나 연결이 끊기면 자동 해제된다.

    단위 테스트의 가짜 연결처럼 fetchval이 없으면 잠금을 건너뛰고 획득한 것으로 본다.
    """
    try:
        acquired = await connection.fetchval(
            "SELECT pg_try_advisory_lock($1)", CRAWL_ADVISORY_LOCK_KEY
        )
    except AttributeError:
        logger.debug("crawl advisory lock skipped by connection fake")
        yield True
        return
    try:
        yield bool(acquired)
    finally:
        if acquired:
            await connection.fetchval("SELECT pg_advisory_unlock($1)", CRAWL_ADVISORY_LOCK_KEY)


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


async def load_reparse_html_targets(
    connection: asyncpg.Connection,
) -> list[CrawlTarget]:
    """v3 파서 개선을 재반영하기 위한 HTML 재파싱 대상을 복원한다.

    네트워크 discovery 없이 기존 코퍼스를 다시 파싱하려는 용도다. 그런데 discovery
    시점 메타인 site_name/site_url/year는 documents 테이블에 저장되지 않는다. 이 값들은
    content_hash 계산에도 들어가므로(parse.build_content_hash), 충실히 복원하지 못하면
    해시가 어긋나 재파싱 결과가 오염되거나 다음 크롤마다 변경으로 오인된다.

    따라서 **seed 설정에서 host로 충실히 복원 가능한** HTML 페이지만 대상으로 한다:
    - site_name/site_url ← URL host와 일치하는 seed의 name/url (general_academic/admission).
    - year ← HTML에는 없음(None).
    - title_hint ← 저장된 title.
    학과(department) 페이지(seed가 아닌 host)와 PDF는 year/site_name을 복원할 수 없어
    제외한다. 이들의 충실한 재파싱은 discovery 산출물을 저장하는 increment ⑤에서 다룬다.
    """
    rows = await connection.fetch(
        """
        SELECT url, title, menu_path, source_scope, page_kind
        FROM documents
        WHERE is_active = TRUE AND source_type = 'html'
        ORDER BY url
        """
    )
    seed_by_host = {urlparse(seed.url).hostname: seed for seed in settings.crawl_seed_sites}
    targets: list[CrawlTarget] = []
    for row in rows:
        seed = seed_by_host.get(urlparse(row["url"]).hostname)
        if seed is None:
            # seed가 아닌 host(학과 사이트 등)는 site_name/url을 복원할 수 없어 건너뛴다.
            continue
        targets.append(
            CrawlTarget(
                url=row["url"],
                menu_path=row["menu_path"],
                source_type="html",
                source_scope=row["source_scope"],
                page_kind=row["page_kind"],
                title_hint=row["title"],
                site_name=seed.name,
                site_url=seed.url.rstrip("/"),
            )
        )
    return targets


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
