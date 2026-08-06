# 세션 기반 프로젝트 기록

이 디렉터리는 Campus Copilot 개발 과정에서 논의·결정·구현·검증된 내용을 도메인별로 정리한 기록입니다.

목적은 두 가지입니다.

1. 포트폴리오나 논문에서 사용할 수 있는 “문제 → 비교 → 선택 → 결과” 흐름을 보존한다.
2. 구현 문서(`docs/kiosk/specs`, `docs/kiosk/plans`)에 포함되기 어려운 의사결정 맥락과 운영 판단을 별도로 보존한다.

## 문서 목록

- [프로젝트 개요와 문서화 흐름](./project-overview-and-docs.md)
- [크롤링·파싱·URL 스코프](./crawl-parse-url-scope.md)
- [청킹과 문서 구조 보존](./chunking-and-document-structure.md)
- [임베딩 전환과 Docker 의존성 최적화](./embedding-and-dependency-optimization.md)
- [런타임 데이터·BM25·인덱싱 검증](./runtime-data-bm25-indexing.md)
- [RAG 답변 품질과 출처 표시 계약](./rag-answer-quality-and-source-contract.md)
- [RAG 평가 방법과 정량 지표](./rag-evaluation-methods.md)
- [문서 재배치·다이어그램·커밋 전략](./documentation-relocation-and-diagrams.md)
- [GitHub 공개 준비와 시크릿 점검](./git-publication-and-secret-audit.md)
- [검색 개선 여정: RRF 융합, 어휘 갭 실패 분석, Best Bets](./retrieval-rrf-vocabulary-gap-best-bets.md)

## 읽는 방법

각 문서는 세션 당시 확인된 내용을 기준으로 작성했습니다. 이후 코드가 변경되었을 수 있으므로, 논문이나 최종 포트폴리오에 반영하기 전에는 링크된 코드·커밋·문서를 다시 확인해야 합니다.

`공란/미확인`으로 표시한 항목은 세션 데이터에 남아 있지 않거나 확정 근거가 부족한 부분입니다.
