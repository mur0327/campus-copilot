# RAG 답변 품질 향상 실행 계획

**Date**: 2026-06-01
**Goal**: 공식 문서 근거에 기반한 최종 답변만 사용자에게 표시하고, 관련 없는 출처 노출과 미검증 토큰 스트리밍을 제거한다.
**Source Of Truth**: `docs/specs/2026-06-01-rag-answer-quality-design.md`

## 1. 목표 상태

사용자는 질문 후 진행 상태만 보고, 검증이 끝난 최종 답변을 한 번에 받는다.

최종 응답은 구조화 필드를 포함한다.

- `answerability`
- `answer`
- `summary`
- `procedure_steps`
- `notes`
- `limitations`
- `sources`
- `conflict_warning`
- `freshness`
- `retrieval_status`

출처 패널에는 검색 후보가 아니라 답변에 실제 사용된 공식 문서만 표시한다.

LLM 출력은 JSON만 허용한다. JSON/schema 검증 실패는 재시도 1회 후 안전한 `error` 이벤트로 처리하고, `insufficient`로 매핑하지 않는다.

## 2. 변경 범위

### Backend

- `backend/app/schemas/chat.py`
- `backend/app/services/rag.py`
- `backend/app/services/retriever.py`
- `backend/app/services/query_log.py`
- `backend/app/api/routes/chat.py`
- `backend/app/prompts/chat_answer.md`
- `backend/tests/services/test_rag.py`
- `backend/tests/services/test_retriever.py`
- `backend/tests/services/test_query_log.py`
- `backend/tests/api/test_chat_sse.py`

### Frontend

- `frontend/src/types/kiosk.ts`
- `frontend/src/api/chat.ts`
- `frontend/src/hooks/useChat.ts`
- `frontend/src/components/kiosk/answer/AnswerPanel.tsx`
- `frontend/src/components/kiosk/answer/AnswerText.tsx`
- `frontend/src/components/kiosk/answer/ProcedureSteps.tsx`
- `frontend/src/components/kiosk/answer/SourceList.tsx`
- related tests under `frontend/src/**/*.test.tsx` and `frontend/src/**/*.test.ts`

## 3. Execution Rules

- Do not show raw JSON, partial JSON, unvalidated model text, or model tokens to users.
- Do not reuse retrieval candidates as user-facing sources.
- Do not infer `procedure_steps` from natural-language answer text.
- Do not bump the cache key version for this change unless explicitly decided later.
- Treat cached payloads without required structured fields as cache misses.
- Keep legacy `answer` for QR, print, logs, and fallback surfaces, but render structured fields first in the answer UI.
- Keep prompt content in a file template, not as a large hard-coded service string.

## 4. Work Plan

### Task 1: Chat Schema Contract

**Files**

- Modify: `backend/app/schemas/chat.py`
- Modify: `frontend/src/types/kiosk.ts`
- Test: backend and frontend type/mapping tests

**Steps**

- [ ] Add `answerability` enum values: `answerable`, `partial`, `insufficient`.
- [ ] Add final response fields: `summary`, `notes`, `limitations`.
- [ ] Keep `conflict_warning` required in the final response with `exists` and optional `description`.
- [ ] Extend `RetrievalStatusPayload` with:
  - `evidence_candidate_count`
  - `display_source_count`
  - `answerability`
- [ ] Add `ChatStatusEvent` for SSE status events with `step`.
- [ ] Remove active reliance on `ChatTokenEvent` and `ChatProcedureStepsEvent` in frontend types.
- [ ] Ensure `ChatResponse.answer` remains required.

**Acceptance**

- Backend response schema can represent `answerable`, `partial`, and `insufficient`.
- Backend response schema always includes `conflict_warning`.
- Frontend types can consume the new final `done` payload.
- Old cached responses missing structured fields can be detected.

### Task 2: Evidence Filtering And Question Intent

**Files**

- Modify: `backend/app/services/retriever.py` or create `backend/app/services/evidence.py`
- Test: `backend/tests/services/test_retriever.py` or new `test_evidence.py`

**Steps**

- [ ] Add named constants:
  - `EVIDENCE_MAX_CANDIDATES = 4`
  - `EVIDENCE_MIN_SCORE = 0.35`
  - `EVIDENCE_MIN_DIRECT_OVERLAP = 1`
  - `EVIDENCE_PREVIEW_CHARS = 160`
- [ ] Normalize Korean particles and common question endings so `신청은` can match `신청`.
- [ ] Add academic keyword starter dictionary:
  - `휴학`, `복학`, `자퇴`, `졸업`, `장학`, `등록금`, `수강신청`, `성적`, `증명서`
  - `신청`, `기간`, `방법`, `서류`, `기준`, `조건`, `문의`, `담당`
- [ ] Implement candidate acceptance:
  - reject missing URL or blank content
  - accept score >= threshold
  - accept title/menu/content overlap >= threshold
  - reject when both score and overlap fail
- [ ] Group duplicates by `document_id`, fallback to canonical URL.
- [ ] Keep highest scoring chunk as display candidate.
- [ ] Allow same-document extra chunks only as internal context.
- [ ] Trim final source-numbered LLM evidence candidates to `EVIDENCE_MAX_CANDIDATES`.
- [ ] Add light question intent classification.

**Acceptance**

- `휴학 신청은 어떻게 하나요?` does not keep unrelated candidates without score or normalized keyword support.
- LLM prompt context receives at most 4 source-numbered evidence candidates.
- Same-document duplicate chunks do not create duplicate displayed sources.
- No-evidence result can be detected before LLM call.

### Task 3: Prompt Template And JSON Parser

**Files**

- Create: `backend/app/prompts/chat_answer.md`
- Modify: `backend/app/services/rag.py`
- Test: `backend/tests/services/test_rag.py`

**Steps**

- [ ] Move prompt rules to `backend/app/prompts/chat_answer.md`.
- [ ] Include JSON output schema in the template.
- [ ] Include one good example and one bad example.
- [ ] Add template loader with explicit placeholder substitution.
- [ ] Add JSON parser and schema validator for LLM output.
- [ ] Add one repair retry for invalid JSON/schema output.
- [ ] On repeated JSON/schema failure, return SSE `error` with:

```text
답변을 확인하는 중 문제가 발생했습니다. 다시 질문해 주세요.
```

- [ ] Log internal failure reason as `json_validation_failed`.

**Acceptance**

- LLM output is never displayed before JSON parsing and validation.
- JSON/schema failure is not mapped to `insufficient`.
- Procedure steps come from JSON only.

### Task 4: Source Validation And Final Response Assembly

**Files**

- Modify: `backend/app/services/rag.py`
- Test: `backend/tests/services/test_rag.py`

**Steps**

- [ ] Validate `used_source_numbers`.
- [ ] Remove out-of-range and duplicate source numbers.
- [ ] Force `[]` when answerability is `insufficient`.
- [ ] Downgrade `answerable` or `partial` to `insufficient` when validated source numbers are empty.
- [ ] Build final `sources` only from validated used source numbers.
- [ ] Assemble legacy `answer` from:
  - `summary`
  - `확인된 절차`
  - `준비/주의사항`
  - `확인이 필요한 점`
- [ ] Set `freshness` from displayed sources.
- [ ] Preserve `conflict_warning` from the conflict lookup in every final response.
- [ ] Populate `retrieval_status.evidence_candidate_count`, `display_source_count`, and `answerability`.
- [ ] Ensure assembled `answer`, `summary`, `notes`, and `limitations` do not include visible source numbers such as `[1]`.

**Acceptance**

- Search candidates never appear as sources unless selected through validated `used_source_numbers`.
- `insufficient` always has empty `sources` and empty `procedure_steps`.
- `partial` shows only used sources and limitations.
- Final answer text does not expose source numbers.
- Final response always includes `conflict_warning`.

### Task 5: Chat SSE Contract

**Files**

- Modify: `backend/app/api/routes/chat.py`
- Test: `backend/tests/api/test_chat_sse.py`

**Steps**

- [ ] Replace token streaming with optional `status` events.
- [ ] Supported status steps:
  - `retrieving`
  - `checking_evidence`
  - `generating`
  - `validating`
- [ ] Remove `token` event emission.
- [ ] Remove `procedure_steps` event emission.
- [ ] Emit `done` only after final response validation.
- [ ] Return `done` immediately on valid cache hit.
- [ ] Treat no evidence candidates as direct `insufficient` without LLM call.
- [ ] Treat JSON/schema failure as `error`, not `done`.

**Acceptance**

- Event flow is `status* -> done` or `status* -> error`.
- User-facing answer text appears only from `done`.
- Cache hit emits `done` without fake status events.

### Task 6: Query Log Payload

**Files**

- Modify: `backend/app/services/query_log.py`
- Test: `backend/tests/services/test_query_log.py`
- Test: `backend/tests/api/test_chat_sse.py`

**Steps**

- [ ] Keep `items` as displayed sources only.
- [ ] Add `_meta.retrieval_candidates` with:
  - `chunk_id`
  - `title`
  - `url`
  - `score`
  - `chunk_type`
  - `preview`
- [ ] Store at most 8 retrieval candidates.
- [ ] Collapse whitespace in previews.
- [ ] Limit preview to 160 characters.
- [ ] Keep whole `sources` log payload under 32 KB.
- [ ] Avoid raw HTML, raw JSON payloads, and full table chunks in previews.
- [ ] Redact obvious phone numbers, email addresses, and resident-registration-number-like patterns from query mirrors and previews.
- [ ] Add `_meta.answerability`, `_meta.used_source_numbers`, and `_meta.prompt_version`.
- [ ] Store `_meta.used_source_numbers` as validated LLM evidence candidate numbers, not display-card indexes.
- [ ] Add `_meta.retrieval_status` with the same retrieval/answerability diagnostics returned in `done`.

**Acceptance**

- Admin quality-review logs can explain why a candidate was considered.
- User-facing source list remains separate from retrieval candidates.
- Query logs include `retrieval_status`.
- Log payload stays compact.

### Task 7: Frontend Final-Only UX

**Files**

- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/src/hooks/useChat.ts`
- Modify: `frontend/src/store/kioskStore.ts` if needed
- Test: `frontend/src/hooks/useChat.test.ts`
- Test: `frontend/src/api/chat.test.ts`

**Steps**

- [ ] Parse `status`, `done`, and `error` events only.
- [ ] Remove token accumulation from UI state.
- [ ] Map status steps to:
  - `retrieving`: `공식 문서 검색 중`
  - `checking_evidence`: `근거 확인 중`
  - `generating`: `답변 작성 중`
  - `validating`: `답변 검증 중`
- [ ] Store final structured answer from `done`.
- [ ] Ensure stale request guard still prevents old done/error events from replacing current state.
- [ ] Show safe error text from backend `error.message`.
- [ ] Use the generic fallback only for request, transport, and unexpected runtime failures where no safe backend message was received.

**Acceptance**

- User never sees raw JSON or token fragments.
- Final answer appears only after `done`.
- Progress states are visible while waiting.

### Task 8: Frontend Structured Answer Rendering

**Files**

- Modify: `frontend/src/components/kiosk/answer/AnswerPanel.tsx`
- Modify: `frontend/src/components/kiosk/answer/AnswerText.tsx`
- Modify: `frontend/src/components/kiosk/answer/ProcedureSteps.tsx`
- Modify: `frontend/src/components/kiosk/answer/SourceList.tsx`
- Test: related answer component tests

**Steps**

- [ ] Render `summary` as the primary answer.
- [ ] Show `partial` label as `일부 정보 확인됨`.
- [ ] Show `insufficient` label as `공식 문서 근거 부족`.
- [ ] Render `notes` as `준비/주의사항`.
- [ ] Render `limitations` as `확인이 필요한 점`.
- [ ] Keep `answer` for full answer, QR, and print compatibility.
- [ ] Preserve existing conflict warning rendering with the new structured payload.
- [ ] Rename source panel to `답변에 사용된 공식 문서`.
- [ ] Empty source state: `답변에 사용된 공식 문서가 없습니다`.
- [ ] Empty procedure state: `확인된 절차가 없습니다`.
- [ ] Remove `별도 절차가 필요하지 않습니다`.

**Acceptance**

- `answerable`, `partial`, and `insufficient` render distinctly.
- Conflict warning remains visible when present.
- Procedure absence does not imply no procedure is required.
- Only displayed sources appear in source panel and print payload.

## 5. Verification Plan

### Backend

Run focused tests:

```bash
cd backend && uv run pytest \
  tests/services/test_retriever.py \
  tests/services/test_rag.py \
  tests/services/test_query_log.py \
  tests/api/test_chat_sse.py
```

Run broader backend tests if the focused suite passes:

```bash
cd backend && uv run pytest
```

### Frontend

Run focused tests:

```bash
cd frontend && npm test -- \
  src/api/chat.test.ts \
  src/hooks/useChat.test.ts \
  src/components/kiosk/answer/AnswerPanel.test.tsx \
  src/components/kiosk/answer/ProcedureSteps.test.tsx \
  src/components/kiosk/answer/SourceList.test.tsx
```

Run broader frontend checks if focused tests pass:

```bash
cd frontend && npm test
```

### Manual Smoke

With local services running:

1. Ask `휴학 신청은 어떻게 하나요?` while the crawl set lacks a 휴학 procedure document.
2. Confirm progress status appears before the final result.
3. Confirm no token fragments or raw JSON appear.
4. Confirm final answer is `insufficient` or `partial` according to validated evidence.
5. Confirm unrelated sources such as `대학평의원회`, `총장에게 바란다`, or `졸업학점 2024` do not appear unless actually used.
6. Confirm source panel title is `답변에 사용된 공식 문서`.
7. Confirm query log stores displayed sources separately from retrieval candidate previews.

## 6. Rollout Notes

- This change intentionally alters the chat SSE event contract.
- Frontend and backend must be updated together.
- Cache key version remains unchanged, but old payloads without structured fields are ignored as cache misses.
- Existing admin log readers should tolerate the expanded `_meta` object.
