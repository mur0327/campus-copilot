from dataclasses import dataclass

import pytest

from tasks.embed import build_chroma_id, embed_pending_chunks, prune_orphan_vectors


def test_build_chroma_id_uses_chunk_uuid():
    assert build_chroma_id("abc-123") == "chunk:abc-123"


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
