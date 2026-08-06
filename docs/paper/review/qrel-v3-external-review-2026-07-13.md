# qrel v3 무맥락 외부 리뷰 — 2026-07-13

대상 커밋: `547ef38877ab2f71a743c54aced7aee3fc4426b5`

## 결론

qrel v3는 집계·버전 보존·축 분리의 방향은 맞지만, 현재 상태로 graded nDCG/Recall 재채점과 EXP-07의 기초로 사용하면 안 된다. 특히 다음 세 문제가 기초를 흔든다.

1. `gold_sources_v3.csv`가 35개 `answer` 문항의 양의 gold만 담고, `corpus_support`가 full/partial인데 deployment가 abstain인 7문항(Q005, Q006, Q016, Q023, Q031, Q039, Q040)의 문서 판정을 전부 누락했다. 따라서 문서 수준에서 support와 deployment 축이 다시 합쳐졌다.
2. `corpus_support`는 전체 코퍼스가 아니라 hybrid top-5 + EXP-06 evidence로 조건화된 evidence-pool support다. 첨부된 세 검색기 top-5 합집합 156 qid-URL 쌍 중 시트에 제시된 것은 90쌍뿐이며, 66쌍(42.3%)이 누락됐다. 18문항 중 17문항에서 다른 모드 후보가 빠졌다.
3. 시스템은 chunk를 순위화하지만 시트와 기존 scorer는 URL 단위로 합친다. 같은 URL의 무관 chunk가 먼저 나오면 정답 hit로 계산된다.

v3는 동결 상태로 보존하고, 수정은 v4로 발행하는 편이 맞다.

## 재계산 결과

- `question_judgments_v3.csv`: 50행, full 36 / partial 6 / none 8, answer 35 / abstain 15 — 기록과 일치.
- `gold_sources_v3.csv`: 55행, full 39 / partial 15 / invalid 1, current 54 / stale 1, match 54 / mismatch 1 — 기록과 일치.
- 저자 확정본 대 지도교수: support 10/18, Cohen's κ=0.3043478261; deployment 13/18, κ=0.3283582090 — 기록의 0.30/0.33과 일치.
- Claude 초벌 대 지도교수 deployment: 14/18, κ=0.5324675325 — 기록과 일치.
- 첨부 시트: 18문항, 92 qid-URL 쌍.
- 세 검색기 top-5 합집합(18문항): 156 qid-URL 쌍; 시트와 겹침 90; 누락 66(42.3%); 17/18문항에 누락 존재.
- 첨부 ZIP에는 retrieval JSONL 3개만 있다. `final-response-20260711-101912.jsonl:1`이 원천으로 지정한 `eval/results/retrieval-20260705-094816.jsonl`은 첨부되지 않았다.

## 치명

### C1. 50문항 qrel이라고 했지만 문서 수준 qrel은 35개 answer 문항만 존재한다

`question_judgments_v3.csv`에서 Q005, Q006, Q016, Q023, Q031, Q039, Q040은 support가 full/partial이면서 deployment가 abstain이다. 그러나 `gold_sources_v3.csv`에는 이 7문항의 행이 하나도 없다. 그 결과 stale/mismatch evidence를 retrieval support로는 양성, deployment로는 음성으로 다루는 것이 불가능하다.

이 누락 때문에 55행의 temporal/audience 분포가 stale 1, mismatch 1에 불과하다. 실제 질문 수준에는 stale(Q040), audience mismatch(Q016/Q031), acquisition failure(Q039) 등 양의 support를 가진 비배포 문항이 더 있다.

수정: 모든 pooled candidate에 `support_grade`, `temporal_validity`, `audience_scope`, `judged`를 부여하고, 두 평가용 gain을 파생한다.

- support gain: full=2, partial=1, invalid=0
- deployable gain: current+match인 full/partial만 2/1, 나머지 0

### C2. `corpus_support`가 hybrid-conditioned pool support다

`qrel-v3-criteria.md` 원칙 3과 `make_blind_sheet.py`는 hybrid top-5와 EXP-06 evidence만 시트에 싣는다. 첨부 세 모드 top-5 합집합 기준으로 156쌍 중 66쌍이 빠졌다. 이는 BM25/dense/hybrid를 비교할 qrel을 hybrid 결과로 주로 발굴한 셈이다.

구체 사례:

- Q043: semantic top-4의 캠퍼스맵은 학생처가 상지관(3호관)에 있음을 제공하지만 시트에서 빠졌다 (`retrieval-semantic-20260712-061027.jsonl:43`; 시트 Q043은 `qrel-v3-blind-sheet.html:1143-1209`).
- Q024: semantic 단독의 출석인정 관련 자료들이 시트에서 빠졌다 (`retrieval-semantic-20260712-061027.jsonl:24`).
- Q045: library 도메인이 크롤 범위 밖이라는 사실은 acquisition failure인데, top-5 제시물만 보고 corpus none/absent로 굳었다.

수정: 최소한 세 시스템 top-k 합집합을 pool로 만들고, `corpus_support`를 계속 쓰려면 별도의 corpus audit를 해야 한다. 현재 자료만 유지할 경우 필드명은 `presented_evidence_support` 또는 `pool_support`가 정확하다.

### C3. 공개 라벨이 원칙 2를 직접 위반한다

- Q005: 시트 본문은 납부기간 및 고지서 확인을 명시한다 (`qrel-v3-blind-sheet.html:113-166`). 그런데 낡은 공지라는 이유로 support까지 partial로 내리고 reason을 absent로 기록했다. 시효는 축 ②에서 처리한다는 원칙 2와 정면 충돌한다. 현재 원칙을 그대로 쓰면 최소 `full/abstain(stale)`이고, claim-level temporal rule을 채택하면 `full/answer`가 가능하다. `partial/abstain(absent)`는 성립하지 않는다.
- Q031: 대학원 학사일정이 “분할납부 신청기간”을 명시한다 (`qrel-v3-blind-sheet.html:811-855`). 원칙 2처럼 대상자를 축 ②로 보내면 ①은 full, ②는 abstain(audience mismatch)여야 한다. 현재 partial은 Q016에서 적용한 순수 축 분리와 불일치한다.
- Q032: 질문 CSV는 partial/answer인데, 발행된 두 문서 모두 full이다. 시트에도 HUIS 고지서 조회 경로가 직접 적혀 있다 (`qrel-v3-blind-sheet.html:877-936`). 질문 수준은 full/answer가 맞다.

### C4. 최종 코드북을 동일하게 쓴 독립 2인 신뢰도라고 말할 수 없다

지도교수 JSON export는 2026-07-13 00:21Z(한국시간 09:21)이고, 초기 기준/Claude 초벌 커밋은 16:02 KST다. 원칙 11~13은 그 뒤 저자 adjudication에서 정식화됐다. 교수에게 제공된 시트는 기본 두 축과 시효/대상 예시만 포함하며 원칙 11~13은 없다 (`qrel-v3-blind-sheet.html:78-111`).

또한 저자는 Claude 초벌의 경계 6건을 본 뒤 확정했고, 독립 판정자가 아니다. 따라서 현재 agreement/κ는 “동일한 최종 코드북을 사용한 독립 2인 신뢰도”가 아니라 “독립 교수 판정과 LLM 보조 저자 adjudication의 진단적 비교”다.

### C5. 시스템은 chunk를 순위화하지만 qrel/scorer는 URL을 hit로 처리한다 — 요청한 다섯 프레임 밖의 발견

`run_questions.py:first_gold_rank`는 content signature가 맞지 않아도 URL이 gold와 같으면 첫 rank를 hit로 반환한다. `make_blind_sheet.py`도 URL로 중복 제거하며 첫 chunk만 남긴다.

Q009 hybrid 결과가 실증 사례다. 같은 `GraduateGrades/pdfdownload/2025` URL이 rank 3과 4에 나오며, rank 3 chunk는 사실상 `- - 1 -`, rank 4 chunk에 학점표가 있다 (`retrieval-hybrid-20260712-061045.jsonl:9`). 현재 scorer는 rank 3을 정답으로 센다. 이는 entry page invalid를 고친 뒤에도 MRR/nDCG가 다시 부풀 수 있는 경로다.

수정: 논문에서 page discovery와 evidence-chunk retrieval을 분리하고, 근거 지지 지표는 qid-chunk 또는 qid-document-span 단위로 채점한다. URL 중복은 점수 계산 전에 canonical document로 dedupe하되, “정답 chunk가 실제 top-k에 있었는가”를 별도 보고한다.

## 중요

### I1. 시효는 ‘문서 성격’이 아니라 답에 사용한 claim 단위여야 한다

현재 원칙 11을 문자 그대로 적용하면 날짜가 박힌 Q003/Q030 공지는 stale여야 하지만 CSV에서는 current다. 반대로 Q032의 2025-2 공지는 stale다. 실제로 원하는 규칙은 “문서가 공지인가”가 아니라 “답에 사용하는 사실이 기간 값인가, 지속되는 경로/기관 정보인가”다.

권장 규칙: `temporal_validity`는 질문에 답하기 위해 채택한 claim에 부여한다. 같은 문서의 “2026-1 납부일”은 stale이고 “HUIS 고지서 메뉴”는 current일 수 있다.

### I2. Q033의 ‘명시 vs 유추’는 entailment와 추측을 섞는다

18/19학점에 +3학점을 명시한 문서에서 21/22를 계산하는 것은 약한 추측이 아니라 결정적 entailment다. 이를 partial로 내리면 RAG의 정상적인 조합/산술을 벌점 처리한다. 반면 Q006의 서류명 등가성은 제시 재료만으로 entail되지 않는다.

권장: support sufficiency와 directness를 분리한다.

- `support_grade`: 답이 논리적으로 도출되는가
- `derivation`: explicit / deterministic_derived / speculative

### I3. partial support에서 답변/거절을 나누는 규칙이 없다

Q032는 partial/answer, Q005·Q006·Q023·Q031·Q039는 partial/abstain이다. “안전한 제한 답변”을 허용하는지, 완전한 절차만 답변으로 보는지 기준이 없다. Q006의 official current page는 정확한 HUIS 경로를 주며, 명칭만 다르다 (`qrel-v3-blind-sheet.html:237-242`). `absent, stale`는 사실과 맞지 않는다.

권장: `expected_behavior = full_answer / qualified_answer / abstain`으로 바꾸거나, binary를 유지하면 partial의 answer 조건을 명문화한다.

### I4. reason이 support와 모순되거나 원인 층을 섞는다

- Q005/Q006/Q023: support partial인데 reason absent.
- Q021: “어디서 확인”이라는 위치 질문이므로 personalized가 아니라 안내 경로 부재가 문제다 (`qrel-v3-blind-sheet.html:436-457`).
- Q024: 알려진 규정/PDF 수집 실패가 있다면 absent보다 acquisition_failure가 맞다.
- Q039: acquisition_failure와 stale이 병존한다.
- Q045: library 도메인이 크롤 밖이라는 실행 기록과 absent가 충돌한다.

권장: `primary_reason` 하나와 `secondary_reasons[]`를 분리하고 precedence를 고정한다.

### I5. 기존 55행 중 재검토가 필요한 행

1. Q030 beauty 공지: 본문이 “뷰티미용학과 재학생”을 대상으로 하는데 audience_scope=match다 (`qrel-v3-blind-sheet.html:741-783`). 현재 원칙 5라면 mismatch 또는 unknown이다.
2. Q030 공식 5254: “제목만 텍스트, 본문 이미지”라고 스스로 적고 partial을 줬다. 원칙 12의 본문 기준이면 invalid가 더 일관된다.
3. Q037 드림라이프 FAQ: 졸업증명서가 목록에 없고 공식 안내와 충돌하는데 positive partial gain을 준다. `invalid` 또는 별도 `contradictory` 플래그가 필요하다.
4. Q041 계절학기: 구체 기간이 없는데 partial을 주는 것이 허용되는지 partial 예시로 명문화해야 한다.
5. Q003/Q030의 current는 원칙 11과 충돌하므로 행 또는 원칙을 수정해야 한다.
6. Q033 deterministic derivation을 partial로 두는 기준은 별도 directness 축으로 이동하는 편이 낫다.

나머지 49행에서는 제공된 재료와 기록 범위 내에서 명백한 원칙 위반을 찾지 못했다.

### I6. 저자 ‘논의 전’ 원본이 보존되지 않았다

기록은 Claude-저자 논의 전 agreement를 support 11/18, deployment 12/18로 적는다. 그러나 공개된 저자 JSON은 논의 후 확정값이며 revision history 필드가 없다. 이 JSON과 Claude 초벌을 비교하면 14/18, 13/18이 나온다. 따라서 11/18·12/18은 현재 산출물만으로 재현할 수 없다.

수정: 최초 export, adjudicated export를 별도 immutable 파일로 보존하고 SHA-256을 기록한다.

### I7. 낮은 κ를 ‘answerability가 자명하지 않다’는 실증으로 해석하면 공격받는다

18문항은 기존 insufficient 층에서 목적표집됐고, 최종 코드북도 동일하게 공유되지 않았다. 낮은 κ는 task ambiguity 외에 codebook drift, prevalence, instruction 차이를 반영한다. 전체 50문항 신뢰도로 일반화할 수 없다.

논문에는 raw agreement, confusion matrix, category prevalence를 함께 싣고 κ는 descriptive로 한정한다.

### I8. 현재 scorer는 v2 기본값과 binary metric을 그대로 쓴다

`run_questions.py` 기본 파일은 `questions.csv`와 `gold_sources.csv`이고, `GoldSource`는 `relevance` 필드를 요구한다. metric도 single-relevant binary nDCG다. v3 CSV를 그대로 넘기면 스키마가 맞지 않거나, 새 등급을 사용하지 못한다.

수정: v4 전용 scorer를 새로 만들고 기존 결과 JSONL의 내장 `gold_*` 필드는 무시한 채 v4 qrel과 offline join한다.

### I9. 대상자 기준은 ‘일반 학생’이 아니라 query-implied audience로 정의해야 한다

시트는 “키오스크 앞의 일반 학생”을 기준으로 하지만, 질문셋에는 편입 지원자·신입생·기숙사 신청자도 있다. `audience_scope=match`는 문서 호스트가 아니라 질문이 전제하는 사용자 집단과 claim의 적용 범위로 판정해야 한다.

## 사소

1. 첨부 설명은 retrieval JSONL 4개라고 했지만 ZIP에는 3개다. 누락된 원천은 `retrieval-20260705-094816.jsonl`이다.
2. `eval/README.md`와 기존 scorer 문서는 v2 기준이라, 재채점 때 실수 가능성이 크다.
3. Q011=Q035 중복을 보존하고 dedup sensitivity를 계획한 것은 타당하다. headline과 dedup 결과를 함께 보고해야 한다.
4. v2를 불변 보존하고 Q009 entry page를 invalid로 바꾼 계보 처리는 잘했다.

## 18문항 독립 재판정 요약

| QID | 현재 | 리뷰 결론 |
|---|---|---|
| Q005 | partial / abstain / absent | ① full. ②는 temporal 단위 선택에 따라 answer 또는 stale abstain. absent는 불가. |
| Q006 | partial / abstain / absent, stale | partial은 가능. current official 경로가 있으므로 stale/absent는 불가; qualified answer 또는 terminology mismatch 규칙 필요. |
| Q015 | full / answer | 유지. |
| Q016 | full / abstain / audience mismatch | 유지 가능. query-implied audience 규칙을 명시. |
| Q021 | none / abstain / personalized | support/deployment 유지 가능, reason은 absent/acquisition failure. 위치 질문이라 personalized는 부정확. |
| Q022 | none / abstain / absent | 제시 pool 기준 유지. corpus-wide none으로 부르지 말 것. |
| Q023 | partial / abstain / absent | partial 유지; absent는 모순. qualified answer 기준 필요. |
| Q024 | none / abstain / absent | pool 기준 none. known/missing regulation이면 acquisition failure; union pool 재판정. |
| Q026 | none / abstain / absent | 유지. |
| Q030 | full / answer | claim-level temporal/audience rule을 채택할 때만 유지. 문서 행은 수정 필요. |
| Q031 | partial / abstain / audience mismatch | ① full, ② abstain(audience mismatch). |
| Q032 | partial / answer | full / answer. |
| Q039 | partial / abstain / acquisition failure | 유지, stale을 secondary reason으로 추가. |
| Q040 | full / abstain / stale | 유지. |
| Q043 | none / abstain / absent | sheet 기준 유지; semantic CampusMap 포함 union pool에서 재판정. |
| Q045 | none / abstain / absent | none / abstain / acquisition failure. |
| Q049 | none / abstain / absent | pool 기준 유지. corpus-wide none은 미검증. |
| Q050 | none / abstain / absent | pool 기준 유지. corpus-wide none은 미검증. |

## 논문 방법 절 권장 문구 — 현재 상태를 정직하게 기술하는 경우

> 기존 qrel에서 insufficient로 분류된 18문항에 대해 지도교수 1인이 기존 라벨을 보지 않은 상태로 판정하였다. 판정 자료는 hybrid top-5와 EXP-06 evidence 후보를 고정하여 제시한 블라인드 시트였으므로, 본 판정의 support는 전체 코퍼스의 존재 명제가 아니라 제시된 evidence pool 내 지지를 뜻한다. 저자 판정은 LLM 보조 초벌과 경계 사례 일부 노출 이후 확정되었으므로 독립 판정자로 간주하지 않았다. 최종 원칙 11~13은 교수 판정 이후의 adjudication에서 정식화되었다. 따라서 raw agreement와 Cohen's κ는 교수 판정 개봉 전에 동결한 저자 확정본과의 진단적 비교로 보고하며, 동일한 최종 코드북을 사용한 독립 2인 신뢰도 추정치로 해석하지 않는다. 18문항은 기존 insufficient 층에서 목적표집되었으므로 이 수치를 전체 50문항으로 일반화하지 않았다.

“세 판정자가 동일 규칙으로 독립 판정했다”, “2인 판정 신뢰도”, “낮은 κ가 answerability의 본질적 모호성을 입증했다”는 문구는 쓰면 안 된다.

## v4 후 권장 문구

> BM25-only, dense-only, hybrid production mode의 top-5 합집합과 EXP-06에서 사용된 정확한 chunk ID를 pooled evidence로 구성하였다. 최종 코드북을 판정 전에 동결하고, 저자와 독립 판정자가 동일한 코드북으로 개별 판정하였다. 논의 전 원본 판정은 immutable JSON과 SHA-256으로 보존했으며, 불일치는 별도의 adjudicated qrel에 기록하였다. 문서-질문 쌍마다 support grade와 답에 사용한 claim의 temporal validity 및 audience scope를 판정하였다. 검색 평가는 support relevance와 deployable relevance를 별도로 계산하였다.

## 다음 단계 차단 조건

검색 재채점과 EXP-07 전에 다음을 완료해야 한다.

1. v4 codebook 동결: pool/corpus 명칭, claim-level temporal/audience, partial answer 기준, set-level aggregation 규칙.
2. 세 모드 top-5 union 414 qid-URL 쌍(207 unique URL)을 pooled judgment 대상으로 만들기. graded nDCG를 보고하려면 unjudged와 invalid를 구분한다.
3. 7개 support-positive abstain 질문의 문서 qrel 추가.
4. Q005/Q031/Q032 및 reason 오류 수정.
5. exact EXP-06 source JSONL 또는 used chunk manifest 복구.
6. fresh independent rater가 final codebook으로 최소 18문항 재판정. 불가능하면 기존 교수 결과는 face-validity diagnostic로만 보고.
7. chunk-level evidence hit와 URL-level page hit를 분리한 scorer 작성.
8. `nDCG_support@5`, `nDCG_deployable@5`, `Recall_full@5`, `Recall_any@5`, `Recall_deployable@5`를 별도 보고하고 분모 N을 명시.
9. invalid Q009 entry page는 gain 0으로 두고, CSV에 없다는 이유만으로 unjudged 문서를 invalid 처리하지 않기.
10. URL/문서 중복은 최초 canonical rank만 사용하고 Q011/Q035 dedup sensitivity 병기.
11. EXP-07은 coverage, 정확 답변률, 과잉답변률, 과잉거절률, partial answer를 분리하며, deployment=abstain 문항을 정확도 분모에서 빼서 성능을 부풀리지 않기.

## 재현 부록

- `/mnt/data/qrel-v3-attachment-audit.json`
- `/mnt/data/recompute_qrel_attachment_audit.py`
