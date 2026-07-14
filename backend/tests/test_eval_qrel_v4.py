import math
import sys
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from eval.adjudicate_v4_qrel import build_adjudicated  # noqa: E402
from eval.build_v4_qrel import (  # noqa: E402
    JUDGMENT_SCHEMA_VERSION,
    build_question_rows,
    load_json,
    validate_judgment_payload,
)
from eval.check_v4_invariants import (  # noqa: E402
    ActualChunk,
    find_invariant_failures,
)
from eval.make_v4_pool import (  # noqa: E402
    EXPECTED_ALL_PAIRS,
    EXPECTED_INSUFFICIENT_PAIRS,
    EXPECTED_UNIQUE_URLS,
    INSUFFICIENT_IDS,
    collect_pool_candidates,
    recover_exp06_candidate,
    validate_frozen_top5,
)
from eval.make_v4_question_review import render_question_review  # noqa: E402
from eval.make_v4_sheet import (  # noqa: E402
    EMAIL_RE,
    PHONE_RE,
    ChunkRecord,
    mask_pii,
    render_sheet,
)
from eval.score_v4 import (  # noqa: E402
    assert_top5_judged,
    normalized_dcg,
    page_gains_at_k,
    score_retrieval_rows,
)


def page(
    question_id: str,
    url: str,
    *,
    grade: str,
    temporal: str = "current",
    audience: str = "match",
    judged: str = "true",
) -> dict[str, str]:
    return {
        "question_id": question_id,
        "canonical_url": url,
        "provenance": "top5",
        "judged": judged,
        "support_grade": grade,
        "temporal_validity": temporal,
        "audience_scope": audience,
        "notes": "",
    }


def evidence(
    question_id: str,
    url: str,
    chunk_id: str,
    *,
    grade: str = "",
    evidence_type: str = "",
    content_hash: str = "hash",
    judged: str = "true",
) -> dict[str, str]:
    return {
        "question_id": question_id,
        "canonical_url": url,
        "chunk_id": chunk_id,
        "content_hash": content_hash,
        "judged": judged,
        "evidence_grade": grade,
        "evidence_type": evidence_type,
        "notes": "",
    }


def question(
    question_id: str,
    *,
    pool_support: str,
    behavior: str,
    primary_reason: str = "",
    secondary_reasons: str = "",
    override: str = "false",
    sources: str = "",
) -> dict[str, str]:
    return {
        "question_id": question_id,
        "pool_support": pool_support,
        "expected_behavior": behavior,
        "primary_reason": primary_reason,
        "secondary_reasons": secondary_reasons,
        "composition_override": override,
        "composition_sources": sources,
        "notes": "",
    }


def valid_invariant_inputs():
    pages = [
        page("Q001", "https://example.test/full", grade="full"),
        page("Q002", "https://example.test/invalid", grade="invalid"),
        page(
            "Q003",
            "https://example.test/stale",
            grade="full",
            temporal="stale",
        ),
        page(
            "Q004",
            "https://example.test/audience",
            grade="full",
            audience="mismatch",
        ),
        page("Q011", "https://example.test/duplicate-a", grade="invalid"),
        page("Q035", "https://example.test/duplicate-b", grade="invalid"),
    ]
    evidence_rows = [
        evidence(
            "Q001",
            "https://example.test/full",
            "c1",
            grade="full",
            evidence_type="text_chunk",
            content_hash="h1",
        ),
        evidence("Q002", "https://example.test/invalid", "c2"),
        evidence(
            "Q003",
            "https://example.test/stale",
            "c3",
            grade="full",
            evidence_type="text_chunk",
            content_hash="h3",
        ),
        evidence(
            "Q004",
            "https://example.test/audience",
            "c4",
            grade="full",
            evidence_type="text_chunk",
            content_hash="h4",
        ),
    ]
    questions = [
        question("Q001", pool_support="full", behavior="full_answer"),
        question(
            "Q002",
            pool_support="none",
            behavior="abstain",
            primary_reason="absent",
        ),
        question(
            "Q003",
            pool_support="full",
            behavior="abstain",
            primary_reason="stale",
        ),
        question(
            "Q004",
            pool_support="full",
            behavior="abstain",
            primary_reason="audience_mismatch",
        ),
        question(
            "Q011",
            pool_support="none",
            behavior="abstain",
            primary_reason="absent",
        ),
        question(
            "Q035",
            pool_support="none",
            behavior="abstain",
            primary_reason="absent",
        ),
    ]
    actual = {
        "c1": ActualChunk("https://example.test/full", "h1"),
        "c3": ActualChunk("https://example.test/stale", "h3"),
        "c4": ActualChunk("https://example.test/audience", "h4"),
    }
    return pages, evidence_rows, questions, actual


def run_invariants(pages, evidence_rows, questions, actual, *, top5_pages=None, top5_chunks=None):
    return find_invariant_failures(
        pages,
        evidence_rows,
        questions,
        top5_page_pairs=top5_pages or set(),
        top5_chunk_pairs=top5_chunks or set(),
        actual_chunks=actual,
    )


def test_frozen_top5_pool_counts_match_contract():
    candidates = collect_pool_candidates()
    validate_frozen_top5(candidates)

    assert len(candidates.top5_page_pairs) == EXPECTED_ALL_PAIRS
    assert (
        sum(question_id in INSUFFICIENT_IDS for question_id, _ in candidates.top5_page_pairs)
        == EXPECTED_INSUFFICIENT_PAIRS
    )
    assert len({url for _, url in candidates.top5_page_pairs}) == EXPECTED_UNIQUE_URLS
    assert len(candidates.exp06_seeds) == 51
    assert candidates.exp06_source_downgrades == 0


def test_exp06_signature_mismatch_downgrades_to_url_seed():
    evidence_item = {
        "source_number": 1,
        "url": "https://example.test/a",
        "sig_mismatch": False,
    }
    source_row = {
        "evidence_candidates": [
            {
                "source_number": 1,
                "url": "https://example.test/a",
                "chunk_id": "old-chunk",
                "content_sig": "old-signature",
            }
        ],
        "retrieved": [{"chunk_id": "old-chunk", "content_sig": "different-signature"}],
    }

    assert recover_exp06_candidate("Q001", evidence_item, source_row) is None


def test_normalized_dcg_matches_hand_calculation():
    expected = (1 + 2 / math.log2(3)) / (2 + 1 / math.log2(3))

    assert normalized_dcg([1, 2], [2, 1]) == pytest.approx(expected)


def test_page_gains_zeroes_repeated_canonical_url():
    retrieval = {
        "id": "Q001",
        "retrieved": [
            {"rank": 1, "url": "https://example.test/a", "chunk_id": "a1"},
            {"rank": 2, "url": "https://example.test/a/", "chunk_id": "a2"},
            {"rank": 3, "url": "https://example.test/b", "chunk_id": "b1"},
        ],
    }
    qrels = {
        ("Q001", "https://example.test/a"): {"support_grade": "full"},
        ("Q001", "https://example.test/b"): {"support_grade": "partial"},
    }

    assert page_gains_at_k(retrieval, qrels) == [2, 0, 1]


def test_unjudged_top5_asserts_instead_of_scoring():
    retrieval = {
        "id": "Q001",
        "retrieved": [{"rank": 1, "url": "https://example.test/a", "chunk_id": "c1"}],
    }
    pages = {
        ("Q001", "https://example.test/a"): {
            "judged": "false",
            "support_grade": "",
        }
    }
    evidence_qrels = {("Q001", "c1"): {"judged": "true"}}

    with pytest.raises(AssertionError, match="unjudged"):
        assert_top5_judged([retrieval], pages, evidence_qrels)


def test_page_navigation_question_is_excluded_from_evidence_denominator():
    retrieval = [
        {
            "id": "Q001",
            "retrieved": [
                {
                    "rank": 1,
                    "url": "https://example.test/a",
                    "chunk_id": "c1",
                }
            ],
        }
    ]
    pages = [page("Q001", "https://example.test/a", grade="full")]
    evidence_rows = [
        evidence(
            "Q001",
            "https://example.test/a",
            "c1",
            grade="full",
            evidence_type="page_navigation",
        )
    ]

    metrics = score_retrieval_rows(retrieval, pages, evidence_rows)

    assert metrics["EvidenceHit_full@5"]["N"] == 0
    assert metrics["EvidenceHit_any@5"]["N"] == 0


def test_composition_override_uses_explicit_support_and_sources():
    pages = [page("Q001", "https://example.test/a", grade="partial")]
    judgments = [
        {
            "question_id": "Q001",
            "judged": True,
            "expected_behavior": "qualified_answer",
            "composition_override": True,
            "pool_support": "full",
            "composition_sources": ["https://example.test/a", "https://example.test/b"],
        }
    ]

    rows = build_question_rows(["Q001"], pages, judgments)

    assert rows[0]["pool_support"] == "full"
    assert rows[0]["composition_override"] == "true"
    assert rows[0]["composition_sources"] == ("https://example.test/a|https://example.test/b")


def test_unjudged_question_payload_is_not_published():
    pages = [page("Q001", "https://example.test/a", grade="full")]
    judgments = [
        {
            "question_id": "Q001",
            "judged": False,
            "expected_behavior": "full_answer",
            "composition_override": False,
        }
    ]

    rows = build_question_rows(["Q001"], pages, judgments)

    assert rows[0]["pool_support"] == "full"
    assert rows[0]["expected_behavior"] == ""


def test_three_judgment_files_share_sheet_export_schema():
    payload = {
        "schema_version": JUDGMENT_SCHEMA_VERSION,
        "audit": False,
        "judge": "판정자",
        "date": "2026-07-14",
        "exported_at": "2026-07-14T00:00:00+00:00",
        "pages": [],
        "evidence": [],
        "questions": [],
    }

    validate_judgment_payload(payload)
    with pytest.raises(ValueError, match="공통 스키마 필드 누락"):
        validate_judgment_payload({key: value for key, value in payload.items() if key != "pages"})


def test_valid_invariant_fixture_has_no_failures():
    inputs = valid_invariant_inputs()

    assert run_invariants(*inputs) == []


def test_qualified_answer_may_record_reasons():
    pages, evidence_rows, questions, actual = valid_invariant_inputs()
    questions[0].update(
        expected_behavior="qualified_answer",
        primary_reason="missing_required_claim",
    )

    failures = run_invariants(pages, evidence_rows, questions, actual)

    assert not any("[I11]" in failure for failure in failures)


def test_abstain_with_deployable_full_requires_policy_exclusion():
    pages, evidence_rows, questions, actual = valid_invariant_inputs()
    questions[0].update(
        expected_behavior="abstain",
        primary_reason="missing_required_claim",
    )

    failures = run_invariants(pages, evidence_rows, questions, actual)

    assert any("[I11]" in failure and "deployable full" in failure for failure in failures)

    questions[0]["primary_reason"] = "policy_exclusion"
    failures = run_invariants(pages, evidence_rows, questions, actual)
    assert not any("deployable full" in failure for failure in failures)


@pytest.mark.parametrize(
    ("invariant", "mutate"),
    [
        (
            "I01",
            lambda p, e, q, a: ({("Q999", "https://example.test/missing")}, set()),
        ),
        (
            "I02",
            lambda p, e, q, a: (set(), {("Q999", "missing-chunk")}),
        ),
        (
            "I03",
            lambda p, e, q, a: q[0].update(pool_support="partial"),
        ),
        (
            "I04",
            lambda p, e, q, a: e.__setitem__(slice(None), [row for row in e if row["chunk_id"] != "c1"]),
        ),
        (
            "I05",
            lambda p, e, q, a: (
                e[1].update(evidence_grade="full", evidence_type="text_chunk", content_hash="h2"),
                a.update(c2=ActualChunk("https://example.test/invalid", "h2")),
            ),
        ),
        (
            "I06",
            lambda p, e, q, a: e[0].update(content_hash="wrong"),
        ),
        (
            "I07",
            lambda p, e, q, a: p[0].update(temporal_validity="stale"),
        ),
        (
            "I08",
            lambda p, e, q, a: (
                p.append(page("Q003", "https://example.test/current", grade="partial")),
                e.append(
                    evidence(
                        "Q003",
                        "https://example.test/current",
                        "c-current",
                        grade="partial",
                        evidence_type="text_chunk",
                        content_hash="hc",
                    )
                ),
                a.update(c_current=ActualChunk("https://example.test/current", "hc")),
            ),
        ),
        (
            "I09",
            lambda p, e, q, a: (
                p.append(
                    page(
                        "Q004",
                        "https://example.test/match",
                        grade="partial",
                        temporal="stale",
                    )
                ),
                e.append(
                    evidence(
                        "Q004",
                        "https://example.test/match",
                        "c-match",
                        grade="partial",
                        evidence_type="text_chunk",
                        content_hash="hm",
                    )
                ),
                a.update(c_match=ActualChunk("https://example.test/match", "hm")),
            ),
        ),
        (
            "I10",
            lambda p, e, q, a: p[1].update(judged="false"),
        ),
        (
            "I11",
            lambda p, e, q, a: q[2].update(primary_reason="stale", secondary_reasons="acquisition_failure"),
        ),
        (
            "I12",
            lambda p, e, q, a: (
                p.__setitem__(slice(None), [row for row in p if row["question_id"] != "Q035"]),
                q.__setitem__(slice(None), [row for row in q if row["question_id"] != "Q035"]),
            ),
        ),
    ],
)
def test_each_v4_invariant_has_a_failing_case(invariant, mutate):
    pages, evidence_rows, questions, actual = deepcopy(valid_invariant_inputs())
    top5_pages: set[tuple[str, str]] = set()
    top5_chunks: set[tuple[str, str]] = set()

    result = mutate(pages, evidence_rows, questions, actual)
    if invariant in {"I01", "I02"}:
        top5_pages, top5_chunks = result
    failures = run_invariants(
        pages,
        evidence_rows,
        questions,
        actual,
        top5_pages=top5_pages,
        top5_chunks=top5_chunks,
    )

    assert any(f"[{invariant}]" in failure for failure in failures), failures


def test_sheet_masks_phone_and_email_and_stays_blind():
    raw = "062-940-1234, 940-5678, author@example.com"
    masked = mask_pii(raw)
    assert PHONE_RE.search(masked) is None
    assert EMAIL_RE.search(masked) is None

    pages = [page("Q001", "https://example.test/a", grade="invalid", judged="false")]
    chunks = [
        evidence(
            "Q001",
            "https://example.test/a",
            "c1",
            content_hash="hash",
            judged="false",
        )
    ]
    questions = {"Q001": {"id": "Q001", "question": "문의처는 어디인가요?"}}
    records = {
        "c1": ChunkRecord(
            chunk_id="c1",
            canonical_url="https://example.test/a",
            title="연락처",
            menu_path="안내",
            chunk_index=0,
            content=raw,
            content_hash="hash",
        )
    }

    document = render_sheet(pages, chunks, questions, records)

    assert "062-940-1234" not in document
    assert "author@example.com" not in document
    assert all(word not in document.lower() for word in ("mode", "rank", "score"))


def test_audit_sheet_adds_required_automatic_bundle_timers_without_changing_rows():
    pages = [page("Q001", "https://example.test/a", grade="invalid", judged="false")]
    chunks = [
        evidence(
            "Q001",
            "https://example.test/a",
            "c1",
            content_hash="hash",
            judged="false",
        )
    ]
    questions = {"Q001": {"id": "Q001", "question": "문의처는 어디인가요?"}}
    records = {
        "c1": ChunkRecord(
            chunk_id="c1",
            canonical_url="https://example.test/a",
            title="연락처",
            menu_path="안내",
            chunk_index=0,
            content="본문",
            content_hash="hash",
        )
    }
    audit_ids = {
        "P|Q001|https://example.test/a",
        "E|Q001|c1",
    }

    document = render_sheet(
        pages,
        chunks,
        questions,
        records,
        audit_ids=audit_ids,
        export_filename="qrel-v4-secondary-audit-repilot.json",
    )

    assert 'data-timed="true"' in document
    assert "판정 시작(필수)" in document
    assert "setBundleControlsEnabled(card, false)" in document
    assert "finishBundleTimer(card)" in document
    assert "bundleConsistencyError" in document
    assert "완전·일부 페이지에는 최소 한 개의 양성 청크 근거가 필요합니다." in document
    assert "audit_timing" in document
    assert "시점과 대상을 무시하고 질문에 담긴 주장만 봅니다" in document
    assert 'data-export-name="qrel-v4-secondary-audit-repilot.json"' in document
    assert r"+ '\n그래도 내보낼까요?'" in document
    assert "완료 0/1묶음" in document
    assert document.count('class="judge judgment-row" data-kind="page"') == 1
    assert document.count('class="judge judgment-row" data-kind="evidence"') == 1


def test_audit_sheet_shows_context_page_without_controls_or_timer():
    pages = [
        page("Q001", "https://example.test/a", grade="invalid", judged="false"),
        page("Q001", "https://example.test/b", grade="full", judged="false"),
    ]
    chunks = [
        evidence(
            "Q001",
            "https://example.test/a",
            "c1",
            content_hash="h1",
            judged="false",
        ),
        evidence(
            "Q001",
            "https://example.test/b",
            "c2",
            content_hash="h2",
            judged="false",
        ),
    ]
    questions = {"Q001": {"id": "Q001", "question": "증명서를 발급할 수 있나요?"}}
    records = {
        "c1": ChunkRecord("c1", "https://example.test/a", "FAQ", "안내", 0, "일부 목록", "h1"),
        "c2": ChunkRecord("c2", "https://example.test/b", "공식 안내", "안내", 0, "전체 목록", "h2"),
    }
    audit_ids = {
        "P|Q001|https://example.test/a",
        "E|Q001|c1",
        "C|P|Q001|https://example.test/b",
    }

    document = render_sheet(pages, chunks, questions, records, audit_ids=audit_ids)

    assert "비교 문맥 · 이 페이지는 판정하지 않습니다." in document
    assert document.count('<section class="page-card" data-timed="true"') == 1
    assert document.count('<section class="page-card context-card"') == 1
    assert document.count('class="judge judgment-row" data-kind="page"') == 1
    assert document.count('class="judge judgment-row" data-kind="evidence"') == 1


def test_sheet_keeps_the_full_chunk_content_for_judgment():
    pages = [page("Q001", "https://example.test/a", grade="partial", judged="false")]
    chunks = [
        evidence(
            "Q001",
            "https://example.test/a",
            "c1",
            content_hash="h1",
            judged="false",
        )
    ]
    questions = {"Q001": {"id": "Q001", "question": "신청은 어떻게 하나요?"}}
    tail = "관련 신청 절차가 청크 끝에 있습니다."
    records = {
        "c1": ChunkRecord(
            "c1",
            "https://example.test/a",
            "FAQ",
            "안내",
            0,
            "앞부분 " * 300 + tail,
            "h1",
        )
    }

    document = render_sheet(pages, chunks, questions, records)

    assert tail in document
    assert "이하 생략" not in document


def test_question_review_requires_explicit_review_and_shows_final_positive_context():
    payload = {
        "pages": [
            {
                "row_id": "P|Q001|https://example.test/a",
                "question_id": "Q001",
                "canonical_url": "https://example.test/a",
                "judged": True,
                "support_grade": "full",
                "temporal_validity": "current",
                "audience_scope": "match",
                "notes": "공식 절차를 직접 제시함.",
            }
        ],
        "evidence": [
            {
                "row_id": "E|Q001|c1",
                "question_id": "Q001",
                "canonical_url": "https://example.test/a",
                "chunk_id": "c1",
                "judged": True,
                "evidence_grade": "full",
                "evidence_type": "text_chunk",
                "notes": "절차 본문.",
            }
        ],
        "questions": [
            {
                "row_id": "Q|Q001",
                "question_id": "Q001",
                "judged": True,
                "expected_behavior": "full_answer",
                "primary_reason": "",
                "secondary_reasons": [],
                "composition_override": False,
                "pool_support": "",
                "composition_sources": [],
                "notes": "완전 답변 가능.",
            }
        ],
        "date": "2026-07-14",
    }
    metadata = {
        "Q001": {
            "id": "Q001",
            "category": "학사",
            "question": "신청은 어떻게 하나요?",
            "question_type": "procedure",
        }
    }
    records = {
        "c1": ChunkRecord(
            "c1",
            "https://example.test/a",
            "신청 안내",
            "안내",
            0,
            "신청 메뉴에서 접수합니다.",
            "h1",
        )
    }

    document = render_question_review(payload, metadata, records)

    assert 'class="question-card"' in document
    assert 'data-derived-support="full"' in document
    assert "신청 메뉴에서 접수합니다." in document
    assert "초벌 제안:" in document
    assert "이 판정 확정" in document
    assert "미검토 문항이" in document
    assert "data-kind=\"page\"" not in document


def test_adjudication_applies_author_question_changes_to_page_and_evidence():
    payload = build_adjudicated(
        load_json(REPO_ROOT / "eval" / "qrel-v4-primary-initial.json"),
        load_json(REPO_ROOT / "eval" / "qrel-v4-question-review.json"),
    )
    pages = {row["row_id"]: row for row in payload["pages"]}
    evidence_rows = {row["row_id"]: row for row in payload["evidence"]}
    questions = {row["question_id"]: row for row in payload["questions"]}

    assert pages["P|Q008|https://www.honam.ac.kr/ClassLessonApply"]["support_grade"] == "partial"
    assert evidence_rows["E|Q008|33478902-8a72-4b39-a885-10686fc9436b"]["evidence_grade"] == "partial"
    assert questions["Q008"]["pool_support"] == "partial"
    assert questions["Q008"]["expected_behavior"] == "qualified_answer"

    assert pages["P|Q036|https://www.honam.ac.kr/ExamResult"]["support_grade"] == "partial"
    assert evidence_rows["E|Q036|e319bc25-7e16-4762-b274-c08cc926abd5"]["evidence_grade"] == "partial"
    assert questions["Q036"]["pool_support"] == "partial"
    assert questions["Q036"]["expected_behavior"] == "abstain"
    assert questions["Q036"]["primary_reason"] == "acquisition_failure"
