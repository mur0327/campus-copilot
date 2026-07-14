"""Freeze a commit-safe manifest for a completed private EXP-07 run."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.exp07_common import (  # noqa: E402
    RUN_SCHEMA_VERSION,
    canonical_json_hash,
    load_jsonl,
    private_data_markers,
    sha256_file,
    write_json,
)
from eval.exp07_corpus import comparable_fingerprint, fingerprints_match  # noqa: E402

QUESTIONS_PATH = REPO_ROOT / "eval" / "questions.csv"
QREL_PATH = REPO_ROOT / "eval" / "qrel-v4-adjudicated.json"
QREL_MANIFEST_PATH = REPO_ROOT / "eval" / "qrel-v4-manifest.sha256"
RUBRIC_PATH = REPO_ROOT / "eval" / "exp07-answer-rubric.md"
PROMPT_PATH = REPO_ROOT / "backend" / "app" / "prompts" / "chat_answer.md"
DEFAULT_OUTPUT = REPO_ROOT / "eval" / "exp07-run-manifest.json"
KOREA_TZ = ZoneInfo("Asia/Seoul")
MANIFEST_SCHEMA_VERSION = "exp07-run-manifest-1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the safe post-run EXP-07 manifest."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON object required")
    return payload


def canonical_question_ids(path: Path = QUESTIONS_PATH) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        return [str(row["id"]) for row in csv.DictReader(input_file)]


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _local_date(value: str) -> str | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(KOREA_TZ).date().isoformat()


def _raw_sensitive_markers(records: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in records:
        for attempt in record.get("attempts") or []:
            for call in attempt.get("llm_calls") or []:
                raw_output = call.get("raw_output")
                if isinstance(raw_output, str):
                    counts.update(private_data_markers(raw_output))
    return counts


def validate_run_artifacts(
    *,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
    before: dict[str, Any],
    after: dict[str, Any],
    raw_path: Path,
    expected_question_ids: list[str],
    current_git_head: str | None,
) -> list[str]:
    failures: list[str] = []
    metadata = summary.get("metadata") or {}
    if summary.get("schema_version") != RUN_SCHEMA_VERSION:
        failures.append("run.json schema_version mismatch")
    if summary.get("status") != "completed":
        failures.append("run status is not completed")
    if summary.get("corpus_unchanged") is not True or not fingerprints_match(
        before, after
    ):
        failures.append("corpus fingerprint changed or is unavailable")
    if summary.get("finalization_errors"):
        failures.append("run finalization contains errors")
    if metadata.get("canonical_run") is not True:
        failures.append("run is not marked canonical")
    if metadata.get("rounds") != 3 or metadata.get("question_count") != 50:
        failures.append("canonical run requires 3 rounds and 50 questions")
    if set(metadata.get("question_order") or []) != set(expected_question_ids):
        failures.append("question order does not contain the canonical question set")
    if len(metadata.get("question_order") or []) != len(expected_question_ids):
        failures.append("question order length differs from the canonical question set")
    if summary.get("raw_sha256") != sha256_file(raw_path):
        failures.append("raw.jsonl SHA-256 mismatch")
    if summary.get("raw_size") != raw_path.stat().st_size:
        failures.append("raw.jsonl size mismatch")
    if summary.get("planned_response_records") != 150:
        failures.append("planned response count is not 150")

    metadata_rows = [row for row in records if row.get("record_type") == "run_metadata"]
    response_rows = [row for row in records if row.get("record_type") == "response"]
    if len(metadata_rows) != 1 or canonical_json_hash(
        metadata_rows[0]
    ) != canonical_json_hash(metadata):
        failures.append("raw metadata does not match run.json")
    if len(response_rows) != 150 or summary.get("completed_response_records") != len(
        response_rows
    ):
        failures.append("raw response count is not 150")

    expected_order = metadata.get("question_order") or []
    seen_keys: set[tuple[int, str]] = set()
    observed_dates: set[str] = set()
    for round_number in (1, 2, 3):
        rows = sorted(
            (row for row in response_rows if row.get("round") == round_number),
            key=lambda row: int(row.get("ordinal") or 0),
        )
        if [row.get("question_id") for row in rows] != expected_order:
            failures.append(f"round {round_number} order differs from frozen order")
        if [row.get("ordinal") for row in rows] != list(range(1, 51)):
            failures.append(f"round {round_number} ordinals are not 1 through 50")
        for row in rows:
            key = (round_number, str(row.get("question_id") or ""))
            if key in seen_keys:
                failures.append(f"duplicate response record: {key}")
            seen_keys.add(key)
            if row.get("schema_version") != RUN_SCHEMA_VERSION:
                failures.append(f"response schema mismatch: {key}")
            if row.get("run_id") != summary.get("run_id"):
                failures.append(f"response run_id mismatch: {key}")
            attempts = row.get("attempts") or []
            if not attempts or any(
                attempt.get("status") not in {"success", "error"}
                for attempt in attempts
            ):
                failures.append(f"invalid attempt list: {key}")
            if len(attempts) > 2:
                failures.append(f"more than one evaluation-level retry: {key}")
            if len(attempts) == 2 and attempts[0].get("retryable") is not True:
                failures.append(f"non-retryable failure was retried: {key}")
            status = row.get("status")
            if status == "success":
                selected = row.get("selected_attempt")
                if selected not in {1, 2} or not isinstance(
                    row.get("final_response"), dict
                ):
                    failures.append(
                        f"successful record has no valid selected response: {key}"
                    )
                elif attempts[selected - 1].get(
                    "status"
                ) != "success" or canonical_json_hash(
                    attempts[selected - 1].get("final_response")
                ) != canonical_json_hash(row.get("final_response")):
                    failures.append(
                        f"selected attempt differs from final response: {key}"
                    )
                elif any(
                    attempt.get("status") == "success"
                    for attempt in attempts[: selected - 1]
                ):
                    failures.append(
                        f"record did not select the first successful attempt: {key}"
                    )
            elif status == "system_error":
                if row.get("final_response") is not None:
                    failures.append(f"system_error contains a final response: {key}")
                if any(attempt.get("status") == "success" for attempt in attempts):
                    failures.append(
                        f"system_error contains a successful attempt: {key}"
                    )
            else:
                failures.append(f"invalid response status: {key}")
            for attempt in attempts:
                for field in ("started_at", "completed_at"):
                    local_date = _local_date(str(attempt.get(field) or ""))
                    if local_date:
                        observed_dates.add(local_date)

    if observed_dates != {str(summary.get("started_date") or "")}:
        failures.append(
            "responses were not completed on the frozen Korean calendar date"
        )
    if current_git_head is not None and metadata.get("git_commit") != current_git_head:
        failures.append("current Git HEAD differs from the pre-run commit")
    computed_system_errors = sum(
        row.get("status") == "system_error" for row in response_rows
    )
    computed_llm_calls = sum(
        len(attempt.get("llm_calls") or [])
        for row in response_rows
        for attempt in row.get("attempts") or []
    )
    computed_json_repairs = sum(
        call.get("kind") == "json_repair"
        for row in response_rows
        for attempt in row.get("attempts") or []
        for call in attempt.get("llm_calls") or []
    )
    computed_embedding_calls = sum(
        len(attempt.get("embedding_calls") or [])
        for row in response_rows
        for attempt in row.get("attempts") or []
    )
    for field, computed in (
        ("system_error_count", computed_system_errors),
        ("llm_call_count", computed_llm_calls),
        ("llm_json_repair_count", computed_json_repairs),
        ("embedding_call_count", computed_embedding_calls),
    ):
        if summary.get(field) != computed:
            failures.append(f"{field} differs from raw records")
    return failures


def build_manifest(
    run_dir: Path,
    *,
    expected_question_ids: list[str] | None = None,
    current_git_head: str | None = None,
    verify_current_files: bool = True,
) -> dict[str, Any]:
    summary_path = run_dir / "run.json"
    raw_path = run_dir / "raw.jsonl"
    before_path = run_dir / "corpus-before.json"
    after_path = run_dir / "corpus-after.json"
    summary = load_json(summary_path)
    records = load_jsonl(raw_path)
    before = load_json(before_path)
    after = load_json(after_path)
    question_ids = expected_question_ids or canonical_question_ids()
    failures = validate_run_artifacts(
        summary=summary,
        records=records,
        before=before,
        after=after,
        raw_path=raw_path,
        expected_question_ids=question_ids,
        current_git_head=current_git_head,
    )
    if verify_current_files:
        metadata = summary.get("metadata") or {}
        frozen_files = {
            "questions_sha256": QUESTIONS_PATH,
            "qrel_sha256": QREL_PATH,
            "qrel_manifest_sha256": QREL_MANIFEST_PATH,
            "rubric_sha256": RUBRIC_PATH,
            "prompt_sha256": PROMPT_PATH,
        }
        for field, path in frozen_files.items():
            if metadata.get(field) != sha256_file(path):
                failures.append(f"{field} differs from the pre-run file")
    if failures:
        raise ValueError("EXP-07 run manifest gate failed:\n- " + "\n- ".join(failures))

    metadata = summary["metadata"]
    responses = [row for row in records if row.get("record_type") == "response"]
    error_types = Counter(
        str(attempt.get("error_type") or "unknown")
        for row in responses
        for attempt in row.get("attempts") or []
        if attempt.get("status") == "error"
    )
    marker_counts = _raw_sensitive_markers(responses)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": summary["run_id"],
        "status": summary["status"],
        "run_completed_at": summary["completed_at"],
        "generated_at": datetime.now(UTC).isoformat(),
        "provenance": {
            "git_commit": metadata["git_commit"],
            "questions_sha256": metadata["questions_sha256"],
            "qrel_sha256": metadata["qrel_sha256"],
            "qrel_manifest_sha256": metadata["qrel_manifest_sha256"],
            "rubric_sha256": metadata["rubric_sha256"],
            "prompt_sha256": metadata["prompt_sha256"],
        },
        "configuration": {
            "provider": metadata["provider"],
            "llm_model": metadata["llm_model"],
            "embedding_model": metadata["embedding_model"],
            "runtime_packages": metadata["runtime_packages"],
            "sampling_parameters": metadata["sampling_parameters"],
            "retriever": metadata["retriever"],
            "seed": metadata["seed"],
            "rounds": metadata["rounds"],
            "question_order": metadata["question_order"],
            "llm_rpm_limit": metadata["llm_rpm_limit"],
            "embedding_rpm_limit": metadata["embedding_rpm_limit"],
            "safety_factor": metadata["safety_factor"],
            "retry_policy": metadata["retry_policy"],
            "cache_bypassed": metadata["cache_bypassed"],
            "timezone": metadata["timezone"],
        },
        "records": {
            "question_count": 50,
            "response_record_count": len(responses),
            "success_count": sum(row.get("status") == "success" for row in responses),
            "system_error_count": sum(
                row.get("status") == "system_error" for row in responses
            ),
            "evaluation_retry_count": sum(
                len(row.get("attempts") or []) - 1 for row in responses
            ),
            "llm_call_count": summary["llm_call_count"],
            "llm_json_repair_count": summary["llm_json_repair_count"],
            "embedding_call_count": summary["embedding_call_count"],
            "error_type_counts": dict(sorted(error_types.items())),
        },
        "private_raw": {
            "file_name": raw_path.name,
            "size": raw_path.stat().st_size,
            "sha256": sha256_file(raw_path),
            "sensitive_pattern_counts": dict(sorted(marker_counts.items())),
        },
        "corpus": {
            "unchanged": True,
            "before_file_sha256": sha256_file(before_path),
            "after_file_sha256": sha256_file(after_path),
            "fingerprint": comparable_fingerprint(before),
        },
    }


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args.run_dir, current_git_head=git_head())
    write_json(args.output, manifest)
    print(f"wrote: {args.output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
