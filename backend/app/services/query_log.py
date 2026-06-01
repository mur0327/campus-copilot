from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import QueryLog

SPACE_RE = re.compile(r"\s+")
PHONE_RE = re.compile(r"[0-9]{2,3}-[0-9]{3,4}-[0-9]{4}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RRN_RE = re.compile(r"\d{6}-[1-4]\d{6}")
MAX_SOURCE_LOG_BYTES = 32 * 1024


def normalize_query(query: str) -> str:
    return SPACE_RE.sub(" ", query.strip()).lower()


def redact_private_identifiers(text: str) -> str:
    redacted = PHONE_RE.sub("[redacted]", text)
    redacted = EMAIL_RE.sub("[redacted]", redacted)
    return RRN_RE.sub("[redacted]", redacted)


def build_sources_log_payload(
    *,
    items: list[dict[str, Any]],
    status: str,
    cache_hit: bool,
    category: str | None,
    query: str,
    error_type: str | None = None,
    retrieval_status: dict[str, Any] | None = None,
    retrieval_candidates: list[dict[str, Any]] | None = None,
    answerability: str | None = None,
    used_source_numbers: list[int] | None = None,
    prompt_version: str = "chat-answer-json-v1",
) -> dict[str, Any]:
    payload = {
        "_meta": {
            "status": status,
            "cache_hit": cache_hit,
            "category": category,
            "normalized_query": redact_private_identifiers(normalize_query(query)),
            "error_type": error_type,
            "answerability": answerability,
            "used_source_numbers": used_source_numbers or [],
            "prompt_version": prompt_version,
            "retrieval_candidates": retrieval_candidates or [],
            "retrieval_status": retrieval_status,
        },
        "items": items,
    }
    encoded = str(payload).encode("utf-8")
    if len(encoded) <= MAX_SOURCE_LOG_BYTES:
        return payload
    payload["_meta"]["retrieval_candidates"] = []
    return payload


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
