# 크롤링·파싱·청킹·색인 파이프라인

## 목적

worker 크롤링 작업은 주소 수집, 검증, 문서 fetch, 파싱, 청킹, 저장, 벡터/BM25 색인을 단일 `run_crawl()` 흐름에서 수행한다. 정리 범위는 현재 실행 단위와 중간 산출물 경계다.

## 현재 전체 흐름

```mermaid
flowchart TD
    ADMIN["Admin UI\nPOST /api/v1/admin/crawl"]
    BACKEND["Backend\nadmin.trigger_crawl()"]
    WORKER_API["Worker trigger API\nPOST /internal/crawl"]
    RUN["run_crawl()\nworker/tasks/crawl.py"]

    HTML_DISCOVERY["HTML 대상 수집\n discover_html_targets_with_failures()"]
    PDF_DISCOVERY["PDF 대상 수집\n discover_pdf_targets()"]
    LIMIT["대상 제한\n apply_crawl_target_limit()"]

    INGEST["execute_ingestion()"]
    JOB_START["crawl_jobs 생성\n create_crawl_job()"]
    EXISTING["기존 문서 상태 조회\n load_existing_document_states()"]

    PROCESS["대상별 처리\n fetch_and_maybe_parse_documents()"]
    FETCH_HTML["HTML fetch\n fetch_html()"]
    FETCH_PDF["PDF fetch\n fetch_pdf_bytes()"]
    HASH["content_hash 비교\n build_content_hash()"]
    SKIP{"기존 hash와 같고\nchunk_count > 0?"}

    PARSE_HTML["HTML 파싱\n parse_html()"]
    PARSE_PDF["PDF 파싱\n parse_pdf()"]
    CHUNK["청킹/정규화\n markdown_blocks_to_chunks()\n markdown_to_text_chunks()"]
    PERSIST["문서 저장\n persist_document()"]

    INDEX["색인 생성\n index_crawl_documents()"]
    EMBED["Embedding + Chroma upsert\n embed_pending_chunks()"]
    PRUNE["Orphan vector 정리\n prune_orphan_vectors()"]
    BM25["BM25 인덱스 작성\n write_bm25_indexes()"]
    JOB_DONE["crawl_jobs 완료/실패 기록\n finish_crawl_job()"]

    ADMIN --> BACKEND --> WORKER_API --> RUN
    RUN --> HTML_DISCOVERY
    RUN --> PDF_DISCOVERY
    HTML_DISCOVERY --> LIMIT
    PDF_DISCOVERY --> LIMIT
    LIMIT --> INGEST
    INGEST --> JOB_START --> EXISTING --> PROCESS

    PROCESS --> FETCH_HTML --> HASH
    PROCESS --> FETCH_PDF --> HASH
    HASH --> SKIP
    SKIP -->|yes| INDEX
    SKIP -->|no, html| PARSE_HTML
    SKIP -->|no, pdf| PARSE_PDF
    PARSE_HTML --> CHUNK
    PARSE_PDF --> CHUNK
    CHUNK --> PERSIST --> INDEX
    INDEX --> EMBED --> PRUNE --> BM25 --> JOB_DONE
```

## HTML 대상 수집 흐름

```mermaid
flowchart TD
    ROOTS["settings.crawl_target_urls"]
    MAIN["각 root /main fetch"]
    MENU["메인 메뉴 추출\nextract_menu_targets()"]
    DEPT["학과 사이트 추출\nextract_department_sites()"]
    DEPT_MAIN["학과별 /main fetch"]
    DEPT_MENU["학과 메뉴 추출"]
    DEDUPE["URL 중복 제거\ndedupe_targets()"]
    EXPAND["상세 페이지 후보 확인\nexpand_article_box_targets_by_parent()"]
    RETRY["실패 후보 재확인"]
    FINAL_VALIDATE["대상 URL 최종 검증\nvalidate_targets_with_failures()"]
    RESULT["CrawlDiscoveryResult\n targets + failures"]

    ROOTS --> MAIN --> MENU --> DEPT
    DEPT --> DEPT_MAIN --> DEPT_MENU --> DEDUPE
    MENU --> DEDUPE
    DEDUPE --> EXPAND --> RETRY --> FINAL_VALIDATE --> RESULT
```

HTML discovery는 메뉴 수집, 학과 사이트 확장, `article.articleBox` 후보 확장, 실패 후보 재시도, 최종 본문 검증을 포함한다.

## 문서 처리와 청킹 흐름

```mermaid
flowchart TD
    TARGET["CrawlTarget"]
    TYPE{"source_type"}

    HTML_FETCH["HTML fetch"]
    ARTICLE["article 영역 추출\nextract_article_html()"]
    HTML_HASH["article_html + parser version + target metadata\ncontent_hash"]
    CRAWL4AI["crawl4ai raw HTML -> Markdown\nArticleMarkdownRenderer"]

    PDF_FETCH["PDF bytes fetch"]
    PDF_HASH["pdf bytes + parser version + target metadata\ncontent_hash"]
    PDF_LOADER["OpenDataLoaderPDFLoader\nPDF -> Markdown documents"]

    BLOCKS["Markdown block 분리\nsplit_markdown_ordered_blocks()"]
    TEXT["Text block\nMarkdownHeaderTextSplitter\nRecursiveCharacterTextSplitter\nchunk_size=500, overlap=100"]
    TABLE["Table block\nnormalize_markdown_table()\n표는 table chunk로 보존"]
    HTML_TABLE["HTML 원본 table 재추출\nextract_html_table_chunks()"]
    ROADMAP["학기 로드맵 파생 chunk\nbuild_semester_roadmap_chunks()"]
    DOC["ParsedDocument\ntext/table chunks"]

    TARGET --> TYPE
    TYPE -->|html| HTML_FETCH --> ARTICLE --> HTML_HASH --> CRAWL4AI --> BLOCKS
    TYPE -->|pdf| PDF_FETCH --> PDF_HASH --> PDF_LOADER --> BLOCKS
    BLOCKS --> TEXT --> DOC
    BLOCKS --> TABLE --> DOC
    ARTICLE --> HTML_TABLE --> DOC
    TABLE --> ROADMAP --> DOC
```

## 단계별 현재 경계

| 단계 | 현재 대표 함수 | 현재 산출물 | 재시작/재사용 관점 |
| --- | --- | --- | --- |
| 트리거 | `CrawlTriggerService.trigger()` | worker 메모리 상태 | 실행 중복 방지만 수행. 단계별 resume 단위 없음 |
| HTML discovery | `discover_html_targets_with_failures()` | `CrawlDiscoveryResult` | DB/파일 저장 없음 |
| PDF discovery | `discover_pdf_targets()` | `list[CrawlTarget]` | DB/파일 저장 없음 |
| 대상 제한 | `apply_crawl_target_limit()` | 제한된 target 목록 | 실행 중 메모리 값 |
| crawl job 시작 | `create_crawl_job()` | `crawl_jobs` row | 진행률/결과 기록용. target manifest 저장 없음 |
| 기존 문서 비교 | `load_existing_document_states()` + `build_content_hash()` | skip/change 판단 | 원문 raw cache 없이 매번 URL fetch 후 비교 |
| HTML 파싱 | `parse_html()` | `ParsedDocument` | markdown/raw HTML 중간 산출물 저장 없음 |
| PDF 파싱 | `parse_pdf()` | `ParsedDocument` | PDF bytes/loader 결과 중간 산출물 저장 없음 |
| 청킹 | `markdown_blocks_to_chunks()` | `ParsedChunk` 목록 | parser/chunking 변경 시 기존 chunk 재생성 단위가 문서 저장과 결합됨 |
| 저장 | `persist_document()` | `documents`, `document_chunks` | 문서 단위로 기존 chunk 삭제 후 새 chunk 삽입 |
| 벡터 색인 | `index_crawl_documents()` | Chroma vector + `chroma_id` | `chroma_id IS NULL` chunk만 pending 처리 |
| BM25 작성 | `write_bm25_indexes()` | `.data/bm25` cache | 벡터 색인 단계 뒤에 같은 ingestion 흐름에서 실행 |
| 완료 기록 | `finish_crawl_job()` | `crawl_jobs.status` | 전체 흐름의 완료/실패만 기록 |

## 현재 구조에서 오래 걸리는 이유

현재 실행 단위는 다음과 같이 구성된다.

```text
run_crawl()
  = URL discovery
  + URL validation
  + document fetch
  + HTML/PDF parsing
  + chunking
  + PostgreSQL persistence
  + Chroma embedding
  + BM25 indexing
```

파싱 또는 청킹 로직 검증 시에도 표준 진입점은 주소 수집과 URL 검증부터 다시 시작한다. discovery 결과, 검증된 target manifest, raw HTML/PDF, Markdown 변환 결과, chunk 결과가 독립적인 재사용 산출물로 남지 않는다.

## 모듈화 시 나눌 만한 실행 단위

현재 흐름 기준의 후보 실행 단위는 다음과 같다. 미구현 구조다.

```mermaid
flowchart LR
    A["1. target discovery\nURL manifest 생성"]
    B["2. target validation\n검증된 URL manifest 생성"]
    C["3. raw fetch\nHTML/PDF 원문 cache"]
    D["4. parse\nParsedDocument 또는 Markdown 산출"]
    E["5. chunk\nParsedChunk 산출"]
    F["6. persist\nPostgreSQL 반영"]
    G["7. index\nChroma/BM25 갱신"]

    A --> B --> C --> D --> E --> F --> G
```

해당 경계가 분리되면 청킹 로직 변경 시 `raw fetch` 또는 `parse` 산출물을 재사용하고, `chunk -> persist -> index` 단계만 재실행할 수 있다.

## 관련 코드

- [worker/tasks/crawl.py](../../../worker/tasks/crawl.py)
- [worker/tasks/parse.py](../../../worker/tasks/parse.py)
- [worker/tasks/parsers/markdown.py](../../../worker/tasks/parsers/markdown.py)
- [worker/tasks/storage.py](../../../worker/tasks/storage.py)
- [worker/tasks/embed.py](../../../worker/tasks/embed.py)
- [worker/tasks/bm25.py](../../../worker/tasks/bm25.py)
- [worker/tasks/trigger.py](../../../worker/tasks/trigger.py)
- [backend/app/api/routes/admin.py](../../../backend/app/api/routes/admin.py)
