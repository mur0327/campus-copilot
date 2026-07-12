"""qrel v3 블라인드 판정 시트 생성기.

insufficient 18문항에 대해 시스템이 실제 검색·사용한 문서(hybrid top-5 +
EXP-06 근거의 합집합)를 제시하고, 독립 판정자(지도교수)가 두 축을 체크하는
시트를 만든다. v2 라벨·저자 판정은 어디에도 넣지 않는다(블라인드 유지).

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
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = REPO_ROOT / "eval" / "questions.csv"
HYBRID_JSONL = REPO_ROOT / "eval" / "results" / "retrieval-hybrid-20260712-061045.jsonl"
EXP06_JSONL = REPO_ROOT / "eval" / "results" / "final-response-20260711-101912.jsonl"
OUT_PATH = REPO_ROOT / "eval" / "results" / "qrel-v3-blind-sheet.md"

TOP_N = 5
PREVIEW_CHARS = 220

PHONE_RE = re.compile(r"\b01[0-9][-.\s]?\d{3,4}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def mask_pii(text: str) -> str:
    text = PHONE_RE.sub("010-****-****", text)
    return EMAIL_RE.sub("***@***", text)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


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

    lines: list[str] = []
    lines.append("# qrel v3 블라인드 판정 시트 (18문항)")
    lines.append("")
    lines.append("판정자: ______________  판정일: ______________")
    lines.append("")
    lines.append("안내: 캠퍼스 안내 키오스크가 학생 질문에 답할 때 쓰는 문서들입니다.")
    lines.append("각 문항마다 아래 문서 목록만 근거로 두 가지를 판정해 주세요.")
    lines.append("문서 목록에 없는 지식(직접 아시는 학교 정보 포함)은 쓰지 말아 주세요.")
    lines.append("")
    lines.append("- ① 이 문서들 안에 질문의 답이 있습니까? — 있음 / 일부만 / 없음")
    lines.append("- ② 이 문서들을 근거로, 지금 키오스크 앞의 일반 학생에게 답해 줘도")
    lines.append("  됩니까? — 답변 / 거절. 거절이라면 이유에 표시해 주세요")
    lines.append("  (예: 답이 아예 없음, 옛날 공지, 특정 대상 전용, 개인 로그인 정보")
    lines.append("  필요, 기타).")
    lines.append("")
    lines.append("---")

    for question in insufficient:
        qid = question["id"]
        lines.append("")
        lines.append(f"## {qid}. {question['question']}")
        lines.append("")

        docs: list[dict] = []
        seen_urls: set[str] = set()
        hybrid_row = hybrid_by_id.get(qid)
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
        exp06_row = exp06_by_id.get(qid)
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

        for index, doc in enumerate(docs, start=1):
            path_note = f" · 메뉴: {doc['menu_path']}" if doc["menu_path"] else ""
            lines.append(f"**문서 {index}. {mask_pii(doc['title'])}**{path_note}")
            lines.append(f"<{doc['url']}>")
            if doc["preview"]:
                preview = mask_pii(doc["preview"][:PREVIEW_CHARS])
                lines.append("")
                lines.append(f"> {preview}{'…' if len(doc['preview']) > PREVIEW_CHARS else ''}")
            lines.append("")

        lines.append("① 답이 있습니까?  □ 있음  □ 일부만  □ 없음")
        lines.append("")
        lines.append("② 지금 답해도 됩니까?  □ 답변  □ 거절")
        lines.append("")
        lines.append("   거절 이유:  □ 답 없음  □ 옛날 공지  □ 특정 대상 전용")
        lines.append("   □ 개인 로그인 정보 필요  □ 기타: ______________")
        lines.append("")
        lines.append("메모: ")
        lines.append("")
        lines.append("---")

    content = "\n".join(lines) + "\n"
    remaining = PHONE_RE.search(content)
    if remaining:
        raise SystemExit(f"unmasked phone number remains near: {remaining.group()[:4]}***")
    OUT_PATH.write_text(content, encoding="utf-8")
    doc_counts = f"questions={len(insufficient)}"
    print(f"saved: {OUT_PATH} ({doc_counts})")


if __name__ == "__main__":
    main()
