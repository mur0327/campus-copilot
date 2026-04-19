from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

SourceType = Literal["html", "pdf"]
ChunkType = Literal["text", "table"]


@dataclass(slots=True)
class CrawlTarget:
    url: str
    menu_path: str
    source_type: SourceType
    title_hint: str | None = None
    year: int | None = None


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
    source_type: SourceType
    content_hash: str
    crawled_at: datetime
    chunks: list[ParsedChunk] = field(default_factory=list)


@dataclass(slots=True)
class CrawlStats:
    pages_crawled: int = 0
    pages_changed: int = 0
    failures: list[str] = field(default_factory=list)
