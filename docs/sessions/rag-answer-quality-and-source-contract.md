# RAG 답변 품질과 출처 표시 계약

## 도메인

Campus Copilot의 핵심 품질 영역입니다. 단순히 답변이 자연스러운지보다, 공식 문서 근거가 충분한지, 관련 없는 출처가 화면에 뜨지 않는지, 근거 부족을 안전하게 인정하는지가 중요했습니다.

## 목표

실제 `.data`와 현재 RAG 흐름을 기준으로, 답변 옆에 관련 없는 출처가 표시되는 문제를 확인했습니다. 이후 이 내용을 `docs`의 답변 품질 지침서와 구현 계획서로 문서화했습니다.

## 문제

질문 예시는 `휴학 신청은 어떻게 하나요?`였습니다. 당시 응답 metadata에는 질문과 직접 관련 없는 출처가 함께 표시됐습니다.

세션에서 관찰된 예:

- 조직도
- 대학평의원회
- 총장에게 바란다
- 졸업학점 2024

문제의 핵심은 “검색된 후보”와 “실제로 답변에 사용한 공식 출처”가 분리되어 있지 않았다는 점입니다.

## 확인한 흐름

당시 구조에서는 retrieval 결과가 있으면 backend가 `sources`를 forwarding했고, frontend의 `SourceList`는 non-empty `sources` 배열을 그대로 렌더링했습니다.

즉, 다음이 같은 것으로 취급됐습니다.

- retrieval candidate
- evidence candidate
- answer-used source
- UI displayed source

이 구조에서는 답변이 “근거 부족”이어도 검색 후보가 있으면 출처가 뜰 수 있었습니다.

## 비교한 선택지

- 검색 후보를 그대로 출처로 보여주기
- top-k retrieval 결과 중 URL dedupe만 해서 보여주기
- LLM 답변에 사용한 source number만 표시하기
- 공식 문서 근거로 충분히 사용된 source만 `sources`에 남기기
- 근거 부족이면 `sources=[]`와 `answerability=insufficient`로 내리기

선택한 방향은 마지막 두 가지였습니다.

## 선택: 답변 품질 계약 문서화

작성된 문서:

- [RAG 답변 품질 향상 지침서](../kiosk/specs/2026-06-01-rag-answer-quality-design.md)
- [RAG 답변 품질 구현 계획](../kiosk/plans/2026-06-01-rag-answer-quality-implementation.md)

핵심 계약:

- `answerability`: `answerable | partial | insufficient`
- `sources`: 실제 답변에 사용한 공식 문서만 포함
- retrieval candidates와 displayed sources 분리
- `conflict_warning`
- `retrieval_status`
- JSON-only LLM output
- final-only kiosk UX
- source-number는 내부용이며 사용자에게 노출하지 않음
- query log에는 사용자 표시 출처와 retrieval candidate metadata를 구분해서 보존
- JSON/schema 실패는 `insufficient`가 아니라 안전한 `error`로 처리

현재 코드에도 이 계약의 일부가 반영되어 있습니다.

- `backend/app/schemas/chat.py`에는 `answerability`, `conflict_warning`, `retrieval_status`가 schema에 포함되어 있습니다.
- `backend/app/api/routes/chat.py`는 evidence candidate가 없을 때 `insufficient_response()`를 사용합니다.
- JSON validation failure는 `error` event로 반환합니다.
- `frontend/src/components/kiosk/answer/SourceList.tsx`의 제목도 “답변에 사용된 공식 문서”입니다.

## 결과

RAG 품질 문제는 단순 prompt 수정이 아니라 API contract, source filtering, query logging, frontend source rendering까지 이어지는 시스템 문제로 정리됐습니다.

이후 관련 구현 커밋도 이어졌습니다.

- `69066fb docs(rag): define answer quality contract`
- `5439897 feat(rag): enforce structured final answers`
- `2ff15c6 fix(chat): deduplicate answer sources`
- `59bcc64 fix(kiosk): render markdown in answer source cards`

## 포트폴리오/논문 포인트

- RAG citation 문제를 “retrieved source와 cited source의 분리”로 정의했습니다.
- `answerability`를 도입해 답변 가능성 자체를 모델 출력 계약에 포함했습니다.
- `insufficient`를 공식 근거 부족에만 쓰도록 하여 error와 evidence insufficiency를 분리했습니다.
- 키오스크 사용자를 위해 final-only UX를 선택했습니다.

## 관련 코드·자료

- [backend/app/schemas/chat.py](../../backend/app/schemas/chat.py)
- [backend/app/api/routes/chat.py](../../backend/app/api/routes/chat.py)
- [backend/app/services/rag.py](../../backend/app/services/rag.py)
- [backend/app/services/retriever.py](../../backend/app/services/retriever.py)
- [backend/app/prompts/chat_answer.md](../../backend/app/prompts/chat_answer.md)
- [frontend/src/components/kiosk/answer/SourceList.tsx](../../frontend/src/components/kiosk/answer/SourceList.tsx)
- [RAG 답변 품질 지침서](../kiosk/specs/2026-06-01-rag-answer-quality-design.md)
- [RAG 답변 품질 구현 계획](../kiosk/plans/2026-06-01-rag-answer-quality-implementation.md)

## 주석

- 이 문서는 “정확한 답변을 생성한다”보다 “공식 근거가 부족할 때 부족하다고 말한다”를 더 중요한 품질 기준으로 둡니다.
- 학사 안내 도메인에서는 그럴듯한 오답보다 안전한 `insufficient`가 더 나은 선택일 수 있습니다.

## 공란/미확인

- 실제 사용자에게 `partial`과 `insufficient`를 어떻게 표현할지에 대한 UX 테스트 결과는 없습니다.
- source filtering 기준의 threshold나 ranking parameter에 대한 정량 실험은 아직 공란입니다.
