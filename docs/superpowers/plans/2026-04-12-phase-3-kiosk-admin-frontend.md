# Phase 3 Kiosk/Admin Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** UI/UX 설계서(2026-04-09)와 Phase Roadmap의 Phase 3 범위를 기반으로 키오스크 3-화면(main / input / answer), 관리자 화면(`/admin`), 전역 상태·훅·API 어댑터를 구현하여 `docker compose up` 상태에서 키오스크와 운영자 동선이 모두 동작하는 프론트엔드를 완성한다.

**Architecture:** Zustand 전역 스토어가 키오스크 화면 모드(`main|input|answer`)와 쿼리를 관리하고, `useIdleTimer` 훅이 30초 무조작 리셋을 담당한다. 키오스크 데이터는 API 어댑터가 실제 `/api/v1/*` 응답을 우선 사용하고, 현재 백엔드 stub 또는 미구현 엔드포인트에서는 화면 검증이 가능한 mock/fallback 데이터를 반환한다. `useChat` 계층은 Phase 3에서는 현재 `POST /api/v1/chat` JSON 응답을 기준으로 동작하며, Phase 4에서 SSE/RAG 응답이 활성화되면 `useSSEChat`으로 확장한다. 관리자 화면은 `/api/v1/admin/status`, `/crawl`, `/conflicts`, `/logs`를 React Query로 조회/실행하고 stub 응답에서도 빈 상태와 작업 트리거 상태를 명확히 보여준다.

**Tech Stack:** React 19 + TypeScript + Vite, Tailwind CSS v4, Zustand 5, @tanstack/react-query 5, react-simple-keyboard + hangul-js, react-qr-code, lucide-react, vitest + @testing-library/react + jsdom. `@microsoft/fetch-event-source`는 Phase 4 SSE 연동을 준비할 때 추가한다.

**Prerequisite:** Phase 1 scaffold와 Phase 2 worker crawling/parsing baseline 완료 상태 가정 — `frontend/` 디렉터리, `vite.config.ts`, `package.json`, `src/main.tsx`, `src/App.tsx`, `src/pages/KioskPage.tsx`, `src/pages/AdminPage.tsx` 존재. 현재 백엔드의 Phase 3 관련 라우트는 대부분 stub이며, Phase 3 프론트엔드는 실제 데이터 완성을 Phase 4 이후로 넘기고 사용자 동선·상태 표현·API 경계만 안정화한다.

**Current Implementation Status (2026-05-06):** Phase 3 baseline implementation is complete and committed in scoped frontend commits. `QueryClientProvider` is installed at `frontend/src/main.tsx`; `KioskPage` owns kiosk mode routing and idle reset only. STT/TTS are UI entry points with future-use comments and do not call browser Web Speech APIs. Verification passed with `npm run test:run` (24 files / 51 tests), `npm run typecheck`, `npm run build`, and `docker compose up --build` smoke for `/`, `/admin`, and backend health. The 1280x800 viewport/device pass remains a UI-iteration follow-up, not a completed automated check.

**Source Documents:**
- `docs/superpowers/plans/2026-04-08-phase-roadmap.md`
- `docs/superpowers/specs/2026-04-08-architecture-design.md`
- `docs/superpowers/specs/2026-04-09-ui-ux-design.md`
- `docs/superpowers/specs/2026-05-06-phase-3-kiosk-admin-frontend-design.md`
- `docs/superpowers/plans/2026-04-08-phase-1-project-scaffold.md`
- `docs/superpowers/specs/2026-04-19-phase-2-crawling-parsing-design.md`
- `docs/superpowers/plans/2026-04-19-phase-2-crawling-parsing-implementation.md`

---

## Phase 3 Scope Update

이 문서는 기존 키오스크 전용 초안을 Phase 3 프론트엔드 구현 계획으로 승격한 문서다. Phase 3의 완료 기준은 키오스크 화면만이 아니라 `/admin` 운영자 화면까지 포함한다.

**포함 범위:**
- 키오스크 카테고리 진입, FAQ 진입, 직접 질문 입력
- 답변 화면의 답변, 출처, 절차, 충돌 경고, 인쇄/QR/TTS 액션 UI
- 30초 idle reset 및 터치스크린 기준 레이아웃
- 관리자 상태, 수동 크롤링, 충돌 목록, 로그 조회 화면
- 현재 stub API에서도 동작하는 mock/fallback 데이터 계층

**제외 범위:**
- Phase 4의 실제 RAG 검색, 임베딩, LLM 응답 생성
- 실제 SSE 스트리밍 백엔드 구현
- 관리자 인증/권한
- Raspberry Pi print-service 실기기 검증

---

## ⚠️ Backend API Gaps

현재 백엔드에는 `/api/v1/chat`, `/api/v1/categories`, `/api/v1/recent`, `/api/v1/admin/status`, `/api/v1/admin/crawl`, `/api/v1/admin/conflicts`, `/api/v1/admin/logs` 라우트가 있으나 대부분 stub 응답이다. 아래 항목은 Phase 3 화면 동선에 필요하지만 백엔드 계약이 아직 충분하지 않으므로, 프론트엔드 API 계층에서 mock/fallback으로 대체한다.

**Phase 3 decision:** `GET /api/v1/faq`, `GET /api/v1/popular` 백엔드 stub 라우트는 Phase 3에 추가하지 않는다. Phase 3에서는 프론트엔드 fallback 데이터로 키오스크 화면 동선을 검증하고, 실제 FAQ/인기 질문 공급 방식은 Phase 4 검색/응답 생성 작업에서 확정한다.

| 엔드포인트 | 용도 | 조치 |
|------------|------|------|
| `GET /api/v1/categories` | 카테고리 목록 | backend stub이 존재한다. 빈 배열, 404, 네트워크 실패 시 mock 카테고리 사용 |
| `GET /api/v1/faq?category=<id>` | 카테고리별 FAQ 최대 6건 | Phase 3 backend에는 추가하지 않음; `api/faq.ts` 구현 + mock |
| `GET /api/v1/popular` | 인기 질문 목록 (순위 + 조회수) | Phase 3 backend에는 추가하지 않음; `api/popular.ts` 구현 + mock |
| `POST /api/v1/chat` | 질문 답변 | Phase 3에서는 JSON `ChatResponse` 기준; SSE는 Phase 4 확장 |
| `GET /api/v1/admin/*` | 운영 상태, 충돌, 로그 | stub 또는 빈 배열을 정상 빈 상태로 렌더링 |

---

## File Map

```
frontend/
├── package.json                              Modify: 의존성 추가 + test 스크립트
├── vite.config.ts                            Modify: vitest 설정 추가
├── src/
│   ├── main.tsx                              Modify: QueryClientProvider 설치
│   ├── test-setup.ts                         Create: @testing-library/jest-dom import
│   ├── types/
│   │   └── kiosk.ts                          Create: 공유 타입 정의
│   ├── store/
│   │   ├── kioskStore.ts                     Create: Zustand 스토어
│   │   └── kioskStore.test.ts                Create: 스토어 단위 테스트
│   ├── hooks/
│   │   ├── useIdleTimer.ts                   Create: 30초 idle 리셋 훅
│   │   ├── useIdleTimer.test.ts              Create
│   │   ├── useChat.ts                        Create: Phase 3 JSON chat 훅
│   │   └── useChat.test.ts                   Create
│   ├── api/
│   │   ├── categories.ts                     Create: GET /api/v1/categories
│   │   ├── faq.ts                            Create: GET /api/v1/faq?category=<id>
│   │   ├── popular.ts                        Create: GET /api/v1/popular
│   │   ├── chat.ts                           Create: POST /api/v1/chat JSON client
│   │   └── admin.ts                          Create: GET/POST /api/v1/admin/* client
│   ├── pages/
│   │   ├── KioskPage.tsx                     Modify: mode 라우터 + idle
│   │   └── AdminPage.tsx                     Modify: 관리자 dashboard 조립
│   └── components/
│       ├── admin/
│       │   ├── StatusPanel.tsx               Create: 문서 수 / 마지막 크롤링 / 상태
│       │   ├── CrawlControl.tsx              Create: 수동 크롤링 버튼 + 결과 상태
│       │   ├── ConflictTable.tsx             Create: 충돌 목록 빈 상태 포함
│       │   └── LogTable.tsx                  Create: 질의 로그 빈 상태 포함
│       └── kiosk/
│           ├── MainScreen.tsx                Create: 메인 화면 조립
│           ├── InputMode.tsx                 Create: 입력 모드 조립
│           ├── AnswerScreen.tsx              Create: 답변 화면 조립
│           ├── main/
│           │   ├── HeaderBar.tsx             Create
│           │   ├── CategoryBar.tsx           Create
│           │   ├── FAQGrid.tsx               Create
│           │   └── InputBar.tsx              Create
│           ├── input/
│           │   ├── SearchBar.tsx             Create
│           │   ├── PopularList.tsx           Create
│           │   └── VirtualKeyboard.tsx       Create
│           └── answer/
│               ├── QuestionBar.tsx           Create
│               ├── AnswerPanel.tsx           Create
│               ├── AnswerText.tsx            Create
│               ├── ProcedureSteps.tsx        Create
│               ├── SidePanel.tsx             Create
│               ├── SourceList.tsx            Create
│               ├── ConflictWarning.tsx       Create
│               ├── ActionBar.tsx             Create: TTS future-use 진입점 포함
│               └── QRModal.tsx               Create
```

---

## Task 1: 의존성 + 테스트 환경 설정

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/test-setup.ts`

- [ ] **Step 1: 런타임 의존성 설치**

```bash
cd frontend
npm install zustand @tanstack/react-query \
  react-simple-keyboard hangul-js react-qr-code lucide-react
```

Expected: `node_modules/zustand`, `node_modules/react-simple-keyboard` 등 생성

- [ ] **Step 2: 개발/테스트 의존성 설치**

```bash
npm install -D vitest @testing-library/react @testing-library/user-event \
  @testing-library/jest-dom jsdom @vitest/coverage-v8
```

Expected: `node_modules/vitest` 생성

- [ ] **Step 3: `vite.config.ts`에 vitest 설정 추가**

```ts
/// <reference types="vitest" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test-setup.ts'],
    },
  }
})
```

- [ ] **Step 4: `src/test-setup.ts` 작성**

```ts
import '@testing-library/jest-dom'
```

- [ ] **Step 5: `package.json` scripts에 test 추가**

`"scripts"` 섹션에 추가:
```json
"test": "vitest",
"test:run": "vitest run"
```

- [ ] **Step 6: 빈 테스트로 환경 동작 확인**

```bash
# 임시 smoke 테스트
echo 'import { describe, it, expect } from "vitest"; describe("smoke", () => { it("works", () => expect(1).toBe(1)); });' > src/smoke.test.ts
npm run test:run -- src/smoke.test.ts
```

Expected:
```
✓ src/smoke.test.ts (1)
  ✓ smoke > works
Test Files  1 passed (1)
```

- [ ] **Step 7: smoke 파일 삭제 후 커밋**

```bash
rm src/smoke.test.ts
git add package.json vite.config.ts src/test-setup.ts
git commit -m "chore(frontend): add vitest and kiosk runtime dependencies

- install zustand, react-query, react-simple-keyboard
- install hangul-js, react-qr-code, lucide-react
- configure vitest with jsdom and @testing-library/jest-dom

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 2: 공유 타입 정의

**Files:**
- Create: `frontend/src/types/kiosk.ts`

- [ ] **Step 1: 타입 파일 작성**

```ts
// frontend/src/types/kiosk.ts

export type KioskMode = 'main' | 'input' | 'answer';

export interface Category {
  id: string;
  name: string;
}

export interface FAQItem {
  id: string;
  question: string;
  category_id: string;
  priority?: number;
}

export interface PopularItem {
  rank: number;
  question: string;
  view_count: number;
}

export type SourceFreshness = 'recent' | 'stale';

export function normalizeFreshness(value: string): SourceFreshness {
  return value === 'recent' || value === 'stale' ? value : 'stale';
}

export interface Source {
  title: string;
  url: string;
  crawled_at: string;
  freshness: string;
}

export interface ConflictWarning {
  exists: boolean;
  description?: string;
}

export interface AnswerData {
  answer: string;
  sources: Source[];
  procedureSteps: string[];
  conflictWarning: ConflictWarning | null;
  isStreaming: boolean;
}

export interface ChatRequestPayload {
  question: string;
  category?: string | null;
}

export interface ChatResponsePayload {
  answer: string;
  sources: Array<{
    title: string;
    url: string;
    crawled_at: string;
  }>;
  procedure_steps: string[];
  conflict_warning: ConflictWarning;
  freshness: SourceFreshness;
}
```

- [ ] **Step 2: TypeScript 타입 검사**

```bash
npx tsc --noEmit
```

Expected: 오류 없음

- [ ] **Step 3: 커밋**

```bash
git add src/types/kiosk.ts
git commit -m "feat(frontend): add shared kiosk TypeScript types

- KioskMode, Category, FAQItem, PopularItem
- Source, ConflictWarning, AnswerData

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 3: Zustand 스토어

**Files:**
- Create: `frontend/src/store/kioskStore.ts`
- Create: `frontend/src/store/kioskStore.test.ts`

- [ ] **Step 1: 실패 테스트 작성**

```ts
// frontend/src/store/kioskStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useKioskStore } from './kioskStore'

const initialState = {
  mode: 'main' as const,
  selectedCategory: null,
  currentQuery: '',
  answerData: null,
}

beforeEach(() => {
  useKioskStore.setState(initialState)
})

describe('kioskStore', () => {
  it('has correct initial state', () => {
    const state = useKioskStore.getState()
    expect(state.mode).toBe('main')
    expect(state.selectedCategory).toBeNull()
    expect(state.currentQuery).toBe('')
    expect(state.answerData).toBeNull()
  })

  it('setMode changes mode', () => {
    useKioskStore.getState().setMode('input')
    expect(useKioskStore.getState().mode).toBe('input')
  })

  it('setCategory updates selectedCategory', () => {
    useKioskStore.getState().setCategory('admission')
    expect(useKioskStore.getState().selectedCategory).toBe('admission')
  })

  it('setCategory accepts null for 전체', () => {
    useKioskStore.getState().setCategory('admission')
    useKioskStore.getState().setCategory(null)
    expect(useKioskStore.getState().selectedCategory).toBeNull()
  })

  it('submitQuery sets currentQuery and mode to answer', () => {
    useKioskStore.getState().submitQuery('휴학 신청 방법')
    const state = useKioskStore.getState()
    expect(state.currentQuery).toBe('휴학 신청 방법')
    expect(state.mode).toBe('answer')
  })

  it('setAnswerData updates answerData', () => {
    const data = {
      answer: '안녕하세요',
      sources: [],
      procedureSteps: [],
      conflictWarning: null,
      isStreaming: true,
    }
    useKioskStore.getState().setAnswerData(data)
    expect(useKioskStore.getState().answerData).toEqual(data)
  })

  it('setAnswerData accepts functional updater', () => {
    useKioskStore.getState().setAnswerData({
      answer: '안녕',
      sources: [],
      procedureSteps: [],
      conflictWarning: null,
      isStreaming: true,
    })
    useKioskStore.getState().setAnswerData(prev =>
      prev ? { ...prev, answer: prev.answer + '하세요' } : null
    )
    expect(useKioskStore.getState().answerData?.answer).toBe('안녕하세요')
  })

  it('resetToMain resets all state', () => {
    useKioskStore.getState().setMode('answer')
    useKioskStore.getState().setCategory('admission')
    useKioskStore.getState().submitQuery('테스트')
    useKioskStore.getState().resetToMain()
    const state = useKioskStore.getState()
    expect(state.mode).toBe('main')
    expect(state.selectedCategory).toBeNull()
    expect(state.currentQuery).toBe('')
    expect(state.answerData).toBeNull()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/store/kioskStore.test.ts
```

Expected: FAIL — `kioskStore` not found

- [ ] **Step 3: 스토어 구현**

```ts
// frontend/src/store/kioskStore.ts
import { create } from 'zustand'
import type { KioskMode, AnswerData } from '../types/kiosk'

interface KioskStore {
  mode: KioskMode
  selectedCategory: string | null
  currentQuery: string
  answerData: AnswerData | null
  idleTimer: ReturnType<typeof setTimeout> | null

  setMode: (mode: KioskMode) => void
  setCategory: (cat: string | null) => void
  submitQuery: (query: string) => void
  setAnswerData: (
    data: AnswerData | null | ((prev: AnswerData | null) => AnswerData | null)
  ) => void
  resetToMain: () => void
  setIdleTimer: (timer: ReturnType<typeof setTimeout> | null) => void
}

export const useKioskStore = create<KioskStore>((set) => ({
  mode: 'main',
  selectedCategory: null,
  currentQuery: '',
  answerData: null,
  idleTimer: null,

  setMode: (mode) => set({ mode }),
  setCategory: (selectedCategory) => set({ selectedCategory }),
  submitQuery: (query) => set({ currentQuery: query, mode: 'answer' }),
  setAnswerData: (data) =>
    set((state) => ({
      answerData: typeof data === 'function' ? data(state.answerData) : data,
    })),
  resetToMain: () => {
    // Future TTS integration should stop active speech here before clearing state.
    set({
      mode: 'main',
      selectedCategory: null,
      currentQuery: '',
      answerData: null,
    })
  },
  setIdleTimer: (idleTimer) => set({ idleTimer }),
}))
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/store/kioskStore.test.ts
```

Expected:
```
✓ src/store/kioskStore.test.ts (8)
Test Files  1 passed (1)
```

- [ ] **Step 5: 커밋**

```bash
git add src/store/kioskStore.ts src/store/kioskStore.test.ts
git commit -m "feat(frontend): implement Zustand kiosk store

- mode, selectedCategory, currentQuery, answerData state
- setAnswerData supports functional updater for later streaming expansion
- resetToMain clears all kiosk state; future TTS stop belongs at this boundary

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 4: `useIdleTimer` 훅

**Files:**
- Create: `frontend/src/hooks/useIdleTimer.ts`
- Create: `frontend/src/hooks/useIdleTimer.test.ts`

- [ ] **Step 1: 실패 테스트 작성**

```ts
// frontend/src/hooks/useIdleTimer.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useIdleTimer } from './useIdleTimer'

const IDLE_MS = 30_000

describe('useIdleTimer', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('fires callback after 30 seconds', () => {
    const onIdle = vi.fn()
    renderHook(() => useIdleTimer(onIdle))
    act(() => vi.advanceTimersByTime(IDLE_MS))
    expect(onIdle).toHaveBeenCalledTimes(1)
  })

  it('does not fire before 30 seconds', () => {
    const onIdle = vi.fn()
    renderHook(() => useIdleTimer(onIdle))
    act(() => vi.advanceTimersByTime(IDLE_MS - 1))
    expect(onIdle).not.toHaveBeenCalled()
  })

  it('resets timer on touchstart', () => {
    const onIdle = vi.fn()
    renderHook(() => useIdleTimer(onIdle))
    act(() => vi.advanceTimersByTime(20_000))
    act(() => { document.dispatchEvent(new Event('touchstart')) })
    act(() => vi.advanceTimersByTime(20_000))
    expect(onIdle).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(10_001))
    expect(onIdle).toHaveBeenCalledTimes(1)
  })

  it('resets timer on click', () => {
    const onIdle = vi.fn()
    renderHook(() => useIdleTimer(onIdle))
    act(() => vi.advanceTimersByTime(25_000))
    act(() => { document.dispatchEvent(new Event('click')) })
    act(() => vi.advanceTimersByTime(25_000))
    expect(onIdle).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(5_001))
    expect(onIdle).toHaveBeenCalledTimes(1)
  })

  it('cleans up on unmount', () => {
    const onIdle = vi.fn()
    const { unmount } = renderHook(() => useIdleTimer(onIdle))
    unmount()
    act(() => vi.advanceTimersByTime(IDLE_MS))
    expect(onIdle).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/hooks/useIdleTimer.test.ts
```

Expected: FAIL — `useIdleTimer` not found

- [ ] **Step 3: 훅 구현**

```ts
// frontend/src/hooks/useIdleTimer.ts
import { useEffect, useRef, useCallback } from 'react'

const IDLE_TIMEOUT_MS = 30_000
const ACTIVITY_EVENTS = ['touchstart', 'click', 'keydown'] as const

export function useIdleTimer(onIdle: () => void) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onIdleRef = useRef(onIdle)
  onIdleRef.current = onIdle

  const reset = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => onIdleRef.current(), IDLE_TIMEOUT_MS)
  }, [])

  useEffect(() => {
    reset()
    ACTIVITY_EVENTS.forEach((ev) => document.addEventListener(ev, reset))
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      ACTIVITY_EVENTS.forEach((ev) => document.removeEventListener(ev, reset))
    }
  }, [reset])
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/hooks/useIdleTimer.test.ts
```

Expected:
```
✓ src/hooks/useIdleTimer.test.ts (5)
Test Files  1 passed (1)
```

- [ ] **Step 5: 커밋**

```bash
git add src/hooks/useIdleTimer.ts src/hooks/useIdleTimer.test.ts
git commit -m "feat(frontend): implement useIdleTimer hook

- fires onIdle callback after 30s of inactivity
- resets on touchstart, click, keydown
- cleans up timer and event listeners on unmount

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 5: API 함수

**Files:**
- Create: `frontend/src/api/categories.ts`
- Create: `frontend/src/api/faq.ts`
- Create: `frontend/src/api/popular.ts`

**Phase 3 adjustment:** 모든 API 함수는 실제 응답을 우선 사용하되, 현재 백엔드가 stub/빈 배열/404를 반환하거나 네트워크 실패가 발생하면 mock/fallback을 반환한다. 500 계열 서버 오류는 fallback과 함께 개발자가 볼 수 있는 오류 로그를 남긴다. 이 fallback은 Phase 4 API 구현 후 제거 가능한 얇은 어댑터로 둔다.

- [ ] **Step 1: 실패 테스트 작성**

```ts
// frontend/src/api/categories.test.ts
import { describe, it, expect, vi, afterEach } from 'vitest'
import { fetchCategories } from './categories'
import { fetchFAQ } from './faq'
import { fetchPopular } from './popular'
import type { Category, FAQItem, PopularItem } from '../types/kiosk'

afterEach(() => vi.restoreAllMocks())

describe('fetchCategories', () => {
  it('calls GET /api/v1/categories and returns API array', async () => {
    const mock: Category[] = [{ id: 'admission', name: '학사행정' }]
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mock,
    } as Response)
    const result = await fetchCategories()
    expect(fetch).toHaveBeenCalledWith('/api/v1/categories')
    expect(result).toEqual(mock)
  })

  it('uses fallback categories when backend returns empty array', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response)
    const result = await fetchCategories()
    expect(result.length).toBeGreaterThan(0)
    expect(result[0]).toHaveProperty('id')
  })

  it('uses fallback categories on 404 response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
    } as Response)
    const result = await fetchCategories()
    expect(result.length).toBeGreaterThan(0)
  })
})

describe('fetchFAQ', () => {
  it('calls GET /api/v1/faq with category param', async () => {
    const mock: FAQItem[] = [{ id: '1', question: '휴학 방법?', category_id: 'admission' }]
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mock,
    } as Response)
    const result = await fetchFAQ('admission')
    expect(fetch).toHaveBeenCalledWith('/api/v1/faq?category=admission')
    expect(result).toEqual(mock)
  })

  it('calls GET /api/v1/faq without param when null', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response)
    await fetchFAQ(null)
    expect(fetch).toHaveBeenCalledWith('/api/v1/faq')
  })

  it('uses fallback FAQ on 404 because backend route is not implemented in Phase 3', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 404 } as Response)
    const result = await fetchFAQ(null)
    expect(result.length).toBeGreaterThan(0)
  })
})

describe('fetchPopular', () => {
  it('calls GET /api/v1/popular and returns array', async () => {
    const mock: PopularItem[] = [{ rank: 1, question: '등록금 납부 기간?', view_count: 312 }]
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mock,
    } as Response)
    const result = await fetchPopular()
    expect(fetch).toHaveBeenCalledWith('/api/v1/popular')
    expect(result).toEqual(mock)
  })

  it('uses fallback popular questions on 404 because backend route is not implemented in Phase 3', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 404 } as Response)
    const result = await fetchPopular()
    expect(result.length).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/api/categories.test.ts
```

Expected: FAIL — modules not found

- [ ] **Step 3: API 함수 구현**

```ts
// frontend/src/api/mockKioskData.ts
import type { Category, FAQItem, PopularItem } from '../types/kiosk'

export const fallbackCategories: Category[] = [
  { id: 'academic', name: '학사행정' },
  { id: 'scholarship', name: '장학·등록' },
  { id: 'facility', name: '시설·부서' },
  { id: 'career', name: '취업·진로' },
]

export const fallbackFAQ: FAQItem[] = [
  { id: 'faq-1', question: '휴학 신청은 어디에서 하나요?', category_id: 'academic', priority: 1 },
  { id: 'faq-2', question: '등록금 납부 기간은 언제인가요?', category_id: 'scholarship', priority: 2 },
  { id: 'faq-3', question: '증명서는 어디에서 발급하나요?', category_id: 'academic', priority: 3 },
  { id: 'faq-4', question: '생활관 문의는 어디로 하나요?', category_id: 'facility', priority: 4 },
  { id: 'faq-5', question: '취업 상담은 어떻게 신청하나요?', category_id: 'career', priority: 5 },
  { id: 'faq-6', question: '장학금 신청 조건은 무엇인가요?', category_id: 'scholarship', priority: 6 },
]

export const fallbackPopular: PopularItem[] = [
  { rank: 1, question: '휴학 신청 방법은?', view_count: 312 },
  { rank: 2, question: '등록금 납부 기간은?', view_count: 251 },
  { rank: 3, question: '증명서 발급 위치는?', view_count: 198 },
]
```

```ts
// frontend/src/api/categories.ts
import type { Category } from '../types/kiosk'
import { fallbackCategories } from './mockKioskData'

export async function fetchCategories(): Promise<Category[]> {
  try {
    const res = await fetch('/api/v1/categories')
    if (!res.ok) {
      if (res.status >= 500) console.error(`categories fetch failed: ${res.status}`)
      return fallbackCategories
    }
    const data = await res.json() as Category[]
    return data.length > 0 ? data : fallbackCategories
  } catch {
    return fallbackCategories
  }
}
```

```ts
// frontend/src/api/faq.ts
// NOTE: GET /api/v1/faq 는 아키텍처 설계서에 미포함 — 백엔드 추가 필요
import type { FAQItem } from '../types/kiosk'
import { fallbackFAQ } from './mockKioskData'

export async function fetchFAQ(categoryId: string | null): Promise<FAQItem[]> {
  const url = categoryId
    ? `/api/v1/faq?category=${encodeURIComponent(categoryId)}`
    : '/api/v1/faq'
  try {
    const res = await fetch(url)
    if (!res.ok) {
      if (res.status >= 500) console.error(`faq fetch failed: ${res.status}`)
      return fallbackFAQ.filter((item) => !categoryId || item.category_id === categoryId).slice(0, 6)
    }
    const data = await res.json() as FAQItem[]
    const fallback = fallbackFAQ.filter((item) => !categoryId || item.category_id === categoryId).slice(0, 6)
    return data.length > 0 ? data : fallback
  } catch {
    return fallbackFAQ.filter((item) => !categoryId || item.category_id === categoryId).slice(0, 6)
  }
}
```

```ts
// frontend/src/api/popular.ts
// NOTE: GET /api/v1/popular 는 아키텍처 설계서에 미포함 — 백엔드 추가 필요
import type { PopularItem } from '../types/kiosk'
import { fallbackPopular } from './mockKioskData'

export async function fetchPopular(): Promise<PopularItem[]> {
  try {
    const res = await fetch('/api/v1/popular')
    if (!res.ok) {
      if (res.status >= 500) console.error(`popular fetch failed: ${res.status}`)
      return fallbackPopular
    }
    const data = await res.json() as PopularItem[]
    return data.length > 0 ? data : fallbackPopular
  } catch {
    return fallbackPopular
  }
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/api/categories.test.ts
```

Expected:
```
✓ src/api/categories.test.ts (7)
Test Files  1 passed (1)
```

- [ ] **Step 5: 커밋**

```bash
git add src/api/mockKioskData.ts src/api/categories.ts src/api/faq.ts src/api/popular.ts src/api/categories.test.ts
git commit -m "feat(frontend): add API fetch functions for categories, faq, popular

- fetchCategories: GET /api/v1/categories with stub fallback
- fetchFAQ: GET /api/v1/faq?category=<id> with backend-gap fallback
- fetchPopular: GET /api/v1/popular with backend-gap fallback

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 6: `useChat` 훅

**Files:**
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/api/chat.test.ts`
- Create: `frontend/src/hooks/useChat.ts`
- Create: `frontend/src/hooks/useChat.test.ts`

**Phase 3 adjustment:** SSE 훅은 Phase 4 RAG/SSE 연동 시점으로 미룬다. Phase 3에서는 현재 백엔드 스키마(`ChatRequest.question`, `ChatResponse.answer/sources/procedure_steps/conflict_warning/freshness`)에 맞춰 JSON `POST /api/v1/chat`을 호출하고, 응답을 `AnswerData` 형태로 변환한다. 로딩 중에는 `isStreaming: true`를 사용해 동일한 답변 화면 컴포넌트를 재사용한다.

- [ ] **Step 1: API 실패 테스트 작성**

```ts
// frontend/src/api/chat.test.ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { postChat } from './chat'

afterEach(() => vi.restoreAllMocks())

describe('postChat', () => {
  it('calls POST /api/v1/chat with question', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        answer: 'stub response',
        sources: [],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: 'recent',
      }),
    } as Response)
    await postChat({ question: '휴학 신청' })
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/chat',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: '휴학 신청' }),
      })
    )
  })

  it('throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 500 } as Response)
    await expect(postChat({ question: '휴학 신청' })).rejects.toThrow('chat fetch failed: 500')
  })
})
```

- [ ] **Step 2: API 테스트 실패 확인**

```bash
npm run test:run -- src/api/chat.test.ts
```

Expected: FAIL — `chat` module not found

- [ ] **Step 3: API 구현**

```ts
// frontend/src/api/chat.ts
import type { ChatRequestPayload, ChatResponsePayload } from '../types/kiosk'

export async function postChat(payload: ChatRequestPayload): Promise<ChatResponsePayload> {
  const res = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`chat fetch failed: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 4: 훅 실패 테스트 작성**

```ts
// frontend/src/hooks/useChat.test.ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useChat } from './useChat'
import { useKioskStore } from '../store/kioskStore'

vi.mock('../api/chat', () => ({
  postChat: vi.fn(),
}))

import { postChat } from '../api/chat'

beforeEach(() => {
  useKioskStore.setState({
    mode: 'main',
    selectedCategory: null,
    currentQuery: '',
    answerData: null,
    idleTimer: null,
  })
  vi.clearAllMocks()
})

describe('useChat', () => {
  it('maps ChatResponse into AnswerData with source freshness', async () => {
    vi.mocked(postChat).mockResolvedValue({
      answer: '휴학은 포털에서 신청합니다.',
      sources: [{ title: '학사안내', url: 'https://example.edu', crawled_at: '2026-04-19' }],
      procedure_steps: ['포털 접속', '휴학 신청'],
      conflict_warning: { exists: false },
      freshness: 'recent',
    })
    const { result } = renderHook(() => useChat())
    await act(async () => { await result.current.submit('휴학 신청') })
    expect(useKioskStore.getState().answerData).toEqual({
      answer: '휴학은 포털에서 신청합니다.',
      sources: [{ title: '학사안내', url: 'https://example.edu', crawled_at: '2026-04-19', freshness: 'recent' }],
      procedureSteps: ['포털 접속', '휴학 신청'],
      conflictWarning: { exists: false },
      isStreaming: false,
    })
  })

  it('sets fallback error answer when request fails', async () => {
    vi.mocked(postChat).mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useChat())
    await act(async () => { await result.current.submit('휴학 신청') })
    expect(useKioskStore.getState().answerData?.isStreaming).toBe(false)
    expect(useKioskStore.getState().answerData?.answer).toContain('답변을 불러오지 못했습니다')
  })
})
```

- [ ] **Step 5: 훅 구현**

```ts
// frontend/src/hooks/useChat.ts
import { useCallback } from 'react'
import { postChat } from '../api/chat'
import { useKioskStore } from '../store/kioskStore'
import { normalizeFreshness } from '../types/kiosk'

export function useChat() {
  const setAnswerData = useKioskStore((s) => s.setAnswerData)

  const submit = useCallback(
    async (question: string) => {
      setAnswerData({
        answer: '',
        sources: [],
        procedureSteps: [],
        conflictWarning: null,
        isStreaming: true,
      })

      try {
        const response = await postChat({ question })
        setAnswerData({
          answer: response.answer,
          sources: response.sources.map((source) => ({
            ...source,
            freshness: normalizeFreshness(response.freshness),
          })),
          procedureSteps: response.procedure_steps,
          conflictWarning: response.conflict_warning,
          isStreaming: false,
        })
      } catch {
        setAnswerData({
          answer: '답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.',
          sources: [],
          procedureSteps: [],
          conflictWarning: null,
          isStreaming: false,
        })
      }
    },
    [setAnswerData]
  )

  return { submit }
}
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
npm run test:run -- src/api/chat.test.ts src/hooks/useChat.test.ts
```

Expected:
```
✓ src/api/chat.test.ts (2)
✓ src/hooks/useChat.test.ts (2)
Test Files  2 passed
```

- [ ] **Step 7: 커밋**

```bash
git add src/api/chat.ts src/api/chat.test.ts src/hooks/useChat.ts src/hooks/useChat.test.ts
git commit -m "feat(frontend): implement JSON chat hook

- call POST /api/v1/chat with current backend schema
- map ChatResponse into kiosk AnswerData
- handle failed requests with a visible fallback answer

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 7: `KioskPage` 모드 라우터

**Files:**
- Modify: `frontend/src/pages/KioskPage.tsx`
- Create: `frontend/src/pages/KioskPage.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/pages/KioskPage.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useKioskStore } from '../store/kioskStore'
import KioskPage from './KioskPage'

// 화면 컴포넌트를 stub으로 대체
vi.mock('../components/kiosk/MainScreen', () => ({
  MainScreen: () => <div data-testid="main-screen" />,
}))
vi.mock('../components/kiosk/InputMode', () => ({
  InputMode: () => <div data-testid="input-mode" />,
}))
vi.mock('../components/kiosk/AnswerScreen', () => ({
  AnswerScreen: () => <div data-testid="answer-screen" />,
}))

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('KioskPage', () => {
  it('renders MainScreen when mode is main', () => {
    useKioskStore.setState({ mode: 'main' })
    render(<KioskPage />, { wrapper })
    expect(screen.getByTestId('main-screen')).toBeInTheDocument()
    expect(screen.queryByTestId('input-mode')).not.toBeInTheDocument()
    expect(screen.queryByTestId('answer-screen')).not.toBeInTheDocument()
  })

  it('renders InputMode when mode is input', () => {
    useKioskStore.setState({ mode: 'input' })
    render(<KioskPage />, { wrapper })
    expect(screen.getByTestId('input-mode')).toBeInTheDocument()
  })

  it('renders AnswerScreen when mode is answer', () => {
    useKioskStore.setState({ mode: 'answer' })
    render(<KioskPage />, { wrapper })
    expect(screen.getByTestId('answer-screen')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/pages/KioskPage.test.tsx
```

Expected: FAIL — stub 컴포넌트 없음 또는 KioskPage가 모드 분기 없음

- [ ] **Step 3: `KioskPage` 구현**

```tsx
// frontend/src/pages/KioskPage.tsx
import { useKioskStore } from '../store/kioskStore'
import { useIdleTimer } from '../hooks/useIdleTimer'
import { MainScreen } from '../components/kiosk/MainScreen'
import { InputMode } from '../components/kiosk/InputMode'
import { AnswerScreen } from '../components/kiosk/AnswerScreen'

export default function KioskPage() {
  const mode = useKioskStore((s) => s.mode)
  const resetToMain = useKioskStore((s) => s.resetToMain)

  useIdleTimer(() => {
    // Future TTS integration should stop active speech as part of idle reset.
    resetToMain()
  })

  return (
    <main className="h-screen w-screen overflow-hidden">
      {mode === 'main' && <MainScreen />}
      {mode === 'input' && <InputMode />}
      {mode === 'answer' && <AnswerScreen />}
    </main>
  )
}
```

`QueryClientProvider`는 실제 구현에서 `frontend/src/main.tsx`의 app root에 설치되어 `KioskPage`와 `AdminPage`가 같은 React Query client를 공유한다.

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/pages/KioskPage.test.tsx
```

Expected:
```
✓ src/pages/KioskPage.test.tsx (3)
Test Files  1 passed (1)
```

- [ ] **Step 5: 커밋**

```bash
git add src/pages/KioskPage.tsx src/pages/KioskPage.test.tsx
git commit -m "feat(frontend): implement KioskPage mode router

- renders MainScreen / InputMode / AnswerScreen based on store.mode
- uses app-root QueryClientProvider from frontend/src/main.tsx
- activates 30s idle reset via useIdleTimer

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 8: `HeaderBar` + `InputBar`

**Files:**
- Create: `frontend/src/components/kiosk/main/HeaderBar.tsx`
- Create: `frontend/src/components/kiosk/main/HeaderBar.test.tsx`
- Create: `frontend/src/components/kiosk/main/InputBar.tsx`
- Create: `frontend/src/components/kiosk/main/InputBar.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/components/kiosk/main/HeaderBar.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { HeaderBar } from './HeaderBar'

describe('HeaderBar', () => {
  it('renders service name', () => {
    render(<HeaderBar />)
    expect(screen.getByText('캠퍼스 코파일럿')).toBeInTheDocument()
  })
})
```

```tsx
// frontend/src/components/kiosk/main/InputBar.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { InputBar } from './InputBar'

describe('InputBar', () => {
  it('calls onFocus when input area is tapped', () => {
    const onFocus = vi.fn()
    render(<InputBar onFocus={onFocus} onVoice={vi.fn()} />)
    fireEvent.click(screen.getByRole('textbox'))
    expect(onFocus).toHaveBeenCalledTimes(1)
  })

  it('calls onVoice when mic button is tapped', () => {
    const onVoice = vi.fn()
    render(<InputBar onFocus={vi.fn()} onVoice={onVoice} />)
    fireEvent.click(screen.getByRole('button', { name: /음성/i }))
    expect(onVoice).toHaveBeenCalledTimes(1)
  })

  it('renders placeholder text', () => {
    render(<InputBar onFocus={vi.fn()} onVoice={vi.fn()} />)
    expect(screen.getByPlaceholderText('질문을 입력하거나 탭하세요')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/components/kiosk/main/HeaderBar.test.tsx src/components/kiosk/main/InputBar.test.tsx
```

Expected: FAIL — components not found

- [ ] **Step 3: `HeaderBar` 구현**

```tsx
// frontend/src/components/kiosk/main/HeaderBar.tsx
export function HeaderBar() {
  return (
    <header className="flex items-center px-6 py-4 shrink-0">
      <span className="text-2xl font-bold">캠퍼스 코파일럿</span>
      <span className="ml-2 text-sm opacity-60">호남대학교 학사안내 키오스크</span>
    </header>
  )
}
```

- [ ] **Step 4: `InputBar` 구현**

```tsx
// frontend/src/components/kiosk/main/InputBar.tsx
import { Mic } from 'lucide-react'

interface InputBarProps {
  onFocus: () => void
  onVoice: () => void
}

export function InputBar({ onFocus, onVoice }: InputBarProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 shrink-0">
      <button
        aria-label="음성 입력"
        onClick={onVoice}
        className="p-3 rounded-full shrink-0"
      >
        <Mic size={24} />
      </button>
      <input
        type="text"
        readOnly
        placeholder="질문을 입력하거나 탭하세요"
        onClick={onFocus}
        className="flex-1 px-4 py-3 rounded-xl cursor-pointer"
      />
    </div>
  )
}
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
npm run test:run -- src/components/kiosk/main/HeaderBar.test.tsx src/components/kiosk/main/InputBar.test.tsx
```

Expected: `✓` 4 tests passed

- [ ] **Step 6: 커밋**

```bash
git add src/components/kiosk/main/HeaderBar.tsx src/components/kiosk/main/HeaderBar.test.tsx \
        src/components/kiosk/main/InputBar.tsx src/components/kiosk/main/InputBar.test.tsx
git commit -m "feat(frontend): add HeaderBar and InputBar components

- HeaderBar: logo and service name display
- InputBar: read-only input (tap to enter) + mic button

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 9: `CategoryBar`

**Files:**
- Create: `frontend/src/components/kiosk/main/CategoryBar.tsx`
- Create: `frontend/src/components/kiosk/main/CategoryBar.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/components/kiosk/main/CategoryBar.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CategoryBar } from './CategoryBar'
import type { Category } from '../../../../types/kiosk'

const categories: Category[] = [
  { id: 'admission', name: '학사행정' },
  { id: 'scholarship', name: '장학·등록' },
]

describe('CategoryBar', () => {
  it('renders 전체 tab', () => {
    render(<CategoryBar categories={categories} selectedCategory={null} onSelect={vi.fn()} />)
    expect(screen.getByText('전체')).toBeInTheDocument()
  })

  it('renders all category chips', () => {
    render(<CategoryBar categories={categories} selectedCategory={null} onSelect={vi.fn()} />)
    expect(screen.getByText('학사행정')).toBeInTheDocument()
    expect(screen.getByText('장학·등록')).toBeInTheDocument()
  })

  it('calls onSelect(null) when 전체 is clicked', () => {
    const onSelect = vi.fn()
    render(<CategoryBar categories={categories} selectedCategory={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('전체'))
    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it('calls onSelect with category id on chip click', () => {
    const onSelect = vi.fn()
    render(<CategoryBar categories={categories} selectedCategory={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('학사행정'))
    expect(onSelect).toHaveBeenCalledWith('admission')
  })

  it('marks 전체 as active when selectedCategory is null', () => {
    render(<CategoryBar categories={categories} selectedCategory={null} onSelect={vi.fn()} />)
    expect(screen.getByText('전체').closest('button')).toHaveAttribute('aria-pressed', 'true')
  })

  it('marks selected category chip as active', () => {
    render(<CategoryBar categories={categories} selectedCategory="admission" onSelect={vi.fn()} />)
    expect(screen.getByText('학사행정').closest('button')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('장학·등록').closest('button')).toHaveAttribute('aria-pressed', 'false')
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/components/kiosk/main/CategoryBar.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 구현**

```tsx
// frontend/src/components/kiosk/main/CategoryBar.tsx
import type { Category } from '../../../../types/kiosk'

interface CategoryBarProps {
  categories: Category[]
  selectedCategory: string | null
  onSelect: (id: string | null) => void
}

export function CategoryBar({ categories, selectedCategory, onSelect }: CategoryBarProps) {
  return (
    <nav className="flex flex-wrap gap-2 px-4 py-2 shrink-0">
      <button
        aria-pressed={selectedCategory === null}
        onClick={() => onSelect(null)}
        className="px-4 py-2 rounded-full"
      >
        전체
      </button>
      {categories.map((cat) => (
        <button
          key={cat.id}
          aria-pressed={selectedCategory === cat.id}
          onClick={() => onSelect(cat.id)}
          className="px-4 py-2 rounded-full"
        >
          {cat.name}
        </button>
      ))}
    </nav>
  )
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/components/kiosk/main/CategoryBar.test.tsx
```

Expected: `✓` 6 tests passed

- [ ] **Step 5: 커밋**

```bash
git add src/components/kiosk/main/CategoryBar.tsx src/components/kiosk/main/CategoryBar.test.tsx
git commit -m "feat(frontend): add CategoryBar component

- renders 전체 tab + category chips from API data
- aria-pressed for active state (no screen transition on select)

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 10: `FAQGrid`

**Files:**
- Create: `frontend/src/components/kiosk/main/FAQGrid.tsx`
- Create: `frontend/src/components/kiosk/main/FAQGrid.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/components/kiosk/main/FAQGrid.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FAQGrid } from './FAQGrid'
import type { FAQItem } from '../../../../types/kiosk'

const faqs: FAQItem[] = Array.from({ length: 8 }, (_, i) => ({
  id: String(i),
  question: `FAQ 질문 ${i + 1}`,
  category_id: 'admission',
}))

describe('FAQGrid', () => {
  it('renders up to 6 FAQ items', () => {
    render(<FAQGrid faqs={faqs} onSelect={vi.fn()} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(6)
  })

  it('renders FAQ question text', () => {
    render(<FAQGrid faqs={faqs.slice(0, 3)} onSelect={vi.fn()} />)
    expect(screen.getByText('FAQ 질문 1')).toBeInTheDocument()
    expect(screen.getByText('FAQ 질문 3')).toBeInTheDocument()
  })

  it('calls onSelect with FAQ item when button is clicked', () => {
    const onSelect = vi.fn()
    render(<FAQGrid faqs={faqs.slice(0, 3)} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('FAQ 질문 2'))
    expect(onSelect).toHaveBeenCalledWith(faqs[1])
  })

  it('renders empty state when no faqs', () => {
    render(<FAQGrid faqs={[]} onSelect={vi.fn()} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/components/kiosk/main/FAQGrid.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 구현**

```tsx
// frontend/src/components/kiosk/main/FAQGrid.tsx
import type { FAQItem } from '../../../../types/kiosk'

interface FAQGridProps {
  faqs: FAQItem[]
  onSelect: (item: FAQItem) => void
}

const MAX_DISPLAY = 6

export function FAQGrid({ faqs, onSelect }: FAQGridProps) {
  const displayed = faqs.slice(0, MAX_DISPLAY)

  return (
    <div className="grid grid-cols-3 gap-3 p-4 flex-1 content-start overflow-hidden">
      {displayed.map((faq) => (
        <button
          key={faq.id}
          onClick={() => onSelect(faq)}
          className="p-4 rounded-xl text-left overflow-hidden"
        >
          <span className="block truncate">{faq.question}</span>
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/components/kiosk/main/FAQGrid.test.tsx
```

Expected: `✓` 4 tests passed

- [ ] **Step 5: 커밋**

```bash
git add src/components/kiosk/main/FAQGrid.tsx src/components/kiosk/main/FAQGrid.test.tsx
git commit -m "feat(frontend): add FAQGrid component

- 3-column grid, max 6 items displayed
- text overflow truncation per spec
- onSelect callback with full FAQItem

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 11: `MainScreen` 조립

**Files:**
- Create: `frontend/src/components/kiosk/MainScreen.tsx`
- Create: `frontend/src/components/kiosk/MainScreen.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/components/kiosk/MainScreen.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MainScreen } from './MainScreen'

vi.mock('./main/HeaderBar', () => ({ HeaderBar: () => <div data-testid="header-bar" /> }))
vi.mock('./main/CategoryBar', () => ({ CategoryBar: () => <div data-testid="category-bar" /> }))
vi.mock('./main/FAQGrid', () => ({ FAQGrid: () => <div data-testid="faq-grid" /> }))
vi.mock('./main/InputBar', () => ({ InputBar: () => <div data-testid="input-bar" /> }))

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('MainScreen', () => {
  it('renders all 4 sections', () => {
    render(<MainScreen />, { wrapper })
    expect(screen.getByTestId('header-bar')).toBeInTheDocument()
    expect(screen.getByTestId('category-bar')).toBeInTheDocument()
    expect(screen.getByTestId('faq-grid')).toBeInTheDocument()
    expect(screen.getByTestId('input-bar')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/components/kiosk/MainScreen.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 구현**

```tsx
// frontend/src/components/kiosk/MainScreen.tsx
import { useQuery } from '@tanstack/react-query'
import { useKioskStore } from '../../store/kioskStore'
import { useChat } from '../../hooks/useChat'
import { fetchCategories } from '../../api/categories'
import { fetchFAQ } from '../../api/faq'
import { HeaderBar } from './main/HeaderBar'
import { CategoryBar } from './main/CategoryBar'
import { FAQGrid } from './main/FAQGrid'
import { InputBar } from './main/InputBar'
import type { FAQItem } from '../../types/kiosk'

export function MainScreen() {
  const selectedCategory = useKioskStore((s) => s.selectedCategory)
  const setCategory = useKioskStore((s) => s.setCategory)
  const setMode = useKioskStore((s) => s.setMode)
  const submitQuery = useKioskStore((s) => s.submitQuery)
  const { submit } = useChat()

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
  })

  const { data: faqs = [] } = useQuery({
    queryKey: ['faq', selectedCategory],
    queryFn: () => fetchFAQ(selectedCategory),
  })

  function handleFAQSelect(item: FAQItem) {
    submitQuery(item.question)
    submit(item.question)
  }

  function handleInputFocus() {
    setMode('input')
  }

  function handleVoice() {
    // STT는 InputMode SearchBar에서 처리
    setMode('input')
  }

  return (
    <div className="flex flex-col h-full">
      <HeaderBar />
      <CategoryBar
        categories={categories}
        selectedCategory={selectedCategory}
        onSelect={setCategory}
      />
      <FAQGrid faqs={faqs} onSelect={handleFAQSelect} />
      <InputBar onFocus={handleInputFocus} onVoice={handleVoice} />
    </div>
  )
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/components/kiosk/MainScreen.test.tsx
```

Expected: `✓` 1 test passed

- [ ] **Step 5: 커밋**

```bash
git add src/components/kiosk/MainScreen.tsx src/components/kiosk/MainScreen.test.tsx
git commit -m "feat(frontend): assemble MainScreen with react-query data fetching

- categories via GET /api/v1/categories
- faq via GET /api/v1/faq?category=<id> (refetches on selectedCategory change)
- FAQ select triggers JSON chat and navigates to answer

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 12: `SearchBar` + `PopularList`

**Files:**
- Create: `frontend/src/components/kiosk/input/SearchBar.tsx`
- Create: `frontend/src/components/kiosk/input/SearchBar.test.tsx`
- Create: `frontend/src/components/kiosk/input/PopularList.tsx`
- Create: `frontend/src/components/kiosk/input/PopularList.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/components/kiosk/input/SearchBar.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBar } from './SearchBar'

describe('SearchBar', () => {
  it('calls onBack when ← button is clicked', () => {
    const onBack = vi.fn()
    render(<SearchBar value="" onChange={vi.fn()} onBack={onBack} onSubmit={vi.fn()} onVoice={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /뒤로/i }))
    expect(onBack).toHaveBeenCalledTimes(1)
  })

  it('displays current value in input', () => {
    render(<SearchBar value="휴학 신청" onChange={vi.fn()} onBack={vi.fn()} onSubmit={vi.fn()} onVoice={vi.fn()} />)
    expect(screen.getByDisplayValue('휴학 신청')).toBeInTheDocument()
  })

  it('calls onSubmit when enter key is pressed and value is not empty', () => {
    const onSubmit = vi.fn()
    render(<SearchBar value="테스트" onChange={vi.fn()} onBack={vi.fn()} onSubmit={onSubmit} onVoice={vi.fn()} />)
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' })
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('does not call onSubmit when value is empty', () => {
    const onSubmit = vi.fn()
    render(<SearchBar value="" onChange={vi.fn()} onBack={vi.fn()} onSubmit={onSubmit} onVoice={vi.fn()} />)
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' })
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
```

```tsx
// frontend/src/components/kiosk/input/PopularList.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PopularList } from './PopularList'
import type { PopularItem } from '../../../../types/kiosk'

const items: PopularItem[] = [
  { rank: 1, question: '등록금 납부 기간은?', view_count: 312 },
  { rank: 2, question: '휴학 신청 방법은?', view_count: 251 },
]

describe('PopularList', () => {
  it('renders rank numbers', () => {
    render(<PopularList items={items} onSelect={vi.fn()} />)
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders question text', () => {
    render(<PopularList items={items} onSelect={vi.fn()} />)
    expect(screen.getByText('등록금 납부 기간은?')).toBeInTheDocument()
  })

  it('renders view count', () => {
    render(<PopularList items={items} onSelect={vi.fn()} />)
    expect(screen.getByText('312')).toBeInTheDocument()
  })

  it('calls onSelect with question text when item is clicked', () => {
    const onSelect = vi.fn()
    render(<PopularList items={items} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('등록금 납부 기간은?'))
    expect(onSelect).toHaveBeenCalledWith('등록금 납부 기간은?')
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/components/kiosk/input/SearchBar.test.tsx src/components/kiosk/input/PopularList.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 구현**

```tsx
// frontend/src/components/kiosk/input/SearchBar.tsx
import { ArrowLeft, Mic } from 'lucide-react'

interface SearchBarProps {
  value: string
  onChange: (val: string) => void
  onBack: () => void
  onSubmit: () => void
  onVoice: () => void
}

export function SearchBar({ value, onChange, onBack, onSubmit, onVoice }: SearchBarProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 shrink-0">
      <button
        aria-label="뒤로"
        onClick={onBack}
        className="p-3 rounded-full shrink-0"
      >
        <ArrowLeft size={24} />
      </button>
      <input
        type="text"
        autoFocus
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && value.trim()) onSubmit() }}
        placeholder="질문을 입력하세요"
        className="flex-1 px-4 py-3 rounded-xl"
      />
      <button
        aria-label="음성 입력"
        onClick={onVoice}
        className="p-3 rounded-full shrink-0"
      >
        <Mic size={24} />
      </button>
    </div>
  )
}
```

```tsx
// frontend/src/components/kiosk/input/PopularList.tsx
import type { PopularItem } from '../../../../types/kiosk'

interface PopularListProps {
  items: PopularItem[]
  onSelect: (question: string) => void
}

export function PopularList({ items, onSelect }: PopularListProps) {
  return (
    <div className="flex-1 overflow-y-auto px-4 py-2">
      <p className="text-sm mb-2 opacity-60">다른 사람들이 자주 물은 질문</p>
      <ul>
        {items.map((item) => (
          <li key={item.rank}>
            <button
              onClick={() => onSelect(item.question)}
              className="w-full flex items-center gap-4 py-3 text-left"
            >
              <span className="w-6 text-center font-bold shrink-0">{item.rank}</span>
              <span className="flex-1 truncate">{item.question}</span>
              <span className="shrink-0 text-sm opacity-60">{item.view_count}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/components/kiosk/input/SearchBar.test.tsx src/components/kiosk/input/PopularList.test.tsx
```

Expected: `✓` 8 tests passed

- [ ] **Step 5: 커밋**

```bash
git add src/components/kiosk/input/SearchBar.tsx src/components/kiosk/input/SearchBar.test.tsx \
        src/components/kiosk/input/PopularList.tsx src/components/kiosk/input/PopularList.test.tsx
git commit -m "feat(frontend): add SearchBar and PopularList components

- SearchBar: back button, autoFocus input, mic, enter-to-submit
- PopularList: rank + question + view count; tap fills input

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 13: `VirtualKeyboard` + `InputMode` 조립

**Files:**
- Create: `frontend/src/components/kiosk/input/VirtualKeyboard.tsx`
- Create: `frontend/src/components/kiosk/input/VirtualKeyboard.test.tsx`
- Create: `frontend/src/components/kiosk/InputMode.tsx`
- Create: `frontend/src/components/kiosk/InputMode.test.tsx`

> **Korean IME 주의**: `react-simple-keyboard`는 레이아웃 렌더링만 처리하며 한글 자모 조합(받침 처리 등)은 직접 구현해야 한다. `hangul-js` 라이브러리(`Hangul.a()`)로 자모 배열 → 음절 변환을 수행한다.

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/components/kiosk/input/VirtualKeyboard.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VirtualKeyboard } from './VirtualKeyboard'

// react-simple-keyboard는 DOM 기반이므로 mock 처리
vi.mock('react-simple-keyboard', () => ({
  default: ({ onChange }: { onChange: (input: string) => void }) => (
    <div data-testid="keyboard" onClick={() => onChange('테스트')} />
  ),
}))

describe('VirtualKeyboard', () => {
  it('renders the keyboard', () => {
    render(<VirtualKeyboard value="" onChange={vi.fn()} onSubmit={vi.fn()} />)
    expect(screen.getByTestId('keyboard')).toBeInTheDocument()
  })
})
```

```tsx
// frontend/src/components/kiosk/InputMode.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InputMode } from './InputMode'

vi.mock('./input/SearchBar', () => ({ SearchBar: () => <div data-testid="search-bar" /> }))
vi.mock('./input/PopularList', () => ({ PopularList: () => <div data-testid="popular-list" /> }))
vi.mock('./input/VirtualKeyboard', () => ({ VirtualKeyboard: () => <div data-testid="virtual-keyboard" /> }))

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('InputMode', () => {
  it('renders SearchBar, PopularList, VirtualKeyboard', () => {
    render(<InputMode />, { wrapper })
    expect(screen.getByTestId('search-bar')).toBeInTheDocument()
    expect(screen.getByTestId('popular-list')).toBeInTheDocument()
    expect(screen.getByTestId('virtual-keyboard')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/components/kiosk/input/VirtualKeyboard.test.tsx src/components/kiosk/InputMode.test.tsx
```

Expected: FAIL

- [ ] **Step 3: `VirtualKeyboard` 구현**

```tsx
// frontend/src/components/kiosk/input/VirtualKeyboard.tsx
import { useState } from 'react'
import Keyboard from 'react-simple-keyboard'
import 'react-simple-keyboard/build/css/index.css'
import Hangul from 'hangul-js'

// 한글 QWERTY 레이아웃 (두벌식 표준)
const koreanLayout = {
  default: [
    'ㅂ ㅈ ㄷ ㄱ ㅅ ㅛ ㅕ ㅑ ㅐ ㅔ {bksp}',
    'ㅁ ㄴ ㅇ ㄹ ㅎ ㅗ ㅓ ㅏ ㅣ {enter}',
    '{shift} ㅋ ㅌ ㅊ ㅍ ㅠ ㅜ ㅡ {shift}',
    '{한영} {space} {한영}',
  ],
  shift: [
    'ㅃ ㅉ ㄸ ㄲ ㅆ ㅛ ㅕ ㅑ ㅒ ㅖ {bksp}',
    'ㅁ ㄴ ㅇ ㄹ ㅎ ㅗ ㅓ ㅏ ㅣ {enter}',
    '{shift} ㅋ ㅌ ㅊ ㅍ ㅠ ㅜ ㅡ {shift}',
    '{한영} {space} {한영}',
  ],
  english: [
    'q w e r t y u i o p {bksp}',
    'a s d f g h j k l {enter}',
    '{shift} z x c v b n m {shift}',
    '{한영} {space} {한영}',
  ],
}

interface VirtualKeyboardProps {
  value: string
  onChange: (val: string) => void
  onSubmit: () => void
}

export function VirtualKeyboard({ value, onChange, onSubmit }: VirtualKeyboardProps) {
  const [layoutName, setLayoutName] = useState<'default' | 'shift' | 'english'>('default')
  // 조합 중인 자모 배열 (한글 조합용)
  const [jamoBuffer, setJamoBuffer] = useState<string[]>([])

  function handleKeyPress(button: string) {
    if (button === '{enter}') {
      if (value.trim()) onSubmit()
      return
    }
    if (button === '{shift}') {
      setLayoutName((prev) => (prev === 'shift' ? 'default' : 'shift'))
      return
    }
    if (button === '{한영}') {
      setLayoutName((prev) => (prev === 'english' ? 'default' : 'english'))
      setJamoBuffer([])
      return
    }
    if (button === '{space}') {
      const assembled = Hangul.assemble(jamoBuffer)
      onChange(value.replace(/.$/, '') + assembled + ' ')
      setJamoBuffer([])
      return
    }
    if (button === '{bksp}') {
      if (jamoBuffer.length > 0) {
        const newBuffer = jamoBuffer.slice(0, -1)
        setJamoBuffer(newBuffer)
        const assembled = Hangul.assemble(newBuffer)
        onChange(value.slice(0, -1) + (assembled || ''))
      } else {
        onChange(value.slice(0, -1))
      }
      return
    }

    if (layoutName !== 'english') {
      const newBuffer = [...jamoBuffer, button]
      setJamoBuffer(newBuffer)
      const assembled = Hangul.assemble(newBuffer)
      // 조합 중인 마지막 음절 교체
      const base = jamoBuffer.length > 0 ? value.slice(0, -1) : value
      onChange(base + assembled)
    } else {
      setJamoBuffer([])
      onChange(value + button)
    }

    if (layoutName === 'shift') setLayoutName('default')
  }

  return (
    <div className="shrink-0">
      <Keyboard
        layoutName={layoutName}
        layout={koreanLayout}
        onKeyPress={handleKeyPress}
        display={{
          '{bksp}': '⌫',
          '{enter}': '전송',
          '{shift}': '⇧',
          '{space}': '스페이스',
          '{한영}': '한/영',
        }}
        buttonTheme={[
          { class: 'key-disabled', buttons: value.trim() ? '' : '{enter}' },
        ]}
      />
    </div>
  )
}
```

- [ ] **Step 4: `InputMode` 구현**

```tsx
// frontend/src/components/kiosk/InputMode.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useKioskStore } from '../../store/kioskStore'
import { useChat } from '../../hooks/useChat'
import { fetchPopular } from '../../api/popular'
import { SearchBar } from './input/SearchBar'
import { PopularList } from './input/PopularList'
import { VirtualKeyboard } from './input/VirtualKeyboard'

export function InputMode() {
  const [inputValue, setInputValue] = useState('')
  const resetToMain = useKioskStore((s) => s.resetToMain)
  const submitQuery = useKioskStore((s) => s.submitQuery)
  const { submit } = useChat()

  const { data: popularItems = [] } = useQuery({
    queryKey: ['popular'],
    queryFn: fetchPopular,
  })

  function handleSubmit() {
    if (!inputValue.trim()) return
    submitQuery(inputValue.trim())
    submit(inputValue.trim())
  }

  function handlePopularSelect(question: string) {
    setInputValue(question)
  }

  function handleVoice() {
    // Future STT integration starts here after HTTPS/browser support is verified.
  }

  return (
    <div className="flex flex-col h-full">
      <SearchBar
        value={inputValue}
        onChange={setInputValue}
        onBack={resetToMain}
        onSubmit={handleSubmit}
        onVoice={handleVoice}
      />
      <PopularList items={popularItems} onSelect={handlePopularSelect} />
      <VirtualKeyboard
        value={inputValue}
        onChange={setInputValue}
        onSubmit={handleSubmit}
      />
    </div>
  )
}
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
npm run test:run -- src/components/kiosk/input/VirtualKeyboard.test.tsx src/components/kiosk/InputMode.test.tsx
```

Expected: `✓` 2 tests passed

- [ ] **Step 6: 커밋**

```bash
git add src/components/kiosk/input/VirtualKeyboard.tsx src/components/kiosk/input/VirtualKeyboard.test.tsx \
        src/components/kiosk/InputMode.tsx src/components/kiosk/InputMode.test.tsx
git commit -m "feat(frontend): add VirtualKeyboard and InputMode

- VirtualKeyboard: Korean QWERTY (두벌식) with hangul-js composition
- InputMode: SearchBar + PopularList + VirtualKeyboard assembly
- STT UI entry point only; actual Web Speech API activation is deferred

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 14: `QuestionBar` + `AnswerText` + `ProcedureSteps` + `AnswerPanel`

**Files:**
- Create: `frontend/src/components/kiosk/answer/QuestionBar.tsx`
- Create: `frontend/src/components/kiosk/answer/QuestionBar.test.tsx`
- Create: `frontend/src/components/kiosk/answer/AnswerText.tsx`
- Create: `frontend/src/components/kiosk/answer/AnswerText.test.tsx`
- Create: `frontend/src/components/kiosk/answer/ProcedureSteps.tsx`
- Create: `frontend/src/components/kiosk/answer/ProcedureSteps.test.tsx`
- Create: `frontend/src/components/kiosk/answer/AnswerPanel.tsx`
- Create: `frontend/src/components/kiosk/answer/AnswerPanel.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/components/kiosk/answer/QuestionBar.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QuestionBar } from './QuestionBar'

describe('QuestionBar', () => {
  it('renders the question text', () => {
    render(<QuestionBar question="휴학 신청 방법은 무엇인가요?" onHome={vi.fn()} />)
    expect(screen.getByText('휴학 신청 방법은 무엇인가요?')).toBeInTheDocument()
  })

  it('calls onHome when 처음으로 is clicked', () => {
    const onHome = vi.fn()
    render(<QuestionBar question="테스트" onHome={onHome} />)
    fireEvent.click(screen.getByRole('button', { name: /처음으로/i }))
    expect(onHome).toHaveBeenCalledTimes(1)
  })
})
```

```tsx
// frontend/src/components/kiosk/answer/AnswerText.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnswerText } from './AnswerText'

describe('AnswerText', () => {
  it('renders answer text', () => {
    render(<AnswerText text="휴학은 포털에서 신청하세요." isStreaming={false} />)
    expect(screen.getByText('휴학은 포털에서 신청하세요.')).toBeInTheDocument()
  })

  it('shows streaming cursor when isStreaming is true', () => {
    render(<AnswerText text="안녕" isStreaming={true} />)
    expect(screen.getByTestId('streaming-cursor')).toBeInTheDocument()
  })

  it('hides cursor when streaming is done', () => {
    render(<AnswerText text="완료" isStreaming={false} />)
    expect(screen.queryByTestId('streaming-cursor')).not.toBeInTheDocument()
  })
})
```

```tsx
// frontend/src/components/kiosk/answer/ProcedureSteps.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProcedureSteps } from './ProcedureSteps'

describe('ProcedureSteps', () => {
  it('renders numbered steps', () => {
    render(<ProcedureSteps steps={['포털 로그인', '휴학신청서 작성', '지도교수 승인']} />)
    expect(screen.getByText('포털 로그인')).toBeInTheDocument()
    expect(screen.getByText('지도교수 승인')).toBeInTheDocument()
  })

  it('renders nothing when steps is empty', () => {
    const { container } = render(<ProcedureSteps steps={[]} />)
    expect(container.firstChild).toBeNull()
  })
})
```

```tsx
// frontend/src/components/kiosk/answer/AnswerPanel.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AnswerPanel } from './AnswerPanel'

describe('AnswerPanel', () => {
  it('renders AnswerText and ProcedureSteps', () => {
    render(
      <AnswerPanel
        answer="답변 내용"
        procedureSteps={['1단계', '2단계']}
        isStreaming={false}
      />
    )
    expect(screen.getByText('답변 내용')).toBeInTheDocument()
    expect(screen.getByText('1단계')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/components/kiosk/answer/QuestionBar.test.tsx \
  src/components/kiosk/answer/AnswerText.test.tsx \
  src/components/kiosk/answer/ProcedureSteps.test.tsx \
  src/components/kiosk/answer/AnswerPanel.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 구현**

```tsx
// frontend/src/components/kiosk/answer/QuestionBar.tsx
import { ArrowLeft } from 'lucide-react'

interface QuestionBarProps {
  question: string
  onHome: () => void
}

export function QuestionBar({ question, onHome }: QuestionBarProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 shrink-0">
      <span className="flex-1 truncate font-medium">{question}</span>
      <button
        aria-label="처음으로"
        onClick={onHome}
        className="flex items-center gap-1 px-4 py-2 rounded-lg shrink-0"
      >
        <ArrowLeft size={18} />
        처음으로
      </button>
    </div>
  )
}
```

```tsx
// frontend/src/components/kiosk/answer/AnswerText.tsx
interface AnswerTextProps {
  text: string
  isStreaming: boolean
}

export function AnswerText({ text, isStreaming }: AnswerTextProps) {
  return (
    <div className="flex-1 overflow-y-auto p-4 leading-relaxed">
      {text}
      {isStreaming && (
        <span
          data-testid="streaming-cursor"
          className="inline-block w-0.5 h-5 ml-0.5 animate-pulse"
          aria-hidden
        >
          ▌
        </span>
      )}
    </div>
  )
}
```

```tsx
// frontend/src/components/kiosk/answer/ProcedureSteps.tsx
interface ProcedureStepsProps {
  steps: string[]
}

export function ProcedureSteps({ steps }: ProcedureStepsProps) {
  if (steps.length === 0) return null

  return (
    <ol className="flex gap-2 px-4 pb-3 shrink-0 overflow-x-auto">
      {steps.map((step, i) => (
        <li key={i} className="flex items-center gap-2 whitespace-nowrap px-3 py-2 rounded-lg">
          <span className="font-bold">{i + 1}</span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  )
}
```

```tsx
// frontend/src/components/kiosk/answer/AnswerPanel.tsx
import { AnswerText } from './AnswerText'
import { ProcedureSteps } from './ProcedureSteps'

interface AnswerPanelProps {
  answer: string
  procedureSteps: string[]
  isStreaming: boolean
}

export function AnswerPanel({ answer, procedureSteps, isStreaming }: AnswerPanelProps) {
  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <AnswerText text={answer} isStreaming={isStreaming} />
      <ProcedureSteps steps={procedureSteps} />
    </div>
  )
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npm run test:run -- src/components/kiosk/answer/QuestionBar.test.tsx \
  src/components/kiosk/answer/AnswerText.test.tsx \
  src/components/kiosk/answer/ProcedureSteps.test.tsx \
  src/components/kiosk/answer/AnswerPanel.test.tsx
```

Expected: `✓` 9 tests passed

- [ ] **Step 5: 커밋**

```bash
git add src/components/kiosk/answer/QuestionBar.tsx src/components/kiosk/answer/QuestionBar.test.tsx \
        src/components/kiosk/answer/AnswerText.tsx src/components/kiosk/answer/AnswerText.test.tsx \
        src/components/kiosk/answer/ProcedureSteps.tsx src/components/kiosk/answer/ProcedureSteps.test.tsx \
        src/components/kiosk/answer/AnswerPanel.tsx src/components/kiosk/answer/AnswerPanel.test.tsx
git commit -m "feat(frontend): add answer panel components

- QuestionBar: question text + 처음으로 button
- AnswerText: loading cursor (▌) indicator while JSON chat is pending
- ProcedureSteps: numbered horizontal steps, hidden when empty
- AnswerPanel: AnswerText + ProcedureSteps assembly

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 15: `SourceList` + `ConflictWarning` + `ActionBar` + `SidePanel` + `AnswerScreen` 조립

**Files:**
- Create: `frontend/src/components/kiosk/answer/SourceList.tsx`
- Create: `frontend/src/components/kiosk/answer/SourceList.test.tsx`
- Create: `frontend/src/components/kiosk/answer/ConflictWarning.tsx`
- Create: `frontend/src/components/kiosk/answer/ConflictWarning.test.tsx`
- Create: `frontend/src/components/kiosk/answer/ActionBar.tsx`
- Create: `frontend/src/components/kiosk/answer/ActionBar.test.tsx`
- Create: `frontend/src/components/kiosk/answer/QRModal.tsx`
- Create: `frontend/src/components/kiosk/answer/SidePanel.tsx`
- Create: `frontend/src/components/kiosk/answer/SidePanel.test.tsx`
- Create: `frontend/src/components/kiosk/AnswerScreen.tsx`
- Create: `frontend/src/components/kiosk/AnswerScreen.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```tsx
// frontend/src/components/kiosk/answer/SourceList.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SourceList } from './SourceList'
import type { Source } from '../../../../types/kiosk'

const sources: Source[] = [
  { title: '학사안내', url: 'http://x', crawled_at: '2025-03-15', freshness: 'recent' },
  { title: '공지사항', url: 'http://y', crawled_at: '2023-01-10', freshness: 'stale' },
]

describe('SourceList', () => {
  it('renders source titles', () => {
    render(<SourceList sources={sources} />)
    expect(screen.getByText('학사안내')).toBeInTheDocument()
    expect(screen.getByText('공지사항')).toBeInTheDocument()
  })

  it('shows freshness badge for recent source', () => {
    render(<SourceList sources={[sources[0]]} />)
    expect(screen.getByText('최신')).toBeInTheDocument()
  })

  it('shows freshness badge for stale source', () => {
    render(<SourceList sources={[sources[1]]} />)
    expect(screen.getByText('오래됨')).toBeInTheDocument()
  })

  it('renders crawled_at date', () => {
    render(<SourceList sources={[sources[0]]} />)
    expect(screen.getByText('2025-03-15')).toBeInTheDocument()
  })
})
```

```tsx
// frontend/src/components/kiosk/answer/ConflictWarning.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConflictWarning } from './ConflictWarning'

describe('ConflictWarning', () => {
  it('renders warning description when exists is true', () => {
    render(<ConflictWarning warning={{ exists: true, description: '날짜가 다릅니다.' }} />)
    expect(screen.getByText('날짜가 다릅니다.')).toBeInTheDocument()
  })

  it('renders nothing when exists is false', () => {
    const { container } = render(<ConflictWarning warning={{ exists: false }} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when warning is null', () => {
    const { container } = render(<ConflictWarning warning={null} />)
    expect(container.firstChild).toBeNull()
  })
})
```

```tsx
// frontend/src/components/kiosk/answer/ActionBar.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ActionBar } from './ActionBar'

describe('ActionBar', () => {
  it('renders 인쇄, QR, 읽기 buttons', () => {
    render(<ActionBar answerText="" />)
    expect(screen.getByRole('button', { name: /인쇄/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /QR/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /읽기/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npm run test:run -- src/components/kiosk/answer/SourceList.test.tsx \
  src/components/kiosk/answer/ConflictWarning.test.tsx \
  src/components/kiosk/answer/ActionBar.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 구현**

```tsx
// frontend/src/components/kiosk/answer/SourceList.tsx
import type { Source } from '../../../../types/kiosk'

interface SourceListProps {
  sources: Source[]
}

export function SourceList({ sources }: SourceListProps) {
  return (
    <ul className="flex flex-col gap-2 overflow-y-auto flex-1">
      {sources.map((src, i) => (
        <li key={i} className="px-3 py-2 rounded-lg">
          <div className="flex items-center gap-2">
            <span className="truncate flex-1 font-medium text-sm">{src.title}</span>
            <span
              className={`shrink-0 text-xs px-2 py-0.5 rounded-full ${
                src.freshness === 'recent' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
              }`}
            >
              {src.freshness === 'recent' ? '최신' : '오래됨'}
            </span>
          </div>
          <p className="text-xs opacity-60 mt-1">{src.crawled_at}</p>
        </li>
      ))}
    </ul>
  )
}
```

```tsx
// frontend/src/components/kiosk/answer/ConflictWarning.tsx
import type { ConflictWarning as ConflictWarningType } from '../../../../types/kiosk'

interface ConflictWarningProps {
  warning: ConflictWarningType | null
}

export function ConflictWarning({ warning }: ConflictWarningProps) {
  if (!warning?.exists) return null

  return (
    <div className="px-3 py-2 rounded-lg mt-2 shrink-0">
      <p className="text-sm font-semibold mb-1">⚠ 정보 충돌 감지</p>
      {warning.description && (
        <p className="text-sm opacity-80">{warning.description}</p>
      )}
    </div>
  )
}
```

```tsx
// frontend/src/components/kiosk/answer/QRModal.tsx
import { QRCodeSVG } from 'react-qr-code'
import { X } from 'lucide-react'

interface QRModalProps {
  url: string
  onClose: () => void
}

export function QRModal({ url, onClose }: QRModalProps) {
  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="p-8 rounded-2xl flex flex-col items-center gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        <QRCodeSVG value={url} size={240} />
        <p className="text-sm opacity-60">QR 코드를 스캔하여 답변을 저장하세요</p>
        <button
          aria-label="닫기"
          onClick={onClose}
          className="p-2 rounded-full"
        >
          <X size={20} />
        </button>
      </div>
    </div>
  )
}
```

```tsx
// frontend/src/components/kiosk/answer/ActionBar.tsx
import { useMemo, useState } from 'react'
import { Printer, QrCode, Volume2 } from 'lucide-react'
import { QRModal } from './QRModal'

interface ActionBarProps {
  question: string
  answer: string
  sources: Source[]
}

export function ActionBar({ question, answer, sources }: ActionBarProps) {
  const [showQR, setShowQR] = useState(false)
  const [printStatus, setPrintStatus] = useState<'idle' | 'pending' | 'failed'>('idle')

  const qrValue = useMemo(
    () => JSON.stringify({ question, answerPreview: answer.slice(0, 280) }),
    [answer, question],
  )

  async function handlePrint() {
    setPrintStatus('pending')
    const res = await fetch('http://localhost:6310/print', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, answer, sources }),
    }).catch(() => null)
    setPrintStatus(res?.ok ? 'idle' : 'failed')
  }

  function showTtsPlaceholder() {
    // Future TTS integration starts here after kiosk browser support is verified.
  }

  return (
    <>
      <div className="flex gap-3 px-3 py-3 shrink-0">
        <button
          aria-label="인쇄"
          onClick={handlePrint}
          disabled={printStatus === 'pending'}
          className="flex items-center gap-2 px-4 py-2 rounded-lg"
        >
          <Printer size={18} />
          인쇄
        </button>
        <button
          aria-label="QR 코드"
          onClick={() => setShowQR(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg"
        >
          <QrCode size={18} />
          QR
        </button>
        <button
          aria-label="읽기 예정"
          onClick={showTtsPlaceholder}
          className="flex items-center gap-2 px-4 py-2 rounded-lg"
        >
          <Volume2 size={18} />
          읽기 예정
        </button>
      </div>
      {printStatus === 'failed' && (
        <p className="px-3 text-sm text-red-600">인쇄 서비스에 연결하지 못했습니다.</p>
      )}
      <p className="px-3 text-sm text-slate-500">TTS는 추후 운영 환경에서 사용할 예정입니다.</p>
      {showQR && (
        <QRModal
          value={qrValue}
          onClose={() => setShowQR(false)}
        />
      )}
    </>
  )
}
```

```tsx
// frontend/src/components/kiosk/answer/SidePanel.tsx
import type { Source, ConflictWarning as ConflictWarningType } from '../../../../types/kiosk'
import { SourceList } from './SourceList'
import { ConflictWarning } from './ConflictWarning'
import { ActionBar } from './ActionBar'

interface SidePanelProps {
  sources: Source[]
  conflictWarning: ConflictWarningType | null
  answerText: string
}

export function SidePanel({ sources, conflictWarning, answerText }: SidePanelProps) {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      <SourceList sources={sources} />
      <ConflictWarning warning={conflictWarning} />
      <ActionBar answerText={answerText} />
    </div>
  )
}
```

- [ ] **Step 4: `SidePanel` 테스트 작성 + `AnswerScreen` 조립**

```tsx
// frontend/src/components/kiosk/answer/SidePanel.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SidePanel } from './SidePanel'

vi.mock('./SourceList', () => ({ SourceList: () => <div data-testid="source-list" /> }))
vi.mock('./ConflictWarning', () => ({ ConflictWarning: () => <div data-testid="conflict-warning" /> }))
vi.mock('./ActionBar', () => ({ ActionBar: () => <div data-testid="action-bar" /> }))

describe('SidePanel', () => {
  it('renders SourceList, ConflictWarning, ActionBar', () => {
    render(<SidePanel sources={[]} conflictWarning={null} answerText="" />)
    expect(screen.getByTestId('source-list')).toBeInTheDocument()
    expect(screen.getByTestId('conflict-warning')).toBeInTheDocument()
    expect(screen.getByTestId('action-bar')).toBeInTheDocument()
  })
})
```

```tsx
// frontend/src/components/kiosk/AnswerScreen.tsx
import { useEffect } from 'react'
import { useKioskStore } from '../../store/kioskStore'
import { useChat } from '../../hooks/useChat'
import { QuestionBar } from './answer/QuestionBar'
import { AnswerPanel } from './answer/AnswerPanel'
import { SidePanel } from './answer/SidePanel'

export function AnswerScreen() {
  const currentQuery = useKioskStore((s) => s.currentQuery)
  const answerData = useKioskStore((s) => s.answerData)
  const resetToMain = useKioskStore((s) => s.resetToMain)
  const { submit } = useChat()

  // 쿼리가 있고 answerData가 없을 때 자동 시작 (FAQ 탭 → answer 전환 시)
  useEffect(() => {
    if (currentQuery && !answerData) {
      submit(currentQuery)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const answer = answerData?.answer ?? ''
  const sources = answerData?.sources ?? []
  const procedureSteps = answerData?.procedureSteps ?? []
  const conflictWarning = answerData?.conflictWarning ?? null
  const isStreaming = answerData?.isStreaming ?? true

  return (
    <div className="flex flex-col h-full">
      <QuestionBar question={currentQuery} onHome={resetToMain} />
      <div className="flex flex-1 overflow-hidden">
        <div className="w-3/5 overflow-hidden flex flex-col">
          <AnswerPanel
            answer={answer}
            procedureSteps={procedureSteps}
            isStreaming={isStreaming}
          />
        </div>
        <div className="w-2/5 overflow-hidden flex flex-col border-l">
          <SidePanel
            sources={sources}
            conflictWarning={conflictWarning}
            answerText={answer}
          />
        </div>
      </div>
    </div>
  )
}
```

```tsx
// frontend/src/components/kiosk/AnswerScreen.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useKioskStore } from '../../store/kioskStore'
import { AnswerScreen } from './AnswerScreen'

vi.mock('./answer/QuestionBar', () => ({ QuestionBar: () => <div data-testid="question-bar" /> }))
vi.mock('./answer/AnswerPanel', () => ({ AnswerPanel: () => <div data-testid="answer-panel" /> }))
vi.mock('./answer/SidePanel', () => ({ SidePanel: () => <div data-testid="side-panel" /> }))
vi.mock('../../hooks/useChat', () => ({ useChat: () => ({ submit: vi.fn() }) }))

beforeEach(() => {
  useKioskStore.setState({
    mode: 'answer',
    selectedCategory: null,
    currentQuery: '휴학 신청',
    answerData: { answer: '', sources: [], procedureSteps: [], conflictWarning: null, isStreaming: true },
    idleTimer: null,
  })
})

describe('AnswerScreen', () => {
  it('renders QuestionBar, AnswerPanel, SidePanel', () => {
    render(<AnswerScreen />)
    expect(screen.getByTestId('question-bar')).toBeInTheDocument()
    expect(screen.getByTestId('answer-panel')).toBeInTheDocument()
    expect(screen.getByTestId('side-panel')).toBeInTheDocument()
  })
})
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
npm run test:run -- \
  src/components/kiosk/answer/SourceList.test.tsx \
  src/components/kiosk/answer/ConflictWarning.test.tsx \
  src/components/kiosk/answer/ActionBar.test.tsx \
  src/components/kiosk/answer/SidePanel.test.tsx \
  src/components/kiosk/AnswerScreen.test.tsx
```

Expected: `✓` 10 tests passed

- [ ] **Step 6: 전체 테스트 통과 확인**

```bash
npm run test:run
```

Expected:
```
Test Files  15+ passed
Tests       40+ passed
```

- [ ] **Step 7: TypeScript 검사**

```bash
npx tsc --noEmit
```

Expected: 오류 없음

- [ ] **Step 8: 커밋**

```bash
git add src/components/kiosk/answer/ src/components/kiosk/AnswerScreen.tsx src/components/kiosk/AnswerScreen.test.tsx
git commit -m "feat(frontend): complete answer screen components

- SourceList: source cards with freshness badge (최신/오래됨)
- ConflictWarning: conditional render when conflict exists
- QRModal: react-qr-code overlay
- ActionBar: print (localhost:6310), QR modal, TTS UI entry point
- SidePanel, AnswerScreen: full 60/40 layout assembly

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 16: 관리자 API + 화면

**Files:**
- Create: `frontend/src/api/admin.ts`
- Modify: `frontend/src/pages/AdminPage.tsx`
- Create: `frontend/src/components/admin/StatusPanel.tsx`
- Create: `frontend/src/components/admin/CrawlControl.tsx`
- Create: `frontend/src/components/admin/ConflictTable.tsx`
- Create: `frontend/src/components/admin/LogTable.tsx`
- Create: `frontend/src/api/admin.test.ts`
- Create: `frontend/src/pages/AdminPage.test.tsx`
- Create: focused component tests as needed

- [ ] **Step 1: 관리자 API 타입과 fetch 함수 작성**

`fetchAdminStatus`, `triggerAdminCrawl`, `fetchAdminConflicts`, `fetchAdminLogs`를 만든다. 현재 백엔드 stub 응답(`documents: 0`, `last_crawled: null`, 빈 배열)을 정상 상태로 처리한다.

```ts
// frontend/src/api/admin.ts
export interface AdminStatus {
  documents: number
  last_crawled: string | null
}

export interface AdminConflict {
  id: string
  chunk_a_id?: string
  chunk_b_id?: string
  conflict_type?: string
  severity?: string
  is_resolved?: boolean
  summary?: string
}

export interface AdminLog {
  id: string
  query?: string
  answer?: string
  has_conflict?: boolean
  response_ms?: number
  created_at?: string | null
}

export async function fetchAdminStatus(): Promise<AdminStatus> {
  const res = await fetch('/api/v1/admin/status')
  if (!res.ok) throw new Error(`admin status fetch failed: ${res.status}`)
  return res.json()
}

export async function triggerAdminCrawl(): Promise<{ status: string }> {
  const res = await fetch('/api/v1/admin/crawl', { method: 'POST' })
  if (!res.ok) throw new Error(`admin crawl failed: ${res.status}`)
  return res.json()
}

export async function fetchAdminConflicts(): Promise<AdminConflict[]> {
  const res = await fetch('/api/v1/admin/conflicts')
  if (!res.ok) throw new Error(`admin conflicts fetch failed: ${res.status}`)
  return res.json()
}

export async function fetchAdminLogs(): Promise<AdminLog[]> {
  const res = await fetch('/api/v1/admin/logs')
  if (!res.ok) throw new Error(`admin logs fetch failed: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 2: 관리자 화면 레이아웃 구현**

`/admin` 첫 화면에서 운영자가 바로 읽을 수 있게 상태, 수동 크롤링, 충돌 목록, 질의 로그를 한 작업 화면에 배치한다. 빈 배열은 오류가 아니라 "표시할 항목 없음" 상태로 렌더링한다.

컴포넌트 책임:
- `StatusPanel`: `documents`, `last_crawled` 표시. `last_crawled === null`은 "아직 수집 기록 없음"으로 표시한다.
- `CrawlControl`: `useMutation`으로 `triggerAdminCrawl` 실행. pending 중 버튼 비활성화, 성공 시 "크롤링 요청됨" 표시, 성공 후 `['admin-status']`, `['admin-logs']` query를 invalidate한다.
- `ConflictTable`: 충돌 목록 테이블. 빈 배열은 "표시할 충돌 없음"으로 표시한다.
- `LogTable`: 질의 로그 테이블. 빈 배열은 "표시할 로그 없음"으로 표시한다.
- `AdminPage`: 위 컴포넌트를 조립하고 `useQuery` key는 각각 `['admin-status']`, `['admin-conflicts']`, `['admin-logs']`로 고정한다.

- [ ] **Step 3: 수동 크롤링 동작 구현**

버튼 탭 시 `POST /api/v1/admin/crawl`을 호출하고, 성공 시 `triggered` 상태를 토스트 또는 인라인 상태로 표시한다. 중복 클릭 방지를 위해 pending 상태에서는 버튼을 비활성화한다.

- [ ] **Step 4: 테스트**

React Query provider로 `AdminPage`를 렌더링하고 다음을 검증한다.
- status stub 응답이 화면에 표시된다.
- conflicts/logs 빈 배열이 빈 상태로 표시된다.
- 수동 크롤링 버튼이 API 호출 후 성공 상태를 표시한다.
- pending 중 수동 크롤링 버튼이 비활성화된다.
- 실패 응답은 해당 panel 안에서 오류 상태로 표시되고 다른 panel 렌더링을 막지 않는다.

- [ ] **Step 5: 커밋**

```bash
git add src/api/admin.ts src/pages/AdminPage.tsx src/components/admin/
git commit -m "feat(frontend): implement phase 3 admin dashboard

- add admin API client for status, crawl, conflicts, logs
- render status, manual crawl, conflict, and log panels
- handle stub and empty states clearly

Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 17: Phase 3 통합 검증

- [x] **Step 1: 단위 테스트 전체 실행**

```bash
npm run test:run
```

Result (2026-05-06): passed, 24 files / 51 tests.

- [x] **Step 2: 타입 검사**

```bash
npm run typecheck
```

Result (2026-05-06): passed.

- [x] **Step 3: 프로덕션 빌드**

```bash
npm run build
```

Result (2026-05-06): passed.

- [x] **Step 4: Docker Compose 기준 smoke 확인**

```bash
docker compose up --build
```

Expected:
- `/` 키오스크 화면이 main/input/answer 동선을 제공한다.
- `/admin` 관리자 화면이 stub API 기준으로 상태와 빈 목록을 표시한다.
- `/api/v1/*` proxy가 backend로 전달된다.

Result (2026-05-06): passed. Confirmed `/`, `/admin`, backend health, and running frontend/backend/worker/postgres/redis/chromadb services.

- [ ] **Step 5: 1280x800 키오스크 viewport 수동/브라우저 확인**

브라우저 개발자 도구 또는 Playwright를 사용할 수 있으면 1280x800 viewport로 다음을 확인한다.
- main 화면에서 Header/Category/FAQ/InputBar가 겹치지 않는다.
- main → input → answer 동선이 2단계 안에 완료된다.
- 터치 대상 버튼이 10.1인치 kiosk에서 누르기 어렵지 않은 크기로 유지된다.
- 긴 질문/출처 제목이 말줄임 처리되고 주변 UI를 밀어내지 않는다.
- 30초 idle reset 시 main으로 복귀한다.
- TTS는 Phase 3에서 UI 진입점만 제공하므로 실제 음성 정지는 후속 TTS 활성화 시 검증한다.

- [ ] **Step 6: 관리자 동선 smoke 확인**

`/admin`에서 다음을 확인한다.
- status stub(`documents: 0`, `last_crawled: null`)이 빈 상태가 아닌 정상 상태로 표시된다.
- conflicts/logs 빈 배열이 빈 상태로 표시된다.
- 수동 크롤링 버튼이 pending/success/error 상태를 표시한다.
- mutation 성공 후 status/log queries가 invalidate된다.

---

## Self-Review

### 1. Spec 커버리지 점검

| 설계서 요구사항 | 구현 Task |
|--------------|----------|
| Header Bar (로고+서비스명) | Task 8 HeaderBar |
| Category Bar (chip 형태, flex wrap, 화면 전환 없음) | Task 9 CategoryBar |
| FAQ Grid (3열 2행, 최대 6개, 말줄임) | Task 10 FAQGrid |
| Input Bar (항상 하단 고정, 🎤 버튼) | Task 8 InputBar |
| Search Bar (← 복귀, 자동 포커스, STT future-use 진입점) | Task 12 SearchBar |
| Popular List (순위+질문+조회수, 탭→입력창에 채움) | Task 12 PopularList |
| Virtual Keyboard (한글 QWERTY, 전송 키 비활성화) | Task 13 VirtualKeyboard |
| Answer Panel 로딩 커서(▌) | Task 14 AnswerText |
| Procedure Steps (`procedure_steps`, 조건부) | Task 14 ProcedureSteps |
| Source Panel (제목+갱신일+freshness 뱃지) | Task 15 SourceList |
| Conflict Warning (조건부 표시) | Task 15 ConflictWarning |
| Action Bar (인쇄/QR/TTS future-use 진입점) | Task 15 ActionBar |
| QR 모달 | Task 15 QRModal |
| 30초 idle 리셋 | Task 4 useIdleTimer |
| Zustand 전역 스토어 | Task 3 kioskStore |
| JSON Chat 훅 | Task 6 useChat |
| KioskPage mode 라우터 | Task 7 KioskPage |
| API: categories, faq, popular | Task 5 |
| 관리자 상태 화면 | Task 16 AdminPage / StatusPanel |
| 수동 크롤링 트리거 | Task 16 CrawlControl |
| 관리자 충돌 목록 | Task 16 ConflictTable |
| 관리자 로그 조회 | Task 16 LogTable |
| Phase 3 통합 검증 | Task 17, 1280x800 viewport는 UI 반복 개선 후속 확인 |

**누락 없음**

### 2. Placeholder 스캔

- 코드 블록 내 TBD/TODO 없음
- 모든 Step에 실제 코드 포함

### 3. 타입 일관성

- `Source`, `ConflictWarning`, `AnswerData` 타입: Task 2에서 정의 → 이후 모든 컴포넌트에서 동일 경로(`../types/kiosk`) import
- `setAnswerData` 함수형 업데이터 시그니처: Task 3에서 정의 → Task 6에서 사용 (일치)
- `FAQItem` 타입: Task 2에서 정의 → `FAQGrid.onSelect` 콜백에서 사용 (일치)

### 4. 알려진 제한사항

- **VirtualKeyboard**: `hangul-js`의 `Hangul.assemble()`은 자모 배열 조합을 처리하지만 이중 받침(예: ㄳ, ㄵ) 처리는 추가 검증 필요
- **STT/TTS**: Phase 3은 UI 진입점만 제공한다. 실제 Web Speech API 활성화는 운영 HTTPS와 kiosk 브라우저 지원을 확인한 뒤 진행한다.
- **print-service**: `localhost:6310` 경로는 Raspberry Pi 로컬 환경 전용; 개발 환경에서는 CORS 오류 발생 가능
