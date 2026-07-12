# 논문 준비 문서

Campus Copilot을 응용/경험/성능분석/실패분석 논문으로 정리해 한국멀티미디어학회
(KMMS)에 투고하기 위한 작업 문서 모음이다. 목표 투고일은 2026-07-31이며,
지도교수가 이 방향을 승인했다(2026-07-10).

현재 무엇이 확정이고 무엇이 남았는지는 항상
[05-scope-and-positioning.md](05-scope-and-positioning.md)가 기준이다.
특히 §7 다음 액션이 최신 우선순위다.

## 문서 안내

- [00-doc-style-guide.md](00-doc-style-guide.md) — 이 폴더의 마크다운 형식 규칙
  정본. 문서를 쓰거나 고치기 전에 먼저 읽는다.
- [01-paper-outline.md](01-paper-outline.md) — 초기의 넓은 구상. 이후 05에서
  범위를 좁혔으므로 역사 자료로만 참조.
- [02-related-work.md](02-related-work.md) — 관련 연구 조사. 인용 태그로
  검증 상태를 표시한다.
- [03-evaluation-plan.md](03-evaluation-plan.md) — 초기 평가 계획. 실제 실행된
  실험은 06이 기준.
- [04-glossary.md](04-glossary.md) — 용어집.
- [05-scope-and-positioning.md](05-scope-and-positioning.md) — 방향·기여·RQ·
  헤드라인의 확정/미결정 현황판. 갱신 시 날짜를 남긴다.
- [06-experiment-log.md](06-experiment-log.md) — 실험 기록. append-only:
  기존 항목은 고치지 않고 번복·수정은 새 항목(추기)으로 덧붙인다.
- [07-external-review-2026-07-08.md](07-external-review-2026-07-08.md) — 외부
  리뷰 1 (GPT Pro). 포지셔닝 재검증, 거절을 한계로 프레이밍.
- [08-weaknesses-and-mitigations.md](08-weaknesses-and-mitigations.md) — 심사위원
  관점 약점(W1~)과 대응 현황.
- [09-external-review-2026-07-10.md](09-external-review-2026-07-10.md) — 외부
  리뷰 2 (GPT, 저장소 열람). 실험 우선순위·qrel 재판정·헤드라인 교체 권고.
- [10-research-questions.md](10-research-questions.md) — 확정된 RQ 3개와 전체
  헤드라인. RQ↔실험↔문서 매핑.
- [11-rq1-retriever-comparison.md](11-rq1-retriever-comparison.md) — RQ1 서술
  골격 (검색기 비교, 논문 5절).
- [12-rq2-failure-analysis.md](12-rq2-failure-analysis.md) — RQ2 서술 골격
  (실패 분석, 논문 6절).
- [13-rq3-abstention-final-response.md](13-rq3-abstention-final-response.md) —
  RQ3 서술 골격 (거절·최종 응답, 논문 7절). 거절 프레이밍·용어 표준의 정본.
- [99-meeting-notes.md](99-meeting-notes.md) — 지도교수 미팅 메모.
- [guide/](guide/) — KMMS 투고 규정·체크리스트. 규정 전문과 양식 파일은
  gitignore된 로컬 참고용이며 저장소에는 요약·체크리스트만 커밋한다.

## 처음 읽는 순서

1. 05 — 지금 어디까지 왔고 무엇이 미결정인지.
2. 06 — 실험이 실제로 뭘 보여줬는지 (뒤쪽 추기까지 읽어야 최신 판정).
3. 08 — 알려진 약점과 대응 계획.
4. 09 — 가장 최근 외부 리뷰가 바꾼 것.

## 번호 체계

00은 규범, 01~09는 작업 문서(대체로 생성 순서), 99는 회의록이다. 외부 리뷰처럼
날짜가 중요한 문서는 파일명에 날짜를 넣는다. 실험 데이터와 결과 파일은
`eval/`(질문셋·gold·결과), 세션 단위 상세 기록은 `docs/sessions/`에 있다.
