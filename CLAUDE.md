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
  - `docs/kiosk/specs/2026-06-01-rag-answer-quality-design.md`: RAG 답변 품질과 JSON 계약 설계 문서
- `eval/`: 논문 및 RAG 평가용 질문 데이터셋과 평가 스크립트
- `static/`: 정적 HTML 등 외부 제공용 파일
- `chromadb/`: 로컬 ChromaDB 데이터

## Crawl Pipeline CLI

크롤은 discover → parse → index 페이즈로 분리되어 있고, 필요한 구간만 골라 실행할 수 있습니다.
진입점은 `worker/tasks/pipeline.py`이며 관리자 대시보드의 크롤 버튼도 같은 파이프라인(full)을 실행합니다.

```bash
# 풀크롤 (discover→parse→index, 대시보드 버튼과 동일)
docker compose exec worker python -m tasks.pipeline

# 재파싱+재색인만: 네트워크 discovery 없이 target artifact + fetch 캐시로 재처리
docker compose exec worker python -m tasks.pipeline --from parse

# 재색인만 (pending chunk 임베딩 + BM25 재작성)
docker compose exec worker python -m tasks.pipeline --from index

# 대상 개수만 확인 (색인/저장 없음)
docker compose exec worker python -m tasks.pipeline --dry-run

# 변경이 없어도 전부 재파싱 (파서 수정 반영 등)
docker compose exec worker python -m tasks.pipeline --from parse --force
```

동작 규칙:

- `--from parse`는 마지막 성공 크롤이 저장한 target artifact(`CRAWL_TARGET_ARTIFACT_PATH`)를
  읽습니다. artifact가 없으면 에러가 나므로 풀크롤(discover)을 먼저 1회 실행하세요.
- 재파싱은 fetch 캐시(`CRAWL_FETCH_CACHE_DIR`)를 cache_first로 읽어 네트워크 재요청을 피합니다.
  캐시 미스만 네트워크로 폴백합니다.
- 파서를 수정하면 `worker/tasks/parse.py`의 `PARSER_VERSION`을 범프하세요. content_hash에
  버전이 포함되어 다음 실행에서 자동으로 전부 재파싱됩니다(`--force` 불필요).
- 색인 입력 규칙(제목·메뉴 경로를 본문 앞에 붙임)이 바뀌면 전량 재임베딩이 필요합니다:
  `UPDATE document_chunks SET chroma_id = NULL;` 실행 후 `--from index`를 돌리세요
  (같은 chroma ID로 덮어써서 프룬이 필요 없습니다).
- index 페이즈는 문서 검색 키워드(`documents.search_keywords`, BM25 전용 문서 확장)를
  생성할 수 있지만 **기본 비활성**입니다(`SEARCH_KEYWORD_GENERATION_ENABLED=true`로 켬).
  N=20 평가에서 MRR 소폭 하락이 확인되어, 질문셋 확장 후 재검증 전까지 꺼 둡니다.
  켜면 활성+키워드 NULL 문서만 대상이라 재실행해도 중복 생성이 없고, 본문이 바뀌면
  자동으로 NULL로 리셋됩니다. `GEMINI_API_KEY`가 없으면 조용히 스킵합니다.
  키워드 프롬프트(`worker/tasks/keywords.py`)를 수정하면 전량 재생성이 필요합니다:
  `UPDATE documents SET search_keywords = NULL;` 실행 후 `--from index`를 돌리세요
  (재임베딩과 달리 임베딩 비용이 없고 BM25만 다시 씁니다).
- 동시 실행은 Postgres advisory lock으로 보호됩니다. 스케줄 크롤과 CLI가 겹치면 늦게 온 쪽이
  조용히 skip됩니다(status="skipped").

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
