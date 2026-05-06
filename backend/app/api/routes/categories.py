from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.document import Document, QueryLog
from app.schemas.kiosk import CategoryResponse, FAQResponse, PopularResponse
from app.services.query_log import normalize_query

router = APIRouter(tags=["categories"])

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


async def load_active_category_ids(session: AsyncSession) -> set[str]:
    result = await session.execute(
        select(Document.category)
        .where(Document.is_active.is_(True), Document.category.is_not(None))
        .distinct()
    )
    return {row[0] for row in result.all() if row[0]}


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(session: AsyncSession = Depends(get_db)) -> list[CategoryResponse]:
    items = [CategoryResponse(**item) for item in CURATED_CATEGORIES]
    known_ids = {item.id for item in items}
    active_category_ids = await load_active_category_ids(session)

    for category_id in sorted(active_category_ids):
        if category_id not in known_ids:
            items.append(CategoryResponse(id=category_id, name=category_id))

    return items


@router.get("/faq", response_model=list[FAQResponse])
async def list_faq(category: str | None = None) -> list[FAQResponse]:
    items = [FAQResponse(**item) for item in CURATED_FAQ]
    if category:
        items = [item for item in items if item.category_id == category]
    return sorted(items, key=lambda item: item.priority, reverse=True)


@router.get("/popular", response_model=list[PopularResponse])
async def list_popular(session: AsyncSession = Depends(get_db)) -> list[PopularResponse]:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    result = await session.execute(
        select(QueryLog.query)
        .where(QueryLog.created_at >= cutoff)
        .order_by(QueryLog.created_at.desc(), QueryLog.id.desc())
        .limit(200)
    )

    counts: Counter[str] = Counter()
    display_questions: dict[str, str] = {}
    for query in result.scalars().all():
        normalized = normalize_query(query)
        if not normalized:
            continue
        counts[normalized] += 1
        display_questions.setdefault(normalized, query.strip())

    ranked_questions = sorted(
        counts.items(),
        key=lambda item: (-item[1], display_questions[item[0]]),
    )[:10]
    return [
        PopularResponse(
            rank=index,
            question=display_questions[normalized],
            view_count=view_count,
        )
        for index, (normalized, view_count) in enumerate(ranked_questions, start=1)
    ]


@router.get("/recent")
async def list_recent() -> list[object]:
    return []
