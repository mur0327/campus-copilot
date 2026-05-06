from pydantic import BaseModel, Field


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


class ChatRequest(BaseModel):
    question: str
    category: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    procedure_steps: list[str] = Field(default_factory=list)
    conflict_warning: ConflictWarning = Field(
        default_factory=lambda: ConflictWarning(exists=False)
    )
    freshness: str = "recent"
    retrieval_status: RetrievalStatusPayload = Field(default_factory=RetrievalStatusPayload)


class ChatMetadataEvent(BaseModel):
    sources: list[Source]
    freshness: str
    conflict_warning: ConflictWarning
    retrieval_status: RetrievalStatusPayload = Field(default_factory=RetrievalStatusPayload)


class ChatTokenEvent(BaseModel):
    text: str


class ChatProcedureStepsEvent(BaseModel):
    procedure_steps: list[str]
