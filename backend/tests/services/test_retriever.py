import os
import pickle
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

from app.services.retriever import (  # noqa: E402
    BM25Index,
    HybridRetriever,
    RetrievalResult,
    merge_ranked_results,
    tokenize_korean_light,
)


def make_result(
    content: str,
    *,
    category: str | None = "academic",
    chunk_index: int = 0,
    chunk_type: str = "text",
    document_id=None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=document_id or uuid4(),
        content=content,
        chunk_type=chunk_type,
        chunk_index=chunk_index,
        score=0,
        title="휴학",
        url="https://example.test/a",
        menu_path="학사 > 휴학",
        category=category,
        crawled_at=datetime.now(UTC),
        meta=None,
    )


def make_row(
    chunk_id,
    *,
    content: str = "휴학 신청은 포털에서 진행합니다.",
    category: str | None = "academic",
    chunk_index: int = 0,
    chunk_type: str = "text",
    document_id=None,
    title: str = "휴학",
    url: str = "https://example.test/a",
):
    document_id = document_id or uuid4()
    chunk = SimpleNamespace(
        id=chunk_id,
        document_id=document_id,
        content=content,
        chunk_type=chunk_type,
        chunk_index=chunk_index,
        meta={"source": "fake-db"},
    )
    document = SimpleNamespace(
        id=document_id,
        title=title,
        url=url,
        menu_path="학사 > 휴학",
        category=category,
        crawled_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    return chunk, document


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeChromaCollection:
    def __init__(self, *, chunk_ids=None, distances=None, metadatas=None):
        self.chunk_ids = chunk_ids or [uuid4()]
        self.distances = distances or [0.2 for _ in self.chunk_ids]
        self.metadatas = metadatas
        self.queries = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        return {
            "ids": [[f"chunk:{chunk_id}" for chunk_id in self.chunk_ids]],
            "distances": [self.distances],
            "metadatas": [
                self.metadatas
                if self.metadatas is not None
                else [{"chunk_id": str(chunk_id)} for chunk_id in self.chunk_ids]
            ],
        }


class FakeQueryEmbedder:
    def encode(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_tokenize_korean_light_keeps_hangul_and_numbers():
    assert tokenize_korean_light("2026학년도 휴학 신청!") == ["2026학년도", "휴학", "신청"]


def test_bm25_index_returns_matching_chunk_first():
    first = make_result("휴학 신청은 포털에서 진행합니다.")
    second = first.model_copy(update={"chunk_id": uuid4(), "content": "장학금 안내입니다."})

    index = BM25Index([first, second])

    assert index.search("휴학 신청", top_n=1)[0].chunk_id == first.chunk_id


def test_bm25_index_with_punctuation_only_content_returns_empty_results():
    index = BM25Index([make_result("!!!")])

    assert index.search("휴학 신청", top_n=1) == []


def test_merge_ranked_results_deduplicates_and_combines_scores():
    chunk_id = uuid4()
    base = make_result("휴학 신청").model_copy(update={"chunk_id": chunk_id, "score": 0.2})

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
            raise AssertionError("BM25 should not fall back to database loading")

    session = FakeSession()
    retriever = HybridRetriever(
        collection=FakeChromaCollection(),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
    )

    first_index = await retriever.ensure_bm25_index(session)
    second_index = await retriever.ensure_bm25_index(session)

    assert session.loads == 0
    assert first_index is not second_index


@pytest.mark.asyncio
async def test_hybrid_retriever_returns_empty_bm25_when_worker_cache_is_missing(
    tmp_path: Path,
):
    watermark = datetime(2026, 5, 1, tzinfo=UTC)

    class FakeSession:
        def __init__(self):
            self.loads = 0

        async def scalar(self, statement):
            return watermark

        async def execute(self, statement):
            self.loads += 1
            raise AssertionError("BM25 should not fall back to database loading")

    session = FakeSession()
    retriever = HybridRetriever(
        collection=FakeChromaCollection(),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
        bm25_cache_dir=tmp_path,
    )
    loaded_index = await retriever.ensure_bm25_index(session, "academic")

    assert loaded_index.search("휴학 신청", top_n=1) == []
    assert session.loads == 0
    assert list(tmp_path.glob("*.pkl")) == []


@pytest.mark.asyncio
async def test_hybrid_retriever_loads_worker_bm25_file_cache(tmp_path: Path):
    watermark = datetime(2026, 5, 1, tzinfo=UTC)
    result = make_result("휴학 신청은 포털에서 진행합니다.")
    cache_path = tmp_path / "bm25-b8a98203ec9d769d.pkl"
    worker_bm25 = BM25Index([result])
    with cache_path.open("wb") as cache_file:
        pickle.dump(
            {
                "version": 1,
                "watermark": watermark,
                "category": "academic",
                "records": [result.model_dump(mode="json")],
                "corpus": worker_bm25.corpus,
                "index": worker_bm25.index,
            },
            cache_file,
        )

    class LoadingSession:
        async def scalar(self, statement):
            return watermark

        async def execute(self, statement):
            raise AssertionError("BM25 should load from worker file cache")

    retriever = HybridRetriever(
        collection=FakeChromaCollection(),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
        bm25_cache_dir=tmp_path,
    )

    loaded_index = await retriever.ensure_bm25_index(LoadingSession(), "academic")

    assert loaded_index.search("휴학 신청", top_n=1)[0].chunk_id == result.chunk_id


@pytest.mark.asyncio
async def test_retrieve_uses_bm25_index_snapshot_from_requested_category(tmp_path: Path):
    watermark = datetime(2026, 5, 1, tzinfo=UTC)
    academic = make_result("휴학 신청은 포털에서 진행합니다.", category="academic")
    scholarship = make_result("장학금 안내입니다.", category="scholarship")

    class RebuildingRetriever(HybridRetriever):
        async def search_chroma(self, session, question, category, semantic_top_n):
            await self.ensure_bm25_index(session, "scholarship")
            return []

    class CategorySession:
        async def scalar(self, statement):
            return watermark

    academic_path = tmp_path / "bm25-b8a98203ec9d769d.pkl"
    scholarship_path = tmp_path / "bm25-f552935eea2a6d76.pkl"
    for cache_path, category, result in [
        (academic_path, "academic", academic),
        (scholarship_path, "scholarship", scholarship),
    ]:
        worker_bm25 = BM25Index([result])
        with cache_path.open("wb") as cache_file:
            pickle.dump(
                {
                    "version": 1,
                    "watermark": watermark,
                    "category": category,
                    "records": [result.model_dump(mode="json")],
                    "corpus": worker_bm25.corpus,
                    "index": worker_bm25.index,
                },
                cache_file,
            )

    retriever = RebuildingRetriever(
        collection=FakeChromaCollection(),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
        bm25_cache_dir=tmp_path,
    )

    results = await retriever.retrieve(
        CategorySession(),
        question="휴학 신청",
        category="academic",
        semantic_top_n=1,
        bm25_top_n=1,
    )

    assert results[0].category == "academic"
    assert "휴학" in results[0].content


@pytest.mark.asyncio
async def test_retrieve_with_status_degrades_to_semantic_only_when_bm25_is_missing(tmp_path: Path):
    chunk_id = uuid4()

    class SemanticOnlySession:
        async def scalar(self, statement):
            return datetime(2026, 5, 1, tzinfo=UTC)

        async def execute(self, statement):
            return FakeResult([make_row(chunk_id)])

    retriever = HybridRetriever(
        collection=FakeChromaCollection(chunk_ids=[chunk_id]),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
        bm25_cache_dir=tmp_path,
    )

    response = await retriever.retrieve_with_status(
        SemanticOnlySession(),
        question="휴학 신청",
        category="academic",
        semantic_top_n=1,
        bm25_top_n=1,
    )

    assert response.status.mode == "semantic_only"
    assert response.status.degraded is True
    assert response.status.semantic_available is True
    assert response.status.bm25_available is False
    assert response.results[0].chunk_id == chunk_id


@pytest.mark.asyncio
async def test_retrieve_expands_heading_with_following_table_for_detail_question(tmp_path: Path):
    document_id = uuid4()
    heading_id = uuid4()
    detail_id = uuid4()

    class DetailSession:
        def __init__(self):
            self.execute_calls = 0

        async def scalar(self, statement):
            return datetime(2026, 5, 1, tzinfo=UTC)

        async def execute(self, statement):
            self.execute_calls += 1
            if self.execute_calls == 1:
                return FakeResult(
                    [
                        make_row(
                            heading_id,
                            content="# 2025학년도 입학생 졸업학점 구성표",
                            chunk_index=0,
                            chunk_type="text",
                            document_id=document_id,
                            title="졸업학점 2025",
                            url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
                        )
                    ]
                )
            return FakeResult(
                [
                    make_row(
                        detail_id,
                        content=(
                            "학과(부): 컴퓨터공학과 | 교양영역: 12 | 전공영역: 60 | "
                            "자유선택: 30 | 졸업 이수 학점: 120 | "
                            "학과별 졸업 최소이수학점 구성표 상세 행입니다."
                        ),
                        chunk_index=1,
                        chunk_type="table",
                        document_id=document_id,
                        title="졸업학점 2025",
                        url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
                    )
                ]
            )

    session = DetailSession()
    retriever = HybridRetriever(
        collection=FakeChromaCollection(chunk_ids=[heading_id]),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=4,
        bm25_cache_dir=tmp_path,
    )

    response = await retriever.retrieve_with_status(
        session,
        question="졸업학점에 대해서 설명해주세요",
        category=None,
        semantic_top_n=1,
        bm25_top_n=1,
    )

    assert [result.chunk_id for result in response.results] == [heading_id, detail_id]
    assert response.results[1].chunk_type == "table"
    assert "졸업 이수 학점: 120" in response.results[1].content


@pytest.mark.asyncio
async def test_retrieve_with_status_degrades_to_keyword_only_when_chroma_fails(tmp_path: Path):
    watermark = datetime(2026, 5, 1, tzinfo=UTC)
    result = make_result("휴학 신청은 포털에서 진행합니다.")
    cache_path = tmp_path / "bm25-b8a98203ec9d769d.pkl"
    worker_bm25 = BM25Index([result])
    with cache_path.open("wb") as cache_file:
        pickle.dump(
            {
                "version": 1,
                "watermark": watermark,
                "category": "academic",
                "records": [result.model_dump(mode="json")],
                "corpus": worker_bm25.corpus,
                "index": worker_bm25.index,
            },
            cache_file,
        )

    class FailingChromaCollection(FakeChromaCollection):
        def query(self, **kwargs):
            raise RuntimeError("chroma unavailable")

    class KeywordSession:
        async def scalar(self, statement):
            return watermark

    retriever = HybridRetriever(
        collection=FailingChromaCollection(),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
        bm25_cache_dir=tmp_path,
    )

    response = await retriever.retrieve_with_status(
        KeywordSession(),
        question="휴학 신청",
        category="academic",
        semantic_top_n=1,
        bm25_top_n=1,
    )

    assert response.status.mode == "keyword_only"
    assert response.status.degraded is True
    assert response.status.semantic_available is False
    assert response.status.bm25_available is True
    assert response.results[0].chunk_id == result.chunk_id


@pytest.mark.asyncio
async def test_retrieve_with_status_returns_empty_when_chroma_and_bm25_are_unavailable(tmp_path: Path):
    class FailingChromaCollection(FakeChromaCollection):
        def query(self, **kwargs):
            raise RuntimeError("chroma unavailable")

    class EmptySession:
        async def scalar(self, statement):
            return datetime(2026, 5, 1, tzinfo=UTC)

    retriever = HybridRetriever(
        collection=FailingChromaCollection(),
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
        bm25_cache_dir=tmp_path,
    )

    response = await retriever.retrieve_with_status(
        EmptySession(),
        question="휴학 신청",
        category="academic",
        semantic_top_n=1,
        bm25_top_n=1,
    )

    assert response.status.mode == "empty"
    assert response.status.degraded is True
    assert response.results == []


@pytest.mark.asyncio
async def test_search_chroma_reloads_chunk_metadata_and_filters_category_from_db():
    academic_id = uuid4()
    scholarship_id = uuid4()
    missing_id = uuid4()
    collection = FakeChromaCollection(
        chunk_ids=[scholarship_id, academic_id, "not-a-uuid", missing_id],
        distances=[0.5, 0.25, 0.1, None],
    )

    class FakeSession:
        def __init__(self):
            self.rows_by_id = {
                academic_id: make_row(academic_id, category="academic"),
                scholarship_id: make_row(
                    scholarship_id,
                    content="장학금 신청 안내입니다.",
                    category="scholarship",
                ),
            }
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            params = statement.compile().params
            requested_ids = next(value for value in params.values() if isinstance(value, list))
            category = next(value for value in params.values() if value == "academic")
            rows = [
                self.rows_by_id[chunk_id]
                for chunk_id in reversed(requested_ids)
                if chunk_id in self.rows_by_id and self.rows_by_id[chunk_id][1].category == category
            ]
            return FakeResult(rows)

    session = FakeSession()
    retriever = HybridRetriever(
        collection=collection,
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
    )

    results = await retriever.search_chroma(
        session,
        question="휴학 신청",
        category="academic",
        semantic_top_n=4,
    )

    assert [result.chunk_id for result in results] == [academic_id]
    assert results[0].category == "academic"
    assert results[0].meta == {"source": "fake-db"}
    assert results[0].score == 0.8
    assert collection.queries[0]["query_embeddings"] == [[0.1, 0.2, 0.3]]
    assert collection.queries[0]["where"] == {"category": "academic"}
    compiled_params = session.statements[0].compile().params
    requested_ids = next(value for value in compiled_params.values() if isinstance(value, list))
    assert isinstance(requested_ids[0], UUID)
    compiled_sql = str(session.statements[0].compile())
    assert "documents.is_active IS true" in compiled_sql
    assert "document_chunks.content !=" in compiled_sql
    assert "documents.category =" in compiled_sql


@pytest.mark.asyncio
async def test_search_chroma_uses_chroma_ids_when_metadata_chunk_id_is_missing_or_invalid():
    chunk_id = uuid4()
    collection = FakeChromaCollection(
        chunk_ids=[chunk_id],
        distances=[0.5],
        metadatas=[{"chunk_id": "not-a-uuid"}],
    )

    class FakeSession:
        async def execute(self, statement):
            return FakeResult([make_row(chunk_id)])

    retriever = HybridRetriever(
        collection=collection,
        embedder=FakeQueryEmbedder(),
        semantic_weight=0.7,
        bm25_weight=0.3,
        final_top_k=6,
    )

    results = await retriever.search_chroma(
        FakeSession(),
        question="휴학 신청",
        category=None,
        semantic_top_n=1,
    )

    assert [result.chunk_id for result in results] == [chunk_id]
