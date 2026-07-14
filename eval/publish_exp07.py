"""Publish sanitized EXP-07 responses, judgments, and descriptive aggregates."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.exp07_common import (  # noqa: E402
    PUBLIC_SCHEMA_VERSION,
    aggregate_primary,
    load_jsonl,
    mask_nested,
    model_behavior,
    private_data_markers,
    sha256_file,
    structured_repeat_summary,
    validated_judgment_index,
    write_json,
)
from eval.make_exp07_primary_sheet import (  # noqa: E402
    assert_committed_file,
    primary_records,
    selected_attempt,
)
from eval.make_exp07_reveal_sheet import load_expected_behaviors, raw_output_diagnostic  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"
RUN_MANIFEST_PATH = EVAL_DIR / "exp07-run-manifest.json"
DEFAULT_RESPONSES_PATH = EVAL_DIR / "exp07-responses-public.json"
DEFAULT_JUDGMENTS_PATH = EVAL_DIR / "exp07-judgments.json"
DEFAULT_RESULTS_PATH = EVAL_DIR / "exp07-results.json"
DEFAULT_CSV_PATH = EVAL_DIR / "exp07-results.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish sanitized EXP-07 artifacts.")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("judgments", type=Path)
    parser.add_argument("--manifest", type=Path, default=RUN_MANIFEST_PATH)
    parser.add_argument("--responses-output", type=Path, default=DEFAULT_RESPONSES_PATH)
    parser.add_argument("--judgments-output", type=Path, default=DEFAULT_JUDGMENTS_PATH)
    parser.add_argument("--results-output", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_PATH)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON object required")
    return payload


def _result_metadata(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": value.get("chunk_id"),
        "content_hash": value.get("content_hash"),
        "title": value.get("title"),
        "url": value.get("url"),
        "menu_path": value.get("menu_path"),
        "source_scope": value.get("source_scope"),
        "page_kind": value.get("page_kind"),
        "crawled_at": value.get("crawled_at"),
    }


def _public_evidence(attempt: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    for candidate in (attempt or {}).get("evidence_candidates") or []:
        rows.append(
            {
                "source_number": candidate.get("source_number"),
                "display_result": _result_metadata(
                    candidate.get("display_result") or {}
                ),
                "context_results": [
                    _result_metadata(context)
                    for context in candidate.get("context_results") or []
                ],
            }
        )
    return rows


def _public_final_response(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    status = value.get("retrieval_status") or {}
    return {
        "answerability": value.get("answerability"),
        "answer": value.get("answer"),
        "summary": value.get("summary"),
        "procedure_steps": value.get("procedure_steps") or [],
        "notes": value.get("notes") or [],
        "limitations": value.get("limitations") or [],
        "sources": [
            {
                "title": source.get("title"),
                "url": source.get("url"),
                "crawled_at": source.get("crawled_at"),
                "freshness": source.get("freshness"),
                "chunk_id": source.get("chunk_id"),
            }
            for source in value.get("sources") or []
        ],
        "conflict_warning": value.get("conflict_warning"),
        "freshness": value.get("freshness"),
        "retrieval_status": {
            "mode": status.get("mode"),
            "degraded": status.get("degraded"),
            "semantic_available": status.get("semantic_available"),
            "bm25_available": status.get("bm25_available"),
            "evidence_candidate_count": status.get("evidence_candidate_count"),
            "display_source_count": status.get("display_source_count"),
            "answerability": status.get("answerability"),
        },
    }


def public_response(
    record: dict[str, Any],
    *,
    redact_private_content: bool = False,
) -> dict[str, Any]:
    attempt = selected_attempt(record)
    final_response = _public_final_response(record.get("final_response"))
    evidence_metadata = _public_evidence(attempt)
    if redact_private_content and final_response is not None:
        final_response = {
            "answerability": final_response.get("answerability"),
            "answer": "[개인정보 위험으로 응답 내용 비공개]",
            "summary": "[개인정보 위험으로 응답 내용 비공개]",
            "procedure_steps": [],
            "notes": [],
            "limitations": [],
            "sources": [],
            "conflict_warning": {"exists": False, "description": None},
            "freshness": final_response.get("freshness"),
            "retrieval_status": final_response.get("retrieval_status"),
            "redacted_due_to_privacy": True,
        }
        evidence_metadata = []
    payload = {
        "run_id": record.get("run_id"),
        "round": record.get("round"),
        "ordinal": record.get("ordinal"),
        "question_id": record.get("question_id"),
        "question": record.get("question"),
        "dataset_category": record.get("dataset_category"),
        "dataset_question_type": record.get("dataset_question_type"),
        "status": record.get("status"),
        "evaluation_attempt_count": len(record.get("attempts") or []),
        "final_response": final_response,
        "injected_evidence_metadata": evidence_metadata,
    }
    return mask_nested(payload)


def ensure_no_private_markers(label: str, value: Any) -> None:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    markers = private_data_markers(encoded)
    if markers:
        raise ValueError(
            f"{label} still contains private-data patterns: {', '.join(markers)}"
        )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["analysis", "metric", "group", "count", "denominator", "rate"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(output.getvalue(), encoding="utf-8", newline="")
    temporary.replace(path)


def _metric_row(
    analysis: str, metric: str, group: str, value: dict[str, Any]
) -> dict[str, Any]:
    return {
        "analysis": analysis,
        "metric": metric,
        "group": group,
        "count": value.get("count", value.get("success_count")),
        "denominator": value.get("denominator"),
        "rate": value.get("rate"),
    }


def aggregate_csv_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for analysis in ("all_50", "exclude_q035"):
        aggregate = results[analysis]
        rows.append(
            {
                "analysis": analysis,
                "metric": "end_to_end_success",
                "group": "all",
                "count": aggregate["success_count"],
                "denominator": aggregate["question_count"],
                "rate": aggregate["success_rate"],
            }
        )
        rows.append(
            {
                "analysis": analysis,
                "metric": "system_error",
                "group": "all",
                "count": aggregate["system_error_count"],
                "denominator": aggregate["question_count"],
                "rate": round(
                    aggregate["system_error_count"] / aggregate["question_count"], 6
                ),
            }
        )
        for group, value in aggregate["by_expected_behavior"].items():
            rows.append(_metric_row(analysis, "end_to_end_success", group, value))
        for metric, value in aggregate["behavior_errors"].items():
            rows.append(_metric_row(analysis, metric, "opportunity_set", value))
        for key in (
            "content_accuracy_counts",
            "claim_support_counts",
            "source_display_counts",
            "temporal_counts",
            "audience_counts",
            "privacy_counts",
        ):
            denominator = sum(aggregate[key].values())
            for group, count in aggregate[key].items():
                rows.append(
                    {
                        "analysis": analysis,
                        "metric": key.removesuffix("_counts"),
                        "group": group,
                        "count": count,
                        "denominator": denominator,
                        "rate": round(count / denominator, 6) if denominator else None,
                    }
                )
    repeat = results["structured_response_behavior_repeat_agreement"]
    rows.append(
        {
            "analysis": "three_rounds",
            "metric": "structured_response_behavior_repeat_agreement",
            "group": "all",
            "count": repeat["three_of_three_count"],
            "denominator": repeat["question_count"],
            "rate": repeat["three_of_three_rate"],
        }
    )
    return rows


def build_outputs(
    *,
    run_dir: Path,
    judgments_path: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    assert_committed_file(manifest_path)
    summary = load_json(run_dir / "run.json")
    manifest = load_json(manifest_path)
    raw_path = run_dir / "raw.jsonl"
    if manifest.get("run_id") != summary.get("run_id"):
        raise ValueError("run manifest belongs to another run")
    if (manifest.get("private_raw") or {}).get("sha256") != sha256_file(raw_path):
        raise ValueError("run manifest does not match private raw")
    records = [
        row for row in load_jsonl(raw_path) if row.get("record_type") == "response"
    ]
    primary = primary_records(records)
    question_ids = {str(record["question_id"]) for record in primary}
    judgments_payload = load_json(judgments_path)
    if not judgments_payload.get("reveal_started_at"):
        raise ValueError("post-lock reveal/adjudication export is required")
    judgments = validated_judgment_index(
        judgments_payload,
        expected_run_id=str(summary["run_id"]),
        expected_raw_sha256=str(summary["raw_sha256"]),
        expected_question_ids=question_ids,
    )
    primary_by_id = {str(record["question_id"]): record for record in primary}
    for question_id, record in primary_by_id.items():
        if judgments[question_id].get("response_status") != record.get("status"):
            raise ValueError(
                f"{question_id}: judgment response status differs from the run"
            )
        if record.get("status") != "success":
            continue
        diagnostic = raw_output_diagnostic(record)
        review = judgments[question_id].get("raw_output_privacy_review")
        if diagnostic["markers"] and review not in {
            "safe_public_or_nonpersonal",
            "privacy_risk",
        }:
            raise ValueError(
                f"{question_id}: raw output sensitive patterns were not reviewed"
            )
        if not diagnostic["markers"] and review not in {
            "no_sensitive_pattern",
            "safe_public_or_nonpersonal",
            "privacy_risk",
        }:
            raise ValueError(f"{question_id}: raw output privacy diagnostic is missing")

    privacy_risk_question_ids = {
        question_id
        for question_id, judgment in judgments.items()
        if judgment.get("privacy") == "privacy_risk"
    }
    public_responses = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "run_id": summary["run_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "private_judgments_sha256": sha256_file(judgments_path),
        "responses": [
            public_response(
                record,
                redact_private_content=str(record.get("question_id"))
                in privacy_risk_question_ids,
            )
            for record in records
        ],
    }
    public_judgment_rows = []
    for question_id, judgment in judgments.items():
        row = deepcopy(judgment)
        if question_id in privacy_risk_question_ids:
            row["memo"] = "[개인정보 위험 관련 메모 비공개]"
            for revision in row.get("revision_history") or []:
                revision["reason"] = "[개인정보 위험 관련 조정 이유 비공개]"
        public_judgment_rows.append(row)
    public_judgments = mask_nested(
        {
            "schema_version": PUBLIC_SCHEMA_VERSION,
            "run_id": summary["run_id"],
            "manifest_sha256": sha256_file(manifest_path),
            "private_judgments_sha256": sha256_file(judgments_path),
            "primary_judgments_sha256": judgments_payload.get(
                "primary_judgments_sha256"
            ),
            "judge": judgments_payload.get("judge"),
            "rubric_sha256": judgments_payload.get("rubric_sha256"),
            "primary_exported_at": judgments_payload.get("primary_exported_at"),
            "reveal_started_at": judgments_payload.get("reveal_started_at"),
            "adjudicated_exported_at": judgments_payload.get("exported_at"),
            "judgments": public_judgment_rows,
        }
    )
    expected = load_expected_behaviors()
    aggregate_judgments = {
        question_id: row
        for question_id, row in judgments.items()
        if row.get("response_status") == "success"
    }
    aggregate_records = {question_id: row for question_id, row in primary_by_id.items()}
    results = {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "run_id": summary["run_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "private_judgments_sha256": sha256_file(judgments_path),
        "all_50": aggregate_primary(aggregate_records, expected, aggregate_judgments),
        "exclude_q035": aggregate_primary(
            aggregate_records,
            expected,
            aggregate_judgments,
            exclude_question_ids=frozenset({"Q035"}),
        ),
        "structured_response_behavior_repeat_agreement": structured_repeat_summary(
            records
        ),
        "raw_output_privacy_diagnostic_counts": {
            value: sum(
                row.get("raw_output_privacy_review") == value
                for row in judgments.values()
            )
            for value in (
                "no_sensitive_pattern",
                "safe_public_or_nonpersonal",
                "privacy_risk",
            )
        },
        "structured_behaviors_by_round": [
            {
                "question_id": question_id,
                "behaviors": [
                    model_behavior(
                        (
                            next(
                                record
                                for record in records
                                if record.get("question_id") == question_id
                                and record.get("round") == round_number
                            ).get("final_response")
                            or {}
                        ).get("answerability")
                    )
                    for round_number in (1, 2, 3)
                ],
            }
            for question_id in sorted(question_ids)
        ],
    }
    ensure_no_private_markers("public responses", public_responses)
    ensure_no_private_markers("public judgments", public_judgments)
    return public_responses, public_judgments, results


def main() -> None:
    args = parse_args()
    responses, judgments, results = build_outputs(
        run_dir=args.run_dir.resolve(),
        judgments_path=args.judgments.resolve(),
        manifest_path=args.manifest.resolve(),
    )
    write_json(args.responses_output, responses)
    write_json(args.judgments_output, judgments)
    results["public_artifacts"] = {
        "responses_sha256": sha256_file(args.responses_output),
        "judgments_sha256": sha256_file(args.judgments_output),
    }
    write_json(args.results_output, results)
    _write_csv(args.csv_output, aggregate_csv_rows(results))
    print(f"wrote: {args.responses_output.relative_to(REPO_ROOT)}")
    print(f"wrote: {args.judgments_output.relative_to(REPO_ROOT)}")
    print(f"wrote: {args.results_output.relative_to(REPO_ROOT)}")
    print(f"wrote: {args.csv_output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
