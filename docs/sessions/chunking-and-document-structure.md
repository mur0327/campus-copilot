# 청킹과 문서 구조 보존

## 도메인

크롤링된 HTML/PDF 문서를 RAG 검색에 적합한 chunk로 나누는 영역입니다. 학사 안내 문서는 절차, 표, 제목 계층이 중요하기 때문에 단순 문자 수 분할만으로는 정보 구조가 흐트러질 수 있습니다.

## 목표

청킹에 사용된 기술을 실제 코드와 문서 기준으로 확인하는 것이 목표였습니다. 일반적인 RAG 청킹 개념 설명이 아니라, Campus Copilot worker에서 실제로 사용하는 구현을 기준으로 정리했습니다.

## 문제

문서마다 형식이 다릅니다.

- HTML 본문
- PDF에서 추출된 Markdown 성격의 텍스트
- 표 형태의 학점/요건 정보
- 제목 계층이 있는 공지/학사 안내 문서

이 문서들을 모두 같은 방식으로 자르면 표가 깨지거나 제목 맥락이 사라질 수 있습니다.

## 확인한 구현

현재 text chunking은 `langchain-text-splitters`를 사용합니다.

1. `MarkdownHeaderTextSplitter`
   - `#`, `##`, `###`, `####` 헤더 기준으로 1차 분할
   - 헤더 metadata를 보존

2. `RecursiveCharacterTextSplitter`
   - `chunk_size=500`
   - `chunk_overlap=100`
   - `add_start_index=True`

코드 기준으로는 `worker/tasks/parsers/markdown.py`의 `markdown_to_text_chunks()`가 중심입니다.

```python
header_splitter = MarkdownHeaderTextSplitter(...)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    add_start_index=True,
)
```

HTML과 PDF는 모두 Markdown 계열 표현으로 정규화된 뒤 이 청킹 경로를 탑니다.

## 표 처리

표는 일반 텍스트와 다르게 다룹니다.

- Markdown table block을 먼저 감지합니다.
- 일반 text chunk처럼 recursive split하지 않습니다.
- 하나의 `ParsedChunk(chunk_type="table")`로 보존합니다.
- 졸업학점 같은 특수 테이블은 별도 normalization 경로를 가집니다.

이 선택은 학사 안내 도메인에서 중요합니다. 표는 행·열 관계가 깨지면 답변 근거로 활용하기 어렵기 때문입니다.

## 비교한 선택지

- 단순 fixed-size text split
- token 기반 split
- Markdown header-aware split
- 표를 text로 펼친 뒤 split
- 표를 별도 chunk type으로 보존

현재 구현은 “Markdown header-aware split + recursive character split + table-preserving chunk”에 가깝습니다.

## 선택 이유

- 제목 구조를 metadata로 남길 수 있습니다.
- chunk 크기를 제한하면서도 앞뒤 overlap으로 문맥 손실을 줄일 수 있습니다.
- 표는 문서 구조를 유지해야 하기 때문에 text chunk와 다르게 보존합니다.
- HTML/PDF 모두 같은 Markdown 기반 처리로 합류시켜 구현 복잡도를 줄입니다.

## 결과

Campus Copilot의 chunking은 단순 텍스트 분할이 아니라, 학사 문서의 구조를 검색 가능한 단위로 보존하는 설계로 정리할 수 있습니다.

## 관련 코드·자료

- [worker/tasks/parsers/markdown.py](../../worker/tasks/parsers/markdown.py)
- [worker/tasks/parsers/html_tables.py](../../worker/tasks/parsers/html_tables.py)
- [worker/tasks/parse.py](../../worker/tasks/parse.py)
- [Phase 2 crawling/parsing design](../kiosk/specs/2026-04-19-phase-2-crawling-parsing-design.md)
- 관련 커밋 예시:
  - `bf1d128 feat(worker): add html parsing pipeline`
  - `e1da17a feat(worker): add pdf parsing pipeline`
  - `d82f903 feat(worker): normalize parser output`
  - `be3b594 fix(rag): expand detail table context`

## 포트폴리오/논문 포인트

- “문서 구조 보존형 RAG chunking” 사례로 설명할 수 있습니다.
- 표 정보를 별도 chunk type으로 보존한 점은 학사 안내 도메인에 맞춘 설계 판단입니다.
- header metadata는 검색 결과의 맥락 해석과 답변 근거 구성에 도움을 줍니다.

## 공란/미확인

- chunk size 500 / overlap 100의 정량적 최적화 실험 결과는 세션 데이터에 없습니다.
- 표 chunk와 text chunk의 retrieval 성능 차이를 별도로 측정한 기록은 없습니다.
