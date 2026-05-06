from __future__ import annotations

import re
from typing import Any

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
