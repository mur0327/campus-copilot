# qrel v4 도구 구현 지시서 (Codex)

## 배경

Campus Copilot의 RAG 평가용 채점표(qrel)를 v3에서 v4로 재구축한다.
외부 리뷰가 v3의 기초 결함을 지적했다: 판정 pool이 hybrid 결과에 편향됐고, 문서 qrel에 abstain 문항의 행이 없고, scorer가 URL 수준이라 엉뚱한 chunk도 정답으로 센다.
v4는 세 검색 모드(bm25/semantic/hybrid)의 top-5 합집합 + 기존 양성 gold를 pooled 방식으로 전량 판정하고, page 계층과 evidence(chunk) 계층을 분리해 채점한다.

Codex의 담당은 **도구 구현만**이다.
판정값(라벨)은 저자 측이 별도로 채운다.

배경 문서(참고용, 수정 금지):

- [eval/qrel-v3-criteria.md](../../eval/qrel-v3-criteria.md): v3 판정 원칙
- [eval/qrel-v3-adjudication-2026-07-13.md](../../eval/qrel-v3-adjudication-2026-07-13.md): v3 판정 기록
- [eval/make_blind_sheet.py](../../eval/make_blind_sheet.py): v3 판정 시트 생성기(재사용 대상)
- [eval/run_questions.py](../../eval/run_questions.py): URL 정규화·기존 scorer(참고만, v4에서 재사용 금지 항목 있음)
- `eval/qrel-v4-criteria.md`: v4 코드북(작성 예정). 스키마가 어긋나면 본 지시서가 우선한다.

## 작업 범위

할 것:

- 아래 스크립트 6개를 `eval/`에 신규 작성

하지 말 것:

- 판정값 채우기(support_grade 등은 전부 빈 값 또는 unjudged로 생성)
- v2·v3 산출물 수정(`gold_sources.csv`, `gold_sources_v3.csv`, `question_judgments_v3.csv`, `qrel-v3-*.md`, `qrel-v3-judgment-*.json`은 불변)
- 검색 재실행(입력 JSONL은 동결본)
- `eval/results/` 밖에 문서 본문 전문·연락처·작성자 실명 출력

## 입력 데이터 (동결본, 수정 금지)

- `eval/results/retrieval-bm25-20260712-061017.jsonl`
- `eval/results/retrieval-semantic-20260712-061027.jsonl`
- `eval/results/retrieval-hybrid-20260712-061045.jsonl`
- `eval/results/final-response-20260711-101912.jsonl`: EXP-06 근거 seed. 근거 항목에 chunk_id가 없으면 URL 수준 seed로만 사용한다.
- `eval/results/retrieval-20260705-094816.jsonl`: 위 EXP-06 실행의 원천 retrieval 로그. EXP-06 근거의 chunk 수준 복구에 사용할 수 있다. 단 7/5 스냅샷이라 7/12 동결 실행과 chunk_id가 다를 수 있으므로 대조는 content_sig 기준으로 하고, 대조 실패 시 URL 수준 seed로 강등한다.
- `eval/gold_sources_v3.csv`: v3 양성 gold(seed)
- `eval/questions.csv`: 50문항

retrieval JSONL 레코드 구조: 최상위 `id`(=question_id), `retrieved` 리스트의 각 항목에 `rank`, `score`, `chunk_id`, `document_id`, `title`, `url`, `menu_path`, `source_scope`, `page_kind`, `content_preview`, `content_sig`가 있다.
JSONL 안의 `gold_rank`, `answerability` 등 v2 파생 필드는 **신뢰하지 말고 무시**한다.

청크 전문은 로컬 DB에서 읽는다: `postgresql://campus:campus@localhost:5432/campus_copilot` (docker compose postgres 필요, asyncpg 사용, make_blind_sheet.py 참고).

## 산출 파일 스키마

**1. eval/page_pool_v4.csv (page 판정 대상)**

- 컬럼: `question_id`, `canonical_url`, `provenance`, `judged`, `support_grade`, `temporal_validity`, `audience_scope`, `notes`
- provenance: `top5` | `seed_v3` | `exp06` (복수면 `|`로 연결)
- 생성 시 judged=false, 판정 컬럼은 빈 값

**2. eval/chunk_pool_v4.csv (evidence 판정 대상)**

- 컬럼: `question_id`, `canonical_url`, `chunk_id`, `content_hash`, `judged`, `evidence_grade`, `evidence_type`, `notes`
- content_hash는 retrieval JSONL의 `content_sig`를 그대로 사용

**3. eval/target_sources_v4.csv (코퍼스 밖 정답, 검색 qrel과 분리)**

- 컬럼: `question_id`, `target_url`, `in_corpus_snapshot`, `failure_reason`, `notes`
- 스켈레톤만 생성(행 추가는 저자 측)

**4. eval/gold_pages_v4.csv, eval/gold_evidence_v4.csv (발행본)**

- pool CSV와 동일 컬럼 + 판정 완료 상태
- adjudicated JSON을 병합해 생성

**5. eval/question_judgments_v4.csv (질문 수준, 파생)**

- 컬럼: `question_id`, `pool_support`, `expected_behavior`, `primary_reason`, `secondary_reasons`, `composition_override`, `composition_sources`, `notes`
- secondary_reasons는 `|` 구분 다중값

**6. 판정 원본 JSON 계보 (eval/에 커밋)**

- `qrel-v4-primary-initial.json`: 1차 초벌 전량
- `qrel-v4-secondary-audit.json`: 2차 감사 대상 행만
- `qrel-v4-adjudicated.json`: 최종 확정
- 세 JSON의 내부 구조는 판정 시트의 내보내기 형식과 동일하게 Codex가 정의하되, 세 파일이 같은 스키마를 쓰고 build_v4_qrel.py가 유일한 소비자여야 한다
- v3 교수 판정 JSON은 v4 계보에 포함하지 않는다(역사 자료)

## enum 정의

- `support_grade`: full / partial / invalid
- `temporal_validity`: current / stale / unknown
- `audience_scope`: match / mismatch / unknown
- `evidence_grade`: full / partial
- `evidence_type`: text_chunk / page_navigation
- `pool_support`: full / partial / none
- `expected_behavior`: full_answer / qualified_answer / abstain
- `reason`: acquisition_failure / absent / missing_required_claim / stale / audience_mismatch / personalized / policy_exclusion
- reason 우선순위(primary 선정용): acquisition_failure > absent·missing_required_claim > stale·audience_mismatch > personalized > policy_exclusion

## 구현할 스크립트

**1. eval/make_v4_pool.py**

- 세 retrieval JSONL의 문항별 top-5를 합집합으로 모아 page pool을 만든다.
- URL 정규화는 run_questions.py의 `normalize_url`을 재사용한다.
- gold_sources_v3.csv의 양성 행(support_grade가 full/partial인 행)과 EXP-06 근거 URL을 seed로 합친다.
- top-5에 등장한 모든 chunk(qid × chunk_id)로 chunk pool을 만든다.
- seed 페이지가 top-5 밖이라 chunk가 JSONL에 없으면 DB에서 해당 URL의 chunk를 로드해 후보로 추가한다.
- 실행 로그에 검증 수치를 출력한다: 18개 insufficient 문항의 top-5 합집합은 156쌍, 50문항 전체는 414쌍(고유 207 URL)이어야 한다. insufficient 문항 ID는 Q005 Q006 Q015 Q016 Q021 Q022 Q023 Q024 Q026 Q030 Q031 Q032 Q039 Q040 Q043 Q045 Q049 Q050이다.

**2. eval/make_v4_sheet.py**

- make_blind_sheet.py를 기반으로 판정 시트(단일 HTML)를 생성한다: DB 청크 전문(1500자), 전화·이메일 자동 마스킹 + 생성 시 마스킹 검증, 출처 칩(서브도메인 매핑), 판정 JSON 내보내기 버튼.
- v4 요건: mode·rank·score를 시트에 표시하지 않고, 문서 순서는 canonical_url 정렬로 제시한다(순위 정보가 판정에 영향을 주지 않게).
- `--audit ids.txt` 모드: 지정한 행만 싣고 기존 초벌 라벨을 표시하지 않는다(2차 감사용).
- 출력은 `eval/results/`에만 쓴다(게시판 작성자 실명 재노출 방지, 커밋 금지).

**3. eval/build_v4_qrel.py**

- adjudicated JSON을 pool CSV에 병합해 gold_pages_v4.csv, gold_evidence_v4.csv를 발행한다.
- 질문 수준 pool_support를 자동 파생한다: full 문서 1개 이상이면 full, 아니면 partial 1개 이상이면 partial, 아니면 none.
- composition_override=true인 문항은 파생 대신 명시값을 쓰고 composition_sources를 기록한다.
- expected_behavior·reason은 adjudicated JSON의 질문 수준 항목에서 병합한다.
- 발행 전 check_v4_invariants를 호출해 실패하면 발행하지 않는다.

**4. eval/check_v4_invariants.py**

- 아래 검사를 전부 수행하고 하나라도 실패하면 exit 1 + 실패 행 목록 출력.

1. 세 실행 top-5의 모든 qid–URL 쌍이 judged 상태다.
2. 세 실행 top-5의 모든 qid–chunk 쌍이 evidence 판정 상태를 가진다.
3. 질문 pool_support가 page qrel의 최대 등급과 일치한다(composition_override 예외).
4. full/partial 페이지는 gold evidence가 1개 이상이다(evidence_type=page_navigation이면 면제).
5. invalid 페이지에는 gold evidence가 없다.
6. gold chunk의 content_hash가 해당 URL의 실제 chunk와 일치한다.
7. expected_behavior=full_answer인 질문은 current+match인 full 문서를 가진다.
8. abstain(stale)은 current+match 대체 근거가 없을 때만 허용한다.
9. abstain(audience_mismatch)은 match 대체 근거가 없을 때만 허용한다.
10. unjudged 행이 채점에 섞이지 않는다(발견 시 실패).
11. reason 값이 enum과 precedence 규칙에 맞는다(primary 단일, expected_behavior가 abstain 또는 qualified_answer가 아닌데 reason이 있으면 실패, full_answer는 reason 빈 값).
12. 중복 문항 쌍(Q011=Q035)이 둘 다 존재하고 독립 판정돼 있다.

**5. eval/score_v4.py**

- 세 retrieval JSONL을 v4 qrel과 오프라인 join해 재채점한다(JSONL 내 v2 파생 필드 무시).
- page 지표: `PageHit_full@5`, `PageHit_any@5`, `nDCG_support@5`(gain full=2, partial=1, invalid=0), `nDCG_deployable@5`(current+match인 full/partial만 2/1, 그 외 0).
- evidence 지표: `EvidenceHit_full@5`, `EvidenceHit_any@5`.
- evidence 지표의 분모는 text_chunk 근거가 필요한 문항만으로 하고 N을 결과에 명시한다(page_navigation 문항은 page 지표만).
- 같은 canonical URL의 두 번째 이후 등장은 page 지표에서 gain 0으로 처리한다.
- 세 실행 top-5에 unjudged 쌍이 하나라도 있으면 assert로 중단한다(조용한 결과 생성 금지).
- 모든 지표를 Q011/Q035 포함본과 제거본(49문항) 두 벌로 산출한다.
- 지표별 분모 N을 함께 출력하고, 결과는 `eval/results/scores-v4-<timestamp>.json`과 요약 CSV로 저장한다.

**6. eval/make_v4_manifest.py**

- SHA-256 manifest(`eval/qrel-v4-manifest.sha256`)를 생성한다.
- 대상: v4 코드북 문서, questions.csv, 세 retrieval JSONL, pool CSV 2개, 발행 CSV 3개, target_sources_v4.csv, 판정 JSON 3개, score_v4.py 소스.

## 개발 규칙

- 실행 방식은 기존 관례를 따른다: DB가 필요한 스크립트는 `uv run --project backend python eval/xxx.py`, 순수 파일 처리는 `python3 eval/xxx.py`.
- 파생 규칙·invariant·지표 계산은 순수 함수로 분리하고 pytest 단위 테스트를 붙인다(nDCG 손계산 대조, URL 중복 gain 0, unjudged assert, composition_override, invariant 실패 케이스 각 1개 이상).
- `uv run --project backend ruff check eval` 통과.
- 문서·주석·로그는 한국어, 기존 eval 스크립트의 docstring 스타일을 따른다.

## 수용 기준

- make_v4_pool.py 실행 로그의 합집합 수치가 위 기대값(156, 414, 207)과 일치한다.
- 판정 컬럼이 빈 pool로 score_v4.py를 돌리면 unjudged assert로 실패한다(음성 테스트).
- 시트 HTML에 mode·rank·score 문자열이 없고, 마스킹 검증을 통과한다.
- pytest와 ruff가 통과한다.
