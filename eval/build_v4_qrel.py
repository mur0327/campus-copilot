"""최종 adjudicated JSON을 qrel v4 발행 CSV로 변환한다.

pool 행의 식별자와 동결 hash는 그대로 두고 판정값만 병합한다. 모든 invariant가
통과하기 전에는 발행 파일을 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.check_v4_invariants import (  # noqa: E402
    PAGE_REQUIRED_FIELDS,
    QUESTION_FIELDS,
    collect_top5_pairs,
    derive_pool_support,
    find_invariant_failures,
    load_actual_chunks,
    load_csv,
    load_question_ids,
    parse_bool,
    split_values,
)
from eval.make_v4_pool import (  # noqa: E402
    CHUNK_FIELDS,
    CHUNK_POOL_PATH,
    DB_DSN,
    PAGE_FIELDS,
    PAGE_POOL_PATH,
    write_csv_atomic,
)
from eval.run_questions import normalize_url  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"
ADJUDICATED_PATH = EVAL_DIR / "qrel-v4-adjudicated.json"
QUESTIONS_PATH = EVAL_DIR / "questions.csv"
GOLD_PAGES_PATH = EVAL_DIR / "gold_pages_v4.csv"
GOLD_EVIDENCE_PATH = EVAL_DIR / "gold_evidence_v4.csv"
QUESTION_JUDGMENTS_PATH = EVAL_DIR / "question_judgments_v4.csv"
JUDGMENT_SCHEMA_VERSION = "qrel-v4-judgment-1"
JUDGMENT_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "audit",
        "judge",
        "date",
        "exported_at",
        "pages",
        "evidence",
        "questions",
    }
)
JUDGMENT_ROW_FIELDS = {
    "pages": frozenset(
        {
            "row_id",
            "question_id",
            "canonical_url",
            "judged",
            "support_grade",
            "temporal_validity",
            "audience_scope",
            "notes",
        }
    ),
    "evidence": frozenset(
        {
            "row_id",
            "question_id",
            "canonical_url",
            "chunk_id",
            "judged",
            "evidence_grade",
            "evidence_type",
            "notes",
        }
    ),
    "questions": frozenset(
        {
            "row_id",
            "question_id",
            "judged",
            "expected_behavior",
            "primary_reason",
            "secondary_reasons",
            "composition_override",
            "pool_support",
            "composition_sources",
            "notes",
        }
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: 최상위 JSON은 객체여야 합니다")
    validate_judgment_payload(payload, path=path)
    return payload


def validate_judgment_payload(
    payload: Mapping[str, Any],
    *,
    path: Path | None = None,
) -> None:
    """primary·secondary·adjudicated가 공유하는 시트 JSON 계약을 검사한다."""

    label = str(path) if path else "판정 JSON"
    missing = JUDGMENT_TOP_LEVEL_FIELDS - set(payload)
    if missing:
        raise ValueError(f"{label}: 공통 스키마 필드 누락: {', '.join(sorted(missing))}")
    if payload.get("schema_version") != JUDGMENT_SCHEMA_VERSION:
        raise ValueError(f"{label}: schema_version이 {JUDGMENT_SCHEMA_VERSION}이 아닙니다")
    if not isinstance(payload.get("audit"), bool):
        raise ValueError(f"{label}: audit는 불리언이어야 합니다")
    for field in ("judge", "date", "exported_at"):
        if not isinstance(payload.get(field), str):
            raise ValueError(f"{label}: {field}는 문자열이어야 합니다")
    for field in ("pages", "evidence", "questions"):
        value = payload.get(field)
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError(f"{label}: {field}는 객체 배열이어야 합니다")
        for index, row in enumerate(value):
            missing_row_fields = JUDGMENT_ROW_FIELDS[field] - set(row)
            if missing_row_fields:
                raise ValueError(
                    f"{label}: {field}[{index}] 공통 스키마 필드 누락: {', '.join(sorted(missing_row_fields))}"
                )
            if not isinstance(row["judged"], bool):
                raise ValueError(f"{label}: {field}[{index}].judged는 불리언이어야 합니다")
    for index, row in enumerate(payload["questions"]):
        if not isinstance(row["secondary_reasons"], list):
            raise ValueError(f"{label}: questions[{index}].secondary_reasons는 배열이어야 합니다")
        if not isinstance(row["composition_sources"], list):
            raise ValueError(f"{label}: questions[{index}].composition_sources는 배열이어야 합니다")
        if not isinstance(row["composition_override"], bool):
            raise ValueError(f"{label}: questions[{index}].composition_override는 불리언이어야 합니다")
    for index, row in enumerate(payload["pages"]):
        expected_row_id = f"P|{row['question_id']}|{normalize_url(str(row['canonical_url']))}"
        if row["row_id"] != expected_row_id:
            raise ValueError(f"{label}: pages[{index}].row_id가 식별자와 다릅니다")
    for index, row in enumerate(payload["evidence"]):
        expected_row_id = f"E|{row['question_id']}|{row['chunk_id']}"
        if row["row_id"] != expected_row_id:
            raise ValueError(f"{label}: evidence[{index}].row_id가 식별자와 다릅니다")
    for index, row in enumerate(payload["questions"]):
        expected_row_id = f"Q|{row['question_id']}"
        if row["row_id"] != expected_row_id:
            raise ValueError(f"{label}: questions[{index}].row_id가 식별자와 다릅니다")


def _entries(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"adjudicated JSON의 {key}는 객체 배열이어야 합니다")
    return [dict(row) for row in value]


def _judged_text(value: Any, *, fallback: bool) -> str:
    parsed = parse_bool(value)
    return "true" if (fallback if parsed is None else parsed) else "false"


def _index_unique(
    rows: Iterable[dict[str, Any]],
    *,
    key_fn: Any,
    label: str,
) -> dict[Any, dict[str, Any]]:
    indexed: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = key_fn(row)
        if key in indexed:
            raise ValueError(f"adjudicated JSON에 {label} 중복 행이 있습니다: {key}")
        indexed[key] = row
    return indexed


def merge_page_rows(
    pool_rows: list[dict[str, str]],
    judgments: list[dict[str, Any]],
) -> list[dict[str, str]]:
    indexed = _index_unique(
        judgments,
        key_fn=lambda row: (
            str(row.get("question_id") or ""),
            normalize_url(str(row.get("canonical_url") or "")),
        ),
        label="페이지",
    )
    pool_keys = {(row["question_id"], normalize_url(row["canonical_url"])) for row in pool_rows}
    extras = set(indexed) - pool_keys
    if extras:
        raise ValueError(f"page pool에 없는 판정 행: {sorted(extras)}")

    merged: list[dict[str, str]] = []
    for pool in pool_rows:
        key = (pool["question_id"], normalize_url(pool["canonical_url"]))
        judgment = indexed.get(key)
        row = dict(pool)
        if judgment is None:
            row.update(
                judged="false",
                support_grade="",
                temporal_validity="",
                audience_scope="",
                notes="",
            )
        else:
            complete = all(
                str(judgment.get(field) or "") for field in ("support_grade", "temporal_validity", "audience_scope")
            )
            row.update(
                judged=_judged_text(judgment.get("judged"), fallback=complete),
                support_grade=str(judgment.get("support_grade") or ""),
                temporal_validity=str(judgment.get("temporal_validity") or ""),
                audience_scope=str(judgment.get("audience_scope") or ""),
                notes=str(judgment.get("notes") or ""),
            )
        merged.append(row)
    return merged


def merge_evidence_rows(
    pool_rows: list[dict[str, str]],
    judgments: list[dict[str, Any]],
) -> list[dict[str, str]]:
    indexed = _index_unique(
        judgments,
        key_fn=lambda row: (
            str(row.get("question_id") or ""),
            str(row.get("chunk_id") or ""),
        ),
        label="근거",
    )
    pool_index = {(row["question_id"], row["chunk_id"]): row for row in pool_rows}
    extras = set(indexed) - set(pool_index)
    if extras:
        raise ValueError(f"chunk pool에 없는 판정 행: {sorted(extras)}")

    merged: list[dict[str, str]] = []
    for pool in pool_rows:
        key = (pool["question_id"], pool["chunk_id"])
        judgment = indexed.get(key)
        row = dict(pool)
        if judgment is None:
            row.update(
                judged="false",
                evidence_grade="",
                evidence_type="",
                notes="",
            )
        else:
            judged_fields_present = "evidence_grade" in judgment and "evidence_type" in judgment
            canonical_url = normalize_url(str(judgment.get("canonical_url") or ""))
            if canonical_url and canonical_url != normalize_url(pool["canonical_url"]):
                raise ValueError(f"{key}: adjudicated 근거의 canonical_url이 pool과 다릅니다")
            row.update(
                judged=_judged_text(judgment.get("judged"), fallback=judged_fields_present),
                evidence_grade=str(judgment.get("evidence_grade") or ""),
                evidence_type=str(judgment.get("evidence_type") or ""),
                notes=str(judgment.get("notes") or ""),
            )
        merged.append(row)
    return merged


def _pipe(value: Any) -> str:
    return "|".join(split_values(value))


def load_question_order(path: Path = QUESTIONS_PATH) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        return [row["id"] for row in csv.DictReader(input_file)]


def build_question_rows(
    question_ids: list[str],
    page_rows: list[dict[str, str]],
    judgments: list[dict[str, Any]],
) -> list[dict[str, str]]:
    indexed = _index_unique(
        judgments,
        key_fn=lambda row: str(row.get("question_id") or ""),
        label="질문",
    )
    extras = set(indexed) - set(question_ids)
    if extras:
        raise ValueError(f"questions.csv에 없는 질문 판정: {sorted(extras)}")

    pages_by_question: dict[str, list[dict[str, str]]] = defaultdict(list)
    for page in page_rows:
        pages_by_question[page["question_id"]].append(page)

    rows: list[dict[str, str]] = []
    for question_id in question_ids:
        judgment = indexed.get(question_id, {})
        if parse_bool(judgment.get("judged")) is not True:
            judgment = {}
        override = parse_bool(judgment.get("composition_override")) is True
        derived = derive_pool_support(pages_by_question.get(question_id, []))
        pool_support = str(judgment.get("pool_support") or "") if override else derived
        rows.append(
            {
                "question_id": question_id,
                "pool_support": pool_support,
                "expected_behavior": str(judgment.get("expected_behavior") or ""),
                "primary_reason": str(judgment.get("primary_reason") or ""),
                "secondary_reasons": _pipe(judgment.get("secondary_reasons")),
                "composition_override": "true" if override else "false",
                "composition_sources": _pipe(judgment.get("composition_sources")),
                "notes": str(judgment.get("notes") or ""),
            }
        )
    return rows


def build_rows(
    page_pool: list[dict[str, str]],
    chunk_pool: list[dict[str, str]],
    question_ids: list[str],
    payload: Mapping[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    pages = merge_page_rows(page_pool, _entries(payload, "pages"))
    evidence = merge_evidence_rows(chunk_pool, _entries(payload, "evidence"))
    questions = build_question_rows(
        question_ids,
        pages,
        _entries(payload, "questions"),
    )
    return pages, evidence, questions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="adjudicated JSON에서 qrel v4를 발행합니다.")
    parser.add_argument("--adjudicated", type=Path, default=ADJUDICATED_PATH)
    parser.add_argument("--page-pool", type=Path, default=PAGE_POOL_PATH)
    parser.add_argument("--chunk-pool", type=Path, default=CHUNK_POOL_PATH)
    parser.add_argument("--db-dsn", default=DB_DSN)
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    page_pool = load_csv(args.page_pool, PAGE_REQUIRED_FIELDS)
    chunk_pool = load_csv(args.chunk_pool, CHUNK_FIELDS)
    question_ids = load_question_order()
    pages, evidence, questions = build_rows(
        page_pool,
        chunk_pool,
        question_ids,
        load_json(args.adjudicated),
    )

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
        print(f"qrel v4 발행 중단: invariant 실패 {len(failures)}건")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    write_csv_atomic(GOLD_PAGES_PATH, fieldnames=PAGE_FIELDS, rows=pages)
    write_csv_atomic(GOLD_EVIDENCE_PATH, fieldnames=CHUNK_FIELDS, rows=evidence)
    write_csv_atomic(
        QUESTION_JUDGMENTS_PATH,
        fieldnames=QUESTION_FIELDS,
        rows=questions,
    )
    print(f"qrel v4 발행 완료: 페이지 {len(pages)}행, 근거 {len(evidence)}행, 질문 {len(questions)}행")
    print(f"저장: {GOLD_PAGES_PATH}, {GOLD_EVIDENCE_PATH}, {QUESTION_JUDGMENTS_PATH}")


if __name__ == "__main__":
    asyncio.run(run())
