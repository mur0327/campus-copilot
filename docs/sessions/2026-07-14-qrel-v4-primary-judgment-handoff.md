# qrel v4 전량 초벌 판정 — 새 세션 이관 지시서 (2026-07-14)

이 문서는 새 Claude 세션이 맥락 없이 qrel v4의 1차 초벌 판정을 시작하기 위한 지시서다.
판정 규칙의 정본은 [eval/qrel-v4-criteria.md](../../eval/qrel-v4-criteria.md)이며, 시작 전에 반드시 전문을 읽는다.
배경이 필요하면 [docs/paper/16](../paper/16-external-review-2026-07-13.md)(외부 리뷰 5·6과 v4 설계 승인), 도구 계약은 [2026-07-14-qrel-v4-codex-instructions.md](2026-07-14-qrel-v4-codex-instructions.md)를 본다.

## 1. 작업 정의

- 역할: 코드북 §8의 "1차 초벌" 판정자. LLM(Claude)이 pool 전량을 판정하고 저자는 이후 별도 감사를 한다.
- 대상: `eval/page_pool_v4.csv` 424행(support_grade·temporal_validity·audience_scope), `eval/chunk_pool_v4.csv` 626행(evidence_grade·evidence_type), 질문 50건(expected_behavior·reason).
- 출력: `eval/qrel-v4-primary-initial.json` 단일 파일.
- 판정값은 이 세션이 처음 만든다. pool CSV 자체는 수정하지 않는다.

## 2. 순서와 우선순위

- 필수분 먼저: insufficient 18문항(Q005 Q006 Q015 Q016 Q021 Q022 Q023 Q024 Q026 Q030 Q031 Q032 Q039 Q040 Q043 Q045 Q049 Q050)과 support 양성 abstain 7문항(Q005 Q006 Q016 Q023 Q031 Q039 Q040)의 행 전부.
- 그다음 answerable 나머지 문항.
- 질문 단위로 진행한다: 해당 질문의 page 행 → 그 페이지들의 chunk 행 → 질문 수준 판정 순.
- 일정이 밀려 중단해도 이미 한 판정은 유효하다(부분 pooling 서술로 낙하). 단, 채점(score_v4.py)은 세 실행 top-5가 전량 판정되기 전에는 불가능하다.

## 3. 판정 재료

- 재료는 pool에 있는 청크의 전문만이다. 재료 밖 탐색·사적 지식은 라벨에 쓰지 않고 notes로만 남긴다(코드북 원칙 3·10).
- 청크 전문은 로컬 DB에서 읽는다: `postgresql://campus:campus@localhost:5432/campus_copilot` (docker compose postgres 필요).
- 조회 SQL: `SELECT c.content FROM document_chunks c WHERE c.id = $chunk_id` 또는 URL 단위로 `JOIN documents d ON d.id = c.document_id WHERE d.url = ...`.
- 질문 텍스트는 `eval/questions.csv`의 `question` 컬럼이다.
- 컨텍스트 관리: 질문 1건 분량의 청크 전문만 스크래치패드에 덤프해 읽고, 판정을 JSON에 기록한 뒤 다음 질문으로 넘어간다. 1,050행을 한 번에 컨텍스트에 넣지 않는다.

## 4. 판정 규칙 요지 (정본은 코드북, 아래는 리마인더)

- 판정 시점은 2026-07-14 고정. 시한부 공지는 유효기간 경과 시 stale, 상시 안내·FAQ는 current.
- 축 분리: support는 내용 지지만, 시기·대상은 temporal·audience로.
- 대상자: 서브도메인은 1차 신호, 본문 내용으로 확정. match/mismatch 근거 문구를 notes에 발췌로 남긴다(발췌에 실명·연락처 인용 금지).
- 본문 기준: 본문이 이미지뿐이면 제목이 정답 같아도 invalid.
- 결정적 산술 도출은 full, 명칭 등가 추측은 금지(등가 미확인까지만 말할 수 있고, 미확인이 대상 식별에 치명적이면 abstain).
- evidence: 양성 페이지의 지지 chunk 전부에 grade를 주고, 위치 질문은 page_navigation. invalid 페이지의 chunk는 양성 없이 judged 처리.
- 질문 수준: pool_support는 파생이므로 직접 정하지 않는다(조합 예외만 composition_override). expected_behavior와 reason만 판정한다. reason은 abstain·qualified_answer에만.
- 코드북 §9의 초벌 출발값 표(Q005 Q006 Q023 Q030 Q031 Q032 Q033 Q037 Q039 Q041 Q045, Q021·Q024 재검토)를 출발점으로 반영하되, 재료를 실제로 읽고 확인한다. 특히 Q030 뷰티학과 공지는 본문 발췌 확인 후 audience를 확정한다.
- 확신이 낮거나 규칙이 갈리는 행은 notes 앞에 `경계:`를 붙인다. 이 표시가 저자 감사 대상 선정에 쓰인다.

## 5. 출력 스키마

`build_v4_qrel.py`의 `validate_judgment_payload`가 검사하는 `qrel-v4-judgment-1` 스키마를 따른다.

- 최상위: `schema_version`("qrel-v4-judgment-1"), `audit`(false), `judge`("Claude (Fable 5) 초벌"), `date`, `exported_at`, `pages[]`, `evidence[]`, `questions[]`.
- row_id 규칙: pages `P|{question_id}|{canonical_url}`, evidence `E|{question_id}|{chunk_id}`, questions `Q|{question_id}`.
- pages 행: row_id, question_id, canonical_url, judged(불리언), support_grade, temporal_validity, audience_scope, notes.
- evidence 행: row_id, question_id, canonical_url, chunk_id, judged, evidence_grade(음성이면 빈 문자열), evidence_type(음성이면 빈 문자열), notes.
- questions 행: row_id, question_id, judged, expected_behavior, primary_reason, secondary_reasons(배열), composition_override(불리언), pool_support(override일 때만), composition_sources(배열), notes.
- 시작할 때 pool CSV에서 전 행을 judged=false로 초기화한 JSON을 만들어 두고 채워가면 중단·재개가 안전하다.
- 완료 검증: 파이썬에서 `from eval.build_v4_qrel import load_json; load_json(Path("eval/qrel-v4-primary-initial.json"))`이 통과하고 judged=false가 0이어야 한다.

## 6. 완료 후 처리

- 초벌 JSON을 검증 후 즉시 커밋한다(저자 감사 전 초벌 동결 증거, 원본 보존 원칙).
- 저자 감사 대상 목록을 만든다: 모든 양성(full/partial) 행, 모든 `경계:` 행, 코드북 §9의 v3→v4 변경 행, stale·mismatch로 배포 판정이 달라지는 행, invalid 중 층화 무작위 표본 20~30쌍(모드·순위·질문 유형 섞기, 표본 추출 시드 기록).
- 감사 시트 생성: `uv run --project backend python eval/make_v4_sheet.py --audit <ids 파일>` (초벌 라벨이 표시되지 않는 블라인드 감사 모드, 출력은 eval/results/에만).
- 관리자님께 감사 분량과 예상 소요를 보고하고 시트를 전달한다.

## 7. 하지 말 것

- v2·v3 산출물, pool CSV, 동결 JSONL 수정.
- 판정 근거로 웹 검색·크롤·재료 밖 코퍼스 탐색(발견하면 notes에만).
- 예상 일치율·지표 수치를 어떤 문서에도 쓰기.
- eval/results/ 밖에 청크 전문·실명·연락처 출력.
- 감사 전에 초벌 라벨을 저자에게 요약해 보여주기(감사는 초벌을 가린 채 진행한다).

## 8. 프로젝트 상태 (2026-07-14 기준)

- 최근 커밋: `07e47e0`(v4 도구), `0e3ba41`(코드북·리뷰 16 정본), `547ef38`(v3 발행).
- 일정: 7/20 초안, 7/29 사실상 완성, 7/31 KMMS 투고. 초벌은 7/15 중 완료가 목표.
- 이후 파이프라인: 저자 감사 → adjudication → `build_v4_qrel.py` 발행(invariant 자동 게이트) → `make_v4_manifest.py` → `score_v4.py` 재채점 → EXP-07(그 전에 answer rubric 동결).
- push는 관리자님이 직접 한다.
