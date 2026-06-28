import pickle
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel
from rank_bm25 import BM25Okapi
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.types import PageKind, SourceScope

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
DETAIL_QUERY_KEYWORDS = ("학점", "요건", "구성표", "기간", "금액", "시간", "기준")
DETAIL_TABLE_MIN_CHARS = 80
EVIDENCE_MAX_CANDIDATES = 4
EVIDENCE_MIN_SCORE = 0.35
EVIDENCE_MIN_DIRECT_OVERLAP = 1
EVIDENCE_PREVIEW_CHARS = 160
DEDUP_MIN_CONTENT_CHARS = 40
ACADEMIC_KEYWORDS = frozenset(
    {
        "휴학",
        "복학",
        "자퇴",
        "졸업",
        "장학",
        "등록금",
        "수강신청",
        "성적",
        "증명서",
        "신청",
        "기간",
        "방법",
        "서류",
        "기준",
        "조건",
        "문의",
        "담당",
        "입학",
        "상담",
    }
)
# 의도 분류 우선순위(위에서부터 먼저 매칭). "조기졸업 신청 조건"처럼 신청이 섞여도
# 질문의 초점(조건/시점/연락처)이 절차보다 앞서야 하므로 procedure를 가장 뒤에 둔다.
QUESTION_INTENT_KEYWORDS = {
    "requirement": ("조건", "기준", "요건", "자격"),
    "deadline": ("언제", "기간", "마감", "일정"),
    "contact": ("문의", "담당", "전화", "연락", "부서"),
    "procedure": ("어떻게", "방법", "절차", "신청"),
}
FACTUAL_KEYWORDS = ("무엇", "얼마", "몇", "누구", "어디", "확인", "가능", "종류")
KOREAN_TOKEN_SUFFIXES = (
    "으로부터",
    "에게서",
    "에서는",
    "에서",
    "으로",
    "로",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "과",
    "와",
    "도",
    "만",
    "의",
    "에",
    "요",
    "죠",
    "까",
)


class RetrievalResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    chunk_type: str
    chunk_index: int | None = None
    score: float
    title: str | None
    url: str
    menu_path: str | None
    category: str | None
    source_scope: SourceScope
    page_kind: PageKind
    crawled_at: datetime | None
    meta: dict | None


class RetrievalStatus(BaseModel):
    mode: str
    degraded: bool = False
    semantic_available: bool = True
    bm25_available: bool = True
    semantic_error: str | None = None
    bm25_error: str | None = None


class RetrievalResponse(BaseModel):
    results: list[RetrievalResult]
    status: RetrievalStatus


class EvidenceCandidate(BaseModel):
    display_result: RetrievalResult
    context_results: list[RetrievalResult]
    source_number: int
    overlap: int


def tokenize_korean_light(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def normalize_query_keywords(text: str) -> set[str]:
    # 복합어와 활용형도 핵심어로 잡기 위해 부분 문자열 포함으로 매칭한다.
    # 예: "재학증명서"에서 "증명서", "문의하면"에서 "문의", "편입학"에서 "입학"을 추출한다.
    keywords: set[str] = set()
    for token in tokenize_korean_light(text):
        normalized = _strip_korean_suffix(token)
        keywords.update(keyword for keyword in ACADEMIC_KEYWORDS if keyword in normalized)
    return keywords


def classify_question_intent(question: str) -> str:
    for intent, keywords in QUESTION_INTENT_KEYWORDS.items():
        if any(keyword in question for keyword in keywords):
            return intent
    # 위치·사실 질의("어디서 확인", "종류", "가능한가")는 절차가 아니라 사실 조회다.
    if any(keyword in question for keyword in FACTUAL_KEYWORDS):
        return "factual"
    return "unknown"


def filter_evidence_candidates(
    question: str,
    results: list[RetrievalResult],
    *,
    max_candidates: int = EVIDENCE_MAX_CANDIDATES,
) -> list[EvidenceCandidate]:
    query_keywords = normalize_query_keywords(question)
    grouped: dict[str, list[tuple[RetrievalResult, int]]] = {}
    for result in results:
        overlap = _direct_keyword_overlap(result, query_keywords)
        if not _is_accepted_evidence_result(result, overlap):
            continue
        grouped.setdefault(_evidence_group_key(result), []).append((result, overlap))

    candidates: list[EvidenceCandidate] = []
    for group_results in grouped.values():
        sorted_group = sorted(group_results, key=lambda item: item[0].score, reverse=True)
        display_result = sorted_group[0][0]
        context_results = [item[0] for item in sorted_group]
        candidates.append(
            EvidenceCandidate(
                display_result=display_result,
                context_results=context_results,
                source_number=0,
                overlap=max(item[1] for item in sorted_group),
            )
        )

    candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate.display_result.score,
            candidate.overlap,
            _rank_datetime(candidate.display_result.crawled_at),
        ),
        reverse=True,
    )[:max_candidates]
    return [candidate.model_copy(update={"source_number": index + 1}) for index, candidate in enumerate(candidates)]


def _strip_korean_suffix(token: str) -> str:
    current = token.lower()
    for suffix in KOREAN_TOKEN_SUFFIXES:
        if len(current) > len(suffix) + 1 and current.endswith(suffix):
            return current[: -len(suffix)]
    return current


def _direct_keyword_overlap(result: RetrievalResult, query_keywords: set[str]) -> int:
    if not query_keywords:
        return 0
    text = " ".join(part for part in (result.title, result.menu_path, result.content) if part)
    target_keywords = normalize_query_keywords(text)
    return len(query_keywords & target_keywords)


def _is_accepted_evidence_result(result: RetrievalResult, overlap: int) -> bool:
    if not result.url.strip() or not result.content.strip():
        return False
    if result.score >= EVIDENCE_MIN_SCORE:
        return True
    return overlap >= EVIDENCE_MIN_DIRECT_OVERLAP


def _evidence_group_key(result: RetrievalResult) -> str:
    return str(result.document_id) if result.document_id else _canonical_url(result.url)


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


class BM25Index:
    def __init__(
        self,
        results: list[RetrievalResult],
        *,
        corpus: list[list[str]] | None = None,
        index: BM25Okapi | None = None,
    ) -> None:
        self.results = results
        self.corpus = corpus if corpus is not None else [tokenize_korean_light(result.content) for result in results]
        self.index = index if index is not None else BM25Okapi(self.corpus) if any(self.corpus) else None

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

    ranked = sorted(
        merged.values(),
        key=lambda result: (
            result.score,
            # 같은 본문이 여러 학과 사이트에 복제된 경우 대표 사이트 문서를 대표로 남긴다.
            result.source_scope == "general_academic",
            _rank_datetime(result.crawled_at),
            result.chunk_type == "table",
        ),
        reverse=True,
    )
    return _dedup_ranked_results(ranked)[:final_top_k]


def _dedup_ranked_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
    # 학과 사이트마다 같은 페이지가 복제되어 top-k가 동일 문서로 채워지는 것을 막는다.
    # 입력이 점수 내림차순이므로 시그니처별 첫 항목이 대표(최고 점수)로 남는다.
    seen: set[str] = set()
    deduped: list[RetrievalResult] = []
    for result in results:
        signature = _dedup_signature(result)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(result)
    return deduped


def _dedup_signature(result: RetrievalResult) -> str:
    # 본문이 충분히 길면 정규화한 본문 해시로 중복을 묶고, 너무 짧으면 정규화 URL로 대체한다.
    normalized = " ".join(result.content.split()).lower()
    if len(normalized) >= DEDUP_MIN_CONTENT_CHARS:
        return "content:" + sha256(normalized.encode("utf-8")).hexdigest()
    return "url:" + _canonical_url(result.url)


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
        chunk_index=chunk.chunk_index,
        score=0,
        title=document.title,
        url=document.url,
        menu_path=document.menu_path,
        category=document.category,
        source_scope=document.source_scope,
        page_kind=document.page_kind,
        crawled_at=document.crawled_at,
        meta=chunk.meta,
    )


class HybridRetriever:
    def __init__(
        self,
        *,
        collection,
        embedder,
        semantic_weight: float,
        bm25_weight: float,
        final_top_k: int,
        bm25_cache_dir: str | Path | None = None,
    ) -> None:
        self.collection = collection
        self.embedder = embedder
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        self.final_top_k = final_top_k
        self.bm25_cache: dict[str | None, tuple[datetime | None, BM25Index]] = {}
        self.bm25_cache_dir = Path(bm25_cache_dir) if bm25_cache_dir else None

    async def ensure_bm25_index(self, session: AsyncSession, category: str | None = None) -> BM25Index:
        index, _available, _error = await self._ensure_bm25_index_status(session, category)
        return index

    async def _ensure_bm25_index_status(
        self,
        session: AsyncSession,
        category: str | None = None,
    ) -> tuple[BM25Index, bool, str | None]:
        watermark = await session.scalar(select(func.max(DocumentChunk.created_at)))
        cached = self.bm25_cache.get(category)
        if cached and cached[0] == watermark:
            return cached[1], bool(cached[1].results), None

        file_cached = self._load_bm25_file_cache(category, watermark)
        if file_cached is not None:
            self.bm25_cache[category] = (watermark, file_cached)
            return file_cached, True, None

        bm25_index = BM25Index([])
        self.bm25_cache[category] = (watermark, bm25_index)
        return bm25_index, False, "worker BM25 index is missing or stale"

    def _bm25_cache_path(self, category: str | None) -> Path | None:
        if self.bm25_cache_dir is None:
            return None
        category_key = category if category is not None else "_all"
        digest = sha256(category_key.encode("utf-8")).hexdigest()[:16]
        return self.bm25_cache_dir / f"bm25-{digest}.pkl"

    def _load_bm25_file_cache(
        self,
        category: str | None,
        watermark: datetime | None,
    ) -> BM25Index | None:
        cache_path = self._bm25_cache_path(category)
        if cache_path is None or not cache_path.exists():
            return None

        try:
            with cache_path.open("rb") as cache_file:
                payload = pickle.load(cache_file)
        except (OSError, pickle.PickleError, EOFError):
            return None

        if not isinstance(payload, dict):
            return None
        if payload.get("watermark") != watermark:
            return None
        if payload.get("category") != category:
            return None
        records = payload.get("records")
        corpus = payload.get("corpus")
        index = payload.get("index")
        if not isinstance(records, list) or not isinstance(corpus, list):
            return None
        if index is not None and not isinstance(index, BM25Okapi):
            return None

        try:
            results = [RetrievalResult.model_validate(record) for record in records]
        except ValueError:
            return None
        if len(results) != len(corpus):
            return None
        return BM25Index(results, corpus=corpus, index=index)

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        question: str,
        category: str | None,
        semantic_top_n: int,
        bm25_top_n: int,
    ) -> list[RetrievalResult]:
        response = await self.retrieve_with_status(
            session,
            question=question,
            category=category,
            semantic_top_n=semantic_top_n,
            bm25_top_n=bm25_top_n,
        )
        return response.results

    async def retrieve_with_status(
        self,
        session: AsyncSession,
        *,
        question: str,
        category: str | None,
        semantic_top_n: int,
        bm25_top_n: int,
    ) -> RetrievalResponse:
        bm25_index, bm25_available, bm25_error = await self._ensure_bm25_index_status(session, category)
        bm25_results = bm25_index.search(question, bm25_top_n)

        semantic_available = True
        semantic_error = None
        try:
            semantic_results = await self.search_chroma(session, question, category, semantic_top_n)
        except Exception as exc:
            semantic_available = False
            semantic_error = type(exc).__name__
            semantic_results = []

        results = merge_ranked_results(
            semantic_results,
            bm25_results,
            self.semantic_weight,
            self.bm25_weight,
            self.final_top_k,
        )
        results = await self.expand_detail_context(session, results, question=question, category=category)
        # 상세 컨텍스트 확장이 문서별로 같은 표를 다시 붙일 수 있어 최종 단계에서 한 번 더 중복을 제거한다.
        results = _dedup_ranked_results(results)
        return RetrievalResponse(
            results=results,
            status=RetrievalStatus(
                mode=_retrieval_mode(
                    results=results,
                    semantic_available=semantic_available,
                    bm25_available=bm25_available,
                ),
                degraded=not semantic_available or not bm25_available,
                semantic_available=semantic_available,
                bm25_available=bm25_available,
                semantic_error=semantic_error,
                bm25_error=bm25_error,
            ),
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

    async def expand_detail_context(
        self,
        session: AsyncSession,
        results: list[RetrievalResult],
        *,
        question: str,
        category: str | None,
    ) -> list[RetrievalResult]:
        if not _should_expand_detail_context(question, results):
            return results

        existing_chunk_ids = {result.chunk_id for result in results}
        candidate_results = [
            result
            for result in results
            if _is_heading_like_result(result) and not _has_detail_table_for_document(results, result.document_id)
        ]
        if not candidate_results:
            return results

        statement = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.document_id.in_(list({result.document_id for result in candidate_results})),
                DocumentChunk.chunk_type == "table",
                DocumentChunk.content != "",
                func.length(DocumentChunk.content) >= DETAIL_TABLE_MIN_CHARS,
                Document.is_active.is_(True),
            )
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
        if category:
            statement = statement.where(Document.category == category)

        expansion_rows = await session.execute(statement)
        table_results = [row_to_retrieval_result(row) for row in expansion_rows.all()]
        expansion_by_document = _nearest_following_tables(candidate_results, table_results)
        if not expansion_by_document:
            return results

        expanded_results: list[RetrievalResult] = []
        added_chunk_ids = set(existing_chunk_ids)
        for result in results:
            expanded_results.append(result)
            expansion = expansion_by_document.get(result.document_id)
            if expansion is None or expansion.chunk_id in added_chunk_ids:
                continue
            expanded_results.append(expansion.model_copy(update={"score": result.score}))
            added_chunk_ids.add(expansion.chunk_id)

        return expanded_results[: self.final_top_k]


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


def _should_expand_detail_context(question: str, results: list[RetrievalResult]) -> bool:
    if not results or not any(keyword in question for keyword in DETAIL_QUERY_KEYWORDS):
        return False
    return any(_is_heading_like_result(result) for result in results)


def _is_heading_like_result(result: RetrievalResult) -> bool:
    content = result.content.strip()
    if not content:
        return True
    if len(content) <= DETAIL_TABLE_MIN_CHARS:
        return True
    first_line = content.splitlines()[0].strip()
    return first_line.startswith("#") or "계속" in first_line


def _has_detail_table_for_document(results: list[RetrievalResult], document_id: UUID) -> bool:
    return any(
        result.document_id == document_id and result.chunk_type == "table" and not _is_heading_like_result(result)
        for result in results
    )


def _nearest_following_tables(
    candidate_results: list[RetrievalResult],
    table_results: list[RetrievalResult],
) -> dict[UUID, RetrievalResult]:
    candidate_index_by_document: dict[UUID, int] = {}
    for result in candidate_results:
        if result.chunk_index is None:
            continue
        current = candidate_index_by_document.get(result.document_id)
        if current is None or result.chunk_index < current:
            candidate_index_by_document[result.document_id] = result.chunk_index

    expansion_by_document: dict[UUID, RetrievalResult] = {}
    for table_result in table_results:
        candidate_index = candidate_index_by_document.get(table_result.document_id)
        if candidate_index is None or table_result.chunk_index is None:
            continue
        if table_result.chunk_index <= candidate_index:
            continue
        if table_result.document_id not in expansion_by_document:
            expansion_by_document[table_result.document_id] = table_result
    return expansion_by_document


def _retrieval_mode(
    *,
    results: list[RetrievalResult],
    semantic_available: bool,
    bm25_available: bool,
) -> str:
    if not results:
        return "empty"
    if semantic_available and bm25_available:
        return "hybrid"
    if semantic_available:
        return "semantic_only"
    if bm25_available:
        return "keyword_only"
    return "empty"
