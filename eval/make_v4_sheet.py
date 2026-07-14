"""qrel v4 페이지·근거 판정용 단일 HTML 시트를 만든다.

판정자는 검색 방식이나 순위 정보를 보지 않고 canonical URL 정렬 순서로 페이지와
청크 전문을 읽는다. 감사 실행은 지정한 행의 입력칸만 싣고 기존 라벨은 읽지 않는다.
출력에는 게시판 작성자 실명이 남을 수 있으므로 eval/results 밖으로 쓸 수 없다.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import html
import re
import sys
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.check_v4_invariants import load_csv  # noqa: E402
from eval.make_v4_pool import (  # noqa: E402
    CHUNK_FIELDS,
    CHUNK_POOL_PATH,
    DB_DSN,
    PAGE_FIELDS,
    PAGE_POOL_PATH,
    RESULTS_DIR,
)
from eval.run_questions import content_signature, normalize_url  # noqa: E402

QUESTIONS_PATH = REPO_ROOT / "eval" / "questions.csv"
DEFAULT_OUT_PATH = RESULTS_DIR / "qrel-v4-judgment-sheet.html"
DEFAULT_AUDIT_OUT_PATH = RESULTS_DIR / "qrel-v4-audit-sheet.html"
CONTENT_CHARS = 1500
JUDGMENT_SCHEMA_VERSION = "qrel-v4-judgment-1"

PHONE_RE = re.compile(
    r"(?<![0-9A-Za-z])(?:\(?0\d{1,2}\)?[-.\s)]*\d{3,4}[-.\s]?\d{4}"
    r"|1[5-8]\d{2}[-.\s]?\d{4}|\d{3,4}[-.\s]\d{4})(?![0-9A-Za-z])"
)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
BLIND_LITERAL_RE = re.compile(r"mode|rank|score", re.IGNORECASE)

SITE_LABELS = {
    "www.honam.ac.kr": "대학 공식 사이트(전교 공통)",
    "enter.honam.ac.kr": "입학안내 사이트(입학처)",
    "graduate.honam.ac.kr": "대학원 사이트",
    "dorm.honam.ac.kr": "생활관(기숙사) 사이트",
    "gyoyang.honam.ac.kr": "교양·융합전공 사이트",
    "dreamlife.honam.ac.kr": "드림라이프대학(단과대학) 사이트",
}

PAGE_CSS = """
* { box-sizing: border-box; }
body {
  max-width: 70rem; margin: 1.5rem auto; padding: 0 1.2rem 6rem;
  color: #172033; background: #fff; line-height: 1.55;
  font-family: Pretendard, "Noto Sans KR", "Malgun Gothic", sans-serif;
}
h1 { margin-bottom: .3rem; font-size: 1.6rem; }
h2 { margin: 2.2rem 0 .8rem; padding-top: 1rem; border-top: 4px solid #172033; }
h3 { margin: 0; font-size: 1.05rem; }
.guide { padding: 1rem 1.2rem; border: 1px solid #8993a4; border-radius: 10px; background: #f7f8fb; }
.guide li { margin: .3rem 0; }
.page-card { margin: 1rem 0; border: 2px solid #687386; border-radius: 10px; overflow: hidden; }
.page-head { padding: .8rem 1rem; background: #eef1f6; }
.chip { display: inline-block; margin-right: .45rem; padding: .05rem .45rem; border: 1px solid #8aa2c2;
  border-radius: 5px; color: #24466f; background: #e8f0fa; font-size: .75rem; font-weight: 700; }
.url { margin-top: .2rem; color: #4b5565; font: .78rem ui-monospace, Consolas, monospace; word-break: break-all; }
.row-id { margin-top: .25rem; color: #6b7280; font: .72rem ui-monospace, Consolas, monospace; word-break: break-all; }
.chunk { margin: .8rem; border: 1px solid #c5cad3; border-radius: 8px; overflow: hidden; }
.chunk-head { padding: .45rem .65rem; color: #364152; background: #f5f6f8; font-size: .8rem; }
.content { padding: .65rem .8rem; white-space: pre-wrap; word-break: break-word; font-size: .88rem; }
.judge { margin: .8rem; padding: .8rem 1rem; border: 2px solid #2e4d72; border-radius: 8px; background: #fbfdff; }
.judge-title { margin-bottom: .45rem; font-weight: 800; }
.bundle-timer { margin-top: .6rem; }
.bundle-timer button { margin-right: .5rem; padding: .25rem .55rem; border: 1px solid #6d7890;
  border-radius: 5px; background: #fff; cursor: pointer; }
.bundle-timer button:disabled { cursor: default; background: #eef2f7; }
.timing-summary { margin-top: .8rem; padding: .65rem .8rem; border: 1px solid #9aa3b2;
  border-radius: 7px; background: #fff; }
.context-card { border-style: dashed; background: #f7f8fa; }
.context-note { margin-top: .55rem; color: #5b6472; font-weight: 700; }
.axis { margin: .45rem 0; }
.axis-title { display: inline-block; min-width: 9.5rem; font-weight: 700; }
label { display: inline-block; margin: .15rem .9rem .15rem 0; }
input[type="radio"], input[type="checkbox"] { margin-right: .3rem; }
input[type="text"], textarea, select { padding: .3rem .4rem; border: 1px solid #9aa3b2;
  border-radius: 4px; font: inherit; }
textarea { width: 100%; min-height: 3.2rem; resize: vertical; }
.question-judge { margin-top: 1rem; border-color: #7c3f72; background: #fffafd; }
.muted { color: #667085; font-size: .82rem; }
.export-btn { position: fixed; right: 1.2rem; bottom: 1.2rem; padding: .7rem 1rem; border: 0;
  border-radius: 8px; color: #fff; background: #24466f; font: inherit; font-weight: 800;
  cursor: pointer; box-shadow: 0 3px 12px #0004; }
@media print {
  body { max-width: none; margin: 0; }
  .page-card, .chunk, .judge { break-inside: avoid; }
  .export-btn { display: none; }
}
"""

SHEET_JS = """
function formatElapsed(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}분 ${String(remainder).padStart(2, '0')}초`;
}

function medianSeconds(values) {
  if (!values.length) return null;
  const ordered = values.slice().sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? ordered[middle]
    : Math.round((ordered[middle - 1] + ordered[middle]) / 2);
}

function timingSnapshot() {
  const cards = Array.from(document.querySelectorAll('.page-card[data-timed="true"]'));
  const bundles = cards.map((card) => ({
    page_row_id: card.dataset.pageRowId,
    elapsed_seconds: Number(card.dataset.elapsedSeconds || 0) || null,
  }));
  const elapsed = bundles.map((bundle) => bundle.elapsed_seconds).filter(Boolean);
  return {
    bundle_count: bundles.length,
    complete_bundle_count: elapsed.length,
    median_seconds: medianSeconds(elapsed),
    bundles,
  };
}

function updateTimingSummary() {
  const summary = document.getElementById('timing-summary');
  if (!summary) return;
  const timing = timingSnapshot();
  const elapsed = timing.bundles.map((bundle) => bundle.elapsed_seconds).filter(Boolean);
  if (!elapsed.length) {
    summary.textContent = `완료 0/${timing.bundle_count}묶음 · 판정 시작 버튼을 누르면 선택지가 열립니다.`;
    return;
  }
  summary.textContent = `완료 ${timing.complete_bundle_count}/${timing.bundle_count}묶음`
    + ` · 중앙 ${formatElapsed(timing.median_seconds)}`
    + ` · 개별 ${elapsed.map(formatElapsed).join(', ')}`;
}

function setBundleControlsEnabled(card, enabled) {
  card.querySelectorAll('.judgment-row input, .judgment-row select, .judgment-row textarea')
    .forEach((control) => { control.disabled = !enabled; });
}

function bundleIsComplete(card) {
  const page = card.querySelector('.judgment-row[data-kind="page"]');
  if (!page || !picked(page, 'support_grade') || !picked(page, 'temporal_validity')
      || !picked(page, 'audience_scope')) return false;
  return Array.from(card.querySelectorAll('.judgment-row[data-kind="evidence"]'))
    .every((section) => {
      const grade = picked(section, 'evidence_grade');
      return grade === 'none' || Boolean(grade && picked(section, 'evidence_type'));
    });
}

function startBundleTimer(button) {
  const card = button.closest('.page-card');
  const output = card.querySelector('.bundle-time');
  if (card.dataset.timerStarted) return;
  card.dataset.timerStarted = String(Date.now());
  button.textContent = '판정 중';
  button.disabled = true;
  output.textContent = '모든 항목을 고르면 자동 완료됩니다.';
  setBundleControlsEnabled(card, true);
}

function finishBundleTimer(card) {
  if (!card.dataset.timerStarted || card.dataset.elapsedSeconds) return;
  const elapsed = Math.max(1, Math.round((Date.now() - Number(card.dataset.timerStarted)) / 1000));
  card.dataset.elapsedSeconds = String(elapsed);
  const button = card.querySelector('.bundle-timer button');
  const output = card.querySelector('.bundle-time');
  button.textContent = '판정 완료';
  output.textContent = formatElapsed(elapsed);
  updateTimingSummary();
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.page-card[data-timed="true"]').forEach((card) => {
    setBundleControlsEnabled(card, false);
  });
  document.addEventListener('change', (event) => {
    const card = event.target.closest('.page-card[data-timed="true"]');
    if (card && bundleIsComplete(card)) finishBundleTimer(card);
  });
});

function picked(section, field) {
  const item = section.querySelector(`input[data-field="${field}"]:checked`);
  return item ? item.value : null;
}

function textValue(section, field) {
  const item = section.querySelector(`[data-field="${field}"]`);
  return item ? item.value.trim() : '';
}

function exportJudgments() {
  const result = {
    schema_version: 'qrel-v4-judgment-1',
    audit: document.body.dataset.audit === 'true',
    judge: document.getElementById('judge-name').value.trim(),
    date: document.getElementById('judge-date').value.trim(),
    exported_at: new Date().toISOString(),
    pages: [],
    evidence: [],
    questions: [],
  };
  const incomplete = [];

  if (result.audit) {
    result.audit_timing = timingSnapshot();
    result.audit_timing.bundles
      .filter((bundle) => !bundle.elapsed_seconds)
      .forEach((bundle) => incomplete.push(`TIMER|${bundle.page_row_id}`));
  }

  document.querySelectorAll('.judgment-row[data-kind="page"]').forEach((section) => {
    const support = picked(section, 'support_grade');
    const temporal = picked(section, 'temporal_validity');
    const audience = picked(section, 'audience_scope');
    const complete = Boolean(support && temporal && audience);
    if (!complete) incomplete.push(section.dataset.rowId);
    result.pages.push({
      row_id: section.dataset.rowId,
      question_id: section.dataset.questionId,
      canonical_url: section.dataset.canonicalUrl,
      judged: complete,
      support_grade: support || '',
      temporal_validity: temporal || '',
      audience_scope: audience || '',
      notes: textValue(section, 'notes'),
    });
  });

  document.querySelectorAll('.judgment-row[data-kind="evidence"]').forEach((section) => {
    const rawGrade = picked(section, 'evidence_grade');
    const evidenceType = picked(section, 'evidence_type');
    const complete = rawGrade === 'none' || Boolean(rawGrade && evidenceType);
    if (!complete) incomplete.push(section.dataset.rowId);
    result.evidence.push({
      row_id: section.dataset.rowId,
      question_id: section.dataset.questionId,
      canonical_url: section.dataset.canonicalUrl,
      chunk_id: section.dataset.chunkId,
      judged: complete,
      evidence_grade: rawGrade === 'none' ? '' : (rawGrade || ''),
      evidence_type: rawGrade === 'none' ? '' : (evidenceType || ''),
      notes: textValue(section, 'notes'),
    });
  });

  document.querySelectorAll('.judgment-row[data-kind="question"]').forEach((section) => {
    const behavior = picked(section, 'expected_behavior');
    const primary = textValue(section, 'primary_reason');
    const override = section.querySelector('[data-field="composition_override"]').checked;
    const explicitSupport = textValue(section, 'pool_support');
    const secondary = Array.from(
      section.querySelectorAll('input[data-field="secondary_reasons"]:checked')
    ).map((item) => item.value);
    const complete = Boolean(behavior)
      && (behavior !== 'abstain' || Boolean(primary))
      && (!override || Boolean(explicitSupport));
    if (!complete) incomplete.push(section.dataset.rowId);
    result.questions.push({
      row_id: section.dataset.rowId,
      question_id: section.dataset.questionId,
      judged: complete,
      expected_behavior: behavior || '',
      primary_reason: primary,
      secondary_reasons: secondary,
      composition_override: override,
      pool_support: override ? explicitSupport : '',
      composition_sources: textValue(section, 'composition_sources')
        .split('|').map((item) => item.trim()).filter(Boolean),
      notes: textValue(section, 'notes'),
    });
  });

  if (incomplete.length) {
    const proceed = confirm(
      '미완료 행이 있습니다: ' + incomplete.slice(0, 20).join(', ')
      + (incomplete.length > 20 ? ` 외 ${incomplete.length - 20}건` : '')
      + '\\n그래도 내보낼까요?'
    );
    if (!proceed) return;
  }
  const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = document.body.dataset.exportName || (result.audit
    ? 'qrel-v4-secondary-audit.json'
    : 'qrel-v4-primary-initial.json');
  link.click();
  URL.revokeObjectURL(link.href);
}
"""


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    canonical_url: str
    title: str
    menu_path: str
    chunk_index: int
    content: str
    content_hash: str


def mask_pii(text: str) -> str:
    masked = PHONE_RE.sub("***-****-****", text)
    return EMAIL_RE.sub("***@***", masked)


def assert_masked(text: str) -> None:
    # 청크 식별자의 숫자 구간(예: 4459-9230)을 교내 전화로 오인하지 않는다.
    searchable = UUID_RE.sub("", text)
    phone = PHONE_RE.search(searchable)
    if phone:
        raise ValueError(f"마스킹되지 않은 전화번호가 남았습니다: {phone.group()[:4]}***")
    email = EMAIL_RE.search(searchable)
    if email:
        raise ValueError("마스킹되지 않은 이메일이 남았습니다")


def site_label(url: str) -> str:
    hostname = re.sub(r"^https?://", "", url).split("/")[0].lower()
    if hostname in SITE_LABELS:
        return SITE_LABELS[hostname]
    if hostname.endswith(".honam.ac.kr"):
        return "특정 학과 사이트"
    return hostname


def page_row_id(question_id: str, canonical_url: str) -> str:
    return f"P|{question_id}|{canonical_url}"


def evidence_row_id(question_id: str, chunk_id: str) -> str:
    return f"E|{question_id}|{chunk_id}"


def question_row_id(question_id: str) -> str:
    return f"Q|{question_id}"


def load_questions(path: Path = QUESTIONS_PATH) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        return {row["id"]: dict(row) for row in csv.DictReader(input_file)}


async def load_chunk_records(
    chunk_rows: Iterable[Mapping[str, str]],
    *,
    dsn: str = DB_DSN,
) -> dict[str, ChunkRecord]:
    rows = list(chunk_rows)
    ids: list[uuid.UUID] = []
    invalid_ids: list[str] = []
    for chunk_id in sorted({row["chunk_id"] for row in rows}):
        try:
            ids.append(uuid.UUID(chunk_id))
        except ValueError:
            invalid_ids.append(chunk_id)
    if invalid_ids:
        raise ValueError(f"UUID가 아닌 chunk_id: {', '.join(invalid_ids)}")

    connection = await asyncpg.connect(dsn)
    try:
        records = await connection.fetch(
            """
            SELECT c.id, c.chunk_index, c.content, d.url, d.title, d.menu_path
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.id = ANY($1::uuid[])
            """,
            ids,
        )
    finally:
        await connection.close()

    loaded = {
        str(record["id"]): ChunkRecord(
            chunk_id=str(record["id"]),
            canonical_url=normalize_url(record["url"]),
            title=str(record["title"] or "(제목 없음)"),
            menu_path=str(record["menu_path"] or ""),
            chunk_index=int(record["chunk_index"]),
            content=str(record["content"] or ""),
            content_hash=content_signature(record["content"]),
        )
        for record in records
    }

    failures: list[str] = []
    for row in rows:
        record = loaded.get(row["chunk_id"])
        row_id = evidence_row_id(row["question_id"], row["chunk_id"])
        if record is None:
            failures.append(f"{row_id}: DB 청크 누락")
            continue
        if record.canonical_url != normalize_url(row["canonical_url"]):
            failures.append(f"{row_id}: URL 불일치")
        if record.content_hash != row["content_hash"]:
            failures.append(f"{row_id}: content_hash 불일치")
    if failures:
        raise ValueError("판정 시트 DB 검증 실패:\n" + "\n".join(f"- {x}" for x in failures))
    return loaded


def _obscure_blind_literals(escaped: str) -> str:
    # SpecialScore 같은 실제 URL은 화면에 그대로 보이되 원문 HTML에는 금지어를 남기지 않는다.
    return BLIND_LITERAL_RE.sub(
        lambda match: match.group()[:-1] + f"&#{ord(match.group()[-1])};",
        escaped,
    )


def _attr(value: str) -> str:
    return _obscure_blind_literals(html.escape(value, quote=True))


def _text(value: str) -> str:
    return _obscure_blind_literals(html.escape(value))


def _radio(group: str, field: str, value: str, label: str) -> str:
    return (
        f'<label><input type="radio" name="{_attr(group)}" '
        f'data-field="{_attr(field)}" value="{_attr(value)}">'
        f"{_text(label)}</label>"
    )


def render_page_judgment(question_id: str, canonical_url: str, index: int) -> str:
    row_id = page_row_id(question_id, canonical_url)
    prefix = f"p-{index}"
    support = "".join(
        _radio(f"{prefix}-support", "support_grade", value, label)
        for value, label in (("full", "완전"), ("partial", "일부"), ("invalid", "무관"))
    )
    temporal = "".join(
        _radio(f"{prefix}-time", "temporal_validity", value, label)
        for value, label in (
            ("current", "현행"),
            ("stale", "지난 정보"),
            ("unknown", "불명"),
        )
    )
    audience = "".join(
        _radio(f"{prefix}-audience", "audience_scope", value, label)
        for value, label in (
            ("match", "대상 일치"),
            ("mismatch", "대상 불일치"),
            ("unknown", "불명"),
        )
    )
    return f"""
<div class="judge judgment-row" data-kind="page" data-row-id="{_attr(row_id)}"
 data-question-id="{_attr(question_id)}" data-canonical-url="{_attr(canonical_url)}">
  <div class="judge-title">페이지 판정</div>
  <div class="row-id">행 ID: {_text(row_id)}</div>
  <div class="axis"><span class="axis-title">내용 지지</span>{support}</div>
  <div class="axis"><span class="axis-title">시점</span>{temporal}</div>
  <div class="axis"><span class="axis-title">대상</span>{audience}</div>
  <div class="axis"><span class="axis-title">메모</span><textarea data-field="notes"></textarea></div>
</div>"""


def render_chunk(
    pool_row: Mapping[str, str],
    record: ChunkRecord,
    *,
    control_index: int | None,
) -> str:
    row_id = evidence_row_id(pool_row["question_id"], pool_row["chunk_id"])
    content = mask_pii(record.content)
    shown = content[:CONTENT_CHARS]
    if len(content) > CONTENT_CHARS:
        shown += " … (이하 생략 — 청크가 더 이어짐)"
    control = ""
    if control_index is not None:
        prefix = f"e-{control_index}"
        grade = "".join(
            _radio(f"{prefix}-grade", "evidence_grade", value, label)
            for value, label in (
                ("full", "완전 근거"),
                ("partial", "부분 근거"),
                ("none", "근거 아님"),
            )
        )
        evidence_type = "".join(
            _radio(f"{prefix}-type", "evidence_type", value, label)
            for value, label in (
                ("text_chunk", "본문 근거"),
                ("page_navigation", "페이지 위치 자체가 근거"),
            )
        )
        control = f"""
<div class="judge judgment-row" data-kind="evidence" data-row-id="{_attr(row_id)}"
 data-question-id="{_attr(pool_row["question_id"])}"
 data-canonical-url="{_attr(pool_row["canonical_url"])}"
 data-chunk-id="{_attr(pool_row["chunk_id"])}">
  <div class="judge-title">청크 근거 판정</div>
  <div class="row-id">행 ID: {_text(row_id)}</div>
  <div class="axis"><span class="axis-title">근거 강도</span>{grade}</div>
  <div class="axis"><span class="axis-title">근거 유형</span>{evidence_type}</div>
  <div class="muted">‘근거 아님’을 고르면 근거 유형은 선택하지 않습니다.</div>
  <div class="axis"><span class="axis-title">메모</span><textarea data-field="notes"></textarea></div>
</div>"""
    return f"""
<div class="chunk">
  <div class="chunk-head">청크 {record.chunk_index} · {_text(mask_pii(record.title))}
    <div class="row-id">{_text(row_id)}</div>
  </div>
  <div class="content">{_text(shown)}</div>
  {control}
</div>"""


def render_page(
    page: Mapping[str, str],
    chunks: list[tuple[Mapping[str, str], ChunkRecord, bool]],
    *,
    page_control: bool,
    page_index: int,
    evidence_counter: list[int],
    show_timer: bool = False,
    context_only: bool = False,
) -> str:
    canonical_url = page["canonical_url"]
    first = chunks[0][1]
    rendered_chunks: list[str] = []
    for pool_row, record, evidence_control in chunks:
        control_index = None
        if evidence_control:
            evidence_counter[0] += 1
            control_index = evidence_counter[0]
        rendered_chunks.append(render_chunk(pool_row, record, control_index=control_index))
    page_judgment = render_page_judgment(page["question_id"], canonical_url, page_index) if page_control else ""
    timer = ""
    if show_timer and page_control:
        timer = """
    <div class="bundle-timer"><button type="button" onclick="startBundleTimer(this)">판정 시작(필수)</button>
      <span class="bundle-time muted">미측정</span></div>"""
    context_note = ""
    if context_only:
        context_note = '<div class="context-note">비교 문맥 · 이 페이지는 판정하지 않습니다.</div>'
    return f"""
<section class="page-card{' context-card' if context_only else ''}"{' data-timed="true"' if timer else ""}
 data-page-row-id="{_attr(page_row_id(page['question_id'], canonical_url))}">
  <div class="page-head">
    <h3><span class="chip">{_text(site_label(canonical_url))}</span>{_text(mask_pii(first.title))}</h3>
    <div class="url">{_text(mask_pii(canonical_url))}</div>
    {f'<div class="muted">메뉴: {_text(mask_pii(first.menu_path))}</div>' if first.menu_path else ""}
    {context_note}
    {timer}
  </div>
  {"".join(rendered_chunks)}
  {page_judgment}
</section>"""


def render_question_judgment(question_id: str, index: int) -> str:
    prefix = f"q-{index}"
    behavior = "".join(
        _radio(f"{prefix}-behavior", "expected_behavior", value, label)
        for value, label in (
            ("full_answer", "완전 답변"),
            ("qualified_answer", "제한을 밝힌 답변"),
            ("abstain", "답변 보류"),
        )
    )
    reason_options = (
        ("", "선택 안 함"),
        ("acquisition_failure", "수집 실패"),
        ("absent", "코퍼스에 없음"),
        ("missing_required_claim", "필수 주장 누락"),
        ("stale", "지난 정보"),
        ("audience_mismatch", "대상 불일치"),
        ("personalized", "개인 정보 필요"),
        ("policy_exclusion", "정책상 제외"),
    )
    primary = "".join(f'<option value="{_attr(value)}">{_text(label)}</option>' for value, label in reason_options)
    secondary = "".join(
        f'<label><input type="checkbox" data-field="secondary_reasons" value="{_attr(value)}">{_text(label)}</label>'
        for value, label in reason_options[1:]
    )
    row_id = question_row_id(question_id)
    return f"""
<div class="judge question-judge judgment-row" data-kind="question"
 data-row-id="{_attr(row_id)}" data-question-id="{_attr(question_id)}">
  <div class="judge-title">질문 수준 판정</div>
  <div class="row-id">행 ID: {_text(row_id)}</div>
  <div class="axis"><span class="axis-title">기대 동작</span>{behavior}</div>
  <div class="axis"><span class="axis-title">주된 이유</span>
    <select data-field="primary_reason">{primary}</select>
  </div>
  <div class="axis"><span class="axis-title">부차 이유</span>{secondary}</div>
  <div class="axis"><label><input type="checkbox" data-field="composition_override">여러 페이지 조합으로
    support를 명시</label></div>
  <div class="axis"><span class="axis-title">명시 support</span>
    <select data-field="pool_support"><option value="">선택 안 함</option><option value="full">full</option>
      <option value="partial">partial</option><option value="none">none</option></select>
  </div>
  <div class="axis"><span class="axis-title">조합 출처</span>
    <input type="text" data-field="composition_sources" placeholder="URL을 | 로 구분"></div>
  <div class="axis"><span class="axis-title">메모</span><textarea data-field="notes"></textarea></div>
</div>"""


def load_audit_ids(path: Path) -> set[str]:
    values = {
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if not values:
        raise ValueError(f"{path}: 감사 행 ID가 없습니다")
    return values


def render_sheet(
    page_rows: list[dict[str, str]],
    chunk_rows: list[dict[str, str]],
    questions: Mapping[str, Mapping[str, str]],
    records: Mapping[str, ChunkRecord],
    *,
    audit_ids: set[str] | None = None,
    export_filename: str | None = None,
) -> str:
    control_audit_ids = audit_ids
    context_page_control_ids: set[str] = set()
    if audit_ids is not None:
        context_page_control_ids = {
            value.removeprefix("C|")
            for value in audit_ids
            if value.startswith("C|")
        }
        control_audit_ids = {
            value for value in audit_ids if not value.startswith("C|")
        }

    pages_by_question: dict[str, list[dict[str, str]]] = defaultdict(list)
    chunks_by_page: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for page in page_rows:
        pages_by_question[page["question_id"]].append(page)
    for row in chunk_rows:
        chunks_by_page[(row["question_id"], normalize_url(row["canonical_url"]))].append(row)

    valid_ids = set(questions)
    valid_ids.update(question_row_id(question_id) for question_id in questions)
    valid_ids.update(page_row_id(row["question_id"], row["canonical_url"]) for row in page_rows)
    valid_ids.update(evidence_row_id(row["question_id"], row["chunk_id"]) for row in chunk_rows)
    if audit_ids is not None:
        unknown = sorted((control_audit_ids or set()) - valid_ids)
        if unknown:
            raise ValueError("pool에 없는 감사 행 ID:\n" + "\n".join(f"- {x}" for x in unknown))
        unknown_context = sorted(context_page_control_ids - valid_ids)
        if unknown_context:
            raise ValueError(
                "pool에 없는 비교 문맥 페이지 ID:\n"
                + "\n".join(f"- {x}" for x in unknown_context)
            )
        invalid_context = sorted(
            value for value in context_page_control_ids if not value.startswith("P|")
        )
        if invalid_context:
            raise ValueError("비교 문맥은 페이지 ID만 허용합니다")

    sections: list[str] = []
    page_counter = 0
    question_counter = 0
    evidence_counter = [0]
    for question_id, question in sorted(questions.items()):
        select_all = control_audit_ids is None or question_id in control_audit_ids
        include_question_control = select_all or (
            control_audit_ids is not None
            and question_row_id(question_id) in control_audit_ids
        )
        rendered_pages: list[str] = []
        for page in sorted(pages_by_question.get(question_id, []), key=lambda row: row["canonical_url"]):
            page_id = page_row_id(question_id, page["canonical_url"])
            page_control = select_all or (
                control_audit_ids is not None and page_id in control_audit_ids
            )
            context_only = page_id in context_page_control_ids and not page_control
            page_chunks = sorted(
                chunks_by_page[(question_id, normalize_url(page["canonical_url"]))],
                key=lambda row: (records[row["chunk_id"]].chunk_index, row["chunk_id"]),
            )
            selected_chunks = []
            for chunk in page_chunks:
                evidence_id = evidence_row_id(question_id, chunk["chunk_id"])
                evidence_control = select_all or (
                    control_audit_ids is not None
                    and evidence_id in control_audit_ids
                )
                if (
                    control_audit_ids is None
                    or select_all
                    or page_control
                    or evidence_control
                    or context_only
                ):
                    selected_chunks.append((chunk, records[chunk["chunk_id"]], evidence_control))
            if not selected_chunks:
                continue
            if page_control:
                page_counter += 1
            rendered_pages.append(
                render_page(
                    page,
                    selected_chunks,
                    page_control=page_control,
                    page_index=page_counter,
                    evidence_counter=evidence_counter,
                    show_timer=audit_ids is not None,
                    context_only=context_only,
                )
            )

        if not rendered_pages and not include_question_control:
            continue
        question_counter += 1
        question_judgment = render_question_judgment(question_id, question_counter) if include_question_control else ""
        sections.append(
            f"<section><h2>{_text(question_id)}. "
            f"{_text(mask_pii(str(question['question'])))}</h2>"
            + "".join(rendered_pages)
            + question_judgment
            + "</section>"
        )

    audit = audit_ids is not None
    title = "qrel v4 2차 감사 시트" if audit else "qrel v4 1차 전량 판정 시트"
    guide = """
<div class="guide">
  <strong>판정 원칙</strong>
  <ul>
    <li>제시된 페이지와 청크만 근거로 판정합니다.</li>
    <li><strong>내용 지지</strong>: 시점과 대상을 무시하고 질문에 담긴 주장만 봅니다.
      정확히 답하면 완전, 의미 있는 일부만 답하면 일부, 필요한 주장이 없으면 무관입니다.</li>
    <li>지난 정보나 대상이 다른 정보도 내용 자체가 정확하면 완전 또는 일부일 수 있습니다.
      예를 들어 담당 부서만 있고 위치가 없으면 위치 질문에 일부입니다.</li>
    <li><strong>시점</strong>: 2026-07-14 기준입니다. 마감된 신청·행사 정보는 지난 정보입니다.
      과거 연도가 보여도 해당 입학년도 학생에게 계속 적용되는 규정이면 현행일 수 있습니다.</li>
    <li><strong>대상</strong>: 질문이 전제하는 사람과 문서 본문의 대상을 비교합니다.
      학과 사이트는 불일치의 신호지만, 본문이 전교 공통임을 보여주면 일치입니다.</li>
    <li><strong>청크 근거</strong>: 청크 자체가 질문에 필요한 주장을 지지하는지 봅니다.
      양성 페이지 안에도 근거가 아닌 청크가 있을 수 있고, 무관 페이지의 청크는 근거 아님입니다.</li>
    <li>위치 안내 질문은 페이지 도달 자체가 답일 때만 페이지 위치 자체를 근거로 고릅니다.</li>
    <li>이 시트에는 검색 방식·순위·점수가 표시되지 않습니다.</li>
  </ul>
</div>"""
    timing_summary = ""
    if audit:
        timing_summary = (
            f'<div id="timing-summary" class="timing-summary">완료 0/{page_counter}묶음 · '
            "판정 시작 버튼을 누르면 선택지가 열리고, 모든 항목을 고르면 시간이 자동 저장됩니다.</div>"
        )
    resolved_export_filename = export_filename or (
        "qrel-v4-secondary-audit.json" if audit else "qrel-v4-primary-initial.json"
    )
    output = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{PAGE_CSS}</style>
</head>
<body data-audit="{"true" if audit else "false"}"
 data-export-name="{_attr(resolved_export_filename)}">
<h1>{title}</h1>
<p>판정자 <input type="text" id="judge-name"> · 판정일 <input type="text" id="judge-date"></p>
{guide}
{timing_summary}
{"".join(sections)}
<button type="button" class="export-btn" onclick="exportJudgments()">판정 JSON 내보내기</button>
<script>{SHEET_JS}</script>
</body>
</html>
"""
    assert_masked(output)
    lowered = output.lower()
    forbidden = [value for value in ("mode", "rank", "score") if value in lowered]
    if forbidden:
        raise ValueError(f"블라인드 HTML에 금지 문자열이 있습니다: {', '.join(forbidden)}")
    return output


def ensure_results_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(RESULTS_DIR.resolve())
    except ValueError as error:
        raise ValueError(f"판정 시트는 {RESULTS_DIR} 안에만 쓸 수 있습니다") from error
    return resolved


def write_html_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="qrel v4 블라인드 판정 HTML을 생성합니다.")
    parser.add_argument("--audit", type=Path, help="감사할 행 ID를 한 줄씩 적은 파일")
    parser.add_argument("--out", type=Path, help="eval/results 안의 출력 HTML 경로")
    parser.add_argument("--download-name", help="브라우저에서 내보낼 JSON 파일명")
    parser.add_argument("--db-dsn", default=DB_DSN)
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    page_rows = load_csv(PAGE_POOL_PATH, PAGE_FIELDS)
    chunk_rows = load_csv(CHUNK_POOL_PATH, CHUNK_FIELDS)
    questions = load_questions()
    records = await load_chunk_records(chunk_rows, dsn=args.db_dsn)
    audit_ids = load_audit_ids(args.audit) if args.audit else None
    output_path = args.out or (DEFAULT_AUDIT_OUT_PATH if audit_ids is not None else DEFAULT_OUT_PATH)
    output_path = ensure_results_path(output_path)
    document = render_sheet(
        page_rows,
        chunk_rows,
        questions,
        records,
        audit_ids=audit_ids,
        export_filename=args.download_name,
    )
    write_html_atomic(output_path, document)
    row_count = document.count('class="judge judgment-row"') + document.count(
        'class="judge question-judge judgment-row"'
    )
    print(f"저장: {output_path} (판정 행 {row_count}개)")
    print("전화·이메일 마스킹 및 블라인드 문자열 검증 통과")


if __name__ == "__main__":
    asyncio.run(run())
