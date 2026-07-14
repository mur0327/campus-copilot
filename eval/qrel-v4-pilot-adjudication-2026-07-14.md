# qrel v4 B2 파일럿 조정 기록

작성일: 2026-07-14. 상태: 저자 최종 결정 완료.

이 문서는 첫 사용성 점검과 공식 재파일럿의 판정 차이, 최종 결정, 본 감사 범위를 기록한다.
초벌과 저자 감사의 판정값은 덮어쓰지 않고, 이 결정은 전체 감사가 끝난 뒤 `qrel-v4-adjudicated.json`에 반영한다.

## 1. 입력과 계보

- 첫 사용성 점검: `qrel-v4-secondary-audit.json`, 10묶음, 페이지 10행, evidence 18행. 시간 측정 누락과 축 설명 부족으로 공식 층화 표본 결과에서는 제외한다.
- 공식 재파일럿: `qrel-v4-secondary-audit-repilot.json`, 파생 시드 `qrel-v4-b2-20260714|repilot-1`, 첫 묶음과 겹치지 않는 10묶음, 페이지 10행, evidence 13행.
- 공식 재파일럿의 10묶음 시간은 모두 기록됐고 중앙값은 17초다.
- 저자가 입력한 판정일 `2027-07-14`는 내보낸 시점 및 실제 작업일과 불일치하는 명백한 메타데이터 오타라 `2026-07-14`로 정정했다. 판정값은 바꾸지 않았다.

## 2. 공식 재파일럿 대조

표적 감사 2묶음에서는 Q033이 전 축에서 일치했고 Q037의 support와 audience 및 evidence가 달랐다.
층화 표본 8묶음에서는 페이지 5묶음과 evidence 5행에 차이가 있었다.
표적 감사와 층화 표본을 합친 일치율이나 κ는 계산하지 않는다.

## 3. 조정 결정

저자가 2026-07-14에 아래 조정안을 최종 확정했다.

| 대상 | 저자 감사 | 최종 결정 | 근거 |
| --- | --- | --- | --- |
| Q007 계절학기 공지 | full/stale/match, evidence full | partial/stale/match, evidence partial text_chunk | 동계 계절학기 일정은 일반 수강신청 기간의 일부만 지지한다. |
| Q015 모집요강 다운로드 | evidence full text_chunk | evidence full page_navigation | 질문 초점이 확인 위치라 페이지 도달 자체가 답이다. |
| Q020 장학 문의 표 | partial/current/match, evidence partial page_navigation | full/current/match, evidence full text_chunk | 본문이 학생지원팀 전화번호를 직접 제시한다. |
| Q022 입시 FAQ | invalid/current/match | invalid/current/mismatch | 수시 지원자용 FAQ는 학생 예비군 신청 대상과 다르다. |
| Q037 드림라이프 FAQ | full/current/match, evidence full text_chunk | invalid/current/mismatch, evidence 없음 | 인터넷 발급 가능 목록에 졸업증명서가 없고 중앙 공식 안내와 충돌한다. |
| Q039 모집요강 다운로드 | partial/current/match, evidence partial page_navigation | invalid/current/match, evidence 없음 | 지원 자격의 실제 claim 없이 다운로드 링크와 목차만 있다. |
| Q048 입사일 확인 청크 `f504038f-1f3a-453c-aac1-b8e5cb6503f8` | evidence 없음 | evidence 없음으로 저자 감사 수용 | 별도 입사일 공지는 입사 신청 방법을 지지하지 않는다. |
| Q049 생활관 위급상황 | invalid/stale/unknown | invalid/current/mismatch | 상시 생활관 안내이며 생활관 입사자 대상이다. |

Q048의 해당 evidence 행은 초벌의 `partial/text_chunk`를 최종 `없음`으로 바꾼다.
나머지 차이는 초벌값을 유지한다.

## 4. 시트 보완

Q037은 충돌 대상인 중앙 공식 안내가 시트에 함께 나오지 않아 저자가 충돌을 확인할 수 없었다.
본 감사에서는 충돌 또는 여러 문서 조합을 이유로 선정된 묶음에 같은 질문의 관련 페이지를 라벨 없는 비교 문맥으로 함께 제시한다.
비교 문맥 페이지에는 판정 컨트롤과 시간이 붙지 않는다.

## 5. 본 감사 범위

비표적 층화 표본은 20묶음으로 동결한다.
최종 선정 범위는 고위험 표적 67묶음과 비표적 층화 표본 20묶음으로 총 87묶음이다.
첫 사용성 점검에서 완료한 표적 5묶음과 공식 재파일럿 10묶음은 다시 판정하지 않으므로, 본 감사 시트의 남은 판정량은 72묶음이다.
중대한 초벌 오류가 같은 사전 정의 유형에서 반복되면 프로토콜의 확대 규칙을 적용한다.
