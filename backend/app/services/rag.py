import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.schemas.chat import ChatResponse, ConflictWarning, RetrievalStatusPayload, Source
from app.services.freshness import calculate_source_freshness, calculate_top_level_freshness
from app.services.llm import LLMMessage, LLMProvider
from app.services.query_log import redact_private_identifiers
from app.services.retriever import (
    EVIDENCE_PREVIEW_CHARS,
    EvidenceCandidate,
    RetrievalResult,
    classify_question_intent,
    filter_evidence_candidates,
)

NO_GROUNDED_CONTEXT_ANSWER = "검색된 공식 문서에서 답변 근거를 확인하지 못했습니다."
JSON_VALIDATION_ERROR_ANSWER = "답변을 확인하는 중 문제가 발생했습니다. 다시 질문해 주세요."
PROMPT_VERSION = "chat-answer-json-v1"
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat_answer.md"
SOURCE_NUMBER_RE = re.compile(r"\[\d+]")


class LLMOutputValidationError(RuntimeError):
    pass


class AnswerDraft(BaseModel):
    answerability: Literal["answerable", "partial", "insufficient"]
    summary: str
    procedure_steps: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    used_source_numbers: list[int] = Field(default_factory=list)


def build_prompt_messages(
    question: str,
    retrieval_results: list[RetrievalResult],
    conflict_warning: ConflictWarning,
) -> list[LLMMessage]:
    candidates = filter_evidence_candidates(question, retrieval_results)
    return build_prompt_messages_from_candidates(
        question=question,
        evidence_candidates=candidates,
        conflict_warning=conflict_warning,
    )


def build_prompt_messages_from_candidates(
    *,
    question: str,
    evidence_candidates: list[EvidenceCandidate],
    conflict_warning: ConflictWarning,
) -> list[LLMMessage]:
    template = _load_prompt_template()
    prompt = _render_template(
        template,
        {
            "question": question,
            "question_intent": classify_question_intent(question),
            "conflict_warning": _conflict_text(conflict_warning),
            "evidence_context": _evidence_context(evidence_candidates),
        },
    )
    return [LLMMessage(role="system", content=prompt)]


async def generate_answer(
    *,
    question: str,
    category: str | None,
    retrieval_results: list[RetrievalResult],
    conflict_warning: ConflictWarning,
    provider: LLMProvider,
    stale_days: int,
    retrieval_status: RetrievalStatusPayload | None = None,
) -> ChatResponse:
    evidence_candidates = filter_evidence_candidates(question, retrieval_results)
    status = _status_with_counts(
        retrieval_status or RetrievalStatusPayload(mode="hybrid" if retrieval_results else "empty"),
        evidence_candidate_count=len(evidence_candidates),
        display_source_count=0,
        answerability="insufficient",
    )
    if not evidence_candidates:
        return insufficient_response(
            conflict_warning=conflict_warning,
            retrieval_status=status,
        )

    draft = await generate_answer_draft(
        question=question,
        evidence_candidates=evidence_candidates,
        conflict_warning=conflict_warning,
        provider=provider,
    )
    return assemble_chat_response(
        draft=draft,
        evidence_candidates=evidence_candidates,
        conflict_warning=conflict_warning,
        stale_days=stale_days,
        retrieval_status=status,
    )


async def generate_answer_draft(
    *,
    question: str,
    evidence_candidates: list[EvidenceCandidate],
    conflict_warning: ConflictWarning,
    provider: LLMProvider,
) -> AnswerDraft:
    messages = build_prompt_messages_from_candidates(
        question=question,
        evidence_candidates=evidence_candidates,
        conflict_warning=conflict_warning,
    )
    raw_output = await provider.generate(messages)
    try:
        return parse_answer_draft(raw_output)
    except LLMOutputValidationError:
        repair_messages = [
            *messages,
            LLMMessage(
                role="user",
                content=(
                    "이전 출력은 유효한 JSON schema를 만족하지 않았습니다. "
                    "설명 없이 JSON 객체만 다시 출력하세요."
                ),
            ),
        ]
        try:
            return parse_answer_draft(await provider.generate(repair_messages))
        except LLMOutputValidationError as exc:
            raise LLMOutputValidationError("json_validation_failed") from exc


def parse_answer_draft(raw_output: str) -> AnswerDraft:
    try:
        return AnswerDraft.model_validate_json(raw_output)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise LLMOutputValidationError("json_validation_failed") from exc


def assemble_chat_response(
    *,
    draft: AnswerDraft,
    evidence_candidates: list[EvidenceCandidate],
    conflict_warning: ConflictWarning,
    stale_days: int,
    retrieval_status: RetrievalStatusPayload,
) -> ChatResponse:
    used_source_numbers = validate_used_source_numbers(
        draft.used_source_numbers,
        candidate_count=len(evidence_candidates),
        answerability=draft.answerability,
    )
    answerability = draft.answerability
    downgraded_due_to_sources = False
    if answerability in {"answerable", "partial"} and not used_source_numbers:
        answerability = "insufficient"
        downgraded_due_to_sources = True

    if answerability == "insufficient":
        used_source_numbers = []
        sources: list[Source] = []
        procedure_steps: list[str] = []
        summary = (
            NO_GROUNDED_CONTEXT_ANSWER
            if downgraded_due_to_sources
            else draft.summary or NO_GROUNDED_CONTEXT_ANSWER
        )
    else:
        sources = [
            _source_from_result(evidence_candidates[number - 1].display_result, stale_days)
            for number in used_source_numbers
        ]
        procedure_steps = _clean_text_list(draft.procedure_steps)
        summary = draft.summary

    notes = _clean_text_list(draft.notes)
    limitations = _clean_text_list(draft.limitations)
    if answerability == "insufficient":
        notes = []

    freshness = (
        calculate_top_level_freshness([source.freshness or "stale" for source in sources])
        if sources
        else "stale"
    )
    retrieval_status = _status_with_counts(
        retrieval_status,
        evidence_candidate_count=len(evidence_candidates),
        display_source_count=len(sources),
        answerability=answerability,
    )
    return ChatResponse(
        answerability=answerability,
        answer=assemble_answer_text(
            summary=summary,
            procedure_steps=procedure_steps,
            notes=notes,
            limitations=limitations,
        ),
        summary=_strip_source_numbers(summary),
        sources=sources,
        procedure_steps=procedure_steps,
        notes=notes,
        limitations=limitations,
        conflict_warning=conflict_warning,
        freshness=freshness,
        retrieval_status=retrieval_status,
    )


def insufficient_response(
    *,
    conflict_warning: ConflictWarning,
    retrieval_status: RetrievalStatusPayload | None = None,
    summary: str = NO_GROUNDED_CONTEXT_ANSWER,
    limitations: list[str] | None = None,
) -> ChatResponse:
    status = _status_with_counts(
        retrieval_status or RetrievalStatusPayload(mode="empty"),
        evidence_candidate_count=0,
        display_source_count=0,
        answerability="insufficient",
    )
    clean_limitations = _clean_text_list(limitations or [])
    return ChatResponse(
        answerability="insufficient",
        answer=assemble_answer_text(
            summary=summary,
            procedure_steps=[],
            notes=[],
            limitations=clean_limitations,
        ),
        summary=summary,
        sources=[],
        procedure_steps=[],
        notes=[],
        limitations=clean_limitations,
        conflict_warning=conflict_warning,
        freshness="stale",
        retrieval_status=status,
    )


def validate_used_source_numbers(
    used_source_numbers: list[int],
    *,
    candidate_count: int,
    answerability: str,
) -> list[int]:
    if answerability == "insufficient":
        return []
    validated: list[int] = []
    for number in used_source_numbers:
        if number < 1 or number > candidate_count or number in validated:
            continue
        validated.append(number)
    return validated


def assemble_answer_text(
    *,
    summary: str,
    procedure_steps: list[str],
    notes: list[str],
    limitations: list[str],
) -> str:
    sections = [_strip_source_numbers(summary).strip()]
    procedure_steps = _clean_text_list(procedure_steps)
    notes = _clean_text_list(notes)
    limitations = _clean_text_list(limitations)
    if procedure_steps:
        sections.append(
            "확인된 절차\n"
            + "\n".join(f"{index + 1}. {step}" for index, step in enumerate(procedure_steps))
        )
    if notes:
        sections.append("준비/주의사항\n" + "\n".join(f"- {note}" for note in notes))
    if limitations:
        sections.append("확인이 필요한 점\n" + "\n".join(f"- {item}" for item in limitations))
    return "\n\n".join(section for section in sections if section.strip())


def sources_from_results(retrieval_results: list[RetrievalResult], stale_days: int) -> list[Source]:
    return dedupe_sources_by_url([_source_from_result(result, stale_days) for result in retrieval_results])


def dedupe_sources_by_url(source_items: list[Source]) -> list[Source]:
    sources: list[Source] = []
    seen_urls: set[str] = set()
    for source in source_items:
        if source.url in seen_urls:
            continue
        seen_urls.add(source.url)
        sources.append(source)
    return sources


def _source_from_result(result: RetrievalResult, stale_days: int) -> Source:
    freshness = calculate_source_freshness(result.crawled_at, stale_days)
    return Source(
        title=result.title or result.menu_path or result.url,
        url=result.url,
        crawled_at=_crawled_at_iso(result.crawled_at),
        freshness=freshness,
        chunk_id=str(result.chunk_id),
    )


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def _conflict_text(conflict_warning: ConflictWarning) -> str:
    if not conflict_warning.exists:
        return "충돌 없음"
    return conflict_warning.description or "검색 결과에 서로 다른 공식 문서 내용이 포함되어 있습니다."


def _evidence_context(evidence_candidates: list[EvidenceCandidate]) -> str:
    blocks = []
    for candidate in evidence_candidates:
        result = candidate.display_result
        content = "\n\n".join(context.content for context in candidate.context_results)
        blocks.append(
            "\n".join(
                [
                    f"[{candidate.source_number}] {result.title or result.menu_path or result.url}",
                    f"URL: {result.url}",
                    f"메뉴: {result.menu_path or ''}",
                    f"내용: {content}",
                ]
            )
        )
    return "\n\n".join(blocks)


def retrieval_candidate_log_items(results: list[RetrievalResult]) -> list[dict[str, Any]]:
    items = []
    for result in results[:8]:
        items.append(
            {
                "chunk_id": str(result.chunk_id),
                "title": result.title or result.menu_path or result.url,
                "url": result.url,
                "score": result.score,
                "chunk_type": result.chunk_type,
                "preview": _preview(result.content),
            }
        )
    return items


def _preview(content: str) -> str:
    collapsed = re.sub(r"\s+", " ", content).strip()
    return redact_private_identifiers(collapsed)[:EVIDENCE_PREVIEW_CHARS]


def _clean_text_list(items: list[str]) -> list[str]:
    return [_strip_source_numbers(item).strip() for item in items if _strip_source_numbers(item).strip()]


def _strip_source_numbers(text: str) -> str:
    return SOURCE_NUMBER_RE.sub("", text).strip()


def _status_with_counts(
    status: RetrievalStatusPayload,
    *,
    evidence_candidate_count: int,
    display_source_count: int,
    answerability: str,
) -> RetrievalStatusPayload:
    return status.model_copy(
        update={
            "evidence_candidate_count": evidence_candidate_count,
            "display_source_count": display_source_count,
            "answerability": answerability,
        }
    )


def _crawled_at_iso(crawled_at: datetime | None) -> str:
    if crawled_at is None:
        return ""
    if crawled_at.tzinfo is None:
        crawled_at = crawled_at.replace(tzinfo=UTC)
    return crawled_at.isoformat()
