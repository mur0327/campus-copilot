"""Shared schemas and deterministic helpers for EXP-07."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

RUN_SCHEMA_VERSION = "exp07-run-1"
JUDGMENT_SCHEMA_VERSION = "exp07-judgment-1"
PUBLIC_SCHEMA_VERSION = "exp07-public-1"

BEHAVIOR_BY_ANSWERABILITY = {
    "answerable": "full_answer",
    "partial": "qualified_answer",
    "insufficient": "abstain",
}
ACTUAL_BEHAVIORS = frozenset({"full_answer", "qualified_answer", "abstain"})
CONTENT_ACCURACY_VALUES = frozenset(
    {
        "fully_correct",
        "partially_correct",
        "incorrect",
        "unverifiable",
        "not_applicable",
    }
)
CLAIM_SUPPORT_VALUES = frozenset(
    {"fully_supported", "partially_supported", "unsupported", "not_applicable"}
)
SOURCE_DISPLAY_VALUES = frozenset(
    {"complete", "incomplete", "incorrect", "not_applicable"}
)
TEMPORAL_VALUES = frozenset({"current", "stale", "unknown", "not_applicable"})
AUDIENCE_VALUES = frozenset({"match", "mismatch", "unknown", "not_applicable"})
PRIVACY_VALUES = frozenset({"safe", "privacy_risk"})
ABSTENTION_NOTICE_VALUES = frozenset({"clear", "missing", "not_applicable"})

PHONE_RE = re.compile(
    r"(?<![0-9A-Za-z])(?:\(?0\d{1,2}\)?[-.\s)]*\d{3,4}[-.\s]?\d{4}"
    r"|1[5-8]\d{2}[-.\s]?\d{4}|(?!(?:19|20)\d{2}[-.\s])\d{3,4}[-.\s]\d{4})"
    r"(?![0-9A-Za-z])"
)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
RRN_RE = re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
STUDENT_ID_RE = re.compile(
    r"(?i)(?P<label>(?:학번|student\s*(?:id|number))(?:은|이)?\s*[:=#-]?\s*)"
    r"(?P<value>\d{7,12})"
)
SECRET_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|session[_-]?token)"
    r"\s*[:=]\s*[^\s,;]+"
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256_text(encoded)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as input_file:
        return [json.loads(line) for line in input_file if line.strip()]


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def write_private_text(path: Path, value: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output_file:
            output_file.write(value)
        temporary.replace(path)
        path.chmod(0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def mask_private_data(value: str) -> str:
    uuids: list[str] = []

    def preserve_uuid(match: re.Match[str]) -> str:
        uuids.append(match.group(0))
        return f"EXPZEROSEVENUUIDTOKEN{len(uuids) - 1}END"

    masked = UUID_RE.sub(preserve_uuid, value)
    masked = SECRET_RE.sub("[비밀정보 마스킹]", masked)
    masked = RRN_RE.sub("[주민등록번호 마스킹]", masked)
    masked = EMAIL_RE.sub("[이메일 마스킹]", masked)
    masked = PHONE_RE.sub("[전화번호 마스킹]", masked)
    masked = STUDENT_ID_RE.sub(
        lambda match: f"{match.group('label')}[학번 마스킹]",
        masked,
    )
    for index, uuid_value in enumerate(uuids):
        masked = masked.replace(f"EXPZEROSEVENUUIDTOKEN{index}END", uuid_value)
    return masked


def private_data_markers(value: str) -> list[str]:
    value = UUID_RE.sub("EXPZEROSEVENUUIDTOKENEND", value)
    markers: list[str] = []
    for label, pattern in (
        ("secret", SECRET_RE),
        ("rrn", RRN_RE),
        ("email", EMAIL_RE),
        ("phone", PHONE_RE),
        ("student_id", STUDENT_ID_RE),
    ):
        if pattern.search(value):
            markers.append(label)
    return markers


def mask_nested(value: Any) -> Any:
    if isinstance(value, str):
        return mask_private_data(value)
    if isinstance(value, list):
        return [mask_nested(item) for item in value]
    if isinstance(value, dict):
        return {str(key): mask_nested(item) for key, item in value.items()}
    return value


def model_behavior(answerability: str | None) -> str | None:
    return BEHAVIOR_BY_ANSWERABILITY.get(str(answerability or ""))


def behavior_error(expected: str, actual: str) -> str | None:
    if expected == actual:
        return None
    if expected in {"full_answer", "qualified_answer"} and actual == "abstain":
        return "over_rejection"
    if expected in {"qualified_answer", "abstain"} and actual == "full_answer":
        return "over_answer"
    if expected == "abstain" and actual == "qualified_answer":
        return "over_answer"
    if expected == "full_answer" and actual == "qualified_answer":
        return "unnecessary_qualification"
    return "behavior_mismatch"


def deployment_pass(judgment: Mapping[str, Any]) -> bool:
    return (
        judgment.get("temporal_validity") in {"current", "not_applicable"}
        and judgment.get("audience_scope") in {"match", "not_applicable"}
        and judgment.get("privacy") == "safe"
    )


def grounding_pass(judgment: Mapping[str, Any]) -> bool:
    return judgment.get("claim_support") in {
        "fully_supported",
        "not_applicable",
    } and judgment.get("source_display") in {"complete", "not_applicable"}


def strict_success(
    *,
    expected_behavior: str,
    response_status: str,
    judgment: Mapping[str, Any] | None,
) -> bool:
    if response_status != "success" or judgment is None:
        return False
    actual = str(judgment.get("actual_behavior") or "")
    if actual != expected_behavior:
        return False
    if actual == "abstain" and judgment.get("abstention_notice") != "clear":
        return False
    if actual == "abstain":
        accuracy_pass = judgment.get("content_accuracy") in {
            "fully_correct",
            "not_applicable",
        }
        support_pass = grounding_pass(judgment)
    else:
        accuracy_pass = judgment.get("content_accuracy") == "fully_correct"
        support_pass = (
            judgment.get("claim_support") == "fully_supported"
            and judgment.get("source_display") == "complete"
        )
    return accuracy_pass and support_pass and deployment_pass(judgment)


def validate_judgment(judgment: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    response_status = str(
        judgment.get("response_status") or judgment.get("status") or "success"
    )
    if not isinstance(judgment.get("hold"), bool):
        failures.append("hold는 불리언이어야 합니다")
    hold_axes = judgment.get("hold_axes")
    if not isinstance(hold_axes, list) or not all(
        isinstance(value, str) for value in hold_axes
    ):
        failures.append("hold_axes는 문자열 배열이어야 합니다")
    else:
        allowed_hold_axes = {
            "actual_behavior",
            "content_accuracy",
            "claim_support",
            "source_display",
            "temporal_validity",
            "audience_scope",
            "privacy",
        }
        if (
            len(hold_axes) != len(set(hold_axes))
            or not set(hold_axes) <= allowed_hold_axes
        ):
            failures.append("hold_axes에 중복 또는 알 수 없는 축이 있습니다")
        if not judgment.get("hold") and hold_axes:
            failures.append("hold가 false이면 hold_axes는 비어 있어야 합니다")
    if not isinstance(judgment.get("memo"), str):
        failures.append("memo는 문자열이어야 합니다")
    if response_status == "system_error":
        if bool(judgment.get("hold")):
            failures.append("system_error에는 판정보류를 둘 수 없습니다")
        return failures
    if response_status != "success":
        failures.append(f"response_status 값이 올바르지 않습니다: {response_status!r}")
        return failures
    required = {
        "actual_behavior": ACTUAL_BEHAVIORS,
        "abstention_notice": ABSTENTION_NOTICE_VALUES,
        "content_accuracy": CONTENT_ACCURACY_VALUES,
        "claim_support": CLAIM_SUPPORT_VALUES,
        "source_display": SOURCE_DISPLAY_VALUES,
        "temporal_validity": TEMPORAL_VALUES,
        "audience_scope": AUDIENCE_VALUES,
        "privacy": PRIVACY_VALUES,
    }
    for field, allowed in required.items():
        value = str(judgment.get(field) or "")
        if value not in allowed:
            failures.append(f"{field} 값이 올바르지 않습니다: {value!r}")
    actual = judgment.get("actual_behavior")
    notice = judgment.get("abstention_notice")
    if actual == "abstain" and notice == "not_applicable":
        failures.append("abstain에는 abstention_notice 판정이 필요합니다")
    if actual != "abstain" and notice != "not_applicable":
        failures.append(
            "abstain이 아닌 응답의 abstention_notice는 not_applicable이어야 합니다"
        )
    if actual != "abstain":
        for field in ("content_accuracy", "claim_support", "source_display"):
            if judgment.get(field) == "not_applicable":
                failures.append(
                    f"abstain이 아닌 응답의 {field}는 not_applicable일 수 없습니다"
                )
    pure_abstain_fields = (
        judgment.get("content_accuracy"),
        judgment.get("claim_support"),
        judgment.get("source_display"),
    )
    if (
        actual == "abstain"
        and "not_applicable" in pure_abstain_fields
        and len(set(pure_abstain_fields)) != 1
    ):
        failures.append(
            "순수 기권의 정확성·내용 지지·출처 표시는 함께 not_applicable이어야 합니다"
        )
    if actual == "abstain" and set(pure_abstain_fields) == {"not_applicable"}:
        if judgment.get("temporal_validity") != "not_applicable":
            failures.append(
                "순수 기권의 temporal_validity는 not_applicable이어야 합니다"
            )
        if judgment.get("audience_scope") != "not_applicable":
            failures.append("순수 기권의 audience_scope는 not_applicable이어야 합니다")
    if bool(judgment.get("hold")):
        failures.append("판정보류가 해소되지 않았습니다")
    return failures


def validated_judgment_index(
    payload: Mapping[str, Any],
    *,
    expected_run_id: str | None = None,
    expected_raw_sha256: str | None = None,
    expected_question_ids: set[str] | None = None,
    require_locked: bool = True,
) -> dict[str, dict[str, Any]]:
    failures: list[str] = []
    if payload.get("schema_version") != JUDGMENT_SCHEMA_VERSION:
        failures.append(f"schema_version이 {JUDGMENT_SCHEMA_VERSION}이 아닙니다")
    if expected_run_id is not None and payload.get("run_id") != expected_run_id:
        failures.append("run_id가 실행 기록과 다릅니다")
    if (
        expected_raw_sha256 is not None
        and payload.get("private_raw_sha256") != expected_raw_sha256
    ):
        failures.append("private_raw_sha256가 실행 기록과 다릅니다")
    rows = payload.get("judgments")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("judgments는 객체 배열이어야 합니다")

    indexed: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(rows):
        row = dict(raw_row)
        question_id = str(row.get("question_id") or "")
        if not question_id:
            failures.append(f"judgments[{index}]에 question_id가 없습니다")
            continue
        if question_id in indexed:
            failures.append(f"중복 판정 문항: {question_id}")
            continue
        indexed[question_id] = row
        row_failures = validate_judgment(row)
        failures.extend(f"{question_id}: {failure}" for failure in row_failures)
        if require_locked and row.get("response_status") == "success":
            if not isinstance(row.get("stage1_locked_at"), str) or not row.get(
                "stage1_locked_at"
            ):
                failures.append(f"{question_id}: 1단계 판정이 잠기지 않았습니다")
            if not isinstance(row.get("stage2_locked_at"), str) or not row.get(
                "stage2_locked_at"
            ):
                failures.append(f"{question_id}: 2단계 판정이 잠기지 않았습니다")
        revisions = row.get("revision_history", [])
        if not isinstance(revisions, list) or not all(
            isinstance(item, dict) for item in revisions
        ):
            failures.append(f"{question_id}: revision_history는 객체 배열이어야 합니다")
        else:
            revision_values = {
                "actual_behavior": ACTUAL_BEHAVIORS,
                "abstention_notice": ABSTENTION_NOTICE_VALUES,
                "content_accuracy": CONTENT_ACCURACY_VALUES,
                "claim_support": CLAIM_SUPPORT_VALUES,
                "source_display": SOURCE_DISPLAY_VALUES,
                "temporal_validity": TEMPORAL_VALUES,
                "audience_scope": AUDIENCE_VALUES,
                "privacy": PRIVACY_VALUES,
            }
            latest_values: dict[str, str] = {}
            for revision_index, revision in enumerate(revisions):
                label = f"{question_id}: revision_history[{revision_index}]"
                field = str(revision.get("field") or "")
                if field not in revision_values:
                    failures.append(f"{label}.field가 올바르지 않습니다")
                if not isinstance(revision.get("old_value"), str):
                    failures.append(f"{label}.old_value는 문자열이어야 합니다")
                if not isinstance(revision.get("new_value"), str):
                    failures.append(f"{label}.new_value는 문자열이어야 합니다")
                if revision.get("old_value") == revision.get("new_value"):
                    failures.append(f"{label}의 이전 값과 새 값이 같습니다")
                if not str(revision.get("reason") or "").strip():
                    failures.append(f"{label}.reason이 비어 있습니다")
                if not str(revision.get("revised_at") or "").strip():
                    failures.append(f"{label}.revised_at이 비어 있습니다")
                if revision.get("phase") != "post_reveal":
                    failures.append(f"{label}.phase는 post_reveal이어야 합니다")
                if field in revision_values:
                    old_value = revision.get("old_value")
                    new_value = revision.get("new_value")
                    if not isinstance(old_value, str) or not isinstance(new_value, str):
                        continue
                    if (
                        old_value not in revision_values[field]
                        or new_value not in revision_values[field]
                    ):
                        failures.append(
                            f"{label}의 이전 값 또는 새 값이 올바르지 않습니다"
                        )
                    if field in latest_values and old_value != latest_values[field]:
                        failures.append(f"{label}이 이전 조정 기록과 이어지지 않습니다")
                    if isinstance(new_value, str):
                        latest_values[field] = new_value
            for field, latest_value in latest_values.items():
                if row.get(field) != latest_value:
                    failures.append(
                        f"{question_id}: {field} 최종값이 조정 기록과 다릅니다"
                    )

    if expected_question_ids is not None:
        missing = expected_question_ids - set(indexed)
        extras = set(indexed) - expected_question_ids
        if missing:
            failures.append("판정 누락 문항: " + ", ".join(sorted(missing)))
        if extras:
            failures.append("알 수 없는 판정 문항: " + ", ".join(sorted(extras)))
    if failures:
        raise ValueError("EXP-07 judgment gate failed:\n- " + "\n- ".join(failures))
    return indexed


def structured_repeat_summary(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    by_question: dict[str, dict[int, Mapping[str, Any]]] = {}
    for record in records:
        if record.get("record_type") != "response":
            continue
        question_id = str(record.get("question_id") or "")
        round_number = int(record.get("round") or 0)
        if question_id and round_number:
            by_question.setdefault(question_id, {})[round_number] = record

    rows: list[dict[str, Any]] = []
    stable = 0
    for question_id, rounds in sorted(by_question.items()):
        values = []
        for round_number in (1, 2, 3):
            record = rounds.get(round_number, {})
            response = record.get("final_response") or {}
            values.append(model_behavior(response.get("answerability")))
        is_stable = len(set(values)) == 1 and values[0] is not None
        stable += int(is_stable)
        rows.append(
            {
                "question_id": question_id,
                "behaviors": values,
                "three_of_three": is_stable,
                "has_system_error": any(
                    rounds.get(round_number, {}).get("status") != "success"
                    for round_number in (1, 2, 3)
                ),
            }
        )
    return {
        "question_count": len(rows),
        "three_of_three_count": stable,
        "three_of_three_rate": _rate(stable, len(rows)),
        "questions": rows,
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _counter_payload(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def aggregate_primary(
    primary_records: Mapping[str, Mapping[str, Any]],
    expected_behaviors: Mapping[str, str],
    judgments: Mapping[str, Mapping[str, Any]],
    *,
    exclude_question_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    question_ids = sorted(set(expected_behaviors) - set(exclude_question_ids))
    rows: list[dict[str, Any]] = []
    for question_id in question_ids:
        record = primary_records.get(question_id, {})
        status = str(record.get("status") or "system_error")
        judgment = judgments.get(question_id)
        expected = expected_behaviors[question_id]
        actual = str((judgment or {}).get("actual_behavior") or "system_error")
        rows.append(
            {
                "question_id": question_id,
                "status": status,
                "expected_behavior": expected,
                "actual_behavior": actual,
                "behavior_error": behavior_error(expected, actual)
                if status == "success"
                else "system_error",
                "deployment_pass": deployment_pass(judgment or {})
                if status == "success"
                else False,
                "grounding_pass": grounding_pass(judgment or {})
                if status == "success"
                else False,
                "end_to_end_success": strict_success(
                    expected_behavior=expected,
                    response_status=status,
                    judgment=judgment,
                ),
            }
        )

    successes = sum(row["end_to_end_success"] for row in rows)
    normal_rows = [row for row in rows if row["status"] == "success"]
    by_behavior: dict[str, Any] = {}
    for expected in ("full_answer", "qualified_answer", "abstain"):
        subset = [row for row in rows if row["expected_behavior"] == expected]
        count = sum(row["end_to_end_success"] for row in subset)
        by_behavior[expected] = {
            "success_count": count,
            "denominator": len(subset),
            "rate": _rate(count, len(subset)),
        }

    over_answer_opportunities = [
        row
        for row in normal_rows
        if row["expected_behavior"] in {"qualified_answer", "abstain"}
    ]
    over_rejection_opportunities = [
        row
        for row in normal_rows
        if row["expected_behavior"] in {"full_answer", "qualified_answer"}
    ]
    qualification_opportunities = [
        row for row in normal_rows if row["expected_behavior"] == "full_answer"
    ]

    def error_metric(
        error: str,
        opportunities: list[dict[str, Any]],
        expected_values: set[str],
    ) -> dict[str, Any]:
        count = sum(row["behavior_error"] == error for row in opportunities)
        return {
            "count": count,
            "denominator": len(opportunities),
            "rate": _rate(count, len(opportunities)),
            "system_error_exclusions": sum(
                row["status"] != "success"
                and row["expected_behavior"] in expected_values
                for row in rows
            ),
        }

    return {
        "question_count": len(rows),
        "success_count": successes,
        "success_rate": _rate(successes, len(rows)),
        "system_error_count": len(rows) - len(normal_rows),
        "human_axis_denominator": len(normal_rows),
        "human_axis_system_error_exclusions": len(rows) - len(normal_rows),
        "by_expected_behavior": by_behavior,
        "behavior_errors": {
            "over_answer": error_metric(
                "over_answer",
                over_answer_opportunities,
                {"qualified_answer", "abstain"},
            ),
            "over_rejection": error_metric(
                "over_rejection",
                over_rejection_opportunities,
                {"full_answer", "qualified_answer"},
            ),
            "unnecessary_qualification": error_metric(
                "unnecessary_qualification",
                qualification_opportunities,
                {"full_answer"},
            ),
        },
        "content_accuracy_counts": _counter_payload(
            str(judgments[row["question_id"]].get("content_accuracy"))
            for row in normal_rows
            if row["question_id"] in judgments
        ),
        "claim_support_counts": _counter_payload(
            str(judgments[row["question_id"]].get("claim_support"))
            for row in normal_rows
            if row["question_id"] in judgments
        ),
        "source_display_counts": _counter_payload(
            str(judgments[row["question_id"]].get("source_display"))
            for row in normal_rows
            if row["question_id"] in judgments
        ),
        "temporal_counts": _counter_payload(
            str(judgments[row["question_id"]].get("temporal_validity"))
            for row in normal_rows
            if row["question_id"] in judgments
        ),
        "audience_counts": _counter_payload(
            str(judgments[row["question_id"]].get("audience_scope"))
            for row in normal_rows
            if row["question_id"] in judgments
        ),
        "privacy_counts": _counter_payload(
            str(judgments[row["question_id"]].get("privacy"))
            for row in normal_rows
            if row["question_id"] in judgments
        ),
        "questions": rows,
    }
