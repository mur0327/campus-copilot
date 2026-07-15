import asyncio
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from eval import publish_exp07 as publish_exp07_module  # noqa: E402
from eval.exp07_common import (  # noqa: E402
    aggregate_primary,
    behavior_error,
    mask_nested,
    mask_private_data,
    private_data_markers,
    strict_success,
    structured_repeat_summary,
    validated_judgment_index,
    write_private_text,
)
from eval.exp07_corpus import (  # noqa: E402
    bm25_fingerprint,
    chroma_fingerprint,
    fingerprints_match,
)
from eval.make_exp07_manifest import build_manifest  # noqa: E402
from eval.make_exp07_primary_sheet import render_sheet as render_primary_sheet  # noqa: E402
from eval.make_exp07_reveal_sheet import render_sheet as render_reveal_sheet  # noqa: E402
from eval.make_exp07_stage1_manifest import (  # noqa: E402
    assert_stage1_unchanged,
    injected_evidence_coverage,
    validate_stage1_snapshot,
)
from eval.publish_exp07 import public_response  # noqa: E402
from eval.run_exp07 import (  # noqa: E402
    AsyncStartRateLimiter,
    SyncStartRateLimiter,
    assert_gemini_transport_retry_disabled,
    is_retryable_execution_error,
    retry_after_seconds,
)


def full_judgment(question_id: str, *, behavior: str = "full_answer") -> dict:
    return {
        "question_id": question_id,
        "response_status": "success",
        "actual_behavior": behavior,
        "abstention_notice": "clear" if behavior == "abstain" else "not_applicable",
        "content_accuracy": "fully_correct" if behavior != "abstain" else "not_applicable",
        "claim_support": "fully_supported" if behavior != "abstain" else "not_applicable",
        "source_display": "complete" if behavior != "abstain" else "not_applicable",
        "temporal_validity": "current" if behavior != "abstain" else "not_applicable",
        "audience_scope": "match" if behavior != "abstain" else "not_applicable",
        "privacy": "safe",
        "hold": False,
        "hold_axes": [],
        "memo": "",
        "stage1_locked_at": "2026-07-15T01:00:00+00:00",
        "stage2_locked_at": "2026-07-15T02:00:00+00:00",
        "revision_history": [],
    }


def stage1_judgment(question_id: str, *, behavior: str = "full_answer") -> dict:
    row = full_judgment(question_id, behavior=behavior)
    for field in (
        "content_accuracy",
        "claim_support",
        "source_display",
        "temporal_validity",
        "audience_scope",
        "privacy",
    ):
        row[field] = ""
    row["stage2_locked_at"] = None
    return row


def response_record(
    question_id: str,
    *,
    round_number: int = 1,
    answerability: str = "answerable",
    answer: str = "공식 안내입니다.",
) -> dict:
    result = {
        "chunk_id": "5c8e58fe-51e3-4f38-8b2b-8bedc39d9971",
        "document_id": "ad4fd882-e088-4e20-9f0e-2db89b388f59",
        "content": "근거 전문 062-940-0000",
        "content_hash": "hash",
        "chunk_type": "text",
        "chunk_index": 0,
        "score": 1.0,
        "relevance": "high",
        "title": "공식 안내",
        "url": "https://example.test/guide",
        "menu_path": "안내 > 절차",
        "category": None,
        "source_scope": "general_academic",
        "page_kind": "academic",
        "crawled_at": "2026-07-15T00:00:00+00:00",
        "meta": {},
    }
    final = {
        "answerability": answerability,
        "answer": answer,
        "summary": answer,
        "procedure_steps": [],
        "notes": [],
        "limitations": [],
        "sources": [
            {
                "title": "공식 안내",
                "url": "https://example.test/guide",
                "crawled_at": "2026-07-15T00:00:00+00:00",
                "freshness": "recent",
                "chunk_id": result["chunk_id"],
            }
        ],
        "conflict_warning": {"exists": False, "description": None},
        "freshness": "recent",
        "retrieval_status": {
            "mode": "hybrid",
            "degraded": False,
            "semantic_available": True,
            "bm25_available": True,
            "semantic_error": None,
            "bm25_error": None,
            "evidence_candidate_count": 1,
            "display_source_count": 1,
            "answerability": answerability,
        },
    }
    attempt = {
        "started_at": "2026-07-15T00:00:00+00:00",
        "completed_at": "2026-07-15T00:00:01+00:00",
        "status": "success",
        "retrieval_status": final["retrieval_status"],
        "retrieved": [result],
        "evidence_candidates": [{"source_number": 1, "display_result": result, "context_results": [result]}],
        "conflict_warning": final["conflict_warning"],
        "embedding_calls": [{"status": "success"}],
        "llm_calls": [
            {
                "kind": "initial",
                "status": "success",
                "raw_output": "원시 출력 private@example.test",
            }
        ],
        "final_response": final,
    }
    return {
        "record_type": "response",
        "schema_version": "exp07-run-1",
        "run_id": "exp07-test",
        "round": round_number,
        "ordinal": int(question_id[1:]),
        "question_id": question_id,
        "question": f"질문 {question_id}",
        "dataset_category": "학사",
        "dataset_question_type": "fact",
        "status": "success",
        "selected_attempt": 1,
        "attempts": [attempt],
        "final_response": final,
    }


def test_private_data_masking_preserves_dates_and_uuid():
    value = (
        "실행일 20260715, 표기 2026-0715, "
        "청크 5c8e58fe-51e3-4f38-8b2b-8bedc39d9971, "
        "학번: 2026123456, 062-940-0000, private@example.test"
    )

    masked = mask_private_data(value)

    assert "20260715" in masked
    assert "2026-0715" in masked
    assert "5c8e58fe-51e3-4f38-8b2b-8bedc39d9971" in masked
    assert "학번: [학번 마스킹]" in masked
    assert "[전화번호 마스킹]" in masked
    assert "[이메일 마스킹]" in masked
    assert private_data_markers("2026-0715 5c8e58fe-51e3-4f38-8b2b-8bedc39d9971") == []
    assert mask_nested({"rows": [value]})["rows"][0] == masked


def test_private_artifacts_are_written_with_owner_only_permissions(tmp_path):
    path = tmp_path / "private.html"

    write_private_text(path, "private")

    assert path.read_text(encoding="utf-8") == "private"
    assert path.stat().st_mode & 0o777 == 0o600


def test_behavior_and_strict_success_contract():
    judgment = full_judgment("Q001")

    assert behavior_error("full_answer", "qualified_answer") == "unnecessary_qualification"
    assert behavior_error("abstain", "qualified_answer") == "over_answer"
    assert behavior_error("qualified_answer", "abstain") == "over_rejection"
    assert strict_success(
        expected_behavior="full_answer",
        response_status="success",
        judgment=judgment,
    )

    judgment["temporal_validity"] = "unknown"
    assert not strict_success(
        expected_behavior="full_answer",
        response_status="success",
        judgment=judgment,
    )

    judgment = full_judgment("Q001")
    judgment["content_accuracy"] = "not_applicable"
    judgment["claim_support"] = "not_applicable"
    judgment["source_display"] = "not_applicable"
    assert not strict_success(
        expected_behavior="full_answer",
        response_status="success",
        judgment=judgment,
    )


def test_judgment_gate_requires_locks_and_resolved_holds():
    row = full_judgment("Q001")
    payload = {
        "schema_version": "exp07-judgment-1",
        "run_id": "run",
        "private_raw_sha256": "raw",
        "judgments": [row],
    }

    assert (
        validated_judgment_index(
            payload,
            expected_run_id="run",
            expected_raw_sha256="raw",
            expected_question_ids={"Q001"},
        )["Q001"]
        == row
    )

    payload["judgments"][0]["hold"] = True
    with pytest.raises(ValueError, match="판정보류"):
        validated_judgment_index(payload)


def test_stage1_snapshot_is_frozen_before_stage_two_and_compared_later():
    row = stage1_judgment("Q001")
    row["abstention_notice"] = ""
    payload = {
        "schema_version": "exp07-judgment-1",
        "run_id": "run",
        "private_raw_sha256": "raw",
        "rubric_sha256": "rubric",
        "judgments": [row],
    }

    assert validate_stage1_snapshot(
        payload,
        expected_run_id="run",
        expected_raw_sha256="raw",
        expected_rubric_sha256="rubric",
        expected_statuses={"Q001": "success"},
    )["Q001"]["abstention_notice"] == "not_applicable"

    final_payload = deepcopy(payload)
    final_payload["judgments"][0].update(full_judgment("Q001"))
    assert_stage1_unchanged(payload, final_payload)

    final_payload["judgments"][0]["actual_behavior"] = "abstain"
    with pytest.raises(ValueError, match="actual_behavior differs from stage one"):
        assert_stage1_unchanged(payload, final_payload)

    final_payload = deepcopy(payload)
    final_payload["rubric_sha256"] = "other-rubric"
    with pytest.raises(ValueError, match="rubric_sha256 differs"):
        assert_stage1_unchanged(payload, final_payload)


def test_stage1_snapshot_does_not_normalize_a_blank_abstain_notice():
    row = stage1_judgment("Q001", behavior="abstain")
    row["abstention_notice"] = ""
    payload = {
        "schema_version": "exp07-judgment-1",
        "run_id": "run",
        "private_raw_sha256": "raw",
        "rubric_sha256": "rubric",
        "judgments": [row],
    }

    with pytest.raises(ValueError, match="invalid abstention_notice"):
        validate_stage1_snapshot(
            payload,
            expected_run_id="run",
            expected_raw_sha256="raw",
            expected_rubric_sha256="rubric",
            expected_statuses={"Q001": "success"},
        )


def test_injected_evidence_coverage_distinguishes_unjudged_rows():
    records = [response_record(f"Q{index:03d}") for index in range(1, 51)]
    qrel = {
        "pages": [],
        "evidence": [],
    }
    for record in records:
        display = record["attempts"][0]["evidence_candidates"][0][
            "display_result"
        ]
        qrel["pages"].append(
            {
                "question_id": record["question_id"],
                "canonical_url": display["url"],
                "judged": True,
                "support_grade": "full",
            }
        )
        qrel["evidence"].append(
            {
                "question_id": record["question_id"],
                "chunk_id": display["chunk_id"],
                "judged": True,
                "evidence_grade": "full",
            }
        )

    covered = injected_evidence_coverage(records, qrel)
    qrel["pages"] = [row for row in qrel["pages"] if row["question_id"] != "Q001"]
    qrel["evidence"] = [
        row for row in qrel["evidence"] if row["question_id"] != "Q001"
    ]
    unjudged = injected_evidence_coverage(records, qrel)

    assert covered["page_status_counts"] == {"full": 50}
    assert covered["chunk_status_counts"] == {"positive": 50}
    assert covered["questions_with_unjudged_chunk"] == []
    assert unjudged["page_status_counts"] == {"full": 49, "unjudged": 1}
    assert unjudged["chunk_status_counts"] == {
        "positive": 49,
        "unjudged": 1,
    }
    assert unjudged["questions_with_unjudged_chunk"] == ["Q001"]


def test_aggregate_keeps_system_errors_in_end_to_end_denominator():
    expected = {"Q001": "full_answer", "Q035": "full_answer"}
    records = {
        "Q001": {"status": "success"},
        "Q035": {"status": "system_error"},
    }
    judgments = {"Q001": full_judgment("Q001")}

    all_rows = aggregate_primary(records, expected, judgments)
    sensitivity = aggregate_primary(
        records,
        expected,
        judgments,
        exclude_question_ids=frozenset({"Q035"}),
    )

    assert (all_rows["success_count"], all_rows["question_count"]) == (1, 2)
    assert all_rows["system_error_count"] == 1
    assert (sensitivity["success_count"], sensitivity["question_count"]) == (1, 1)


def test_structured_repeat_summary_is_not_content_stability():
    rows = [
        response_record("Q001", round_number=1, answerability="answerable", answer="첫 답"),
        response_record("Q001", round_number=2, answerability="answerable", answer="다른 답"),
        response_record("Q001", round_number=3, answerability="answerable", answer="또 다른 답"),
        response_record("Q002", round_number=1, answerability="answerable"),
        response_record("Q002", round_number=2, answerability="partial"),
        response_record("Q002", round_number=3, answerability="answerable"),
    ]

    summary = structured_repeat_summary(rows)

    assert summary["three_of_three_count"] == 1
    assert summary["questions"][0]["three_of_three"] is True
    assert summary["questions"][1]["three_of_three"] is False


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.value

    async def async_sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds

    def sync_sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def test_rate_limiters_apply_eighty_percent_safety_margin():
    async_clock = FakeClock()
    limiter = AsyncStartRateLimiter(60, clock=async_clock, sleep=async_clock.async_sleep)

    asyncio.run(limiter.wait())
    delay = asyncio.run(limiter.wait())

    assert limiter.effective_rpm == 48
    assert delay == pytest.approx(1.25)
    limiter.defer(3)
    assert asyncio.run(limiter.wait()) == pytest.approx(3)

    sync_clock = FakeClock()
    sync_limiter = SyncStartRateLimiter(120, clock=sync_clock, sleep=sync_clock.sync_sleep)
    sync_limiter.wait()
    assert sync_limiter.wait() == pytest.approx(0.625)


def test_retry_policy_only_retries_infrastructure_errors():
    class StatusError(Exception):
        status_code = 429

    class RequestTimeout(Exception):
        pass

    class LLMOutputValidationError(Exception):
        pass

    class Response:
        headers = {"Retry-After": "7"}

    error = StatusError("limited")
    error.response = Response()

    assert is_retryable_execution_error(error)
    assert is_retryable_execution_error(RequestTimeout())
    assert not is_retryable_execution_error(LLMOutputValidationError())
    assert not is_retryable_execution_error(ValueError())
    assert retry_after_seconds(error) == 7


def test_gemini_transport_retry_guard_rejects_hidden_sdk_retries():
    class Options:
        retry_options = None

    class ApiClient:
        _http_options = Options()

    class Client:
        _api_client = ApiClient()

    class Provider:
        client = Client()

    assert_gemini_transport_retry_disabled(Provider())
    Options.retry_options = object()
    with pytest.raises(RuntimeError, match="retry policy"):
        assert_gemini_transport_retry_disabled(Provider())


class FakeCollection:
    def __init__(self, rows: list[tuple[str, dict]]):
        self.rows = rows

    def count(self):
        return len(self.rows)

    def get(self, *, limit, offset, include):
        assert include == ["metadatas"]
        page = self.rows[offset : offset + limit]
        return {"ids": [row[0] for row in page], "metadatas": [row[1] for row in page]}


def test_lightweight_corpus_fingerprints_are_deterministic(tmp_path):
    first = chroma_fingerprint(FakeCollection([("b", {"v": 2}), ("a", {"v": 1})]), page_size=1)
    second = chroma_fingerprint(FakeCollection([("a", {"v": 1}), ("b", {"v": 2})]), page_size=2)
    (tmp_path / "bm25-a.pkl").write_bytes(b"cache")

    assert first == second
    assert bm25_fingerprint(tmp_path)["file_count"] == 1
    assert fingerprints_match(
        {"captured_at": "before", "database": {}, "chroma": first, "bm25": {}},
        {"captured_at": "after", "database": {}, "chroma": second, "bm25": {}},
    )


def manifest_fixture(tmp_path: Path) -> tuple[Path, list[str]]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    question_ids = [f"Q{index:03d}" for index in range(1, 51)]
    metadata = {
        "record_type": "run_metadata",
        "schema_version": "exp07-run-1",
        "run_id": "exp07-test",
        "created_at": "2026-07-15T00:00:00+00:00",
        "git_commit": "abc123",
        "questions_sha256": "questions",
        "qrel_sha256": "qrel",
        "qrel_manifest_sha256": "qrel-manifest",
        "rubric_sha256": "rubric",
        "prompt_sha256": "prompt",
        "provider": "gemini",
        "llm_model": "model",
        "embedding_model": "embedding",
        "runtime_packages": {
            "google-genai": "1.72.0",
            "voyageai": "0.3.7",
            "chromadb": "1.5.8",
            "asyncpg": "0.31.0",
        },
        "sampling_parameters": "provider_defaults_unspecified",
        "retriever": {"mode": "hybrid", "category": None},
        "seed": 20260715,
        "rounds": 3,
        "question_order": question_ids,
        "question_count": 50,
        "llm_rpm_limit": 60,
        "embedding_rpm_limit": 60,
        "safety_factor": 0.8,
        "cache_bypassed": True,
        "canonical_run": True,
        "retry_policy": {"evaluation_level_max_retries": 1},
        "timezone": "Asia/Seoul",
    }
    responses = []
    for round_number in (1, 2, 3):
        for ordinal, question_id in enumerate(question_ids, start=1):
            row = response_record(question_id, round_number=round_number)
            row["ordinal"] = ordinal
            responses.append(row)
    raw_path = run_dir / "raw.jsonl"
    raw_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in [metadata, *responses]) + "\n",
        encoding="utf-8",
    )
    before = {
        "schema_version": "exp07-corpus-fingerprint-1",
        "captured_at": "2026-07-15T00:00:00+00:00",
        "database": {"sha256": "db"},
        "chroma": {"sha256": "chroma"},
        "bm25": {"sha256": "bm25"},
    }
    after = deepcopy(before)
    after["captured_at"] = "2026-07-15T00:10:00+00:00"
    (run_dir / "corpus-before.json").write_text(json.dumps(before), encoding="utf-8")
    (run_dir / "corpus-after.json").write_text(json.dumps(after), encoding="utf-8")
    import hashlib

    raw_bytes = raw_path.read_bytes()
    summary = {
        "schema_version": "exp07-run-1",
        "run_id": "exp07-test",
        "status": "completed",
        "abort_reason": None,
        "started_date": "2026-07-15",
        "completed_at": "2026-07-15T00:10:00+00:00",
        "completed_response_records": 150,
        "planned_response_records": 150,
        "system_error_count": 0,
        "llm_call_count": 150,
        "llm_json_repair_count": 0,
        "embedding_call_count": 150,
        "corpus_unchanged": True,
        "finalization_errors": [],
        "raw_file": "raw.jsonl",
        "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "raw_size": len(raw_bytes),
        "metadata": metadata,
    }
    (run_dir / "run.json").write_text(json.dumps(summary), encoding="utf-8")
    return run_dir, question_ids


def test_run_manifest_gate_accepts_only_complete_canonical_run(tmp_path):
    run_dir, question_ids = manifest_fixture(tmp_path)

    manifest = build_manifest(run_dir, expected_question_ids=question_ids, verify_current_files=False)

    assert manifest["records"]["response_record_count"] == 150
    assert manifest["configuration"]["question_order"] == question_ids
    assert "responses" not in manifest

    summary_path = run_dir / "run.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["metadata"]["canonical_run"] = False
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="not marked canonical"):
        build_manifest(run_dir, expected_question_ids=question_ids, verify_current_files=False)


def test_primary_sheet_contains_no_labels_raw_outputs_or_repeats():
    record = response_record("Q001", answer="ROUND1 사용자 답변")
    reference = {
        "Q001": {
            "pages": [
                {
                    "url": "https://example.test/reference",
                    "title": "참조 페이지",
                    "menu_path": "학사",
                    "source_scope": "general_academic",
                    "page_kind": "academic",
                    "crawled_at": "2026-07-15",
                    "chunks": [
                        {
                            "chunk_id": "chunk",
                            "chunk_index": 0,
                            "content": "라벨 없는 참조 전문",
                        }
                    ],
                }
            ],
            "target_urls": [],
        }
    }

    document = render_primary_sheet(
        run_id="run",
        raw_sha256="raw",
        judge="author",
        records=[record],
        references=reference,
    )

    assert "ROUND1 사용자 답변" in document
    assert "라벨 없는 참조 전문" in document
    assert "lock-stage-one" in document
    assert "expected_behavior" not in document
    assert "answerability" not in document
    assert "retrieval_status" not in document
    assert "원시 출력 private@example.test" not in document
    assert "ROUND2" not in document


def test_reveal_sheet_shows_expected_behavior_and_repeat_diagnostics():
    judgments_payload = {
        "schema_version": "exp07-judgment-1",
        "run_id": "run",
        "private_raw_sha256": "raw",
        "exported_at": "2026-07-15T02:00:00+00:00",
        "judgments": [full_judgment("Q001")],
    }
    grouped = {
        "Q001": {
            1: response_record("Q001", round_number=1, answer="첫 답"),
            2: response_record("Q001", round_number=2, answerability="partial", answer="둘째 답"),
            3: response_record("Q001", round_number=3, answer="셋째 답"),
        }
    }

    document = render_reveal_sheet(
        judgments_payload=judgments_payload,
        judgments={"Q001": full_judgment("Q001")},
        grouped_records=grouped,
        expected_behaviors={"Q001": "full_answer"},
    )

    assert "기대 행동" in document
    assert "둘째 답" in document
    assert "post_reveal" in document
    assert "원시 출력 private@example.test" in document


def test_public_response_drops_raw_and_evidence_text_and_masks_private_data():
    record = response_record(
        "Q001",
        answer="전화 062-940-0000, 이메일 private@example.test로 문의하세요.",
    )

    published = public_response(record)
    encoded = json.dumps(published, ensure_ascii=False)

    assert "raw_output" not in encoded
    assert "원시 출력 private@example.test" not in encoded
    assert "근거 전문 062-940-0000" not in encoded
    assert "[전화번호 마스킹]" in encoded
    assert "[이메일 마스킹]" in encoded
    assert "5c8e58fe-51e3-4f38-8b2b-8bedc39d9971" in encoded

    redacted = public_response(record, redact_private_content=True)
    assert redacted["final_response"]["redacted_due_to_privacy"] is True
    assert redacted["injected_evidence_metadata"] == []


def test_publish_pipeline_emits_150_sanitized_responses_and_50_49_results(
    tmp_path,
    monkeypatch,
):
    run_dir, question_ids = manifest_fixture(tmp_path)
    manifest = build_manifest(
        run_dir,
        expected_question_ids=question_ids,
        verify_current_files=False,
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    summary = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    judgments = []
    for question_id in question_ids:
        row = full_judgment(question_id)
        row["raw_output_privacy_review"] = "safe_public_or_nonpersonal"
        judgments.append(row)
    judgments_path = tmp_path / "judgments.json"
    judgments_path.write_text(
        json.dumps(
            {
                "schema_version": "exp07-judgment-1",
                "run_id": "exp07-test",
                "judge": "author",
                "rubric_sha256": "rubric",
                "private_raw_sha256": summary["raw_sha256"],
                "primary_exported_at": "2026-07-15T02:00:00+00:00",
                "reveal_started_at": "2026-07-15T03:00:00+00:00",
                "exported_at": "2026-07-15T04:00:00+00:00",
                "judgments": judgments,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        publish_exp07_module,
        "assert_committed_file",
        lambda _path: None,
    )

    responses, public_judgments, results = publish_exp07_module.build_outputs(
        run_dir=run_dir,
        judgments_path=judgments_path,
        manifest_path=manifest_path,
    )

    assert len(responses["responses"]) == 150
    assert len(public_judgments["judgments"]) == 50
    assert results["all_50"]["question_count"] == 50
    assert results["exclude_q035"]["question_count"] == 49
    assert "raw_output" not in json.dumps(responses, ensure_ascii=False)
