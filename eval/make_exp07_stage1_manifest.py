"""Freeze safe lineage for the private EXP-07 stage-one judgment snapshot."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.exp07_common import (  # noqa: E402
    ABSTENTION_NOTICE_VALUES,
    ACTUAL_BEHAVIORS,
    JUDGMENT_SCHEMA_VERSION,
    canonical_json_hash,
    load_jsonl,
    sha256_file,
    write_json,
)
from eval.make_exp07_primary_sheet import (  # noqa: E402
    assert_committed_file,
    primary_records,
    selected_attempt,
)
from eval.run_questions import normalize_url  # noqa: E402

RUN_MANIFEST_PATH = REPO_ROOT / "eval" / "exp07-run-manifest.json"
QREL_PATH = REPO_ROOT / "eval" / "qrel-v4-adjudicated.json"
QREL_MANIFEST_PATH = REPO_ROOT / "eval" / "qrel-v4-manifest.sha256"
RUBRIC_PATH = REPO_ROOT / "eval" / "exp07-answer-rubric.md"
DEFAULT_OUTPUT = REPO_ROOT / "eval" / "exp07-stage1-manifest.json"
MANIFEST_SCHEMA_VERSION = "exp07-stage1-manifest-1"

STAGE2_FIELDS = (
    "content_accuracy",
    "claim_support",
    "source_display",
    "temporal_validity",
    "audience_scope",
    "privacy",
)
IMMUTABLE_STAGE1_FIELDS = (
    "response_status",
    "actual_behavior",
    "abstention_notice",
    "stage1_locked_at",
)
QREL_LINEAGE_PATHS = (
    REPO_ROOT / "eval" / "gold_pages_v4.csv",
    REPO_ROOT / "eval" / "gold_evidence_v4.csv",
    REPO_ROOT / "eval" / "question_judgments_v4.csv",
    REPO_ROOT / "eval" / "target_sources_v4.csv",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the safe EXP-07 stage-one lineage manifest."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("stage1_snapshot", type=Path)
    parser.add_argument("--primary-html", type=Path, default=None)
    parser.add_argument("--run-manifest", type=Path, default=RUN_MANIFEST_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON object required")
    return payload


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _private_file(path: Path, *, run_dir: Path, label: str) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(run_dir.resolve()):
        raise ValueError(f"{label} must stay inside the private run directory")
    if resolved.stat().st_mode & 0o077:
        raise ValueError(f"{label} must use owner-only permissions")


def _sha_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, file_name = line.split(maxsplit=1)
        entries[file_name.strip()] = digest
    return entries


def canonicalize_primary_sheet_judgment(
    judgment: Mapping[str, Any],
) -> dict[str, Any]:
    row = dict(judgment)
    if (
        row.get("response_status") == "success"
        and row.get("actual_behavior") != "abstain"
        and row.get("abstention_notice") in {None, ""}
    ):
        # The frozen primary HTML intended to set this value but its select
        # omitted the matching option, so browsers exported an empty string.
        row["abstention_notice"] = "not_applicable"
    return row


def validate_stage1_snapshot(
    payload: Mapping[str, Any],
    *,
    expected_run_id: str,
    expected_raw_sha256: str,
    expected_rubric_sha256: str,
    expected_statuses: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    failures: list[str] = []
    if payload.get("schema_version") != JUDGMENT_SCHEMA_VERSION:
        failures.append(f"schema_version is not {JUDGMENT_SCHEMA_VERSION}")
    if payload.get("run_id") != expected_run_id:
        failures.append("run_id differs from the completed run")
    if payload.get("private_raw_sha256") != expected_raw_sha256:
        failures.append("private_raw_sha256 differs from the completed run")
    if payload.get("rubric_sha256") != expected_rubric_sha256:
        failures.append("rubric_sha256 differs from the frozen rubric")
    rows = payload.get("judgments")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("judgments must be an object array")

    indexed: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(rows):
        row = canonicalize_primary_sheet_judgment(raw_row)
        question_id = str(row.get("question_id") or "")
        if not question_id:
            failures.append(f"judgments[{index}] has no question_id")
            continue
        if question_id in indexed:
            failures.append(f"duplicate judgment: {question_id}")
            continue
        indexed[question_id] = row
        expected_status = expected_statuses.get(question_id)
        if row.get("response_status") != expected_status:
            failures.append(f"{question_id}: response_status differs from the run")
        if expected_status == "system_error":
            if row.get("stage1_locked_at") or row.get("stage2_locked_at"):
                failures.append(f"{question_id}: system_error contains a judgment lock")
            continue
        if expected_status != "success":
            failures.append(f"{question_id}: unknown response status")
            continue
        behavior = str(row.get("actual_behavior") or "")
        notice = str(row.get("abstention_notice") or "")
        if behavior not in ACTUAL_BEHAVIORS:
            failures.append(f"{question_id}: invalid actual_behavior")
        if notice not in ABSTENTION_NOTICE_VALUES:
            failures.append(f"{question_id}: invalid abstention_notice")
        if behavior == "abstain" and notice not in {"clear", "missing"}:
            failures.append(f"{question_id}: abstain has no notice judgment")
        if behavior != "abstain" and notice != "not_applicable":
            failures.append(f"{question_id}: non-abstain has an abstention notice")
        if not isinstance(row.get("stage1_locked_at"), str) or not row.get(
            "stage1_locked_at"
        ):
            failures.append(f"{question_id}: stage one is not locked")
        if row.get("stage2_locked_at"):
            failures.append(f"{question_id}: stage two is already locked")
        for field in STAGE2_FIELDS:
            if row.get(field) not in {None, ""}:
                failures.append(f"{question_id}: {field} was entered before stage two")
        hold_axes = row.get("hold_axes")
        if row.get("hold") is not False or hold_axes not in (None, []):
            failures.append(f"{question_id}: stage-two hold state is not empty")
        if row.get("memo") not in {None, ""}:
            failures.append(f"{question_id}: stage-two memo is not empty")
        if row.get("revision_history") not in (None, []):
            failures.append(f"{question_id}: revision history is not empty")

    if set(indexed) != set(expected_statuses):
        failures.append("stage-one question set differs from the completed run")
    if failures:
        raise ValueError("invalid stage-one snapshot:\n- " + "\n- ".join(failures))
    return indexed


def assert_stage1_unchanged(
    baseline_payload: Mapping[str, Any],
    final_payload: Mapping[str, Any],
) -> None:
    lineage_fields = (
        "schema_version",
        "run_id",
        "private_raw_sha256",
        "rubric_sha256",
    )
    failures = [
        f"{field} differs from the frozen stage-one snapshot"
        for field in lineage_fields
        if baseline_payload.get(field) != final_payload.get(field)
    ]
    baseline_rows = {
        str(row.get("question_id") or ""): row
        for row in baseline_payload.get("judgments") or []
    }
    final_rows = {
        str(row.get("question_id") or ""): row
        for row in final_payload.get("judgments") or []
    }
    if set(baseline_rows) != set(final_rows):
        failures.append("question set differs from the frozen stage-one snapshot")
    for question_id in sorted(set(baseline_rows) & set(final_rows)):
        baseline_row = canonicalize_primary_sheet_judgment(
            baseline_rows[question_id]
        )
        final_row = canonicalize_primary_sheet_judgment(final_rows[question_id])
        for field in IMMUTABLE_STAGE1_FIELDS:
            if baseline_row.get(field) != final_row.get(field):
                failures.append(f"{question_id}: {field} differs from stage one")
    if failures:
        raise ValueError("stage-one lineage check failed:\n- " + "\n- ".join(failures))


def injected_evidence_coverage(
    records: list[dict[str, Any]], qrel: Mapping[str, Any]
) -> dict[str, Any]:
    context_rows: list[dict[str, str]] = []
    primary = primary_records(records)
    for record in primary:
        attempt = selected_attempt(record)
        for candidate in (attempt or {}).get("evidence_candidates") or []:
            for context in candidate.get("context_results") or []:
                context_rows.append(
                    {
                        "question_id": str(record["question_id"]),
                        "canonical_url": normalize_url(str(context.get("url") or "")),
                        "chunk_id": str(context.get("chunk_id") or ""),
                        "content_hash": str(context.get("content_hash") or ""),
                    }
                )

    page_index = {
        (str(row["question_id"]), normalize_url(str(row["canonical_url"]))): row
        for row in qrel.get("pages") or []
    }
    chunk_index = {
        (str(row["question_id"]), str(row["chunk_id"])): row
        for row in qrel.get("evidence") or []
    }
    unique_pages = {
        (row["question_id"], row["canonical_url"]): row for row in context_rows
    }
    unique_chunks = {
        (row["question_id"], row["chunk_id"]): row for row in context_rows
    }
    coverage_rows: list[dict[str, str]] = []
    page_counts: Counter[str] = Counter()
    chunk_counts: Counter[str] = Counter()
    unjudged_page_questions: set[str] = set()
    unjudged_chunk_questions: set[str] = set()

    for key, row in unique_pages.items():
        qrel_row = page_index.get(key)
        status = (
            str(qrel_row.get("support_grade") or "unjudged")
            if qrel_row and qrel_row.get("judged") is True
            else "unjudged"
        )
        page_counts[status] += 1
        if status == "unjudged":
            unjudged_page_questions.add(row["question_id"])

    for key, row in unique_chunks.items():
        qrel_row = chunk_index.get(key)
        if not qrel_row or qrel_row.get("judged") is not True:
            status = "unjudged"
            unjudged_chunk_questions.add(row["question_id"])
        elif qrel_row.get("evidence_grade") in {"full", "partial"}:
            status = "positive"
        else:
            status = "judged_non_support"
        chunk_counts[status] += 1
        page_qrel = page_index.get((row["question_id"], row["canonical_url"]))
        page_status = (
            str(page_qrel.get("support_grade") or "unjudged")
            if page_qrel and page_qrel.get("judged") is True
            else "unjudged"
        )
        coverage_rows.append(
            {
                **row,
                "page_status": page_status,
                "chunk_status": status,
            }
        )

    injected_question_ids = {row["question_id"] for row in context_rows}
    return {
        "injected_context_row_count": len(context_rows),
        "unique_question_page_count": len(unique_pages),
        "page_status_counts": dict(sorted(page_counts.items())),
        "unique_question_chunk_count": len(unique_chunks),
        "chunk_status_counts": dict(sorted(chunk_counts.items())),
        "questions_without_injected_evidence": sorted(
            {str(row["question_id"]) for row in primary} - injected_question_ids
        ),
        "questions_with_unjudged_page": sorted(unjudged_page_questions),
        "questions_with_unjudged_chunk": sorted(unjudged_chunk_questions),
        "coverage_rows_sha256": canonical_json_hash(
            sorted(
                coverage_rows,
                key=lambda row: (row["question_id"], row["chunk_id"]),
            )
        ),
    }


def build_stage1_manifest(
    *,
    run_dir: Path,
    stage1_snapshot: Path,
    primary_html: Path,
    run_manifest_path: Path = RUN_MANIFEST_PATH,
    qrel_path: Path = QREL_PATH,
    qrel_manifest_path: Path = QREL_MANIFEST_PATH,
    rubric_path: Path = RUBRIC_PATH,
    current_git_head: str | None = None,
    qrel_lineage_paths: tuple[Path, ...] = QREL_LINEAGE_PATHS,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    stage1_snapshot = stage1_snapshot.resolve()
    primary_html = primary_html.resolve()
    _private_file(stage1_snapshot, run_dir=run_dir, label="stage-one snapshot")
    _private_file(primary_html, run_dir=run_dir, label="primary judgment HTML")

    summary = load_json(run_dir / "run.json")
    raw_path = run_dir / "raw.jsonl"
    records = load_jsonl(raw_path)
    run_manifest = load_json(run_manifest_path)
    qrel = load_json(qrel_path)
    snapshot = load_json(stage1_snapshot)
    if run_manifest.get("run_id") != summary.get("run_id"):
        raise ValueError("run manifest belongs to another run")
    if (run_manifest.get("private_raw") or {}).get("sha256") != sha256_file(
        raw_path
    ):
        raise ValueError("run manifest raw SHA-256 differs from the private run")
    provenance = run_manifest.get("provenance") or {}
    if provenance.get("rubric_sha256") != sha256_file(rubric_path):
        raise ValueError("frozen rubric differs from the run manifest")
    if provenance.get("qrel_sha256") != sha256_file(qrel_path):
        raise ValueError("frozen qrel differs from the run manifest")
    if provenance.get("qrel_manifest_sha256") != sha256_file(qrel_manifest_path):
        raise ValueError("qrel manifest differs from the completed run")

    primary = primary_records(records)
    expected_statuses = {
        str(record["question_id"]): str(record["status"]) for record in primary
    }
    indexed = validate_stage1_snapshot(
        snapshot,
        expected_run_id=str(summary["run_id"]),
        expected_raw_sha256=str(summary["raw_sha256"]),
        expected_rubric_sha256=str(provenance["rubric_sha256"]),
        expected_statuses=expected_statuses,
    )
    qrel_manifest_entries = _sha_manifest(qrel_manifest_path)
    qrel_lineage: dict[str, str] = {}
    for path in qrel_lineage_paths:
        relative = path.resolve().relative_to(REPO_ROOT).as_posix()
        actual = sha256_file(path)
        if qrel_manifest_entries.get(relative) != actual:
            raise ValueError(f"{relative} differs from qrel-v4-manifest.sha256")
        qrel_lineage[relative] = actual

    stage1_times = sorted(
        str(row["stage1_locked_at"])
        for row in indexed.values()
        if row.get("stage1_locked_at")
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": summary["run_id"],
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": current_git_head or git_head(),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "private_stage1": {
            "file_name": stage1_snapshot.name,
            "size": stage1_snapshot.stat().st_size,
            "sha256": sha256_file(stage1_snapshot),
            "exported_at": snapshot.get("exported_at"),
            "judge": snapshot.get("judge"),
            "judgment_count": len(indexed),
            "stage1_locked_count": len(stage1_times),
            "stage2_locked_count": sum(
                bool(row.get("stage2_locked_at")) for row in indexed.values()
            ),
            "stage2_value_count": sum(
                any(row.get(field) not in {None, ""} for field in STAGE2_FIELDS)
                for row in indexed.values()
            ),
            "first_locked_at": stage1_times[0] if stage1_times else None,
            "last_locked_at": stage1_times[-1] if stage1_times else None,
        },
        "primary_html": {
            "file_name": primary_html.name,
            "size": primary_html.stat().st_size,
            "sha256": sha256_file(primary_html),
        },
        "provenance": {
            "private_raw_sha256": summary["raw_sha256"],
            "rubric_sha256": provenance["rubric_sha256"],
            "qrel_sha256": provenance["qrel_sha256"],
            "qrel_manifest_sha256": provenance["qrel_manifest_sha256"],
            "qrel_lineage": qrel_lineage,
            "qrel_judgment_date": qrel.get("date"),
            "run_date": summary.get("started_date"),
        },
        "round1_injected_evidence_coverage": injected_evidence_coverage(
            records, qrel
        ),
        "frozen_interpretation": {
            "content_accuracy_basis": "frozen_v4_reference_bundle",
            "claim_support_basis": "round1_actual_injected_evidence",
            "unjudged_injected_evidence": "use_unverifiable_only_when_the_claim_cannot_be_confirmed_in_the_frozen_v4_reference",
            "full_answer_behavior": "substantive_answer_without_an_explicit_material_limitation;_accuracy_is_judged_separately",
            "pure_abstain_not_applicable": "no_supplementary_factual_guidance_and_no_displayed_sources",
            "temporal_validity_basis": "run_date",
            "primary_html_blank_non_abstain_notice": "normalized_to_not_applicable",
        },
    }


def main() -> None:
    args = parse_args()
    assert_committed_file(args.run_manifest)
    run_dir = args.run_dir.resolve()
    primary_html = (
        args.primary_html or (run_dir / "exp07-primary-judgment.html")
    ).resolve()
    manifest = build_stage1_manifest(
        run_dir=run_dir,
        stage1_snapshot=args.stage1_snapshot,
        primary_html=primary_html,
        run_manifest_path=args.run_manifest,
    )
    write_json(args.output, manifest)
    print(f"wrote: {args.output.resolve().relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
