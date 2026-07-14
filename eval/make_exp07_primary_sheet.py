"""Build the private two-stage blind judgment sheet for EXP-07 round 1."""

from __future__ import annotations

import argparse
import asyncio
import csv
import html
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.exp07_common import (  # noqa: E402
    JUDGMENT_SCHEMA_VERSION,
    load_jsonl,
    sha256_file,
    write_private_text,
)
from eval.make_v4_pool import DB_DSN, RESULTS_DIR  # noqa: E402
from eval.run_questions import content_signature, normalize_url  # noqa: E402

GOLD_EVIDENCE_PATH = REPO_ROOT / "eval" / "gold_evidence_v4.csv"
TARGET_SOURCES_PATH = REPO_ROOT / "eval" / "target_sources_v4.csv"
RUBRIC_PATH = REPO_ROOT / "eval" / "exp07-answer-rubric.md"
RUN_MANIFEST_PATH = REPO_ROOT / "eval" / "exp07-run-manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the private blind EXP-07 primary sheet."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--judge", default="author")
    parser.add_argument("--dsn", default=DB_DSN)
    parser.add_argument("--manifest", type=Path, default=RUN_MANIFEST_PATH)
    return parser.parse_args()


def _attr(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _text(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def selected_attempt(record: dict[str, Any]) -> dict[str, Any] | None:
    selected = record.get("selected_attempt")
    attempts = record.get("attempts") or []
    if record.get("status") != "success" or not isinstance(selected, int):
        return None
    index = selected - 1
    if index < 0 or index >= len(attempts):
        raise ValueError(f"{record.get('question_id')}: selected attempt is invalid")
    attempt = attempts[index]
    if attempt.get("status") != "success":
        raise ValueError(
            f"{record.get('question_id')}: selected attempt is not successful"
        )
    return attempt


def primary_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in records
        if row.get("record_type") == "response" and row.get("round") == 1
    ]
    rows.sort(key=lambda row: int(row.get("ordinal") or 0))
    if len(rows) != 50 or len({str(row.get("question_id")) for row in rows}) != 50:
        raise ValueError(
            "blind primary sheet requires exactly 50 unique round-1 records"
        )
    return rows


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as input_file:
        return list(csv.DictReader(input_file))


async def load_reference_bundles(
    question_ids: set[str],
    *,
    dsn: str,
) -> dict[str, dict[str, Any]]:
    evidence_rows = [
        row
        for row in _load_csv(GOLD_EVIDENCE_PATH)
        if row["question_id"] in question_ids
        and row["evidence_grade"] in {"full", "partial"}
    ]
    chunk_ids = sorted({row["chunk_id"] for row in evidence_rows})
    records: dict[str, Any] = {}
    if chunk_ids:
        connection = await asyncpg.connect(dsn)
        try:
            rows = await connection.fetch(
                """
                SELECT
                    c.id AS chunk_id,
                    c.content,
                    c.chunk_index,
                    c.chunk_type,
                    d.url,
                    d.title,
                    d.menu_path,
                    d.source_scope,
                    d.page_kind,
                    d.crawled_at
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.id = ANY($1::uuid[])
                """,
                [uuid.UUID(value) for value in chunk_ids],
            )
        finally:
            await connection.close()
        records = {str(row["chunk_id"]): row for row in rows}
    missing = sorted(set(chunk_ids) - set(records))
    if missing:
        raise ValueError(
            f"reference chunks are missing from the frozen database: {', '.join(missing)}"
        )

    grouped: dict[str, dict[str, Any]] = {
        question_id: {"pages": [], "target_urls": []} for question_id in question_ids
    }
    pages: dict[tuple[str, str], dict[str, Any]] = {}
    for evidence in evidence_rows:
        record = records[evidence["chunk_id"]]
        actual_url = normalize_url(str(record["url"]))
        expected_url = normalize_url(evidence["canonical_url"])
        if actual_url != expected_url:
            raise ValueError(f"{evidence['chunk_id']}: reference URL differs from qrel")
        actual_hash = content_signature(str(record["content"]))
        if actual_hash != evidence["content_hash"]:
            raise ValueError(
                f"{evidence['chunk_id']}: reference content hash differs from qrel"
            )
        key = (evidence["question_id"], expected_url)
        page = pages.setdefault(
            key,
            {
                "url": actual_url,
                "title": record["title"],
                "menu_path": record["menu_path"],
                "source_scope": record["source_scope"],
                "page_kind": record["page_kind"],
                "crawled_at": record["crawled_at"].isoformat()
                if record["crawled_at"]
                else None,
                "chunks": [],
            },
        )
        page["chunks"].append(
            {
                "chunk_id": evidence["chunk_id"],
                "chunk_index": record["chunk_index"],
                "chunk_type": record["chunk_type"],
                "content_hash": actual_hash,
                "content": record["content"],
            }
        )
    for (question_id, _url), page in sorted(pages.items()):
        page["chunks"].sort(key=lambda row: (int(row["chunk_index"]), row["chunk_id"]))
        grouped[question_id]["pages"].append(page)

    for row in _load_csv(TARGET_SOURCES_PATH):
        question_id = row["question_id"]
        if question_id in grouped:
            grouped[question_id]["target_urls"].append(row["target_url"])
    for bundle in grouped.values():
        bundle["target_urls"] = sorted(set(bundle["target_urls"]))
    return grouped


def _render_sources(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return '<p class="empty">표시된 출처가 없습니다.</p>'
    cards = []
    for source in sources:
        cards.append(
            f"""
            <article class="source-card">
              <strong>{_text(source.get("title") or source.get("url"))}</strong>
              <span class="badge">{_text(source.get("freshness") or "unknown")}</span>
              <div>{_text(source.get("crawled_at"))}</div>
              <div class="url">{_text(source.get("url"))}</div>
            </article>
            """
        )
    return "".join(cards)


def _render_injected(attempt: dict[str, Any] | None) -> str:
    candidates = (attempt or {}).get("evidence_candidates") or []
    if not candidates:
        return '<p class="empty">이 실행에서 주입된 evidence가 없습니다.</p>'
    cards = []
    for candidate in candidates:
        display = candidate.get("display_result") or {}
        chunks = []
        for context in candidate.get("context_results") or []:
            chunks.append(
                f"""
                <div class="chunk">
                  <div class="chunk-meta">청크 {int(context.get("chunk_index") or 0)} · {_text(context.get("chunk_id"))}</div>
                  <pre>{_text(context.get("content"))}</pre>
                </div>
                """
            )
        cards.append(
            f"""
            <article class="evidence-card">
              <h4>[{_text(candidate.get("source_number"))}] {_text(display.get("title") or display.get("url"))}</h4>
              <div class="meta">메뉴: {_text(display.get("menu_path"))} · 수집: {_text(display.get("crawled_at"))}</div>
              <div class="url">{_text(display.get("url"))}</div>
              {"".join(chunks)}
            </article>
            """
        )
    return "".join(cards)


def _render_reference(bundle: dict[str, Any]) -> str:
    cards = []
    for page in bundle.get("pages") or []:
        chunks = "".join(
            f"""
            <div class="chunk">
              <div class="chunk-meta">청크 {int(chunk.get("chunk_index") or 0)} · {_text(chunk.get("chunk_id"))}</div>
              <pre>{_text(chunk.get("content"))}</pre>
            </div>
            """
            for chunk in page.get("chunks") or []
        )
        cards.append(
            f"""
            <article class="reference-card">
              <h4>{_text(page.get("title") or page.get("url"))}</h4>
              <div class="meta">메뉴: {_text(page.get("menu_path"))} · 수집: {_text(page.get("crawled_at"))}</div>
              <div class="meta">범위: {_text(page.get("source_scope"))} · 유형: {_text(page.get("page_kind"))}</div>
              <div class="url">{_text(page.get("url"))}</div>
              {chunks}
            </article>
            """
        )
    target_cards = "".join(
        f'<li class="url">{_text(url)}</li>' for url in bundle.get("target_urls") or []
    )
    if target_cards:
        cards.append(
            '<article class="reference-card"><h4>동결 코퍼스 전문이 없는 공식 대상 URL</h4>'
            f"<ul>{target_cards}</ul></article>"
        )
    if not cards:
        return '<p class="empty">동결 qrel에서 제공할 수 있는 양성 참조 전문이나 대상 URL이 없습니다.</p>'
    return "".join(cards)


def _select(field: str, options: list[tuple[str, str]], *, blank: str = "선택") -> str:
    rendered = [f'<option value="">{_text(blank)}</option>']
    rendered.extend(
        f'<option value="{_attr(value)}">{_text(label)}</option>'
        for value, label in options
    )
    return f'<select data-field="{_attr(field)}">{"".join(rendered)}</select>'


def render_case(record: dict[str, Any], reference: dict[str, Any]) -> str:
    question_id = str(record["question_id"])
    if record.get("status") == "system_error":
        return f"""
        <section class="case system-error" data-question-id="{_attr(question_id)}" data-status="system_error">
          <header><span class="qid">{_text(question_id)}</span><h2>{_text(record.get("question"))}</h2></header>
          <p>정상 최종 응답이 없어 사람 판정 대상에서 제외됩니다. 종합 성공에서는 실패로 계산됩니다.</p>
        </section>
        """

    final = record.get("final_response") or {}
    attempt = selected_attempt(record)
    behavior_select = _select(
        "actual_behavior",
        [
            ("full_answer", "완전 답변"),
            ("qualified_answer", "제한 답변"),
            ("abstain", "기권"),
        ],
    )
    notice_select = _select(
        "abstention_notice",
        [("clear", "근거 부족 고지가 명확함"), ("missing", "고지가 없거나 불명확함")],
        blank="기권일 때 선택",
    )
    return f"""
    <section class="case" data-question-id="{_attr(question_id)}" data-status="success">
      <header><span class="qid">{_text(question_id)}</span><h2>{_text(record.get("question"))}</h2></header>
      <div class="stage stage-one">
        <h3>1단계 · 실제 행동</h3>
        <p class="guide">답변 문장과 사용자 표시 출처만 보고 판정합니다. 구조화 상태 배지는 의도적으로 제외했습니다.</p>
        <article class="answer"><pre>{_text(final.get("answer"))}</pre></article>
        <div class="source-grid">{_render_sources(final.get("sources") or [])}</div>
        {f'<div class="warning">충돌 안내: {_text((final.get("conflict_warning") or {}).get("description"))}</div>' if (final.get("conflict_warning") or {}).get("exists") else ""}
        <label>실제 행동 {behavior_select}</label>
        <label>기권 고지 {notice_select}</label>
        <button type="button" data-action="lock-stage-one">1단계 잠금 후 근거 보기</button>
        <span class="locked-at" data-output="stage-one"></span>
      </div>
      <div class="stage stage-two hidden">
        <h3>2단계 · 정확성·근거·배포 적합성</h3>
        <p class="guide">왼쪽은 이 실행에서 실제 주입된 evidence, 오른쪽은 라벨을 제거한 동결 참조 묶음입니다.</p>
        <div class="evidence-grid">
          <div><h4>실제 주입 evidence</h4>{_render_injected(attempt)}</div>
          <div><h4>v4 참조 묶음</h4>{_render_reference(reference)}</div>
        </div>
        <div class="axes">
          <label>내용 정확성 {_select("content_accuracy", [("fully_correct", "완전 정확"), ("partially_correct", "일부 정확"), ("incorrect", "오답"), ("unverifiable", "동결 자료로 검증 불가"), ("not_applicable", "순수 기권으로 해당 없음")])}</label>
          <label>내용 지지 {_select("claim_support", [("fully_supported", "완전 지지"), ("partially_supported", "일부 지지"), ("unsupported", "지지 없음/모순"), ("not_applicable", "순수 기권으로 해당 없음")])}</label>
          <label>출처 표시 {_select("source_display", [("complete", "완전"), ("incomplete", "불완전"), ("incorrect", "무관 출처 포함"), ("not_applicable", "순수 기권으로 해당 없음")])}</label>
          <label>시간 적합성 {_select("temporal_validity", [("current", "현행"), ("stale", "과거/만료"), ("unknown", "확정 불가"), ("not_applicable", "해당 없음")])}</label>
          <label>대상 적합성 {_select("audience_scope", [("match", "대상 일치"), ("mismatch", "대상 불일치"), ("unknown", "확정 불가"), ("not_applicable", "해당 없음")])}</label>
          <label>개인정보 {_select("privacy", [("safe", "안전"), ("privacy_risk", "개인정보 위험")])}</label>
        </div>
        <div class="hold-row">
          <label><input type="checkbox" data-field="hold"> 판정보류</label>
          <span>애매한 축:</span>
          {"".join(f'<label><input type="checkbox" data-hold-axis="{field}"> {_text(label)}</label>' for field, label in [("actual_behavior", "행동"), ("content_accuracy", "정확성"), ("claim_support", "지지"), ("source_display", "출처"), ("temporal_validity", "시간"), ("audience_scope", "대상"), ("privacy", "개인정보")])}
        </div>
        <label class="memo">판정 메모<textarea data-field="memo"></textarea></label>
        <button type="button" data-action="save-stage-two">2단계 저장</button>
        <span class="locked-at" data-output="stage-two"></span>
      </div>
    </section>
    """


PAGE_CSS = """
* { box-sizing: border-box; }
body { max-width: 92rem; margin: 1.5rem auto; padding: 0 1.2rem 7rem; color: #172033;
  font-family: Pretendard, "Noto Sans KR", "Malgun Gothic", sans-serif; line-height: 1.55; }
h1 { margin-bottom: .3rem; } h2 { margin: .2rem 0; font-size: 1.2rem; } h3 { margin-top: 0; }
.top-guide, .guide { padding: .8rem 1rem; border: 1px solid #96a0b1; border-radius: 8px; background: #f7f8fb; }
.progress { position: sticky; top: 0; z-index: 5; padding: .7rem 1rem; background: #172033; color: #fff; }
.case { margin: 1.5rem 0; border: 2px solid #64748b; border-radius: 12px; overflow: hidden; }
.case > header { display: flex; gap: .8rem; align-items: baseline; padding: .8rem 1rem; background: #eef2f7; }
.qid { font: 700 .8rem ui-monospace, monospace; color: #315780; }.stage { padding: 1rem; }
.stage-two { border-top: 4px solid #315780; background: #fbfdff; }.hidden { display: none; }
.answer, .source-card, .evidence-card, .reference-card { margin: .7rem 0; padding: .8rem; border: 1px solid #b5bdca; border-radius: 8px; background: #fff; }
pre { margin: 0; white-space: pre-wrap; word-break: break-word; font: inherit; }
.source-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: .6rem; }
.source-card { margin: 0; }.badge { float: right; padding: .05rem .4rem; border-radius: 5px; background: #fff1c7; font-size: .75rem; }
.url, .chunk-meta, .meta { color: #5b6574; font: .76rem ui-monospace, monospace; word-break: break-all; }
.evidence-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; align-items: start; }
.chunk { margin-top: .6rem; border-top: 1px dashed #aab2c0; padding-top: .6rem; }.chunk pre { font-size: .88rem; }
.axes { display: grid; grid-template-columns: repeat(2, minmax(18rem, 1fr)); gap: .7rem; margin-top: 1rem; }
label { display: block; font-weight: 650; } select, textarea { width: 100%; margin-top: .25rem; padding: .45rem; border: 1px solid #8993a4; border-radius: 5px; font: inherit; }
.hold-row { margin-top: 1rem; padding: .7rem; border: 1px solid #c29b52; background: #fff9e8; }.hold-row label { display: inline-block; margin-right: .8rem; }
.memo { margin-top: .7rem; }.memo textarea { min-height: 4rem; }button { margin-top: .8rem; padding: .55rem .8rem; border: 0; border-radius: 6px; background: #244e7c; color: #fff; font: inherit; font-weight: 750; cursor: pointer; }
button:disabled { background: #8993a4; cursor: default; }.locked-at { margin-left: .7rem; color: #47627e; font-size: .8rem; }
.empty { padding: .7rem; background: #f3f4f6; color: #697386; }.warning { padding: .6rem; background: #fff1e7; }
.toolbar { position: fixed; right: 1rem; bottom: 1rem; z-index: 10; display: flex; gap: .5rem; padding: .6rem; border-radius: 9px; background: #fff; box-shadow: 0 3px 16px #0004; }
@media (max-width: 900px) { .evidence-grid, .axes { grid-template-columns: 1fr; } }
"""


PAGE_JS = r"""
const storageKey = `exp07-primary-${document.body.dataset.runId}-${document.body.dataset.rawSha}`;
const fields = ['actual_behavior', 'abstention_notice', 'content_accuracy', 'claim_support',
  'source_display', 'temporal_validity', 'audience_scope', 'privacy', 'memo'];

function control(card, field) { return card.querySelector(`[data-field="${field}"]`); }
function setControls(card, selector, disabled) {
  card.querySelectorAll(selector).forEach((item) => { item.disabled = disabled; });
}
function nowIso() { return new Date().toISOString(); }

function readCard(card) {
  const status = card.dataset.status;
  if (status === 'system_error') {
    return { question_id: card.dataset.questionId, response_status: status, hold: false,
      hold_axes: [], memo: '', stage1_locked_at: null, stage2_locked_at: null, revision_history: [] };
  }
  const row = { question_id: card.dataset.questionId, response_status: status };
  fields.forEach((field) => { row[field] = control(card, field)?.value || ''; });
  row.hold = Boolean(control(card, 'hold')?.checked);
  row.hold_axes = Array.from(card.querySelectorAll('[data-hold-axis]:checked')).map((item) => item.dataset.holdAxis);
  row.stage1_locked_at = card.dataset.stage1LockedAt || null;
  row.stage2_locked_at = card.dataset.stage2LockedAt || null;
  row.revision_history = [];
  return row;
}

function payload() {
  return {
    schema_version: document.body.dataset.schemaVersion,
    run_id: document.body.dataset.runId,
    judge: document.body.dataset.judge,
    rubric_sha256: document.body.dataset.rubricSha,
    private_raw_sha256: document.body.dataset.rawSha,
    exported_at: nowIso(),
    reveal_started_at: null,
    judgments: Array.from(document.querySelectorAll('.case')).map(readCard),
  };
}

function persist() { localStorage.setItem(storageKey, JSON.stringify(payload())); updateProgress(); }

function applyRow(card, row) {
  fields.forEach((field) => { if (control(card, field)) control(card, field).value = row[field] || ''; });
  if (control(card, 'hold')) control(card, 'hold').checked = Boolean(row.hold);
  const axes = new Set(row.hold_axes || []);
  card.querySelectorAll('[data-hold-axis]').forEach((item) => { item.checked = axes.has(item.dataset.holdAxis); });
  card.dataset.stage1LockedAt = row.stage1_locked_at || '';
  card.dataset.stage2LockedAt = row.stage2_locked_at || '';
  syncCard(card);
}

function syncCard(card) {
  if (card.dataset.status === 'system_error') return;
  const stageOneLocked = Boolean(card.dataset.stage1LockedAt);
  const stageTwoLocked = Boolean(card.dataset.stage2LockedAt);
  setControls(card, '.stage-one select, [data-action="lock-stage-one"]', stageOneLocked);
  card.querySelector('.stage-two').classList.toggle('hidden', !stageOneLocked);
  setControls(card, '.stage-two select, .stage-two textarea, .stage-two input, [data-action="save-stage-two"]', stageTwoLocked);
  card.querySelector('[data-output="stage-one"]').textContent = stageOneLocked ? `잠금 ${card.dataset.stage1LockedAt}` : '';
  card.querySelector('[data-output="stage-two"]').textContent = stageTwoLocked ? `확정 ${card.dataset.stage2LockedAt}` : '';
}

function validateStageOne(card) {
  const behavior = control(card, 'actual_behavior').value;
  const notice = control(card, 'abstention_notice');
  if (!behavior) return '실제 행동을 선택해 주세요.';
  if (behavior === 'abstain' && !notice.value) return '기권 고지를 판정해 주세요.';
  if (behavior !== 'abstain') notice.value = 'not_applicable';
  return null;
}

function validateStageTwo(card) {
  for (const field of ['content_accuracy', 'claim_support', 'source_display', 'temporal_validity', 'audience_scope', 'privacy']) {
    if (!control(card, field).value) return `${field} 항목을 선택해 주세요.`;
  }
  const behavior = control(card, 'actual_behavior').value;
  const triad = ['content_accuracy', 'claim_support', 'source_display'].map((field) => control(card, field).value);
  if (behavior !== 'abstain' && triad.includes('not_applicable')) return '기권이 아닌 응답에는 정확성·지지·출처 해당 없음을 쓸 수 없습니다.';
  if (behavior === 'abstain' && triad.includes('not_applicable') && new Set(triad).size !== 1) return '순수 기권의 정확성·지지·출처는 함께 해당 없음이어야 합니다.';
  if (behavior === 'abstain' && triad.every((value) => value === 'not_applicable')
      && (control(card, 'temporal_validity').value !== 'not_applicable' || control(card, 'audience_scope').value !== 'not_applicable')) {
    return '순수 기권의 시간·대상 적합성도 해당 없음이어야 합니다.';
  }
  if (control(card, 'hold').checked) {
    if (!card.querySelector('[data-hold-axis]:checked')) return '보류할 축을 하나 이상 선택해 주세요.';
    if (!control(card, 'memo').value.trim()) return '판정보류 이유를 메모해 주세요.';
  }
  return null;
}

function updateProgress() {
  const cards = Array.from(document.querySelectorAll('.case'));
  const systemErrors = cards.filter((card) => card.dataset.status === 'system_error').length;
  const stageOne = cards.filter((card) => card.dataset.stage1LockedAt).length;
  const stageTwo = cards.filter((card) => card.dataset.stage2LockedAt).length;
  const holds = cards.filter((card) => control(card, 'hold')?.checked).length;
  document.querySelector('.progress').textContent = `행동 잠금 ${stageOne}/${cards.length - systemErrors} · 최종 확정 ${stageTwo}/${cards.length - systemErrors} · 보류 ${holds} · 시스템 오류 ${systemErrors}`;
}

function download(value, suffix) {
  const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], { type: 'application/json' });
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob);
  link.download = `${document.body.dataset.runId}-primary-judgments-${suffix}.json`; link.click();
  URL.revokeObjectURL(link.href);
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('button'); if (!button) return;
  const card = button.closest('.case');
  if (button.dataset.action === 'lock-stage-one') {
    const error = validateStageOne(card); if (error) return alert(error);
    if (!confirm('근거를 공개한 뒤에는 1단계 행동 판정을 수정할 수 없습니다. 잠글까요?')) return;
    card.dataset.stage1LockedAt = nowIso(); syncCard(card); persist();
  }
  if (button.dataset.action === 'save-stage-two') {
    const error = validateStageTwo(card); if (error) return alert(error);
    if (!control(card, 'hold').checked) card.dataset.stage2LockedAt = nowIso();
    syncCard(card); persist();
  }
  if (button.dataset.action === 'export-draft') download(payload(), 'draft');
  if (button.dataset.action === 'export-final') {
    const rows = payload().judgments;
    const incomplete = rows.filter((row) => row.response_status === 'success' && (!row.stage1_locked_at || !row.stage2_locked_at));
    const holds = rows.filter((row) => row.hold);
    if (incomplete.length || holds.length) return alert(`미완료 ${incomplete.length}건, 보류 ${holds.length}건을 먼저 해소해 주세요.`);
    download(payload(), 'locked');
  }
});

document.addEventListener('change', (event) => {
  if (event.target.matches('[data-field="hold"]') && !event.target.checked) {
    event.target.closest('.case').querySelectorAll('[data-hold-axis]').forEach((item) => { item.checked = false; });
  }
  if (event.target.matches('select, textarea, input')) persist();
});

document.querySelector('[data-action="import"]').addEventListener('change', async (event) => {
  const file = event.target.files[0]; if (!file) return;
  const imported = JSON.parse(await file.text());
  if (imported.run_id !== document.body.dataset.runId || imported.private_raw_sha256 !== document.body.dataset.rawSha) {
    return alert('이 실행의 판정 JSON이 아닙니다.');
  }
  const byId = new Map(imported.judgments.map((row) => [row.question_id, row]));
  document.querySelectorAll('.case').forEach((card) => { if (byId.has(card.dataset.questionId)) applyRow(card, byId.get(card.dataset.questionId)); });
  persist();
});

document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem(storageKey);
  if (saved) {
    try {
      const value = JSON.parse(saved); const byId = new Map(value.judgments.map((row) => [row.question_id, row]));
      document.querySelectorAll('.case').forEach((card) => { if (byId.has(card.dataset.questionId)) applyRow(card, byId.get(card.dataset.questionId)); });
    } catch (_error) { localStorage.removeItem(storageKey); }
  }
  document.querySelectorAll('.case').forEach(syncCard); updateProgress();
});
"""


def render_sheet(
    *,
    run_id: str,
    raw_sha256: str,
    judge: str,
    records: list[dict[str, Any]],
    references: dict[str, dict[str, Any]],
) -> str:
    cases = "".join(
        render_case(
            record,
            references.get(
                str(record["question_id"]), {"pages": [], "target_urls": []}
            ),
        )
        for record in records
    )
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>EXP-07 블라인드 본판정</title><style>{PAGE_CSS}</style></head>
<body data-schema-version="{_attr(JUDGMENT_SCHEMA_VERSION)}" data-run-id="{_attr(run_id)}"
 data-raw-sha="{_attr(raw_sha256)}" data-rubric-sha="{_attr(sha256_file(RUBRIC_PATH))}" data-judge="{_attr(judge)}">
<h1>EXP-07 블라인드 본판정</h1>
<p class="top-guide">1단계 행동 판정을 잠그기 전에는 주입 근거와 참조 묶음이 보이지 않습니다. 이 파일에는 기대 행동, 모델 자체 구조화 판정, 원시 LLM 출력과 2·3회차 응답이 들어 있지 않습니다.</p>
<div class="progress"></div>{cases}
<div class="toolbar"><label>JSON 불러오기<input type="file" accept="application/json" data-action="import"></label>
<button type="button" data-action="export-draft">중간 JSON</button><button type="button" data-action="export-final">잠금 JSON</button></div>
<script>{PAGE_JS}</script></body></html>"""


def _private_output_path(path: Path, run_dir: Path) -> None:
    resolved = path.resolve()
    allowed_roots = (RESULTS_DIR.resolve(), run_dir.resolve())
    if not any(
        resolved == root or resolved.is_relative_to(root) for root in allowed_roots
    ):
        raise ValueError("unmasked judgment sheets must stay under eval/results")


def assert_committed_file(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise ValueError("the safe run manifest must be committed in this repository")
    relative = resolved.relative_to(REPO_ROOT)
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(relative)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        raise ValueError("the safe run manifest must be committed before judgment")
    changed = subprocess.run(
        ["git", "status", "--porcelain", "--", str(relative)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if changed.strip():
        raise ValueError("the safe run manifest has uncommitted changes")


async def async_main(args: argparse.Namespace) -> Path:
    run_dir = args.run_dir.resolve()
    raw_path = run_dir / "raw.jsonl"
    summary = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if (
        summary.get("status") != "completed"
        or summary.get("corpus_unchanged") is not True
    ):
        raise ValueError("primary sheet requires a completed run with unchanged corpus")
    if summary.get("raw_sha256") != sha256_file(raw_path):
        raise ValueError("private raw SHA-256 differs from run.json")
    assert_committed_file(args.manifest)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("run_id") != summary.get("run_id"):
        raise ValueError("run manifest belongs to another run")
    if (manifest.get("private_raw") or {}).get("sha256") != summary.get("raw_sha256"):
        raise ValueError("run manifest raw SHA-256 differs from run.json")
    if (manifest.get("provenance") or {}).get("rubric_sha256") != sha256_file(
        RUBRIC_PATH
    ):
        raise ValueError("frozen rubric differs from the run manifest")
    records = primary_records(load_jsonl(raw_path))
    references = await load_reference_bundles(
        {str(record["question_id"]) for record in records},
        dsn=args.dsn,
    )
    output = (args.output or (run_dir / "exp07-primary-judgment.html")).resolve()
    _private_output_path(output, run_dir)
    document = render_sheet(
        run_id=str(summary["run_id"]),
        raw_sha256=str(summary["raw_sha256"]),
        judge=args.judge,
        records=records,
        references=references,
    )
    write_private_text(output, document)
    return output


def main() -> None:
    output = asyncio.run(async_main(parse_args()))
    print(f"wrote: {output.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
