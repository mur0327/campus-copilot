# 관련 연구 재조사 결과: Claude 몫 (축 2·3·5·6)

**상태: 조사 완료, 병합 대기.**
**작성일 2026-07-16.**

`docs/paper/related-work/INSTRUCTIONS.md`의 공통 계약을 따르며, 병합 결과는 `docs/paper/19-paper-master.md`에 반영한다.
태그 체계는 02 문서와 같다(📗 정통/저명 · 📘 심사 통과 · 📄 preprint · ❓ 등급 낮음/불명).
각 항목은 arXiv abs 또는 공식 페이지에 실제 접속해 제목·저자·핵심 주장을 대조했고, 접속 실패 항목은 §8 미확인 목록에 분리했다.

## 1. 요약

- 축 2: 5편 확정 후보. page 단위 provenance 평가(KILT)와 "관련성 라벨 히트가 유용 근거를 보장하지 않음"(eRAG)의 선례 확보.
- 축 3: 4편 확정 후보. attribution 개념 정의(AIS)부터 상용 시스템 citation 실측(Liu et al.)까지 축 완성.
- 축 5: 3편 확정 후보. temporal 축 선례는 풍부하나 audience(대상자) 축을 문서 판정에 넣은 학술 선례는 미발견.
- 축 6: 국내 1편과 해외 2편 확정 후보. 같은 도메인(대학 정책 RAG) 최신 사례는 검색 성공률 단일 축 평가에 머묾.
- 신규성 위협: 정면 충돌 없음(§2 상세).

## 2. 신규성 위협

정면 충돌(우리와 같은 분해 평가를 이미 수행) 문헌은 발견하지 못했다. 근접 문헌 세 건과 우리와의 거리는 다음과 같다.

- HoH(2025): outdated 정보가 RAG 답변을 해치는 방식을 벤치마크로 실증. 우리 temporal 축과 문제의식이 같으나, 위키 기반 동적 벤치마크이지 실배포 기관 코퍼스의 qrel 축 분리가 아니다.
- TREC RAG Track(2024·2025): relevance, nugget coverage, attribution을 결합한 다층 평가. "한 점수로 합치지 않기" 철학은 같으나 시간 유효성·대상자·기대 행동 축은 없다.
- Carolina Guide(2026 preprint, USC): 같은 도메인(대학 학사 정책 RAG). 평가는 retrieval success, MRR, safety F1에 그쳐 분해 평가가 없다. 오히려 우리 차별성(같은 도메인에서 축 분리 평가 부재)을 보여주는 대조 사례다.

audience_scope를 문서 판정 축으로 분리한 사례와 기대 행동(완전/제한/거절) 대 실제 행동 대조를 실배포 도메인에서 수행한 사례는 이번 축 범위에서 미발견이다. 후자는 Codex 축 4 결과와 교차 확인이 필요하다.

## 3. 축 2: RAG retrieval·evidence 평가와 page·passage 단위 지표

| 문헌 | 위상 | 확인 | 본 연구와의 관계 | 권고 |
| --- | --- | --- | --- | --- |
| Petroni et al., *KILT: a Benchmark for Knowledge Intensive Language Tasks*, NAACL 2021 | 📗 | [arXiv abs/2009.02252](https://arxiv.org/abs/2009.02252) 2026-07-16 | page-level provenance 평가의 원류. 우리 page qrel(canonical URL 단위 판정)의 직접 선례 | 인용 확정 후보 |
| Salemi & Zamani, *Evaluating Retrieval Quality in Retrieval-Augmented Generation* (eRAG), 2024 | 📘 | [arXiv abs/2404.13781](https://arxiv.org/abs/2404.13781) 2026-07-16 | 쿼리-문서 관련성 라벨과 RAG 성능의 상관이 낮음을 지적. 우리 출발점(URL 히트가 비지지 청크도 정답 처리)과 같은 문제의식이며, 해법은 downstream 자동 평가로 우리(사람 evidence qrel)와 다름 | 인용 확정 후보. SIGIR 2024로 알려짐, 게재처 표기는 집필 전 확인(§8) |
| Es et al., *Ragas: Automated Evaluation of Retrieval Augmented Generation*, 2023 | 📘 | [arXiv abs/2309.15217](https://arxiv.org/abs/2309.15217) 2026-07-16 | reference-free LLM 판정(faithfulness·context 축). 우리와 대비되는 접근이며(우리는 동결 qrel과 사람 감사), RAGAS 계열이 시간 유효성을 못 본다는 점이 우리 배포 축의 공백 논거 | 인용 확정 후보. EACL 2024 demo로 알려짐, 표기 확인(§8) |
| Saad-Falcon et al., *ARES: An Automated Evaluation Framework for RAG Systems*, NAACL 2024 | 📗 | [arXiv abs/2311.09476](https://arxiv.org/abs/2311.09476) 2026-07-16 | 경량 판정자 미세조정에 소량 사람 주석을 결합. LLM 판정과 사람 검증의 결합이라는 점에서 우리 절차의 이웃 | 인용 확정 후보 |
| NIST, *TREC 2025 Retrieval Augmented Generation (RAG) Track* (overview + proceedings) | 📗 | [NIST proceedings](https://pages.nist.gov/trec-browser/trec34/rag/proceedings/) 2026-07-16 | relevance·completeness·attribution을 결합한 다층 평가와 pooled 판정 관행의 현행 표준. 축 7(Codex)과 걸침 | 인용 확정 후보. overview 저자 서지는 미확인(§8) |

종합: 02 문서에는 이 축이 사실상 비어 있었다(BEIR의 Recall/nDCG 관행만 인용). KILT가 page 단위, eRAG가 관련성 라벨의 한계, TREC RAG가 다층 평가 관행을 각각 지지해 우리 3계층 qrel 설계의 배경 절을 구성할 수 있다. RAGAS와 ARES는 자동 평가 대비 우리의 사람 판정과 감사 선택을 정당화하는 대조군으로 쓴다.

## 4. 축 3: groundedness·citation·attribution

| 문헌 | 위상 | 확인 | 본 연구와의 관계 | 권고 |
| --- | --- | --- | --- | --- |
| Rashkin et al., *Measuring Attribution in Natural Language Generation Models* (AIS), 2021~ | 📗 | [arXiv abs/2112.12870](https://arxiv.org/abs/2112.12870) 2026-07-16 | "확인된 출처에 귀속 가능한가"라는 attribution 개념 정의의 원류. 우리 근거 축(내용 지지 + 표시 출처) 판정의 이론적 기반 | 인용 확정 후보. Computational Linguistics 2023 게재로 알려짐, 표기 확인(§8) |
| Gao et al., *Enabling Large Language Models to Generate Text with Citations* (ALCE), EMNLP 2023 | 📗 | [arXiv abs/2305.14627](https://arxiv.org/abs/2305.14627) 2026-07-16 | citation precision/recall 자동 평가 벤치마크. 최고 모델도 완전 인용 지지가 50% 부족하다는 결과는 우리 EXP-07 근거 축 실패 6문항과 대조 서술 가능 | 인용 확정 후보 |
| Liu, Zhang & Liang, *Evaluating Verifiability in Generative Search Engines*, Findings of EMNLP 2023 | 📘 | [arXiv abs/2304.09848](https://arxiv.org/abs/2304.09848) 2026-07-16 | 상용 4개 시스템 실측(citation recall 51.5%, precision 74.5%). 실배포 시스템의 출처 신뢰 문제를 실증해 우리 응용 사례 프레이밍과 정렬 | 인용 확정 후보 |
| Bohnet et al., *Attributed Question Answering: Evaluation and Modeling for Attributed LLMs*, 2022~23 | 📄 | [arXiv abs/2212.08037](https://arxiv.org/abs/2212.08037) 2026-07-16 | attributed QA 평가 프레임워크(사람 주석 금표준 + 자동 지표 보조). 우리 판정 절차와 구조 유사 | 보류. preprint이며 AIS·ALCE로 축 대표가 되면 제외 가능 |

종합: attribution 개념(AIS), 자동 평가(ALCE), 실배포 실측(Liu et al.)의 3단 구성이면 관련 연구 절에서 이 축은 충분하다. 우리 고유 기여는 citation 지지 여부가 아니라 "지지되는 출처라도 stale·mismatch면 배포 부적합"이라는 다음 층을 얹은 것으로 서술한다.

## 5. 축 5: 시간·대상자 등 배포 맥락 분리 평가

| 문헌 | 위상 | 확인 | 본 연구와의 관계 | 권고 |
| --- | --- | --- | --- | --- |
| Zhang & Choi, *SituatedQA: Incorporating Extra-Linguistic Contexts into QA*, EMNLP 2021 | 📗 | [arXiv abs/2109.06157](https://arxiv.org/abs/2109.06157) 2026-07-16 | 시간·지리 맥락에 따라 답이 달라지는 QA(NQ-Open의 16.5%). "같은 질문, 맥락 따라 다른 답"의 원류로 우리 temporal·audience 축의 가장 가까운 학술 선례. 단 질문 맥락 축이지 문서 판정 축은 아님 | 인용 확정 후보 |
| Vu et al., *FreshLLMs: Refreshing Large Language Models with Search Engine Augmentation* (FreshQA), 2023 | 📄 | [arXiv abs/2310.03214](https://arxiv.org/abs/2310.03214) 2026-07-16 | 빠르게 변하는 지식과 거짓 전제 질문의 사실성 평가(사람 평가 5만 건 이상). temporal 축 평가 관행의 대표 | 인용 확정 후보. ACL 2024 Findings 게재로 알려짐, 표기 확인(§8) |
| Ouyang et al., *HoH: A Dynamic Benchmark for Evaluating the Impact of Outdated Information on RAG*, 2025 | 📄 | [arXiv abs/2503.04800](https://arxiv.org/abs/2503.04800) 2026-07-16 | 낡은 정보가 주의 분산으로 정확도를 낮추고 현재 정보가 있어도 오답을 유도함을 실증. 우리 stale 축과 EXP-06/07의 "낡은 근거의 충실한 오답"을 직접 지지 | 인용 확정 후보. 게재처 확인 필요(§8) |

종합: temporal 축은 SituatedQA(맥락 의존), FreshQA(사실성), HoH(RAG에서의 해악 실증)로 계보가 탄탄하다. 반면 audience(문서의 대상 집단) 축을 관련성 판정에 분리해 넣은 학술 문헌은 이번 조사에서 찾지 못했다(산업 블로그의 "context trustworthiness" 논의 수준만 존재). 관련 연구 절에서 temporal은 선행에 접속하고, audience는 본 도메인의 요구(학과 미러·회차 공지·집단별 안내)에서 도출한 신설 축으로 서술하는 것이 정직하고 방어 가능하다.

## 6. 축 6: 기관·대학 행정 문서 RAG 응용

| 문헌 | 위상 | 확인 | 본 연구와의 관계 | 권고 |
| --- | --- | --- | --- | --- |
| 이재승·이종민·유제혁, 검색 증강 생성 기반 거대언어모델을 이용한 대학 학습관리시스템 학생 질의응답 챗봇, 방송공학회논문지 29(5), 2024 | 📘 | [KCI](https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART003121104) · [학회 PDF](https://www.kibme.org/resources/journal/20241002112934469.pdf) 2026-07-16 | 국내 대학 도메인 RAG 챗봇 선행 사례(LMS 질의응답). KMMS 투고에 국내 계보 인용으로 유용 | 인용 확정 후보. 원문 PDF 대조는 집필 시 |
| Trienes et al., *Marcel: A Lightweight and Open-Source Conversational Agent for University Student Support*, EMNLP 2025 System Demonstrations | 📘 | [arXiv abs/2507.13937](https://arxiv.org/abs/2507.13937) 2026-07-16 | 대학 학생 지원 RAG(FAQ 검색기, 하이브리드 대비 평가, 운영 인사이트 보고). 해외 동종 사례의 대표 | 인용 확정 후보 |
| Torsion & Zhou, *Carolina Guide: A Multi-Agent RAG System with Institutional Guardrails for Academic Policy Assistance*, 2026 | 📄 | [arXiv abs/2606.28360](https://arxiv.org/abs/2606.28360) 2026-07-16 | 같은 도메인(대학 학사 정책)의 최신 사례. 평가는 retrieval success 98.9%, MRR 0.989, safety F1뿐이라 축 분리 평가 부재의 대조 사례 | 후보. 미심사 preprint라 본문 인용은 대조 목적 한정 |
| Li & Iwata, *A Locally Deployed RAG-Based Academic Advising System for Course Selection*, KES 2026 (Procedia CS) | ❓ | [arXiv abs/2606.02983](https://arxiv.org/abs/2606.02983) 2026-07-16 | 수강 지도 RAG 로컬 배포 사례. 평가 방법이 초록에 없음 | 보류. 사례 존재 근거로만 |

종합: 대학 행정 RAG 응용은 2024~2026에 사례가 빠르게 늘고 있으나, 확인한 범위에서 평가는 검색 성공률·사용성·안전성 단일 축에 머문다. "응용 사례는 많지만 분해 평가는 없다"가 이 축의 관련 연구 결론이며 우리 기여 2(분리 평가 절차)의 위치를 정해준다.

## 7. 타 축 후보 (Codex 몫으로 이관)

- 축 4: Chen et al., *RGB: Benchmarking Large Language Models in Retrieval-Augmented Generation*, AAAI 2024. negative rejection 능력 포함. https://arxiv.org/abs/2309.01431
- 축 7: *The Great Nugget Recall: Automating Fact Extraction and RAG Evaluation with LLMs*, 2025. TREC 계열 LLM 자동 판정. https://arxiv.org/abs/2504.15068
- 축 7: GroUSE(COLING 2025). grounded QA 평가자의 메타 평가. https://aclanthology.org/2025.coling-main.304.pdf

## 8. 미확인 목록

- ARGObot(ACM Southeast Conference 2025, DOI 10.1145/3696673.3723065): ACM DL 403으로 원문 접근 실패. 제목과 DOI 존재는 검색 결과로만 확인했으므로 인용하려면 다른 경로가 필요하다.
- AttributionBench(arXiv 2402.15089): 미접속. 축 3은 확정 후보 4편으로 충분해 추가 조사를 생략했다.
- TREC 2025 RAG overview 논문의 저자·서지: NIST 목차 페이지에서 제목만 확인했다.
- 게재처 표기 미확정 5건(eRAG는 SIGIR 2024, RAGAS는 EACL 2024 demo, FreshLLMs는 ACL 2024 Findings, AIS는 Computational Linguistics 2023, HoH는 불명): arXiv 페이지에 학회 표기가 없어 집필 시 학회 프로그램 페이지와 대조가 필요하다.
- Antico et al. 2024(Milano-Bicocca 사례): 검색 요약에만 등장, 원문 미확인.

## 9. 추가 조사 아이디어 (실행 안 함)

- TimeQA, RealTime QA 등 temporal QA 벤치마크 계열 보강(SituatedQA·FreshQA로 충분하면 불요)
- 축 6 국내 사례 KCI 심층 검색(학사 규정 특화 사례 존재 여부)
- TREC 2024 RAG overview(Pradeep et al.)의 정확한 서지 확정
