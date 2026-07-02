# Campus Copilot

Campus Copilot은 호남대학교 학사 안내를 위한 키오스크 중심 서비스입니다.

## Folder Structure

- `backend/`: FastAPI API, RAG 서비스, DB 마이그레이션, 백엔드 테스트
  - `backend/app/prompts/chat_answer.md`: LLM 최종 답변 생성 프롬프트
  - `backend/app/schemas/chat.py`: 채팅 응답 JSON 구조와 RAG metadata 계약
- `worker/`: 공지 크롤링, 문서 파싱, 임베딩, 인덱싱 작업
- `frontend/`: 키오스크 화면, 관리자 화면, 프론트엔드 테스트
  - `frontend/src/types/kiosk.ts`: 프론트엔드 채팅 응답 수신 타입
- `pi-setup/`: Raspberry Pi 키오스크 및 로컬 프린트 서비스 설정
- `docs/`: 설계서, 구현 계획, 세션 기록, 논문 준비 문서
  - `docs/specs/2026-06-01-rag-answer-quality-design.md`: RAG 답변 품질과 JSON 계약 설계 문서
- `eval/`: 논문 및 RAG 평가용 질문 데이터셋과 평가 스크립트
- `static/`: 정적 HTML 등 외부 제공용 파일
- `chromadb/`: 로컬 ChromaDB 데이터

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
