# Phase 4 Indexing Search RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 2에서 적재한 공식 문서 청크를 임베딩하고, ChromaDB + BM25 hybrid retrieval과 LLM provider를 통해 실제 `/api/v1/chat` SSE 질의응답을 키오스크 frontend까지 연결한다.

**Architecture:** `worker`는 PostgreSQL `document_chunks`를 ChromaDB와 BM25 파일 인덱스로 배치 인덱싱하고 `chroma_id`를 갱신한다. `backend`는 Chroma semantic search와 worker가 생성한 BM25 파일 인덱스를 읽어 hybrid retrieval을 수행하며, freshness/conflict/query log, LLM provider, RAG orchestration을 service layer로 분리하고 chat route는 SSE event stream만 조립한다. `frontend`는 Phase 3 JSON chat/fallback 중심 연결을 `@microsoft/fetch-event-source` 기반 streaming client로 전환하고, fallback은 개발 전용 flag 뒤로 이동한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, asyncpg, ChromaDB, sentence-transformers, rank-bm25, aiocache Redis, sse-starlette, httpx, google-genai, llama.cpp server, pytest, pytest-asyncio, React 19, TypeScript, Vite, Zustand, React Query, @microsoft/fetch-event-source, vitest.

---

## Source Documents

- `docs/superpowers/specs/2026-05-06-phase-4-indexing-search-rag-design.md`
- `docs/superpowers/plans/2026-04-08-phase-roadmap.md`
- `docs/superpowers/specs/2026-04-08-architecture-design.md`
- `docs/superpowers/specs/2026-04-19-phase-2-crawling-parsing-design.md`
- `docs/superpowers/plans/2026-04-19-phase-2-crawling-parsing-implementation.md`
- `docs/superpowers/specs/2026-05-06-phase-3-kiosk-admin-frontend-design.md`
- `docs/superpowers/plans/2026-04-12-phase-3-kiosk-admin-frontend.md`

## Phase 4 Contract

Phase 4 is not backend-only. It is complete only when:

- active `document_chunks` are embedded into ChromaDB
- `document_chunks.chroma_id` points at real Chroma vector ids
- backend hybrid retrieval returns source metadata
- `/api/v1/chat` streams `metadata`, `token`, `procedure_steps`, `done` events
- generated answers include sources, procedure steps, freshness, and conflict warning
- query logs are stored and visible in `/admin`
- categories, FAQ, and popular questions come from backend
- kiosk works with `VITE_ENABLE_KIOSK_FALLBACK=false`

## Execution Rules

- If a follow-up fix belongs to the same task before moving to the next task, amend the task commit instead of creating a new commit. Use `git commit --amend` after updating the staged files so each task remains one coherent commit.
- Before using a library, SDK, or external API whose behavior matters to the implementation, check the current version and usage with Context7. This applies especially to `chromadb`, `sentence-transformers`, `rank-bm25`, `sse-starlette`, `google-genai`, `llama.cpp`, and `@microsoft/fetch-event-source`.
- If Context7 documentation and existing repository usage disagree, prefer the repository pattern for local integration and note the mismatch before implementing.
- Follow `/home/mur0327/.codex/COMMIT.md` for every commit. Each commit message must include the trailer `Co-Authored-By: Codex <codex@openai.com>`.
- Use this commit command shape in every task:

```bash
git commit -m "type(scope): subject" \
  -m "- concise body line" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

## File Map

```text
backend/
  app/core/config.py                         Modify: Phase 4 env settings
  app/api/routes/chat.py                     Modify: SSE chat route
  app/api/routes/categories.py               Modify: real categories/recent/faq/popular routes
  app/api/routes/admin.py                    Modify: real DB-backed admin routes
  app/schemas/chat.py                        Modify: source freshness/chunk id and SSE payload helpers
  app/schemas/kiosk.py                       Create: category, FAQ, popular response schemas
  app/schemas/admin.py                       Create: admin response schemas
  app/services/chroma_client.py              Create: shared Chroma client wrapper
  app/services/retriever.py                  Create: Chroma + BM25 retriever
  app/services/freshness.py                  Create: freshness calculator
  app/services/conflict.py                   Create: unresolved conflict lookup
  app/services/query_log.py                  Create: query log writer/reader
  app/services/llm.py                        Create: provider protocol + llama.cpp/Gemini providers
  app/services/rag.py                        Create: grounded answer orchestration
  tests/                                     Create: backend Phase 4 tests

worker/
  core/config.py                             Modify: embedding/index settings
  tasks/embed.py                             Modify: real embedding + Chroma indexing
  tasks/storage.py                           Modify: conflict invalidation before chunk replace
  tests/tasks/test_embed.py                  Create
  tests/tasks/test_storage_conflicts.py      Create

frontend/
  package.json                               Modify: add @microsoft/fetch-event-source
  src/api/chat.ts                            Modify: SSE client
  src/api/categories.ts                      Modify: fallback flag policy
  src/api/faq.ts                             Modify: fallback flag policy
  src/api/popular.ts                         Modify: fallback flag policy
  src/hooks/useChat.ts                       Modify: streaming state updates
  src/types/kiosk.ts                         Modify: source freshness/chunk id and SSE event types
  src/hooks/useChat.test.ts                  Modify
  src/api/kioskApi.test.ts                   Modify
```

---

### Task 1: Phase 4 Settings And Shared Types

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Modify: `worker/core/config.py`
- Modify: `.env.example`
- Create: `backend/app/schemas/kiosk.py`
- Create: `backend/app/schemas/admin.py`
- Modify: `backend/app/schemas/chat.py`
- Test: `backend/tests/test_phase4_config.py`
- Test: `worker/tests/tasks/test_config.py`

- [ ] **Step 1: Write backend config tests**

Create `backend/tests/test_phase4_config.py`:

```python
from app.core.config import Settings


def test_phase_four_backend_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

    settings = Settings(_env_file=None)

    assert settings.chroma_collection == "campus_copilot_chunks"
    assert settings.retriever_semantic_top_n == 20
    assert settings.retriever_bm25_top_n == 20
    assert settings.retriever_final_top_k == 6
    assert settings.retriever_semantic_weight == 0.7
    assert settings.retriever_bm25_weight == 0.3
    assert settings.freshness_stale_days == 180
    assert settings.chat_cache_ttl_seconds == 3600


def test_gemini_provider_requires_model_and_key(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "gemini"
    assert settings.gemini_api_key == ""
    assert settings.gemini_model == ""


def test_llama_cpp_provider_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "llama_cpp"
    assert settings.llama_cpp_base_url == "http://localhost:8080"
    assert settings.llama_cpp_model == "local"
```

- [ ] **Step 1.5: Remove unused Ollama backend dependency**

Modify `backend/pyproject.toml` so the LLM dependency block keeps `google-genai` and removes `ollama`. `llama.cpp` is accessed through its HTTP server with existing `httpx`.

```toml
    # LLM
    "google-genai>=1.33.0",
```

- [ ] **Step 2: Extend backend settings**

Add fields to `backend/app/core/config.py`:

```python
    chroma_collection: str = "campus_copilot_chunks"

    retriever_semantic_top_n: int = 20
    retriever_bm25_top_n: int = 20
    retriever_final_top_k: int = 6
    retriever_semantic_weight: float = 0.7
    retriever_bm25_weight: float = 0.3

    freshness_stale_days: int = 180
    chat_cache_ttl_seconds: int = 3600
    llm_provider: str = "llama_cpp"
    llama_cpp_base_url: str = "http://localhost:8080"
    llama_cpp_model: str = "local"
    gemini_model: str = ""
```

- [ ] **Step 3: Extend worker settings test**

Add assertions to `worker/tests/tasks/test_config.py`:

```python
    assert settings.embedding_model == "jhgan/ko-sroberta-multitask"
    assert settings.chroma_collection == "campus_copilot_chunks"
    assert settings.index_batch_size == 64
```

- [ ] **Step 4: Extend worker settings**

Add fields to `worker/core/config.py`:

```python
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "campus_copilot_chunks"
    embedding_model: str = "jhgan/ko-sroberta-multitask"
    index_batch_size: int = 64
```

- [ ] **Step 5: Add API schemas**

Create `backend/app/schemas/kiosk.py`:

```python
from pydantic import BaseModel


class CategoryResponse(BaseModel):
    id: str
    name: str


class FAQResponse(BaseModel):
    id: str
    question: str
    category_id: str
    priority: int = 0
    source_url: str | None = None


class PopularResponse(BaseModel):
    rank: int
    question: str
    view_count: int
```

Create `backend/app/schemas/admin.py`:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AdminStatusResponse(BaseModel):
    documents: int
    chunks: int
    indexed_chunks: int
    last_crawled: datetime | None


class AdminConflictResponse(BaseModel):
    id: UUID
    chunk_a_id: UUID
    chunk_b_id: UUID
    conflict_type: str
    severity: str
    is_resolved: bool
    summary: str | None = None


class AdminLogResponse(BaseModel):
    id: UUID
    query: str
    answer: str | None
    has_conflict: bool
    response_ms: int | None
    created_at: datetime | None
```

- [ ] **Step 6: Extend chat schemas**

Modify `backend/app/schemas/chat.py`:

```python
class Source(BaseModel):
    title: str
    url: str
    crawled_at: str
    freshness: str | None = None
    chunk_id: str | None = None


class ChatMetadataEvent(BaseModel):
    sources: list[Source]
    freshness: str
    conflict_warning: ConflictWarning


class ChatTokenEvent(BaseModel):
    text: str


class ChatProcedureStepsEvent(BaseModel):
    procedure_steps: list[str]
```

- [ ] **Step 7: Update `.env.example`**

Add:

```bash
EMBEDDING_MODEL=jhgan/ko-sroberta-multitask
CHROMA_COLLECTION=campus_copilot_chunks
INDEX_BATCH_SIZE=64
BM25_CACHE_DIR=.data/bm25
CRAWL_MARKDOWN_CONCURRENCY=1
CRAWL_MARKDOWN_TIMEOUT_SECONDS=45
CRAWL_DOCUMENT_TIMEOUT_SECONDS=120
RETRIEVER_SEMANTIC_TOP_N=20
RETRIEVER_BM25_TOP_N=20
RETRIEVER_FINAL_TOP_K=6
RETRIEVER_SEMANTIC_WEIGHT=0.7
RETRIEVER_BM25_WEIGHT=0.3
RETRIEVER_BM25_CACHE_DIR=.data/bm25
FRESHNESS_STALE_DAYS=180
CHAT_CACHE_TTL_SECONDS=3600
LLM_PROVIDER=llama_cpp
LLAMA_CPP_BASE_URL=http://localhost:8080
LLAMA_CPP_MODEL=local
GEMINI_MODEL=
VITE_ENABLE_KIOSK_FALLBACK=false
```

- [ ] **Step 8: Verify**

Run:

```bash
cd backend && uv run pytest tests/test_phase4_config.py -v
cd ../worker && uv run pytest tests/tasks/test_config.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add .env.example backend/pyproject.toml backend/uv.lock backend/app/core/config.py backend/app/schemas backend/tests/test_phase4_config.py worker/core/config.py worker/tests/tasks/test_config.py
git commit -m "feat(rag): add phase four settings and schemas" \
  -m "- add backend and worker phase four configuration" \
  -m "- switch local llm settings to llama.cpp" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 2: Worker Embedding And Chroma Indexing

**Files:**
- Modify: `worker/tasks/embed.py`
- Modify: `worker/tasks/crawl.py`
- Test: `worker/tests/tasks/test_embed.py`
- Test: `worker/tests/tasks/test_crawl.py`

- [ ] **Step 0: Check library docs**

Use Context7 to confirm current usage for `chromadb` collection `upsert`, `get`, and `delete`, and `sentence-transformers` `SentenceTransformer.encode`. Record the checked versions/API notes in the task commit body or implementation notes. If Context7 lacks an entry, use official docs or installed package introspection and note that fallback.

- [ ] **Step 1: Write embedding tests with fakes**

Create `worker/tests/tasks/test_embed.py`:

```python
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
```

- [ ] **Step 2: Implement `EmbedSummary` and helpers**

In `worker/tasks/embed.py`:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class EmbedSummary:
    chunks_seen: int = 0
    chunks_indexed: int = 0
    chunks_skipped: int = 0
    vectors_pruned: int = 0
    errors: list[str] | None = None


def build_chroma_id(chunk_id: str) -> str:
    return f"chunk:{chunk_id}"
```

Add:

```python
ACTIVE_CHROMA_IDS_SQL = """
SELECT c.chroma_id
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.is_active = TRUE
  AND c.chroma_id IS NOT NULL
"""
```

- [ ] **Step 3: Implement pending chunk query**

Add to `worker/tasks/embed.py`:

```python
PENDING_CHUNKS_SQL = """
SELECT
    c.id,
    c.document_id,
    c.content,
    c.chunk_type,
    c.chunk_index,
    d.url,
    d.title,
    d.menu_path,
    d.category,
    d.source_type,
    d.crawled_at
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.is_active = TRUE
  AND c.content <> ''
  AND c.chroma_id IS NULL
ORDER BY d.crawled_at DESC NULLS LAST, c.created_at ASC
LIMIT $1
"""
```

- [ ] **Step 4: Implement `embed_pending_chunks`**

Add:

```python
async def embed_pending_chunks(connection, collection, embedder, batch_size: int) -> EmbedSummary:
    rows = await connection.fetch(PENDING_CHUNKS_SQL, batch_size)
    summary = EmbedSummary(chunks_seen=len(rows), errors=[])
    if not rows:
        return summary

    texts = [row["content"] for row in rows]
    embeddings = embedder.encode(texts)
    ids = [build_chroma_id(str(row["id"])) for row in rows]
    metadatas = [
        {
            "chunk_id": str(row["id"]),
            "document_id": str(row["document_id"]),
            "url": row["url"],
            "title": row["title"] or "",
            "menu_path": row["menu_path"] or "",
            "category": row["category"] or "",
            "source_type": row["source_type"],
            "chunk_type": row["chunk_type"],
            "chunk_index": row["chunk_index"],
            "crawled_at": row["crawled_at"].isoformat() if row["crawled_at"] else "",
        }
        for row in rows
    ]

    collection.upsert(
        ids=ids,
        embeddings=[list(vector) for vector in embeddings],
        documents=texts,
        metadatas=metadatas,
    )

    for chroma_id, row in zip(ids, rows, strict=True):
        await connection.execute(
            "UPDATE document_chunks SET chroma_id = $1 WHERE id = $2",
            chroma_id,
            str(row["id"]),
        )
        summary.chunks_indexed += 1
    return summary
```

- [ ] **Step 5: Add real factory functions**

Add:

```python
def create_embedder(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def create_chroma_collection(host: str, port: int, collection_name: str):
    import chromadb

    client = chromadb.HttpClient(host=host, port=port)
    return client.get_or_create_collection(collection_name)
```

- [ ] **Step 6: Implement orphan vector pruning**

Add:

```python
async def prune_orphan_vectors(connection, collection) -> int:
    rows = await connection.fetch(ACTIVE_CHROMA_IDS_SQL)
    active_ids = {row["chroma_id"] for row in rows}
    existing = collection.get(include=[])
    orphan_ids = [chroma_id for chroma_id in existing.get("ids", []) if chroma_id not in active_ids]
    if orphan_ids:
        collection.delete(ids=orphan_ids)
    return len(orphan_ids)
```

- [ ] **Step 7: Wire indexing inside crawl ingestion**

Modify `worker/tasks/crawl.py`, not `scheduler.py`. `scheduler.py` only registers `run_crawl`; the crawl job lifecycle and `crawl_jobs.error` updates live in `execute_ingestion()`.

After changed documents are persisted and before `finish_crawl_job()`, call an indexing helper that:

1. creates the Chroma collection
2. creates the embedder
3. calls `embed_pending_chunks()`
4. calls `prune_orphan_vectors()`
5. writes BM25 file indexes under `.data/bm25/`
6. marks the crawl job failed when indexing errors or summary failures occur

Document-level crawl failures may remain partial success, but indexing failures must make the crawl job `failed` because retrieval cannot be trusted until ChromaDB and BM25 outputs are available.

- [ ] **Step 8: Verify**

Run:

```bash
cd worker && uv run pytest tests/tasks/test_embed.py -v
cd worker && uv run pytest tests/tasks/test_crawl.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add worker/tasks/embed.py worker/tasks/crawl.py worker/tests/tasks/test_embed.py worker/tests/tasks/test_crawl.py
git commit -m "feat(worker): index chunks into chromadb" \
  -m "- embed pending chunks and prune orphan vectors" \
  -m "- run indexing inside crawl ingestion lifecycle" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 3: Conflict Invalidation Before Chunk Replacement

**Files:**
- Modify: `worker/tasks/storage.py`
- Test: `worker/tests/tasks/test_storage_conflicts.py`

- [ ] **Step 1: Write conflict invalidation test**

Create `worker/tests/tasks/test_storage_conflicts.py`:

```python
import pytest

from tasks.storage import invalidate_conflicts_for_document


@pytest.mark.asyncio
async def test_invalidate_conflicts_for_document_deletes_related_pairs():
    calls = []

    class FakeConnection:
        async def execute(self, query, document_id):
            calls.append((query, document_id))

    await invalidate_conflicts_for_document(FakeConnection(), "doc-1")

    assert calls
    assert "conflict_pairs" in calls[0][0]
    assert calls[0][1] == "doc-1"
```

- [ ] **Step 2: Implement invalidation helper**

Add to `worker/tasks/storage.py`:

```python
async def invalidate_conflicts_for_document(connection: asyncpg.Connection, document_id: str) -> None:
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
```

- [ ] **Step 3: Call before chunk delete**

Modify `replace_document_chunks`:

```python
async def replace_document_chunks(
    connection: asyncpg.Connection,
    document_id: str,
    document: ParsedDocument,
) -> None:
    await invalidate_conflicts_for_document(connection, document_id)
    await connection.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
    ...
```

- [ ] **Step 4: Verify**

Run:

```bash
cd worker && uv run pytest tests/tasks/test_storage_conflicts.py tests/tasks/test_storage.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add worker/tasks/storage.py worker/tests/tasks/test_storage_conflicts.py
git commit -m "fix(worker): invalidate conflicts before replacing chunks" \
  -m "- delete stale conflict pairs before chunk replacement" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 4: Backend Retrieval Foundation

**Files:**
- Create: `backend/app/services/chroma_client.py`
- Create: `backend/app/services/retriever.py`
- Test: `backend/tests/services/test_retriever.py`

- [ ] **Step 0: Check library docs**

Use Context7 to confirm current usage for `chromadb` query responses and `rank-bm25` scoring APIs. Record the checked versions/API notes in the task commit body or implementation notes. If Context7 lacks an entry, use official docs or installed package introspection and note that fallback.

- [ ] **Step 1: Write retriever tests**

Create `backend/tests/services/test_retriever.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from app.services.retriever import (
    BM25Index,
    RetrievalResult,
    merge_ranked_results,
    tokenize_korean_light,
)


def test_tokenize_korean_light_keeps_hangul_and_numbers():
    assert tokenize_korean_light("2026학년도 휴학 신청!") == ["2026학년도", "휴학", "신청"]


def test_bm25_index_returns_matching_chunk_first():
    first = RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="휴학 신청은 포털에서 진행합니다.",
        chunk_type="text",
        score=0,
        title="휴학",
        url="https://example.test/a",
        menu_path="학사 > 휴학",
        category="academic",
        crawled_at=datetime.now(UTC),
        meta=None,
    )
    second = first.model_copy(update={"chunk_id": uuid4(), "content": "장학금 안내입니다."})

    index = BM25Index([first, second])

    assert index.search("휴학 신청", top_n=1)[0].chunk_id == first.chunk_id


def test_merge_ranked_results_deduplicates_and_combines_scores():
    chunk_id = uuid4()
    base = RetrievalResult(
        chunk_id=chunk_id,
        document_id=uuid4(),
        content="휴학 신청",
        chunk_type="text",
        score=0.2,
        title="휴학",
        url="https://example.test/a",
        menu_path="학사",
        category="academic",
        crawled_at=datetime.now(UTC),
        meta=None,
    )

    merged = merge_ranked_results([base], [base.model_copy(update={"score": 1.0})], 0.7, 0.3, 6)

    assert len(merged) == 1
    assert merged[0].score == 0.44


@pytest.mark.asyncio
async def test_hybrid_retriever_rebuilds_bm25_on_watermark_change():
    class FakeSession:
        def __init__(self):
            self.watermarks = [datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 5, 2, tzinfo=UTC)]
            self.loads = 0

        async def scalar(self, statement):
            return self.watermarks.pop(0)

        async def execute(self, statement):
            self.loads += 1
            return FakeResult([make_result("휴학 신청은 포털에서 진행합니다.")])

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    session = FakeSession()
    retriever = HybridRetriever(
        collection=FakeChromaCollection(),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
    )

    await retriever.ensure_bm25_index(session)
    await retriever.ensure_bm25_index(session)

    assert session.loads == 2
```

- [ ] **Step 2: Implement retrieval models and tokenizer**

Create `backend/app/services/retriever.py`:

```python
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from rank_bm25 import BM25Okapi


TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    chunk_type: str
    score: float
    title: str | None
    url: str
    menu_path: str | None
    category: str | None
    crawled_at: datetime | None
    meta: dict | None


def tokenize_korean_light(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]
```

The test above also needs local fakes:

```python
def make_result(content: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=content,
        chunk_type="text",
        score=0,
        title="휴학",
        url="https://example.test/a",
        menu_path="학사 > 휴학",
        category="academic",
        crawled_at=datetime.now(UTC),
        meta=None,
    )


class FakeChromaCollection:
    def query(self, **kwargs):
        return {
            "ids": [["chunk:unused"]],
            "distances": [[0.2]],
            "metadatas": [[{"chunk_id": str(uuid4())}]],
        }


class FakeQueryEmbedder:
    def encode(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]
```

- [ ] **Step 3: Implement BM25 index**

Add:

```python
class BM25Index:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results
        self.corpus = [tokenize_korean_light(result.content) for result in results]
        self.index = BM25Okapi(self.corpus) if self.corpus else None

    def search(self, query: str, top_n: int) -> list[RetrievalResult]:
        if self.index is None:
            return []
        scores = self.index.get_scores(tokenize_korean_light(query))
        ranked = sorted(
            zip(self.results, scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [result.model_copy(update={"score": float(score)}) for result, score in ranked[:top_n] if score > 0]
```

- [ ] **Step 4: Implement score merge**

Add:

```python
def normalize_scores(results: list[RetrievalResult]) -> list[RetrievalResult]:
    if not results:
        return []
    max_score = max(result.score for result in results) or 1.0
    return [result.model_copy(update={"score": round(result.score / max_score, 6)}) for result in results]


def merge_ranked_results(
    semantic_results: list[RetrievalResult],
    bm25_results: list[RetrievalResult],
    semantic_weight: float,
    bm25_weight: float,
    final_top_k: int,
) -> list[RetrievalResult]:
    merged: dict[UUID, RetrievalResult] = {}
    for result in normalize_scores(semantic_results):
        merged[result.chunk_id] = result.model_copy(update={"score": result.score * semantic_weight})
    for result in normalize_scores(bm25_results):
        existing = merged.get(result.chunk_id)
        score = result.score * bm25_weight
        if existing:
            merged[result.chunk_id] = existing.model_copy(update={"score": round(existing.score + score, 6)})
        else:
            merged[result.chunk_id] = result.model_copy(update={"score": round(score, 6)})
    return sorted(
        merged.values(),
        key=lambda result: (
            result.score,
            result.crawled_at or datetime.min,
            result.chunk_type == "table",
        ),
        reverse=True,
    )[:final_top_k]
```

- [ ] **Step 5: Add Chroma client wrapper**

Create `backend/app/services/chroma_client.py`:

```python
import chromadb

from app.core.config import settings


def get_chroma_collection():
    client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return client.get_or_create_collection(settings.chroma_collection)
```

- [ ] **Step 6: Add active chunk loading and watermark rebuild**

Add to `backend/app/services/retriever.py`:

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk


def row_to_retrieval_result(row) -> RetrievalResult:
    chunk, document = row
    return RetrievalResult(
        chunk_id=chunk.id,
        document_id=document.id,
        content=chunk.content,
        chunk_type=chunk.chunk_type,
        score=0,
        title=document.title,
        url=document.url,
        menu_path=document.menu_path,
        category=document.category,
        crawled_at=document.crawled_at,
        meta=chunk.meta,
    )


async def load_active_chunks(session: AsyncSession, category: str | None = None) -> list[RetrievalResult]:
    statement = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.is_active.is_(True), DocumentChunk.content != "")
    )
    if category:
        statement = statement.where(Document.category == category)
    result = await session.execute(statement)
    return [row_to_retrieval_result(row) for row in result.all()]
```

- [ ] **Step 7: Add `HybridRetriever`**

Add:

```python
class HybridRetriever:
    def __init__(
        self,
        *,
        collection,
        embedder,
        semantic_weight: float,
        bm25_weight: float,
        final_top_k: int,
    ) -> None:
        self.collection = collection
        self.embedder = embedder
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        self.final_top_k = final_top_k
        self.watermark: datetime | None = None
        self.bm25_index = BM25Index([])

    async def ensure_bm25_index(self, session: AsyncSession, category: str | None = None) -> None:
        watermark = await session.scalar(select(func.max(DocumentChunk.created_at)))
        if watermark == self.watermark:
            return
        chunks = await load_active_chunks(session, category)
        self.bm25_index = BM25Index(chunks)
        self.watermark = watermark

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        question: str,
        category: str | None,
        semantic_top_n: int,
        bm25_top_n: int,
    ) -> list[RetrievalResult]:
        await self.ensure_bm25_index(session, category)
        semantic_results = await self.search_chroma(session, question, category, semantic_top_n)
        bm25_results = self.bm25_index.search(question, bm25_top_n)
        return merge_ranked_results(
            semantic_results,
            bm25_results,
            self.semantic_weight,
            self.bm25_weight,
            self.final_top_k,
        )
```

- [ ] **Step 8: Implement Chroma search path**

Add `search_chroma()` to `HybridRetriever`. It should encode the question, call `collection.query()`, extract `chunk_id` values from metadata, load matching chunks from PostgreSQL, and apply category filtering through DB query as the final source of truth.

- [ ] **Step 9: Verify**

Run:

```bash
cd backend && uv run pytest tests/services/test_retriever.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/chroma_client.py backend/app/services/retriever.py backend/tests/services/test_retriever.py
git commit -m "feat(rag): add hybrid retriever" \
  -m "- combine chroma semantic search with bm25 keyword search" \
  -m "- rebuild bm25 index from document chunk watermark" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 5: Freshness, Conflict, And Query Log Services

**Files:**
- Create: `backend/app/services/freshness.py`
- Create: `backend/app/services/conflict.py`
- Create: `backend/app/services/query_log.py`
- Test: `backend/tests/services/test_freshness.py`
- Test: `backend/tests/services/test_query_log.py`

- [ ] **Step 1: Write freshness tests**

Create `backend/tests/services/test_freshness.py`:

```python
from datetime import UTC, datetime, timedelta

from app.services.freshness import calculate_source_freshness, calculate_top_level_freshness


def test_source_without_crawled_at_is_stale():
    assert calculate_source_freshness(None, stale_days=180) == "stale"


def test_recent_source_is_recent():
    assert calculate_source_freshness(datetime.now(UTC), stale_days=180) == "recent"


def test_old_source_is_stale():
    old = datetime.now(UTC) - timedelta(days=181)
    assert calculate_source_freshness(old, stale_days=180) == "stale"


def test_top_level_is_stale_if_any_source_is_stale():
    assert calculate_top_level_freshness(["recent", "stale"]) == "stale"
```

- [ ] **Step 2: Implement freshness service**

Create `backend/app/services/freshness.py`:

```python
from datetime import UTC, datetime, timedelta


def calculate_source_freshness(crawled_at: datetime | None, stale_days: int) -> str:
    if crawled_at is None:
        return "stale"
    now = datetime.now(UTC)
    if crawled_at.tzinfo is None:
        crawled_at = crawled_at.replace(tzinfo=UTC)
    return "stale" if now - crawled_at > timedelta(days=stale_days) else "recent"


def calculate_top_level_freshness(values: list[str]) -> str:
    if not values:
        return "stale"
    return "stale" if any(value != "recent" for value in values) else "recent"
```

- [ ] **Step 3: Implement conflict service**

Create `backend/app/services/conflict.py`:

```python
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import ConflictPair
from app.schemas.chat import ConflictWarning


async def load_conflict_warning(session: AsyncSession, chunk_ids: list[UUID]) -> ConflictWarning:
    if not chunk_ids:
        return ConflictWarning(exists=False)
    result = await session.execute(
        select(ConflictPair).where(
            ConflictPair.is_resolved.is_(False),
            or_(
                ConflictPair.chunk_a_id.in_(chunk_ids),
                ConflictPair.chunk_b_id.in_(chunk_ids),
            ),
        )
    )
    conflict = result.scalars().first()
    if conflict is None:
        return ConflictWarning(exists=False)
    return ConflictWarning(
        exists=True,
        description=conflict.description
        or "관련 문서 간 내용 차이가 있어 담당 부서 확인이 필요합니다.",
    )
```

- [ ] **Step 4: Implement query log service**

Create `backend/app/services/query_log.py`:

```python
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import QueryLog


SPACE_RE = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    return SPACE_RE.sub(" ", query.strip()).lower()


def build_sources_log_payload(
    *,
    items: list[dict[str, Any]],
    status: str,
    cache_hit: bool,
    category: str | None,
    query: str,
    error_type: str | None = None,
) -> dict[str, Any]:
    return {
        "_meta": {
            "status": status,
            "cache_hit": cache_hit,
            "category": category,
            "normalized_query": normalize_query(query),
            "error_type": error_type,
        },
        "items": items,
    }


async def write_query_log(
    session: AsyncSession,
    *,
    query: str,
    answer: str | None,
    sources: dict[str, Any],
    has_conflict: bool,
    response_ms: int | None,
) -> QueryLog:
    log = QueryLog(
        query=query,
        answer=answer,
        sources=sources,
        has_conflict=has_conflict,
        response_ms=response_ms,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log
```

- [ ] **Step 5: Verify**

Create `backend/tests/services/test_query_log.py` before running verification:

```python
from app.services.query_log import build_sources_log_payload, normalize_query


def test_normalize_query_trims_lowercases_and_collapses_spaces():
    assert normalize_query("  휴학   신청은?  ") == "휴학 신청은?"


def test_build_sources_log_payload_wraps_items_and_metadata():
    payload = build_sources_log_payload(
        items=[{"title": "휴학", "url": "https://example.test"}],
        status="success",
        cache_hit=True,
        category="academic",
        query="휴학 신청은?",
    )

    assert payload["_meta"]["status"] == "success"
    assert payload["_meta"]["cache_hit"] is True
    assert payload["_meta"]["category"] == "academic"
    assert payload["_meta"]["normalized_query"] == "휴학 신청은?"
    assert payload["items"][0]["title"] == "휴학"
```

Run:

```bash
cd backend && uv run pytest tests/services/test_freshness.py -v
cd backend && uv run pytest tests/services/test_query_log.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/freshness.py backend/app/services/conflict.py backend/app/services/query_log.py backend/tests/services
git commit -m "feat(rag): add freshness conflict and query log services" \
  -m "- calculate source freshness and unresolved conflicts" \
  -m "- store query log metadata for rag responses" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 6: LLM Providers And RAG Orchestration

**Files:**
- Create: `backend/app/services/llm.py`
- Create: `backend/app/services/rag.py`
- Test: `backend/tests/services/test_llm.py`
- Test: `backend/tests/services/test_rag.py`

- [ ] **Step 0: Check provider docs**

Use Context7 to confirm current usage for `google-genai` async generate/stream APIs and `llama.cpp` server OpenAI-compatible chat completions. Record the checked versions/API notes in the task commit body or implementation notes. If Context7 lacks an entry, use official docs or installed package introspection and note that fallback.

- [ ] **Step 1: Write LLM provider config tests**

Create `backend/tests/services/test_llm.py`:

```python
import pytest

from app.services.llm import LLMMessage, StaticLLMProvider, validate_provider_settings


def test_static_provider_streams_answer_tokens():
    provider = StaticLLMProvider("안녕하세요")

    assert provider.generate_sync([LLMMessage(role="user", content="질문")]) == "안녕하세요"


def test_gemini_requires_model_and_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        validate_provider_settings("gemini", gemini_api_key="", gemini_model="")
```

- [ ] **Step 2: Implement provider protocol and static test provider**

Create `backend/app/services/llm.py`:

```python
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str


class LLMProvider(Protocol):
    async def generate(self, messages: list[LLMMessage]) -> str: ...
    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]: ...


class StaticLLMProvider:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def generate_sync(self, messages: list[LLMMessage]) -> str:
        return self.answer

    async def generate(self, messages: list[LLMMessage]) -> str:
        return self.answer

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        for token in self.answer.split(" "):
            yield token + " "


def validate_provider_settings(
    provider: str,
    *,
    llama_cpp_base_url: str = "",
    llama_cpp_model: str = "",
    gemini_api_key: str = "",
    gemini_model: str = "",
) -> None:
    if provider == "llama_cpp" and (not llama_cpp_base_url or not llama_cpp_model):
        raise ValueError("LLAMA_CPP_BASE_URL and LLAMA_CPP_MODEL are required")
    if provider == "gemini" and (not gemini_api_key or not gemini_model):
        raise ValueError("GEMINI_API_KEY and GEMINI_MODEL are required")
```

- [ ] **Step 3: Add llama.cpp and Gemini providers**

Add provider classes that implement `generate` and `stream`. Keep provider-specific SDK details inside `llm.py`.

```python
class LlamaCppProvider:
    def __init__(self, *, base_url: str, model: str) -> None:
        import httpx

        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=60)
        self.model = model

    async def generate(self, messages: list[LLMMessage]) -> str:
        response = await self.client.post(
            "/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": message.role, "content": message.content} for message in messages],
                "stream": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        import json

        async with self.client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": message.role, "content": message.content} for message in messages],
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break
                payload = json.loads(data)
                token = payload["choices"][0].get("delta", {}).get("content", "")
                if token:
                    yield token


class GeminiProvider:
    def __init__(self, *, api_key: str, model: str) -> None:
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def generate(self, messages: list[LLMMessage]) -> str:
        prompt = "\n\n".join(f"{message.role}: {message.content}" for message in messages)
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return response.text or ""

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        prompt = "\n\n".join(f"{message.role}: {message.content}" for message in messages)
        async for chunk in await self.client.aio.models.generate_content_stream(
            model=self.model,
            contents=prompt,
        ):
            if chunk.text:
                yield chunk.text
```

If the installed `google-genai` async streaming method name differs, update this code and `test_llm.py` in the same task based on the installed package API before committing.

- [ ] **Step 4: Write RAG assembly test**

Create `backend/tests/services/test_rag.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.chat import ConflictWarning
from app.services.llm import StaticLLMProvider
from app.services.rag import build_prompt_messages, generate_answer
from app.services.retriever import RetrievalResult


def make_result():
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="휴학 신청은 포털에서 신청합니다.",
        chunk_type="text",
        score=1.0,
        title="휴학 안내",
        url="https://example.test/leave",
        menu_path="학사 > 휴학",
        category="academic",
        crawled_at=datetime.now(UTC),
        meta=None,
    )


def test_build_prompt_uses_only_retrieved_context():
    messages = build_prompt_messages("휴학은?", [make_result()], ConflictWarning(exists=False))

    assert "검색된 공식 문서" in messages[0].content
    assert "휴학 신청은 포털" in messages[1].content


@pytest.mark.asyncio
async def test_generate_answer_returns_sources_and_steps():
    result = await generate_answer(
        question="휴학은?",
        category="academic",
        retrieval_results=[make_result()],
        conflict_warning=ConflictWarning(exists=False),
        provider=StaticLLMProvider("휴학 신청은 포털에서 신청합니다."),
        stale_days=180,
    )

    assert result.answer.startswith("휴학 신청")
    assert result.sources[0].title == "휴학 안내"
    assert result.freshness == "recent"
```

- [ ] **Step 5: Implement RAG service**

Create `backend/app/services/rag.py` with:

```python
from app.schemas.chat import ChatResponse, ConflictWarning, Source
from app.services.freshness import calculate_source_freshness, calculate_top_level_freshness
from app.services.llm import LLMMessage, LLMProvider
from app.services.retriever import RetrievalResult


def build_prompt_messages(
    question: str,
    retrieval_results: list[RetrievalResult],
    conflict_warning: ConflictWarning,
) -> list[LLMMessage]:
    context = "\n\n".join(
        f"[{index + 1}] {result.title or result.url}\n{result.content}"
        for index, result in enumerate(retrieval_results)
    )
    return [
        LLMMessage(
            role="system",
            content=(
                "검색된 공식 문서 근거만 사용해 한국어 존댓말로 답변하세요. "
                "근거가 부족하면 부족하다고 말하세요."
            ),
        ),
        LLMMessage(role="user", content=f"질문: {question}\n\n검색된 공식 문서:\n{context}"),
    ]


def extract_procedure_steps(answer: str) -> list[str]:
    return [line.strip("- 0123456789. ") for line in answer.splitlines() if line.strip().startswith(("-", "1.", "2.", "3."))]
```

Then implement `generate_answer` to call provider, calculate source freshness, top-level freshness, and return `ChatResponse`.

- [ ] **Step 6: Verify**

Run:

```bash
cd backend && uv run pytest tests/services/test_llm.py tests/services/test_rag.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/llm.py backend/app/services/rag.py backend/tests/services/test_llm.py backend/tests/services/test_rag.py
git commit -m "feat(rag): add llm providers and grounded answer service" \
  -m "- add llama.cpp and gemini provider implementations" \
  -m "- assemble grounded rag answers from retrieved chunks" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 7: Chat SSE Route With Cache And Logs

**Files:**
- Modify: `backend/app/api/routes/chat.py`
- Test: `backend/tests/api/test_chat_sse.py`

- [ ] **Step 0: Check SSE docs**

Use Context7 to confirm current usage for `sse-starlette` `EventSourceResponse`. Record the checked version/API notes in the task commit body or implementation notes. If Context7 lacks an entry, use official docs or installed package introspection and note that fallback.

- [ ] **Step 1: Write SSE route test**

Create `backend/tests/api/test_chat_sse.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_chat_rejects_blank_question():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={"question": ""})

    assert response.status_code in {400, 422}
```

Add a second test with fake route dependencies:

```python
@pytest.mark.asyncio
async def test_chat_stream_returns_named_events():
    app.dependency_overrides.clear()
    app.state.test_retrieval_results = ["fake-result"]
    app.state.test_tokens = ["휴학", " 신청은", " 포털에서"]
    app.state.test_procedure_steps = ["포털에 로그인합니다."]
    app.state.test_query_logs = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?"},
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert body.index("event: metadata") < body.index("event: token")
    assert body.index("event: token") < body.index("event: procedure_steps")
    assert body.index("event: procedure_steps") < body.index("event: done")
    assert app.state.test_query_logs[-1]["query"] == "휴학 신청은?"
```

- [ ] **Step 2: Implement SSE formatting helper**

In `backend/app/api/routes/chat.py`:

```python
import json
from collections.abc import AsyncIterator


def sse_event(event: str, data: dict) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}
```

Also add small dependency-provider functions in `chat.py` so tests can override retriever, RAG service, cache, and query log writer without monkeypatching internals.

```python
def get_chat_dependencies():
    return {
        "retriever": None,
        "rag_service": None,
        "cache": None,
        "query_log_writer": None,
    }
```

- [ ] **Step 3: Replace stub route**

Use `EventSourceResponse` from `sse_starlette.sse`. The route should:

1. validate non-empty question
2. check Redis cache by normalized question/category
3. retrieve chunks
4. compute conflict warning
5. emit `metadata`
6. stream LLM tokens as `token`
7. emit `procedure_steps`
8. emit `done`
9. write query log for success/failure/cache hit

Cache hit must still emit `metadata` and `done` in that order and write a query log with `cache_hit=true`.

- [ ] **Step 4: Keep JSON-compatible final payload**

The `done` event must contain:

```json
{
  "answer": "...",
  "sources": [],
  "procedure_steps": [],
  "conflict_warning": {"exists": false, "description": null},
  "freshness": "recent"
}
```

- [ ] **Step 5: Verify**

Run:

```bash
cd backend && uv run pytest tests/api/test_chat_sse.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/chat.py backend/tests/api/test_chat_sse.py
git commit -m "feat(api): stream rag chat responses" \
  -m "- emit named sse events for rag chat" \
  -m "- record query logs for streamed chat" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 8: Backend Categories FAQ Popular And Admin Routes

**Files:**
- Modify: `backend/app/api/routes/categories.py`
- Modify: `backend/app/api/routes/admin.py`
- Test: `backend/tests/api/test_kiosk_routes.py`
- Test: `backend/tests/api/test_admin_routes.py`

- [ ] **Step 1: Write kiosk route tests**

Create `backend/tests/api/test_kiosk_routes.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_categories_returns_backend_owned_categories():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/categories")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert {"id", "name"} <= response.json()[0].keys()
    assert any(item["id"] == "academic" for item in response.json())


@pytest.mark.asyncio
async def test_faq_route_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/faq")

    assert response.status_code == 200
```

Add admin crawl trigger coverage to `backend/tests/api/test_admin_routes.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_admin_crawl_trigger_returns_triggered_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/crawl")

    assert response.status_code == 200
    assert response.json()["status"] == "triggered"
```

- [ ] **Step 2: Implement curated category and FAQ seed**

Modify `backend/app/api/routes/categories.py`:

```python
CURATED_CATEGORIES = [
    {"id": "academic", "name": "학사행정"},
    {"id": "scholarship", "name": "장학 등록"},
    {"id": "campus", "name": "캠퍼스 생활"},
    {"id": "career", "name": "취업 진로"},
]

CURATED_FAQ = [
    {
        "id": "academic-leave",
        "question": "휴학 신청은 어떻게 하나요?",
        "category_id": "academic",
        "priority": 10,
        "source_url": None,
    },
]
```

`/api/v1/categories` must combine active DB categories with this curated label map. Use curated categories as backend-owned minimum data, then append any active `documents.category` values not already known.

```python
async def load_active_category_ids(session: AsyncSession) -> set[str]:
    result = await session.execute(
        select(Document.category)
        .where(Document.is_active.is_(True), Document.category.is_not(None))
        .distinct()
    )
    return {row[0] for row in result.all() if row[0]}
```

- [ ] **Step 3: Add `/faq` and `/popular`**

Implement:

```python
@router.get("/faq", response_model=list[FAQResponse])
async def list_faq(category: str | None = None) -> list[FAQResponse]:
    items = [FAQResponse(**item) for item in CURATED_FAQ]
    if category:
        items = [item for item in items if item.category_id == category]
    return sorted(items, key=lambda item: item.priority, reverse=True)
```

For `/popular`, query `query_logs`, normalize repeated questions, and return top 10. If there are no logs, return `[]`.

- [ ] **Step 4: Replace admin stubs**

Modify `backend/app/api/routes/admin.py` to query:

- active document count
- chunk count
- indexed chunk count
- latest `crawl_jobs.completed_at`
- unresolved conflicts
- recent query logs

Keep `/api/v1/admin/crawl` as a real trigger boundary. In local Phase 4, it may enqueue or start `run_crawl()` according to the existing worker integration, but the response must not pretend crawl completion. If the trigger runs in-process, call the same indexing refresh path used by worker ingestion. If it delegates to worker/scheduler, return `{"status": "triggered"}` and make admin status/logs expose the later crawl/index result.

- [ ] **Step 5: Verify**

Run:

```bash
cd backend && uv run pytest tests/api/test_kiosk_routes.py tests/api/test_admin_routes.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/categories.py backend/app/api/routes/admin.py backend/tests/api/test_kiosk_routes.py backend/tests/api/test_admin_routes.py
git commit -m "feat(api): serve kiosk and admin data from backend" \
  -m "- provide backend-owned categories faq and popular questions" \
  -m "- expose db-backed admin status conflicts and logs" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 9: Frontend SSE Chat And Fallback Gate

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/src/api/categories.ts`
- Modify: `frontend/src/api/faq.ts`
- Modify: `frontend/src/api/popular.ts`
- Modify: `frontend/src/types/kiosk.ts`
- Modify: `frontend/src/hooks/useChat.ts`
- Test: `frontend/src/hooks/useChat.test.ts`
- Test: `frontend/src/api/kioskApi.test.ts`

- [ ] **Step 0: Check frontend SSE docs**

Use Context7 to confirm current usage for `@microsoft/fetch-event-source`, especially POST body, `Accept: text/event-stream`, abort signal, and `onmessage` event handling. Record the checked version/API notes in the task commit body or implementation notes. If Context7 lacks an entry, use official docs or installed package introspection and note that fallback.

- [ ] **Step 1: Install SSE client**

Run:

```bash
cd frontend
npm install @microsoft/fetch-event-source
```

Expected: `package.json` and `package-lock.json` include `@microsoft/fetch-event-source`.

- [ ] **Step 2: Add SSE event types**

Modify `frontend/src/types/kiosk.ts`:

```ts
export type ChatSSEEvent =
  | { type: "metadata"; sources: Source[]; freshness: SourceFreshness; conflict_warning: ConflictWarning }
  | { type: "token"; text: string }
  | { type: "procedure_steps"; procedure_steps: string[] }
  | { type: "done"; payload: ChatResponsePayload }
  | { type: "error"; message: string; retryable: boolean };
```

Extend `ChatResponsePayload.sources[]`:

```ts
sources: Array<{
  title: string;
  url: string;
  crawled_at: string;
  freshness?: SourceFreshness;
  chunk_id?: string;
}>;
```

- [ ] **Step 3: Implement fallback flag helper**

In each of `categories.ts`, `faq.ts`, and `popular.ts`, gate fallback with:

```ts
const fallbackEnabled = import.meta.env.VITE_ENABLE_KIOSK_FALLBACK === "true";
```

When `fallbackEnabled` is false:

- categories: throw on 404, empty array, or network failure
- FAQ: throw on 404 or network failure; category filters may legitimately return an empty array only if backend returns 200
- popular: throw on 404 or network failure; `[]` is a valid empty state when there are no query logs

- [ ] **Step 4: Implement SSE chat client**

Modify `frontend/src/api/chat.ts`:

```ts
import { fetchEventSource } from "@microsoft/fetch-event-source";

import type { ChatRequestPayload, ChatResponsePayload } from "../types/kiosk";

export interface ChatStreamHandlers {
  onMetadata(data: unknown): void;
  onToken(text: string): void;
  onProcedureSteps(steps: string[]): void;
  onDone(payload: ChatResponsePayload): void;
  onError(message: string): void;
}

export async function streamChat(
  payload: ChatRequestPayload,
  handlers: ChatStreamHandlers,
  signal: AbortSignal,
) {
  await fetchEventSource("/api/v1/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
    onmessage(event) {
      const data = JSON.parse(event.data);
      if (event.event === "metadata") handlers.onMetadata(data);
      if (event.event === "token") handlers.onToken(data.text);
      if (event.event === "procedure_steps") handlers.onProcedureSteps(data.procedure_steps);
      if (event.event === "done") handlers.onDone(data);
      if (event.event === "error") handlers.onError(data.message);
    },
  });
}
```

Keep `postChat` only for tests that explicitly cover legacy JSON compatibility, or remove it and update tests.

- [ ] **Step 5: Update `useChat`**

Use `AbortController` and Phase 3 request id guard. On submit:

- set empty streaming answer
- call `streamChat`
- append tokens
- update procedure steps on event
- set final answer on done
- abort previous request on new submit

- [ ] **Step 6: Update tests**

In `frontend/src/hooks/useChat.test.ts`, mock `streamChat` and verify:

- token events append text
- procedure steps update
- done sets `isStreaming=false`
- stale request after reset does not overwrite current answer

In `frontend/src/api/kioskApi.test.ts`, set `vi.stubEnv("VITE_ENABLE_KIOSK_FALLBACK", "false")` and verify 404 rejects for categories/FAQ/popular. Also verify popular `200 []` resolves to `[]`.

- [ ] **Step 7: Verify**

Run:

```bash
cd frontend && npm run test:run
cd frontend && npm run typecheck
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api frontend/src/hooks/useChat.ts frontend/src/hooks/useChat.test.ts frontend/src/types/kiosk.ts
git commit -m "feat(frontend): stream chat responses over sse" \
  -m "- connect kiosk chat to post sse stream" \
  -m "- gate fallback data behind development flag" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

### Task 10: End-To-End Verification

**Files:**
- No planned file changes

- [ ] **Step 1: Run backend tests**

```bash
cd backend
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run worker tests**

```bash
cd worker
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend tests and build**

```bash
cd frontend
npm run test:run
npm run typecheck
npm run build
```

Expected: PASS.

- [ ] **Step 4: Run compose smoke**

```bash
docker compose up --build
```

Expected:

- backend responds at `http://localhost:8000/health`
- frontend responds at `http://localhost:5173/`
- postgres, redis, chromadb are healthy

- [ ] **Step 5: Verify Phase 4 user path**

With seeded or crawled documents:

```bash
curl -N \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"question":"휴학 신청은 어떻게 하나요?","category":"academic"}' \
  http://localhost:8000/api/v1/chat
```

Expected stream includes:

```text
event: metadata
event: token
event: procedure_steps
event: done
```

- [ ] **Step 6: Verify fallback-disabled frontend path**

Set:

```bash
VITE_ENABLE_KIOSK_FALLBACK=false
```

Then verify:

- `/api/v1/categories` is called and returns backend data
- `/api/v1/faq` is called and returns backend data
- `/api/v1/popular` is called and returns backend data or real empty state
- kiosk main -> input -> answer shows streaming answer and sources
- `/admin` shows query log after chat

---

## Self-Review Checklist

- [ ] Spec coverage: Tasks 1-10 cover worker indexing, conflict invalidation, retrieval, freshness, conflict warning, query logs, LLM providers, RAG answer generation, SSE chat, categories/FAQ/popular backend supply, admin DB routes, frontend SSE, fallback gate, and smoke verification.
- [ ] Placeholder scan: no task may leave placeholder wording or deferred implementation as the final instruction.
- [ ] Type consistency: `ChatResponsePayload`, `Source`, `ConflictWarning`, and SSE event names must match between backend schemas, frontend types, and tests.
- [ ] Phase boundary: no AWS deployment, Pi kiosk startup, real printer validation, Web Speech API STT/TTS activation, admin auth, or production observability work is included.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-phase-4-indexing-search-rag.md`.

Recommended execution mode: **Subagent-Driven**. Dispatch a fresh subagent per task, review between tasks, and amend same-task fixes into that task's commit before moving on.
