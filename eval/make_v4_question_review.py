"""조정된 page·evidence를 바탕으로 50문항 질문 수준 검토 시트를 만든다."""

from __future__ import annotations

import argparse
import asyncio
import html
import sys
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.build_v4_qrel import load_json  # noqa: E402
from eval.check_v4_invariants import derive_pool_support, load_csv  # noqa: E402
from eval.make_v4_pool import CHUNK_FIELDS, CHUNK_POOL_PATH  # noqa: E402
from eval.make_v4_sheet import (  # noqa: E402
    ChunkRecord,
    ensure_results_path,
    load_chunk_records,
    load_questions,
    mask_pii,
    site_label,
    write_html_atomic,
)
from eval.run_questions import normalize_url  # noqa: E402

RESULTS_DIR = REPO_ROOT / "eval" / "results"
DEFAULT_JUDGMENTS_PATH = (
    REPO_ROOT / "tmp" / "qrel-v4" / "qrel-v4-page-evidence-adjudicated.json"
)
DEFAULT_OUT_PATH = RESULTS_DIR / "qrel-v4-question-review.html"
DEFAULT_DOWNLOAD_NAME = "qrel-v4-question-review.json"

BEHAVIOR_LABELS = {
    "full_answer": "완전 답변",
    "qualified_answer": "제한을 밝힌 답변",
    "abstain": "답변 보류",
}
REASON_LABELS = {
    "": "선택 안 함",
    "acquisition_failure": "수집 실패",
    "absent": "코퍼스에 없음",
    "missing_required_claim": "필수 주장 누락",
    "stale": "지난 정보",
    "audience_mismatch": "대상 불일치",
    "personalized": "개인 정보 필요",
    "policy_exclusion": "정책상 제외",
}


def _text(value: object) -> str:
    return html.escape(mask_pii(str(value or "")), quote=False)


def _attr(value: object) -> str:
    return html.escape(mask_pii(str(value or "")), quote=True)


def _question_sort_key(question_id: str) -> tuple[int, str]:
    numeric = question_id.removeprefix("Q")
    return (int(numeric) if numeric.isdigit() else sys.maxsize, question_id)


def _index_unique(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) or "")
        if not key or key in indexed:
            raise ValueError(f"{field}가 비었거나 중복됐습니다: {key!r}")
        indexed[key] = row
    return indexed


def _badge(value: str) -> str:
    labels = {
        "full": "완전",
        "partial": "일부",
        "invalid": "무관",
        "current": "현행",
        "stale": "지난 정보",
        "unknown": "불명",
        "match": "대상 일치",
        "mismatch": "대상 불일치",
        "text_chunk": "본문 근거",
        "page_navigation": "페이지 이동 근거",
    }
    return f'<span class="badge badge-{_attr(value)}">{_text(labels.get(value, value))}</span>'


def _render_evidence(
    evidence_rows: list[dict[str, Any]],
    records: Mapping[str, ChunkRecord],
) -> str:
    rendered: list[str] = []
    for row in sorted(evidence_rows, key=lambda item: str(item["chunk_id"])):
        grade = str(row.get("evidence_grade") or "")
        if grade not in {"full", "partial"}:
            continue
        record = records[str(row["chunk_id"])]
        rendered.append(
            f"""
<details class="evidence">
  <summary>{_badge(grade)} {_badge(str(row.get("evidence_type") or ""))}
    청크 {record.chunk_index} · {_text(record.title)}</summary>
  <div class="row-id">{_text(row['row_id'])}</div>
  <pre>{_text(record.content)}</pre>
  {f'<div class="note">{_text(row.get("notes"))}</div>' if row.get("notes") else ''}
</details>"""
        )
    return "".join(rendered) or '<div class="empty">양성 evidence가 없습니다.</div>'


def _render_positive_pages(
    question_id: str,
    pages: list[dict[str, Any]],
    evidence_by_page: Mapping[tuple[str, str], list[dict[str, Any]]],
    records: Mapping[str, ChunkRecord],
) -> str:
    positive = [row for row in pages if row.get("support_grade") in {"full", "partial"}]
    if not positive:
        return '<div class="empty">판정 pool에 양성 페이지가 없습니다.</div>'

    rendered: list[str] = []
    for page in sorted(positive, key=lambda row: str(row["canonical_url"])):
        canonical_url = normalize_url(str(page["canonical_url"]))
        evidence_rows = evidence_by_page.get((question_id, canonical_url), [])
        record = next(
            (records[str(row["chunk_id"])] for row in evidence_rows if str(row["chunk_id"]) in records),
            None,
        )
        title = record.title if record else canonical_url
        rendered.append(
            f"""
<article class="page-summary">
  <h4><span class="site">{_text(site_label(canonical_url))}</span>{_text(title)}</h4>
  <div class="badges">{_badge(str(page['support_grade']))}
    {_badge(str(page['temporal_validity']))} {_badge(str(page['audience_scope']))}</div>
  <div class="url">{_text(canonical_url)}</div>
  {f'<div class="note">{_text(page.get("notes"))}</div>' if page.get("notes") else ''}
  {_render_evidence(evidence_rows, records)}
</article>"""
        )
    return "".join(rendered)


def _render_controls(
    question_id: str,
    recommendation: Mapping[str, Any],
    derived_support: str,
) -> str:
    behavior_value = str(recommendation.get("expected_behavior") or "")
    behaviors = "".join(
        f'<label><input type="radio" name="{_attr(question_id)}-behavior" '
        f'data-field="expected_behavior" value="{_attr(value)}"'
        f'{" checked" if value == behavior_value else ""}>{_text(label)}</label>'
        for value, label in BEHAVIOR_LABELS.items()
    )

    primary_value = str(recommendation.get("primary_reason") or "")
    primary = "".join(
        f'<option value="{_attr(value)}"'
        f'{" selected" if value == primary_value else ""}>{_text(label)}</option>'
        for value, label in REASON_LABELS.items()
    )

    secondary_values = {str(value) for value in recommendation.get("secondary_reasons", [])}
    secondary = "".join(
        f'<label><input type="checkbox" data-field="secondary_reasons" value="{_attr(value)}"'
        f'{" checked" if value in secondary_values else ""}>{_text(label)}</label>'
        for value, label in REASON_LABELS.items()
        if value
    )

    override = recommendation.get("composition_override") is True
    explicit_support = str(recommendation.get("pool_support") or derived_support)
    support_options = "".join(
        f'<option value="{value}"'
        f'{" selected" if value == explicit_support else ""}>{value}</option>'
        for value in ("full", "partial", "none")
    )
    sources = "|".join(str(value) for value in recommendation.get("composition_sources", []))
    notes = str(recommendation.get("notes") or "")

    return f"""
<div class="controls">
  <div class="axis"><strong>기대 동작</strong>{behaviors}</div>
  <div class="axis"><label><strong>주된 이유</strong>
    <select data-field="primary_reason">{primary}</select></label></div>
  <div class="axis"><strong>부차 이유</strong>{secondary}</div>
  <details class="composition">
    <summary>여러 페이지 조합 예외</summary>
    <label><input type="checkbox" data-field="composition_override"{' checked' if override else ''}>
      조합으로 support를 명시</label>
    <label>명시 support <select data-field="pool_support">{support_options}</select></label>
    <label>조합 출처 <input type="text" data-field="composition_sources"
      value="{_attr(sources)}" placeholder="URL을 | 로 구분"></label>
  </details>
  <label class="notes"><strong>판정 메모</strong>
    <textarea data-field="notes">{_text(notes)}</textarea></label>
  <div class="review-actions">
    <button type="button" onclick="markReviewed(this)">이 판정 확정</button>
    <span class="review-status">미검토</span>
  </div>
</div>"""


def render_question_review(
    payload: Mapping[str, Any],
    question_metadata: Mapping[str, Mapping[str, str]],
    records: Mapping[str, ChunkRecord],
    *,
    export_filename: str = DEFAULT_DOWNLOAD_NAME,
) -> str:
    pages = [dict(row) for row in payload["pages"]]
    evidence_rows = [dict(row) for row in payload["evidence"]]
    recommendations = _index_unique([dict(row) for row in payload["questions"]], "question_id")
    missing = sorted(set(question_metadata) - set(recommendations))
    extras = sorted(set(recommendations) - set(question_metadata))
    if missing or extras:
        raise ValueError(f"질문 판정 범위 불일치: missing={missing}, extras={extras}")

    pages_by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    evidence_by_page: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for page in pages:
        pages_by_question[str(page["question_id"])].append(page)
    for row in evidence_rows:
        evidence_by_page[(str(row["question_id"]), normalize_url(str(row["canonical_url"])))].append(row)

    sections: list[str] = []
    for question_id in sorted(question_metadata, key=_question_sort_key):
        metadata = question_metadata[question_id]
        recommendation = recommendations[question_id]
        question_pages = pages_by_question.get(question_id, [])
        derived_support = derive_pool_support(question_pages)
        deployable_full = sum(
            row.get("support_grade") == "full"
            and row.get("temporal_validity") == "current"
            and row.get("audience_scope") == "match"
            for row in question_pages
        )
        deployable_partial = sum(
            row.get("support_grade") == "partial"
            and row.get("temporal_validity") == "current"
            and row.get("audience_scope") == "match"
            for row in question_pages
        )
        recommendation_text = BEHAVIOR_LABELS.get(
            str(recommendation.get("expected_behavior") or ""),
            str(recommendation.get("expected_behavior") or ""),
        )
        reasons = [
            str(recommendation.get("primary_reason") or ""),
            *(str(value) for value in recommendation.get("secondary_reasons", [])),
        ]
        reason_text = ", ".join(REASON_LABELS[value] for value in reasons if value)
        sections.append(
            f"""
<section class="question-card" data-question-id="{_attr(question_id)}"
 data-derived-support="{_attr(derived_support)}" data-reviewed="false">
  <h2>{_text(question_id)}. {_text(metadata['question'])}</h2>
  <div class="meta">{_text(metadata.get('category', ''))} · {_text(metadata.get('question_type', ''))}</div>
  <div class="summary">
    <span>파생 pool support: <strong>{_text(derived_support)}</strong></span>
    <span>현행·대상 일치: full {deployable_full}개 / partial {deployable_partial}개</span>
  </div>
  <div class="proposal"><strong>초벌 제안:</strong> {_text(recommendation_text)}
    {f' · {_text(reason_text)}' if reason_text else ''}</div>
  <div class="proposal-note">{_text(recommendation.get('notes', ''))}</div>
  <details class="sources">
    <summary>최종 양성 페이지와 근거 확인</summary>
    {_render_positive_pages(question_id, question_pages, evidence_by_page, records)}
  </details>
  {_render_controls(question_id, recommendation, derived_support)}
</section>"""
        )

    payload_date = str(payload.get("date") or "2026-07-14")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>qrel v4 질문 수준 전량 검토</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; line-height: 1.55; }}
body {{ margin: 0; background: #f5f6f8; color: #20242b; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 24px 18px 100px; }}
.top {{ background: white; border: 1px solid #d8dde6; border-radius: 12px; padding: 20px; }}
.sticky {{ position: sticky; top: 0; z-index: 5; display: flex; gap: 14px; align-items: center;
  padding: 12px 18px; background: #18212f; color: white; }}
.sticky button {{ margin-left: auto; }}
.question-card {{ background: white; border: 1px solid #d8dde6; border-radius: 12px;
  margin-top: 18px; padding: 20px; scroll-margin-top: 76px; }}
.question-card[data-reviewed="true"] {{ border-color: #238636; box-shadow: 0 0 0 1px #238636; }}
h1, h2, h4 {{ line-height: 1.3; }}
h2 {{ margin: 0 0 4px; font-size: 1.25rem; }}
.meta, .url, .row-id, .empty {{ color: #667085; font-size: .9rem; }}
.summary, .proposal {{ display: flex; flex-wrap: wrap; gap: 8px 20px; margin-top: 12px; }}
.proposal {{ padding: 10px 12px; border-radius: 8px; background: #eef4ff; }}
.proposal-note, .note {{ margin-top: 8px; white-space: pre-wrap; }}
.sources {{ margin-top: 14px; }}
.page-summary {{ margin-top: 12px; padding: 14px; border: 1px solid #e1e5ec; border-radius: 8px; }}
.page-summary h4 {{ margin: 0 0 8px; }}
.site {{ display: inline-block; margin-right: 8px; padding: 2px 7px; border-radius: 999px;
  background: #e8edf5; font-size: .78rem; font-weight: 600; }}
.badge {{ display: inline-block; margin-right: 5px; padding: 2px 7px; border-radius: 999px;
  background: #edf0f4; font-size: .78rem; }}
.badge-full, .badge-current, .badge-match {{ background: #dafbe1; color: #116329; }}
.badge-partial, .badge-stale, .badge-mismatch {{ background: #fff1c2; color: #7d4e00; }}
.evidence {{ margin-top: 10px; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; padding: 12px; background: #f6f8fa;
  border-radius: 6px; max-height: 420px; overflow: auto; }}
.controls {{ margin-top: 18px; padding-top: 14px; border-top: 1px solid #e1e5ec; }}
.axis {{ display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; margin: 10px 0; }}
.axis strong {{ min-width: 92px; }}
label {{ display: inline-flex; gap: 5px; align-items: center; }}
select, input[type="text"], textarea, button {{ font: inherit; }}
textarea {{ display: block; width: 100%; min-height: 76px; box-sizing: border-box; margin-top: 6px; }}
.notes {{ display: block; margin-top: 12px; }}
.composition {{ margin: 12px 0; }}
.composition label {{ display: flex; margin: 8px 0; }}
.composition input[type="text"] {{ flex: 1; }}
.review-actions {{ display: flex; gap: 12px; align-items: center; margin-top: 14px; }}
button {{ border: 0; border-radius: 7px; padding: 8px 13px; cursor: pointer; }}
.review-actions button, #export {{ background: #0969da; color: white; }}
.review-status {{ color: #9a6700; font-weight: 700; }}
.question-card[data-reviewed="true"] .review-status {{ color: #238636; }}
@media (max-width: 700px) {{ .sticky {{ flex-wrap: wrap; }} .sticky button {{ margin-left: 0; }} }}
</style>
</head>
<body data-export-name="{_attr(export_filename)}" data-judgment-date="{_attr(payload_date)}">
<div class="sticky"><strong id="progress">검토 0/{len(sections)}</strong>
  <label><input type="checkbox" id="unfinished-only" onchange="filterCards()">미검토만 보기</label>
  <button type="button" id="export" onclick="exportReview()">검토 JSON 내보내기</button></div>
<main>
<section class="top">
  <h1>qrel v4 질문 수준 전량 검토</h1>
  <p>페이지·근거 조정 뒤의 최종 양성 자료를 보고 50문항의 기대 동작과 사유를 확인합니다.</p>
  <p>초벌 제안은 작업량을 줄이기 위한 참고값이며, 각 문항의 자료를 확인한 뒤
    ‘이 판정 확정’을 눌러야 완료로 계산됩니다. 값을 바꾸면 해당 문항은 다시 미검토 상태가 됩니다.</p>
  <ul>
    <li>완전 답변: 현행·대상 일치인 full 페이지로 질문을 완전히 답할 수 있음</li>
    <li>제한을 밝힌 답변: 일부가 빠졌음을 명시하면 유용하고 오해 없는 답이 가능함</li>
    <li>답변 보류: 유용한 현행·대상 일치 근거가 없거나 핵심 결손 때문에 안전한 답이 불가능함</li>
  </ul>
</section>
{''.join(sections)}
</main>
<script>
const STORAGE_KEY = 'qrel-v4-question-review-v1';

function selectedRadio(card, field) {{
  return card.querySelector(`input[data-field="${{field}}"]:checked`)?.value || '';
}}

function checkedValues(card, field) {{
  return Array.from(card.querySelectorAll(`input[data-field="${{field}}"]:checked`))
    .map((input) => input.value);
}}

function field(card, name) {{ return card.querySelector(`[data-field="${{name}}"]`); }}

function collect(card) {{
  const override = field(card, 'composition_override').checked;
  return {{
    row_id: `Q|${{card.dataset.questionId}}`,
    question_id: card.dataset.questionId,
    judged: card.dataset.reviewed === 'true',
    expected_behavior: selectedRadio(card, 'expected_behavior'),
    primary_reason: field(card, 'primary_reason').value,
    secondary_reasons: checkedValues(card, 'secondary_reasons'),
    composition_override: override,
    pool_support: override ? field(card, 'pool_support').value : card.dataset.derivedSupport,
    composition_sources: override
      ? field(card, 'composition_sources').value.split('|').map((value) => value.trim()).filter(Boolean)
      : [],
    notes: field(card, 'notes').value.trim(),
  }};
}}

function validationError(card) {{
  const row = collect(card);
  if (!row.expected_behavior) return '기대 동작을 선택하세요.';
  if (row.expected_behavior === 'full_answer' && (row.primary_reason || row.secondary_reasons.length))
    return '완전 답변에는 사유를 두지 않습니다.';
  if (row.expected_behavior !== 'full_answer' && !row.primary_reason)
    return '제한 답변·답변 보류에는 주된 이유가 필요합니다.';
  if (row.secondary_reasons.includes(row.primary_reason)) return '주된 이유와 부차 이유가 중복됐습니다.';
  if (row.composition_override && (!row.pool_support || !row.composition_sources.length))
    return '조합 예외에는 support와 출처가 필요합니다.';
  return '';
}}

function updateProgress() {{
  const cards = Array.from(document.querySelectorAll('.question-card'));
  const reviewed = cards.filter((card) => card.dataset.reviewed === 'true').length;
  document.getElementById('progress').textContent = `검토 ${{reviewed}}/${{cards.length}}`;
}}

function markReviewed(button) {{
  const card = button.closest('.question-card');
  const error = validationError(card);
  if (error) {{ alert(error); return; }}
  card.dataset.reviewed = 'true';
  card.querySelector('.review-status').textContent = '검토 완료';
  saveState();
  updateProgress();
  filterCards();
}}

function markDirty(card) {{
  if (card.dataset.reviewed !== 'true') return;
  card.dataset.reviewed = 'false';
  card.querySelector('.review-status').textContent = '수정 후 재확인 필요';
  updateProgress();
}}

function saveState() {{
  const rows = Array.from(document.querySelectorAll('.question-card')).map(collect);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(rows));
}}

function restoreState() {{
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return;
  let rows;
  try {{ rows = JSON.parse(raw); }} catch {{ return; }}
  for (const row of rows) {{
    const card = document.querySelector(`.question-card[data-question-id="${{row.question_id}}"]`);
    if (!card) continue;
    const behavior = card.querySelector(`input[data-field="expected_behavior"][value="${{row.expected_behavior}}"]`);
    if (behavior) behavior.checked = true;
    field(card, 'primary_reason').value = row.primary_reason || '';
    card.querySelectorAll('input[data-field="secondary_reasons"]').forEach((input) => {{
      input.checked = (row.secondary_reasons || []).includes(input.value);
    }});
    field(card, 'composition_override').checked = !!row.composition_override;
    field(card, 'pool_support').value = row.pool_support || card.dataset.derivedSupport;
    field(card, 'composition_sources').value = (row.composition_sources || []).join('|');
    field(card, 'notes').value = row.notes || '';
    card.dataset.reviewed = row.judged ? 'true' : 'false';
    card.querySelector('.review-status').textContent = row.judged ? '검토 완료' : '미검토';
  }}
}}

function filterCards() {{
  const unfinishedOnly = document.getElementById('unfinished-only').checked;
  document.querySelectorAll('.question-card').forEach((card) => {{
    card.hidden = unfinishedOnly && card.dataset.reviewed === 'true';
  }});
}}

function exportReview() {{
  const cards = Array.from(document.querySelectorAll('.question-card'));
  const incomplete = cards.filter((card) => card.dataset.reviewed !== 'true');
  if (incomplete.length) {{
    alert(`미검토 문항이 ${{incomplete.length}}개 남았습니다: `
      + incomplete.slice(0, 10).map((card) => card.dataset.questionId).join(', '));
    return;
  }}
  for (const card of cards) {{
    const error = validationError(card);
    if (error) {{ alert(`${{card.dataset.questionId}}: ${{error}}`); return; }}
  }}
  const output = {{
    schema_version: 'qrel-v4-judgment-1',
    audit: false,
    judge: '저자 질문 수준 전량 검토',
    date: document.body.dataset.judgmentDate,
    exported_at: new Date().toISOString(),
    pages: [],
    evidence: [],
    questions: cards.map(collect),
  }};
  const blob = new Blob([JSON.stringify(output, null, 2)], {{type: 'application/json'}});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = document.body.dataset.exportName;
  link.click();
  URL.revokeObjectURL(link.href);
}}

document.addEventListener('DOMContentLoaded', () => {{
  restoreState();
  document.querySelectorAll('.question-card input, .question-card select, .question-card textarea')
    .forEach((control) => {{
      control.addEventListener('input', () => {{ markDirty(control.closest('.question-card')); saveState(); }});
      control.addEventListener('change', () => {{ markDirty(control.closest('.question-card')); saveState(); }});
    }});
  updateProgress();
}});
</script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="qrel v4 질문 수준 전량 검토 시트를 생성합니다.")
    parser.add_argument("--judgments", type=Path, default=DEFAULT_JUDGMENTS_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_PATH)
    parser.add_argument("--download-name", default=DEFAULT_DOWNLOAD_NAME)
    parser.add_argument("--chunk-pool", type=Path, default=CHUNK_POOL_PATH)
    parser.add_argument("--db-dsn", default=None)
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    payload = load_json(args.judgments)
    records = await load_chunk_records(
        load_csv(args.chunk_pool, CHUNK_FIELDS),
        **({"dsn": args.db_dsn} if args.db_dsn else {}),
    )
    document = render_question_review(
        payload,
        load_questions(),
        records,
        export_filename=args.download_name,
    )
    output_path = ensure_results_path(args.out)
    write_html_atomic(output_path, document)
    question_count = document.count('class="question-card"')
    print(f"저장: {output_path} (질문 {question_count}개)")


if __name__ == "__main__":
    asyncio.run(run())
