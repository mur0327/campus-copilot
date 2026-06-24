# 런타임 데이터·BM25·인덱싱 검증

## 도메인

RAG 런타임 데이터 저장 위치, BM25 sparse index cache, Chroma dense vector index, ingestion 완료 검증 영역입니다.

## 목표

두 가지 문제를 순차적으로 정리했습니다.

1. `.data`가 root, backend, worker 아래에 여러 개 생기는 문제를 정리하기
2. Docker 컨테이너에서 임베딩/인덱싱이 정상 완료됐는지 실제 runtime evidence로 확인하기

## 문제 1: `.data`가 여러 곳에 생김

원인은 container 내부 경로와 host filesystem 경로가 혼동된 데 있었습니다.

당시 구조에서는 `./backend:/app`, `./worker:/app` 같은 bind mount와 `/app/.data/bm25` target, 상대 cache path가 섞이면서 host의 `backend/.data`, `worker/.data`가 생길 수 있었습니다.

해결 기준은 container 내부 경로가 아니라 host에서 관리 가능한 repo-root `.data`였습니다.

## 선택: repo-root `.data` 하나로 통합

결정:

- repo-root `.data`를 runtime data root로 사용
- `.data`는 Git ignore 유지
- BM25 cache는 root `.data/bm25`로 통합
- Compose에 임시 env override를 쌓지 않고 `.env.example`과 실제 env 값을 source of truth로 정리

현재 `.env.example` 기준:

- `RETRIEVER_BM25_CACHE_DIR=../.data/bm25`
- `BM25_CACHE_DIR=../.data/bm25`

backend/worker 하위에서 실행해도 `../.data/bm25`가 repo-root `.data/bm25`를 가리키도록 정리했습니다.

## BM25 env 역할

`BM25_CACHE_DIR`와 `RETRIEVER_BM25_CACHE_DIR`는 이름이 비슷하지만 소유자가 다릅니다.

| env | 소유 컴포넌트 | 역할 |
| --- | --- | --- |
| `BM25_CACHE_DIR` | worker | crawl/indexing 중 BM25 pickle 파일을 씀 |
| `RETRIEVER_BM25_CACHE_DIR` | backend | chat retrieval 중 worker가 만든 BM25 pickle 파일을 읽음 |

두 값은 같은 물리 디렉터리를 가리켜야 합니다.

파일 형식은 `bm25-<sha256(category)[:16]>.pkl`이고, category `None`은 `_all`에 대응합니다.

## 문제 2: 임베딩 완료 여부 확인

Docker 컨테이너 로그를 기준으로 임베딩이 정상 완료됐는지 확인했습니다. 한 로그 라인만으로 판단하지 않고, 여러 runtime source를 교차 확인했습니다.

확인한 것:

- `docker ps`
- worker logs
- backend admin status API
- PostgreSQL count
- Chroma collection count

당시 확인된 값:

- documents: `50`
- chunks: `257`
- indexed_chunks: `257`
- Chroma `campus_copilot_chunks`: `257` vectors
- worker log: `crawl indexing completed ... pending_after=0`
- crawl log: `pages_crawled=50`, `pages_changed=50`, `failures=0`

## 비교한 판단 방식

- 한 로그 라인을 보고 성공/실패 판단
- backend status만 보고 판단
- DB count만 보고 판단
- worker log + backend status + PostgreSQL + Chroma를 함께 확인

선택한 방식은 네 번째였습니다.

## 결과

임베딩/인덱싱 완료는 정상으로 판단했습니다. backend log에 `stale running crawl job cleaned up by admin status`처럼 의심스러운 메시지가 있었지만, 최신 crawl job 상태와 Chroma vector count가 맞았기 때문에 실패로 보지 않았습니다.

## 포트폴리오/논문 포인트

- dense vector store와 sparse BM25 cache를 함께 쓰는 hybrid retrieval 운영 구조입니다.
- ingestion 완료 조건을 “문서 수 → chunk 수 → indexed chunk 수 → vector count”로 검증했습니다.
- runtime data path를 host 운영 가능성 중심으로 정리했습니다.

## 관련 코드·자료

- [.env.example](../../.env.example)
- [docker-compose.yml](../../docker-compose.yml)
- [backend/app/services/retriever.py](../../backend/app/services/retriever.py)
- [worker/tasks/bm25.py](../../worker/tasks/bm25.py)
- [worker/tasks/crawl.py](../../worker/tasks/crawl.py)
- [Phase 4 indexing/search/RAG design](../specs/2026-05-06-phase-4-indexing-search-rag-design.md)
- 관련 커밋:
  - `1f065a7 fix(env): update BM25 cache directory paths in .env and docker-compose`
  - `eb2be69 feat(rag): build bm25 indexes in worker`
  - `229f644 feat(worker): index chunks into chromadb`

## 주석

- `.data`는 Git ignore 대상이므로 `git stash -a` 같은 명령은 주의해야 합니다.
- ignored runtime data를 건드리지 않으려면 `git stash push -u`가 더 안전한 흐름입니다.

## 공란/미확인

- 운영 환경에서 `.data` 권한을 어떤 uid/gid/mode로 최종 고정할지는 세션 데이터만으로 확정되지 않습니다.
- BM25 cache invalidation 정책의 장기 운영 기준은 별도 실험이 필요합니다.
