# 프로젝트 개요와 문서화 흐름

## 도메인

Campus Copilot은 호남대학교 학사 안내를 위한 키오스크 중심 서비스입니다. 단순 질의응답 데모가 아니라, 공식 학사 문서를 수집하고 RAG로 답변하며 키오스크 UI에서 사용자가 바로 안내를 받을 수 있게 하는 end-to-end 시스템으로 다뤄졌습니다.

## 목표

프로젝트를 공개 가능한 포트폴리오/논문 재료로 정리하기 위해 저장소의 역할과 작업 규칙을 단순화했습니다. 기존의 긴 작업 지침을 줄이고, 프로젝트 개요, 테스트 방법과 순서, `docs` 내 설계서·계획서 위치를 간단히 드러내는 방향으로 정리했습니다.

## 문제

- 프로젝트의 실제 구조는 여러 하위 시스템으로 나뉘어 있었지만, 안내 문서가 길어지면 핵심이 흐려질 수 있었습니다.
- 구현 문서와 작업 지침이 섞이면 새 독자가 “이 프로젝트가 무엇을 하는지”보다 “어떻게 작업해야 하는지”를 먼저 읽게 됩니다.
- 포트폴리오 관점에서는 프로젝트 설명, 하위 시스템, 검증 명령, 설계 문서 위치가 빠르게 드러나는 편이 더 유리했습니다.

## 비교한 선택지

- 긴 handbook 형태 유지
- 기존 내용 일부만 수정
- 기존 내용을 지우고 짧은 repository guide로 재작성

세 번째 방식인 짧은 repository guide 재작성이 선택됐습니다.

## 선택

`AGENTS.md`를 짧은 프로젝트 가이드로 정리했습니다.

- `backend`: FastAPI API와 RAG 서비스
- `worker`: 공지 크롤링, 파싱, 임베딩, 스케줄 작업
- `frontend`: 키오스크 UI와 관리자 UI
- `pi-setup`: Raspberry Pi 키오스크와 로컬 프린트 서비스 설정
- `docs`: 설계서와 구현 계획서

테스트 순서도 하위 시스템별로 명시했습니다.

- backend: `uv run ruff check .`, `uv run pytest`
- worker: `uv run ruff check .`, `uv run pytest`
- frontend: `npm run typecheck`, `npm run test:run`, `npm run build`
- frontend 전체 smoke가 필요하면 `npm run smoke`

## 결과

현재 `AGENTS.md`는 짧은 안내 문서 역할을 합니다. 프로젝트의 외부 설명은 `README.md`, 설계·계획은 `docs/specs`와 `docs/plans`, 세션 기반 맥락은 이 `docs/sessions` 디렉터리로 나누는 구조가 되었습니다.

## 포트폴리오/논문에 쓸 수 있는 포인트

- Campus Copilot은 “공식 학사 문서 기반 RAG 키오스크”라는 도메인 문제를 가진 시스템입니다.
- 백엔드, worker, frontend, Raspberry Pi 배포 영역이 분리된 구조입니다.
- 세션 기반 문서화는 구현 결과뿐 아니라 의사결정 과정을 보존하는 보조 자료입니다.

## 관련 자료

- [AGENTS.md](../../AGENTS.md)
- [README.md](../../README.md)
- [설계 문서 디렉터리](../kiosk/specs/)
- [구현 계획 디렉터리](../kiosk/plans/)

## 공란/미확인

- 최종 논문 목차에서 이 프로젝트를 “RAG 시스템”, “키오스크 UX”, “도메인 특화 정보검색” 중 어디에 가장 강하게 배치할지는 아직 미정입니다.
- 실제 사용자 테스트나 현장 배포 결과는 이 세션 데이터만으로는 확인되지 않습니다.
