# RAG 평가 방법과 정량 지표

## 도메인

RAG 시스템의 정확도 검증과 정량 평가 방법입니다. Campus Copilot에서는 답변 하나만 맞으면 되는 것이 아니라, 검색된 문서, 표시된 출처, 최종 답변, 근거 부족 처리까지 나누어 평가해야 합니다.

## 목표

RAG 시스템의 정확도 검증 방식과 정량 평가 방법을 정리했습니다. 현재 답변 품질 지침서를 기준으로 평가 축과 지표를 구성했습니다.

## 문제

RAG 정확도를 하나의 점수로만 보면 실패 원인을 알기 어렵습니다.

예를 들어:

- 정답 문서는 검색됐지만 LLM이 잘못 사용했을 수 있습니다.
- 검색 후보는 많지만 화면에 관련 없는 출처가 표시됐을 수 있습니다.
- 공식 문서가 없는데도 답변을 지어냈을 수 있습니다.
- 답변은 맞지만 절차 단계가 빠졌을 수 있습니다.

따라서 evaluation은 여러 축으로 분해해야 합니다.

## 선택한 평가 축

### 1. 검색 정확도

정답 문서가 retrieval top-k 안에 들어오는지 확인합니다.

예시 지표:

- `Retrieval Recall@K`
- `MRR`

### 2. 근거 사용 정확도

검색 후보 중 실제 답변에 사용한 공식 문서만 source로 표시하는지 확인합니다.

예시 지표:

- `Source Precision`
- forbidden source 노출 여부
- displayed source count

### 3. 답변 정확도

최종 답변이 기대 핵심 내용과 절차를 올바르게 포함하는지 확인합니다.

예시 지표:

- `Answerability Accuracy`
- `Groundedness Score`
- `Procedure Step Accuracy`
- `Insufficient False Positive Rate`

## eval case 구조

평가 데이터는 `질문 세트 + 기대값 + 점수 계산` 구조로 두는 방식이 적합합니다.

예시 필드:

```json
{
  "question": "휴학 신청은 어떻게 하나요?",
  "gold_document_url": "",
  "gold_answerability": "answerable | partial | insufficient",
  "expected_core_answer": [],
  "expected_procedure_steps": [],
  "forbidden_sources": []
}
```

## 채점 방식

우선 deterministic하게 채점할 수 있는 항목을 앞에 둡니다.

- 정답 URL이 top-k 안에 있는가
- 표시 출처가 허용 목록 안에 있는가
- forbidden source가 표시되지 않았는가
- `answerability`가 기대값과 같은가
- `insufficient` 상황에서 `sources=[]`인가

LLM-as-judge는 보조 신호로 둡니다. 특히 URL/source precision은 code로 채점하는 편이 안정적입니다.

## 관련 구현·문서와 연결

평가 지표는 RAG answer-quality contract와 직접 연결됩니다.

- `answerability`
- `sources`
- `retrieval_status.evidence_candidate_count`
- `retrieval_status.display_source_count`
- `conflict_warning`
- `procedure_steps`

현재 schema에는 `RetrievalStatusPayload`가 있고, `evidence_candidate_count`, `display_source_count`, `answerability` 같은 필드가 있습니다.

## 결과

RAG 정확도 검증은 “검색 정확도 + 근거 사용 정확도 + 답변 정확도”로 분리하는 방향으로 정리됐습니다. 포트폴리오/논문에서는 이 구조를 evaluation framework로 제시할 수 있습니다.

## 포트폴리오/논문 포인트

- RAG 평가를 단일 subjective score가 아니라 진단 가능한 지표 세트로 정의했습니다.
- official-source QA 도메인에서는 source precision과 insufficient handling이 핵심 지표가 됩니다.
- deterministic check와 LLM-as-judge를 역할 분리했습니다.

## 관련 코드·자료

- [RAG 답변 품질 지침서](../specs/2026-06-01-rag-answer-quality-design.md)
- [RAG 답변 품질 구현 계획](../plans/2026-06-01-rag-answer-quality-implementation.md)
- [backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)
- [backend/tests/api/test_chat_sse.py](../../backend/tests/api/test_chat_sse.py)
- [backend/tests/services/test_rag.py](../../backend/tests/services/test_rag.py)

## 공란/미확인

- 실제 `eval_cases.jsonl` 파일은 세션 데이터 기준으로 생성되지 않았습니다.
- gold question set의 크기, 난이도, 학사 카테고리 분포는 미정입니다.
- metric별 통과 기준선은 아직 정해지지 않았습니다.
