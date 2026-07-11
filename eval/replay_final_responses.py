"""Replay final RAG responses from stored EXP-02 evidence candidates."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_SOURCE_PATH = REPO_ROOT / "eval" / "results" / "retrieval-20260705-094816.jsonl"
DEFAULT_RESULTS_DIR = REPO_ROOT / "eval" / "results"
PROMPT_PATH = BACKEND_ROOT / "app" / "prompts" / "chat_answer.md"
TOPICALLY_ADJACENT_IDS = frozenset({"Q021", "Q023", "Q043"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay final responses from the stored EXP-02 evidence context.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_PATH,
        help="Retrieval JSONL containing the evidence candidates to replay.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory for replay JSONL and human judgment sheet outputs.",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="Replay only the first N selected questions.",
    )
    parser.add_argument(
        "--local-services",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use localhost defaults for the repo-level Postgres service.",
    )
    return parser.parse_args()


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def configure_runtime_env(*, local_services: bool) -> None:
    """Set import-time backend settings before importing app modules."""

    if local_services:
        os.environ["ENVIRONMENT"] = "production"
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot"
        )
        os.environ["CHROMA_HOST"] = "localhost"
        os.environ["CHROMA_PORT"] = "8001"
        os.environ["RETRIEVER_BM25_CACHE_DIR"] = str(REPO_ROOT / ".data" / "bm25")

    sys.path.insert(0, str(BACKEND_ROOT))


def content_signature(text: str | None) -> str:
    if not text:
        return ""
    normalized = " ".join(text.split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_replay_rows(path: Path, *, limit: int | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source_file:
        for line_number, line in enumerate(source_file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
            if (
                row.get("expected_answerability") == "insufficient"
                and len(row.get("evidence_candidates") or []) >= 1
            ):
                rows.append(row)

    if limit is None and len(rows) != 16:
        raise ValueError(f"expected 16 replay rows in {path}, found {len(rows)}")
    return rows[:limit] if limit is not None else rows


async def load_chunk_contents(session: Any, rows: list[dict[str, Any]]) -> dict[UUID, str]:
    from sqlalchemy import select

    from app.models.document import DocumentChunk

    chunk_ids = {
        UUID(candidate["chunk_id"])
        for row in rows
        for candidate in row["evidence_candidates"]
    }
    statement = select(DocumentChunk.id, DocumentChunk.content).where(
        DocumentChunk.id.in_(chunk_ids)
    )
    contents = dict((await session.execute(statement)).all())
    missing = sorted(str(chunk_id) for chunk_id in chunk_ids - contents.keys())
    if missing:
        raise ValueError(f"missing document chunks: {', '.join(missing)}")
    return contents


def reconstruct_evidence_candidates(
    stored_candidates: list[dict[str, Any]],
    chunk_contents: dict[UUID, str],
) -> tuple[list[Any], list[dict[str, Any]]]:
    from app.services.retriever import EvidenceCandidate, RetrievalResult

    candidates: list[EvidenceCandidate] = []
    evidence_metadata: list[dict[str, Any]] = []
    for stored in stored_candidates:
        chunk_id = UUID(stored["chunk_id"])
        content = chunk_contents[chunk_id]
        result = RetrievalResult(
            chunk_id=chunk_id,
            document_id=UUID(stored["document_id"]),
            content=content,
            chunk_type=stored["chunk_type"],
            chunk_index=stored.get("chunk_index"),
            score=stored["score"],
            relevance=stored.get("relevance"),
            title=stored.get("title"),
            url=stored["url"],
            menu_path=stored.get("menu_path"),
            category=stored.get("category"),
            source_scope=stored["source_scope"],
            page_kind=stored["page_kind"],
            crawled_at=stored.get("crawled_at"),
            meta=stored.get("meta"),
        )
        candidates.append(
            EvidenceCandidate(
                display_result=result,
                context_results=[result],
                source_number=stored["source_number"],
                overlap=stored["overlap"],
            )
        )
        evidence_metadata.append(
            {
                "source_number": stored["source_number"],
                "overlap": stored["overlap"],
                "url": stored["url"],
                "title": stored.get("title"),
                "sig_mismatch": content_signature(content) != stored.get("content_sig", ""),
            }
        )
    return candidates, evidence_metadata


def metadata_record(*, model: str, run_at: datetime, source_path: Path) -> dict[str, Any]:
    return {
        "record_type": "metadata",
        "gemini_model": model,
        "chat_answer_prompt_sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        "run_timestamp": run_at.isoformat(),
        "source_jsonl_path": display_path(source_path),
        "conflict_warning_fixed": {"exists": False, "description": None},
    }


def response_record(
    *,
    row: dict[str, Any],
    evidence_metadata: list[dict[str, Any]],
    draft: Any,
    response: Any,
) -> dict[str, Any]:
    final_payload = response.model_dump(mode="json")
    return {
        "record_type": "response",
        "id": row["id"],
        "question": row["question"],
        "evidence": evidence_metadata,
        "conflict_warning_fixed": {"exists": False, "description": None},
        "draft_answerability": draft.answerability,
        "final_answerability": response.answerability,
        "downgraded": draft.answerability != response.answerability,
        "answer": response.answer,
        "used_sources": [source.model_dump(mode="json") for source in response.sources],
        "final_response": final_payload,
    }


def judgment_section(record: dict[str, Any]) -> str:
    group = (
        "topically-adjacent"
        if record["id"] in TOPICALLY_ADJACENT_IDS
        else "clearly-irrelevant"
    )
    evidence_lines = "\n".join(
        f"- [{item['source_number']}] {item['title'] or '(제목 없음)'} — {item['url']}"
        for item in record["evidence"]
    )
    answer = record["answer"] or "(빈 응답)"
    return f"""## {record['id']}

- EXP-02 group: `{group}`
- 질문: {record['question']}

### 근거

{evidence_lines}

### 최종 답변

{answer}

### 사람 판정

- response behavior (답변/부분답변·확인권고/명시적거절):
- grounding (완전지지/일부지지/미지지·모순/무관):
- coverage type (public-document-absence/acquisition-failure/scope-policy-exclusion/personalized-system-information):
"""


def write_judgment_sheet(path: Path, records: list[dict[str, Any]], run_at: datetime) -> None:
    header = f"""# Leaked evidence final-response judgment

- 실행 시각: {run_at.isoformat()}
- 판정 대상: {len(records)}건

"""
    sections = "\n".join(judgment_section(record) for record in records)
    path.write_text(header + sections, encoding="utf-8")


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


async def run() -> None:
    args = parse_args()
    configure_runtime_env(local_services=args.local_services)

    from app.core.config import settings
    from app.core.db import AsyncSessionLocal, engine
    from app.schemas.chat import ConflictWarning, RetrievalStatusPayload
    from app.services.llm import GeminiProvider, validate_provider_settings
    from app.services.rag import assemble_chat_response, generate_answer_draft

    validate_provider_settings(
        "gemini",
        gemini_api_key=settings.gemini_api_key,
        gemini_model=settings.gemini_model,
    )
    rows = load_replay_rows(args.source, limit=args.limit)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    run_at = datetime.now(UTC)
    stamp = run_at.strftime("%Y%m%d-%H%M%S")
    jsonl_path = args.out_dir / f"final-response-{stamp}.jsonl"
    judgment_path = args.out_dir / f"final-response-judgment-{stamp}.md"
    conflict_warning = ConflictWarning(exists=False)
    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    records: list[dict[str, Any]] = []

    try:
        async with AsyncSessionLocal() as session:
            chunk_contents = await load_chunk_contents(session, rows)

        with jsonl_path.open("w", encoding="utf-8") as output_file:
            output_file.write(
                json.dumps(
                    metadata_record(
                        model=settings.gemini_model,
                        run_at=run_at,
                        source_path=args.source,
                    ),
                    ensure_ascii=False,
                )
                + "\n"
            )
            for row in rows:
                evidence_candidates, evidence_metadata = reconstruct_evidence_candidates(
                    row["evidence_candidates"], chunk_contents
                )
                draft = await generate_answer_draft(
                    question=row["question"],
                    evidence_candidates=evidence_candidates,
                    conflict_warning=conflict_warning,
                    provider=provider,
                )
                response = assemble_chat_response(
                    draft=draft,
                    evidence_candidates=evidence_candidates,
                    conflict_warning=conflict_warning,
                    stale_days=settings.freshness_stale_days,
                    retrieval_status=RetrievalStatusPayload(**row["retrieval_status"]),
                )
                record = response_record(
                    row=row,
                    evidence_metadata=evidence_metadata,
                    draft=draft,
                    response=response,
                )
                records.append(record)
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

        write_judgment_sheet(judgment_path, records, run_at)
    finally:
        await provider.aclose()
        await engine.dispose()

    print(f"jsonl: {display_path(jsonl_path)}")
    print(f"judgment: {display_path(judgment_path)}")


if __name__ == "__main__":
    asyncio.run(run())
