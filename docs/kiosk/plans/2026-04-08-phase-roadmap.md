# Campus Copilot — Phase Roadmap

## 목적

이 문서는 전체 프로젝트를 한 번에 상세 설계하지 않고, 페이즈별로 문서화 범위를 분리하기 위한 기준 문서입니다.

- 현재 정식 상세 문서 기준 baseline: `Phase 3` 키오스크 / 관리자 프론트엔드 완료
- 다음 active phase 후보: `Phase 4` 인덱싱 + 검색 + 응답 생성
- `Phase 3` UI는 구현된 초안 상태이며, 후속 UI polish는 Phase 3 baseline 위에서 반복 개선
- `Phase 4` 이후 페이즈: 개요만 먼저 정의하고, 착수 직전에 spec/plan 을 상세화

---

## 문서 운영 원칙

1. 각 페이즈는 `spec -> implementation plan -> execution` 순서로 독립 진행합니다.
2. 아직 착수하지 않은 페이즈는 개요 수준까지만 고정합니다.
3. 이전 페이즈의 산출물이 확정되면 다음 페이즈 문서를 구체화합니다.
4. 한 문서가 여러 페이즈를 동시에 상세 지시하지 않도록 유지합니다.

---

## Phase 목록

### Phase 1. 프로젝트 스캐폴딩 + 인프라 설정

- 목표: 전체 저장소 구조, Docker Compose, 패키지 설정, 진입점, Pi 보조 스크립트까지 포함한 실행 가능한 골격 마련
- 산출물:
  - 루트 인프라 파일
  - backend / worker / frontend / pi-setup 기본 구조
  - Alembic 설정
  - `docker compose up` 기준 통합 기동 검증
- 문서 상태: 상세 계획 작성됨
- 관련 문서:
  - [2026-04-08-architecture-design.md](../specs/2026-04-08-architecture-design.md)
  - [2026-04-08-phase-1-project-scaffold.md](2026-04-08-phase-1-project-scaffold.md)

### Phase 2. 수집 + 파싱 파이프라인

- 목표: Crawl4AI 기반 HTML 수집, PDF 분기 처리, 표 추출, 청킹 규칙 구현
- 포함 범위:
  - 메뉴 탐색 및 URL 수집
  - HTML / PDF 파서 구현
  - content hash 기반 변경 감지
  - worker 태스크 실제 로직 연결
- 제외 범위:
  - 사용자 응답 생성 고도화
  - 프론트엔드 UI 완성
- 문서 상태: spec + implementation plan 작성됨
- 관련 문서:
  - [2026-04-19-phase-2-crawling-parsing-design.md](../specs/2026-04-19-phase-2-crawling-parsing-design.md)
  - [2026-04-19-phase-2-crawling-parsing-implementation.md](2026-04-19-phase-2-crawling-parsing-implementation.md)

### Phase 3. 키오스크 / 관리자 프론트엔드

- 목표: 실제 사용 가능한 키오스크 화면과 관리자 화면 완성
- 포함 범위:
  - 카테고리 진입
  - 질의응답 UI
  - 출처 / 절차 / 충돌 표시
  - 관리자 상태 / 수동 크롤링 / 로그 조회 화면
- 구현 상태: baseline 구현 완료
- 문서 상태: spec + implementation plan 작성됨. STT/TTS는 UI 진입점만 제공하며 실제 Web Speech API 활성화는 후속 단계로 유지
- 관련 문서:
  - [2026-05-06-phase-3-kiosk-admin-frontend-design.md](../specs/2026-05-06-phase-3-kiosk-admin-frontend-design.md) - 키오스크 / 관리자 프론트엔드 설계
  - [2026-04-12-phase-3-kiosk-admin-frontend.md](2026-04-12-phase-3-kiosk-admin-frontend.md) - 키오스크 / 관리자 프론트엔드 구현 계획

### Phase 4. 인덱싱 + 검색 + 응답 생성

- 목표: ChromaDB + BM25 기반 검색, LLM provider 추상화, `/api/v1/chat` 실제 응답 구현
- 포함 범위:
  - 임베딩 및 인덱싱
  - retriever / rag / llm service 구현
  - freshness / sources / conflict warning 응답 구조 반영
  - 기본 질의 로그 저장
- 문서 상태: 개요만 정의

### Phase 5. 운영 배포 + Pi 통합 + 품질 보강

- 목표: AWS 운영 배포, Raspberry Pi 연동, 관측성 및 안정화
- 포함 범위:
  - `docker-compose.prod.yml` 운영 검증
  - nginx / HTTPS / 도메인 연결
  - Pi kiosk 자동 시작
  - print-service 실기기 연동
  - 테스트, 린트, 배포 점검 절차 정리
- 문서 상태: 개요만 정의

---

## 다음 문서화 순서

1. `Phase 1` ~ `Phase 3` 문서를 완료 baseline 기록으로 유지합니다.
2. `Phase 4` 착수 전 현재 backend/frontend 경계를 기준으로 검색, RAG, SSE 응답 생성 spec을 작성합니다.
3. 이후 페이즈도 같은 방식으로 반복합니다.
