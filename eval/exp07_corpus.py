"""Create lightweight, non-restorable corpus fingerprints for EXP-07."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg

from eval.exp07_common import canonical_json_hash, sha256_file
from eval.run_questions import content_signature


async def database_fingerprint(dsn: str) -> dict[str, Any]:
    connection = await asyncpg.connect(dsn)
    try:
        rows = await connection.fetch(
            """
            SELECT
                d.id AS document_id,
                d.url,
                d.title,
                d.menu_path,
                d.category,
                d.source_scope,
                d.page_kind,
                d.source_type,
                d.content_hash AS document_content_hash,
                d.search_keywords,
                d.crawled_at,
                d.is_active,
                c.id AS chunk_id,
                c.chunk_index,
                c.content,
                c.chunk_type,
                c.chroma_id,
                c.meta,
                c.created_at
            FROM documents d
            LEFT JOIN document_chunks c ON c.document_id = d.id
            ORDER BY d.id, c.id
            """
        )
    finally:
        await connection.close()

    documents: set[str] = set()
    active_documents: set[str] = set()
    chunk_count = 0
    indexed_chunk_count = 0
    digest_rows: list[dict[str, Any]] = []
    max_crawled_at: str | None = None
    max_chunk_created_at: str | None = None
    for row in rows:
        document_id = str(row["document_id"])
        documents.add(document_id)
        if row["is_active"]:
            active_documents.add(document_id)
        crawled_at = _iso(row["crawled_at"])
        created_at = _iso(row["created_at"])
        if crawled_at and (max_crawled_at is None or crawled_at > max_crawled_at):
            max_crawled_at = crawled_at
        if created_at and (
            max_chunk_created_at is None or created_at > max_chunk_created_at
        ):
            max_chunk_created_at = created_at
        chunk_id = str(row["chunk_id"]) if row["chunk_id"] else None
        if chunk_id:
            chunk_count += 1
        if row["chroma_id"]:
            indexed_chunk_count += 1
        digest_rows.append(
            {
                "document_id": document_id,
                "url": str(row["url"]),
                "title": row["title"],
                "menu_path": row["menu_path"],
                "category": row["category"],
                "source_scope": row["source_scope"],
                "page_kind": row["page_kind"],
                "source_type": row["source_type"],
                "document_content_hash": row["document_content_hash"],
                "search_keywords": row["search_keywords"],
                "crawled_at": crawled_at,
                "is_active": bool(row["is_active"]),
                "chunk_id": chunk_id,
                "chunk_index": row["chunk_index"],
                "chunk_content_hash": content_signature(row["content"])
                if chunk_id
                else None,
                "chunk_type": row["chunk_type"],
                "chroma_id": row["chroma_id"],
                "chunk_meta": row["meta"],
                "chunk_created_at": created_at,
            }
        )
    return {
        "document_count": len(documents),
        "active_document_count": len(active_documents),
        "chunk_count": chunk_count,
        "indexed_chunk_count": indexed_chunk_count,
        "max_crawled_at": max_crawled_at,
        "max_chunk_created_at": max_chunk_created_at,
        "sha256": canonical_json_hash(digest_rows),
    }


def chroma_fingerprint(collection: Any, *, page_size: int = 1000) -> dict[str, Any]:
    expected_count = int(collection.count())
    rows: list[dict[str, Any]] = []
    offset = 0
    while offset < expected_count:
        response = collection.get(limit=page_size, offset=offset, include=["metadatas"])
        ids = list(response.get("ids") or [])
        metadatas = list(response.get("metadatas") or [])
        if not ids:
            break
        for index, item_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else None
            rows.append({"id": str(item_id), "metadata": metadata})
        offset += len(ids)
    rows.sort(key=lambda row: row["id"])
    if len(rows) != expected_count:
        raise ValueError(
            f"Chroma fingerprint count mismatch: expected {expected_count}, got {len(rows)}"
        )
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Chroma fingerprint contains duplicate IDs")
    return {"item_count": len(rows), "sha256": canonical_json_hash(rows)}


def bm25_fingerprint(cache_dir: Path) -> dict[str, Any]:
    files = sorted(path for path in cache_dir.glob("*.pkl") if path.is_file())
    if not files:
        raise FileNotFoundError(f"BM25 cache file is missing: {cache_dir}")
    rows = [
        {
            "name": path.name,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    return {"file_count": len(rows), "files": rows, "sha256": canonical_json_hash(rows)}


async def corpus_fingerprint(
    *, dsn: str, collection: Any, bm25_cache_dir: Path
) -> dict[str, Any]:
    return {
        "schema_version": "exp07-corpus-fingerprint-1",
        "captured_at": datetime.now(UTC).isoformat(),
        "database": await database_fingerprint(dsn),
        "chroma": chroma_fingerprint(collection),
        "bm25": bm25_fingerprint(bm25_cache_dir),
    }


def comparable_fingerprint(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "captured_at"}


def fingerprints_match(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return comparable_fingerprint(before) == comparable_fingerprint(after)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return str(value)
