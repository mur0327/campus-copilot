# 관련 연구

**상태: 예비 조사 기록.**
**작성일 2026-07-12.**

기존 문헌 후보와 당시 판단을 보존하며, 관련 연구와 참고문헌은 원 논문 재조사 뒤 `19-paper-master.md`에서 다시 확정한다. 재조사의 지시서와 조사자별 결과는 [related-work/](related-work/)에 있다.

선행 연구의 접근과 본 연구의 차이를 정리한다. 이 문서는 논문의 관련연구 절 초안이다. [05-scope-and-positioning.md](05-scope-and-positioning.md)의 좁힌 스코프(검색 성능·실패 분석·거절)에 맞춰 5개 축으로 정리한다.

두 축으로 표시한다("실존"과 "저명"은 다른 축).

- 위상(신뢰도): 📗 정통/저명(최상위 심사 학회·저널) · 📘 심사 통과(주류 학회/워크숍) · 📄 preprint·tech report(미심사) · ❓ 저널 등급 낮음/불명
- 검증(실존·제목): ✓ 링크·제목 확인됨(저자 페이지/직접 대조/사용자 확인 2026-07) · ○ 저명·표준 ID라 정본 추정

현재 상태: 링크와 제목은 사용자가 전수 확인함(2026-07). 위상·서지 정리와 인용 여부 결정은 2026-07-12에 완료(§7 투고 전 체크 참조). 남은 것은 집필 시 실제 인용 목록을 이 문서의 "인용 확정" 표시와 대조하는 것뿐이다.

## 1. 하이브리드 검색·순위 융합

RQ1의 배경 문헌을 정리한다.

우리 시스템: BM25(키워드) + 벡터(의미)를 RRF로 융합. 전부 기존 기법이며 방법론적 새로움은 주장하지 않는다(재발명 회피).

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| RAG 원 개념 | 📗·○ Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP*, NeurIPS 2020. [arXiv](https://arxiv.org/abs/2005.11401) | 시스템 기본 틀 |
| 벡터 검색 | 📗·○ Karpukhin et al., *Dense Passage Retrieval (DPR)*, EMNLP 2020. [arXiv](https://arxiv.org/abs/2004.04906) | 의미 검색 근거 |
| 검색 벤치마크 | 📗·○ Thakur et al., *BEIR*, NeurIPS D&B 2021. [arXiv](https://arxiv.org/abs/2104.08663) | Recall/nDCG 평가 관행 |
| 순위 융합(RRF) | 📗·✓ Cormack, Clarke & Büttcher, *Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods*, SIGIR 2009. [PDF](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) | 우리 병합의 원 논문. k=60 표준값 출처(튜닝 아님). SIGIR 정통, 저자 페이지·dvi 메타데이터로 대조 |
| 학습된 sparse | 📗·✓ Formal, Piwowarski & Clinchant, *SPLADE: Sparse Lexical and Expansion Model for First Stage Ranking*, SIGIR 2021 (short). [arXiv](https://arxiv.org/abs/2107.05720) | 용어 확장을 sparse에 내장한 어휘갭 대안. 원 논문 링크로 교체 완료(2026-07-12) |

## 2. 어휘 불일치와 질의·문서 확장

실패 분석의 핵심 배경을 정리한다.

우리 최대 난제("방학↔계절학기": 사용자 어휘와 문서 어휘 불일치). 문헌은 확장을 해법으로 제시하지만, 우리는 이 특정 갭에서 확장이 실패하는 구조적 이유를 부정적 결과로 보고한다.

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| 어휘 불일치·쿼리 확장 개관 | 📄·✓ *Query Expansion in the Age of Pre-trained and LLMs: A Survey*, 2025. [arXiv](https://arxiv.org/abs/2509.07794) | 쿼리 확장 전체 지형 |
| 질의·문서 양방향 확장 | 📄·✓ *TCDE: Topic-Centric Dual Expansion of Queries and Documents*, 2025. [arXiv](https://arxiv.org/abs/2512.17164) | 우리가 시도한 쿼리+문서 확장의 최신판 |
| 문서 확장(질의 생성) | 📄·✓ Nogueira & Lin, *From doc2query to docTTTTTquery*, 2019. [PDF](https://cs.uwaterloo.ca/~jimmylin/publications/Nogueira_Lin_2019_docTTTTTquery-v2.pdf) | 우리 LLM 키워드 생성 시도(→롤백)의 원류. 널리 인용되나 심사 학회지 아닌 tech report |
| 문서 확장(토큰 주입) | 📄·✓ *Doc2Token: Bridging Vocabulary Gap by Predicting Missing Tokens*, 2024. [arXiv](https://arxiv.org/abs/2406.19647) | 누락 토큰 주입으로 우리 시도와 직접 대응 |
| 생성 품질 필터 | 📘·✓ Gospodinov, MacAvaney & Macdonald, *Doc2Query--: When Less is More*, ECIR 2023. [arXiv](https://arxiv.org/abs/2301.03266) · [Springer](https://link.springer.com/chapter/10.1007/978-3-031-28238-6_31) | 환각 확장 걸러내기, 우리 품질 필터 근거. 게재처 확인 완료(2026-07-12) |

우리 기여(부정적 결과): 쿼리 확장은 어휘가 문서에 *있으면* 통했고(전화번호→연락처, Q020 해결), *없으면*(방학) 엉뚱한 문서(계절학기 전용 페이지)를 밀어올려 실패. 결정적 클래스 라벨 주입도 IDF 파괴·클래스 내 변별 불가로 실패. → 5가지 표준 레버의 구조적 실패 분석.

## 3. 미응답 탐지·거절·선택적 QA

2025~2026년에 활발한 핵심 정렬 연구를 정리한다.

우리 최신 발견(정답 없는 질문에 거절 실패, 그리고 거절이 검색과 얽힘)이 가장 뜨거운 최신 연구선과 정확히 맞물린다.

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| 미응답 평가·유형화 | 📗·✓ Peng, Choubey, Xiong & Wu, *UAEval4RAG: Unanswerability Evaluation for RAG*, ACL 2025. [ACL](https://aclanthology.org/2025.acl-long.415/) · [arXiv](https://arxiv.org/abs/2412.12300) | 미응답 6유형 + unanswered/acceptable ratio. 우리 insufficient 라벨링·거절 평가와 같은 문제의식. 원문 대조 완료(2026-07-12)로 인용 확정 |
| 불충분 근거에서의 생성 행동 | 📗·✓ Joren et al., *Sufficient Context: A New Lens on RAG Systems*, ICLR 2025. [arXiv](https://arxiv.org/abs/2411.06037) | 고성능 LLM은 근거가 불충분할 때 거절하는 대신 오답을 낸다. 우리 EXP-06(충실한 오답)과 직접 정렬. 인용 확정(2026-07-12 추가) |
| RAG 미응답 벤치마크 | 📄·✓ *Evaluating RAG on Unanswerable, Uncheatable...*, 2025. [arXiv](https://arxiv.org/abs/2510.11956) | 미응답을 1급 평가 차원으로. 본문 인용은 선택(UAEval4RAG로 충분하면 생략) |
| evidence 충분성 보정 | ❓·✓ *Evidence-Calibrated RAG for Unanswerable QA (SQuAD 2.0)*, 2025. [저널](https://jtie.stekom.ac.id/index.php/jtie/article/view/536) | 거절(근거 점수 문턱) 접근이 우리와 유사하나 저널 등급 낮음. 인용 제외 확정(2026-07-12), 개념은 UAEval4RAG·Sufficient Context로 커버 |
| 3-액션(답/거절/보류) | 📄·✓ *PassiveQA: Epistemically Calibrated QA*, 2026. [arXiv](https://arxiv.org/abs/2604.04565) | 거절을 세분화. 본문 인용 제외(미심사 preprint, 축 대표는 ACL·ICLR로) |
| 확신도 보정·거부 | 📄·✓ *NOVA: Noise-aware Verbal Confidence Calibration*, 2026. [arXiv](https://arxiv.org/abs/2601.11004) | confidence 게이팅. 본문 인용 제외(같은 이유) |

핵심 정렬(우리 실측 ↔ 문헌, 전부 원문 대조 완료):

- UAEval4RAG: 거절은 "요청을 이행하면 안 된다는 진짜 이해"가 아니라 관련 문맥을 못 찾은 데서 오는 경우가 많고, 검색 구성이 거절 성능을 좌우한다(벡터 검색이 answerable 정확도 88.4%인데 unanswerable acceptable ratio는 49.0%인 구성 보고). → 우리 EXP-02·03의 "검색 실패와 거절 실패가 어휘 갭이라는 한 뿌리로 얽힘"과 정렬.
- Sufficient Context(ICLR 2025): 고성능 모델은 근거가 불충분할 때 거절 대신 오답을 내며, 충분성 신호 하나만으로는 거절 결정을 완결하지 못한다. → 우리 EXP-06의 "환각이 아니라 낡거나 대상이 다른 근거의 충실한 오답" 및 EXP-03의 "단일 문턱 분리 천장 0.78"과 정렬.
- 이전 판의 "oracle 검색기로 올바른 거절 0.68→0.93" 인용은 출처를 특정하지 못해 삭제했다(2026-07-12, UAEval4RAG 원문에 해당 수치 없음 확인. [09 §6](09-external-review-2026-07-10.md)의 "출처 미특정 수치 삭제" 결정 이행).

우리 기여: evidence-충분성 거절은 이미 존재(2025)하므로 새 방법이 아니라, 한국 대학 행정이라는 실배포 도메인에서 이를 재현하고 어휘 갭과의 얽힘을 실측한 것이다.

## 4. 한국어 형태소·토큰화

후속 연구의 근거로 검토한 문헌이다.

우리 미해결 미스(방학·교양필수·입사)의 공통 원인은 복합어 토큰화 ("여름방학"≠"방학"). 정석 해법 문헌.

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| 형태소 분석기(도구) | 📘·○ MeCab-ko / 은전한닢 등 사전 기반 형태소 분석기. | 복합명사 분해로 우리 갭의 정석 도구. 인용 형식 확정(2026-07-12): 알고리즘은 Kudo, Yamamoto & Matsumoto, *Applying CRFs to Japanese Morphological Analysis*, EMNLP 2004를 인용하고, mecab-ko-dic(은전한닢)은 각주 URL로 표기 |
| 형태소 인지 subword | 📄·✓ *Linguistically Informed Subword Tokenization & Sub-character Decomposition (Korean)*, 2023~. [arXiv](https://arxiv.org/abs/2311.03928) | 한국어 교착어·복합어 처리. future work 근거로 이 한 편이면 충분 |
| 서브문자 표현 | 📄·✓ *SCRIPT: Subcharacter Compositional Representation (Korean PLM)*, 2026. [arXiv](https://arxiv.org/abs/2604.12377) | 한국어 형태음운 처리. 본문 인용 제외(미심사 preprint, 위 항목으로 충분) |

우리 기여: 형태소 분석 필요성을 실증 3건으로 규명(도입은 future work). 국내 학회(KMMS)에 한국어 특화 어필 포인트.

## 5. RAG 환각·근거·평가

평가 배경 문헌을 정리한다.

| 주제 | 문헌 (위상·검증) | 우리와의 관계 |
|---|---|---|
| 자기검증 RAG | 📗·○ Asai et al., *Self-RAG*, ICLR 2024. [arXiv](https://arxiv.org/abs/2310.11511) | 검색·생성·비평 방식의 거절 학습형 접근 |
| 인용 생성 평가 | 📗·○ Gao et al., *ALCE: Enabling LLMs to Generate Text with Citations*, EMNLP 2023. [arXiv](https://arxiv.org/abs/2305.14627) | 출처 표시 평가(우리 future work) |
| RAG 자동 평가 | 📘·○ Es et al., *RAGAS*, EACL 2024(demo). [arXiv](https://arxiv.org/abs/2309.15217) | 답변 충실도 평가(future work) |
| 사실성 평가 | 📗·○ Min et al., *FActScore*, EMNLP 2023. [arXiv](https://arxiv.org/abs/2305.14251) | 환각 측정(future work) |
| 적응형 RAG | 📘·○ Jeong et al., *Adaptive-RAG*, NAACL 2024. [arXiv](https://arxiv.org/abs/2403.14403) | 질문 난이도별 검색 |
| 강 LLM 시대 수확체감 | 📄·✓ *On the Diminishing Returns of Complex Robust RAG Training*, 2025. [arXiv](https://arxiv.org/abs/2502.11400) | 우리의 "작고 고정된 규칙" 접근을 옹호 |

## 6. 스코프 밖으로 미룬 축

원래 개요에 있었으나 후속 연구로 미룬 주제다.

원래 개요([01](01-paper-outline.md))의 넓은 주제 중 이번 논문에서 평가 없이 구현만 언급하거나 future work로 미루는 것. 관련 문헌은 남겨두되 본문 비중은 최소.

| 주제 | 문헌 (위상·검증) | 처리 |
|---|---|---|
| 최신성 | 📄·○ Vu et al., *FreshLLMs*, 2023. [arXiv](https://arxiv.org/abs/2310.03214) | 구현만, 평가 없음 → future work |
| 문서 충돌 | 📄·✓ Wang, Li, Liu & Shu, *ConflictRAG: Detecting and Resolving Knowledge Conflicts in RAG*, arXiv 2026. [arXiv](https://arxiv.org/abs/2605.17301) | 구현만, future work. arXiv preprint(미심사), 실존 대조함. 본문에서 conflict_scan을 한 문장 이상 다룰 때만 인용 |
| 키오스크/공공 UX | (없음) | 본문 최소 |

## 7. 종합

당시 정리한 논문의 위치는 다음과 같다.

- 방법 새로움 아님: 위 문헌들이 방법(하이브리드·RRF·확장·evidence 보정)을 이미 제공.
- 우리 기여 = 응용+경험: (1) 한국 대학 행정 실배포 시스템, (2) 라벨된 소규모 학사 QA 평가셋(answerable/insufficient 분리), (3) 표준 기법의 실패 유형 분석, (4) 거절과 검색이 어휘 갭으로 얽힌다는 실측(문헌의 oracle-retriever 상한과 정렬).
- 가장 강한 정렬: 3축(미응답/거절)의 최신 이론이 우리 실측을 뒷받침.
- 가장 정직한 차별: 방법이 아니라 도메인 + 부정적 결과 + 얽힘 발견.

투고 전 체크(2026-07-12 전부 해소):

1. ❓ evidence-calibrated 저널 → 인용 제외 확정. 개념은 UAEval4RAG·Sufficient Context(신규 추가, ICLR 2025)로 커버.
2. 📄 2026 preprint → PassiveQA·NOVA·SCRIPT는 본문 인용 제외(축 대표를 심사 통과 문헌으로), ConflictRAG는 conflict_scan을 실제로 다룰 때만 인용.
3. "0.68→0.93" → 출처 특정 실패로 삭제, 검증된 정렬 문장으로 교체(3축 참조).
4. 정본 서지 → Doc2Query--는 ECIR 2023(Springer DOI 확인), SPLADE는 원논문 arXiv 링크로 교체, UAEval4RAG는 저자·원문 대조 완료.
5. MeCab-ko 인용 형식 → Kudo et al., EMNLP 2004 + 도구 각주 URL.

집필 시 남은 일: 실제 참고문헌 목록을 만들 때 이 문서의 "인용 확정/제외" 표시와 대조하고, KMMS 양식의 참고문헌 표기법에 맞춘다.
