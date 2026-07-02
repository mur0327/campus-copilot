"""Refresh document search metadata without refetching source documents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from core.config import settings
from core.types import PageKind, SourceScope
from tasks.bm25 import BM25BuildSummary, write_bm25_indexes
from tasks.classify import infer_page_kind, infer_source_scope
from tasks.embed import create_chroma_collection

logger = logging.getLogger(__name__)

DOCUMENT_METADATA_SQL = """
SELECT id, url, menu_path, source_scope, page_kind
FROM documents
WHERE ($1::boolean OR is_active = TRUE)
ORDER BY crawled_at DESC NULLS LAST, url ASC
"""

UPDATE_DOCUMENT_METADATA_SQL = """
UPDATE documents
SET source_scope = $2,
    page_kind = $3
WHERE id = $1
"""

ACTIVE_INDEXED_CHUNKS_SQL = """
SELECT
    c.id AS chunk_id,
    c.document_id,
    c.chroma_id,
    c.chunk_type,
    c.chunk_index,
    d.url,
    d.title,
    d.menu_path,
    d.category,
    d.source_scope,
    d.page_kind,
    d.source_type,
    d.crawled_at
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.is_active = TRUE
  AND c.content <> ''
  AND c.chroma_id IS NOT NULL
ORDER BY d.crawled_at DESC NULLS LAST, c.created_at ASC
"""


@dataclass(frozen=True, slots=True)
class DocumentMetadataUpdate:
    document_id: str
    old_source_scope: SourceScope
    new_source_scope: SourceScope
    old_page_kind: PageKind
    new_page_kind: PageKind


@dataclass(slots=True)
class ChromaMetadataSummary:
    chunks_seen: int = 0
    chunks_updated: int = 0
    chunks_missing: int = 0
    batches_seen: int = 0
    batches_failed: int = 0
    missing_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MetadataRefreshSummary:
    documents_seen: int = 0
    documents_changed: int = 0
    documents_unchanged: int = 0
    dry_run: bool = False
    chroma_skipped: bool = False
    bm25_skipped: bool = False
    chroma: ChromaMetadataSummary = field(default_factory=ChromaMetadataSummary)
    bm25: BM25BuildSummary | None = None

    @property
    def failed(self) -> bool:
        return bool(self.chroma.errors or self.chroma.missing_ids)


def build_seed_source_scope_by_host() -> dict[str, SourceScope]:
    return {
        urlparse(seed.url).hostname or "": seed.source_scope for seed in settings.crawl_seed_sites
    }


def classify_document_metadata(
    *,
    url: str,
    menu_path: str | None,
    seed_source_scope_by_host: dict[str, SourceScope],
) -> tuple[SourceScope, PageKind]:
    host = urlparse(url).hostname or ""
    source_scope = seed_source_scope_by_host.get(host) or infer_source_scope(url=url)
    page_kind = infer_page_kind(url=url, menu_path=menu_path)
    return source_scope, page_kind


def _coerce_source_scope(value: object) -> SourceScope:
    if value in {"general_academic", "admission", "department", "unknown"}:
        return value  # type: ignore[return-value]
    return "unknown"


def _coerce_page_kind(value: object) -> PageKind:
    if value in {"academic", "admission", "schedule", "certificate", "contact", "unknown"}:
        return value  # type: ignore[return-value]
    return "unknown"


async def plan_document_metadata_updates(
    connection,
    *,
    include_inactive: bool = False,
    seed_source_scope_by_host: dict[str, SourceScope] | None = None,
) -> tuple[int, list[DocumentMetadataUpdate]]:
    seed_map = seed_source_scope_by_host or build_seed_source_scope_by_host()
    rows = await connection.fetch(DOCUMENT_METADATA_SQL, include_inactive)
    updates: list[DocumentMetadataUpdate] = []
    for row in rows:
        new_source_scope, new_page_kind = classify_document_metadata(
            url=row["url"],
            menu_path=row["menu_path"],
            seed_source_scope_by_host=seed_map,
        )
        old_source_scope = _coerce_source_scope(row["source_scope"])
        old_page_kind = _coerce_page_kind(row["page_kind"])
        if old_source_scope == new_source_scope and old_page_kind == new_page_kind:
            continue
        updates.append(
            DocumentMetadataUpdate(
                document_id=str(row["id"]),
                old_source_scope=old_source_scope,
                new_source_scope=new_source_scope,
                old_page_kind=old_page_kind,
                new_page_kind=new_page_kind,
            )
        )
    return len(rows), updates


async def update_document_metadata(connection, updates: list[DocumentMetadataUpdate]) -> None:
    if not updates:
        return
    await connection.executemany(
        UPDATE_DOCUMENT_METADATA_SQL,
        [
            (
                update.document_id,
                update.new_source_scope,
                update.new_page_kind,
            )
            for update in updates
        ],
    )


def build_chroma_metadata(row) -> dict[str, str | int]:
    crawled_at = row["crawled_at"]
    return {
        "chunk_id": str(row["chunk_id"]),
        "document_id": str(row["document_id"]),
        "url": _metadata_text(row["url"]),
        "title": _metadata_text(row["title"]),
        "menu_path": _metadata_text(row["menu_path"]),
        "category": _metadata_text(row["category"]),
        "source_scope": _metadata_text(row["source_scope"]),
        "page_kind": _metadata_text(row["page_kind"]),
        "source_type": _metadata_text(row["source_type"]),
        "chunk_type": _metadata_text(row["chunk_type"]),
        "chunk_index": row["chunk_index"],
        "crawled_at": crawled_at.isoformat() if crawled_at else "",
    }


def _metadata_text(value: object) -> str:
    return "" if value is None else str(value)


def batched(items: list, batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def clear_bm25_cache_files(cache_dir: str | Path) -> int:
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return 0

    removed = 0
    for cache_file in cache_path.glob("bm25-*.pkl"):
        cache_file.unlink()
        removed += 1
    return removed


async def refresh_chroma_metadata(
    connection,
    collection,
    *,
    batch_size: int = 500,
    max_retries: int = 2,
) -> ChromaMetadataSummary:
    rows = await connection.fetch(ACTIVE_INDEXED_CHUNKS_SQL)
    summary = ChromaMetadataSummary(chunks_seen=len(rows))
    rows_by_chroma_id = {row["chroma_id"]: row for row in rows}
    for chunk_batch in batched(rows, batch_size):
        summary.batches_seen += 1
        await _refresh_chroma_metadata_batch(
            collection,
            chunk_batch=chunk_batch,
            rows_by_chroma_id=rows_by_chroma_id,
            summary=summary,
            max_retries=max_retries,
        )
    return summary


async def _refresh_chroma_metadata_batch(
    collection,
    *,
    chunk_batch: list,
    rows_by_chroma_id: dict[str, object],
    summary: ChromaMetadataSummary,
    max_retries: int,
) -> None:
    ids = [row["chroma_id"] for row in chunk_batch]
    for attempt in range(max_retries + 1):
        try:
            existing = collection.get(ids=ids, include=["metadatas"])
            existing_ids = existing.get("ids", [])
            existing_metadatas = existing.get("metadatas", [])
            existing_by_id = {
                chroma_id: dict(metadata or {})
                for chroma_id, metadata in zip(existing_ids, existing_metadatas, strict=False)
            }
            missing_ids = [chroma_id for chroma_id in ids if chroma_id not in existing_by_id]
            update_ids = [chroma_id for chroma_id in ids if chroma_id in existing_by_id]
            update_metadatas = [
                {
                    **existing_by_id[chroma_id],
                    **build_chroma_metadata(rows_by_chroma_id[chroma_id]),
                }
                for chroma_id in update_ids
            ]
            if update_ids:
                collection.update(ids=update_ids, metadatas=update_metadatas)
                summary.chunks_updated += len(update_ids)
            if missing_ids:
                summary.chunks_missing += len(missing_ids)
                summary.missing_ids.extend(missing_ids)
            return
        except Exception as exc:  # pragma: no cover - integration boundary
            if attempt < max_retries:
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            summary.batches_failed += 1
            summary.errors.append(
                f"chroma metadata update failed for batch starting {ids[0]}: {exc}"
            )
            return


async def refresh_search_metadata(
    connection,
    *,
    chroma_collection=None,
    include_inactive: bool = False,
    dry_run: bool = False,
    skip_chroma: bool = False,
    skip_bm25: bool = False,
    batch_size: int = 500,
    max_retries: int = 2,
    bm25_cache_dir: str | Path | None = None,
) -> MetadataRefreshSummary:
    documents_seen, updates = await plan_document_metadata_updates(
        connection,
        include_inactive=include_inactive,
    )
    summary = MetadataRefreshSummary(
        documents_seen=documents_seen,
        documents_changed=len(updates),
        documents_unchanged=documents_seen - len(updates),
        dry_run=dry_run,
        chroma_skipped=skip_chroma or dry_run,
        bm25_skipped=skip_bm25 or dry_run,
    )
    if dry_run:
        return summary

    await update_document_metadata(connection, updates)

    if not skip_chroma:
        collection = chroma_collection or create_chroma_collection(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection_name=settings.chroma_collection,
        )
        summary.chroma = await refresh_chroma_metadata(
            connection,
            collection,
            batch_size=batch_size,
            max_retries=max_retries,
        )

    if not skip_bm25:
        clear_bm25_cache_files(bm25_cache_dir or settings.bm25_cache_dir)
        summary.bm25 = await write_bm25_indexes(
            connection,
            bm25_cache_dir or settings.bm25_cache_dir,
        )

    logger.info(
        "metadata refresh completed: documents_seen=%s documents_changed=%s "
        "chroma_updated=%s chroma_missing=%s bm25_indexes=%s failed=%s",
        summary.documents_seen,
        summary.documents_changed,
        summary.chroma.chunks_updated,
        summary.chroma.chunks_missing,
        summary.bm25.indexes_written if summary.bm25 else 0,
        summary.failed,
    )
    return summary
