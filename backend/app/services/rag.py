import re
from datetime import UTC, datetime

from app.schemas.chat import ChatResponse, ConflictWarning, Source
from app.services.freshness import calculate_source_freshness, calculate_top_level_freshness
from app.services.llm import LLMMessage, LLMProvider
from app.services.retriever import RetrievalResult


NO_GROUNDED_CONTEXT_ANSWER = "검색된 공식 문서 근거가 부족해 답변할 수 없습니다."
PROCEDURE_KEYWORDS = (
    "신청",
    "로그인",
    "제출",
    "선택",
    "확인",
    "방문",
    "작성",
    "업로드",
    "납부",
    "발급",
    "출력",
    "접수",
)


def build_prompt_messages(
    question: str,
    retrieval_results: list[RetrievalResult],
    conflict_warning: ConflictWarning,
) -> list[LLMMessage]:
    context = "\n\n".join(
        f"[{index + 1}] {result.title or result.url}\n{result.content}"
        for index, result in enumerate(retrieval_results)
    )
    conflict_text = ""
    if conflict_warning.exists:
        description = conflict_warning.description or "검색 결과에 서로 다른 공식 문서 내용이 포함되어 있습니다."
        conflict_text = f"\n\n충돌 주의: {description}"

    return [
        LLMMessage(
            role="system",
            content=(
                "검색된 공식 문서 근거만 사용해 한국어 존댓말로 답변하세요. "
                "근거가 부족하면 부족하다고 말하세요."
                f"{conflict_text}"
            ),
        ),
        LLMMessage(role="user", content=f"질문: {question}\n\n검색된 공식 문서:\n{context}"),
    ]


def extract_procedure_steps(answer: str) -> list[str]:
    steps = []
    for line in answer.splitlines():
        stripped = line.strip()
        if not re.match(r"^(-|\d+[.)])\s+", stripped):
            continue
        step = re.sub(r"^(-|\d+[.)])\s+", "", stripped).strip()
        step = step.rstrip(".。")
        if step and any(keyword in step for keyword in PROCEDURE_KEYWORDS):
            steps.append(step)
    return steps


async def generate_answer(
    *,
    question: str,
    category: str | None,
    retrieval_results: list[RetrievalResult],
    conflict_warning: ConflictWarning,
    provider: LLMProvider,
    stale_days: int,
) -> ChatResponse:
    if not retrieval_results:
        return ChatResponse(
            answer=NO_GROUNDED_CONTEXT_ANSWER,
            sources=[],
            procedure_steps=[],
            conflict_warning=conflict_warning,
            freshness="stale",
        )

    answer = await provider.generate(build_prompt_messages(question, retrieval_results, conflict_warning))
    sources = [_source_from_result(result, stale_days) for result in retrieval_results]
    freshness = calculate_top_level_freshness([source.freshness or "stale" for source in sources])

    return ChatResponse(
        answer=answer,
        sources=sources,
        procedure_steps=extract_procedure_steps(answer),
        conflict_warning=conflict_warning,
        freshness=freshness,
    )


def _source_from_result(result: RetrievalResult, stale_days: int) -> Source:
    freshness = calculate_source_freshness(result.crawled_at, stale_days)
    return Source(
        title=result.title or result.menu_path or result.url,
        url=result.url,
        crawled_at=_crawled_at_iso(result.crawled_at),
        freshness=freshness,
        chunk_id=str(result.chunk_id),
    )


def _crawled_at_iso(crawled_at: datetime | None) -> str:
    if crawled_at is None:
        return ""
    if crawled_at.tzinfo is None:
        crawled_at = crawled_at.replace(tzinfo=UTC)
    return crawled_at.isoformat()
