"""승인된 사람 감사와 질문 수준 검토를 qrel v4 최종 JSON으로 조립한다."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.build_v4_qrel import load_json, validate_judgment_payload  # noqa: E402
from eval.check_v4_invariants import derive_pool_support  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"
PRIMARY_PATH = EVAL_DIR / "qrel-v4-primary-initial.json"
QUESTION_REVIEW_PATH = EVAL_DIR / "qrel-v4-question-review.json"
OUT_PATH = EVAL_DIR / "qrel-v4-adjudicated.json"
ADJUDICATED_AT = "2026-07-14T12:20:09Z"


PAGE_OVERRIDES: dict[str, dict[str, object]] = {
    "P|Q008|https://www.honam.ac.kr/ClassLessonApply": {
        "support_grade": "partial",
        "temporal_validity": "current",
        "audience_scope": "match",
        "notes": (
            "정정 허용 조건과 수강신청 절차 준용 원칙은 제시하지만, 질문이 요구하는 "
            "접속 경로와 실제 정정 조작 절차는 제공하지 않아 partial이다."
        ),
    },
    "P|Q013|https://www.honam.ac.kr/ProofIssuanceApply": {
        "support_grade": "full",
        "temporal_validity": "current",
        "audience_scope": "match",
        "notes": (
            "공식 증명발급 페이지가 방문 발급 장소·시간·준비물을 직접 제시한다. "
            "유효한 발급 경로 하나를 완전하게 답하므로 full이다."
        ),
    },
    "P|Q036|https://www.honam.ac.kr/ExamResult": {
        "support_grade": "partial",
        "temporal_validity": "current",
        "audience_scope": "match",
        "notes": (
            "F를 포함한 C+ 이하 과목의 재수강 자격·시기·성적 처리는 제시하지만, "
            "질문이 요구하는 신청 경로와 실제 조작 절차는 없어 partial이다."
        ),
    },
}


EVIDENCE_OVERRIDES: dict[str, dict[str, object]] = {
    "E|Q008|33478902-8a72-4b39-a885-10686fc9436b": {
        "evidence_grade": "partial",
        "evidence_type": "text_chunk",
        "notes": "정정 조건과 수강신청 절차 준용은 지지하지만 실제 접속·조작 절차는 없다.",
    },
    "E|Q013|c9eb2f99-a9cd-4b4f-8dab-78a70598fc82": {
        "evidence_grade": "full",
        "evidence_type": "text_chunk",
        "notes": "발급 장소가 본문에 직접 있으므로 full text_chunk이다.",
    },
    "E|Q036|e319bc25-7e16-4762-b274-c08cc926abd5": {
        "evidence_grade": "partial",
        "evidence_type": "text_chunk",
        "notes": "재수강 자격·시기·성적 처리는 지지하지만 실제 신청 절차는 없다.",
    },
    "E|Q048|f504038f-1f3a-453c-aac1-b8e5cb6503f8": {
        "evidence_grade": "",
        "evidence_type": "",
        "notes": "별도 입사일 공지는 입사 신청 방법을 지지하지 않는다.",
    },
}


QUESTION_OVERRIDES: dict[str, dict[str, object]] = {
    "Q|Q003": {
        "notes": (
            "한국장학재단 신청처를 직접 제시하는 대상 일치 문서는 있으나 모두 지난 회차다. "
            "판정 재료에는 해당 경로의 현재 유효성을 확인하는 current+match full 근거가 없어 "
            "abstain(stale)으로 확정한다."
        ),
    },
    "Q|Q008": {
        "notes": (
            "현행 상시 페이지는 정정 조건과 수강신청 절차 준용까지만 제공한다. "
            "접속 경로와 실제 조작 절차가 현행 판정 재료에 없어, 빠진 범위를 밝힌 제한 답변은 "
            "가능하지만 완전 답변은 불가능하다. 수강신청 시스템이 코퍼스 밖에 있어 "
            "qualified_answer(acquisition_failure)로 확정한다."
        ),
    },
    "Q|Q036": {
        "notes": (
            "현행 자료는 재수강 자격·시기·성적 처리와 수강신청 원칙까지만 제공하고 실제 신청 "
            "경로·조작 절차는 제공하지 않는다. 공식 공지의 상세 매뉴얼 PDF가 코퍼스에 수집되지 "
            "않았고, 절차 질문의 핵심 결손으로 보아 abstain(acquisition_failure)으로 확정한다."
        ),
    },
}


EXPECTED_REVIEW_DECISIONS = {
    "Q003": ("abstain", "stale"),
    "Q008": ("qualified_answer", "acquisition_failure"),
    "Q036": ("abstain", "acquisition_failure"),
}


def _index_rows(rows: list[dict[str, Any]], *, section: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = str(row.get("row_id") or "")
        if not row_id or row_id in indexed:
            raise ValueError(f"{section} row_id가 비었거나 중복됐습니다: {row_id!r}")
        indexed[row_id] = row
    return indexed


def _apply_overrides(
    payload: dict[str, Any],
    section: str,
    overrides: dict[str, dict[str, object]],
) -> None:
    indexed = _index_rows(payload[section], section=section)
    missing = sorted(set(overrides) - set(indexed))
    if missing:
        raise ValueError(f"{section} 조정 대상 행이 없습니다: {missing}")
    for row_id, fields in overrides.items():
        indexed[row_id].update(fields)
        indexed[row_id]["judged"] = True


def _replace_questions(payload: dict[str, Any], review: dict[str, Any]) -> None:
    primary_ids = {str(row["question_id"]) for row in payload["questions"]}
    reviewed = _index_rows(review["questions"], section="questions")
    review_ids = {str(row["question_id"]) for row in reviewed.values()}
    if primary_ids != review_ids:
        raise ValueError(
            "질문 수준 검토 범위가 초벌과 다릅니다: "
            f"missing={sorted(primary_ids - review_ids)}, extras={sorted(review_ids - primary_ids)}"
        )
    unjudged = sorted(
        str(row["question_id"]) for row in reviewed.values() if row.get("judged") is not True
    )
    if unjudged:
        raise ValueError(f"질문 수준 미검토 행이 있습니다: {unjudged}")

    decisions = {str(row["question_id"]): row for row in reviewed.values()}
    for question_id, expected in EXPECTED_REVIEW_DECISIONS.items():
        row = decisions[question_id]
        actual = (str(row.get("expected_behavior") or ""), str(row.get("primary_reason") or ""))
        if actual != expected:
            raise ValueError(f"{question_id} 저자 확정값이 조정 기록과 다릅니다: {actual} != {expected}")

    payload["questions"] = deepcopy(list(reviewed.values()))


def _refresh_pool_support(payload: dict[str, Any]) -> None:
    pages_by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for page in payload["pages"]:
        pages_by_question[str(page["question_id"])].append(page)
    for question in payload["questions"]:
        if question.get("composition_override") is True:
            continue
        question["pool_support"] = derive_pool_support(
            pages_by_question.get(str(question["question_id"]), [])
        )


def build_adjudicated(primary: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(primary)
    _replace_questions(payload, review)
    _apply_overrides(payload, "pages", PAGE_OVERRIDES)
    _apply_overrides(payload, "evidence", EVIDENCE_OVERRIDES)
    _apply_overrides(payload, "questions", QUESTION_OVERRIDES)
    _refresh_pool_support(payload)
    payload["audit"] = False
    payload["judge"] = "LLM 초벌 + B2 사람 감사 + 저자 질문 수준 전량 검토 조정"
    payload["date"] = str(review["date"])
    payload["exported_at"] = ADJUDICATED_AT
    validate_judgment_payload(payload)
    return payload


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="qrel v4 최종 조정 JSON을 조립합니다.")
    parser.add_argument("--primary", type=Path, default=PRIMARY_PATH)
    parser.add_argument("--question-review", type=Path, default=QUESTION_REVIEW_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_adjudicated(load_json(args.primary), load_json(args.question_review))
    write_json_atomic(args.out, payload)
    print(
        f"저장: {args.out} "
        f"(페이지 {len(payload['pages'])}행, 근거 {len(payload['evidence'])}행, "
        f"질문 {len(payload['questions'])}행)"
    )


if __name__ == "__main__":
    main()
