# Worker 테스트 사용법

대부분의 worker 테스트는 별도 환경 변수 없이 실행된다.

```bash
cd worker
uv run pytest
```

일부 테스트는 실제 호남대학교 사이트, 로컬 DB, 파일 출력 등을 사용하므로 기본적으로 skip된다. 아래 환경 변수를 명시해야 실행된다.

## 실제 크롤 URL 목록 확인

실제 호남대학교 사이트에서 최종 크롤 대상 URL 목록을 수집하고 콘솔에 출력한다.

```bash
cd worker
RUN_LIVE_CRAWL_URLS=1 uv run pytest tests/tasks/test_live_crawl_urls.py -s -v
```

HTML URL 출력 개수 제한을 없애려면 `LIVE_CRAWL_URL_LIMIT=0`을 함께 지정한다.

```bash
cd worker
RUN_LIVE_CRAWL_URLS=1 LIVE_CRAWL_URL_LIMIT=0 uv run pytest tests/tasks/test_live_crawl_urls.py -s -v
```

## 실제 크롤 대상 CSV 리포트 생성

실제 크롤 대상 URL을 수집하고 `source_scope`, `page_kind` 등을 포함한 CSV 리포트를 생성한다.

```bash
cd worker
RUN_LIVE_CRAWL_TARGET_REPORT=1 uv run pytest tests/tasks/test_live_crawl_target_report.py --mode=fast -s -v
```

실행 중에는 단계별 진행률이 출력된다.

```text
[  12.34s] 홈페이지 메뉴 수집 중: 1/2 ( 50.0%)
[  45.67s] 상세 페이지 후보 확인 중: 120/733 ( 16.4%)
```

개별 fetch URL까지 보고 싶으면 `--verbose-fetch`를 함께 지정한다.

```bash
cd worker
RUN_LIVE_CRAWL_TARGET_REPORT=1 \
uv run pytest tests/tasks/test_live_crawl_target_report.py \
  --mode=full \
  --verbose-fetch \
  -s -v
```

`--mode`는 두 값을 지원한다.

```text
fast: 대표/학과 메인 메뉴 기준으로 빠르게 리포트를 만든다.
full: 상세 페이지 확장과 최종 URL 검증까지 포함한다.
```

HTML fetch 결과는 기본으로 `.data/live-crawl-cache/`에 캐시된다. 캐시를 무시하고 다시 가져오려면 `--force`를 지정한다.

```bash
cd worker
RUN_LIVE_CRAWL_TARGET_REPORT=1 \
uv run pytest tests/tasks/test_live_crawl_target_report.py --mode=full --force -s -v
```

기본 출력 위치는 다음과 같다.

```text
eval/results/crawl-targets-MODE-YYYYMMDD-HHMMSS.csv
eval/results/crawl-target-summary-MODE-YYYYMMDD-HHMMSS.csv
eval/results/crawl-raw-links-MODE-YYYYMMDD-HHMMSS.csv
```

`crawl-raw-links-...csv`는 DOM에서 발견한 원본 링크를 기록한다. `data_link_true`는 링크에 `data-link="true"`가 붙었는지, `accepted_by_selector`는 현재 크롤 selector에 포함됐는지, `accepted_as_target`은 최종 대상 URL에 남았는지를 뜻한다.

출력 디렉터리를 바꾸려면 `--out-dir`를 지정한다.

```bash
cd worker
RUN_LIVE_CRAWL_TARGET_REPORT=1 \
uv run pytest tests/tasks/test_live_crawl_target_report.py \
  --mode=fast \
  --out-dir=/tmp/crawl-report \
  -s -v
```

파일명을 고정해야 하면 `--timestamp`를 지정한다.

```bash
cd worker
RUN_LIVE_CRAWL_TARGET_REPORT=1 \
uv run pytest tests/tasks/test_live_crawl_target_report.py \
  --mode=fast \
  --timestamp=manual \
  -s -v
```

## 실제 페이지 파싱 샘플 확인

실제 호남대학교 HTML/PDF 페이지를 가져와 파싱 결과 샘플을 콘솔에 출력한다.

```bash
cd worker
RUN_LIVE_PARSE=1 uv run pytest tests/tasks/test_live_parse_samples.py -s -v
```

## 실제 메뉴/학과 페이지 샘플 확인

실제 대표 홈페이지와 학과 사이트 메뉴 일부를 가져와 HTML 구조와 본문 선택 결과를 콘솔에 출력한다.

```bash
cd worker
RUN_LIVE_CRAWL=1 uv run pytest tests/tasks/test_live_crawl_sample.py -s -v
```

## asyncpg JSONB 저장 회귀 확인

실제 PostgreSQL 연결을 사용해 JSONB 저장 동작을 확인한다. 로컬 DB가 떠 있어야 한다.

```bash
cd worker
RUN_DB_STORAGE=1 uv run pytest tests/tasks/test_storage.py::test_asyncpg_jsonb_requires_serialized_meta -s -v
```

필요하면 `DATABASE_URL`을 함께 지정한다.

```bash
cd worker
DATABASE_URL=postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot \
RUN_DB_STORAGE=1 \
uv run pytest tests/tasks/test_storage.py::test_asyncpg_jsonb_requires_serialized_meta -s -v
```
