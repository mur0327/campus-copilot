from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from core.types import ChunkType, PageKind, SourceScope, SourceType


class DocumentProcessingStatus(StrEnum):
    CHANGED = "changed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(slots=True)
class DepartmentSite:
    name: str
    url: str


@dataclass(slots=True)
class CrawlTarget:
    url: str
    menu_path: str
    source_type: SourceType
    source_scope: SourceScope
    page_kind: PageKind
    title_hint: str | None = None
    year: int | None = None
    site_name: str | None = None
    site_url: str | None = None


@dataclass(slots=True)
class ParsedChunk:
    chunk_index: int
    content: str
    chunk_type: ChunkType
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedDocument:
    url: str
    title: str | None
    menu_path: str | None
    category: str | None
    source_scope: SourceScope
    page_kind: PageKind
    source_type: SourceType
    content_hash: str
    crawled_at: datetime
    chunks: list[ParsedChunk] = field(default_factory=list)


@dataclass(slots=True)
class CrawlStats:
    pages_crawled: int = 0
    pages_changed: int = 0
    pages_skipped: int = 0
    status_counts: dict[DocumentProcessingStatus, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    # 다른 프로세스가 크롤 advisory lock을 쥐고 있어 이번 회차를 건너뛴 경우 True.
    skipped: bool = False


@dataclass(slots=True)
class CrawlDiscoveryResult:
    targets: list[CrawlTarget] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
