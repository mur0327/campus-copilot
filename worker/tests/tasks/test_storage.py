import json
import os
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from core.db import normalize_asyncpg_dsn
from tasks import storage
from tasks.contracts import ParsedChunk, ParsedDocument
from tasks.storage import build_chunk_rows


def test_build_chunk_rows_preserves_order():
    document = ParsedDocument(
        url="https://example.com",
        title="Example",
        menu_path="입학",
        category=None,
        source_scope="unknown",
        page_kind="unknown",
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
async def test_update_crawl_job_progress_writes_stage_and_counts():
    executed: list[tuple[str, tuple]] = []

    class Connection:
        async def execute(self, query, *args):
            executed.append((query, args))

    await storage.update_crawl_job_progress(
        Connection(),
        "job-1",
        current_stage="문서 수집 중",
        total_pages=50,
        processed_pages=12,
        pages_crawled=10,
        pages_changed=3,
    )

    assert len(executed) == 1
    query, args = executed[0]
    assert "current_stage = $2" in query
    assert "total_pages = $3" in query
    assert "processed_pages = $4" in query
    assert args == ("job-1", "문서 수집 중", 50, 12, 10, 3)


@pytest.mark.asyncio
async def test_replace_document_chunks_serializes_meta_for_asyncpg():
    document = ParsedDocument(
        url="https://example.com",
        title="Example",
        menu_path="입학",
        category=None,
        source_scope="unknown",
        page_kind="unknown",
        source_type="html",
        content_hash="hash",
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
        chunks=[
            ParsedChunk(
                chunk_index=0,
                content="first",
                chunk_type="text",
                meta={"start_index": 0, "header_1": "안내"},
            )
        ],
    )
    executed: list[tuple[str, object]] = []
    inserted_args: list[tuple] = []

    class Connection:
        async def execute(self, query, *args):
            executed.append((query, args))

        async def executemany(self, query, args):
            inserted_args.extend(args)

    await storage.replace_document_chunks(Connection(), "document-1", document)

    assert len(executed) == 2
    assert "DELETE FROM conflict_pairs" in executed[0][0]
    assert "DELETE FROM document_chunks" in executed[1][0]
    assert len(inserted_args) == 1
    assert isinstance(inserted_args[0][5], str)
    assert json.loads(inserted_args[0][5]) == {"start_index": 0, "header_1": "안내"}


@pytest.mark.asyncio
async def test_persist_document_wraps_upsert_and_replace_in_one_transaction(monkeypatch):
    document = ParsedDocument(
        url="https://example.com",
        title="Example",
        menu_path="입학",
        category=None,
        source_scope="unknown",
        page_kind="unknown",
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


@pytest.mark.skipif(
    os.getenv("RUN_DB_STORAGE") != "1",
    reason="storage DB regression is opt-in; set RUN_DB_STORAGE=1",
)
@pytest.mark.asyncio
async def test_asyncpg_jsonb_requires_serialized_meta():
    connection = await asyncpg.connect(
        normalize_asyncpg_dsn(os.environ["DATABASE_URL"]),
        timeout=5,
    )
    try:
        await connection.execute(
            """
            CREATE TEMP TABLE document_chunks_jsonb_probe (
                id uuid,
                document_id uuid,
                chunk_index integer,
                content text,
                chunk_type text,
                meta jsonb,
                created_at timestamptz
            )
            """
        )

        with pytest.raises(asyncpg.DataError):
            await connection.execute(
                """
                INSERT INTO document_chunks_jsonb_probe (
                    id, document_id, chunk_index, content, chunk_type, meta, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                uuid.uuid4(),
                uuid.uuid4(),
                0,
                "content",
                "text",
                {"header_1": "안내", "start_index": 0},
                datetime.now(UTC),
            )

        await connection.execute(
            """
            INSERT INTO document_chunks_jsonb_probe (
                id, document_id, chunk_index, content, chunk_type, meta, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            uuid.uuid4(),
            uuid.uuid4(),
            0,
            "content",
            "text",
            json.dumps({"header_1": "안내", "start_index": 0}, ensure_ascii=False),
            datetime.now(UTC),
        )
        stored = await connection.fetchval(
            "SELECT meta->>'header_1' FROM document_chunks_jsonb_probe"
        )

        assert stored == "안내"
    finally:
        await connection.close()
