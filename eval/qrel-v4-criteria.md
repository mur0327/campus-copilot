# qrel v4 판정 기준 (2026-07-14)

외부 리뷰 5·6([docs/paper/16](../docs/paper/16-external-review-2026-07-13.md))의 승인 조건과 B2 사람 감사 프로토콜([docs/paper/17](../docs/paper/17-qrel-v4-b2-audit-protocol.md))을 집행하는 판정 규칙이다.
v3(gold_sources_v3.csv, question_judgments_v3.csv, qrel-v3-*.md)는 불변 보존하고 v4를 새 파일로 발행한다.
판정 시작 전에 이 문서를 동결하며, 판정 중 규칙이 바뀌면 변경 내용과 시점을 §11에 기록하고 이미 판정한 행을 재검토한다.
도구 스키마는 [docs/sessions/2026-07-14-qrel-v4-codex-instructions.md](../docs/sessions/2026-07-14-qrel-v4-codex-instructions.md)와 합치해야 한다.

## 1. 판정 구조

세 계층으로 판정한다.

- page qrel(`gold_pages_v4.csv`): 질문 × canonical URL(정규화한 대표 URL) 쌍에 `support_grade`(full/partial/invalid), `temporal_validity`(current/stale/unknown), `audience_scope`(match/mismatch/unknown)를 부여한다.
- evidence qrel(`gold_evidence_v4.csv`): 양성(full/partial) 페이지의 chunk에 `evidence_grade`(full/partial)와 `evidence_type`(text_chunk/page_navigation)을 부여한다. 한 페이지에 여러 gold chunk가 있을 수 있다(1:N).
- 질문 수준(`question_judgments_v4.csv`): `pool_support`(full/partial/none)는 page 판정에서 자동 파생하고, `expected_behavior`(full_answer/qualified_answer/abstain)와 reason을 부여한다.

코퍼스 스냅샷에 없는 외부 정답 페이지는 검색 qrel에 넣지 않고 `target_sources_v4.csv`(question_id, target_url, in_corpus_snapshot, failure_reason)에 기록한다.
이 표는 acquisition failure와 코퍼스 커버리지 분석에만 쓴다.

## 2. 판정 pool

판정 대상은 다음 합집합이다.

- 세 검색 모드(bm25/semantic/hybrid)의 동결 실행(2026-07-12) top-5 qid–URL 쌍 전량
- v3 gold의 양성(full/partial) 행(seed)
- EXP-06 근거로 사용된 URL 중 양성

이 라벨의 이름은 corpus_support가 아니라 **pool_support**다.
전체 코퍼스를 감사한 것이 아니라 관찰된 실행과 기존 양성 seed를 pooled 방식으로 판정한 것이기 때문이다.
pool 밖 문서는 unjudged이며, unjudged는 invalid(판정된 비관련)와 구분한다.
현행 세 실행의 top-5에 unjudged가 남은 채로 채점하면 scorer가 실패해야 한다.

## 3. 판정 원칙

**1. 질문 초점 × 문서 쌍으로 판정한다.**

- 질문이 정확히 무엇을 묻는지(위치/내용/일정/자격)에 대해 판정한다.
- 대상자 기준은 "일반 학생"이 아니라 질문이 전제하는 사용자 집단(query-implied audience)이다. 편입 지원자·신입생·기숙사 신청자 질문은 그 집단 기준으로 match를 판정한다.

**2. 축을 분리한다.**

- pool_support는 내용 지지만 본다. 시기·대상 문제는 temporal_validity·audience_scope와 expected_behavior에서 처리한다.
- "낡은 답이 있는 질문"과 "답이 아예 없는 질문"을 구분해야 고장 위치가 보인다.

**3. 판정 재료는 pool의 청크 전문으로 고정한다.**

- 재료 밖 탐색·판정자의 사적 지식은 라벨에 반영하지 않고 노트로만 남긴다.
- 판정 시트에는 검색 mode·rank·score를 표시하지 않고 문서를 canonical 순서로 제시한다(순위 정보의 앵커링 방지).

**4. 판정 시점은 2026-07-14로 고정한다.**

- temporal_validity의 "지금"은 이 날짜 기준이다(여름방학, 2026학년도 2학기 준비 시점).

**5. 대상자 스코프는 서브도메인을 1차 신호로, 본문 내용으로 확정한다.**

- 학과·대학원 서브도메인 문서라도 본문에서 내용이 전교 공통임이 확인되면 match다.
- "국가 제도니까 누구에게나 적용된다" 같은 외부 지식만으로 match를 주지 않는다.
- match/mismatch 판단의 근거가 된 본문 문구를 notes에 발췌로 남긴다(Q030 뷰티학과 공지가 시험 사례).

**6. 시한부 공지는 유효기간 경과 시 stale이다.**

- 2026-2학기 신청 공지는 판정 시점에 기간 전이므로 current, 2025-2학기 공지는 stale이다.
- 상시 안내·FAQ는 current다.
- "시스템이 지금도 그렇다"는 사적 지식은 시효 근거로 쓰지 않는다.
- 한 문서에 만료된 날짜와 지속되는 경로 안내가 공존하면 문서 등급은 지배적 성격으로 판정하고 notes에 구분을 남긴다.

**7. 개인 포털 로그인이 있어야만 답이 되는 질문은 abstain(personalized)이다.**

- 공개 안내 페이지로 절차·확인 경로를 답할 수 있으면 personalized가 아니다.

**8. 제목이 아니라 본문으로 판정한다.**

- 본문이 이미지뿐이고 제시 텍스트가 질문을 지지하지 않으면 제목이 정답처럼 보여도 invalid다(Q030 공식 공지 5254가 시험 사례).

**9. 명시된 전제에서의 결정적 도출은 full이다.**

- 기준 18/19학점 + 우수 시 3학점 추가 명시에서 최대 21/22를 계산하는 것은 추측이 아니라 결정적 산술이므로 full 지지다(Q033).
- 서로 다른 문서 두 개를 조합해야만 완전해지는 답은 질문 수준에서 composition_override로 처리한다(§6).

**10. 명칭 등가성은 재료 안의 근거로만 판정한다.**

- 질문의 서류명·용어와 재료의 것이 다르면, 재료에 등가 근거가 없는 한 full이 아니다(최대 partial).
- "사실상 같은 서류다"도 "엄연히 다른 서류다"도 재료 밖 단정이므로 금지한다. 재료 기준 판정은 "등가성 미확인"까지다.
- 등가성 미확인이 답의 대상 식별에 치명적이면 expected_behavior는 abstain이다(Q006이 시험 사례).

**11. 미러 문서는 본문 signature로 support만 이어받는다.**

- 본문이 동일한 학과 미러는 support_grade를 공유할 수 있으나 temporal_validity·audience_scope는 URL별로 따로 판정한다(복사 금지).

**12. 중복 문항(Q011=Q035)은 각각 독립 판정한다.**

- 질문셋은 기존 실험과의 비교 가능성을 위해 불변으로 둔다.
- 논문에는 중복 사실만 중립적으로 기술하고, 채점은 포함본과 제거본(49문항)을 병기한다.

## 4. expected_behavior 결정표

| 값 | 기준 |
| --- | --- |
| full_answer | current+match인 full 근거로 질문 초점을 완전히 답할 수 있다 |
| qualified_answer | current+match인 partial 근거(또는 제한적으로 쓸 수 있는 full 근거)로, 빠진 부분을 명시한 유용하고 오해 없는 제한 답변이 가능하다 |
| abstain | 유용한 current+match 근거가 없거나, 빠진 부분이 대상 식별·정확성에 치명적이다 |

허용 조합(정합성 자동 검사, invariant):

- full_answer는 current+match full 문서를 요구한다.
- abstain(stale)은 current+match 대체 근거가 없을 때만, abstain(audience_mismatch)은 match 대체 근거가 없을 때만 가능하다.
- deployable full 근거가 있는데 abstain이면 원칙적으로 오류이며, 예외는 명시적 policy_exclusion으로만 허용한다.

## 5. reason

enum: acquisition_failure / absent / missing_required_claim / stale / audience_mismatch / personalized / policy_exclusion.

- missing_required_claim(신설): 관련 근거는 있으나 답에 필요한 핵심 claim(명칭 등가, 구체 기간 등)이 재료에 없다. pool_support=partial과 공존 가능하며, v3의 "partial인데 absent" 모순을 대체한다.
- absent: 질문 초점에 대한 근거 자체가 pool에 없다(pool_support=none과 짝).
- acquisition_failure: 정답 출처가 크롤 범위 밖이거나 수집·파싱 실패로 코퍼스에 없다(Q045 library 도메인, Q039 PDF 미파싱).
- primary_reason은 단일값, secondary_reasons는 다중값이다.
- primary 선정 우선순위: acquisition_failure > absent·missing_required_claim > stale·audience_mismatch > personalized > policy_exclusion.
- personalized는 개인 값을 직접 답해야만 하는 질문에만 쓰고, 확인 경로를 묻는 질문에는 쓰지 않는다.
- reason은 expected_behavior가 abstain 또는 qualified_answer일 때만 기록한다(qualified_answer의 reason은 제한 답변에서 명시할 빠진 부분이다). full_answer에는 reason을 두지 않는다.
- 실패 유형 분포는 primary 기준과 any-occurrence 기준(등장한 모든 reason을 세는 방식) 두 벌로 보고한다.

## 6. 질문 라벨 파생

pool_support는 page 판정에서 자동 파생한다(수기 동결 금지).

- full 문서가 1개 이상이면 full, 아니면 partial이 1개 이상이면 partial, 아니면 none.
- 두 partial 문서를 조합해야만 완전한 답이 되는 경우만 composition_override=true로 명시하고 composition_sources와 근거를 기록한다.

## 7. evidence 판정

- 양성 페이지에는 실제로 질문을 지지하는 모든 chunk를 gold로 지정한다(chunk_id + content_hash 보존).
- invalid 페이지에는 gold chunk를 지정하지 않는다.
- 위치 질문(Q015류)처럼 페이지 도달 자체가 답이면 evidence_type=page_navigation으로 표시하고, 이 문항은 evidence 지표의 분모에서 제외한다.
- 양성 페이지에서 top-5에 반환된 다른 chunk는 지지 여부만 확인한다(전 chunk 전수 판정은 하지 않는다).

## 8. 판정 절차

- 1차 초벌: LLM이 이 코드북으로 pool 전량을 판정한다. 필수분(insufficient 18문항의 3모드 합집합 + support 양성 abstain 7문항의 문서 행)을 먼저 끝낸다. 실제 판정자·모델 분담은 primary JSON의 judge 필드에 보존한다.
- 2차 감사 단위는 개별 행이 아니라 질문–페이지 묶음이다. 묶음을 고르면 페이지 축과 해당 evidence candidate를 같은 자료 읽기에서 함께 판정한다.
- 표적 감사는 v3→v4 페이지 변경, `경계:` 표시, temporal·audience가 expected behavior에 영향을 주는 사례, 충돌, invariant 후보, composition 근거, §9의 사전 쟁점 페이지를 전량 포함한다.
- 나머지에서는 LLM-positive와 LLM-invalid 묶음을 모두 고정 시드 층화 표본으로 뽑는다. 주요 층은 순위(1–2/3–5/seed), 모드 출현(단일/복수/seed), 문서 성격(일반/특수)이며 질문 유형과 출처 범위를 보조 조건으로 맞춘다.
- 최종 표본 수는 초기 라벨과 선정 사유를 숨긴 10묶음 시간 파일럿의 중앙 시간을 잰 뒤, 불일치를 열기 전에 3~5시간 예산에 맞춰 동결한다. 파일럿 묶음은 최종 표본에 포함한다.
- 시간 측정이 누락되고 축 설명의 사용성 문제가 확인된 첫 10묶음은 공식 파일럿과 층화 표본 결과에서 제외한다. 일부 초벌 대조가 공개됐으므로 같은 묶음을 다시 쓰지 않고, 첫 묶음을 제외한 고정 시드 재파일럿 10묶음으로 교체한다.
- 사람 검토자는 LLM 초기 라벨, 선정 사유, mode·rank·score와 v3 판정을 보지 않는다. 완전한 독립 블라인드가 아니라 초기 라벨 비공개 사람 감사로 기술한다.
- 중대한 불일치는 support grade, temporal validity, audience scope, evidence 지지 또는 expected behavior가 바뀌는 경우다. 같은 사전 정의 유형에서 2건 이상이거나 1건의 체계적 코드북 오적용이면 해당 유형을 확대한다. 독립 유형 여러 곳이면 같은 크기의 표본을 추가하고, 전역 오류일 때만 후보 전량 감사를 검토한다.
- page·evidence 불일치 조정 뒤 expected behavior와 reason은 50문항 전량을 사람이 검토한다. pool_support는 최종 page qrel에서 자동 파생한다.
- 충돌·조합 표적 묶음은 같은 질문의 관련 페이지를 라벨 없는 비교 문맥으로 함께 제시하되, 비교 문맥에는 판정 컨트롤을 두지 않는다.
- 불일치는 조정(adjudication) 기록을 남기고 최종 결정권은 저자에게 있다.
- 표적 감사와 층화 표본 감사는 분리해 보고한다. 둘을 합친 일치율이나 κ를 신뢰도로 보고하지 않고 변경 건수, 대표 오류 유형, 확대 여부를 기술한다.
- 초벌 qrel과 감사 후 qrel의 지표·검색 방식 순위·헤드라인 결론을 비교하고, 결과가 바뀌면 영향을 준 유형을 확대한다.
- 원본 계보: `qrel-v4-primary-initial.json`(초벌 전량), `qrel-v4-secondary-audit.json`(감사 행만), `qrel-v4-adjudicated.json`(최종), `qrel-v4-manifest.sha256`. v3 교수 판정 JSON은 v4 계보에 넣지 않는다(역사 자료).
- 세부 선정·확대·보고 규칙과 논문 서술은 [docs/paper/17](../docs/paper/17-qrel-v4-b2-audit-protocol.md)을 따른다.

## 9. 초벌 출발값 (v3 대비 사전 확정 변경, 2026-07-14 저자 승인)

아래는 초벌의 출발값이며, 최종 질문 라벨은 §6의 파생으로만 확정된다.

| 대상 | v3 | v4 출발값 | 근거 |
| --- | --- | --- | --- |
| Q005 | partial / abstain(absent) | full / abstain, primary stale | 내용은 공지에 있음(원칙 2), 지지 문서가 시한부 공지뿐(원칙 6) |
| Q006 | partial / abstain(absent, stale) | partial / abstain, primary missing_required_claim | stale은 사실과 다름, 명칭 등가 미확인(원칙 10) |
| Q031 | partial / abstain(audience_mismatch) | full / abstain(audience_mismatch) | Q016과 동일한 축 분리(원칙 2) |
| Q032 | partial / answer | full / full_answer | 상시 FAQ가 확인 경로를 직접 지지, 문서 행과 정합 |
| Q033 학점인정 문서 행 | partial | full | 결정적 산술 도출(원칙 9) |
| Q030 공식 5254 행 | partial | invalid | 본문 이미지뿐(원칙 8) |
| Q030 뷰티학과 공지 행 | full/current/match | 본문 발췌 확인 후 확정 | 원칙 5. 전교 공통 문구가 없으면 mismatch로 내려가고 질문 수준이 연쇄 재검토됨 |
| Q037 드림라이프 FAQ 행 | partial | invalid + 충돌 notes | 공식 안내와 모순되는 문서에 양의 게인 금지 |
| Q023 | partial / abstain(absent) | partial / abstain, primary missing_required_claim | partial+absent 모순 해소(§5) |
| Q041 계절학기 행 | partial | partial 유지(예시 고정) | 구체 기간이 없는 관련 안내는 일정 질문에 partial |
| Q045 | reason absent | reason acquisition_failure | library 도메인 크롤 범위 밖(실행 기록 근거) |
| Q039 | acquisition_failure | 유지 + secondary stale | 복합 원인 병기 |
| Q021 | none / abstain(personalized) | 초벌에서 재검토 | 확인 경로를 묻는 질문이라 personalized 부적합(§5), absent 후보 |
| Q024 | none / abstain(absent) | 초벌에서 재검토 | 규정·PDF가 수집 실패로 없는 것이면 acquisition_failure |

## 10. 채점 계약

- page 지표: PageHit_full@5, PageHit_any@5, nDCG_support@5(gain full=2, partial=1, invalid=0), nDCG_deployable@5(current+match인 full/partial만 2/1, 그 외 0).
- unjudged는 gain으로 변환하지 않는다. 현행 세 실행의 top-5에 unjudged가 있으면 채점 자체가 중단된다(§2).
- evidence 지표: EvidenceHit_full@5, EvidenceHit_any@5(분모는 text_chunk 필요 문항, N 명시).
- 같은 canonical URL의 두 번째 이후 등장은 page 지표에서 gain 0이다.
- 모든 지표에 분모 N을 명시하고, Q011/Q035 포함본과 제거본을 병기한다.
- Recall이라는 이름을 쓰면 방법 절에 question-level success rate로 정의한다.
- 채점 전 invariant 12종(도구 지시서 §check_v4_invariants) 통과가 발행 조건이다.

## 11. 변경 기록

- 2026-07-14: 최초 동결.
- 2026-07-14: 사람 감사 시작 전 B2 프로토콜로 변경. 모든 양성 전량 감사 대신 사전 정의 고위험 묶음 전량 + 나머지 양성·음성 층화 표본 + 질문 행동 50문항 전량 검토로 동결했다. 초기 라벨 비공개 10묶음 시간 파일럿과 유형별 확대 규칙을 추가했다.
- 2026-07-14: 첫 시간 파일럿에서 타이머 미사용과 축 설명의 사용성 문제를 확인했다. 첫 10묶음을 공식 표본에서 제외하고, 기존 코드북의 축 정의를 보강한 시트와 겹치지 않는 고정 시드 재파일럿으로 교체했다. 판정 규칙 자체는 바꾸지 않았다.
- 2026-07-14: 공식 재파일럿의 중앙 시간 17초와 조정 비용을 함께 고려해 비표적 층화 표본을 20묶음으로 동결했다. 표적 67묶음과 합친 최종 범위는 87묶음이며 완료 15묶음을 제외한 남은 판정량은 72묶음이다. 충돌·조합 사례의 비교 문맥 표시를 추가했다.

## 12. 산출물

- `eval/gold_pages_v4.csv`, `eval/gold_evidence_v4.csv`, `eval/question_judgments_v4.csv`, `eval/target_sources_v4.csv`
- `eval/qrel-v4-primary-initial.json`, `eval/qrel-v4-secondary-audit.json`, `eval/qrel-v4-adjudicated.json`, `eval/qrel-v4-manifest.sha256`
- 감사 선정 도구: `eval/select_v4_audit.py`(고정 시드·질문–페이지 묶음)
- 재채점 결과: `eval/results/scores-v4-*.json`
