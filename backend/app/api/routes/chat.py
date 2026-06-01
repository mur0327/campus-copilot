from __future__ import annotations

import inspect
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from hashlib import sha256
from time import perf_counter
from typing import Any
from uuid import UUID

from aiocache import Cache
from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.schemas import ChatRequest, ChatResponse, ConflictWarning
from app.schemas.chat import (
    CHAT_RESPONSE_CACHE_REQUIRED_FIELDS,
    ChatStatusEvent,
    RetrievalStatusPayload,
)
from app.services.chroma_client import get_chroma_collection
from app.services.conflict import load_conflict_warning
from app.services.embedding_provider import VoyageEmbedder
from app.services.llm import GeminiProvider, LlamaCppProvider, LLMProvider
from app.services.query_log import build_sources_log_payload, normalize_query, write_query_log
from app.services.rag import (
    JSON_VALIDATION_ERROR_ANSWER,
    NO_GROUNDED_CONTEXT_ANSWER,
    LLMOutputValidationError,
    dedupe_sources_by_url,
    generate_answer,
    insufficient_response,
    retrieval_candidate_log_items,
)
from app.services.retriever import HybridRetriever, RetrievalResult, filter_evidence_candidates

router = APIRouter(tags=["chat"])
DEFAULT_EMBEDDING_MODEL = "voyage-4-large"
_default_retriever: HybridRetriever | None = None
_default_cache: Any | None = None


class LazyHybridRetriever:
    async def retrieve(self, *args, **kwargs) -> list[RetrievalResult]:
        return await _get_default_retriever().retrieve(*args, **kwargs)


_lazy_retriever: LazyHybridRetriever | None = None


def sse_event(event: str, data: dict) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def get_chat_dependencies() -> dict[str, Any]:
    return {
        "retriever": _get_lazy_retriever(),
        "rag_service": None,
        "cache": _get_default_cache(),
        "query_log_writer": write_query_log,
        "llm_provider_factory": _build_llm_provider,
        "conflict_warning_loader": load_conflict_warning,
        "session_factory": AsyncSessionLocal,
    }


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    dependencies: dict[str, Any] = Depends(get_chat_dependencies),
) -> EventSourceResponse:
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="question must not be blank")

    return EventSourceResponse(_chat_events(request, payload, dependencies))


async def _chat_events(
    request: Request,
    payload: ChatRequest,
    dependencies: dict[str, Any],
) -> AsyncIterator[dict[str, str]]:
    if _has_test_chat_hooks(request):
        async for event in _test_chat_events(request, payload):
            yield event
        return

    normalized_question = normalize_query(payload.question)
    cache_key = _cache_key(normalized_question, payload.category)
    started_at = perf_counter()
    retrieval_status = RetrievalStatusPayload(mode="empty")

    try:
        cached_response = _coerce_chat_response(
            await _safe_cache_get(dependencies.get("cache"), cache_key)
        )
        if cached_response is not None:
            yield sse_event("done", cached_response.model_dump(mode="json"))
            await _safe_write_chat_log_with_session(
                dependencies,
                query=payload.question,
                response=cached_response,
                status="success",
                cache_hit=True,
                category=payload.category,
                response_ms=_elapsed_ms(started_at),
            )
            return

        async with _open_session(dependencies) as session:
            yield sse_event("status", ChatStatusEvent(step="retrieving").model_dump(mode="json"))
            retrieval_results, retrieval_status = await _retrieve(
                dependencies.get("retriever"),
                session,
                question=payload.question,
                category=payload.category,
            )
            conflict_warning = await _load_conflict_warning(dependencies, session, _chunk_ids(retrieval_results))

        yield sse_event("status", ChatStatusEvent(step="checking_evidence").model_dump(mode="json"))
        evidence_candidates = filter_evidence_candidates(payload.question, retrieval_results)
        if evidence_candidates:
            provider = await _make_llm_provider(dependencies)
            try:
                yield sse_event("status", ChatStatusEvent(step="generating").model_dump(mode="json"))
                response = await generate_answer(
                    question=payload.question,
                    category=payload.category,
                    retrieval_results=retrieval_results,
                    conflict_warning=conflict_warning,
                    provider=provider,
                    stale_days=settings.freshness_stale_days,
                    retrieval_status=retrieval_status,
                )
                yield sse_event("status", ChatStatusEvent(step="validating").model_dump(mode="json"))
            except LLMOutputValidationError as exc:
                response = ChatResponse(
                    answerability="insufficient",
                    answer=JSON_VALIDATION_ERROR_ANSWER,
                    summary=JSON_VALIDATION_ERROR_ANSWER,
                    sources=[],
                    procedure_steps=[],
                    notes=[],
                    limitations=[],
                    conflict_warning=conflict_warning,
                    freshness="stale",
                    retrieval_status=retrieval_status,
                )
                await _safe_write_chat_log_with_session(
                    dependencies,
                    query=payload.question,
                    response=response,
                    status="failure",
                    cache_hit=False,
                    category=payload.category,
                    response_ms=_elapsed_ms(started_at),
                    error_type=str(exc) or "json_validation_failed",
                    retrieval_results=retrieval_results,
                )
                yield sse_event("error", {"message": JSON_VALIDATION_ERROR_ANSWER, "retryable": True})
                return
            finally:
                await _close_provider(provider)
        else:
            response = insufficient_response(
                conflict_warning=conflict_warning,
                retrieval_status=retrieval_status,
                summary=NO_GROUNDED_CONTEXT_ANSWER,
            )
        await _safe_cache_set(dependencies.get("cache"), cache_key, response.model_dump(mode="json"))
        yield sse_event("done", response.model_dump(mode="json"))

        await _safe_write_chat_log_with_session(
            dependencies,
            query=payload.question,
            response=response,
            status="success",
            cache_hit=False,
            category=payload.category,
            response_ms=_elapsed_ms(started_at),
            retrieval_results=retrieval_results,
        )
    except Exception as exc:
        response = ChatResponse(
            answer="답변 생성 중 오류가 발생했습니다.",
            sources=[],
            procedure_steps=[],
            conflict_warning=ConflictWarning(exists=False),
            freshness="stale",
            retrieval_status=retrieval_status,
        )
        await _safe_write_chat_log_with_session(
            dependencies,
            query=payload.question,
            response=response,
            status="failure",
            cache_hit=False,
            category=payload.category,
            response_ms=_elapsed_ms(started_at),
            error_type=type(exc).__name__,
        )
        yield sse_event(
            "error",
            {"message": "답변 생성 중 오류가 발생했습니다.", "retryable": True},
        )


def _has_test_chat_hooks(request: Request) -> bool:
    return hasattr(request.app.state, "test_tokens")


async def _test_chat_events(request: Request, payload: ChatRequest) -> AsyncIterator[dict[str, str]]:
    answer = "".join(getattr(request.app.state, "test_tokens", []))
    procedure_steps = list(getattr(request.app.state, "test_procedure_steps", []))
    response = ChatResponse(
        answerability="answerable" if answer else "insufficient",
        answer=answer,
        summary=answer,
        sources=[],
        procedure_steps=procedure_steps,
        conflict_warning=ConflictWarning(exists=False),
        freshness="recent",
        retrieval_status=RetrievalStatusPayload(mode="hybrid"),
    )

    yield sse_event("done", response.model_dump(mode="json"))

    if hasattr(request.app.state, "test_query_logs"):
        request.app.state.test_query_logs.append(
            {
                "query": payload.question,
                "cache_hit": False,
                "retrieval_results": list(getattr(request.app.state, "test_retrieval_results", [])),
            }
        )


async def _retrieve(
    retriever: Any,
    session: Any,
    *,
    question: str,
    category: str | None,
) -> tuple[list[RetrievalResult], RetrievalStatusPayload]:
    if retriever is None:
        return [], RetrievalStatusPayload(mode="empty")
    if hasattr(retriever, "retrieve_with_status"):
        response = await retriever.retrieve_with_status(
            session,
            question=question,
            category=category,
            semantic_top_n=settings.retriever_semantic_top_n,
            bm25_top_n=settings.retriever_bm25_top_n,
        )
        return list(response.results), RetrievalStatusPayload.model_validate(response.status)
    results = await retriever.retrieve(
        session,
        question=question,
        category=category,
        semantic_top_n=settings.retriever_semantic_top_n,
        bm25_top_n=settings.retriever_bm25_top_n,
    )
    return results, RetrievalStatusPayload(mode="hybrid" if results else "empty")


def _chunk_ids(retrieval_results: list[RetrievalResult]) -> list[UUID]:
    return [result.chunk_id for result in retrieval_results]


def _open_session(dependencies: dict[str, Any]):
    session_factory = dependencies.get("session_factory") or AsyncSessionLocal
    return session_factory()


async def _load_conflict_warning(
    dependencies: dict[str, Any],
    session: Any,
    chunk_ids: list[UUID],
) -> ConflictWarning:
    loader = dependencies.get("conflict_warning_loader") or load_conflict_warning
    return await _maybe_await(loader(session, chunk_ids))


def _coerce_chat_response(value: Any) -> ChatResponse | None:
    if value is None:
        return None
    if isinstance(value, ChatResponse):
        return _dedupe_chat_response_sources(value)
    if isinstance(value, dict):
        if not _has_structured_chat_fields(value):
            return None
        return _dedupe_chat_response_sources(ChatResponse.model_validate(value))
    if isinstance(value, str):
        payload = json.loads(value)
        if not isinstance(payload, dict) or not _has_structured_chat_fields(payload):
            return None
        return _dedupe_chat_response_sources(ChatResponse.model_validate(payload))
    return None


def _has_structured_chat_fields(value: dict[str, Any]) -> bool:
    return CHAT_RESPONSE_CACHE_REQUIRED_FIELDS.issubset(value)


def _dedupe_chat_response_sources(response: ChatResponse) -> ChatResponse:
    deduped_sources = dedupe_sources_by_url(response.sources)
    if len(deduped_sources) == len(response.sources):
        return response
    return response.model_copy(update={"sources": deduped_sources})


def _cache_key(normalized_question: str, category: str | None) -> str:
    question_hash = sha256(normalized_question.encode("utf-8")).hexdigest()
    return f"chat:v1:{category or '_all'}:{question_hash}"


def _cache_get(cache: Any, key: str) -> Any:
    if cache is None:
        return None
    if hasattr(cache, "get"):
        return cache.get(key)
    if isinstance(cache, dict):
        return cache.get(key)
    return None


async def _safe_cache_get(cache: Any, key: str) -> Any:
    with suppress(Exception):
        return await _maybe_await(_cache_get(cache, key))
    return None


def _cache_set(cache: Any, key: str, value: dict[str, Any]) -> Any:
    if cache is None:
        return None
    if isinstance(cache, dict):
        cache[key] = value
        return None
    if not hasattr(cache, "set"):
        return None

    setter = cache.set
    try:
        return setter(key, value, ttl=settings.chat_cache_ttl_seconds)
    except TypeError:
        pass
    try:
        return setter(key, value, ex=settings.chat_cache_ttl_seconds)
    except TypeError:
        pass
    try:
        return setter(key, value, settings.chat_cache_ttl_seconds)
    except TypeError:
        return setter(key, value)


async def _safe_cache_set(cache: Any, key: str, value: dict[str, Any]) -> None:
    with suppress(Exception):
        await _maybe_await(_cache_set(cache, key, value))
    return None


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _write_chat_log(
    dependencies: dict[str, Any],
    session: Any,
    *,
    query: str,
    response: ChatResponse,
    status: str,
    cache_hit: bool,
    category: str | None,
    response_ms: int,
    error_type: str | None = None,
    retrieval_results: list[RetrievalResult] | None = None,
) -> None:
    writer = dependencies.get("query_log_writer")
    if writer is None:
        return

    await _maybe_await(
        writer(
            session,
            query=query,
            answer=response.answer,
            sources=build_sources_log_payload(
                items=[source.model_dump(mode="json") for source in response.sources],
                status=status,
                cache_hit=cache_hit,
                category=category,
                query=query,
                error_type=error_type,
                retrieval_status=response.retrieval_status.model_dump(mode="json"),
                retrieval_candidates=retrieval_candidate_log_items(retrieval_results or []),
                answerability=_log_answerability(response, error_type),
                used_source_numbers=_used_source_numbers_for_log(query, response, retrieval_results or []),
            ),
            has_conflict=response.conflict_warning.exists,
            response_ms=response_ms,
        )
    )


def _log_answerability(response: ChatResponse, error_type: str | None) -> str | None:
    if error_type == "json_validation_failed":
        return None
    return response.answerability


def _used_source_numbers_for_log(
    query: str,
    response: ChatResponse,
    retrieval_results: list[RetrievalResult],
) -> list[int]:
    if response.answerability == "insufficient" or not response.sources or not retrieval_results:
        return []
    candidates = filter_evidence_candidates(query, retrieval_results)
    number_by_chunk_id = {
        str(candidate.display_result.chunk_id): candidate.source_number
        for candidate in candidates
    }
    used_numbers: list[int] = []
    for source in response.sources:
        number = number_by_chunk_id.get(source.chunk_id or "")
        if number is not None and number not in used_numbers:
            used_numbers.append(number)
    return used_numbers


async def _write_chat_log_with_session(
    dependencies: dict[str, Any],
    *,
    query: str,
    response: ChatResponse,
    status: str,
    cache_hit: bool,
    category: str | None,
    response_ms: int,
    error_type: str | None = None,
    retrieval_results: list[RetrievalResult] | None = None,
) -> None:
    if dependencies.get("query_log_writer") is None:
        return
    async with _open_session(dependencies) as session:
        await _write_chat_log(
            dependencies,
            session,
            query=query,
            response=response,
            status=status,
            cache_hit=cache_hit,
            category=category,
            response_ms=response_ms,
            error_type=error_type,
            retrieval_results=retrieval_results,
        )


async def _safe_write_chat_log_with_session(
    dependencies: dict[str, Any],
    *,
    query: str,
    response: ChatResponse,
    status: str,
    cache_hit: bool,
    category: str | None,
    response_ms: int,
    error_type: str | None = None,
    retrieval_results: list[RetrievalResult] | None = None,
) -> None:
    with suppress(Exception):
        await _write_chat_log_with_session(
            dependencies,
            query=query,
            response=response,
            status=status,
            cache_hit=cache_hit,
            category=category,
            response_ms=response_ms,
            error_type=error_type,
            retrieval_results=retrieval_results,
        )


def _elapsed_ms(started_at: float) -> int:
    return max(round((perf_counter() - started_at) * 1000), 0)


async def _make_llm_provider(dependencies: dict[str, Any]) -> LLMProvider:
    provider_factory = dependencies.get("llm_provider_factory")
    if provider_factory is not None:
        return await _maybe_await(provider_factory())
    provider = dependencies.get("llm_provider")
    if provider is not None:
        return provider
    return _build_llm_provider()


async def _close_provider(provider: Any) -> None:
    close = getattr(provider, "aclose", None)
    if close is None:
        return
    with suppress(Exception):
        await _maybe_await(close())


def _build_llm_provider() -> LLMProvider:
    if settings.llm_provider == "gemini":
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    return LlamaCppProvider(base_url=settings.llama_cpp_base_url, model=settings.llama_cpp_model)


def _get_lazy_retriever() -> LazyHybridRetriever:
    global _lazy_retriever
    if _lazy_retriever is None:
        _lazy_retriever = LazyHybridRetriever()
    return _lazy_retriever


def _get_default_retriever() -> HybridRetriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = HybridRetriever(
            collection=get_chroma_collection(),
            embedder=create_embedder(getattr(settings, "embedding_model", DEFAULT_EMBEDDING_MODEL)),
            semantic_weight=settings.retriever_semantic_weight,
            bm25_weight=settings.retriever_bm25_weight,
            final_top_k=settings.retriever_final_top_k,
            bm25_cache_dir=settings.retriever_bm25_cache_dir,
        )
    return _default_retriever


def _get_default_cache() -> Any:
    global _default_cache
    if _default_cache is None:
        _default_cache = Cache.from_url(settings.redis_url)
    return _default_cache


def create_embedder(model_name: str):
    return VoyageEmbedder(
        model_name=model_name,
        input_type="query",
        api_key=getattr(settings, "voyage_api_key", ""),
        require_api_key=False,
    )
