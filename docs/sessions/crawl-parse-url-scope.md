# 크롤링·파싱·URL 스코프

## 도메인

호남대학교 공식 웹사이트에서 학사 안내에 필요한 HTML/PDF 문서를 수집하고, RAG 인덱싱에 사용할 수 있는 파싱 결과로 만드는 영역입니다.

## 목표

URL 파싱 흐름을 실제 코드 기준으로 설명하고, 현재 구현된 URL 제한을 어떤 용어로 정리할 수 있는지 검토하는 것이 목표였습니다.

## 문제

“파싱 URL 제한”이라는 표현만으로는 구현 범위를 정확히 설명하기 어렵습니다. 실제 코드에서는 parser 하나가 URL을 제한하는 것이 아니라 다음 단계들이 함께 작동합니다.

- 시작 URL 설정
- 메뉴/학과 사이트 discovery
- 도메인 필터링
- 상세 페이지 확장
- 유효성 검증
- HTML/PDF 병합 후 최종 `crawl_target_limit` 적용

따라서 단순히 “parser URL filter”라고 부르면 설계 범위가 실제보다 좁게 해석될 수 있습니다.

## 확인한 코드 흐름

중심 entrypoint는 `worker/tasks/crawl.py`의 `run_crawl()`입니다. 코드 흐름은 다음과 같이 정리됩니다.

1. HTML 대상 수집
   - `discover_html_targets_with_failures()`
   - `crawl_target_urls`와 `/main`에서 시작
   - `ul#mainMenu`를 읽어 메뉴 링크 확장
   - `ul#universityTop`에서 학과 사이트를 수집하고 각 학과의 `/main` 메뉴를 다시 확장
   - `article.articleBox a[href]`로 상세 페이지를 따라감

2. PDF 대상 수집
   - `discover_pdf_targets()`
   - 연도 제한 등 PDF 대상 조건 적용

3. URL 스코프 제한
   - `honam.ac.kr` 도메인만 유지
   - 다운로드 URL/외부 URL 제외
   - `Page Moved` 페이지 제외
   - `article.articleBox`가 없는 페이지 제외

4. 최종 제한
   - `apply_crawl_target_limit()`
   - HTML/PDF를 합친 뒤 `CRAWL_TARGET_LIMIT`에 따라 잘라냄

5. 실제 파싱
   - HTML은 `parse_html()`
   - PDF는 `parse_pdf()`

현재 코드에서도 `apply_crawl_target_limit()`는 HTML/PDF 대상을 합친 뒤 제한을 적용합니다.

```python
combined_targets = [*html_targets, *pdf_targets]
limited_targets = combined_targets[: settings.crawl_target_limit]
```

## 비교한 표현

검토한 표현은 다음과 같습니다.

- URL allowlist
- URL filtering
- crawl scope
- parsing scope
- URL scope restriction
- domain/path allowlist

## 선택

문서 표현으로는 “URL allowlist 기반 parsing scope 제한” 또는 “crawl scope 제한”이 가장 적합합니다.

정확히 말하면 이 기능은 “parser-only 제한”이 아니라 “공식 도메인과 문서 구조를 기준으로 한 crawl/discovery/validation scope 제한”입니다.

## 결과

포트폴리오나 논문에서는 이 부분을 “도메인 특화 ingestion pipeline”으로 설명할 수 있습니다. 일반 웹 크롤러가 아니라, 호남대학교 공식 사이트 구조에 맞춰 수집 범위를 제한하고 유효한 본문 문서만 파싱하는 구조입니다.

## 관련 코드·자료

- [worker/tasks/crawl.py](../../worker/tasks/crawl.py)
- [worker/tasks/parse.py](../../worker/tasks/parse.py)
- [worker/core/config.py](../../worker/core/config.py)
- [Phase 2 crawling/parsing design](../kiosk/specs/2026-04-19-phase-2-crawling-parsing-design.md)
- 관련 커밋 예시:
  - `8936458 feat(worker): add crawl target discovery`
  - `bf1d128 feat(worker): add html parsing pipeline`
  - `e1da17a feat(worker): add pdf parsing pipeline`
  - `accca9a feat(worker): implement honam crawl discovery`
  - `d82f903 feat(worker): normalize parser output`

## 주석

- `crawl_target_limit`은 개발·검증 중 수집량을 줄이는 데도 사용할 수 있습니다.
- URL 제한은 품질과 비용 양쪽에 영향을 줍니다. 공식 문서만 남기면 hallucination 위험은 낮아지지만, 실제 답변 가능한 범위도 수집 범위에 강하게 묶입니다.

## 공란/미확인

- 실제 운영에서 최종적으로 어떤 URL allowlist를 고정할지는 미확인입니다.
- 학과별 사이트 구조가 변경될 때 자동으로 감지하거나 보정하는 정책은 세션 데이터에 확정되어 있지 않습니다.
