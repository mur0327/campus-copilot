"""발행할 qrel v4의 구조·판정·근거 불변식을 검사한다."""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.make_v4_pool import (  # noqa: E402
    CHUNK_FIELDS,
    DB_DSN,
    RETRIEVAL_PATHS,
    load_jsonl,
    top_k_items,
)
from eval.run_questions import content_signature, normalize_url  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"
GOLD_PAGES_PATH = EVAL_DIR / "gold_pages_v4.csv"
GOLD_EVIDENCE_PATH = EVAL_DIR / "gold_evidence_v4.csv"
QUESTION_JUDGMENTS_PATH = EVAL_DIR / "question_judgments_v4.csv"
QUESTIONS_PATH = EVAL_DIR / "questions.csv"

SUPPORT_GRADES = frozenset({"full", "partial", "invalid"})
TEMPORAL_VALUES = frozenset({"current", "stale", "unknown"})
AUDIENCE_VALUES = frozenset({"match", "mismatch", "unknown"})
EVIDENCE_GRADES = frozenset({"full", "partial"})
EVIDENCE_TYPES = frozenset({"text_chunk", "page_navigation"})
POOL_SUPPORT_VALUES = frozenset({"full", "partial", "none"})
EXPECTED_BEHAVIORS = frozenset({"full_answer", "qualified_answer", "abstain"})
REASONS = frozenset(
    {
        "acquisition_failure",
        "absent",
        "missing_required_claim",
        "stale",
        "audience_mismatch",
        "personalized",
        "policy_exclusion",
    }
)
REASON_PRIORITY = {
    "acquisition_failure": 0,
    "absent": 1,
    "missing_required_claim": 1,
    "stale": 2,
    "audience_mismatch": 2,
    "personalized": 3,
    "policy_exclusion": 4,
}

PAGE_REQUIRED_FIELDS = (
    "question_id",
    "canonical_url",
    "provenance",
    "judged",
    "support_grade",
    "temporal_validity",
    "audience_scope",
    "notes",
)
QUESTION_FIELDS = (
    "question_id",
    "pool_support",
    "expected_behavior",
    "primary_reason",
    "secondary_reasons",
    "composition_override",
    "composition_sources",
    "notes",
)


@dataclass(frozen=True)
class ActualChunk:
    canonical_url: str
    content_hash: str


def load_csv(path: Path, required_fields: Sequence[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = set(reader.fieldnames or [])
        missing = set(required_fields) - fieldnames
        if missing:
            raise ValueError(f"{path}: 필수 컬럼 누락: {', '.join(sorted(missing))}")
        return [dict(row) for row in reader]


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def split_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split("|") if item.strip()]


def derive_pool_support(page_rows: Iterable[Mapping[str, Any]]) -> str:
    grades = {str(row.get("support_grade") or "") for row in page_rows}
    if "full" in grades:
        return "full"
    if "partial" in grades:
        return "partial"
    return "none"


def collect_top5_pairs(
    retrieval_paths: Sequence[Path] = RETRIEVAL_PATHS,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    page_pairs: set[tuple[str, str]] = set()
    chunk_pairs: set[tuple[str, str]] = set()
    for path in retrieval_paths:
        for row in load_jsonl(path):
            for item in top_k_items(row):
                page_pairs.add((row["id"], normalize_url(item["url"])))
                chunk_pairs.add((row["id"], str(item["chunk_id"])))
    return page_pairs, chunk_pairs


def _add_duplicate_failures(
    rows: Iterable[Mapping[str, Any]],
    *,
    key_fields: Sequence[str],
    label: str,
    failures: list[str],
) -> None:
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in key_fields)
        if key in seen:
            failures.append(f"[schema] {'|'.join(key)}: {label} 중복 행")
        seen.add(key)


def find_invariant_failures(
    page_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
    question_rows: list[dict[str, str]],
    *,
    top5_page_pairs: set[tuple[str, str]],
    top5_chunk_pairs: set[tuple[str, str]],
    actual_chunks: Mapping[str, ActualChunk],
    expected_question_ids: set[str] | None = None,
) -> list[str]:
    """순수 입력만 받아 모든 실패를 한 번에 반환한다."""

    failures: list[str] = []
    _add_duplicate_failures(
        page_rows,
        key_fields=("question_id", "canonical_url"),
        label="페이지",
        failures=failures,
    )
    _add_duplicate_failures(
        evidence_rows,
        key_fields=("question_id", "chunk_id"),
        label="근거",
        failures=failures,
    )
    _add_duplicate_failures(
        question_rows,
        key_fields=("question_id",),
        label="질문",
        failures=failures,
    )

    page_index: dict[tuple[str, str], dict[str, str]] = {}
    pages_by_question: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in page_rows:
        question_id = row["question_id"]
        canonical_url = normalize_url(row["canonical_url"])
        row_id = f"{question_id}|{canonical_url}"
        page_index[(question_id, canonical_url)] = row
        pages_by_question[question_id].append(row)

        judged = parse_bool(row.get("judged"))
        if judged is not True:
            failures.append(f"[I10] {row_id}: 페이지가 unjudged 상태입니다")
        if row.get("support_grade") not in SUPPORT_GRADES:
            failures.append(f"[schema] {row_id}: support_grade 값이 올바르지 않습니다")
        if row.get("temporal_validity") not in TEMPORAL_VALUES:
            failures.append(f"[schema] {row_id}: temporal_validity 값이 올바르지 않습니다")
        if row.get("audience_scope") not in AUDIENCE_VALUES:
            failures.append(f"[schema] {row_id}: audience_scope 값이 올바르지 않습니다")

    evidence_index: dict[tuple[str, str], dict[str, str]] = {}
    evidence_by_page: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in evidence_rows:
        question_id = row["question_id"]
        canonical_url = normalize_url(row["canonical_url"])
        chunk_id = row["chunk_id"]
        row_id = f"{question_id}|{chunk_id}"
        evidence_index[(question_id, chunk_id)] = row
        evidence_by_page[(question_id, canonical_url)].append(row)

        judged = parse_bool(row.get("judged"))
        if judged is not True:
            failures.append(f"[I10] {row_id}: 근거가 unjudged 상태입니다")

        grade = row.get("evidence_grade") or ""
        evidence_type = row.get("evidence_type") or ""
        if grade and grade not in EVIDENCE_GRADES:
            failures.append(f"[schema] {row_id}: evidence_grade 값이 올바르지 않습니다")
        if evidence_type and evidence_type not in EVIDENCE_TYPES:
            failures.append(f"[schema] {row_id}: evidence_type 값이 올바르지 않습니다")
        if grade and not evidence_type:
            failures.append(f"[schema] {row_id}: 양성 근거에 evidence_type이 없습니다")
        if not grade and evidence_type:
            failures.append(f"[schema] {row_id}: evidence_type은 evidence_grade와 함께 써야 합니다")
        if (question_id, canonical_url) not in page_index:
            failures.append(f"[schema] {row_id}: 대응하는 페이지 행이 없습니다")

    question_index = {row["question_id"]: row for row in question_rows}

    # 1. 세 실행의 모든 top-5 페이지를 명시적으로 판정해야 한다.
    for question_id, canonical_url in sorted(top5_page_pairs):
        row = page_index.get((question_id, canonical_url))
        if row is None:
            failures.append(f"[I01] {question_id}|{canonical_url}: top-5 페이지 누락")
        elif parse_bool(row.get("judged")) is not True:
            failures.append(f"[I01] {question_id}|{canonical_url}: top-5 페이지 미판정")

    # 2. 세 실행의 모든 top-5 청크를 명시적으로 판정해야 한다.
    for question_id, chunk_id in sorted(top5_chunk_pairs):
        row = evidence_index.get((question_id, chunk_id))
        if row is None:
            failures.append(f"[I02] {question_id}|{chunk_id}: top-5 청크 누락")
        elif parse_bool(row.get("judged")) is not True:
            failures.append(f"[I02] {question_id}|{chunk_id}: top-5 청크 미판정")

    # 3. 질문 support는 페이지 최대 등급에서 파생한다.
    for question_id, question in sorted(question_index.items()):
        row_id = question_id
        pool_support = question.get("pool_support") or ""
        if pool_support not in POOL_SUPPORT_VALUES:
            failures.append(f"[schema] {row_id}: pool_support 값이 올바르지 않습니다")
        override = parse_bool(question.get("composition_override"))
        if override is None:
            failures.append(f"[schema] {row_id}: composition_override가 불리언이 아닙니다")
            override = False
        derived = derive_pool_support(pages_by_question.get(question_id, []))
        if override:
            if not split_values(question.get("composition_sources")):
                failures.append(f"[I03] {row_id}: composition_override에 composition_sources가 없습니다")
        elif pool_support != derived:
            failures.append(f"[I03] {row_id}: pool_support={pool_support}, 페이지 파생값={derived}")

    # 4~5. 페이지 양성/음성과 근거 양성의 관계를 검사한다.
    for (question_id, canonical_url), page in sorted(page_index.items()):
        row_id = f"{question_id}|{canonical_url}"
        page_evidence = evidence_by_page.get((question_id, canonical_url), [])
        positive = [row for row in page_evidence if row.get("evidence_grade")]
        has_navigation = any(row.get("evidence_type") == "page_navigation" for row in page_evidence)
        if page.get("support_grade") in {"full", "partial"}:
            if not positive and not has_navigation:
                failures.append(f"[I04] {row_id}: 양성 페이지에 gold evidence가 없습니다")
        elif page.get("support_grade") == "invalid" and positive:
            chunk_ids = ",".join(row["chunk_id"] for row in positive)
            failures.append(f"[I05] {row_id}: invalid 페이지에 gold evidence 존재: {chunk_ids}")

    # 6. 양성 청크의 URL과 내용 해시가 현재 DB 스냅샷과 같아야 한다.
    for row in evidence_rows:
        if not row.get("evidence_grade"):
            continue
        question_id = row["question_id"]
        chunk_id = row["chunk_id"]
        row_id = f"{question_id}|{chunk_id}"
        actual = actual_chunks.get(chunk_id)
        if actual is None:
            failures.append(f"[I06] {row_id}: DB에서 gold chunk를 찾지 못했습니다")
            continue
        if normalize_url(row["canonical_url"]) != actual.canonical_url:
            failures.append(f"[I06] {row_id}: gold chunk가 해당 URL 소속이 아닙니다")
        if row.get("content_hash") != actual.content_hash:
            failures.append(f"[I06] {row_id}: content_hash가 DB 본문과 다릅니다")

    for question_id, question in sorted(question_index.items()):
        pages = pages_by_question.get(question_id, [])
        expected_behavior = question.get("expected_behavior") or ""
        if expected_behavior not in EXPECTED_BEHAVIORS:
            failures.append(f"[schema] {question_id}: expected_behavior 값이 올바르지 않습니다")

        deployable_full = any(
            page.get("support_grade") == "full"
            and page.get("temporal_validity") == "current"
            and page.get("audience_scope") == "match"
            for page in pages
        )
        deployable_any = any(
            page.get("support_grade") in {"full", "partial"}
            and page.get("temporal_validity") == "current"
            and page.get("audience_scope") == "match"
            for page in pages
        )
        audience_match_any = any(
            page.get("support_grade") in {"full", "partial"} and page.get("audience_scope") == "match" for page in pages
        )

        # 7. 완전 답변은 현재·대상 일치 full 근거를 요구한다.
        if expected_behavior == "full_answer" and not deployable_full:
            failures.append(f"[I07] {question_id}: full_answer에 current+match full 페이지가 없습니다")

        primary = question.get("primary_reason") or ""
        secondary = split_values(question.get("secondary_reasons"))
        reasons = ([primary] if primary else []) + secondary

        # 8~9. stale/대상 불일치 거절은 쓸 수 있는 대체 근거가 없어야 한다.
        if expected_behavior == "abstain" and "stale" in reasons and deployable_any:
            failures.append(f"[I08] {question_id}: stale 거절인데 current+match 대체 근거가 있습니다")
        if expected_behavior == "abstain" and "audience_mismatch" in reasons and audience_match_any:
            failures.append(f"[I09] {question_id}: audience_mismatch 거절인데 match 대체 근거가 있습니다")

        # 11. reason enum, 단일 primary, 우선순위, abstain 조합을 잠근다.
        invalid_reasons = sorted(set(reasons) - REASONS)
        if invalid_reasons:
            failures.append(f"[I11] {question_id}: reason enum 위반: {','.join(invalid_reasons)}")
        if len(secondary) != len(set(secondary)) or primary in secondary:
            failures.append(f"[I11] {question_id}: reason이 중복됐습니다")
        if expected_behavior not in {"abstain", "qualified_answer"} and reasons:
            failures.append(f"[I11] {question_id}: full_answer인데 reason이 있습니다")
        if expected_behavior == "abstain" and not primary:
            failures.append(f"[I11] {question_id}: abstain에 primary_reason이 없습니다")
        if expected_behavior == "abstain" and deployable_full and "policy_exclusion" not in reasons:
            failures.append(f"[I11] {question_id}: deployable full 근거가 있는데 abstain입니다")
        valid_reasons = [reason for reason in reasons if reason in REASON_PRIORITY]
        if primary in REASON_PRIORITY and valid_reasons:
            highest_priority = min(REASON_PRIORITY[reason] for reason in valid_reasons)
            if REASON_PRIORITY[primary] != highest_priority:
                failures.append(f"[I11] {question_id}: primary_reason이 우선순위 규칙과 다릅니다")

    # 질문셋과 발행본의 누락·잉여를 함께 잡는다.
    if expected_question_ids is not None:
        actual_question_ids = set(question_index)
        for question_id in sorted(expected_question_ids - actual_question_ids):
            failures.append(f"[schema] {question_id}: 질문 수준 판정 행 누락")
        for question_id in sorted(actual_question_ids - expected_question_ids):
            failures.append(f"[schema] {question_id}: questions.csv에 없는 질문 판정")

    # 12. 의도된 중복 문항도 별도 식별자로 각각 판정돼야 한다.
    for question_id in ("Q011", "Q035"):
        if question_id not in question_index:
            failures.append(f"[I12] {question_id}: 중복 문항의 질문 판정이 없습니다")
        if question_id not in pages_by_question:
            failures.append(f"[I12] {question_id}: 중복 문항의 페이지 판정이 없습니다")

    return failures


async def load_actual_chunks(
    evidence_rows: Iterable[Mapping[str, Any]],
    *,
    dsn: str = DB_DSN,
) -> dict[str, ActualChunk]:
    chunk_ids = sorted(
        {str(row.get("chunk_id") or "") for row in evidence_rows if row.get("evidence_grade") and row.get("chunk_id")}
    )
    if not chunk_ids:
        return {}

    parsed_ids: list[uuid.UUID] = []
    for chunk_id in chunk_ids:
        try:
            parsed_ids.append(uuid.UUID(chunk_id))
        except ValueError:
            continue

    connection = await asyncpg.connect(dsn)
    try:
        records = await connection.fetch(
            """
            SELECT c.id, c.content, d.url
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.id = ANY($1::uuid[])
            """,
            parsed_ids,
        )
    finally:
        await connection.close()
    return {
        str(record["id"]): ActualChunk(
            canonical_url=normalize_url(record["url"]),
            content_hash=content_signature(record["content"]),
        )
        for record in records
    }


def load_question_ids(path: Path = QUESTIONS_PATH) -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        return {row["id"] for row in csv.DictReader(input_file)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="qrel v4 발행 불변식을 검사합니다.")
    parser.add_argument("--pages", type=Path, default=GOLD_PAGES_PATH)
    parser.add_argument("--evidence", type=Path, default=GOLD_EVIDENCE_PATH)
    parser.add_argument("--questions", type=Path, default=QUESTION_JUDGMENTS_PATH)
    parser.add_argument("--db-dsn", default=DB_DSN)
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    pages = load_csv(args.pages, PAGE_REQUIRED_FIELDS)
    evidence = load_csv(args.evidence, CHUNK_FIELDS)
    questions = load_csv(args.questions, QUESTION_FIELDS)
    top5_pages, top5_chunks = collect_top5_pairs()
    actual_chunks = await load_actual_chunks(evidence, dsn=args.db_dsn)
    failures = find_invariant_failures(
        pages,
        evidence,
        questions,
        top5_page_pairs=top5_pages,
        top5_chunk_pairs=top5_chunks,
        actual_chunks=actual_chunks,
        expected_question_ids=load_question_ids(),
    )
    if failures:
        print(f"qrel v4 invariant 실패: {len(failures)}건")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print(f"qrel v4 invariant 통과: 페이지 {len(pages)}행, 근거 {len(evidence)}행, 질문 {len(questions)}행")


if __name__ == "__main__":
    asyncio.run(run())
