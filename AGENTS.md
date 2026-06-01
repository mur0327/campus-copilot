# Campus Copilot

Campus Copilot은 호남대학교 학사 안내를 위한 키오스크 중심 서비스입니다.

- `backend`: FastAPI API와 RAG 서비스
- `worker`: 공지 크롤링, 파싱, 임베딩, 스케줄 작업
- `frontend`: 키오스크 UI와 관리자 UI
- `pi-setup`: Raspberry Pi 키오스크와 로컬 프린트 서비스 설정

## Test

변경 범위에 맞춰 아래 순서로 확인하세요.

1. `backend` 변경 시:
   - `cd backend`
   - `uv run ruff check .`
   - `uv run pytest`
2. `worker` 변경 시:
   - `cd worker`
   - `uv run ruff check .`
   - `uv run pytest`
3. `frontend` 변경 시:
   - `cd frontend`
   - `npm run typecheck`
   - `npm run test:run`
   - `npm run build`

프론트엔드 전체 스모크 확인이 필요하면 `cd frontend && npm run smoke`를 사용하세요.

## Docs

`docs` 디렉터리에는 프로젝트 설계서와 구현 계획서가 있습니다.
