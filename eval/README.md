# Evaluation

이 디렉터리는 Campus Copilot의 RAG 검색 성능과 출처 후보 품질을 확인하기 위한 평가 자료를 둔다.

## 파일 구성

- `questions.csv`: 평가 질문 데이터셋이다.
- `gold_sources.csv`: 질문별 사람이 확인한 공식 정답 문서 목록이다.
- `run_questions.py`: 현재 로컬 `.data`에 적재된 문서를 기준으로 질문별 retrieval 결과를 수집하는 스크립트다.
- `analyze_retrieval_chunks.py`: retrieval JSONL을 chunk 단위 CSV로 펼쳐 파싱 품질과 evidence 후보를 점검하는 스크립트다.
- `results/`: 스크립트 실행 결과가 저장되는 디렉터리다. 결과 파일은 재생성 가능한 산출물이므로 Git에 커밋하지 않는다.

## questions.csv

`questions.csv`는 다음 필드를 사용한다.

```csv
id,category,question,question_type,gold_url,gold_title,answerability,needs_procedure,expected_keywords,notes
```

- `id`: 평가 케이스 ID다.
- `category`: 질문의 업무 카테고리다.
- `question`: 실제로 시스템에 보낼 질문이다.
- `question_type`: 평가 데이터셋에서만 사용하는 질문 분류값이다.
- `gold_url`: 사람이 확인한 공식 정답 문서 URL이다.
- `gold_title`: 사람이 확인한 공식 정답 문서 제목이다.
- `answerability`: 기대 답변 가능 상태다. `answerable`, `partial`, `insufficient` 중 하나를 사용한다.
- `needs_procedure`: 절차형 안내가 필요한 질문인지 표시한다.
- `expected_keywords`: 답변이나 출처 확인 시 참고할 핵심어다.
- `notes`: 라벨링 메모다.

### questions.csv 값

`category`는 질문을 업무 영역별로 나누기 위한 값이다. 현재 초안은 다음 값을 사용한다.

- `휴학/복학`
- `장학금`
- `등록금`
- `수강신청`
- `졸업/학점`
- `성적/시험`
- `증명서`
- `입학/편입`
- `학사일정`
- `부서/문의처`

`question_type`은 평가 데이터셋에서만 사용하는 질문 분류값이다. 채팅 API의 JSON 계약 필드는 아니다.

- `fact`: 단일 사실이나 제도 내용을 묻는 질문이다.
- `procedure`: 사용자가 따라야 할 절차를 묻는 질문이다.
- `date`: 기간, 일정, 마감일을 묻는 질문이다.
- `contact`: 담당 부서, 문의처, 전화번호를 묻는 질문이다.
- `policy`: 조건, 기준, 규정을 묻는 질문이다.

`answerability`는 공식 문서 근거 기준으로 기대하는 답변 가능 상태다.

- `answerable`: 공식 문서만으로 답변할 수 있는 질문이다.
- `partial`: 일부는 답변할 수 있지만 추가 확인이 필요한 질문이다.
- `insufficient`: 현재 공식 문서 근거만으로는 답변하기 어려운 질문이다.

`needs_procedure`는 절차형 안내 필요 여부다.

- `true`: `procedure_steps` 평가가 필요한 질문이다.
- `false`: 절차 단계보다 사실, 일정, 문의처 확인이 중심인 질문이다.

`expected_keywords`는 세미콜론(`;`)으로 구분한다.

```text
휴학;신청;절차;서류
```

초기 단계에서는 `gold_url`과 `gold_title`을 비워둘 수 있다. 다중 정답 문서가 필요한 질문은 `gold_sources.csv`를 기준으로 라벨링한다.

## gold_sources.csv

`gold_sources.csv`는 질문 하나에 정답 문서가 여러 개일 수 있는 경우를 다룬다.

```csv
question_id,gold_url,gold_title,relevance,source_scope,page_kind,notes
```

- `question_id`: `questions.csv`의 `id`와 연결되는 값이다.
- `gold_url`: 사람이 확인한 공식 정답 문서 URL이다.
- `gold_title`: 사람이 확인한 공식 정답 문서 제목이다.
- `relevance`: 해당 문서가 정답으로 쓰이는 정도다.
- `source_scope`: 문서의 출처 범위다.
- `page_kind`: 문서의 기능이나 주제 종류다.
- `notes`: 라벨링 근거와 주의사항이다.

### gold_sources.csv 값

`relevance`는 다음 값을 사용한다.

- `primary`: 질문에 직접 답하는 핵심 정답 문서다.
- `secondary`: 조건에 따라 함께 정답으로 인정할 수 있는 문서다.
- `related`: 후속 설명이나 인접 질문에는 유용하지만, 단독 핵심 정답은 아닌 문서다.

`source_scope`는 출처 범위를 나타내며 다음 값을 사용한다.

- `general_academic`: 재학생 일반 학사 행정 안내 문서다.
- `admission`: 신입학, 편입학, 입학 상담 문서다.
- `department`: 특정 학과나 학과 사이트 문서다.
- `unknown`: 아직 출처 범위를 확정하지 못한 문서다.

`page_kind`는 문서 기능이나 주제 종류를 나타내며 다음 값을 사용한다.

- `academic`: 일반 학사, 제도, 안내 문서다.
- `admission`: 입학, 편입, 입학 상담 관련 문서다.
- `schedule`: 학사일정 문서다.
- `certificate`: 증명서 발급 문서다.
- `contact`: 부서, 담당자, 연락처 안내 문서다.
- `unknown`: 아직 문서 기능을 확정하지 못한 문서다.

`source_scope`와 `page_kind` 분류 규칙만 바뀐 경우 본문 `content_hash`는 변하지 않을 수 있다. 이 경우 기존 DB 문서, Chroma metadata, BM25 cache를 갱신하는 별도 metadata refresh 작업이 필요하며, 해당 작업은 후속 과제로 분리한다.

검색 성능 평가에서는 보통 `primary`와 `secondary`를 정답 URL로 사용한다. `related`는 분석 메모나 후속 답변 품질 평가에 활용한다.

## 실행 전 조건

현재 스크립트는 로컬 Docker Compose 서비스가 떠 있는 상태를 기본값으로 삼는다.

필요한 데이터는 다음 위치에 있어야 한다.

- `.data/postgres`
- `.data/chromadb`
- `.data/bm25`

기본 실행은 localhost에 공개된 PostgreSQL, ChromaDB, BM25 cache를 사용한다. 컨테이너 내부나 별도 환경에서 실행할 때는 `--no-local-services`를 사용한다.

## 사용법

1문항만 먼저 확인한다.

```bash
uv run --project backend python eval/run_questions.py --limit 1
```

전체 질문을 실행한다.

```bash
uv run --project backend python eval/run_questions.py
```

특정 데이터셋 카테고리만 실행한다.

```bash
uv run --project backend python eval/run_questions.py --category "휴학/복학"
```

출력 위치를 바꾼다.

```bash
uv run --project backend python eval/run_questions.py --out-dir /tmp/campus-copilot-eval
```

최신 retrieval JSONL을 chunk 단위 CSV로 펼친다.

```bash
python3 eval/analyze_retrieval_chunks.py
```

특정 질문만 확인한다.

```bash
python3 eval/analyze_retrieval_chunks.py --question-id Q016 --question-id Q017
```

입력 파일과 출력 파일을 직접 지정한다.

```bash
python3 eval/analyze_retrieval_chunks.py \
  --input eval/results/retrieval-20260628-055432.jsonl \
  --output eval/results/retrieval-chunks-debug.csv
```

기본 출력은 chunk 내용의 preview만 포함한다. 입력 JSONL에 full content가 있는 경우 `--include-content`를 지정하면 `content` 컬럼도 함께 출력한다.

## 출력 파일

실행 결과는 기본적으로 `eval/results/`에 저장된다.

- `retrieval-YYYYMMDD-HHMMSS.jsonl`: 질문별 상세 retrieval 결과다.
- `retrieval-YYYYMMDD-HHMMSS.csv`: 빠르게 검토하기 위한 요약 결과다.
- `retrieval-chunks-YYYYMMDD-HHMMSS.csv`: retrieval/evidence 후보를 chunk 단위로 펼친 분석 결과다.

JSONL에는 다음 정보가 포함된다.

- 질문 ID와 질문 본문
- 데이터셋의 질문 분류값
- backend가 분류한 질문 의도
- retrieval 상태
- 최종 top-k 검색 후보
- 답변 프롬프트에 들어갈 수 있는 evidence 후보

CSV는 URL과 제목 중심의 요약 검토용이다. 논문용 Recall@k, MRR, nDCG 계산은 `gold_sources.csv` 라벨링을 마친 뒤 별도 채점 스크립트에서 수행한다.

### 결과 CSV 값

`retrieval-YYYYMMDD-HHMMSS.csv`는 다음 주요 필드를 사용한다.

- `dataset_question_type`: `questions.csv`의 `question_type`을 복사한 값이다.
- `classified_intent`: backend retriever가 질문 문구에서 추정한 의도다.
- `retrieval_mode`: 실제 사용된 검색 모드다.
- `degraded`: 일부 검색 경로가 실패해 degraded 상태로 실행됐는지 여부다.
- `semantic_available`: ChromaDB semantic 검색 사용 가능 여부다.
- `bm25_available`: BM25 keyword 검색 사용 가능 여부다.
- `semantic_error`: semantic 검색 실패 시 예외 이름이다.
- `bm25_error`: BM25 검색 실패 시 원인 메시지다.
- `retrieved_count`: 최종 top-k 검색 후보 수다.
- `evidence_count`: 답변 프롬프트에 들어갈 수 있도록 필터링된 evidence 후보 수다.
- `gold_urls`: `gold_sources.csv`에 라벨링된 공식 정답 문서 URL 목록이다.
- `gold_relevance`: 정답 문서별 relevance 목록이다.
- `gold_source_scopes`: 정답 문서별 `source_scope` 목록이다.
- `gold_page_kinds`: 정답 문서별 `page_kind` 목록이다.
- `gold_hit_top`: `primary` 또는 `secondary` 정답 문서가 top-k 검색 후보에 포함됐는지 여부다.
- `gold_hit_top_rank`: top-k 검색 후보에서 정답 문서가 처음 등장한 순위다.
- `gold_hit_evidence`: `primary` 또는 `secondary` 정답 문서가 evidence 후보에 포함됐는지 여부다.
- `gold_hit_evidence_rank`: evidence 후보에서 정답 문서가 처음 등장한 순위다.
- `top_urls`: 최종 top-k 검색 후보 URL 목록이다. 파이프(`|`)로 구분한다.
- `evidence_urls`: evidence 후보 URL 목록이다. 파이프(`|`)로 구분한다.
- `top_titles`: 최종 top-k 검색 후보 제목 목록이다. 파이프(`|`)로 구분한다.
- `top_source_scopes`: 최종 top-k 검색 후보의 `source_scope` 목록이다.
- `top_page_kinds`: 최종 top-k 검색 후보의 `page_kind` 목록이다.
- `evidence_source_scopes`: evidence 후보의 `source_scope` 목록이다.
- `evidence_page_kinds`: evidence 후보의 `page_kind` 목록이다.

`classified_intent` 값은 backend의 가벼운 질문 의도 분류 결과다.

- `procedure`: `어떻게`, `신청`, `절차`, `방법` 등 절차성 표현이 있는 질문이다.
- `deadline`: `언제`, `기간`, `마감`, `일정` 등 일정성 표현이 있는 질문이다.
- `requirement`: `조건`, `기준`, `요건`, `서류` 등 요구사항 표현이 있는 질문이다.
- `contact`: `문의`, `담당`, `전화`, `연락` 등 문의처 표현이 있는 질문이다.
- `factual`: `무엇`, `얼마`, `몇`, `누구` 등 사실 확인 표현이 있는 질문이다.
- `unknown`: 위 규칙에 명확히 걸리지 않은 질문이다.

`retrieval_mode` 값은 다음 의미다.

- `hybrid`: semantic 검색과 BM25 검색을 모두 사용했다.
- `semantic_only`: semantic 검색만 사용했다.
- `keyword_only`: BM25 검색만 사용했다.
- `empty`: 사용 가능한 검색 결과가 없었다.

`degraded`, `semantic_available`, `bm25_available`은 문자열 `True` 또는 `False`로 저장된다.

### Chunk 분석 CSV 값

`retrieval-chunks-YYYYMMDD-HHMMSS.csv`는 다음 주요 필드를 사용한다.

- `question_id`: 평가 질문 ID다.
- `question`: 질문 본문이다.
- `row_type`: `retrieved` 또는 `evidence`다.
- `rank`: retrieved 후보의 순위다.
- `source_number`: evidence 후보의 출처 번호다.
- `overlap`: evidence 후보의 질문 키워드 겹침 수다.
- `score`: retrieval 점수다.
- `url`: 후보 chunk의 문서 URL이다.
- `source_scope`: 후보 문서의 출처 범위다.
- `page_kind`: 후보 문서의 기능 분류다.
- `chunk_id`: chunk ID다.
- `document_id`: 문서 ID다.
- `chunk_index`: 문서 내부 chunk 순서다.
- `chunk_type`: `text` 또는 `table`이다.
- `content_length`: JSONL에 들어 있는 content 또는 preview의 길이다.
- `content_preview`: chunk 내용을 검토하기 위한 preview다.
- `content_available`: 입력 JSONL에 full `content` 필드가 있었는지 여부다.

실행 후 콘솔에는 입력/출력 파일, 질문 수, retrieved/evidence 행 수, evidence 후보가 0개인 질문 ID가 출력된다.
