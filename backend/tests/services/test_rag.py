import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

from app.schemas.chat import ConflictWarning  # noqa: E402
from app.services.llm import StaticLLMProvider  # noqa: E402
from app.services.rag import build_prompt_messages, extract_procedure_steps, generate_answer  # noqa: E402
from app.services.retriever import RetrievalResult  # noqa: E402


def make_result(*, title: str | None = "휴학 안내", crawled_at: datetime | None = None) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="휴학 신청은 포털에서 신청합니다.",
        chunk_type="text",
        score=1.0,
        title=title,
        url="https://example.test/leave",
        menu_path="학사 > 휴학",
        category="academic",
        crawled_at=crawled_at or datetime.now(UTC),
        meta=None,
    )


class FailingProvider:
    async def generate(self, messages):
        raise AssertionError("provider should not be called")

    async def stream(self, messages):
        raise AssertionError("provider should not be called")
        yield ""


def test_build_prompt_uses_only_retrieved_context():
    messages = build_prompt_messages("휴학은?", [make_result()], ConflictWarning(exists=False))

    assert "검색된 공식 문서" in messages[0].content
    assert "휴학 신청은 포털" in messages[1].content


@pytest.mark.asyncio
async def test_generate_answer_returns_sources_and_steps():
    result = await generate_answer(
        question="휴학은?",
        category="academic",
        retrieval_results=[make_result()],
        conflict_warning=ConflictWarning(exists=False),
        provider=StaticLLMProvider("휴학 신청은 포털에서 신청합니다."),
        stale_days=180,
    )

    assert result.answer.startswith("휴학 신청")
    assert result.sources[0].title == "휴학 안내"
    assert result.freshness == "recent"


@pytest.mark.asyncio
async def test_generate_answer_deduplicates_sources_by_url():
    first = make_result()
    second = make_result().model_copy(
        update={
            "chunk_id": uuid4(),
            "document_id": first.document_id,
            "url": first.url,
            "title": "중복 휴학 안내",
        }
    )

    result = await generate_answer(
        question="휴학은?",
        category="academic",
        retrieval_results=[first, second],
        conflict_warning=ConflictWarning(exists=False),
        provider=StaticLLMProvider("휴학 신청은 포털에서 신청합니다."),
        stale_days=180,
    )

    assert len(result.sources) == 1
    assert result.sources[0].chunk_id == str(first.chunk_id)
    assert result.sources[0].title == "휴학 안내"


@pytest.mark.asyncio
async def test_generate_answer_without_retrieval_results_does_not_call_provider():
    result = await generate_answer(
        question="휴학은?",
        category="academic",
        retrieval_results=[],
        conflict_warning=ConflictWarning(exists=True, description="충돌"),
        provider=FailingProvider(),
        stale_days=180,
    )

    assert result.answer == "검색된 공식 문서 근거가 부족해 답변할 수 없습니다."
    assert result.sources == []
    assert result.procedure_steps == []
    assert result.conflict_warning.exists is True
    assert result.freshness == "stale"


@pytest.mark.asyncio
async def test_generate_answer_uses_menu_path_for_source_title_and_marks_naive_crawled_at_utc():
    result = await generate_answer(
        question="휴학은?",
        category="academic",
        retrieval_results=[make_result(title=None, crawled_at=datetime(2026, 5, 1, 12, 0, 0))],
        conflict_warning=ConflictWarning(exists=False),
        provider=StaticLLMProvider("휴학 신청은 포털에서 신청합니다."),
        stale_days=180,
    )

    assert result.sources[0].title == "학사 > 휴학"
    assert result.sources[0].crawled_at == "2026-05-01T12:00:00+00:00"


def test_extract_procedure_steps_keeps_numbered_steps():
    assert extract_procedure_steps("1. 포털에 로그인합니다.\n2. 휴학 메뉴를 선택합니다.") == [
        "포털에 로그인합니다",
        "휴학 메뉴를 선택합니다",
    ]


def test_extract_procedure_steps_ignores_non_procedure_bullets():
    assert extract_procedure_steps("- 준비물: 신분증\n- 포털에 로그인합니다.") == ["포털에 로그인합니다"]
