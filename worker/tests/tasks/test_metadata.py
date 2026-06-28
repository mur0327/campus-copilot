import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from tasks import metadata
from tasks.bm25 import BM25BuildSummary


def test_classify_document_metadata_prefers_seed_scope_and_uses_menu_path():
    source_scope, page_kind = metadata.classify_document_metadata(
        url="https://graduate.honam.ac.kr/AcademicCalendar",
        menu_path="학사일정",
        seed_source_scope_by_host={"graduate.honam.ac.kr": "admission"},
    )

    assert source_scope == "admission"
    assert page_kind == "schedule"


def test_clear_bm25_cache_files_removes_only_bm25_pickles(tmp_path):
    stale_cache = tmp_path / "bm25-stale.pkl"
    unrelated = tmp_path / "note.txt"
    stale_cache.write_bytes(b"old")
    unrelated.write_text("keep", encoding="utf-8")

    removed = metadata.clear_bm25_cache_files(tmp_path)

    assert removed == 1
    assert not stale_cache.exists()
    assert unrelated.exists()


@pytest.mark.asyncio
async def test_plan_document_metadata_updates_returns_changed_rows_only():
    class FakeConnection:
        async def fetch(self, query, include_inactive):
            assert include_inactive is False
            return [
                {
                    "id": "doc-1",
                    "url": "https://www.honam.ac.kr/ProofIssuanceGuide",
                    "menu_path": "증명서 발급",
                    "source_scope": "unknown",
                    "page_kind": "unknown",
                },
                {
                    "id": "doc-2",
                    "url": "https://enter.honam.ac.kr/transPDF",
                    "menu_path": "편입학 모집요강",
                    "source_scope": "admission",
                    "page_kind": "admission",
                },
            ]

    seen, updates = await metadata.plan_document_metadata_updates(
        FakeConnection(),
        include_inactive=False,
        seed_source_scope_by_host={
            "www.honam.ac.kr": "general_academic",
            "enter.honam.ac.kr": "admission",
        },
    )

    assert seen == 2
    assert len(updates) == 1
    assert updates[0].document_id == "doc-1"
    assert updates[0].new_source_scope == "general_academic"
    assert updates[0].new_page_kind == "certificate"


@pytest.mark.asyncio
async def test_update_document_metadata_writes_only_planned_updates():
    executed = []
    updates = [
        metadata.DocumentMetadataUpdate(
            document_id="doc-1",
            old_source_scope="unknown",
            new_source_scope="general_academic",
            old_page_kind="unknown",
            new_page_kind="certificate",
        )
    ]

    class FakeConnection:
        async def executemany(self, query, args):
            executed.append((query, args))

    await metadata.update_document_metadata(FakeConnection(), updates)

    assert len(executed) == 1
    query, args = executed[0]
    assert "UPDATE documents" in query
    assert args == [("doc-1", "general_academic", "certificate")]


@pytest.mark.asyncio
async def test_refresh_search_metadata_dry_run_does_not_write():
    class FakeConnection:
        def __init__(self):
            self.executed = []

        async def fetch(self, query, include_inactive):
            return [
                {
                    "id": "doc-1",
                    "url": "https://www.honam.ac.kr/ProofIssuanceGuide",
                    "menu_path": "증명서 발급",
                    "source_scope": "unknown",
                    "page_kind": "unknown",
                }
            ]

        async def executemany(self, query, args):
            self.executed.append((query, args))

    connection = FakeConnection()

    summary = await metadata.refresh_search_metadata(connection, dry_run=True)

    assert summary.documents_seen == 1
    assert summary.documents_changed == 1
    assert summary.chroma_skipped is True
    assert summary.bm25_skipped is True
    assert connection.executed == []


@pytest.mark.asyncio
async def test_refresh_chroma_metadata_merges_existing_metadata_and_records_missing():
    class FakeConnection:
        async def fetch(self, query):
            return [
                {
                    "chunk_id": "chunk-1",
                    "document_id": "doc-1",
                    "chroma_id": "chunk:chunk-1",
                    "chunk_type": "text",
                    "chunk_index": 0,
                    "url": "https://www.honam.ac.kr/ProofIssuanceGuide",
                    "title": None,
                    "menu_path": "증명서 발급",
                    "category": None,
                    "source_scope": "general_academic",
                    "page_kind": "certificate",
                    "source_type": "html",
                    "crawled_at": datetime(2026, 6, 28, tzinfo=UTC),
                },
                {
                    "chunk_id": "chunk-2",
                    "document_id": "doc-2",
                    "chroma_id": "chunk:chunk-2",
                    "chunk_type": "text",
                    "chunk_index": 0,
                    "url": "https://enter.honam.ac.kr/transPDF",
                    "title": None,
                    "menu_path": "편입학",
                    "category": None,
                    "source_scope": "admission",
                    "page_kind": "admission",
                    "source_type": "html",
                    "crawled_at": None,
                },
            ]

    class FakeCollection:
        def __init__(self):
            self.updates = []

        def get(self, ids, include):
            assert include == ["metadatas"]
            return {
                "ids": ["chunk:chunk-1"],
                "metadatas": [{"keep": "value", "source_scope": "unknown"}],
            }

        def update(self, ids, metadatas):
            self.updates.append((ids, metadatas))

    collection = FakeCollection()

    summary = await metadata.refresh_chroma_metadata(
        FakeConnection(),
        collection,
        batch_size=10,
    )

    assert summary.chunks_seen == 2
    assert summary.chunks_updated == 1
    assert summary.chunks_missing == 1
    assert summary.missing_ids == ["chunk:chunk-2"]
    assert collection.updates[0][0] == ["chunk:chunk-1"]
    assert collection.updates[0][1][0]["keep"] == "value"
    assert collection.updates[0][1][0]["source_scope"] == "general_academic"
    assert collection.updates[0][1][0]["page_kind"] == "certificate"


@pytest.mark.asyncio
async def test_refresh_search_metadata_can_skip_bm25(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.executed = []

        async def fetch(self, query, *args):
            if "FROM documents" in query:
                return [
                    {
                        "id": "doc-1",
                        "url": "https://enter.honam.ac.kr/transPDF",
                        "menu_path": "편입학 모집요강",
                        "source_scope": "unknown",
                        "page_kind": "unknown",
                    }
                ]
            return []

        async def executemany(self, query, args):
            self.executed.append((query, args))

    async def fail_write_bm25_indexes(connection, cache_dir):
        raise AssertionError("BM25 should be skipped")

    monkeypatch.setattr(metadata, "write_bm25_indexes", fail_write_bm25_indexes)
    connection = FakeConnection()

    summary = await metadata.refresh_search_metadata(
        connection,
        skip_chroma=True,
        skip_bm25=True,
    )

    assert summary.documents_changed == 1
    assert summary.chroma_skipped is True
    assert summary.bm25_skipped is True
    assert connection.executed[0][1] == [("doc-1", "admission", "admission")]


@pytest.mark.asyncio
async def test_refresh_search_metadata_rewrites_bm25(monkeypatch, tmp_path):
    class FakeConnection:
        async def fetch(self, query, *args):
            if "FROM documents" in query:
                return []
            return []

        async def executemany(self, query, args):
            raise AssertionError("no document updates expected")

    called = {}

    async def fake_write_bm25_indexes(connection, cache_dir):
        called["cache_dir"] = cache_dir
        return BM25BuildSummary(chunks_seen=3, indexes_written=1)

    monkeypatch.setattr(metadata, "write_bm25_indexes", fake_write_bm25_indexes)
    stale_cache = tmp_path / "bm25-stale.pkl"
    stale_cache.write_bytes(b"old")

    summary = await metadata.refresh_search_metadata(
        FakeConnection(),
        skip_chroma=True,
        bm25_cache_dir=tmp_path,
    )

    assert summary.bm25 is not None
    assert summary.bm25.chunks_seen == 3
    assert summary.bm25.indexes_written == 1
    assert called["cache_dir"] == tmp_path
    assert not stale_cache.exists()
