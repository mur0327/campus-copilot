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


class ChatMetadataEvent(BaseModel):
    sources: list[Source]
    freshness: str
    conflict_warning: ConflictWarning


class ChatTokenEvent(BaseModel):
    text: str


class ChatProcedureStepsEvent(BaseModel):
    procedure_steps: list[str]
