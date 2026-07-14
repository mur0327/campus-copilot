# qrel v4 사람 감사 조정 기록

작성일: 2026-07-14. 상태: 페이지·evidence와 질문 수준 조정 완료, qrel v4 발행 완료.

이 문서는 qrel v4 초벌, B2 사람 감사, 전문 누락 보정 판정을 대조하고 최종 조정 결과를 기록한다.
원본 판정 JSON은 수정하지 않으며, 승인된 결정은 별도의 `qrel-v4-adjudicated.json`에 반영한다.

## 1. 입력과 계보

| 파일 | 역할 | SHA-256 |
| --- | --- | --- |
| `qrel-v4-primary-initial.json` | LLM 초벌 전량 | `8b0703c9b87dc82c21dfcebb63a40633c8f3449cfa164f2dab07bd71117e4576` |
| `qrel-v4-secondary-audit.json` | 첫 사용성 점검 원본 | `8f054b314e4ebe9acb5cb270a6a2ec26854c13e3977811d279a01c654241c67d` |
| `qrel-v4-secondary-audit-repilot.json` | 공식 시간 재파일럿 | `da8eaf7193258809b18c9a17fea4722dbfbdbeda13f1f6132720967383ee8b3a` |
| `qrel-v4-secondary-audit-remaining.json` | 남은 72묶음 감사 | `8bbf2c88c80d255a318ec9515498225677e99b6675bd14db28a4f7f7295bfadb` |
| `qrel-v4-secondary-audit-truncation-reaudit.json` | 전문 누락 4묶음 보정 | `53a51e8c2ad42582c0b7ad7f0d87cb230dc2d5ad496dd904cee8e3945c0cf770` |
| `qrel-v4-question-review.json` | 저자 질문 수준 50문항 전량 검토 | `564ea5cd1576f244fbe945c23b2820e6114c090d9df548d7bc75c7882a7c4d72` |

최종 감사 선정 범위는 표적 67묶음과 층화 표본 20묶음으로 총 87묶음이다.
조립 결과는 페이지 87행과 evidence 161행이며 누락·중복·선정 범위 밖 행이 없다.

## 2. 전문 누락 보정

기존 시트가 청크 본문을 1,500자로 잘라 전체 감사 evidence 166행 중 5행의 뒤쪽 내용을 표시하지 못했다.
영향 범위는 Q016·Q022·Q025·Q048의 4묶음이다.
기존 원본은 그대로 보존하고 전문을 표시한 시트에서 같은 네 묶음을 초기 라벨 비공개 상태로 다시 판정했다.

| 페이지 | 기존 사람 판정 | 전문 보정 판정 |
| --- | --- | --- |
| Q016 입학 FAQ | invalid/current/match | partial/current/match |
| Q022 입학 FAQ | invalid/current/match | invalid/current/unknown |
| Q025 2025 졸업학점표 | partial/stale/match | partial/current/match |
| Q048 입학 FAQ | invalid/current/unknown | partial/current/unknown |

보정 판정은 위 네 묶음의 기존 사람 판정을 대체한다.
시트 생성기는 이후 청크 전문을 표시하도록 수정하고 회귀 검사를 추가한다.

## 3. 원시 대조

표적 감사 67묶음에서는 페이지 중대 차이 43건과 evidence grade 차이 34건이 있었다.
층화 표본 20묶음에서는 페이지 중대 차이 7건과 evidence grade 차이 7건이 있었다.
이 수는 조정 전 원시 차이이며 초벌 오류 건수가 아니다.

주된 원시 차이는 다음 세 가지였다.

- support와 audience를 분리하지 않고 대상이 다른 문서를 invalid로 내린 경우
- 시한부 공지의 지속되는 일부 경로를 근거로 문서 전체를 current로 올린 경우
- 날짜·전화번호·신청처가 본문에 직접 있는데도 `page_navigation`으로 표시한 경우

`page_navigation`은 제목만으로 답을 판정한다는 뜻이 아니다.
검색된 페이지나 링크 목적지에 도달하는 행위 자체가 다운로드·신청·조회 위치 질문의 목적을 완성할 때 사용한다.
본문에 장소·날짜·신청처·절차처럼 답을 구성하는 정보가 직접 적혀 있으면 `text_chunk`를 사용한다.

## 4. 조정 결과

공식 재파일럿에서 이미 승인한 결정은 `qrel-v4-pilot-adjudication-2026-07-14.md`를 따른다.
그중 Q048 입사일 안내 evidence를 `none`으로 내린 결정은 아래 최종 변경에 포함한다.
Q013 증명발급신청과 Q048 입학 FAQ의 최종값은 2026-07-14 저자 확인으로 승인됐다.

| 대상 | 판정 재료 | 초벌 | 사람 감사 | 최종 | 근거 |
| --- | --- | --- | --- | --- | --- |
| Q013 증명발급신청 페이지 | 방문 발급 장소·시간·준비물 | partial/current/match | full/current/match | full/current/match | 공식 증명발급 페이지가 유효한 발급 경로 하나를 완전하게 답하므로 모든 발급 경로를 열거하지 않아도 full이다. |
| Q013 evidence `c9eb2f99-a9cd-4b4f-8dab-78a70598fc82` | `발급장소: 대학본관 1층 교무학사팀` | partial/text_chunk | full/page_navigation | full/text_chunk | 발급 장소가 청크 본문에 직접 있으므로 강도는 full이고 유형은 text_chunk다. |
| Q048 입학 FAQ 페이지 | `기숙사 신청은 매년 1월 중 기숙사 홈페이지에서 신청 가능` | partial/current/match | partial/current/unknown | partial/current/match | 신청처는 맞지만 입사신청 메뉴와 재학생·복학생 경로가 없어 질문의 절차를 일부만 답한다. 입학 대상 기숙사 신청자를 위한 FAQ이므로 audience는 match다. |
| Q048 evidence `2f65264a-211e-4309-9c8c-58c05c44eaf8` | 같은 FAQ 문답 | partial/text_chunk | none | partial/text_chunk | 기숙사 홈페이지라는 신청처를 본문이 직접 제시하므로 근거는 맞다. 구체 메뉴와 학생 유형별 경로가 없어 partial이다. |
| Q048 evidence `f504038f-1f3a-453c-aac1-b8e5cb6503f8` | `생활관 입사일: 별도공지` | partial/text_chunk | none | none | 입사일 확인 안내는 입사 신청 방법을 지지하지 않는다. 공식 재파일럿 조정에서 승인됐다. |

위 표와 §5의 질문 수준 검토에서 확인된 연쇄 변경을 제외한 원시 차이는 초벌값을 유지한다.
전문 보정 뒤 Q016·Q048의 양성 페이지에서 사람이 모든 evidence를 `none`으로 둔 값은 페이지–evidence 정합성에 맞지 않는다.
전문에 각각 입학상담 접근 경로와 기숙사 신청처가 있으므로 해당 evidence는 초벌의 `partial/text_chunk`를 유지한다.

## 5. 질문 수준 전량 검토

페이지·evidence 조정본을 바탕으로 50문항의 expected behavior와 reason을 저자가 전량 확인했다.
초벌 제안 대비 expected behavior 변경은 Q008과 Q036 두 문항이다.
Q003은 신청처의 지속성과 과거 공지의 시효가 갈리는 경계로 표시됐지만 최종 선택은 초벌과 같은 `abstain(stale)`이다.

| 대상 | 초벌 제안 | 저자 확정 | 연쇄 page·evidence 조정 | 근거 |
| --- | --- | --- | --- | --- |
| Q008 수강신청 정정 | full_answer | qualified_answer(acquisition_failure) | `ClassLessonApply` page·evidence full→partial | 정정 조건과 수강신청 절차 준용은 있으나 접속 경로와 실제 조작 절차가 없다. 코퍼스 밖 수강신청 시스템을 확인처로 기록한다. |
| Q036 F 과목 재수강 | full_answer | abstain(acquisition_failure) | `ExamResult` page·evidence full→partial | 재수강 자격·시기·성적 처리는 있으나 실제 신청 경로·조작 절차가 없다. 공식 공지의 상세 매뉴얼 PDF가 미수집됐다. |

최종 expected behavior 분포는 full_answer 28문항, qualified_answer 3문항, abstain 19문항이다.
질문 수준 시트는 초벌 제안을 표시한 저자 확인 절차였으므로 블라인드 독립 판정으로 해석하지 않는다.
원본의 `[재검토]` 메모는 `qrel-v4-question-review.json`에 보존하고 최종 JSON에는 중립적인 조정 근거를 기록했다.

`acquisition_failure`의 목표 출처는 `target_sources_v4.csv`에 분리했다.
Q008 수강신청 시스템, Q024 대학규정, Q036 수강신청 매뉴얼 PDF, Q039 편입 모집요강 PDF, Q045 도서관 이용시간 페이지를 기록했다.

## 6. 확대 여부

페이지·evidence 감사 단계의 층화 표본에서 확인된 중대한 초벌 오류는 Q048 evidence 과대 판정 1건이다.
Q013은 표적 감사의 페이지·evidence 과소 판정 1묶음이다.

후속 질문 수준 전량 검토에서는 절차 질문의 조건·자격 설명을 실제 신청 방법까지 지지하는 것으로 과대 판정한 Q008·Q036 두 건을 확인했다.
이 단계는 50문항 전체와 최종 양성 근거를 이미 노출한 저자 확인이므로 같은 질문 유형의 미검토 문항이 남지 않는다.
두 문항의 page·evidence를 함께 내리고 최종 질문 판정을 반영했으며, 별도의 표본 확대는 수행하지 않는다.

## 7. 최종 발행

`adjudicate_v4_qrel.py`로 초벌 전체에 승인된 page·evidence 변경과 저자 질문 수준 검토를 병합했다.
최종 `qrel-v4-adjudicated.json`의 SHA-256은 `e5320e4b10089f351ccf1ad0f5d01966b5c2726cf6f518bb7ff8e2b75e651f6d`다.

`build_v4_qrel.py`가 다음 발행본을 생성했다.

| 파일 | 행 수 | SHA-256 |
| --- | ---: | --- |
| `gold_pages_v4.csv` | 424 | `0524bc9676098ca513cc21f345d2f7969ea56c792444d1249336b3268c0b9a14` |
| `gold_evidence_v4.csv` | 626 | `8c3a8f3a66282bb1c4466252f3e5bf89a2f160d91c9abad20ab38436c47d3a00` |
| `question_judgments_v4.csv` | 50 | `bd8ae3a57c63307e23706433dbd73b95f46303306422c8fc3ebd20a6405e969a` |
| `target_sources_v4.csv` | 5 | `ae77faa28d0a4a71d4240bdf50b67caadca59f47e97e8fdfea8cfb35d0080aa4` |

발행 직후 invariant 12종을 다시 실행해 페이지 424행, 근거 626행, 질문 50행 전부 통과했다.
