from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AdminStatusResponse(BaseModel):
    documents: int
    chunks: int
    indexed_chunks: int
    last_crawled: datetime | None
    latest_crawl_job: "AdminCrawlJobResponse | None" = None
    worker_crawl_status: "AdminWorkerCrawlStatusResponse | None" = None


class AdminWorkerCrawlStatusResponse(BaseModel):
    status: str
    current_stage: str | None = None
    total_pages: int = 0
    processed_pages: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class AdminCrawlJobResponse(BaseModel):
    id: UUID
    status: str
    pages_crawled: int
    pages_changed: int
    total_pages: int
    processed_pages: int
    current_stage: str | None
    conflicts_found: int
    started_at: datetime
    completed_at: datetime | None
    error: str | None


class AdminConflictResponse(BaseModel):
    id: UUID
    chunk_a_id: UUID
    chunk_b_id: UUID
    conflict_type: str
    severity: str
    is_resolved: bool
    summary: str | None = None


class AdminLogResponse(BaseModel):
    id: UUID
    query: str
    answer: str | None
    has_conflict: bool
    response_ms: int | None
    created_at: datetime | None
