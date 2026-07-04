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

# RRF(Reciprocal Rank Fusion) 상수. 60은 원논문(Cormack 2009)의 표준값이라
# 튜닝 대상이 아니다(N=20 과적합 회피 원칙). 절대 손대지 않는다.
RRF_K = 60
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
    # score는 RRF(순위 융합)라 랭킹 전용이다. relevance는 가중합 정규화 유사도로
    # evidence 게이트의 절대 관련도 판정을 담당한다(관심사 분리). merge에서만 채운다.
    relevance: float | None = None
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
    # include_pools=True일 때만 채워지는 진단용 병합 전 풀(평가 부검용).
    # 검색이 실제로 쓴 풀을 그대로 담아, 별도 재검색 없이 gold 순위를 재게 한다.
    semantic_pool: list[RetrievalResult] | None = None
    bm25_pool: list[RetrievalResult] | None = None


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
    # score는 RRF(순위)라 절대 관련도가 없다. evidence 채택은 가중합 유사도인 relevance로
    # 판정한다(merge 이후엔 항상 채워짐, 방어적으로만 score 폴백).
    relevance = result.relevance if result.relevance is not None else result.score
    if relevance >= EVIDENCE_MIN_SCORE:
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
        # 폴백 코퍼스도 worker의 search_index_text와 같은 규칙(제목+메뉴경로+본문)으로 만든다.
        self.corpus = (
            corpus
            if corpus is not None
            else [
                tokenize_korean_light(
                    "\n".join(part for part in (result.title, result.menu_path, result.content) if part)
                )
                for result in results
            ]
        )
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
    *,
    question: str | None = None,
) -> list[RetrievalResult]:
    # score는 RRF(순위 융합)로 랭킹만 담당한다: 각 리스트에서 순위 rank마다 1/(RRF_K+rank)를
    # 더해, 한쪽 리스트에서만 강한 히트도 살아남게 한다. relevance는 기존 가중합 정규화 유사도로
    # evidence 게이트의 절대 관련도 판정을 담당한다(관심사 분리).
    objs: dict[UUID, RetrievalResult] = {}
    rrf_scores: dict[UUID, float] = {}
    relevance: dict[UUID, float] = {}

    for rank, result in enumerate(normalize_scores(semantic_results), start=1):
        objs[result.chunk_id] = result
        rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
        relevance[result.chunk_id] = relevance.get(result.chunk_id, 0.0) + result.score * semantic_weight

    for rank, result in enumerate(normalize_scores(bm25_results), start=1):
        objs.setdefault(result.chunk_id, result)
        rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
        relevance[result.chunk_id] = relevance.get(result.chunk_id, 0.0) + result.score * bm25_weight

    merged = [
        objs[chunk_id].model_copy(
            update={"score": round(rrf_scores[chunk_id], 8), "relevance": round(relevance[chunk_id], 6)}
        )
        for chunk_id in objs
    ]

    # 의도-인지 재점수는 dedup·top-k 슬라이스 전에 적용해야 하위 후보도 끌어올릴 수 있다.
    candidates = apply_intent_boost(merged, question) if question else merged

    ranked = sorted(
        candidates,
        key=lambda result: (
            result.score,
            # 같은 본문이 여러 학과 사이트에 복제된 경우 대표 사이트 문서를 대표로 남긴다.
            result.source_scope == "general_academic",
            _rank_datetime(result.crawled_at),
            result.chunk_type == "table",
        ),
        reverse=True,
    )
    # 같은 문서의 청크들이 top-k 슬롯을 여러 개 차지하면 다른 문서가 밀려난다.
    # 문서당 최고 청크 1개만 남겨 top-k를 서로 다른 문서로 채운다.
    return _dedup_by_document(_dedup_ranked_results(ranked))[:final_top_k]


# 곱셈 boost 계수. 1 근처의 보수적 값으로 동점 구간만 부드럽게 재정렬한다.
# 강한 패널티(STRONG)는 page_kind 의미충돌(요건 질문↔일정 문서 등)에만 쓴다.
RANK_FACTOR_BOOST = 1.15
RANK_FACTOR_SOFT_BOOST = 1.1
RANK_FACTOR_CONTACT_BOOST = 1.2
RANK_FACTOR_TITLE_BOOST = 1.2
RANK_FACTOR_SOFT_PENALTY = 0.9
RANK_FACTOR_STRONG_PENALTY = 0.7
RANK_FACTOR_MIN = 0.7
RANK_FACTOR_MAX = 1.4
PHONE_RE = re.compile(r"\d{2,4}-\d{3,4}-\d{4}")
DEPARTMENT_CURRICULUM_MARKER = "DepartmentCurriculum"


def apply_intent_boost(results: list[RetrievalResult], question: str) -> list[RetrievalResult]:
    intent = classify_question_intent(question)
    certificate_query = "증명서" in question
    query_keywords = normalize_query_keywords(question)
    boosted: list[RetrievalResult] = []
    for result in results:
        factor = _intent_factor(result, intent, certificate_query) * _title_factor(result, query_keywords)
        factor = min(max(factor, RANK_FACTOR_MIN), RANK_FACTOR_MAX)
        # 랭킹(score)과 evidence 관련도(relevance)에 같은 factor를 적용해 notice 강등 등이
        # 순위와 근거 채택 양쪽에 일관되게 반영되게 한다.
        update: dict = {"score": round(result.score * factor, 8)}
        if result.relevance is not None:
            update["relevance"] = round(result.relevance * factor, 6)
        boosted.append(result.model_copy(update=update))
    return boosted


def _title_factor(result: RetrievalResult, query_keywords: set[str]) -> float:
    # 제목은 문서 주제를 가장 압축한 신호다. "휴학" 질의에 제목 "일반휴학"처럼
    # 질의 핵심어가 제목에 부분 문자열로 들어가면 우대한다(BM25 통 토큰 매칭의 빈틈 보완).
    title = (result.title or "").strip()
    if not title or not query_keywords:
        return 1.0
    if any(keyword in title for keyword in query_keywords):
        return RANK_FACTOR_TITLE_BOOST
    return 1.0


def _intent_factor(result: RetrievalResult, intent: str, certificate_query: bool) -> float:
    factor = 1.0
    kind = result.page_kind
    url = result.url

    # page_kind 의미충돌은 강하게, 단순 선호는 약하게 차등한다.
    if intent == "requirement":
        if kind == "academic":
            factor *= RANK_FACTOR_BOOST
        if kind == "schedule":
            factor *= RANK_FACTOR_STRONG_PENALTY
    elif intent == "deadline":
        if kind == "schedule":
            factor *= RANK_FACTOR_BOOST
        if DEPARTMENT_CURRICULUM_MARKER in url:
            factor *= RANK_FACTOR_STRONG_PENALTY
    elif intent == "contact":
        if kind == "contact" or PHONE_RE.search(result.content or "") or "문의" in (result.content or ""):
            factor *= RANK_FACTOR_CONTACT_BOOST

    # 증명서 질의는 의도와 별개로 증명 안내 페이지를 우대한다.
    if certificate_query and kind == "certificate":
        factor *= RANK_FACTOR_BOOST

    # 일반 학사 질의는 대표 사이트를 약하게 우대한다.
    if intent in {"procedure", "factual"} and result.source_scope == "general_academic":
        factor *= RANK_FACTOR_SOFT_BOOST

    # 게시글(notice)은 시한부 소식이라 제도·기간·연락처 질문의 정답이 아니다.
    # 의도와 무관하게 약하게 낮춰 안내 페이지가 동점 구간에서 앞서게 한다.
    if kind == "notice":
        factor *= RANK_FACTOR_SOFT_PENALTY

    return min(max(factor, RANK_FACTOR_MIN), RANK_FACTOR_MAX)


def _dedup_by_document(results: list[RetrievalResult]) -> list[RetrievalResult]:
    # 입력이 점수 내림차순이므로 문서별 첫 항목이 대표(최고 점수 청크)로 남는다.
    seen: set[UUID] = set()
    deduped: list[RetrievalResult] = []
    for result in results:
        if result.document_id in seen:
            continue
        seen.add(result.document_id)
        deduped.append(result)
    return deduped


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
        include_pools: bool = False,
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
            question=question,
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
            # 검색이 실제로 사용한 병합 전 풀을 그대로 넘겨 평가가 재검색 없이 진단하게 한다.
            semantic_pool=semantic_results if include_pools else None,
            bm25_pool=bm25_results if include_pools else None,
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
            # 확장 청크도 부모의 relevance를 상속해 evidence 게이트 판정 기준을 일치시킨다.
            expanded_results.append(
                expansion.model_copy(update={"score": result.score, "relevance": result.relevance})
            )
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
