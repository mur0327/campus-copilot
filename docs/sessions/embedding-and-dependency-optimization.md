# 임베딩 전환과 Docker 의존성 최적화

## 도메인

RAG 검색 품질과 배포 비용을 동시에 좌우하는 embedding provider, Python dependency, Docker reproducibility 영역입니다.

## 목표

초기 문제는 Docker build가 과도하게 무거워진 원인을 파악하는 것이었습니다. 추측이 아니라 실제 lockfile과 manifest를 기준으로 원인을 확인했습니다.

이후 로컬 embedding stack을 Voyage AI 기반으로 전환했습니다.

## 문제 1: 무거운 로컬 임베딩 의존성

조사 결과 `sentence-transformers`가 `torch`를 끌어오고, lockfile에는 CUDA/NVIDIA wheel과 `triton`이 포함되어 있었습니다.

원인 chain은 다음과 같이 정리됩니다.

- `sentence-transformers`
- `torch`
- CUDA/NVIDIA 관련 wheel
- `nvidia-cublas`
- `nvidia-cudnn-cu13`
- `triton`

worker Dockerfile에는 `playwright install --with-deps chromium`도 있어 build가 더 무거울 수 있었습니다.

## 비교한 선택지

초기에는 `sentence-transformers`를 유지하는 전제에서 네 가지 방향을 비교했습니다.

1. `torch`를 CPU-only wheel로 고정
2. CPU/GPU extras split
3. embedding을 worker-only로 좁힘
4. embedding을 별도 서비스로 분리

우선순위는 CPU-only wheel 고정으로 정했습니다.

## 선택 1: CPU-only torch

backend와 worker 양쪽에 PyTorch CPU wheel index를 명시하고 lockfile을 다시 생성했습니다.

결과:

- CUDA/NVIDIA/triton package entry 제거
- backend/worker lockfile에 CPU torch 반영
- `uv lock --check`로 확인
- 커밋: `10b17a4 build(deps): use cpu-only torch wheels`

## 문제 2: 로컬 임베딩 유지 자체의 운영 비용

이후 더 큰 방향으로 local embedding dependency를 제거하고 Voyage AI를 사용하기로 결정했습니다.

기존 구조:

- backend query embedding도 `SentenceTransformer`
- worker document embedding도 `SentenceTransformer`

변경 구조:

- backend query embedding: Voyage AI, `input_type="query"`
- worker document embedding: Voyage AI, `input_type="document"`
- 기본 모델: `voyage-4-large`
- local `sentence-transformers`/`torch` 제거
- Hugging Face cache volume 제거

## 선택 2: Voyage AI adapter 도입

backend와 worker에 각각 provider adapter를 만들었습니다.

- [backend/app/services/embedding_provider.py](../../backend/app/services/embedding_provider.py)
- [worker/tasks/embedding_provider.py](../../worker/tasks/embedding_provider.py)

adapter는 다음 성격을 가집니다.

- `input_type`을 `document` 또는 `query`로 제한
- `VOYAGE_API_KEY` 없을 때 명확히 실패
- 429/5xx/network 계열 오류에 retry
- 테스트에서는 fake client를 주입해 실제 API 호출 없이 검증

현재 `.env.example`에는 `EMBEDDING_MODEL=voyage-4-large`, `VOYAGE_API_KEY=`, `CHROMA_COLLECTION=campus_copilot_chunks`가 포함되어 있습니다.

## Docker reproducibility 문제

리뷰 중 Dockerfile이 `pyproject.toml`만 복사하고 `uv sync --no-dev`를 실행한다는 문제가 확인됐습니다. 이 경우 lockfile로 검증한 dependency set과 Docker image의 실제 설치 결과가 달라질 수 있습니다.

수정:

- backend Dockerfile: `COPY pyproject.toml uv.lock ./`
- worker Dockerfile: `COPY pyproject.toml uv.lock ./`
- 양쪽 모두 `uv sync --locked --no-dev`

현재 코드:

- [backend/Dockerfile](../../backend/Dockerfile)
- [worker/Dockerfile](../../worker/Dockerfile)

## 결과

Voyage migration 결과는 다음과 같이 검증됐습니다.

- backend targeted pytest: `21 passed`
- worker targeted pytest: `48 passed`
- backend/worker `ruff check .` 통과
- `docker compose config --quiet` 통과
- 커밋: `d383913 feat(rag): use voyage embeddings`

## 중요한 운영 결정

임베딩 provider를 바꿨지만, 자동 재색인 감지는 이번 범위에서 제외했습니다.

기존 Chroma/Postgres reset과 reindex 관리는 수동으로 수행하는 전제로 정리했습니다. 따라서 다음 사실을 명시했습니다.

- 기존 indexed chunk는 `document_chunks.chroma_id IS NULL` 조건에 의해 자동 재임베딩되지 않습니다.
- collection 이름은 `campus_copilot_chunks` 그대로 유지했습니다.
- provider 변경이 곧 semantic namespace 변경이나 자동 reindex를 의미하지 않습니다.

## 포트폴리오/논문 포인트

- 로컬 embedding model의 Docker 비용을 lockfile 근거로 분석했습니다.
- CPU-only wheel이라는 점진적 최적화와 API 기반 embedding 전환을 모두 다뤘습니다.
- document/query input type 분리는 검색 품질 설계 포인트로 사용할 수 있습니다.
- Docker reproducibility를 위해 lockfile-pinned install을 적용했습니다.

## 관련 코드·자료

- [backend/app/services/embedding_provider.py](../../backend/app/services/embedding_provider.py)
- [worker/tasks/embedding_provider.py](../../worker/tasks/embedding_provider.py)
- [backend/app/api/routes/chat.py](../../backend/app/api/routes/chat.py)
- [worker/tasks/embed.py](../../worker/tasks/embed.py)
- [backend/app/core/config.py](../../backend/app/core/config.py)
- [worker/core/config.py](../../worker/core/config.py)
- [.env.example](../../.env.example)
- [backend/Dockerfile](../../backend/Dockerfile)
- [worker/Dockerfile](../../worker/Dockerfile)
- 관련 커밋:
  - `10b17a4 build(deps): use cpu-only torch wheels`
  - `d383913 feat(rag): use voyage embeddings`

## 공란/미확인

- Voyage AI 전환 전후 retrieval quality를 같은 eval set으로 비교한 결과는 세션 데이터에 없습니다.
- API 비용, latency, rate limit 관측값은 아직 문서화되어 있지 않습니다.
