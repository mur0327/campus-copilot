import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from core.db import normalize_asyncpg_dsn
from tasks import storage
from tasks.contracts import ParsedChunk, ParsedDocument
from tasks.storage import build_chunk_rows, diff_documents_by_hash


def test_diff_documents_by_hash_splits_changed_and_unchanged():
    unchanged = ParsedDocument(
        url="https://example.com/a",
        title="A",
        menu_path="입학",
        category=None,
        source_type="html",
        content_hash="same",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        chunks=[],
    )
    changed = ParsedDocument(
        url="https://example.com/b",
        title="B",
        menu_path="장학",
        category=None,
        source_type="html",
        content_hash="new-hash",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        chunks=[],
    )

    changed_docs, unchanged_docs = diff_documents_by_hash(
        documents=[unchanged, changed],
        existing_hashes={
            "https://example.com/a": "same",
            "https://example.com/b": "old-hash",
        },
    )

    assert [document.url for document in changed_docs] == ["https://example.com/b"]
    assert [document.url for document in unchanged_docs] == ["https://example.com/a"]


def test_build_chunk_rows_preserves_order():
    document = ParsedDocument(
        url="https://example.com",
        title="Example",
        menu_path="입학",
        category=None,
        source_type="html",
        content_hash="hash",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        chunks=[
            ParsedChunk(chunk_index=0, content="first", chunk_type="text", meta={}),
            ParsedChunk(chunk_index=1, content="second", chunk_type="table", meta={"page": 1}),
        ],
    )

    rows = build_chunk_rows(document_id="document-1", document=document)

    assert rows[0]["chunk_index"] == 0
    assert rows[1]["chunk_type"] == "table"
    assert rows[1]["meta"]["page"] == 1


@pytest.mark.asyncio
async def test_persist_document_wraps_upsert_and_replace_in_one_transaction(monkeypatch):
    document = ParsedDocument(
        url="https://example.com",
        title="Example",
        menu_path="입학",
        category=None,
        source_type="html",
        content_hash="hash",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        chunks=[],
    )
    events: list[str] = []

    class Transaction:
        async def __aenter__(self):
            events.append("transaction-enter")
            return self

        async def __aexit__(self, exc_type, exc, tb):
            events.append("transaction-exit")
            return False

    class Connection:
        def transaction(self):
            events.append("transaction-called")
            return Transaction()

    async def fake_upsert_document(connection, incoming_document):
        events.append("upsert")
        assert incoming_document is document
        return "document-1"

    async def fake_replace_document_chunks(connection, document_id, incoming_document):
        events.append("replace")
        assert document_id == "document-1"
        assert incoming_document is document

    monkeypatch.setattr(storage, "upsert_document", fake_upsert_document)
    monkeypatch.setattr(storage, "replace_document_chunks", fake_replace_document_chunks)

    await storage.persist_document(Connection(), document)

    assert events == [
        "transaction-called",
        "transaction-enter",
        "upsert",
        "replace",
        "transaction-exit",
    ]


def test_normalize_asyncpg_dsn_only_rewrites_scheme():
    dsn = "postgresql+asyncpg://user:pa+asyncpgss@localhost:5432/db?application_name=app+asyncpg"

    assert normalize_asyncpg_dsn(dsn) == (
        "postgresql://user:pa+asyncpgss@localhost:5432/db?application_name=app+asyncpg"
    )
