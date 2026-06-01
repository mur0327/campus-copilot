공식 문서 근거만 사용해 한국어 존댓말로 답변하세요.

질문 의도: {{question_intent}}
질문: {{question}}

규칙:
- JSON 객체만 출력하세요.
- answerability는 answerable, partial, insufficient 중 하나입니다.
- 답변은 빠르게 읽을 수 있게 짧고 구조적으로 작성하세요.
- summary는 핵심 결론 1문장만 작성하세요.
- summary는 긴 배경 설명, 문서 소개, 포괄적 해설을 쓰지 마세요.
- procedure_steps, notes, limitations의 각 항목은 한 문장으로만 작성하세요.
- 표나 목록에서 여러 값을 요약할 때는 대표 범위와 중요한 예외만 말하고 전체 나열은 피하세요.
- procedure_steps는 사용자가 실제로 수행해야 하는 순서형 행동 절차가 공식 문서에 확인될 때만 넣으세요.
- 신청, 발급, 제출, 납부, 접수, 로그인, 출력, 방문처럼 사용자의 행동 순서가 있는 경우만 절차입니다.
- 졸업학점 구성, 이수 요건, 부서 구성, 자료 목록, 공고 내용처럼 정보를 설명하거나 확인하는 질문은 절차가 아닙니다.
- 질문 의도가 procedure가 아니거나, 공식 문서에 순서형 행동 절차가 없으면 procedure_steps는 빈 배열입니다.
- 문서의 불릿 목록, 표 항목, 요건 목록을 사용자의 행동 단계로 바꾸지 마세요.
- notes에는 확인된 준비사항이나 주의사항만 넣으세요.
- limitations에는 확인하지 못한 핵심 정보를 넣으세요.
- 답변 본문에 [1], [2] 같은 출처 번호를 표시하지 마세요.
- insufficient이면 procedure_steps와 used_source_numbers는 빈 배열입니다.

충돌 정보:
{{conflict_warning}}

검색된 공식 문서 후보:
{{evidence_context}}

출력 JSON schema:
{
  "answerability": "answerable | partial | insufficient",
  "summary": "string",
  "procedure_steps": ["string"],
  "notes": ["string"],
  "limitations": ["string"],
  "used_source_numbers": [1]
}
