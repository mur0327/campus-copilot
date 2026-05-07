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
    ChatMetadataEvent,
    ChatProcedureStepsEvent,
    ChatTokenEvent,
    RetrievalStatusPayload,
)
from app.services.chroma_client import get_chroma_collection
from app.services.conflict import load_conflict_warning
from app.services.freshness import calculate_top_level_freshness
from app.services.llm import GeminiProvider, LlamaCppProvider, LLMProvider
from app.services.query_log import build_sources_log_payload, normalize_query, write_query_log
from app.services.rag import (
    NO_GROUNDED_CONTEXT_ANSWER,
    _source_from_result,
    build_prompt_messages,
    extract_procedure_steps,
)
from app.services.retriever import HybridRetriever, RetrievalResult

router = APIRouter(tags=["chat"])
DEFAULT_EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"
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
            yield sse_event("metadata", _metadata_payload(cached_response))
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
            retrieval_results, retrieval_status = await _retrieve(
                dependencies.get("retriever"),
                session,
                question=payload.question,
                category=payload.category,
            )
            conflict_warning = await _load_conflict_warning(dependencies, session, _chunk_ids(retrieval_results))

        sources = _sources_from_results(retrieval_results)
        freshness = calculate_top_level_freshness([source.freshness or "stale" for source in sources])
        if not sources:
            freshness = "stale"

        metadata = ChatMetadataEvent(
            sources=sources,
            freshness=freshness,
            conflict_warning=conflict_warning,
            retrieval_status=retrieval_status,
        )
        yield sse_event("metadata", metadata.model_dump(mode="json"))

        if retrieval_results:
            answer = ""
            provider = await _make_llm_provider(dependencies)
            try:
                messages = build_prompt_messages(payload.question, retrieval_results, conflict_warning)
                async for token in provider.stream(messages):
                    answer += token
                    yield sse_event("token", ChatTokenEvent(text=token).model_dump(mode="json"))
            finally:
                await _close_provider(provider)
            procedure_steps = extract_procedure_steps(answer)
        else:
            answer = NO_GROUNDED_CONTEXT_ANSWER
            procedure_steps = []

        response = ChatResponse(
            answer=answer,
            sources=sources,
            procedure_steps=procedure_steps,
            conflict_warning=conflict_warning,
            freshness=freshness,
            retrieval_status=retrieval_status,
        )
        yield sse_event(
            "procedure_steps",
            ChatProcedureStepsEvent(procedure_steps=procedure_steps).model_dump(mode="json"),
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
    tokens = list(getattr(request.app.state, "test_tokens", []))
    procedure_steps = list(getattr(request.app.state, "test_procedure_steps", []))
    answer = "".join(tokens)
    response = ChatResponse(
        answer=answer,
        sources=[],
        procedure_steps=procedure_steps,
        conflict_warning=ConflictWarning(exists=False),
        freshness="recent",
        retrieval_status=RetrievalStatusPayload(mode="hybrid"),
    )

    yield sse_event("metadata", _metadata_payload(response))
    for token in tokens:
        yield sse_event("token", ChatTokenEvent(text=token).model_dump(mode="json"))
    yield sse_event(
        "procedure_steps",
        ChatProcedureStepsEvent(procedure_steps=procedure_steps).model_dump(mode="json"),
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


def _sources_from_results(retrieval_results: list[RetrievalResult]):
    return [_source_from_result(result, settings.freshness_stale_days) for result in retrieval_results]


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


def _metadata_payload(response: ChatResponse) -> dict[str, Any]:
    return ChatMetadataEvent(
        sources=response.sources,
        freshness=response.freshness,
        conflict_warning=response.conflict_warning,
        retrieval_status=response.retrieval_status,
    ).model_dump(mode="json")


def _coerce_chat_response(value: Any) -> ChatResponse | None:
    if value is None:
        return None
    if isinstance(value, ChatResponse):
        return value
    if isinstance(value, dict):
        return ChatResponse.model_validate(value)
    if isinstance(value, str):
        return ChatResponse.model_validate(json.loads(value))
    return None


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
            ),
            has_conflict=response.conflict_warning.exists,
            response_ms=response_ms,
        )
    )


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
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)
