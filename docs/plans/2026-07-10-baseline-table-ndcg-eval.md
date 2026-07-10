# 기준선표(BM25/Vector/Hybrid) + nDCG@k 평가 하네스 확장

작성일: 2026-07-10
배경: KMMS 체크리스트가 요구하는 비교 기준선표와 nDCG@k가 미측정
([docs/paper/05-scope-and-positioning.md](../paper/05-scope-and-positioning.md) §3.2–3.3,
[docs/paper/08-weaknesses-and-mitigations.md](../paper/08-weaknesses-and-mitigations.md) W5).
설계는 문아(Claude), 구현은 Codex 위임.

## 확정된 설계 결정

1. 격리 방식은 "융합만 끈다". 단일 검색기 모드에서도 상세 컨텍스트 확장,
   중복 제거, intent boost 등 후처리는 하이브리드와 동일하게 태운다.
   비교 대상을 검색기 차이로만 한정하기 위함이다.
2. Freshness 행은 기준선표에서 제외한다 (효과 미측정 기능은 "구현했다"까지만
   다루기로 확정, 08 문서 W6).
3. nDCG@k는 binary relevance로 계산한다. 질문당 첫 gold 등장 순위 r 하나만
   보는 단순화(IDCG=1)로, nDCG@5 = 1/log2(1+r) (r ≤ 5), 아니면 0.
4. 세 모드는 같은 코퍼스 스냅숏에서 한 번에(연속으로) 실행해 실행 간 변동
   (Q018 flaky)을 통제한다. 기준선표는 순수 검색이므로 --no-best-bets로 돌린다.
5. 단일 검색기 모드에서는 활성 검색기의 가중치를 1.0으로 둔다 (relevance가
   evidence 게이트와 비교 가능하도록).

## 변경 범위

### backend/app/services/retriever.py

`HybridRetriever.retrieve_with_status()`에 `use_semantic: bool = True`,
`use_bm25: bool = True` 파라미터를 추가한다.

- False인 쪽은 검색 자체를 건너뛰고 빈 결과를 병합에 넘긴다.
- 의도적 비활성화는 장애가 아니다: 해당 쪽 *_available은 True, *_error는 None,
  degraded는 False를 유지한다. mode 문자열은 기존 _retrieval_mode 로직이
  결과 소스 기준으로 정하도록 둔다.
- 기본값이 True/True이므로 API 경로 동작은 변하지 않는다.

### eval/run_questions.py

- `--retriever-mode {hybrid,bm25,semantic}` (기본 hybrid) 추가.
  - bm25: use_semantic=False, bm25_weight=1.0
  - semantic: use_bm25=False, semantic_weight=1.0
  - hybrid: 기존 settings 가중치 그대로
- compute_metrics()에 `ndcg@5` 추가 (위 정의).
- 결과 파일명에 모드 포함: `retrieval-{mode}-{stamp}.*`.
  metrics JSON에 `retriever_mode`, `best_bets` 필드 추가. 콘솔 출력에도 모드 표기.

### backend 테스트

- 단일 모드에서 비활성 검색기가 호출되지 않고 status가 위 규칙대로 나오는지.
- merge_ranked_results에 한쪽 빈 리스트를 넣었을 때 순위가 보존되는지.
- ndcg 계산 단위 테스트 (rank 1 → 1.0, rank 3 → 1/log2(4), miss → 0).

## 검증

- `cd backend && uv run ruff check . && uv run pytest`
- 실제 평가 실행(3모드)은 API 키·로컬 서비스가 필요하므로 구현 완료 후
  문아/관리자가 수행한다. Codex는 eval을 실행하지 않는다.

## 산출물 (구현 후)

- 3모드 실행 결과로 기준선표 작성 → docs/paper/06-experiment-log.md에 EXP-04로
  기록, 사례 수준 분석(어느 질문이 어느 검색기에서만 잡히는지) 포함.
