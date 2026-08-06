# Campus Copilot RAG 답변 품질 향상 지침서

**Date**: 2026-06-01
**Scope**: 답변 품질, 절차 생성, 출처 표시, 프롬프트 유지보수성, 키오스크 답변 UX
**Status**: 지침서

## 1. Purpose

This document defines answer-quality guidelines for Campus Copilot.

Users ask practical academic questions. The system must return grounded, clear, and structurally readable information. It must not show unrelated documents as sources, expose raw model output, or stream incomplete answer text to the kiosk UI.

These guidelines are the source of truth for answer quality, procedure generation, source display, prompt structure, and final-answer UX.

## 2. Core Decisions

### 2.1 Source Display

The source panel must show only official documents that were actually used to support the final answer.

It must not show all retrieval candidates. Retrieval candidates may be stored in logs for quality review, but they are not user-facing sources.

If no official document supports the final answer, `sources` must be empty.

### 2.2 Final-Only Answer Display

The kiosk UI must show only the final validated answer.

The backend may keep SSE as the transport, but answer text token streaming is removed. While the system is working, the frontend shows progress states only. Raw JSON, partial JSON, unvalidated text, and model tokens must never be displayed to users.

### 2.3 Answerability

Every final answer has one `answerability` value:

- `answerable`: the official documents support the core answer.
- `partial`: the official documents support only part of the answer.
- `insufficient`: the official documents do not provide enough support.

`error` is not an `answerability` value. Runtime failures use the API error path.

### 2.4 Final Response Fields

The response adds structured fields while keeping the existing `answer` string for current print, QR, log, and fallback surfaces.

The final API response contains these fields:

- `answerability`: required, one of `answerable | partial | insufficient`
- `answer`: required string, assembled from structured fields
- `summary`: required string
- `procedure_steps`: required string array, empty when no confirmed procedure exists
- `notes`: required string array
- `limitations`: required string array
- `sources`: required source array, empty when no displayed official source exists
- `conflict_warning`: required object with `exists: boolean` and optional `description`
- `freshness`: required, one of `recent | stale`
- `retrieval_status`: required object with retrieval and answer-quality diagnostics

The `answer` string is assembled from the structured fields in this order:

1. `summary`
2. `확인된 절차`
3. `준비/주의사항`
4. `확인이 필요한 점`

Empty sections are omitted.

### 2.5 UI Labels

The UI labels are:

- `answerable`: no special label
- `partial`: `일부 정보 확인됨`
- `insufficient`: `공식 문서 근거 부족`

The source panel title is `답변에 사용된 공식 문서`.

The empty source state is `답변에 사용된 공식 문서가 없습니다`.

The empty procedure state is `확인된 절차가 없습니다`.

The old empty procedure wording `별도 절차가 필요하지 않습니다` must not be used for unknown or insufficient cases.


## 3. Retrieval And Evidence Filtering

Retrieval results are candidates, not sources.

Before calling the LLM, backend code performs a conservative evidence filter:

1. Exclude results without URL or content.
2. Normalize question tokens.
3. Use a small academic-domain keyword dictionary.
4. Check overlap against title, menu path, and content.
5. Apply score thresholds.
6. Group duplicate document chunks.
7. Limit LLM evidence candidates to at most 4 source-numbered candidates.

Filter constants must be explicit, named, and covered by tests. Do not hide score thresholds, maximum candidate counts, or domain dictionary terms as undocumented inline values.

Default filter constants:

- `EVIDENCE_MAX_CANDIDATES = 4`
- `EVIDENCE_MIN_SCORE = 0.35` for merged hybrid scores normalized to `0..1`
- `EVIDENCE_MIN_DIRECT_OVERLAP = 1` normalized query keyword
- `EVIDENCE_PREVIEW_CHARS = 160`

Candidate acceptance rule:

1. Always reject missing URL or blank content.
2. Accept if the merged score is at least `EVIDENCE_MIN_SCORE`.
3. Accept if title, menu path, or content has at least `EVIDENCE_MIN_DIRECT_OVERLAP` normalized keyword overlap.
4. Reject when both score and overlap checks fail.

Duplicate grouping key:

```text
document_id if present, otherwise canonical URL
```

When several chunks belong to the same group, keep the highest scoring chunk as the display candidate. Additional chunks from the same document may be retained only as internal context, not as extra displayed sources.

The domain keyword dictionary starts with high-value academic words such as:

```text
휴학, 복학, 자퇴, 졸업, 장학, 등록금, 수강신청, 성적, 증명서
신청, 기간, 방법, 서류, 기준, 조건, 문의, 담당
```

Korean particles and common question endings are normalized before overlap checks. For example, `신청은` should match `신청`.

Dictionary changes belong near the evidence filter code and must include tests for at least one positive and one negative query example.

The first-pass filter decides topical relevance only. It does not decide whether a procedure can be answered. Procedure answerability is handled by the structured LLM judgment.

If retrieval returns no candidates, or evidence filtering removes every candidate, the backend must not call the LLM. It returns an `insufficient` response directly.

Default insufficient summary:

```text
검색된 공식 문서에서 답변 근거를 확인하지 못했습니다.
```

## 4. Question Intent

The backend classifies question intent lightly before prompt construction.

Initial intent values:

- `procedure`
- `factual`
- `deadline`
- `requirement`
- `contact`
- `unknown`

Questions containing words such as `어떻게`, `신청`, `절차`, or `방법` are treated as `procedure`.

For `procedure` questions, `procedure_steps` must contain only confirmed steps from official document evidence. If the evidence does not support a procedure, `procedure_steps` is empty and missing items are listed in `limitations`.

## 5. Prompt Design

Prompts must be file-based templates, not long hard-coded strings inside service code.

Recommended location:

```text
backend/app/prompts/chat_answer.md
```

The template contains:

- system behavior rules
- input variable placeholders
- output JSON schema
- answer style constraints
- one or two short good/bad examples

Prompt wording should keep answers short:

- `summary` is one or two concise sentences.
- `procedure_steps` includes only confirmed steps.
- `notes` includes only important confirmed notes.
- `limitations` lists missing key information.
- Each item is one sentence.

The backend must not mechanically cut off text by character count. Length and readability are controlled by prompt instructions first.

## 6. LLM Output Contract

The LLM must output JSON only.

Expected shape:

```json
{
  "answerability": "answerable | partial | insufficient",
  "summary": "string",
  "procedure_steps": ["string"],
  "notes": ["string"],
  "limitations": ["string"],
  "used_source_numbers": [1]
}
```

Natural-language parsing must not be used to infer procedure steps from the final answer. Procedure steps come from the structured JSON field.

The LLM output is not the final API response. The LLM never supplies `sources`, `freshness`, `conflict_warning`, or `retrieval_status`. Backend code validates `used_source_numbers`, builds final `sources`, assembles `answer`, and adds operational metadata.

### 6.1 JSON Failure

If JSON parsing or schema validation fails:

1. Retry once with a schema-repair instruction.
2. If it still fails, emit an `error` event with the safe user message below.

Safe user summary:

```text
답변을 확인하는 중 문제가 발생했습니다. 다시 질문해 주세요.
```

The unsafe raw model output must not be displayed.

JSON/schema failure means no validated final answer exists. It must not be mapped to `insufficient`, because `insufficient` is reserved for official-document evidence that is missing or inadequate. Log the internal reason as `json_validation_failed`, but show only the safe user message.

For JSON/schema failures, query-log `_meta.answerability` is `null` and `_meta.error_type` is `json_validation_failed`. This keeps runtime/schema failures separate from `insufficient` evidence judgments.

### 6.2 Used Source Validation

`used_source_numbers` is validated in code:

1. Remove values outside the candidate range.
2. Remove duplicates.
3. Force `[]` when `answerability` is `insufficient`.
4. If `answerable` or `partial` has no validated used source, downgrade to `insufficient`.
5. Build final `sources` only from validated used source numbers.

The answer body does not display source numbers. Source usage is internal and reflected only through the source panel.

Query-log `_meta.used_source_numbers` stores the validated LLM evidence candidate numbers before display-source remapping. It is intended for answer-quality review and may differ from the one-based order of displayed source cards.

## 7. Partial And Insufficient Answers

### 7.1 Partial

`partial` means official documents support only part of the answer.

The UI shows `일부 정보 확인됨`.

Only used sources are shown. Missing information is listed in `limitations`.

If a related department or contact-related fact is confirmed, it may appear in `notes`, but the system must not invent phone numbers, URLs, instructions, or offices not supported by the provided evidence.

Example wording:

```text
조직도에서 교무처 학사지원팀이 학사 관련 부서로 확인됩니다.
```

### 7.2 Insufficient

`insufficient` means the system cannot answer from official documents.

Rules:

- `sources` is empty.
- `procedure_steps` is empty.
- `summary` uses the short insufficient wording.
- `limitations` lists the important missing items when available.

For a procedure question such as `휴학 신청은 어떻게 하나요?`, if the retrieved evidence does not include the application process, `procedure_steps` remains empty.

## 8. SSE Contract

SSE may remain the transport, but its meaning changes from answer-token streaming to progress-state streaming.

Allowed events:

```text
event: status
data: {"step":"retrieving"}

event: status
data: {"step":"checking_evidence"}

event: status
data: {"step":"generating"}

event: status
data: {"step":"validating"}

event: done
data: {"answerability":"answerable", ...}
```

Failure:

```text
event: status
data: {"step":"retrieving"}

event: error
data: {"message":"답변 생성 중 오류가 발생했습니다.","retryable":true}
```

`status` events are optional and may occur zero or more times. Cache hits may return `done` immediately.

JSON/schema validation failure also uses the `error` event, but with this user message:

```text
답변을 확인하는 중 문제가 발생했습니다. 다시 질문해 주세요.
```

Runtime or infrastructure failures use the generic answer-generation error message.

### 8.1 Retrieval Status

`retrieval_status` is included in successful `done` payloads and query logs.

Required fields:

- `mode`: `hybrid | semantic_only | keyword_only | empty`
- `degraded`: boolean
- `semantic_available`: boolean
- `bm25_available`: boolean
- `semantic_error`: string or null
- `bm25_error`: string or null
- `evidence_candidate_count`: number
- `display_source_count`: number
- `answerability`: `answerable | partial | insufficient`

When no evidence candidate remains after filtering, `mode` may still describe the raw retrieval path, but `evidence_candidate_count` is `0`, `display_source_count` is `0`, and the final answerability is `insufficient`.

Removed events:

- `token`
- `procedure_steps`

The frontend maps status step enums to fixed Korean UI messages:

- `retrieving`: `공식 문서 검색 중`
- `checking_evidence`: `근거 확인 중`
- `generating`: `답변 작성 중`
- `validating`: `답변 검증 중`

## 9. Cache

Keep the current cache key version unless the project explicitly decides to change cache identity.

Instead, cached responses that lack the new required structured fields are treated as cache misses.

This avoids mixing old natural-language-only cached responses into the structured answer UI.

The required cache-hit field set is:

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

## 10. Query Logs

Query logs store both user-facing sources and retrieval candidates for quality review.

Recommended payload:

```json
{
  "_meta": {
    "status": "success",
    "cache_hit": false,
    "category": null,
    "normalized_query": "휴학 신청은 어떻게 하나요?",
    "answerability": "partial",
    "used_source_numbers": [1],
    "prompt_version": "chat-answer-json-v1",
    "retrieval_candidates": [
      {
        "chunk_id": "...",
        "title": "조직도",
        "url": "https://www.honam.ac.kr/OrganiChart",
        "score": 0.71,
        "chunk_type": "text",
        "preview": "### 교무처 / * 교무팀 / * 학사지원팀 ..."
      }
    ]
  },
  "items": [
    {
      "title": "조직도",
      "url": "https://www.honam.ac.kr/OrganiChart",
      "crawled_at": "2026-06-01T10:08:14.951433+00:00",
      "freshness": "recent",
      "chunk_id": "..."
    }
  ]
}
```

`items` contains only sources shown to users.

`retrieval_candidates` contains metadata and short previews only. Full chunk content remains in `document_chunks` and is reachable through `chunk_id`.

Preview rules:

- Collapse whitespace before storing the preview.
- Store at most 160 characters.
- Store at most 8 retrieval candidates.
- Keep the whole `sources` log payload under 32 KB.
- Do not store raw HTML, raw JSON payloads, or full table chunks as previews.
- Redact obvious personal identifiers from user query mirrors and previews before storage when detected, including phone numbers, email addresses, and resident-registration-number-like patterns.
- Query log retention is an operations policy, but this answer-quality path must keep payloads compact enough for routine pruning and admin review.

## 11. Application Criteria

The system satisfies this guideline only when:

1. The chat response includes the final response fields defined in this document.
2. Prompt content is loaded from a file-based template.
3. LLM output is parsed and validated as JSON.
4. Invalid JSON/schema output receives one repair attempt before the safe `error` response.
5. Evidence filtering runs before LLM calls.
6. `used_source_numbers` is validated in backend code.
7. Display sources are built only from validated used sources.
8. Requests with no evidence candidates return `insufficient` without calling the LLM.
9. Answer text token streaming is absent from the user-facing flow.
10. The `procedure_steps` SSE event is absent.
11. The frontend displays status messages and final-only answers.
12. The answer UI prefers structured fields over the legacy `answer` string.
13. The source panel title is `답변에 사용된 공식 문서`.
14. Empty procedure wording does not imply that no procedure is required.
15. Query logs separate display sources from retrieval candidate previews.
16. Cached payloads without required structured fields are treated as cache misses.
