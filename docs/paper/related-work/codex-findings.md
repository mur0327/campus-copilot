# Codex 담당 관련 연구 재조사 결과

**상태: 조사 완료, 병합 대기.**
**작성일 2026-07-16.**

`docs/paper/related-work/INSTRUCTIONS.md`의 공통 계약을 따르며, 병합 결과는 `docs/paper/19-paper-master.md`에 반영한다.
범위는 축 1(검색 기법), 축 4(미응답·거절·선택적 답변), 축 7(판정 방법론)이고, 위상 태그는 02 문서와 같다(📗 정통/저명 · 📘 심사 통과 · 📄 preprint/tech report · ❓ 등급 낮음/불명).
표의 모든 확정·보류 문헌은 원문 또는 공식 학술 페이지에서 제목·저자·게재처를 확인했다.

## 1. 요약

| 축 | 핵심 문헌 수 | 신규성 위협 | 결론 |
| --- | ---: | --- | --- |
| 1. BM25·dense·Hybrid·RRF | 10 | 부분적으로 있음 | BM25–dense 상보성, 조건부 fusion 이득, RRF 민감성은 이미 알려져 있다. 현재 RQ1의 가치는 새 검색 원리가 아니라 동일 운영 조건의 대학 행정 코퍼스에서 관찰한 coverage–ranking trade-off에 있다. |
| 4. sufficient context·unanswerability·abstention | 12 | 중대함 | MTRAG/MTRAGEval이 완전·부분·미응답 문항과 생성 행동을 이미 연결한다. 다만 두 연구의 주 채점 gate는 완전·부분 문항을 같은 답변 측으로 묶으므로, 현재 연구의 정확한 `full/qualified/abstain` 기대–실제 일치 판정과 완전히 같지는 않다. |
| 7. pooled judgment·LLM 보조 판정·사람 감사 | 12 | 구성요소 수준에서 있음 | pooling, LLM 초벌+사람 검증, 부분·층화 감사는 선행연구가 있다. 현재 절차는 새 판정 방법으로 주장하기보다 제한된 pool에서의 보수적 사례연구 절차로 방어해야 한다. |

## 2. 신규성 위협

1. 가장 큰 위협은 축 4다. MTRAG는 질문을 answerable/partially answerable/unanswerable로 구분하고 생성 응답의 IDK 여부를 no/partial/yes로 판정하며, MTRAGEval은 underspecified 질문의 clarification까지 추가한다. 따라서 “RAG에서 완전·부분·거절 행동을 구분하거나 기대 answerability와 실제 생성을 대조한 최초 연구”라는 주장은 방어하기 어렵다.
2. 그러나 동일 평가 설계는 아니다. MTRAG와 MTRAGEval의 answerability-conditioned 표는 answerable과 partially answerable를 모두 `IDK=no 또는 partial`인 답변 측으로 처리한다. 현재 연구처럼 `full_answer → full`, `qualified_answer → qualified`, `abstain → abstain`의 정확한 3단계 일치를 독립 채점하는 구조는 확인한 문헌에서 찾지 못했다.
3. 축 1의 lexical–dense 상보성, zero-shot hybrid 이득, in-domain fusion 손해 가능성, RRF 파라미터 민감성은 모두 선행 결과다. RQ1은 보편적 우월성이나 새 fusion 원리를 주장할 수 없다.
4. 축 7의 pooled qrel, LLM 초벌, 사람의 표적·표본 검증도 새 방법이 아니다. 특히 높은 run-level 상관만으로 문서별 gold 타당성이나 새 시스템에 대한 공정성을 보장할 수 없다는 반례가 있으므로, 현재 판정 절차 자체를 방법론 기여로 내세우면 위험하다.
5. 확인한 문헌 중 페이지 회수·내용 정확성·근거·시간/대상자 적합성·기대 응답 행동을 한 기관 행정 RAG에서 함께 분해한 완전한 동일 연구는 없었다. 이 판단은 정본의 기여 문구를 대신하지 않으며, 최종 주장은 별도 정본 리뷰에서 결정해야 한다.

## 3. 축 1: 검색 기법 원 논문과 최근 비교

| 문헌 | 위상 | 확인 | 본 연구와의 관계 | 권고 |
| --- | --- | --- | --- | --- |
| Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” NeurIPS 2020 | 📗 | [NeurIPS 공식 페이지](https://proceedings.neurips.cc/paper/2020/hash/6b493230-Abstract.html), 2026-07-16 | RAG의 parametric/non-parametric memory 결합 계보다. 현재의 분리된 검색·생성 파이프라인이 원 논문의 공동학습 구조와 같다는 근거는 아니다. 기존 02의 제목에는 마지막 `Tasks`가 빠져 있다. | 인용 확정 후보. RAG 계보에 쓰되 구현 동일성은 주장하지 않는다. |
| Karpukhin et al., “Dense Passage Retrieval for Open-Domain Question Answering,” EMNLP 2020 | 📗 | [ACL Anthology](https://aclanthology.org/2020.emnlp-main.550/), 2026-07-16 | dual encoder dense retrieval의 대표 원 논문이다. 특정 ODQA 조건의 BM25 대비 이득은 현재 Voyage 기반 Semantic 경로의 일반적 우월성을 뜻하지 않는다. | 인용 확정 후보. Semantic-only의 방법 계보로 사용한다. |
| Thakur et al., “BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models,” NeurIPS 2021 | 📗 | [NeurIPS 공식 페이지](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html), 2026-07-16 | 이질적 데이터셋에서 BM25가 강건한 zero-shot baseline이며 단일 retriever가 항상 우세하지 않음을 보인다. 현재 단일 코퍼스 결과의 일반화 한계를 뒷받침한다. | 인용 확정 후보. baseline과 도메인별 변동 근거로 사용한다. |
| Cormack, Clarke, Büttcher, “Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods,” SIGIR 2009 | 📗 | [저자 공식 PDF](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)·[DOI](https://doi.org/10.1145/1571941.1572114), 2026-07-16 | RRF와 `Σ 1/(k+r(d))`의 원 출처다. `k=60`은 파일럿에서 near-optimal로 선택된 뒤 후속 검증에서 고정됐으며, 처음부터 튜닝과 무관한 보편 표준값은 아니다. | 인용 확정 후보. “본 연구 데이터로 재튜닝하지 않은 literature-derived 설정”까지만 말한다. |
| Formal, Piwowarski, Clinchant, “SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking,” SIGIR 2021 | 📗 | [arXiv 원문](https://arxiv.org/abs/2107.05720)·[DOI](https://doi.org/10.1145/3404835.3463098), 2026-07-16 | 학습된 sparse expansion이 전통 lexical과 dense 사이의 대안임을 보여준다. 현재 RQ1의 세 구성에는 포함되지 않는다. | 보류. learned sparse 대안을 구분할 지면이 있을 때만 쓴다. |
| Robertson et al., “Okapi at TREC-3,” TREC-3/NIST SP 500-225, 1994/1995 | 📗 | [NIST TREC 공식 페이지](https://pages.nist.gov/trec-browser/trec3/adhoc/proceedings/)·[NIST proceedings](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication500-225.pdf), 2026-07-16 | Okapi term weighting과 길이·빈도 보정의 역사적 계보다. 한 편으로 완결된 BM25 설명을 맡기기에는 2009 정리 논문이 더 적합하다. | 보류. 역사적 기원 보조 인용으로만 사용한다. |
| Robertson, Zaragoza, “The Probabilistic Relevance Framework: BM25 and Beyond,” Foundations and Trends in IR 3(4), 2009 | 📗 | [출판사 공식 페이지](https://www.nowpublishers.com/article/Details/INR-019), 2026-07-16 | PRF부터 BM25/BM25F의 가정·유도·파라미터를 체계적으로 정리한 자가완결적 정본이다. | 인용 확정 후보. 마스터의 BM25 대표 인용으로 권고한다. |
| Chen et al., “Out-of-Domain Semantics to the Rescue! Zero-Shot Hybrid Retrieval Models,” ECIR 2022 | 📘 | [Springer 공식 페이지](https://link.springer.com/chapter/10.1007/978-3-030-99736-6_7)·[arXiv 원문](https://arxiv.org/abs/2201.10582), 2026-07-16 | domain shift에서 dense가 약해지고 lexical이 강건하며, 서로 다른 관련 문서를 회수하는 상보성 때문에 zero-shot RRF가 이득을 낼 수 있음을 보인다. | 인용 확정 후보. 상호 보완 가능성의 조건부 근거로 쓴다. |
| Bruch, Gai, Ingber, “An Analysis of Fusion Functions for Hybrid Retrieval,” ACM TOIS 42(1), 2024 (online 2023) | 📘 | [DOI](https://doi.org/10.1145/3596512)·[arXiv 원문](https://arxiv.org/abs/2210.11934), 2026-07-16 | RRF가 파라미터에 민감하고, 실험한 in/out-of-domain 조건에서 정규화 점수 convex combination이 RRF보다 우세함을 보인다. `k=60`의 보편적 최적성에 대한 직접 반대 근거다. | 인용 확정 후보. RRF를 안전한 보편 기본값으로 과장하지 않게 한다. |
| Louis, van Dijck, Spanakis, “Know When to Fuse: Investigating Non-English Hybrid Retrieval in the Legal Domain,” COLING 2025 | 📘 | [ACL Anthology](https://aclanthology.org/2025.coling-main.290/), 2026-07-16 | 비영어 특수 도메인에서 zero-shot fusion은 도움이 됐지만 in-domain 학습 후에는 많은 fusion 조합이 단일 시스템보다 악화됐다. fusion 효과가 도메인·학습·결합 방식에 의존함을 보인다. | 인용 확정 후보. 현재의 단일 우세 없음과 trade-off 해석에 가장 가깝다. |

기존 02의 다섯 항목은 모두 실재하지만 Lewis와 DPR의 정식 제목을 고쳐야 하고, BM25 정본이 빠져 있었다. 가장 중요한 사실 수정은 RRF `k=60`으로, 원 논문의 파일럿에서 선택된 값이지 “튜닝 아님”인 관행값이 아니다. BEIR만으로는 hybrid 비교를 뒷받침할 수 없으므로 Chen·Bruch·Louis를 함께 놓아 상보성과 fusion 손해 가능성을 모두 보여주는 편이 정확하다. 이 축의 문헌은 현재 RQ1 결과를 “Hybrid 승리/실패”가 아니라 도메인·cutoff·결합 방식에 따른 coverage–ranking trade-off로 제한해 해석하도록 요구한다.

## 4. 축 4: 미응답·거절·선택적 답변

| 문헌 | 위상 | 확인 | 본 연구와의 관계 | 권고 |
| --- | --- | --- | --- | --- |
| Geifman, El-Yaniv, “Selective Classification for Deep Neural Networks,” NeurIPS 2017 | 📗 | [NeurIPS 공식 페이지](https://papers.nips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html), 2026-07-16 | 정한 위험 이하에서 coverage를 최대화하는 selective prediction의 고전이다. QA/RAG 전용은 아니지만 선택적 거절의 이론적 배경이다. | 인용 확정 후보. 지면이 좁으면 Kamath et al.과 통합한다. |
| Rajpurkar, Jia, Liang, “Know What You Don’t Know: Unanswerable Questions for SQuAD,” ACL 2018 | 📗 | [ACL Anthology](https://aclanthology.org/P18-2124/), 2026-07-16 | 근거가 있으면 답하고 없으면 abstain하는 unanswerable QA의 대표 이진 계약이다. 부분 답변이나 RAG retrieval 상태는 다루지 않는다. | 인용 확정 후보. 고전 축을 보강한다. |
| Kamath, Jia, Liang, “Selective Question Answering under Domain Shift,” ACL 2020 | 📗 | [ACL Anthology](https://aclanthology.org/2020.acl-main.503/), 2026-07-16 | IID/OOD 혼합에서 목표 정확도를 유지하며 답변 coverage를 넓히는 selective QA와 risk–coverage를 평가한다. 현재 RQ3의 행동 일치율과는 목적 함수가 다르다. | 인용 확정 후보. selective QA의 직접 선행연구로 쓴다. |
| Peng et al., “Unanswerability Evaluation for Retrieval Augmented Generation,” ACL 2025 | 📗 | [ACL Anthology](https://aclanthology.org/2025.acl-long.415/), 2026-07-16 | UAEval4RAG가 여섯 미응답 유형을 만들고 actual output을 answered/clarification/unanswered 및 acceptable ratio로 평가한다. 구성별로 answerable와 unanswerable 성능의 균형이 달라진다. | 인용 확정 후보. 기존 핵심 문헌을 유지하되 제목과 지표 해석을 바로잡는다. |
| Joren et al., “Sufficient Context: A New Lens on Retrieval Augmented Generation Systems,” ICLR 2025 | 📗 | [ICLR 공식 proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/file/33dffa2e3d2ab74a783d1a8c292f66d9-Paper-Conference.pdf)·[arXiv](https://arxiv.org/abs/2411.06037), 2026-07-16 | context sufficient/insufficient와 actual correct/incorrect/abstain을 교차한다. 불충분 문맥에서도 일부 정답 복원이 가능하므로 sufficiency만으로 강제 거절을 정당화하지는 못한다. | 인용 확정 후보. 기대 조건과 실제 행동의 분리 근거로 쓴다. |
| Liu et al., “Investigating Retrieval-Augmented Generation Systems on Unanswerable, Uncheatable, Realistic, Multi-hop Queries,” ECIR 2026 | 📘 | [Springer 공식 페이지](https://link.springer.com/chapter/10.1007/978-3-032-21300-6_26), 2026-07-16 | CRUMQs가 완전·부분 미응답 multi-hop 질문에서 acceptable/unanswered/clarification/accuracy를 평가한다. 현재의 정확한 3단계 기대–실제 일치 행렬은 아니다. | 인용 확정 후보. 기존 02의 preprint 표기를 정식 게재본으로 갱신한다. |
| Madhusudhan et al., “Do LLMs Know When to NOT Answer? Investigating Abstention Abilities of Large Language Models,” COLING 2025 | 📘 | [ACL Anthology](https://aclanthology.org/2025.coling-main.627/), 2026-07-16 | 기대 answerable/unanswerable와 actual answered/abstained 및 정오답을 교차한다. RAG가 아니고 부분 답변이 없는 이진 설정이다. | 보류. 기대–실제 행동 대조의 근접 선행이나 MTRAG가 더 직접적이다. |
| Kim et al., “When to Speak, When to Abstain: Contrastive Decoding with Abstention,” ACL 2025 | 📗 | [ACL Anthology](https://aclanthology.org/2025.acl-long.479/), 2026-07-16 | 내부 지식과 제공 문맥의 가용성을 조합해 answer/abstain 기대 행동을 정한다. 생성 방법 논문이며 부분 답변은 없다. | 보류. 선택적 생성 방법을 짧게 구분할 때 사용한다. |
| Katsis et al., “mt RAG: A Multi-Turn Conversational Benchmark for Evaluating Retrieval-Augmented Generation Systems,” TACL 2025 | 📗 | [ACL Anthology](https://aclanthology.org/2025.tacl-1.36/), 2026-07-16 | 질문을 answerable/partially answerable/unanswerable로 라벨링하고 응답의 IDK를 no/partial/yes로 판정한다. 다만 주 metric conditioning은 answerable과 partial 문항을 같은 답변 측으로 묶으므로 현재의 정확한 3단계 일치 채점과는 다르다. | 인용 확정 후보(최우선). 가장 직접적인 신규성 위협으로 반드시 다룬다. |
| Rosenthal et al., “MTRAG-UN: A Benchmark for Open Challenges in Multi-Turn RAG Conversations,” Findings of ACL 2026 | 📘 | [ACL Anthology](https://aclanthology.org/2026.findings-acl.503/), 2026-07-16 | 6개 도메인에서 unanswerable, underspecified, non-standalone 질문과 unclear response를 포함한 666개 대화 태스크로 MTRAG를 확장한다. 현재 단일-turn 기관 행정 설정과는 범위가 다르다. | 인용 확정 후보. MTRAGEval의 benchmark 근거로 함께 쓴다. |
| Muhamed et al., “RefusalBench: Generative Evaluation of Selective Refusal in Grounded Language Models,” EACL 2026 | 📘 | [ACL Anthology](https://aclanthology.org/2026.eacl-long.321/), 2026-07-16 | 교란 강도에 따른 기대 answer/refuse와 실제 false/missed refusal, 답변·거절 품질을 분해한다. 부분 답변은 없지만 단순 거절률보다 세밀하다. | 인용 확정 후보. 최신 grounded selective-refusal 평가로 쓴다. |
| Rosenthal et al., “SemEval-2026 Task 8: MTRAGEval: Evaluating Multi-Turn RAG Conversations,” SemEval 2026 | 📘 | [ACL Anthology](https://aclanthology.org/2026.semeval-1.447/), 2026-07-16 | answerable/partial/unanswerable에 IDK judge를 적용하고 underspecified에는 clarification judge를 둔다. partial 문항은 `IDK=no 또는 partial`을 모두 허용하므로 exact partial-match 평가는 아니지만 현재 행동 분해에 강한 선행이다. | 인용 확정 후보(최우선). MTRAG의 2026 확장으로 반드시 다룬다. |

기존 02의 UAEval4RAG는 프레임워크 이름이고 정식 논문 제목은 *Unanswerability Evaluation for Retrieval Augmented Generation*이다. 기존의 `acceptable ratio 49.0%`도 순수 거절률이 아니라 유형별 허용 행동을 합친 값이므로 그렇게 고쳐 읽어야 한다. Sufficient Context의 큰 방향은 유지되지만 “insufficient이면 항상 abstain”으로 단순화할 수 없고, CRUMQs는 ECIR 2026 정식 논문으로 갱신됐다. 가장 큰 누락은 MTRAG/MTRAG-UN/MTRAGEval이며, 이들 때문에 3단계 answerability나 기대–실제 행동 대조 자체의 최초성은 주장할 수 없지만 exact 3-way match와 시간·대상자 적합성을 포함한 현재 전체 분해까지 동일하지는 않다.

## 5. 축 7: pooled judgment·LLM 보조 판정·사람 감사

아래에서 `P`는 pool 한정 판정, `L`은 LLM 전량 초벌, `A`는 위험 기반·표본 사람 감사, `U`는 top-k에 unjudged가 있으면 채점을 중단하는 gate다.

| 문헌 | 위상 | 확인 | 본 연구와의 관계 | 권고 |
| --- | --- | --- | --- | --- |
| Soboroff, “Overview of TREC 2021,” TREC 2021/NIST, 2021 | 📗 | [NIST 공식 PDF](https://trec.nist.gov/pubs/trec30/papers/Overview-2021.pdf), 2026-07-16 | `P`를 조건부 지지한다. 다양한 강한 run의 상위 결과를 합친 pool은 비교용 qrel이 될 수 있지만 얕거나 편향된 pool은 새 시스템에 불리하다. 전통 TREC는 unjudged를 비관련으로 간주하므로 `U`의 직접 근거는 아니다. | 인용 확정 후보. 결과 범위를 세 고정 시스템의 top-5 pool 안으로 제한하는 근거다. |
| Buckley, Voorhees, “Retrieval Evaluation with Incomplete Information,” SIGIR 2004 | 📗 | [NIST 공식 페이지·원문](https://www.nist.gov/publications/retrieval-evaluation-incomplete-information), 2026-07-16 | 불완전 qrel에서 기존 MAP/P@10/R-precision의 왜곡을 보이고, unjudged를 비관련으로 만들지 않는 bpref를 제시한다. `U`가 보편 규칙이라는 근거는 아니지만, 현재 top-k를 완전 판정해 기존 지표 왜곡을 막으려는 선택을 간접 지지한다. | 인용 확정 후보. 불완전 판정 문제의 정본으로 쓴다. |
| Faggioli et al., “Perspectives on Large Language Models for Relevance Judgment,” ICTIR 2023 | 📘 | [University of Padua 공식 레코드](https://research.unipd.it/handle/11577/3497340), 2026-07-16 | `L`을 보조 수단으로, 사람이 승인·거절하거나 저신뢰 사례를 맡는 `A`를 지지한다. 자동화 편향, 환각 근거, 모델 변화와 판정기–검색기 순환성을 경고한다. | 인용 확정 후보. LLM 초벌이 최종 gold가 아니라는 경계를 세운다. |
| Thomas et al., “Large Language Models Can Accurately Predict Searcher Preferences,” SIGIR 2024 | 📗 | [Microsoft Research 공식 페이지](https://www.microsoft.com/en-us/research/publication/large-language-models-can-accurately-predict-searcher-preferences/), 2026-07-16 | 소량 human gold로 모델·프롬프트를 고른 뒤 대량 판정하고 표본 감사·고정 검증 세트로 감시하는 `L+A` 선례다. 프롬프트 표현에도 성능이 흔들리고 고위험 영역은 추가 인간 검토가 필요하다. | 인용 확정 후보. 웹 검색 환경과 현재 대학 행정 qrel의 범위 차이를 밝힌다. |
| Alaofi et al., “LLMs can be Fooled into Labelling a Document as Relevant: best café near me; this paper is perfectly relevant,” SIGIR-AP 2024 | 📘 | [Microsoft Research 공식 페이지](https://www.microsoft.com/en-us/research/publication/llms-can-be-fooled-into-labelling-a-document-as-relevant-best-cafe-near-me-this-paper-is-perfectly-relevant/), 2026-07-16 | 질의어 삽입과 직접 명령문이 LLM relevance를 부풀릴 수 있음을 보여 `L`의 한계와 표적 `A`의 필요성을 뒷받침한다. | 인용 확정 후보. LLM-positive·비정상 overlap·지시문형 문서 감사 근거로 쓴다. |
| Upadhyay et al., “A Large-Scale Study of Relevance Assessments with Large Language Models Using UMBRELA,” ICTIR 2025 | 📘 | [저자 공식 게재본](https://cs.uwaterloo.ca/~jimmylin/publications/3731120.3744605.pdf), 2026-07-16 | TREC RAG depth-20 pool에서 human, LLM+human, LLM-only qrel의 run 순위가 높은 상관을 보였다. topic-level 상관은 더 낮았고 사람 개입이 항상 순위 상관을 높이지는 않아, 집계 유용성과 문항별 진실을 구분해야 한다. | 인용 확정 후보. 현재 RAG qrel 절차와 가장 가까운 긍정 실증이다. |
| Clarke, Dietz, “LLM-based Relevance Assessment Still Can’t Replace Human Relevance Assessment,” EVIA 2025 | 📘 | [NII 공식 원문](https://research.nii.ac.jp/ntcir/workshop/OnlineProceedings18/pdf/evia/01-EVIA2025-EVIA-ClarkeC.pdf), 2026-07-16 | LLM qrel에 맞춘 reranker가 자동 판정에서는 높고 인간 판정에서는 크게 낮아질 수 있음을 보인다. 높은 run 상관도 새 시스템의 공정성을 보장하지 않아 `L`의 최종 gold 대체를 반박하고 `A`를 지지한다. | 인용 확정 후보. UMBRELA의 낙관적 결과와 함께 제시한다. |
| Fröbe et al., “Large Language Model Relevance Assessors Agree With One Another More Than With Human Assessors,” SIGIR 2025 | 📘 | [University of Glasgow 공식 레코드](https://eprints.gla.ac.uk/352747/), 2026-07-16 | 여러 LLM 판정기가 사람보다 서로 더 강하게 합의하고 LLM 기반 reranker를 구조적으로 높게 평가할 수 있음을 보인다. Claude와 Codex를 나눠 썼다는 사실만으로 독립 gold가 되지 않는다. | 인용 확정 후보. 공유 편향과 순환성 위험의 직접 근거다. |
| Merlo et al., “A Cost-Effective Framework to Evaluate LLM-Generated Relevance Judgements,” CIKM 2025 | 📘 | [University of Padua 공식 레코드](https://www.research.unipd.it/handle/11577/3571881), 2026-07-16 | 제한된 확률표본 human judgment로 LLM 판정 품질을 신뢰수준·비용 아래 추정한다. 위험 사례만 고른 비확률 표본은 전체 오류율이나 IAA를 추정할 수 없다는 현재 감사의 경계를 보여준다. | 인용 확정 후보. 전역 정확도 주장을 금지하는 근거로 쓴다. |
| Merlo et al., “Reducing Human Effort to Validate LLM Relevance Judgements via Stratified Sampling,” ECIR 2026 | 📘 | [University of Padua 공식 레코드](https://www.research.unipd.it/handle/11577/3590312), 2026-07-16 | LLM label·confidence 등에 따른 층화와 순차 판정으로 human effort를 줄인다. 현재 20건 층화 표본의 방향은 지지하지만, 고정 20건 자체가 통계 정밀도를 보장하지는 않는다. | 인용 확정 후보. 표본 감사의 장점과 한계를 함께 밝힌다. |
| Takehi, Voorhees, Sakai, Soboroff, “LLM-Assisted Relevance Assessments: When Should We Ask LLMs for Help?,” SIGIR 2025 | 📘 | [NIST 공식 페이지](https://www.nist.gov/publications/llm-assisted-relevance-assessments), 2026-07-16 | LARA는 LLM 예측과 온라인 보정을 사용해 정보가치가 큰 human label을 선택하고 나머지 판정을 보정한다. `L+A` 원리는 지지하지만 현재의 고정 규칙 위험군 감사와 같은 방법은 아니다. | 인용 확정 후보. hybrid 판정 자체가 신규가 아님을 보여준다. |
| Soboroff, “Don’t Use LLMs to Make Relevance Judgments,” Information Retrieval Research 1(1), 2025 | 📘 | [NIST 공식 페이지](https://www.nist.gov/publications/dont-use-llms-make-relevance-judgments), 2026-07-16 | LLM 판정의 평가대상 편향·재현성·대체 타당성에 강한 반론을 제기한다. human final decision과 민감도 보고가 없는 `L` 단독 설계를 방어하기 어렵게 한다. | 인용 확정 후보. 긍정 문헌과 균형을 이루는 한계 근거다. |

기존 02에는 pooling·불완전 qrel·LLM relevance 판정의 타당성 근거가 사실상 없어 이 축은 새로 보강해야 한다. top-5 union qrel은 세 고정 시스템의 관측된 상위 결과 비교에는 쓸 수 있지만 전체 코퍼스의 정답 완전성이나 새 retriever에 대한 공정성을 보장하지 않는다. 문헌은 LLM 판정의 비용·run-level 상관이라는 효용과 공유 편향·gaming·새 시스템 오평가 위험을 동시에 보여주므로, LLM 초벌 뒤 blind human final decision을 남긴 현재 방향은 보수적으로 방어 가능하다. 다만 위험 표적 67건과 층화 20건만으로 전체 LLM 오류율·IAA를 추정할 수 없고, `unjudged` 시 중단은 TREC/bpref 표준이 아니라 top-5 완전 판정을 강제해 실수로 0점 처리하지 않게 하는 연구별 무결성 invariant다.

## 6. 타 축 후보

- “GaRAGe: A Benchmark with Grounding Annotations for RAG Evaluation”. https://aclanthology.org/2025.findings-acl.875/
- “Do RAG Systems Cover What Matters? Evaluating and Optimizing Responses with Sub-Question Coverage”. https://aclanthology.org/2025.naacl-long.301/
- “Evaluation of a retrieval-augmented generation system using a Japanese Institutional Nuclear Medicine Manual and large language model-automated scoring”. https://link.springer.com/article/10.1007/s12194-025-00941-y
- “A Comparison of Methods for Evaluating Generative IR”. https://arxiv.org/abs/2404.04044

## 7. 미확인 목록과 사유

- ❓ Justin Zobel, “How Reliable Are the Results of Large-Scale Information Retrieval Experiments?,” SIGIR 1998([DOI](https://doi.org/10.1145/290941.291014)): ACM 403과 저자 PDF anti-bot 차단으로 세 차례 원문 접속을 완료하지 못했다. 핵심 근거로 쓰지 않고, pooling 한계는 확인 가능한 NIST 원문으로 대체했다.
- 핵심 표의 34편에는 미확인 문헌이 없다. 일부 ACM/OpenReview landing page가 직접 접속을 막은 경우 저자 공식 원문, 공식 proceedings, DOI 메타데이터를 교차 확인했다.
- 확인된 게재본이 없는 후보 preprint는 확정 근거로 승격하지 않았다. 예: Upadhyay, Kamalloo, Lin, “LLMs Can Patch Up Missing Relevance Judgments in Evaluation,” [arXiv:2405.04727](https://arxiv.org/abs/2405.04727).
