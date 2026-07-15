"""Build the private post-lock EXP-07 reveal and revision sheet."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.exp07_common import (  # noqa: E402
    behavior_error,
    load_jsonl,
    model_behavior,
    private_data_markers,
    sha256_file,
    validated_judgment_index,
    write_private_text,
)
from eval.make_exp07_primary_sheet import (  # noqa: E402
    assert_committed_file,
    primary_records,
    selected_attempt,
)
from eval.make_exp07_stage1_manifest import (  # noqa: E402
    MANIFEST_SCHEMA_VERSION as STAGE1_MANIFEST_SCHEMA_VERSION,
    assert_stage1_unchanged,
    canonicalize_primary_sheet_judgment,
    validate_stage1_snapshot,
)
from eval.make_v4_pool import RESULTS_DIR  # noqa: E402

QREL_PATH = REPO_ROOT / "eval" / "qrel-v4-adjudicated.json"
RUN_MANIFEST_PATH = REPO_ROOT / "eval" / "exp07-run-manifest.json"
STAGE1_MANIFEST_PATH = REPO_ROOT / "eval" / "exp07-stage1-manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the private EXP-07 reveal sheet."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("judgments", type=Path)
    parser.add_argument("--manifest", type=Path, default=RUN_MANIFEST_PATH)
    parser.add_argument(
        "--stage1-manifest", type=Path, default=STAGE1_MANIFEST_PATH
    )
    parser.add_argument("--stage1-snapshot", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def _text(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _attr(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON object required")
    return payload


def load_expected_behaviors(path: Path = QREL_PATH) -> dict[str, str]:
    payload = load_json(path)
    return {
        str(row["question_id"]): str(row["expected_behavior"])
        for row in payload.get("questions", [])
    }


def records_by_question(
    records: list[dict[str, Any]],
) -> dict[str, dict[int, dict[str, Any]]]:
    grouped: dict[str, dict[int, dict[str, Any]]] = {}
    for record in records:
        if record.get("record_type") != "response":
            continue
        question_id = str(record.get("question_id") or "")
        round_number = int(record.get("round") or 0)
        if question_id and round_number:
            grouped.setdefault(question_id, {})[round_number] = record
    return grouped


def structured_behavior(record: dict[str, Any] | None) -> str:
    if not record or record.get("status") != "success":
        return "system_error"
    return (
        model_behavior((record.get("final_response") or {}).get("answerability"))
        or "unknown"
    )


def raw_output_diagnostic(record: dict[str, Any] | None) -> dict[str, Any]:
    attempt = selected_attempt(record or {}) if record else None
    outputs = [
        str(call["raw_output"])
        for call in (attempt or {}).get("llm_calls") or []
        if isinstance(call.get("raw_output"), str)
    ]
    markers = sorted(
        {marker for output in outputs for marker in private_data_markers(output)}
    )
    return {"outputs": outputs, "markers": markers}


FIELD_OPTIONS = {
    "actual_behavior": [
        ("full_answer", "완전 답변"),
        ("qualified_answer", "제한 답변"),
        ("abstain", "기권"),
    ],
    "abstention_notice": [
        ("clear", "근거 부족 고지가 명확함"),
        ("missing", "고지가 없거나 불명확함"),
        ("not_applicable", "기권 아님"),
    ],
    "content_accuracy": [
        ("fully_correct", "완전 정확"),
        ("partially_correct", "일부 정확"),
        ("incorrect", "오답"),
        ("unverifiable", "검증 불가"),
        ("not_applicable", "해당 없음"),
    ],
    "claim_support": [
        ("fully_supported", "완전 지지"),
        ("partially_supported", "일부 지지"),
        ("unsupported", "지지 없음/모순"),
        ("not_applicable", "해당 없음"),
    ],
    "source_display": [
        ("complete", "완전"),
        ("incomplete", "불완전"),
        ("incorrect", "무관 출처 포함"),
        ("not_applicable", "해당 없음"),
    ],
    "temporal_validity": [
        ("current", "현행"),
        ("stale", "과거/만료"),
        ("unknown", "확정 불가"),
        ("not_applicable", "해당 없음"),
    ],
    "audience_scope": [
        ("match", "대상 일치"),
        ("mismatch", "대상 불일치"),
        ("unknown", "확정 불가"),
        ("not_applicable", "해당 없음"),
    ],
    "privacy": [("safe", "안전"), ("privacy_risk", "개인정보 위험")],
}


def _select(field: str, current: str) -> str:
    options = "".join(
        f'<option value="{_attr(value)}"{" selected" if value == current else ""}>{_text(label)}</option>'
        for value, label in FIELD_OPTIONS[field]
    )
    return f'<select data-field="{_attr(field)}">{options}</select>'


def _render_repeats(rounds: dict[int, dict[str, Any]], anomaly: bool) -> str:
    summaries = []
    details = []
    for round_number in (1, 2, 3):
        record = rounds.get(round_number)
        behavior = structured_behavior(record)
        summaries.append(
            f'<span class="repeat-chip">{round_number}회차: {_text(behavior)}</span>'
        )
        if anomaly and record and record.get("status") == "success":
            final = record.get("final_response") or {}
            details.append(
                f"""
                <details><summary>{round_number}회차 최종 답변</summary>
                  <pre>{_text(final.get("answer"))}</pre>
                </details>
                """
            )
        elif anomaly and record:
            details.append(f"<p>{round_number}회차: system_error</p>")
    return f'<div class="repeat-row">{"".join(summaries)}</div>{"".join(details)}'


def render_case(
    question_id: str,
    judgment: dict[str, Any],
    rounds: dict[int, dict[str, Any]],
    expected_behavior: str,
) -> str:
    primary = rounds[1]
    if judgment.get("response_status") == "system_error":
        return f"""
        <section class="case system-error" data-question-id="{_attr(question_id)}" data-status="system_error">
          <header><span>{_text(question_id)}</span><h2>{_text(primary.get("question"))}</h2></header>
          <p>본평가 응답은 system_error입니다. 기대 행동: <strong>{_text(expected_behavior)}</strong></p>
          {_render_repeats(rounds, True)}
        </section>
        """

    human_behavior = str(judgment["actual_behavior"])
    model_primary = structured_behavior(primary)
    repeat_behaviors = [structured_behavior(rounds.get(number)) for number in (1, 2, 3)]
    anomaly = (
        len(set(repeat_behaviors)) != 1
        or model_primary != human_behavior
        or "system_error" in repeat_behaviors
    )
    diagnostic = raw_output_diagnostic(primary)
    marker_text = (
        ", ".join(diagnostic["markers"]) if diagnostic["markers"] else "감지 없음"
    )
    raw_details = "".join(
        f"<details><summary>원시 출력 {index}</summary><pre>{_text(output)}</pre></details>"
        for index, output in enumerate(diagnostic["outputs"], start=1)
    )
    selects = "".join(
        f"<label>{_text(field)}{_select(field, str(judgment[field]))}</label>"
        for field in FIELD_OPTIONS
    )
    privacy_review = str(judgment.get("raw_output_privacy_review") or "")
    privacy_select = "".join(
        f'<option value="{value}"{" selected" if value == privacy_review else ""}>{label}</option>'
        for value, label in (
            ("", "선택"),
            ("no_sensitive_pattern", "민감 패턴 감지 없음"),
            ("safe_public_or_nonpersonal", "공개 기관 정보 또는 비개인 정보"),
            ("privacy_risk", "원시 출력 개인정보 위험"),
        )
    )
    return f"""
    <section class="case{" anomaly" if anomaly else ""}" data-question-id="{_attr(question_id)}" data-status="success"
      data-has-raw-markers="{"true" if diagnostic["markers"] else "false"}">
      <header><span>{_text(question_id)}</span><h2>{_text(primary.get("question"))}</h2></header>
      <div class="reveal-grid">
        <div><h3>잠긴 사람 판정</h3><p>실제 행동: <strong>{_text(human_behavior)}</strong></p>
          <p>모델 1회차 구조화 행동: <strong>{_text(model_primary)}</strong></p></div>
        <div><h3>공개된 기준</h3><p>기대 행동: <strong>{_text(expected_behavior)}</strong></p>
          <p>행동 오류: <strong>{_text(behavior_error(expected_behavior, human_behavior) or "none")}</strong></p></div>
      </div>
      {_render_repeats(rounds, anomaly)}
      <details class="revision"><summary>판정 조정</summary>
        <div class="axes">{selects}</div>
        <label>조정 이유<textarea data-field="revision_reason"></textarea></label>
        <button type="button" data-action="apply-revision">변경 기록 적용</button>
        <div class="history"></div>
      </details>
      <details class="raw"><summary>원시 출력 내부 로그 점검 · 민감 패턴: {_text(marker_text)}</summary>
        {raw_details or "<p>LLM 원시 출력이 없습니다.</p>"}
        <label>원시 출력 개인정보 진단<select data-field="raw_output_privacy_review">{privacy_select}</select></label>
      </details>
    </section>
    """


PAGE_CSS = """
* { box-sizing: border-box; } body { max-width: 84rem; margin: 1.5rem auto; padding: 0 1rem 7rem;
  color: #172033; font-family: Pretendard, "Noto Sans KR", "Malgun Gothic", sans-serif; line-height: 1.5; }
.guide { padding: .8rem 1rem; border: 1px solid #9aa3b1; border-radius: 8px; background: #f6f7fa; }
.case { margin: 1.2rem 0; border: 2px solid #637083; border-radius: 10px; overflow: hidden; }
.case.anomaly { border-color: #aa5a19; }.case > header { display: flex; gap: .8rem; padding: .7rem 1rem; background: #edf1f6; }
h2 { margin: 0; font-size: 1.15rem; }.case > *:not(header) { margin-left: 1rem; margin-right: 1rem; }
.reveal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; }.repeat-row { margin: .7rem 0; }
.repeat-chip { display: inline-block; margin: .2rem .4rem .2rem 0; padding: .2rem .5rem; border-radius: 5px; background: #e7edf5; font: .8rem ui-monospace, monospace; }
details { margin: .8rem 0; padding: .7rem; border: 1px solid #aab2bf; border-radius: 7px; }summary { cursor: pointer; font-weight: 750; }
pre { white-space: pre-wrap; word-break: break-word; font: .86rem ui-monospace, monospace; }.axes { display: grid; grid-template-columns: repeat(2, 1fr); gap: .6rem; margin-top: .7rem; }
label { display: block; font-weight: 650; }select, textarea { display: block; width: 100%; padding: .4rem; border: 1px solid #8993a4; border-radius: 5px; font: inherit; }
textarea { min-height: 4rem; }.raw { background: #fff8ed; }.history { margin-top: .6rem; font-size: .85rem; }
button { margin-top: .7rem; padding: .55rem .8rem; border: 0; border-radius: 6px; color: #fff; background: #244e7c; font: inherit; font-weight: 750; cursor: pointer; }
.toolbar { position: fixed; right: 1rem; bottom: 1rem; padding: .6rem; border-radius: 8px; background: #fff; box-shadow: 0 3px 16px #0004; }
@media (max-width: 800px) { .reveal-grid, .axes { grid-template-columns: 1fr; } }
"""


PAGE_JS = r"""
const initialPayload = JSON.parse(document.getElementById('initial-judgments').textContent);
const rows = new Map(initialPayload.judgments.map((row) => [row.question_id, structuredClone(row)]));
const storageKey = `exp07-reveal-${initialPayload.run_id}-${initialPayload.private_raw_sha256}`;
let revealStartedAt = new Date().toISOString();
const judgmentFields = ['actual_behavior', 'abstention_notice', 'content_accuracy', 'claim_support',
  'source_display', 'temporal_validity', 'audience_scope', 'privacy'];

function cardField(card, field) { return card.querySelector(`[data-field="${field}"]`); }
function nowIso() { return new Date().toISOString(); }
function escapeHtml(value) {
  const node = document.createElement('span'); node.textContent = String(value ?? ''); return node.innerHTML;
}
function renderHistory(card) {
  const history = rows.get(card.dataset.questionId).revision_history || [];
  card.querySelector('.history').innerHTML = history.length
    ? history.map((item) => `<div>${escapeHtml(item.revised_at)} · ${escapeHtml(item.field)}: ${escapeHtml(item.old_value)} → ${escapeHtml(item.new_value)} · ${escapeHtml(item.reason)}</div>`).join('')
    : '<div>조정 기록 없음</div>';
}
function persist() {
  localStorage.setItem(storageKey, JSON.stringify({ reveal_started_at: revealStartedAt, judgments: Array.from(rows.values()) }));
}
function proposalError(card) {
  const behavior = cardField(card, 'actual_behavior').value;
  const notice = cardField(card, 'abstention_notice').value;
  if (behavior === 'abstain' && notice === 'not_applicable') return '기권 응답의 고지 여부를 판정해 주세요.';
  if (behavior !== 'abstain' && notice !== 'not_applicable') return '기권이 아닌 응답의 고지는 기권 아님이어야 합니다.';
  const triad = ['content_accuracy', 'claim_support', 'source_display'].map((field) => cardField(card, field).value);
  if (behavior !== 'abstain' && triad.includes('not_applicable')) return '기권이 아닌 응답에는 정확성·지지·출처 해당 없음을 쓸 수 없습니다.';
  if (behavior === 'abstain' && triad.includes('not_applicable') && new Set(triad).size !== 1) return '순수 기권의 정확성·지지·출처는 함께 해당 없음이어야 합니다.';
  if (behavior === 'abstain' && triad.every((value) => value === 'not_applicable')
      && (cardField(card, 'temporal_validity').value !== 'not_applicable' || cardField(card, 'audience_scope').value !== 'not_applicable')) {
    return '순수 기권의 시간·대상 적합성도 해당 없음이어야 합니다.';
  }
  return null;
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('button'); if (!button || button.dataset.action !== 'apply-revision') return;
  const card = button.closest('.case'); const row = rows.get(card.dataset.questionId);
  const changes = judgmentFields.filter((field) => cardField(card, field).value !== row[field]);
  if (!changes.length) return alert('변경된 판정이 없습니다.');
  const validationError = proposalError(card); if (validationError) return alert(validationError);
  const reason = cardField(card, 'revision_reason').value.trim();
  if (!reason) return alert('조정 이유를 입력해 주세요.');
  const revisedAt = nowIso();
  changes.forEach((field) => {
    const next = cardField(card, field).value;
    row.revision_history.push({ field, old_value: row[field], new_value: next, reason, revised_at: revisedAt, phase: 'post_reveal' });
    row[field] = next;
  });
  cardField(card, 'revision_reason').value = ''; renderHistory(card); persist();
});

document.addEventListener('change', (event) => {
  if (!event.target.matches('[data-field="raw_output_privacy_review"]')) return;
  const card = event.target.closest('.case'); rows.get(card.dataset.questionId).raw_output_privacy_review = event.target.value; persist();
});

document.querySelector('[data-action="export"]').addEventListener('click', () => {
  const unsaved = Array.from(document.querySelectorAll('.case[data-status="success"]')).filter((card) => {
    const row = rows.get(card.dataset.questionId);
    return judgmentFields.some((field) => cardField(card, field).value !== row[field]);
  });
  if (unsaved.length) return alert(`적용하지 않은 판정 변경이 ${unsaved.length}건 있습니다.`);
  const missing = Array.from(document.querySelectorAll('.case[data-status="success"]')).filter((card) => {
    const row = rows.get(card.dataset.questionId);
    return card.dataset.hasRawMarkers === 'true' && !row.raw_output_privacy_review;
  });
  if (missing.length) return alert(`원시 출력 민감 패턴 ${missing.length}건을 먼저 점검해 주세요.`);
  document.querySelectorAll('.case[data-status="success"]').forEach((card) => {
    const row = rows.get(card.dataset.questionId);
    if (!row.raw_output_privacy_review) row.raw_output_privacy_review = 'no_sensitive_pattern';
  });
  const output = { ...initialPayload, reveal_started_at: revealStartedAt, exported_at: nowIso(), judgments: Array.from(rows.values()) };
  const blob = new Blob([JSON.stringify(output, null, 2) + '\n'], { type: 'application/json' });
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob);
  link.download = `${initialPayload.run_id}-adjudicated-judgments.json`; link.click(); URL.revokeObjectURL(link.href);
  persist();
});

document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem(storageKey);
  if (saved) {
    try {
      const value = JSON.parse(saved); revealStartedAt = value.reveal_started_at || revealStartedAt;
      value.judgments.forEach((row) => rows.set(row.question_id, row));
      document.querySelectorAll('.case[data-status="success"]').forEach((card) => {
        const row = rows.get(card.dataset.questionId);
        judgmentFields.forEach((field) => { cardField(card, field).value = row[field]; });
        cardField(card, 'raw_output_privacy_review').value = row.raw_output_privacy_review || '';
      });
    } catch (_error) { localStorage.removeItem(storageKey); }
  }
  document.querySelectorAll('.case[data-status="success"]').forEach(renderHistory);
});
"""


def render_sheet(
    *,
    judgments_payload: dict[str, Any],
    judgments: dict[str, dict[str, Any]],
    grouped_records: dict[str, dict[int, dict[str, Any]]],
    expected_behaviors: dict[str, str],
) -> str:
    cases = "".join(
        render_case(
            question_id,
            judgment,
            grouped_records[question_id],
            expected_behaviors[question_id],
        )
        for question_id, judgment in judgments.items()
    )
    initial = dict(judgments_payload)
    initial["primary_exported_at"] = judgments_payload.get("exported_at")
    initial["reveal_started_at"] = None
    initial["judgments"] = list(judgments.values())
    encoded = json.dumps(initial, ensure_ascii=False).replace("<", "\\u003c")
    generated = datetime.now(UTC).isoformat()
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>EXP-07 공개·조정</title>
<style>{PAGE_CSS}</style></head><body><h1>EXP-07 공개·조정</h1>
<p class="guide">본판정이 전량 잠긴 뒤 생성된 파일입니다. 기대 행동과 모델 구조화 판정, 반복 결과를 공개합니다. 공개 후 변경은 이유와 시각이 있는 조정 기록으로만 저장됩니다. 생성 시각: {_text(generated)}</p>
{cases}<div class="toolbar"><button type="button" data-action="export">조정 판정 JSON 내보내기</button></div>
<script id="initial-judgments" type="application/json">{encoded}</script><script>{PAGE_JS}</script></body></html>"""


def _validate_manifest(manifest: dict[str, Any], summary: dict[str, Any]) -> None:
    if manifest.get("run_id") != summary.get("run_id"):
        raise ValueError("run manifest belongs to another run")
    if (manifest.get("private_raw") or {}).get("sha256") != summary.get("raw_sha256"):
        raise ValueError("run manifest raw SHA-256 differs from run.json")


def _load_stage1_lineage(
    *,
    stage1_manifest_path: Path,
    stage1_snapshot_path: Path | None,
    run_dir: Path,
    run_manifest_path: Path,
    run_manifest: dict[str, Any],
    summary: dict[str, Any],
    expected_statuses: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    assert_committed_file(stage1_manifest_path)
    manifest = load_json(stage1_manifest_path)
    if manifest.get("schema_version") != STAGE1_MANIFEST_SCHEMA_VERSION:
        raise ValueError("stage-one manifest schema_version is invalid")
    if manifest.get("run_id") != summary.get("run_id"):
        raise ValueError("stage-one manifest belongs to another run")
    if manifest.get("run_manifest_sha256") != sha256_file(run_manifest_path):
        raise ValueError("stage-one manifest refers to another run manifest")
    provenance = manifest.get("provenance") or {}
    if provenance.get("private_raw_sha256") != summary.get("raw_sha256"):
        raise ValueError("stage-one manifest raw SHA-256 differs from the run")
    if provenance.get("rubric_sha256") != (
        run_manifest.get("provenance") or {}
    ).get("rubric_sha256"):
        raise ValueError("stage-one manifest rubric differs from the run manifest")

    private_stage1 = manifest.get("private_stage1") or {}
    snapshot_path = (
        stage1_snapshot_path
        or (run_dir / str(private_stage1.get("file_name") or ""))
    ).resolve()
    if not snapshot_path.is_relative_to(run_dir):
        raise ValueError("stage-one snapshot must stay inside the private run directory")
    if private_stage1.get("sha256") != sha256_file(snapshot_path):
        raise ValueError("stage-one snapshot SHA-256 differs from its manifest")
    if private_stage1.get("size") != snapshot_path.stat().st_size:
        raise ValueError("stage-one snapshot size differs from its manifest")
    if snapshot_path.stat().st_mode & 0o077:
        raise ValueError("stage-one snapshot must use owner-only permissions")

    primary_html = manifest.get("primary_html") or {}
    primary_html_path = run_dir / str(primary_html.get("file_name") or "")
    if primary_html.get("sha256") != sha256_file(primary_html_path):
        raise ValueError("primary judgment HTML differs from the stage-one manifest")
    baseline = load_json(snapshot_path)
    validate_stage1_snapshot(
        baseline,
        expected_run_id=str(summary["run_id"]),
        expected_raw_sha256=str(summary["raw_sha256"]),
        expected_rubric_sha256=str(provenance["rubric_sha256"]),
        expected_statuses=expected_statuses,
    )
    return manifest, baseline, snapshot_path


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output = (args.output or (run_dir / "exp07-reveal-adjudication.html")).resolve()
    if not (
        output == RESULTS_DIR.resolve() or output.is_relative_to(RESULTS_DIR.resolve())
    ):
        raise ValueError("unmasked reveal sheets must stay under eval/results")
    summary = load_json(run_dir / "run.json")
    raw_path = run_dir / "raw.jsonl"
    if summary.get("raw_sha256") != sha256_file(raw_path):
        raise ValueError("private raw SHA-256 differs from run.json")
    assert_committed_file(args.manifest)
    manifest = load_json(args.manifest)
    _validate_manifest(manifest, summary)
    records = load_jsonl(raw_path)
    primary = primary_records(records)
    question_ids = {str(record["question_id"]) for record in primary}
    expected_statuses = {
        str(record["question_id"]): str(record["status"]) for record in primary
    }
    stage1_manifest, stage1_baseline, stage1_snapshot_path = _load_stage1_lineage(
        stage1_manifest_path=args.stage1_manifest,
        stage1_snapshot_path=args.stage1_snapshot,
        run_dir=run_dir,
        run_manifest_path=args.manifest,
        run_manifest=manifest,
        summary=summary,
        expected_statuses=expected_statuses,
    )
    judgments_payload = load_json(args.judgments)
    judgments_payload["primary_judgments_sha256"] = sha256_file(args.judgments)
    judgments_payload["stage1_manifest_sha256"] = sha256_file(
        args.stage1_manifest
    )
    judgments_payload["stage1_snapshot_sha256"] = sha256_file(
        stage1_snapshot_path
    )
    assert_stage1_unchanged(stage1_baseline, judgments_payload)
    judgments_payload["judgments"] = [
        canonicalize_primary_sheet_judgment(row)
        for row in judgments_payload.get("judgments") or []
    ]
    judgments = validated_judgment_index(
        judgments_payload,
        expected_run_id=str(summary["run_id"]),
        expected_raw_sha256=str(summary["raw_sha256"]),
        expected_question_ids=question_ids,
    )
    if (stage1_manifest.get("private_stage1") or {}).get(
        "judgment_count"
    ) != len(judgments):
        raise ValueError("stage-one manifest judgment count differs from the final JSON")
    primary_by_id = {str(record["question_id"]): record for record in primary}
    for question_id, judgment in judgments.items():
        if judgment.get("response_status") != primary_by_id[question_id].get("status"):
            raise ValueError(
                f"{question_id}: judgment response status differs from the run"
            )
    grouped = records_by_question(records)
    if (
        any(set(rounds) != {1, 2, 3} for rounds in grouped.values())
        or set(grouped) != question_ids
    ):
        raise ValueError("reveal sheet requires complete 3-round records")
    expected = load_expected_behaviors()
    if not question_ids <= set(expected):
        raise ValueError("qrel expected behavior is missing")
    document = render_sheet(
        judgments_payload=judgments_payload,
        judgments=judgments,
        grouped_records=grouped,
        expected_behaviors=expected,
    )
    write_private_text(output, document)
    print(f"wrote: {output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
