from typing import Literal

from pydantic import BaseModel, Field

Answerability = Literal["answerable", "partial", "insufficient"]
Freshness = Literal["recent", "stale"]
ChatStatusStep = Literal["retrieving", "checking_evidence", "generating", "validating"]
CHAT_RESPONSE_CACHE_REQUIRED_FIELDS = frozenset(
    {
        "answerability",
        "answer",
        "summary",
        "procedure_steps",
        "notes",
        "limitations",
        "sources",
        "conflict_warning",
        "freshness",
        "retrieval_status",
    }
)


class Source(BaseModel):
    title: str
    url: str
    crawled_at: str
    freshness: str | None = None
    chunk_id: str | None = None


class ConflictWarning(BaseModel):
    exists: bool
    description: str | None = None


class RetrievalStatusPayload(BaseModel):
    mode: str = "empty"
    degraded: bool = False
    semantic_available: bool = True
    bm25_available: bool = True
    semantic_error: str | None = None
    bm25_error: str | None = None
    evidence_candidate_count: int = 0
    display_source_count: int = 0
    answerability: Answerability = "insufficient"


class ChatRequest(BaseModel):
    question: str
    category: str | None = None


class ChatResponse(BaseModel):
    answerability: Answerability = "insufficient"
    answer: str
    summary: str = ""
    sources: list[Source] = Field(default_factory=list)
    procedure_steps: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    conflict_warning: ConflictWarning = Field(
        default_factory=lambda: ConflictWarning(exists=False)
    )
    freshness: Freshness = "recent"
    retrieval_status: RetrievalStatusPayload = Field(default_factory=RetrievalStatusPayload)


class ChatStatusEvent(BaseModel):
    step: ChatStatusStep
