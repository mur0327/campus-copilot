from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.models.document import ConflictPair, CrawlJob, Document, DocumentChunk, QueryLog
from app.schemas.admin import AdminConflictResponse, AdminLogResponse, AdminStatusResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status", response_model=AdminStatusResponse)
async def status(session: AsyncSession = Depends(get_db)) -> AdminStatusResponse:
    documents = await session.scalar(
        select(func.count()).select_from(Document).where(Document.is_active.is_(True))
    )
    chunks = await session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .join(Document)
        .where(Document.is_active.is_(True))
    )
    indexed_chunks = await session.scalar(
        select(func.count())
        .select_from(DocumentChunk)
        .join(Document)
        .where(
            Document.is_active.is_(True),
            DocumentChunk.chroma_id.is_not(None),
        )
    )
    last_crawled = await session.scalar(
        select(CrawlJob.completed_at)
        .where(CrawlJob.completed_at.is_not(None))
        .order_by(CrawlJob.completed_at.desc())
        .limit(1)
    )

    return AdminStatusResponse(
        documents=documents or 0,
        chunks=chunks or 0,
        indexed_chunks=indexed_chunks or 0,
        last_crawled=last_crawled,
    )


@router.post("/crawl")
async def trigger_crawl() -> dict[str, str]:
    return await trigger_worker_crawl()


async def trigger_worker_crawl() -> dict[str, str]:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(settings.worker_crawl_url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="worker crawl trigger failed") from exc

    payload = response.json()
    status = payload.get("status")
    if status not in {"triggered", "already_running"}:
        raise HTTPException(status_code=502, detail="worker crawl trigger returned invalid status")
    return {"status": status}


@router.get("/conflicts", response_model=list[AdminConflictResponse])
async def list_conflicts(session: AsyncSession = Depends(get_db)) -> list[AdminConflictResponse]:
    result = await session.execute(
        select(ConflictPair)
        .where(ConflictPair.is_resolved.is_(False))
        .order_by(ConflictPair.detected_at.desc())
        .limit(50)
    )

    return [
        AdminConflictResponse(
            id=conflict.id,
            chunk_a_id=conflict.chunk_a_id,
            chunk_b_id=conflict.chunk_b_id,
            conflict_type=conflict.conflict_type,
            severity=conflict.severity,
            is_resolved=conflict.is_resolved,
            summary=conflict.description,
        )
        for conflict in result.scalars().all()
    ]


@router.get("/logs", response_model=list[AdminLogResponse])
async def list_logs(session: AsyncSession = Depends(get_db)) -> list[AdminLogResponse]:
    result = await session.execute(
        select(QueryLog).order_by(QueryLog.created_at.desc()).limit(50)
    )

    return [
        AdminLogResponse(
            id=log.id,
            query=log.query,
            answer=log.answer,
            has_conflict=log.has_conflict,
            response_ms=log.response_ms,
            created_at=log.created_at,
        )
        for log in result.scalars().all()
    ]
