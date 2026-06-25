import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tasks.bm25 import build_bm25_cache_path, write_bm25_indexes
from tasks.embed import (
    build_chroma_id,
    embed_pending_chunks,
    normalize_embedding,
    prune_orphan_vectors,
)


def test_build_chroma_id_uses_chunk_uuid():
    assert build_chroma_id("abc-123") == "chunk:abc-123"


def test_normalize_embedding_converts_values_to_python_float():
    class FloatLike:
        def __float__(self):
            return 0.25

    embedding = normalize_embedding([FloatLike(), 1])

    assert embedding == [0.25, 1.0]
    assert all(type(value) is float for value in embedding)


@pytest.mark.asyncio
async def test_embed_pending_chunks_updates_chroma_ids():
    class FakeConnection:
        def __init__(self):
            self.updated = []

        async def fetch(self, query, limit):
            return [
                {
                    "id": "chunk-1",
                    "document_id": "doc-1",
                    "content": "휴학 신청 안내",
                    "chunk_type": "text",
                    "chunk_index": 0,
                    "url": "https://www.honam.ac.kr/a",
                    "title": "휴학",
                    "menu_path": "학사 > 휴학",
                    "category": "academic",
                    "source_type": "html",
                    "crawled_at": None,
                }
            ]

        async def execute(self, query, chroma_id, chunk_id):
            self.updated.append((chroma_id, chunk_id))

    @dataclass
    class FakeEmbedder:
        def encode(self, texts):
            return [[0.1, 0.2, 0.3] for _ in texts]

    class FakeCollection:
        def __init__(self):
            self.upserts = []

        def upsert(self, ids, embeddings, documents, metadatas):
            self.upserts.append((ids, embeddings, documents, metadatas))

    connection = FakeConnection()
    collection = FakeCollection()

    summary = await embed_pending_chunks(
        connection=connection,
        collection=collection,
        embedder=FakeEmbedder(),
        batch_size=64,
    )

    assert summary.chunks_seen == 1
    assert summary.chunks_indexed == 1
    assert collection.upserts[0][0] == ["chunk:chunk-1"]
    assert all(type(value) is float for value in collection.upserts[0][1][0])
    assert connection.updated == [("chunk:chunk-1", "chunk-1")]


@pytest.mark.asyncio
async def test_prune_orphan_vectors_deletes_vectors_without_db_chunks():
    class FakeConnection:
        async def fetch(self, query):
            return [{"chroma_id": "chunk:chunk-1"}]

    class FakeCollection:
        def __init__(self):
            self.deleted = []

        def get(self, include=None):
            return {"ids": ["chunk:chunk-1", "chunk:orphan"]}

        def delete(self, ids):
            self.deleted.extend(ids)

    collection = FakeCollection()

    pruned = await prune_orphan_vectors(FakeConnection(), collection)

    assert pruned == 1
    assert collection.deleted == ["chunk:orphan"]


@pytest.mark.asyncio
async def test_write_bm25_indexes_persists_all_and_category_indexes(tmp_path: Path):
    class FakeConnection:
        async def fetchval(self, query):
            return datetime(2026, 5, 1, tzinfo=UTC)

        async def fetch(self, query):
            return [
                {
                    "chunk_id": "00000000-0000-0000-0000-000000000001",
                    "document_id": "00000000-0000-0000-0000-000000000101",
                    "content": "휴학 신청은 포털에서 진행합니다.",
                    "chunk_type": "text",
                    "title": "휴학",
                    "url": "https://www.honam.ac.kr/a",
                    "menu_path": "학사 > 휴학",
                    "category": "academic",
                    "crawled_at": datetime(2026, 5, 1, tzinfo=UTC),
                    "meta": '{"source": "test"}',
                },
                {
                    "chunk_id": "00000000-0000-0000-0000-000000000002",
                    "document_id": "00000000-0000-0000-0000-000000000102",
                    "content": "장학금 신청 안내입니다.",
                    "chunk_type": "text",
                    "title": "장학금",
                    "url": "https://www.honam.ac.kr/b",
                    "menu_path": "장학 > 신청",
                    "category": "scholarship",
                    "crawled_at": datetime(2026, 5, 1, tzinfo=UTC),
                    "meta": None,
                },
            ]

    summary = await write_bm25_indexes(FakeConnection(), tmp_path)

    assert summary.indexes_written == 3
    assert build_bm25_cache_path(tmp_path, None).exists()
    assert build_bm25_cache_path(tmp_path, "academic").exists()
    assert build_bm25_cache_path(tmp_path, "scholarship").exists()

    with build_bm25_cache_path(tmp_path, "academic").open("rb") as cache_file:
        payload = pickle.load(cache_file)

    assert payload["records"][0]["meta"] == {"source": "test"}
