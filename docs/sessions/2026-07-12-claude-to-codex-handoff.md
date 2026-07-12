# 세션 이관 — Claude → Codex (2026-07-12 밤)

Claude 세션이 종료되어 다음 작업을 Codex가 이어받는다. 계획·결정의 정본은
리포 문서이므로 여기에는 리포에 없는 세션 지식과 다음 작업의 주의점만 남긴다.

## 읽기 순서

1. [docs/paper/15-external-review-2026-07-12.md](../paper/15-external-review-2026-07-12.md)
   — 현행 계획의 정본. 잠긴 결정 10건, qrel v3 스키마(§4), 실행 순서(§6),
   용어·수치 정본(§5).
2. [docs/paper/README.md](../paper/README.md) → 05(재정렬 딱지) → 06(뒤쪽
   추기까지) → 10~13(확정 해제 딱지 상태).
3. [docs/paper/99-meeting-notes.md](../paper/99-meeting-notes.md) — 월 미팅 안건.
4. [eval/qrel-adjudication-2026-07-11.md](../../eval/qrel-adjudication-2026-07-11.md)
   — v2 판정 기록(역사 자료, v3에서 2축으로 재해석할 원칙들).
5. CLAUDE.md — 테스트·크롤 파이프라인 명령.

## 리포에 없는 세션 지식

- 블라인드 판정 시트는 `eval/results/qrel-v3-blind-sheet.html`(gitignore됨).
  생성기는 `eval/make_blind_sheet.py`(커밋됨, 로컬 postgres 필요). 시트
  발췌에 게시판 작성자 실명이 있어 저장소 커밋·외부 공유 금지.
- 시트의 "판정 결과 내보내기" JSON 형식: `{sheet, judge, date, exported_at,
  judgments: {Qxxx: {corpus_support, deployment, reject_reasons,
  reject_reason_etc, memo}}}`. 일치율 계산 스크립트의 입력으로 설계했다 —
  Codex/저자 초벌 판정도 같은 형식으로 만들면 비교가 자동화된다.
- PII 주의: `eval/results/final-response-20260711-101912.jsonl`과
  `-20260712-061656.jsonl`에 개인 휴대전화 번호가 남아 있다. 마스킹
  스크립트는 EXP-07 단계에서 작성하기로 함(잠긴 결정 8 참조). 그 전까지
  결과 파일 외부 공유 절대 금지.
- 저자는 2026-07-12에 이해 검증을 통과했다: 4단계 사슬(회수→근거 지지→배포
  적합→거절), 판정 축 분리(①은 내용만, 시기·대상은 ②), 질문 초점 원칙
  (Q015: "어디서"를 물으면 위치 답이 정답), 블라인드가 필요한 이유(실수가
  아니라 편향, 독립 판정의 일치율 논리). 설명할 때 창고(코퍼스)·문지기
  (게이트)·채점표(qrel)·정답지 비유가 잘 통한다.
- 월 미팅(7/13) 계획: 시트 전달 + 판정 부탁(회수는 수요일까지), 쪽수
  (8 vs 9), 제목 재논의. 교수님께 개별 문항 힌트 금지(블라인드 유지).
  판정자는 교수님이 최선이지만 필수는 아님 — 개발·라벨링에 관여하지 않은
  동료·재학생도 유효.

## 다음 작업 (15 §6 순서, 마감 7/31)

1. qrel v3 50건 재판정 — 원래 "Claude 초벌 → 저자 확정" 분담이었고 이제
   초벌을 Codex가 맡는다. 원칙: (a) 질문 초점 × 문서 쌍으로 판정 (b)
   corpus_support는 내용만 보고 시기·대상은 deployment 축에서 (c) 재판정
   전 예상 수치·분모를 어떤 문서에도 쓰지 않는다 (d) v2 파일은 불변, v3는
   새 파일로 발행 (e) 문서 수준 등급(full/partial)은 graded nDCG의 전제.
2. 기존 retrieval JSONL 오프라인 재채점(primary-only 민감도, graded
   nDCG@5, MRR cutoff 명시). 후보 풀 재진단은 하지 않는다(14:2는 v2 시점
   기술통계로 역사화).
3. EXP-07: 50문항 전체 end-to-end 평가(구성 불변, raw 출력 보존, 4축 사람
   판정). PII 마스킹 스크립트는 이 단계에서.
4. 10~13·05 본문 일괄 개정 → 집필 전 무맥락 리뷰 1회 → 집필.

## 작업 규칙 (저자 선호, Claude 세션에서 확립)

- 규모 있는 변경은 구현 전에 저자 승인을 받는다.
- 커밋·마무리마다 셀프 리뷰(개인정보 잔존 점검 포함) — 이 습관으로 전화번호
  마스킹 누락과 실명 커밋을 사전에 잡았다.
- 문서 형식 정본: [docs/paper/00-doc-style-guide.md](../paper/00-doc-style-guide.md).
  06 실험 로그는 append-only(수정은 추기로).
- URL은 전체 호스트네임으로 표기한다(학과 서브도메인이 의미를 가짐 —
  graduate/dorm/enter 등, 시트의 출처 칩 매핑은 `eval/make_blind_sheet.py`
  `SITE_LABELS` 참조).

## 오늘의 커밋 (전부 main)

- `59f070a` EXP-03 재현 스크립트 복원(`eval/abstain_separation.py`), 현
  코퍼스에서 수치 전부 재현 확인(06 추기).
- `9225e88` 이전 세션분 — 관련 연구 서지 정리·제목 확정(이후 재논의로 전환).
- `f6bed4c` 외부 리뷰 4 기록(15번) + 10~13·05 딱지 + README + 99 안건.
- `7cb38af`→`3532ffd` 판정 시트 생성기 진화: 블라인드 md → 단일 HTML →
  목적 안내 → 출처 칩(정보 비대칭 해소) → 청크 전문(발췌 부족 해소) →
  축 분리 안내(Q005 예시) → JSON 내보내기·디지털 기입.
