# Campus Copilot — Phase 3 Kiosk/Admin Frontend Design

**Date:** 2026-05-06
**Phase:** Phase 3. 키오스크 / 관리자 프론트엔드
**Status:** Implemented baseline; UI polish remains iterative

## 1. Purpose

Phase 3의 목적은 Phase 2 crawling/parsing baseline 위에서 실제 사용 가능한 프론트엔드 동선을 완성하는 것이다. 이 단계는 키오스크 사용자가 학사 질문을 빠르게 입력하고 답변, 출처, 절차, 충돌 경고를 확인하는 화면과 운영자가 수집 상태, 수동 크롤링, 충돌, 로그를 확인하는 `/admin` 화면을 포함한다.

이 설계서는 기존 `2026-04-09-ui-ux-design.md`의 키오스크 UI 구조를 Phase 3 전체 범위로 확장한다. 세부 구현 순서와 파일 단위 작업은 `docs/superpowers/plans/2026-04-12-phase-3-kiosk-admin-frontend.md`에서 다룬다.

## 2. Source Documents

- `docs/superpowers/plans/2026-04-08-phase-roadmap.md`
- `docs/superpowers/specs/2026-04-08-architecture-design.md`
- `docs/superpowers/specs/2026-04-09-ui-ux-design.md`
- `docs/superpowers/specs/2026-04-19-phase-2-crawling-parsing-design.md`
- `docs/superpowers/plans/2026-04-19-phase-2-crawling-parsing-implementation.md`
- `docs/superpowers/plans/2026-04-08-phase-1-project-scaffold.md`
- `docs/superpowers/plans/2026-04-12-phase-3-kiosk-admin-frontend.md`

## 3. Scope

### Included

- 키오스크 `main`, `input`, `answer` 화면
- 카테고리 선택, FAQ 선택, 직접 질문 입력, 인기 질문 선택
- 답변, 출처, 절차, 충돌 경고, QR, TTS 진입점, 인쇄 액션 UI
- 30초 idle reset
- `/admin` 운영자 화면
- 관리자 상태, 수동 크롤링 요청, 충돌 목록, 질의 로그 표시
- 현재 stub API에서도 동작하는 프론트엔드 mock/fallback 데이터 계층
- TypeScript 타입, React Query 서버 상태, Zustand 키오스크 상태
- Phase 3 기준 단위 테스트, 타입 검사, 빌드, Docker Compose smoke 검증

### Excluded

- 실제 RAG 검색, 임베딩, LLM 응답 생성
- 실제 SSE streaming backend 구현
- `/api/v1/faq`, `/api/v1/popular` backend stub 라우트 추가
- 관리자 인증/권한
- 실제 Redis 기반 인기 질문 산출
- Raspberry Pi print-service 실기기 검증
- 운영 배포, HTTPS, 도메인, Pi 자동 시작

## 4. Phase Boundary Decisions

### 4.1 JSON Chat in Phase 3

상위 아키텍처는 최종 목표로 `POST /api/v1/chat` SSE streaming을 제시한다. 그러나 현재 백엔드의 `POST /api/v1/chat`은 JSON `ChatResponse` stub을 반환한다. Phase 3에서는 현재 API 현실에 맞춰 JSON chat client를 구현한다.

Phase 3 프론트엔드는 `useChat` 계층에서 JSON 응답을 `AnswerData`로 변환한다. 답변 화면은 `isStreaming` 이름의 loading flag를 유지해 Phase 4 SSE 전환 시 컴포넌트 변경을 줄인다. `@microsoft/fetch-event-source`와 `useSSEChat` 구현은 Phase 4에서 활성화한다.

### 4.2 Frontend Fallback for FAQ and Popular Questions

`GET /api/v1/faq`와 `GET /api/v1/popular`는 Phase 3에 backend stub 라우트를 추가하지 않는다. Phase 3에서는 프론트엔드 API 어댑터가 실제 endpoint를 먼저 호출하고, 404, 빈 배열, 네트워크 실패가 발생하면 fallback 데이터를 반환한다.

fallback 데이터는 UI 동선 검증용이며 실제 학사 데이터로 간주하지 않는다. 500 같은 서버 오류는 fallback을 제공하더라도 개발/운영자가 볼 수 있는 오류 상태를 함께 남긴다. 실제 FAQ/인기 질문 공급 방식은 Phase 4 검색/응답 생성 작업에서 확정한다.

`GET /api/v1/categories`는 현재 backend stub 라우트가 존재하지만 빈 배열을 반환할 수 있다. Phase 3 프론트엔드는 빈 배열, 404, 네트워크 실패를 fallback categories로 대체해 키오스크 초기 화면이 깨지지 않게 한다.

### 4.3 Admin Uses Existing Stub Routes

관리자 화면은 이미 존재하는 `/api/v1/admin/status`, `/api/v1/admin/crawl`, `/api/v1/admin/conflicts`, `/api/v1/admin/logs`를 사용한다. stub 응답과 빈 배열은 오류가 아니라 정상 빈 상태로 표시한다.

## 5. Kiosk Design

키오스크 화면 구조는 `2026-04-09-ui-ux-design.md`를 따른다.

### 5.1 Main Screen

- `HeaderBar`: 호남대학교와 서비스명을 표시한다.
- `CategoryBar`: 카테고리 목록과 "전체"를 표시한다. 선택 시 화면 전환 없이 FAQ만 갱신한다.
- `FAQGrid`: 3열 2행, 최대 6개 질문을 표시한다. 긴 텍스트는 말줄임 처리한다.
- `InputBar`: 하단 고정 `[마이크 | 입력창 | 전송]` 구조를 유지한다. 입력창 탭은 `input` 화면으로 전환하고, 마이크 버튼은 STT 진입점으로 동작한다. Phase 3에서는 메인 화면에서 직접 장문 입력을 처리하지 않고 입력 모드로 위임한다.

카테고리와 FAQ는 API 어댑터가 제공한다. `/api/v1/categories`가 빈 배열이면 fallback categories를 사용하고, `/api/v1/faq`가 없으면 fallback FAQ를 카테고리 기준으로 필터링한다.

### 5.2 Input Screen

- `SearchBar`: 뒤로가기, 입력창, 마이크 버튼을 제공한다.
- `PopularList`: 인기 질문 목록을 표시한다. 항목 탭은 입력창에 텍스트를 채우며 자동 전송하지 않는다.
- `VirtualKeyboard`: 한글 QWERTY 중심의 가상 키보드를 제공한다.

전송 버튼은 빈 입력에서 비활성화한다. Phase 3의 STT는 UI 진입점만 제공한다. 실제 Web Speech API 호출은 운영 HTTPS와 브라우저 지원을 확인한 뒤 후속 단계에서 활성화한다.

### 5.3 Answer Screen

- `QuestionBar`: 현재 질문과 처음으로 버튼을 표시한다.
- `AnswerPanel`: 답변 텍스트와 절차 단계를 표시한다.
- `SidePanel`: 출처, 충돌 경고, 인쇄/QR/TTS future-use 진입점 액션을 표시한다.

Phase 3에서는 JSON 응답을 한 번에 받아 표시한다. 로딩 중에는 답변 영역에 cursor/loading affordance를 보여준다. Phase 4 SSE 전환 시 동일한 `AnswerData` shape를 점진적으로 갱신하는 방식으로 확장한다.

### 5.4 QR, Print, and TTS Actions

- QR은 Phase 3에서 frontend-only로 생성한다. `react-qr-code`로 현재 질문과 답변을 확인할 수 있는 client-side 값 또는 URL을 표시하며, `/api/v1/qr` backend 호출은 사용하지 않는다.
- Print는 `POST http://localhost:6310/print`를 호출한다. Phase 3은 버튼, pending/failure 상태, payload shape까지만 고정하고 Raspberry Pi 실기기 출력은 Phase 5에서 검증한다.
- Print payload는 `{ question: string, answer: string, sources: Source[] }` 형태를 기본으로 한다.
- TTS는 Phase 3에서 UI 진입점만 제공하고 기본 OFF로 둔다. 실제 Web Speech API 호출과 idle reset/처음으로 이동 시 음성 정지는 운영 브라우저 지원을 확인한 뒤 후속 단계에서 활성화한다.

### 5.5 Idle Reset

30초 동안 `touchstart`, `click`, `keydown` 활동이 없으면 `resetToMain()`을 호출한다. reset은 다음 상태를 보장한다.

- `mode = 'main'`
- `selectedCategory = null`
- `currentQuery = ''`
- `answerData = null`
- 후속 TTS 활성화 시 이 reset 경계에서 음성 상태도 함께 정리
- 입력 모드의 local input state 초기화

## 6. Admin Design

`/admin`은 운영자가 반복적으로 확인하는 작업 화면이다. 마케팅성 hero가 아니라 상태와 조작을 바로 스캔할 수 있는 조용한 dashboard로 구성한다.

### 6.1 Panels

- `StatusPanel`
  - `documents`와 `last_crawled`를 표시한다.
  - `last_crawled === null`은 "아직 수집 기록 없음"으로 표시한다.

- `CrawlControl`
  - `POST /api/v1/admin/crawl`을 호출한다.
  - pending 중 버튼을 비활성화한다.
  - 성공 시 "크롤링 요청됨" 상태를 표시한다.
  - 성공 후 `admin-status`, `admin-logs` query를 invalidate한다.

- `ConflictTable`
  - 충돌 목록을 테이블로 표시한다.
  - 빈 배열은 "표시할 충돌 없음"으로 표시한다.

- `LogTable`
  - 질의 로그를 테이블로 표시한다.
  - 빈 배열은 "표시할 로그 없음"으로 표시한다.

### 6.2 Admin Error Handling

각 panel은 자신의 query 실패를 자기 영역 안에서 표시한다. 하나의 admin API 실패가 전체 `/admin` 화면 렌더링을 막지 않는다.

## 7. Data Contracts

### 7.1 Kiosk Types

```ts
type KioskMode = 'main' | 'input' | 'answer'

interface Category {
  id: string
  name: string
}

interface FAQItem {
  id: string
  question: string
  category_id: string
  priority?: number
}

interface PopularItem {
  rank: number
  question: string
  view_count: number
}

type SourceFreshness = 'recent' | 'stale'

interface Source {
  title: string
  url: string
  crawled_at: string
  freshness: SourceFreshness
}

interface ConflictWarning {
  exists: boolean
  description?: string
}

interface AnswerData {
  answer: string
  sources: Source[]
  procedureSteps: string[]
  conflictWarning: ConflictWarning | null
  isStreaming: boolean
}
```

### 7.2 Chat Mapping

현재 백엔드 `ChatResponse`는 source별 freshness가 아니라 top-level `freshness`를 가진다.

```ts
interface ChatResponsePayload {
  answer: string
  sources: Array<{
    title: string
    url: string
    crawled_at: string
  }>
  procedure_steps: string[]
  conflict_warning: ConflictWarning
  freshness: SourceFreshness
}
```

`useChat`은 `ChatResponsePayload.sources[]`에 top-level `freshness`를 주입해 UI용 `Source[]`로 변환한다.

백엔드가 `recent` 또는 `stale` 외의 freshness 문자열을 반환하면 UI는 `stale`로 보수적으로 처리하고, 개발 로그에 unknown freshness를 남긴다.

### 7.3 Admin Types

```ts
interface AdminStatus {
  documents: number
  last_crawled: string | null
}

interface AdminConflict {
  id: string
  chunk_a_id?: string
  chunk_b_id?: string
  conflict_type?: string
  severity?: string
  is_resolved?: boolean
  summary?: string
}

interface AdminLog {
  id: string
  query?: string
  answer?: string
  has_conflict?: boolean
  response_ms?: number
  created_at?: string | null
}
```

현재 backend stub이 빈 배열을 반환할 수 있으므로, Phase 3 UI는 빈 배열을 우선 지원한다. 실제 row가 들어올 경우 표시 후보는 Phase 2 DB 모델을 기준으로 한다.

| UI 영역 | Phase 2 DB 필드 기준 표시 후보 |
|---------|-------------------------------|
| ConflictTable | `conflict_type`, `severity`, `is_resolved`, `chunk_a_id`, `chunk_b_id` |
| LogTable | `query`, `has_conflict`, `response_ms`, `created_at` |

Phase 3은 위 필드를 표시 가능한 optional field로 취급한다. backend admin API의 최종 response schema는 Phase 4 이후 실제 query log/conflict 조회 구현에서 확정한다.

## 8. State and Data Flow

### 8.1 Kiosk State

Zustand store는 kiosk client state만 담당한다.

- 화면 모드
- 선택된 카테고리
- 현재 질문
- 답변 데이터
- reset action

서버 데이터는 React Query가 담당한다. categories, FAQ, popular, admin status, admin conflicts, admin logs는 query로 관리한다. crawl trigger는 mutation으로 관리한다.

### 8.2 Query Flow

FAQ 선택 또는 직접 입력 전송 시:

1. `submitQuery(question)`이 `currentQuery`를 저장하고 `mode`를 `answer`로 전환한다.
2. `useChat.submit(question)`이 `/api/v1/chat` JSON endpoint를 호출한다.
3. 응답을 `AnswerData`로 변환한다.
4. `AnswerScreen`이 answer/procedure/source/conflict/action UI를 표시한다.

## 9. Error and Empty States

- 키오스크 API fallback 대상은 categories, FAQ, popular이다.
- FAQ/popular fallback은 404, 빈 배열, 네트워크 실패에 적용한다. 500 계열 서버 오류는 fallback 표시와 함께 오류 상태를 기록한다.
- chat 실패는 빈 화면 대신 "답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."를 표시한다.
- admin status 실패는 status panel 안에서 오류를 표시한다.
- admin conflicts/logs 빈 배열은 정상 빈 상태로 표시한다.
- print-service 호출 실패는 action area 안에서 실패 상태를 표시한다.
- STT/TTS는 Phase 3에서 실제 Web Speech API를 호출하지 않는다. 버튼은 future-use 진입점으로 유지하고 사용자에게 준비 중 상태를 알려준다.

## 10. Accessibility and Kiosk UX

- 1280x800, 10.1인치 터치스크린 기준으로 첫 화면을 설계한다.
- 주요 터치 대상은 최소 64px 높이를 목표로 한다.
- 키보드/마우스 hover에 의존하지 않는다.
- 긴 질문, 출처 제목, 관리자 table cell은 말줄임 또는 wrapping으로 레이아웃을 깨지 않는다.
- idle reset 후 다음 사용자가 이전 사용자의 질문/답변을 보지 않게 한다. 후속 TTS 활성화 시 같은 reset 경계에서 음성 상태도 정리한다.

## 11. Verification

Phase 3 baseline 기준으로 다음을 확인했다.

- `npm run test:run` 통과: 24 files / 51 tests
- `npm run typecheck` 통과
- `npm run build` 통과
- `docker compose up --build` smoke 통과
- Docker smoke에서 `/`, `/admin`, `/api/v1/health` 응답 확인
- Docker smoke에서 frontend, backend, worker, postgres, redis, chromadb 서비스 기동 확인

다음 항목은 UI 초안 이후 반복 개선 시 계속 확인한다.

- `/` main → input → answer 동선 확인
- `/` FAQ 선택 → answer 동선 확인
- `/admin` status, conflicts, logs, crawl button 상태 확인
- FAQ/popular fallback 동작 확인
- chat freshness mapping과 unknown freshness fallback 확인
- QR modal frontend-only 표시 확인
- print-service 실패 상태 확인
- admin panel별 독립 실패 상태 확인
- 1280x800 viewport에서 텍스트 겹침과 터치 대상 확인
- 30초 idle reset과 TTS future-use 진입점 확인

## 12. Open Follow-Up for Phase 4

- `/api/v1/chat` SSE streaming 전환
- 실제 FAQ/popular 공급 방식 확정
- source별 freshness 또는 top-level freshness 계약 재검토
- 실제 query log row와 conflict row schema 확정
- Redis 기반 인기 질문 산출
- 운영 환경 HTTPS에서 STT 검증
