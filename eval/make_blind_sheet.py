"""qrel v3 블라인드 판정 시트 생성기 (단일 HTML).

insufficient 18문항에 대해 시스템이 실제 검색·사용한 문서(hybrid top-5 +
EXP-06 근거의 합집합)를 제시하고, 독립 판정자(지도교수)가 두 축을 체크하는
인쇄용 시트를 만든다. v2 라벨·저자 판정은 어디에도 넣지 않는다(블라인드 유지).

- 축 1 corpus_support: 제시된 문서 안에 질문의 답이 있는가 (있음/일부/없음)
- 축 2 deployment_answerability: 지금 키오스크 사용자에게 답해도 되는가
  (답변/거절 + 이유)

발췌의 개인 연락처(휴대전화)와 이메일은 자동 마스킹한다. 다만 게시판 글의
작성자 실명 등은 자동으로 걸러지지 않으므로, 출력 시트는 gitignore된
eval/results/에만 쓴다 — 저장소에 커밋하지 말 것(재노출 방지).
배경: docs/paper/15-external-review-2026-07-12.md 잠긴 결정 2.
"""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = REPO_ROOT / "eval" / "questions.csv"
HYBRID_JSONL = REPO_ROOT / "eval" / "results" / "retrieval-hybrid-20260712-061045.jsonl"
EXP06_JSONL = REPO_ROOT / "eval" / "results" / "final-response-20260711-101912.jsonl"
OUT_PATH = REPO_ROOT / "eval" / "results" / "qrel-v3-blind-sheet.html"

TOP_N = 5
PREVIEW_CHARS = 220

PHONE_RE = re.compile(r"\b01[0-9][-.\s]?\d{3,4}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# 판정자가 서브도메인 의미를 모르면 대상자 스코프 판정이 불가능하므로(정보
# 비대칭), 호스트네임을 사람이 읽는 출처 유형으로 표기한다. 저자 판정이 아닌
# 사실 메타데이터라 블라인드를 깨지 않는다. 학과명 오기 위험을 피해 유형
# 수준까지만 표기한다.
SITE_LABELS = {
    "www.honam.ac.kr": "대학 공식 사이트(전교 공통)",
    "enter.honam.ac.kr": "입학안내 사이트(입학처)",
    "graduate.honam.ac.kr": "대학원 사이트",
    "dorm.honam.ac.kr": "생활관(기숙사) 사이트",
    "gyoyang.honam.ac.kr": "교양·융합전공 사이트",
    "dreamlife.honam.ac.kr": "드림라이프대학(단과대학) 사이트",
}


def site_label(url: str) -> str:
    hostname = re.sub(r"^https?://", "", url).split("/")[0].lower()
    if hostname in SITE_LABELS:
        return SITE_LABELS[hostname]
    if hostname.endswith(".honam.ac.kr"):
        return "특정 학과 사이트"
    return hostname

PAGE_CSS = """
  * { box-sizing: border-box; }
  body {
    font-family: 'Pretendard', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    line-height: 1.55; color: #111; background: #fff;
    max-width: 52rem; margin: 1.5rem auto; padding: 0 1.2rem;
  }
  h1 { font-size: 1.45rem; margin: 0 0 .3rem; }
  h2 {
    font-size: 1.05rem; margin: 1.8rem 0 .4rem; padding-top: .9rem;
    border-top: 3px solid #222; break-after: avoid;
  }
  .signature { margin: .6rem 0 1rem; font-size: .95rem; }
  .signature .line {
    display: inline-block; min-width: 11rem;
    border-bottom: 1px solid #555; margin: 0 1.6rem 0 .4rem;
  }
  .guide {
    border: 1.5px solid #444; border-radius: 8px;
    padding: .8rem 1rem; font-size: .92rem; background: #fafafa;
  }
  .guide ul { margin: .5rem 0 0; padding-left: 1.2rem; }
  .doc {
    border: 1px solid #ccc; border-radius: 6px;
    padding: .55rem .8rem; margin: .5rem 0; break-inside: avoid;
  }
  .doc .title { font-weight: 600; }
  .scope {
    display: inline-block; font-size: .74rem; font-weight: 600;
    color: #1d3a5f; background: #e8eef7; border: 1px solid #9db4d0;
    border-radius: 4px; padding: 0 .45rem; margin-right: .45rem;
    vertical-align: 1px;
  }
  .doc .meta {
    font-size: .78rem; color: #555; word-break: break-all;
    font-family: ui-monospace, Consolas, monospace;
  }
  .doc .preview {
    font-size: .85rem; color: #333; background: #f6f6f6;
    border-left: 3px solid #bbb; padding: .45rem .6rem; margin-top: .4rem;
  }
  .judge {
    border: 2px solid #222; border-radius: 8px;
    padding: .7rem .95rem; margin: .7rem 0 0; break-inside: avoid;
  }
  .judge .axis { margin: .3rem 0; }
  .judge .reason { margin: .2rem 0 0 1.35rem; font-size: .95rem; }
  input[type="checkbox"] {
    width: .95rem; height: .95rem; vertical-align: -2px; margin-right: .3rem;
  }
  label { margin-right: 1.2rem; white-space: nowrap; }
  .blank {
    display: inline-block; min-width: 9rem; border-bottom: 1px solid #777;
  }
  .memo { margin-top: .5rem; font-size: .95rem; }
  .memo .row { border-bottom: 1px solid #aaa; height: 1.55rem; }
  @media print {
    body { margin: 0 auto; max-width: none; }
    .guide { background: #fff; }
  }
"""


def mask_pii(text: str) -> str:
    text = PHONE_RE.sub("010-****-****", text)
    return EMAIL_RE.sub("***@***", text)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def collect_docs(hybrid_row: dict | None, exp06_row: dict | None) -> list[dict]:
    docs: list[dict] = []
    seen_urls: set[str] = set()
    if hybrid_row:
        for item in hybrid_row["retrieved"][:TOP_N]:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            docs.append(
                {
                    "title": item.get("title") or "(제목 없음)",
                    "url": item["url"],
                    "menu_path": item.get("menu_path") or "",
                    "preview": (item.get("content_preview") or "").strip(),
                }
            )
    if exp06_row:
        for item in exp06_row.get("evidence", []):
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            docs.append(
                {
                    "title": item.get("title") or "(제목 없음)",
                    "url": item["url"],
                    "menu_path": "",
                    "preview": "",
                }
            )
    return docs


def render_doc(index: int, doc: dict) -> str:
    title = html.escape(mask_pii(doc["title"]))
    menu = html.escape(doc["menu_path"])
    url = html.escape(doc["url"])
    scope = html.escape(site_label(doc["url"]))
    parts = [
        '<div class="doc">',
        f'<div class="title"><span class="scope">{scope}</span>문서 {index}. {title}'
        + (f' <span style="font-weight:400">· 메뉴: {menu}</span>' if menu else "")
        + "</div>",
        f'<div class="meta">{url}</div>',
    ]
    if doc["preview"]:
        preview = html.escape(mask_pii(doc["preview"][:PREVIEW_CHARS]))
        ellipsis = "…" if len(doc["preview"]) > PREVIEW_CHARS else ""
        parts.append(f'<div class="preview">{preview}{ellipsis}</div>')
    parts.append("</div>")
    return "\n".join(parts)


def render_question(question: dict, docs: list[dict]) -> str:
    qid = question["id"]
    parts = [f"<h2>{qid}. {html.escape(question['question'])}</h2>"]
    parts.extend(render_doc(i, doc) for i, doc in enumerate(docs, start=1))
    parts.append(
        f"""
<div class="judge">
  <div class="axis">① 이 문서들 안에 답이 있습니까?&nbsp;&nbsp;
    <label><input type="checkbox" name="{qid}-support"> 있음</label>
    <label><input type="checkbox" name="{qid}-support"> 일부만</label>
    <label><input type="checkbox" name="{qid}-support"> 없음</label>
  </div>
  <div class="axis">② 지금 키오스크 사용자에게 답해도 됩니까?&nbsp;&nbsp;
    <label><input type="checkbox" name="{qid}-deploy"> 답변</label>
    <label><input type="checkbox" name="{qid}-deploy"> 거절</label>
  </div>
  <div class="reason">거절 이유:
    <label><input type="checkbox"> 답 없음</label>
    <label><input type="checkbox"> 옛날 공지</label>
    <label><input type="checkbox"> 특정 대상 전용</label>
    <label><input type="checkbox"> 개인 로그인 정보 필요</label>
    <label><input type="checkbox"> 기타 <span class="blank"></span></label>
  </div>
  <div class="memo">메모<div class="row"></div></div>
</div>"""
    )
    return "\n".join(parts)


def main() -> None:
    with QUESTIONS.open(newline="", encoding="utf-8") as f:
        questions = [row for row in csv.DictReader(f)]
    insufficient = [row for row in questions if row["answerability"] == "insufficient"]

    hybrid_by_id = {row["id"]: row for row in load_jsonl(HYBRID_JSONL)}
    exp06_by_id = {
        row["id"]: row
        for row in load_jsonl(EXP06_JSONL)
        if row.get("record_type") == "response"
    }

    sections = [
        render_question(q, collect_docs(hybrid_by_id.get(q["id"]), exp06_by_id.get(q["id"])))
        for q in insufficient
    ]
    body = "\n".join(sections)
    document = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>qrel v3 블라인드 판정 시트</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>qrel v3 블라인드 판정 시트 (18문항)</h1>
<div class="signature">판정자<span class="line"></span>판정일<span class="line"></span></div>
<div class="guide">
  <strong>이 판정이 필요한 이유</strong> — 논문(캠퍼스 안내 RAG 평가)의 채점
  기준이 타당한지 검증하기 위한 절차입니다. 채점 기준을 저자 혼자 판정하면
  편향될 수 있어, 독립 판정 결과와 저자 판정의 일치율을 논문에 보고합니다.
  같은 이유로 저자의 기존 판정은 이 시트에 싣지 않았습니다 — 본인의
  판단만으로 표시해 주세요. (18문항, 예상 소요 1~2시간)
  <br><br>
  <strong>판정 방법</strong> — 아래는 캠퍼스 안내 키오스크가 학생 질문에 답할
  때 쓰는 문서들입니다. 각 문항마다 제시된 문서 목록만 근거로 두 가지를
  판정해 주세요. 문서 목록에 없는 지식(직접 아시는 학교 정보 포함)은 쓰지
  말아 주세요.
  <ul>
    <li>① 이 문서들 안에 질문의 답이 있습니까? — 있음 / 일부만 / 없음</li>
    <li>② 이 문서들을 근거로, 지금 키오스크 앞의 일반 학생에게 답해 줘도
      됩니까? — 답변 / 거절. 거절이라면 이유에 표시해 주세요.</li>
  </ul>
  <br>
  각 문서 앞의 <span class="scope">출처 표기</span>는 문서가 속한 사이트를
  주소 기준으로 자동 분류한 것입니다(예: 대학원 사이트, 특정 학과 사이트,
  대학 공식 사이트). 문서 제목만으로는 출처를 알기 어려워 함께 표기했으며,
  특히 ②(누구에게 답해도 되는가)를 판단하실 때 참고해 주세요.
</div>
{body}
</body>
</html>
"""
    remaining = PHONE_RE.search(document)
    if remaining:
        raise SystemExit(f"unmasked phone number remains near: {remaining.group()[:4]}***")
    OUT_PATH.write_text(document, encoding="utf-8")
    print(f"saved: {OUT_PATH} (questions={len(insufficient)})")


if __name__ == "__main__":
    main()
