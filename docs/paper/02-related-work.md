# 관련 연구

> *남들은 이 문제를 어떻게 풀었고, 우리는 어디가 다른가?*

이 문서는 논문의 관련연구 절 초안이다. [05-scope-and-positioning.md](05-scope-and-positioning.md)의
좁힌 스코프(검색 성능·실패 분석·거절)에 맞춰 **5개 축**으로 정리한다.

> ⚠️ **인용 검증 필수**: 아래 서지 정보 상당수는 LLM/웹 검색으로 수집했다. 투고 전
> 각 문헌의 실제 존재·정확한 서지·게재 여부를 원 출처에서 반드시 확인할 것.
>
> **두 축으로 표시한다("실존"과 "저명"은 다른 축):**
> - **위상(신뢰도)**: 📗 정통/저명(최상위 심사 학회·저널) · 📘 심사 통과(주류 학회/워크숍)
>   · 📄 preprint·tech report(미심사) · ❓ 저널 등급 낮음/불명
> - **검증(실존)**: ✓ 이 세션에 링크·실존을 직접 대조함 · ○ 저명·표준 ID라 정본으로
>   추정(미대조) · ✗ 웹검색 요약 출처, 서지·존재 **미확인 — 투고 전 필수 확인**

---

## 1. 하이브리드 검색·순위 융합 (RQ1 배경)

우리 시스템: BM25(키워드) + 벡터(의미)를 **RRF**로 융합. 전부 기존 기법이며
방법론적 새로움은 주장하지 않는다(재발명 회피).

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| RAG 원 개념 | 📗·○ Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP*, NeurIPS 2020. [arXiv](https://arxiv.org/abs/2005.11401) | 시스템 기본 틀 |
| 벡터 검색 | 📗·○ Karpukhin et al., *Dense Passage Retrieval (DPR)*, EMNLP 2020. [arXiv](https://arxiv.org/abs/2004.04906) | 의미 검색 근거 |
| 검색 벤치마크 | 📗·○ Thakur et al., *BEIR*, NeurIPS D&B 2021. [arXiv](https://arxiv.org/abs/2104.08663) | Recall/nDCG 평가 관행 |
| **순위 융합(RRF)** | 📗·✓ Cormack, Clarke & Büttcher, *Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods*, SIGIR 2009. [PDF](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) | **우리 병합의 원 논문. k=60 표준값 출처(튜닝 아님).** SIGIR 정통, 저자 페이지·dvi 메타데이터로 대조 |
| 학습된 sparse | 📗·✗ Formal et al., *SPLADE*, SIGIR 2021. (아래 링크는 논문 아닌 [개념 설명 블로그](https://www.pinecone.io/learn/splade/)) | 용어 확장을 sparse에 내장 — 어휘갭 대안. **원 논문 링크로 교체 필요** |

---

## 2. 어휘 불일치 / 질의·문서 확장 (실패 분석의 핵심)

우리 최대 난제("방학↔계절학기": 사용자 어휘와 문서 어휘 불일치). 문헌은 확장을
**해법**으로 제시하지만, 우리는 **이 특정 갭에서 확장이 실패하는 구조적 이유**를
부정적 결과로 보고한다.

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| 어휘 불일치·쿼리 확장 개관 | 📄·✗ *Query Expansion in the Age of Pre-trained and LLMs: A Survey*, 2025. [arXiv](https://arxiv.org/html/2509.07794v1) | 쿼리 확장 전체 지형 |
| 질의·문서 양방향 확장 | 📄·✗ *TCDE: Topic-Centric Dual Expansion of Queries and Documents*, 2025. [arXiv](https://arxiv.org/html/2512.17164) | 우리가 시도한 쿼리+문서 확장의 최신판 |
| 문서 확장(질의 생성) | 📄·✓ Nogueira & Lin, *From doc2query to docTTTTTquery*, 2019. [PDF](https://cs.uwaterloo.ca/~jimmylin/publications/Nogueira_Lin_2019_docTTTTTquery-v2.pdf) | 우리 LLM 키워드 생성 시도(→롤백)의 원류. **널리 인용되나 심사 학회지 아닌 tech report** |
| 문서 확장(토큰 주입) | 📄·✗ *Doc2Token: Bridging Vocabulary Gap by Predicting Missing Tokens*, 2024. [arXiv](https://arxiv.org/html/2406.19647) | 누락 토큰 주입 — 우리 시도와 직접 대응 |
| 생성 품질 필터 | 📘·✗ *Doc2Query--: When Less is More*, ECIR 2023(추정). [arXiv](https://arxiv.org/pdf/2301.03266) | 환각 확장 걸러내기 — 우리 품질 필터 근거. 게재처 확인 필요 |

**우리 기여(부정적 결과)**: 쿼리 확장은 어휘가 문서에 *있으면* 통했고(전화번호→연락처,
Q020 해결), *없으면*(방학) 엉뚱한 문서(계절학기 전용 페이지)를 밀어올려 실패.
결정적 클래스 라벨 주입도 IDF 파괴·클래스 내 변별 불가로 실패. → 5가지 표준 레버의
구조적 실패 분석.

---

## 3. 미응답 탐지 / 거절 / 선택적 QA (핵심 정렬 — 2025~26 활발)

우리 최신 발견(정답 없는 질문에 거절 실패, 그리고 거절이 검색과 얽힘)이 **가장 뜨거운
최신 연구선과 정확히 맞물린다.**

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| 미응답 평가·유형화 | 📗·✗ *Unanswerability Evaluation for RAG*, ACL 2025. [ACL](https://aclanthology.org/2025.acl-long.415/) | 미응답 6유형 + unanswered/acceptable ratio. **우리 insufficient 라벨링·거절 평가와 같은 문제의식.** ACL이라 위상 높으나 미대조 |
| RAG 미응답 벤치마크 | 📄·✗ *Evaluating RAG on Unanswerable, Uncheatable...*, 2025. [arXiv](https://www.arxiv.org/pdf/2510.11956v1) | 미응답을 1급 평가 차원으로 |
| **evidence 충분성 보정** | ❓·✗ *Evidence-Calibrated RAG for Unanswerable QA (SQuAD 2.0)*, 2025. [저널](https://jtie.stekom.ac.id/index.php/jtie/article/view/536) | **우리가 하려는 거절(근거 점수 문턱)과 거의 동일. ⚠️저널 등급 낮음 — 개념 참조용, 인용 신중** |
| 3-액션(답/거절/보류) | 📄·✗ *PassiveQA: Epistemically Calibrated QA*, 2026. [arXiv](https://arxiv.org/pdf/2604.04565) | 거절을 세분화 |
| 확신도 보정·거부 | 📄·✗ *NOVA: Noise-aware Verbal Confidence Calibration*, 2026. [arXiv](https://arxiv.org/pdf/2601.11004) | confidence 게이팅 |

**핵심 정렬 (우리 실측 ↔ 문헌 이론)**:
> 한 연구는 "**oracle 검색기를 쓰면 올바른 거절이 0.68→0.93으로 상승**"을 보고 —
> 즉 **검색 품질이 거절 성능의 상한을 정한다.** 이는 우리 EXP-03의 발견
> ("검색 실패와 거절 실패가 어휘 갭이라는 한 뿌리로 얽힘")과 정확히 같은 결론이다.
> 또 "confidence 신호 하나로는 불충분"도 우리의 "단일 문턱 분리 천장 0.78"과 일치.
> (⚠️ 이 "0.68→0.93" 수치의 출처 논문을 특정·확인해야 인용 가능.)

**우리 기여**: evidence-충분성 거절은 이미 존재(2025) → **새 방법이 아니라**,
한국 대학 행정이라는 실배포 도메인에서 이를 재현하고 **어휘 갭과의 얽힘을 실측**.

---

## 4. 한국어 형태소·토큰화 (future work 근거)

우리 미해결 미스(방학·교양필수·입사)의 공통 원인은 **복합어 토큰화**
("여름방학"≠"방학"). 정석 해법 문헌.

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| 형태소 분석기(도구) | 📘·○ MeCab-ko / 은전한닢 등 사전 기반 형태소 분석기. | 복합명사 분해 — 우리 갭의 정석 도구. (도구라 인용 형식 확인) |
| 형태소 인지 subword | 📄·✗ *Linguistically Informed Subword Tokenization & Sub-character Decomposition (Korean)*, 2023~. [arXiv](https://ar5iv.labs.arxiv.org/html/2311.03928) | 한국어 교착어·복합어 처리 |
| 서브문자 표현 | 📄·✗ *SCRIPT: Subcharacter Compositional Representation (Korean PLM)*, 2026. [arXiv](https://arxiv.org/html/2604.12377) | 한국어 형태음운 처리 |

**우리 기여**: 형태소 분석 **필요성을 실증 3건**으로 규명(도입은 future work).
국내 학회(KMMS)에 한국어 특화 어필 포인트.

---

## 5. RAG 환각·근거·평가 (배경)

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| 자기검증 RAG | 📗·○ Asai et al., *Self-RAG*, ICLR 2024. [arXiv](https://arxiv.org/abs/2310.11511) | 검색·생성·비평 — 거절의 학습형 접근 |
| 인용 생성 평가 | 📗·○ Gao et al., *ALCE: Enabling LLMs to Generate Text with Citations*, EMNLP 2023. [arXiv](https://arxiv.org/abs/2305.14627) | 출처 표시 평가(우리 future work) |
| RAG 자동 평가 | 📘·○ Es et al., *RAGAS*, EACL 2024(demo). [arXiv](https://arxiv.org/abs/2309.15217) | 답변 충실도 평가(future work) |
| 사실성 평가 | 📗·○ Min et al., *FActScore*, EMNLP 2023. [arXiv](https://arxiv.org/abs/2305.14251) | 환각 측정(future work) |
| 적응형 RAG | 📘·○ Jeong et al., *Adaptive-RAG*, NAACL 2024. [arXiv](https://arxiv.org/abs/2403.14403) | 질문 난이도별 검색 |
| 강 LLM 시대 수확체감 | 📄·✗ *On the Diminishing Returns of Complex Robust RAG Training*, 2025. [arXiv](https://arxiv.org/pdf/2502.11400) | **우리의 "작고 고정된 규칙" 접근을 옹호** |

---

## 6. 스코프 밖으로 미룬 축 (원래 개요 → future work)

원래 개요([01](01-paper-outline.md))의 넓은 주제 중 이번 논문에서 **평가 없이 구현만**
언급하거나 future work로 미루는 것. 관련 문헌은 남겨두되 본문 비중은 최소.

| 주제 | 문헌 (위상·검증) | 처리 |
|---|---|---|
| 최신성 | 📄·○ Vu et al., *FreshLLMs*, 2023. [arXiv](https://arxiv.org/abs/2310.03214) | 구현만, 평가 없음 → future work |
| 문서 충돌 | 📄·✓ Wang, Li, Liu & Shu, *ConflictRAG: Detecting and Resolving Knowledge Conflicts in RAG*, arXiv 2026. [arXiv](https://arxiv.org/abs/2605.17301) | 구현만 → future work. arXiv preprint(미심사), 실존 대조함 |
| 키오스크/공공 UX | — | 본문 최소 |

---

## 7. 종합: 우리 논문의 위치

- **방법 새로움 아님**: 위 문헌들이 방법(하이브리드·RRF·확장·evidence 보정)을 이미 제공.
- **우리 기여 = 응용+경험**: (1) 한국 대학 행정 실배포 시스템, (2) 라벨된 소규모
  학사 QA 평가셋(answerable/insufficient 분리), (3) 표준 기법의 **실패 유형 분석**,
  (4) **거절과 검색이 어휘 갭으로 얽힌다는 실측**(문헌의 oracle-retriever 상한과 정렬).
- **가장 강한 정렬**: 3축(미응답/거절)의 최신 이론이 우리 실측을 뒷받침.
- **가장 정직한 차별**: 방법이 아니라 **도메인 + 부정적 결과 + 얽힘 발견**.

> **투고 전 체크**: 위 표에서 **✗ 표시(미확인)는 전부 원문 대조**해야 한다. 특히
> 3축의 "0.68→0.93" 출처 논문 특정, evidence-calibrated의 저널 신뢰도 판단,
> 2026 arXiv preprint들(PassiveQA·NOVA·SCRIPT·ConflictRAG)의 인용 적절성 재검토.
