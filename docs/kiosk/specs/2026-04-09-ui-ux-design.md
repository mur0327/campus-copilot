# campus-copilot 키오스크 UI/UX 설계

**날짜**: 2026-04-09
**디스플레이**: 10.1인치 · 1280×800 · 터치스크린 전용 · 라이트 모드
**범위**: 레이아웃 구조 · 화면 동선 · 컴포넌트 경계 · 확장성

> 폰트 종류·크기·색상·여백 수치는 이 문서에서 명시하지 않는다.
> 시각적 스타일은 Tailwind 설정 한 곳에서 관리하며 언제든지 변경 가능하다.
> Phase 3 구현 기준 최신 경계는 `2026-05-06-phase-3-kiosk-admin-frontend-design.md`를 우선한다. 이 문서는 키오스크 UI 구조 초안으로 유지하며, STT/TTS 실제 Web Speech API 호출과 FAQ/popular backend 공급은 후속 단계로 이관한다.

---

## 1. 화면 목록 (Screen Inventory)

| ID | 이름 | 진입 조건 | 복귀 조건 |
|----|------|-----------|-----------|
| `main` | 메인 화면 | 앱 시작 / idle 리셋 / ← 버튼 | — |
| `input` | 입력 모드 | 메인에서 입력창 탭 | ← 버튼 / idle 리셋 |
| `answer` | 답변 화면 | FAQ 탭 / 입력 전송 / 인기 질문 탭 | ← 처음으로 / idle 리셋 |

> 세 화면 외 추가 화면(운영자, 프린트 미리보기 등)은 별도 스펙에서 다룬다.

---

## 2. 메인 화면 (`main`)

### 2-1. 레이아웃 구조

```
┌──────────────────────────────────────────────────────────────┐
│  Header Bar                                                  │  ← 고정 높이
├──────────────────────────────────────────────────────────────┤
│  Category Bar  [ 학사행정 | 장학·등록 | 시설·부서 | 취업·진로 ]  │  ← 고정 높이
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  FAQ Grid  (3열 × 2행, 카테고리 선택에 따라 인라인 필터링)       │  ← 남은 공간 전체
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  Input Bar  [ 🎤 | 입력창 | 전송 ]                            │  ← 고정 높이
└──────────────────────────────────────────────────────────────┘
```

### 2-2. 각 영역 역할

**Header Bar**
- 기관 로고 + 서비스명 표시
- 사용자 조작 없음 (순수 표시 영역)

**Category Bar**
- API에서 받아온 카테고리 목록을 칩(chip) 형태로 나열
- 탭 시 해당 카테고리가 활성화(active 상태), 나머지 비활성
- **화면 전환 없음** — FAQ Grid만 해당 카테고리 항목으로 교체됨
- "전체" 탭 포함 (기본 선택, 모든 FAQ 표시)
- 카테고리 수가 늘어도 가로 스크롤 없이 flex wrap 허용

**FAQ Grid**
- 3열 2행 고정 그리드. 한 화면에 최대 6개 표시
- 카테고리 필터 후 6개 초과 시: 상위 6개만 표시 (API에서 우선순위 정렬)
- 버튼 탭 → `answer` 화면으로 전환
- 텍스트가 버튼 너비를 초과할 경우 말줄임(`text-overflow: ellipsis`)
- **데이터 소스**: `GET /api/v1/categories` 응답에 FAQ 항목 포함하거나,
  별도 `GET /api/v1/faq?category=<id>` 엔드포인트 필요 — 백엔드 설계 시 결정

**Input Bar**
- 항상 화면 하단 고정
- 탭 시 → `input` 모드로 전환 (이 바 자체는 사라짐)
- 🎤 마이크 버튼: STT(음성 입력) 트리거

---

## 3. 입력 모드 (`input`)

### 3-1. 레이아웃 구조

```
┌──────────────────────────────────────────────────────────────┐
│  Search Bar  [ ← | 입력창(포커스) | 🎤 ]                      │  ← 고정 높이, 애니메이션으로 위에서 등장
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Popular List  (다른 사람들이 자주 물은 질문, 순위별 목록)        │  ← 남은 공간
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  Virtual Keyboard  (한/영 전환 포함, react-simple-keyboard)   │  ← 고정 높이 (~40vh)
└──────────────────────────────────────────────────────────────┘
```

### 3-2. 전환 애니메이션

- 메인 화면 Input Bar → 입력 모드 Search Bar: 하단에서 상단으로 슬라이드 업
- 입력 모드 진입 시 Virtual Keyboard는 하단에서 위로 슬라이드 인

### 3-3. 각 영역 역할

**Search Bar**
- `←` 버튼: 메인으로 복귀 (입력 내용 초기화)
- 입력창: 자동 포커스, 가상 키보드와 연동
- 🎤 버튼: push-to-talk STT

**Popular List**
- `GET /api/v1/popular` 응답 기반 (상위 N건, Redis 캐시)
- 표시 항목: 순위 번호 + 질문 텍스트 + 조회 횟수
- 항목 탭 → 해당 텍스트가 Search Bar 입력창에 채워짐 (자동 전송 하지 않음, 사용자가 확인 후 전송)
- 목록 길이: 스크롤 가능, 최소 표시 보장 건수는 API 응답에 의존

**Virtual Keyboard**
- 한글 QWERTY 레이아웃 (기본), 영문·숫자 전환 가능
- 입력 결과는 Search Bar 입력창에 실시간 반영
- 전송 키: 입력창 비어있으면 비활성화

---

## 4. 답변 화면 (`answer`)

### 4-1. 레이아웃 구조

```
┌──────────────────────────────────────────────────────────────┐
│  Question Bar  [ Q | 질문 텍스트 (말줄임)        | ← 처음으로 ] │  ← 고정 높이
├───────────────────────────────┬──────────────────────────────┤
│                               │                              │
│  Answer Panel  (60%)          │  Source Panel  (40%)         │
│  ─────────────────────────    │  ─────────────────────────   │
│  답변 텍스트 (SSE 스트리밍)     │  출처 카드 목록               │
│                               │  (제목 + 갱신일 + 최신 뱃지)   │
│  ─────────────────────────    │                              │
│  Procedure Steps              │  Conflict Warning (조건부)   │
│  (번호 + 단계 설명, 1행 고정)   │                              │
│                               │  ─────────────────────────   │
│                               │  Action Bar                  │
│                               │  [ 인쇄 | QR | 읽기(TTS) ]   │
└───────────────────────────────┴──────────────────────────────┘
```

### 4-2. 각 영역 역할

**Question Bar**
- 질문 텍스트 전체 표시 (길면 말줄임)
- `← 처음으로`: 메인으로 복귀, 상태 초기화

**Answer Panel (좌, 60%)**
- SSE 스트리밍으로 토큰 단위 렌더링 — 첫 글자가 나타나는 즉시 화면에 표시
- 스트리밍 완료 전까지 커서(▌) 표시
- Procedure Steps는 SSE `procedure_steps` 이벤트 수신 후 렌더링 (답변과 독립적 타이밍)
- 절차가 없는 질문에서는 Procedure Steps 영역 미표시 (공간 답변 텍스트에 할당)

**Source Panel (우, 40%)**
- 출처 카드: 문서 제목 + 갱신일 + 최신성 뱃지 (최신 / 오래됨)
- 최신성은 `freshness` 필드 기반 (green / amber)
- SSE `sources` 이벤트 수신 후 렌더링

**Conflict Warning (조건부)**
- SSE `conflict_warning.exists === true` 일 때만 Source Panel 하단에 표시
- 항상 보이는 영역이 아님 — 없을 때는 Source Panel이 더 넓게 사용

**Action Bar**
- 인쇄: `POST http://localhost:6310/print` (Pi 로컬 print-service)
- QR: 답변 URL QR 코드 모달
- 읽기: TTS 토글 (Web Speech API, 기본 OFF)

---

## 5. 화면 동선 (Navigation Flow)

```
                    ┌──────────────────┐
            앱 시작 │                  │ ← 30초 idle 리셋
     ┌──────────────►    main          │◄──────────────────────────────┐
     │              │                  │                               │
     │              └────────┬─────────┘                               │
     │                       │                                         │
     │           ┌───────────┼──────────────┐                          │
     │           │           │              │                          │
     │    카테고리 탭       FAQ 탭         입력창 탭                      │
     │  (화면 유지,         │              │                            │
     │  FAQ만 갱신)         ▼              ▼                            │
     │           │   ┌──────────┐   ┌──────────┐                       │
     │           │   │          │   │          │                       │
     │           │   │  answer  │   │  input   │                       │
     │           │   │          │   │          │                       │
     │           │   └──────────┘   └────┬─────┘                       │
     │           │        │              │                              │
     │           └────────┘         인기질문 탭 → 입력창에 채움           │
     │                              → 사용자가 전송 탭                   │
     │                                  │                              │
     │                                  ▼                              │
     │                           ┌──────────┐                          │
     │                           │          │                          │
     │                           │  answer  │──── ← 처음으로 ───────────┘
     │                           │          │
     │                           └──────────┘
     │
     └── ← 버튼 (input에서) / ← 처음으로 (answer에서) / idle 리셋
```

**모든 경로의 최대 단계 수:**
- main → answer: **1단계** (FAQ 탭 또는 직접 입력)
- main → input → answer: **2단계**

---

## 6. 컴포넌트 구조

```
KioskPage                   ← mode 상태 관리 (main | input | answer)
├── MainScreen
│   ├── HeaderBar
│   ├── CategoryBar         ← selectedCategory 상태 보유
│   ├── FAQGrid             ← selectedCategory prop 수신
│   └── InputBar            ← 탭 시 mode → 'input' 트리거
│
├── InputMode
│   ├── SearchBar           ← 자동 포커스, 입력 상태 보유
│   ├── PopularList         ← GET /api/v1/popular 데이터
│   └── VirtualKeyboard     ← SearchBar와 양방향 연동
│
└── AnswerScreen
    ├── QuestionBar         ← 현재 query prop
    ├── AnswerPanel
    │   ├── AnswerText      ← SSE 스트리밍 렌더링
    │   └── ProcedureSteps ← SSE 수신 후 렌더링 (조건부)
    └── SidePanel
        ├── SourceList      ← SSE 수신 후 렌더링
        ├── ConflictWarning ← 조건부 (conflict_warning.exists)
        └── ActionBar       ← 인쇄 / QR / TTS
```

---

## 7. 전역 상태 (Zustand)

```ts
interface KioskStore {
  // 화면 모드
  mode: 'main' | 'input' | 'answer';

  // 카테고리 필터 (null = 전체)
  selectedCategory: string | null;

  // 현재 질문
  currentQuery: string;

  // 답변 데이터 (answer 모드일 때 유효)
  answerData: AnswerData | null;

  // idle 리셋 타이머 ref
  idleTimer: ReturnType<typeof setTimeout> | null;

  // 액션
  setMode: (mode: KioskStore['mode']) => void;
  setCategory: (cat: string | null) => void;
  submitQuery: (query: string) => void;
  resetToMain: () => void;
  resetIdleTimer: () => void;
}
```

---

## 8. Idle 리셋

- **트리거**: 30초 무조작 (터치 이벤트 없음)
- **동작**: 현재 mode에 관계없이 `resetToMain()` 호출
  - mode → 'main'
  - selectedCategory → null
  - currentQuery → ''
  - answerData → null
  - TTS 정지 (진행 중인 경우)
  - 가상 키보드 입력 초기화

---

## 9. 확장성 고려

### 카테고리·FAQ는 API 응답으로 결정
`GET /api/v1/categories` 응답이 CategoryBar를 구동한다.
카테고리 추가·제거·이름 변경 시 프론트엔드 코드 변경 불필요.

### 우측 패널 확장 (SidePanel)
Source / ConflictWarning / ActionBar 아래에 새 패널(예: 관련 공지, 담당 부서 연락처)을 
`SidePanel`에 컴포넌트를 추가하는 것만으로 삽입 가능.

### 화면 추가
`KioskPage`의 `mode` 타입에 새 값을 추가하고 대응 컴포넌트를 작성하면 새 화면 진입 가능.
기존 화면에 영향 없음.

### 인기 질문 목록 교체
`PopularList`는 `GET /api/v1/popular` 응답에만 의존한다.
순위 알고리즘(횟수 기반 → 시간 가중 등)을 백엔드에서만 변경 가능.

### 스타일 분리 원칙
레이아웃 구조(flex 방향, 비율, overflow)는 컴포넌트 구조에 귀속.
색상·폰트·여백 수치는 Tailwind 테마 토큰(`tailwind.config.ts`)에 집중 관리.
다크 모드, 고대비 모드 전환도 테마 교체만으로 대응 가능하도록 인라인 스타일 사용 금지.

---

## 10. 이 설계에서 다루지 않는 것

- 운영자 화면 (`/admin`) 레이아웃
- QR 모달 상세 디자인
- 프린트 출력 포맷
- 애니메이션 duration / easing 수치
- 색상 팔레트 · 폰트 패밀리 · 여백 스케일
