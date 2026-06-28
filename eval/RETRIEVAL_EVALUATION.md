# RETRIEVAL EVALUATION

Campus Copilot 문서 검색(retrieval) 평가의 방법론과 결과를 정리한 문서다.
논문(RAG 기반 학사 안내) RQ1 "하이브리드 검색이 공식 문서 검색 성능을 개선하는가"의 근거 자료다.

작성 기준일: 2026-06-28

## 1. 개요

- 평가 대상: 현재 로컬 `.data`(PostgreSQL / ChromaDB / BM25)에 적재된 호남대학교 크롤 코퍼스.
- 실행 도구: [run_questions.py](run_questions.py) — backend `HybridRetriever`를 직접 호출해 LLM 없이 top-k 검색 후보만 수집한다.
- 분석 도구: [analyze_retrieval_chunks.py](analyze_retrieval_chunks.py) — 결과 JSONL을 chunk 단위 CSV로 펼쳐 파싱·evidence 품질을 점검한다.

## 2. 평가 데이터셋

- [questions.csv](questions.csv): 10개 카테고리 × 2문항 = 20문항.
- [gold_sources.csv](gold_sources.csv): 사람이 검증한 공식 정답 문서. 18행(질문 16개, 일부 secondary 포함).

| 구분 | 수 | 비고 |
| --- | --- | --- |
| answerable | 16 | 정답 문서가 코퍼스에 존재 |
| insufficient | 4 | 코퍼스에 정답 문서 없음(분모 제외) |

## 3. 방법론

설계 결정은 사전 합의(grill)로 확정했다.

- **gold 출처**: retrieval 결과가 아니라 전체 코퍼스(DB 전문 검색)에서 후보를 뽑고 도메인 전문가가 확정한다. retriever 편향을 배제해 벤치마크 타당성을 확보한다.
- **gold 매칭**: 같은 본문이 여러 학과 사이트에 복제되므로 **본문 content-signature 기준**으로 매칭한다(URL 완전 일치는 fallback). 미러 호스트와 무관하게 "정답 정보를 찾았는가"를 측정한다.
- **insufficient 처리**: 코퍼스에 정답이 없는 문항은 Recall@5/MRR **분모에서 제외**하고 별도로 센다. 검색 랭킹 품질과 크롤 커버리지를 분리한다.
- **지표**: 주지표는 Recall@5와 MRR(이진). evidence Recall@5는 답변 근거 후보 품질의 보조 지표다.

## 4. 검색 개선 작업

| 단계 | 커밋 | 내용 |
| --- | --- | --- |
| 키워드 정규화 | `6f98948` | 복합어·활용형을 부분 문자열로 매칭(재학증명서→증명서, 문의하면→문의). `입학`·`상담` 추가 |
| 중복 제거 | `8069d87` | 학과 미러 문서를 content-signature로 dedupe. 동점 시 대표 사이트(general_academic) 우선 |
| 의도 분류 교정 | `b675a64` | 우선순위를 requirement > deadline > contact > procedure로 재배열. 위치·사실 질의는 factual |
| 의도-인지 랭킹 | `9cb802a` | 의도별 곱셈 boost/penalty(클램프 [0.7, 1.4]). page_kind 의미충돌만 강한 패널티 |

설계 원칙은 **고정 규칙 + 도메인 정당화**이며, gold 지표는 최적화 대상이 아니라 **무회귀 가드레일**로만 쓴다(N=20 과적합 회피).

### 의도-인지 랭킹 규칙

| 질문 의도 | 우대 | 패널티 |
| --- | --- | --- |
| requirement(조건/기준) | academic ×1.15 | schedule ×0.7 (의미충돌) |
| deadline(언제/기간) | schedule ×1.15 | DepartmentCurriculum URL ×0.7 |
| contact(문의/전화) | 전화번호·문의 본문 / contact 페이지 ×1.2 | — |
| 증명서 질의 | certificate 페이지 ×1.15 | — |
| 일반 학사(procedure/factual) | general_academic ×1.1 | 학과 게시판/FAQ URL ×0.9 |

## 5. 결과

answerable 16문항 기준이다.

| 지표 | 베이스라인 | 의도-인지 랭킹 적용 후 |
| --- | --- | --- |
| Recall@5 | 0.4375 (7/16) | 0.4375 |
| MRR | 0.2729 | **0.3385** (+24% 상대) |
| evidence Recall@5 | 0.50 | 0.50 |

가드레일은 모두 통과했다.

- 최종 top-k 중복 행 0개(미러 제거 유지).
- evidence 후보가 비는 문항은 Q017 하나로 변동 없음.
- 키워드 정규화 보강으로 evidence 후보 행 수는 56 → 72로 증가했다(Q013·Q016 복구 포함).

## 6. 핵심 발견: Recall은 ranking이 아니라 recall에 묶여 있다

의도-인지 랭킹은 **MRR을 올렸지만 Recall@5는 그대로**다. 원인을 분석하면 명확하다.

answerable 16문항 중 miss 9문항의 정답 순위(`gold_rank`)는 다음과 같다.

- **8문항: `gold_rank=None`** — 정답 문서가 top-k 후보에 **아예 검색되지 않음**.
- 1문항(Q019): rank 6 — top-5 직전.

즉 대표 공식 페이지(`www.honam.ac.kr/...`)가 학과 미러·공지·대학원 일정에 밀려 후보 집합에 들어오지 못한다. 예) Q012/Q018은 `www.honam.ac.kr/AcademicCalendar` 대신 대학원/학과 일정이 검색된다. 랭킹은 검색된 후보만 재정렬하므로, 남은 갭은 **랭킹이 아니라 recall(임베딩/색인) 문제**다.

→ 향후 과제: 쿼리 임베딩 개선, 대표 문서 우선 색인, 학과 미러 가중치 하향.

## 7. 커버리지·실패 유형 분석

코퍼스에 정답이 없어 insufficient로 분류한 문항을 원인별로 정리한다. 이는 현실 기관 RAG의 검색 성능 상한이 코퍼스 커버리지에 의해 결정됨을 보여준다.

| 유형 | 문항 | 원인 |
| --- | --- | --- |
| 크롤 파싱 한계 | Q015 | 편입 모집요강 실페이지가 canvas PDF 뷰어라 본문 미파싱 |
| 크롤 파싱 한계 | Q016 | 입학상담이 메인 배너 → 외부 카카오톡, 셀렉터 미수집 |
| 정적 페이지 부재 | Q005 | 등록금 납부는 연도별·개인 우편/문자 안내 |
| 정적 페이지 부재 | Q006 | 납부확인서는 종합정보시스템에서 개별 발급 |

추가로 Q019(휴학 문의 부서)는 정답 페이지(`CamPhNum`)에 "휴학" 키워드가 없어, 의미적 연결이 필요한 난이도 높은 케이스다(answerable로 유지).

## 8. 재현 방법

도커 컨테이너(postgres / chromadb)가 떠 있어야 한다.

```bash
# 20문항 전체 실행 → JSONL/CSV/metrics 생성
uv run --project backend python eval/run_questions.py

# 최신 결과를 chunk 단위로 펼쳐 진단
python3 eval/analyze_retrieval_chunks.py
```

결과는 `eval/results/`에 저장되며 재생성 가능한 산출물이라 Git에 커밋하지 않는다.
집계 지표는 `retrieval-<timestamp>-metrics.json`에 기록된다.
