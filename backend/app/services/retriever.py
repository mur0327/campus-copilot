import re
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel
from rank_bm25 import BM25Okapi
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk


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


class BM25Index:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.results = results
        self.corpus = [tokenize_korean_light(result.content) for result in results]
        self.index = BM25Okapi(self.corpus) if any(self.corpus) else None

    def search(self, query: str, top_n: int) -> list[RetrievalResult]:
        if self.index is None or top_n <= 0:
            return []

        query_tokens = tokenize_korean_light(query)
        raw_scores = self.index.get_scores(query_tokens)
        scored = [
            (result, float(raw_score), _token_overlap(tokens, query_tokens))
            for result, tokens, raw_score in zip(self.results, self.corpus, raw_scores, strict=True)
        ]
        ranked = sorted(
            scored,
            key=lambda item: (item[1], item[2]),
            reverse=True,
        )

        results = []
        for result, raw_score, overlap in ranked[:top_n]:
            score = raw_score if raw_score > 0 else float(overlap)
            if score > 0:
                results.append(result.model_copy(update={"score": score}))
        return results


def _token_overlap(tokens: list[str], query_tokens: list[str]) -> int:
    if not tokens or not query_tokens:
        return 0
    return len(set(tokens) & set(query_tokens))


def normalize_scores(results: list[RetrievalResult]) -> list[RetrievalResult]:
    if not results:
        return []
    max_score = max(max(result.score for result in results), 1.0)
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
        merged[result.chunk_id] = result.model_copy(update={"score": round(result.score * semantic_weight, 6)})

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
            _rank_datetime(result.crawled_at),
            result.chunk_type == "table",
        ),
        reverse=True,
    )[:final_top_k]


def _rank_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


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
        self.bm25_cache: dict[str | None, tuple[datetime | None, BM25Index]] = {}

    async def ensure_bm25_index(self, session: AsyncSession, category: str | None = None) -> BM25Index:
        watermark = await session.scalar(select(func.max(DocumentChunk.created_at)))
        cached = self.bm25_cache.get(category)
        if cached and cached[0] == watermark:
            return cached[1]

        chunks = await load_active_chunks(session, category)
        bm25_index = BM25Index(chunks)
        self.bm25_cache[category] = (watermark, bm25_index)
        return bm25_index

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        question: str,
        category: str | None,
        semantic_top_n: int,
        bm25_top_n: int,
    ) -> list[RetrievalResult]:
        bm25_index = await self.ensure_bm25_index(session, category)
        semantic_results = await self.search_chroma(session, question, category, semantic_top_n)
        bm25_results = bm25_index.search(question, bm25_top_n)
        return merge_ranked_results(
            semantic_results,
            bm25_results,
            self.semantic_weight,
            self.bm25_weight,
            self.final_top_k,
        )

    async def search_chroma(
        self,
        session: AsyncSession,
        question: str,
        category: str | None,
        semantic_top_n: int,
    ) -> list[RetrievalResult]:
        query_vector = _first_vector(self.embedder.encode([question]))
        query_kwargs = {
            "query_embeddings": [query_vector],
            "n_results": semantic_top_n,
            "include": ["metadatas", "distances"],
        }
        if category:
            query_kwargs["where"] = {"category": category}

        response = self.collection.query(**query_kwargs)
        chroma_ids = _first_response_list(response.get("ids"))
        metadatas = _first_response_list(response.get("metadatas"))
        distances = _first_response_list(response.get("distances"))

        chunk_ids: list[UUID] = []
        semantic_scores: dict[UUID, float] = {}
        for index in range(max(len(metadatas), len(chroma_ids))):
            metadata = metadatas[index] if index < len(metadatas) else None
            chroma_id = chroma_ids[index] if index < len(chroma_ids) else None
            chunk_id = _extract_chunk_id(metadata, chroma_id)
            if chunk_id is None or chunk_id in semantic_scores:
                continue
            chunk_ids.append(chunk_id)
            distance = distances[index] if index < len(distances) else None
            semantic_scores[chunk_id] = _distance_to_score(distance)

        if not chunk_ids:
            return []

        statement = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.id.in_(chunk_ids),
                Document.is_active.is_(True),
                DocumentChunk.content != "",
            )
        )
        if category:
            statement = statement.where(Document.category == category)

        result = await session.execute(statement)
        rows_by_id = {
            retrieval_result.chunk_id: retrieval_result
            for retrieval_result in (row_to_retrieval_result(row) for row in result.all())
        }

        ordered_results = []
        for chunk_id in chunk_ids:
            retrieval_result = rows_by_id.get(chunk_id)
            if retrieval_result:
                ordered_results.append(
                    retrieval_result.model_copy(update={"score": round(semantic_scores.get(chunk_id, 0), 6)})
                )
        return ordered_results


def _first_vector(encoded) -> list[float]:
    vector = encoded[0] if hasattr(encoded, "__getitem__") else encoded
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(value) for value in vector]


def _first_response_list(value) -> list:
    if not value:
        return []
    return list(value[0] or [])


def _parse_uuid(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _extract_chunk_id(metadata, chroma_id) -> UUID | None:
    if isinstance(metadata, dict):
        chunk_id = _parse_uuid(metadata.get("chunk_id"))
        if chunk_id:
            return chunk_id

    if not isinstance(chroma_id, str):
        return None
    raw_id = chroma_id.removeprefix("chunk:")
    return _parse_uuid(raw_id)


def _distance_to_score(distance) -> float:
    if distance is None:
        return 0
    try:
        distance_value = float(distance)
    except (TypeError, ValueError):
        return 0
    if distance_value < 0:
        return 0
    return 1 / (1 + distance_value)
