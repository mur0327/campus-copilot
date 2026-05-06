from pydantic import BaseModel


class CategoryResponse(BaseModel):
    id: str
    name: str


class FAQResponse(BaseModel):
    id: str
    question: str
    category_id: str
    priority: int = 0
    source_url: str | None = None


class PopularResponse(BaseModel):
    rank: int
    question: str
    view_count: int
