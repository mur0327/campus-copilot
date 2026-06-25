# 관련 연구

### 관련 연구 찾기 [관련 논문](02-related-work.md)

---

> *남들은 이 문제를 어떻게 해결했고, 내 프로젝트는 어디가 어떻게 다른가?*
>

| 분야 | 왜 필요한가 |
| --- | --- |
| RAG | 검색해서 답변하는 기본 기술 |
| Dense Retrieval / BM25 | 문서 검색 성능 비교 |
| 하이브리드 검색 | 키워드 검색 + 의미 검색 결합 근거 |
| Citation / Grounded QA | 출처 있는 답변의 필요성 |
| Freshness-aware QA | 최신 정보 반영 필요성 |
| Public service UX / Kiosk UX | 키오스크 안내 서비스 근거 |
| RAG Evaluation | Recall@k, MRR, nDCG 같은 평가 지표 근거 |

| 논문 | 어디에 쓸 것인가 |
| --- | --- |
| RAG 원 논문 | RAG 개념 설명 |
| DPR 논문 | 벡터 검색 설명 |
| BM25/BEIR 관련 논문 | 검색 성능 평가 기준 |
| RAGAS | RAG 답변 평가 |
| FreshLLMs | 최신성 반영 필요성 |
| ALCE/Citation 논문 | 출처 있는 답변 필요성 |
| ConflictRAG | 문서 충돌 탐지 근거 |

### 관련 논문

---

| 분야 | 논문 |
| --- | --- |
| RAG 기본 | Lewis et al., **Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks**, 2020. ([arXiv](https://arxiv.org/abs/2005.11401?utm_source=chatgpt.com)) |
| Dense Retrieval | Karpukhin et al., **Dense Passage Retrieval for Open-Domain Question Answering**, 2020. ([arXiv](https://arxiv.org/abs/2004.04906?utm_source=chatgpt.com)) |
| 검색 평가 기준 | Thakur et al., **BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models**, 2021. ([arXiv](https://arxiv.org/abs/2104.08663?utm_source=chatgpt.com)) |
| 최신/동적 지식 | Vu et al., **FreshLLMs: Refreshing Large Language Models with Search Engine Augmentation**, 2023. ([arXiv](https://arxiv.org/abs/2310.03214?utm_source=chatgpt.com)) |
| 인용/출처 평가 | Gao et al., **Enabling Large Language Models to Generate Text with Citations**, 2023. ([arXiv](https://arxiv.org/abs/2305.14627?utm_source=chatgpt.com)) |
| 자기 검증 RAG | Asai et al., **Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection**, 2023. ([arXiv](https://arxiv.org/abs/2310.11511?utm_source=chatgpt.com)) |
| RAG 평가 | Es et al., **RAGAS: Automated Evaluation of Retrieval Augmented Generation**, 2023. ([arXiv](https://arxiv.org/abs/2309.15217?utm_source=chatgpt.com)) |
| 사실성 평가 | Min et al., **FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation**, 2023. ([arXiv](https://arxiv.org/abs/2305.14251?utm_source=chatgpt.com)) |
| 적응형 RAG | Jeong et al., **Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity**, 2024. ([arXiv](https://arxiv.org/abs/2403.14403?utm_source=chatgpt.com)) |
| 충돌 처리 RAG | Wang et al., **ConflictRAG: Detecting and Resolving Knowledge Conflicts in Retrieval Augmented Generation**, 2026. ([arXiv](https://arxiv.org/abs/2605.17301?utm_source=chatgpt.com)) |
