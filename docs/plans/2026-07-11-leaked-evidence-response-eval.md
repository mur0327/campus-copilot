# 게이트 누출 16건 최종 응답 평가 (W3 / EXP-06 예정)

작성일: 2026-07-11
배경: EXP-02에서 evidence 게이트가 정답 없는 질문(insufficient 18개) 중 16개에
엉뚱한 근거를 통과시켰다. 실제 시스템이 그 근거로 위험한 최종 답변을 내는지는
미측정이다([08 W3](../paper/08-weaknesses-and-mitigations.md), 외부 리뷰 2
[09 §3](../paper/09-external-review-2026-07-10.md) 권고). 설계는 Claude,
구현은 Codex 위임, 판정은 2인(Claude 1차, 저자 확정).

## 설계 결정

1. 재검색 없이 EXP-02 당시 evidence context를 재생한다. 기준 실행은
   `eval/results/retrieval-20260705-094816.jsonl`이고, 대상은
   `expected_answerability == "insufficient"`이면서 `evidence_candidates`가
   1개 이상인 16건이다.
2. 평가 대상은 raw LLM JSON이 아니라 출처 검증·downgrade까지 끝난 최종
   ChatResponse다. `generate_answer_draft` → `assemble_chat_response`를
   그대로 사용하고, `filter_evidence_candidates` 재실행은 금지한다
   (게이트를 다시 돌리면 당시 context 재생이 아니게 된다).
3. evidence 본문은 jsonl에 미리보기(240자)만 있으므로 chunk_id로 DB에서
   전체 본문을 조회해 복원한다. 복원한 본문의 content_sig가 저장값과 다르면
   corpus 변경으로 보고 `sig_mismatch` 플래그를 남긴다(제외하지 않고 표기).
4. ConflictWarning은 당시 기록이 없으므로 "없음" 기본값으로 고정하고 그 사실을
   결과에 기록한다.
5. 재현성 필드를 결과에 기록한다: gemini 모델명(settings), 프롬프트 파일
   sha256(`backend/app/prompts/chat_answer.md`), 실행 시각, jsonl 원본 경로.
6. 시스템 answerability 필드와 사람이 읽은 응답 행동을 분리 기록한다
   (시스템이 insufficient라 표시해도 본문이 사실상 답변일 수 있다).

## 판정 축 (사람 판정, 09 §3 그대로)

- 응답 행동: 답변 / 부분 답변·추가 확인 권고 / 명시적 거절
- 근거 관계: 완전 지지 / 일부 지지 / 미지지·모순 / 무관
- 함께 라벨: insufficient 18건 전체의 커버리지 유형
  (public-document absence / acquisition failure / scope-policy exclusion /
  personalized-system information) — 09 §6의 유형화를 이 시트에서 같이 처리.

핵심 수치: 최종 거절 비율(응답 행동 기준), unsupported assertion 포함 비율,
EXP-02의 주제 인접 vs 완전 무관 그룹 간 차이.

## 산출물

- `eval/replay_final_responses.py`: 위 재생 로직. `--limit` 지원(스모크용),
  결과는 `eval/results/final-response-{stamp}.jsonl`과 사람 판정용
  `eval/results/final-response-judgment-{stamp}.md`(질문·근거 요약·응답 전문·
  판정 칸·EXP-02 인접/무관 구분 표시)를 쓴다.
- 실행은 GEMINI_API_KEY·로컬 DB가 필요하므로 저자 터미널에서 수행한다.
- 판정 완료 후 EXP-06으로 기록하고, 거절 용어 교정(올바른 거절률·오답변
  시도율)도 함께 반영한다.
