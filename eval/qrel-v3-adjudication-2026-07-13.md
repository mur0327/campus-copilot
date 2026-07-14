# qrel v3 판정 기록 (2026-07-13)

> **정정 (2026-07-14, 외부 리뷰 5·6 반영 — [docs/paper/16](../docs/paper/16-external-review-2026-07-13.md))**
> 본문의 "원시 일치율 70%대 + 낮은 kappa가 answerability 판정이 자명하지 않다는 실증" 해석은 철회한다.
> 18건은 목적표집(무작위가 아니라 insufficient 층만 뽑은 표본)이고 판정자별 지침이 완전히 동일하지 않았으므로, 일치율·κ는 진단적 비교로만 해석한다.
> 저자 JSON은 정합화(amend)된 확정본이라 논의 전 일치율(11/18·12/18)은 이 산출물만으로 재현되지 않으며, 논의 전 값의 근거는 본문 §2의 기록이다.
> 이 문서는 역사 기록으로 보존하며 본문은 수정하지 않는다.
> v3 라벨의 후속 수정은 v4에서만 한다(`qrel-v4-criteria.md`).

판정 기준은 [qrel-v3-criteria.md](qrel-v3-criteria.md)가 정본이다.
이 문서는 판정의 실행 기록이다.
Claude 초벌 → 저자 확정 → 지도교수 블라인드 판정과 비교 → v3 발행 순으로 절을 덧붙인다.

## 1. Claude 초벌 — insufficient 18건 (2026-07-13)

재료: 블라인드 시트와 동일(hybrid top-5 + EXP-06 근거, 청크 전문, retrieval-hybrid-20260712-061045 기준).
이 시점까지 지도교수 판정 값은 미열람이다.
이 초벌의 커밋이 교수 JSON 개봉보다 앞서는 것이 블라인드의 증거다.

| 질문 | ① 근거 | ② 배포 | 이유 | 경계 |
|---|---|---|---|---|
| Q005 등록금 납부 기간 어디서 확인 | full | answer | | ○ |
| Q006 납부확인서 발급 방법 | full | answer | | |
| Q015 편입 모집요강 어디서 확인 | full | answer | | |
| Q016 입학 상담 문의처 | partial | abstain | audience_mismatch | |
| Q021 졸업학점 충족 확인처 | none | abstain | personalized | |
| Q022 예비군 훈련 신청 방법 | none | abstain | absent | |
| Q023 내 학점 확인처 | partial | answer | | ○ |
| Q024 예비군 결석 출석 처리 | none | abstain | absent | ○ |
| Q026 자판기 보충 시점 | none | abstain | absent | |
| Q030 국가근로장학금 신청처 | full | answer | | ○ |
| Q031 등록금 분할 납부 여부 | partial | abstain | audience_mismatch | ○ |
| Q032 등록금 고지서 확인처 | full | answer | | |
| Q039 편입 지원 자격 | partial | abstain | acquisition_failure | |
| Q040 수시 원서 접수 시작일 | full | abstain | stale | |
| Q043 장학 부서 위치 | partial | answer | | ○ |
| Q045 도서관 운영시간 | none | abstain | absent | |
| Q049 예비군 연기 신청 방법 | none | abstain | absent | |
| Q050 축제 일정 | none | abstain | absent | |

집계: ① full 6 / partial 4 / none 8. ② answer 7 / abstain 11.
경계 표시(○) 6건은 초벌 판정자가 스스로 갈릴 만하다고 본 문항이다.

### 문항별 근거

**Q005** ①full ②answer

- 위치 질문(원칙 1). 학기별 납부 안내 공지에 기간과 고지서 조회·출력 경로가 있어 "학기별 납부 안내 공지·HUIS 고지서에서 확인"으로 완전한 답 구성이 가능하다.
- 경계: 공지의 기간 값 자체는 2026-1학기(stale)라, 답이 확인 경로가 아니라 날짜를 그대로 내보내면 위험하다. ②를 abstain(stale)으로 볼 여지가 있다.

**Q006** ①full ②answer

- 증명발급안내(전교 공통 상시)가 교육비납입증명서 발급 절차(HUIS 경로)를 직접 지지한다.
- EXP-06 판정과도 부합.

**Q015** ①full ②answer

- 위치 질문. 모집요강 다운로드 페이지 자체가 답이다.
- 내용 질문이었다면 PDF 미파싱으로 달라진다(원칙 1의 기준 사례).

**Q016** ①partial ②abstain(audience_mismatch)

- 재료의 구체 상담 연락처는 대학원 전용(5955)이다. 학부 입학처는 표제("입학관리처 연락처")만 있고 번호가 재료에 없다.
- 대학원 번호를 일반 질문에 안내하면 대상 오류다.

**Q021** ①none ②abstain(personalized)

- 재료는 졸업학점 요건표로, 질문 초점(내 이수 현황 확인처)과 불일치한다.
- 개인 포털 조회가 필요한 정보다.

**Q022** ①none ②abstain(absent)

- 재료 전부 무관(기숙사 생활, 교과목 등).

**Q023** ①partial ②answer

- 시험/성적 규정의 "성적은 학사DB 등재 후 웹상 조회" 문구가 확인처를 부분 지지한다.
- 경계: 구체 경로(HUIS 메뉴)가 없어 partial 답변의 유용성을 낮게 보면 abstain으로 갈릴 수 있다.

**Q024** ①none ②abstain(absent)

- 예비군 공결 규정이 없다. 인접 규정(군입대 기말고사, 군복무 학점인정)은 질문 초점 불일치.
- 경계: 인접 규정을 "일부"로 볼 여지.

**Q026** ①none ②abstain(absent)

- 자판기 위치는 있으나 보충 일정 정보는 어떤 문서에도 없는 유형(거절 테스트 설계 문항).

**Q030** ①full ②answer

- 신청처(한국장학재단 kosaf.go.kr, 홈페이지·앱)가 학과 공지 여럿에 명시되어 있고, 제도 특성상 상시 유효하다.
- 경계: v2는 "시한부 게시글 불인정" 원칙으로 gold 자체를 안 잡았던 문항이라, 원칙 6의 적용으로 판정이 뒤집히는 대표 사례다.

**Q031** ①partial ②abstain(audience_mismatch)

- 분할납부 신청기간이 대학원 학사일정에만 존재한다. 가상계좌 "분할 입금 불가"는 분납 제도와 다른 개념이다.
- 대학원 일정을 학부 질문에 일반화하면 오답(EXP-06에서 실제 발생한 위험).
- 경계: 학부 기준 정보 부재로 ①을 none으로 볼 여지.

**Q032** ①full ②answer

- HUIS 고지서 조회 경로가 납부 안내와 상시 FAQ에 직접 존재한다. 전교 공통.

**Q039** ①partial ②abstain(acquisition_failure)

- 정본(모집요강 지원자격)은 PDF 미파싱이다.
- 재료의 자격 언급은 2019년 학과 FAQ뿐이라 2026 기준 안내로 부적합(stale 병존).

**Q040** ①full ②abstain(stale)

- 2024·2025년 수시 접수일이 내용상 존재하나 전부 과거 연도다.
- "근거 있음 + 지금 답하면 안 됨" 조합의 기준 사례(원칙 2).
- 이 문서에 개인 휴대전화도 포함되어 공개 적정성 위험이 병존한다.

**Q043** ①partial ②answer

- 부서명(학생지원팀)·연락처(940-5152)는 상시 전화번호부에 있으나 물리적 위치(건물·호실)는 없다.
- 부분 답변(부서·연락처 안내)이 유용하고 무해하다고 봐서 answer.
- 경계: 질문 초점(위치)을 엄격히 보면 abstain.

**Q045** ①none ②abstain(absent)

- 도서관 운영시간이 고정 코퍼스에 없다(library.honam.ac.kr 크롤 범위 밖).
- 외부에 답이 있어도 코퍼스 기준 거절이 맞는 기준 사례.

**Q049** ①none ②abstain(absent)

- 재료 전부 무관.

**Q050** ①none ②abstain(absent)

- 학사일정에 축제 없음, 관련 문서 무관.

재료 밖 노트(라벨 미반영, 원칙 3): 없음.
이번 초벌은 추가 탐색 없이 재료만으로 판정했다.

## 2. 저자 확정 — insufficient 18건 (2026-07-13)

절차: 저자가 초벌 문서를 다시 열지 않은 채 블라인드 시트(HTML)로 직접 기입했다.
단, 직전 대화에서 Claude 초벌의 경계 6건 판정·이유가 노출된 상태였으므로 완전 독립 판정으로 세지 않는다(저자 확정 역할).
기입 결과를 Claude 초벌과 대조해 갈린 8건을 논의했고, 논의에서 판정 원칙 11~13(시효는 문서 성격 / 제목 아닌 본문 / 명칭 등가성)이 추가됐다.

논의 전 일치율(Claude 초벌 vs 저자 기입): ① 11/18, ② 12/18.
저자가 Claude 초벌과 크게 갈린 것은 앵커링이 약했다는 방증으로 기록한다.

확정 판정:

| 질문 | ① 근거 | ② 배포 | 이유 |
|---|---|---|---|
| Q005 | partial | abstain | absent |
| Q006 | partial | abstain | absent, stale |
| Q015 | full | answer | |
| Q016 | full | abstain | audience_mismatch |
| Q021 | none | abstain | personalized |
| Q022 | none | abstain | absent |
| Q023 | partial | abstain | absent |
| Q024 | none | abstain | absent |
| Q026 | none | abstain | absent |
| Q030 | full | answer | |
| Q031 | partial | abstain | audience_mismatch |
| Q032 | full | abstain | stale |
| Q039 | partial | abstain | acquisition_failure |
| Q040 | full | abstain | stale |
| Q043 | none | abstain | absent |
| Q045 | none | abstain | absent |
| Q049 | none | abstain | absent |
| Q050 | none | abstain | absent |

집계: ① full 5 / partial 5 / none 8. ② answer 2 / abstain 16.

갈린 8건의 해소 기록:

- Q005: 저자 판정 채택(Claude 초벌이 경계로 표시했던 방향). 낡은 학기 공지 기반이라 확인 경로 답변도 보수적으로 거절.
- Q006: 저자 판정 채택(원칙 13 신설 계기). 질문의 "납부확인서"와 재료의 "교육비납입증명서"가 재료 안에서 등가로 확인되지 않음. 노트: 코퍼스의 다른 청크에 등가 문장("납부 확인 | 교육비납입증명서 발급 안내")이 존재하나 검색이 가져오지 않아 재료 밖(원칙 3). 검색 실패의 미세 사례로 논문 후보.
- Q016: 저자 판정 채택. ①은 대상 무관하게 내용 존재로 인정(축 분리를 저자가 더 순수하게 적용), 대상 문제는 ②에서 거절.
- Q023: ①은 논의로 일부만 확정(원칙 12, 규정 본문의 "웹상 조회" 한 줄 지지), ②는 저자 판정(거절) 유지.
- Q030: 논의로 답변 확정. 신청처(한국장학재단)는 국가 제도라 학과·학기 무관 상시 사실이라는 Claude 논거를 저자가 수용.
- Q031: 저자 기입과 초벌 일치(partial/abstain), 이유만 audience_mismatch로 구체화.
- Q032: 저자 최종 결정으로 abstain(stale). Claude 이견 병기: 원칙 11·12에 따르면 상시 FAQ 본문이 확인 경로를 지지하므로 answer. 저자는 거절을 유지했고 최종 결정권은 저자에게 있다(원칙 9).
- Q039, Q043: 저자가 재검토로 수정(Q039 일부만·수집 실패, Q043 위치 질문 기준 없음).

이유 구체화 2건(Q021 personalized, Q031 audience_mismatch)은 CSV 분류 정확성을 위한 것으로 저자 동의.
저자 기입 원본은 `eval/qrel-v3-judgment-2026-07-13_저자.json`(수기 수정 이력 포함)이며, 이 표가 확정본이다.

## 3. 지도교수 판정 개봉과 일치율 (2026-07-13)

개봉 시점: §1(Claude 초벌)과 §2(저자 확정)가 커밋된 뒤.
교수 판정 원본은 `eval/qrel-v3-judgment-2026-07-13_지도교수.json`(블라인드 시트로 단독 기입, 18/18 완료).

일치율(§2 저자 확정 vs 교수, 논의 전 동결값):

- ① 근거: 10/18 (55.6%), kappa 0.30
- ② 배포: 13/18 (72.2%), kappa 0.33
- 참고: Claude 초벌 vs 교수는 ② 14/18 (77.8%), kappa 0.53

관찰:

- 판정자별 ② 답변 수: 교수 7 / Claude 초벌 7 / 저자 2. 저자가 가장 엄격했고, 교수와 Claude가 독립적으로 비슷한 관대함을 보였다.
- kappa가 원시 일치율보다 크게 낮은 것은 두 판정자의 거절 비율이 높아 우연 일치 기대치가 크기 때문이다. N=18이라 kappa는 참고 병기(원칙 9).
- 원시 일치율 70%대 + 낮은 kappa 조합 자체가 "answerability 판정은 자명하지 않다"는 논문 주장의 실증이다.

② 배포 불일치 5건의 해소(최종 결정권 저자, 원칙 9):

- Q032 고지서 확인처: **답변으로 수정** (①도 일부만으로 조정, 최종 partial/answer). 3인 중 2인(교수·Claude)이 답변이었고, 교수는 원칙 논거를 모르는 채 재료만으로 같은 결론에 도달 — 상시 FAQ의 존재가 독립 판정자들에게 동일한 신호였다.
- Q006 납부확인서: 거절 유지. 교수는 답변(일부만)이었으나, 명칭 등가성이 제시 재료 안에 없다는 원칙 13을 저자가 유지.
- Q016 입학상담: 거절 유지. 교수는 답변이었으나 재료의 구체 연락처는 대학원 전용 — 대상 오류 위험(원칙 5).
- Q039 편입 자격: 거절 유지. 교수는 있음/답변이었으나 근거가 2019년 학과 FAQ뿐이고 정본(모집요강)은 미수집(원칙 11 취지).
- Q043 장학부서 위치: 거절 유지. 교수는 있음/답변 — 질문 초점(물리적 위치)이 재료에 없다는 저자 판단 유지. 교수도 초점을 부서·연락처로 읽었을 가능성을 논의에 기록.

## 4. v3 질문 수준 확정 — insufficient 18건 (동결)

| 질문 | corpus_support | deployment | reason |
|---|---|---|---|
| Q005 | partial | abstain | absent |
| Q006 | partial | abstain | absent, stale |
| Q015 | full | answer | |
| Q016 | full | abstain | audience_mismatch |
| Q021 | none | abstain | personalized |
| Q022 | none | abstain | absent |
| Q023 | partial | abstain | absent |
| Q024 | none | abstain | absent |
| Q026 | none | abstain | absent |
| Q030 | full | answer | |
| Q031 | partial | abstain | audience_mismatch |
| Q032 | partial | answer | |
| Q039 | partial | abstain | acquisition_failure |
| Q040 | full | abstain | stale |
| Q043 | none | abstain | absent |
| Q045 | none | abstain | absent |
| Q049 | none | abstain | absent |
| Q050 | none | abstain | absent |

집계: ① full 4 / partial 6 / none 8. ② answer 3 / abstain 15.
v2 대비 요지: v2가 "전부 거절 대상"으로 뭉쳤던 18건 중 3건(Q015·Q030·Q032)은 답변이 옳은 문항으로 재분류됐다.
남은 작업: answerable 32건의 질문 수준 판정과 문서 수준 등급, CSV 발행(question_judgments_v3.csv, gold_sources_v3.csv).

## 5. 문서 수준 등급 — answerable gold 전량 (확정)

방법: v2 gold 49행(primary 32 + secondary 17)을 v3 스키마(support_grade / temporal_validity / audience_scope)로 재등급했다.
근거는 v2 판정 노트를 기본으로 하고, 노트만으로 애매한 행은 DB에서 청크 본문을 확인했다(Q003, Q037, Q003 풀 후보 3건).
support_grade는 v2의 primary/secondary 서열이 아니라 내용 기준이다: 질문 초점을 완전히 답하면 full, 일부·조건부면 partial, 답하지 못하면 invalid.
표기: 별표(★)는 기계적 매핑(primary→full, secondary→partial, current, match)과 다르게 판정한 행이다.

| 질문 | 문서 | v2 | v3 등급 | 비고 |
|---|---|---|---|---|
| Q001 | 일반휴학 | primary | full / current / match | |
| Q001 | 입대휴학 | secondary | partial / current / match | 군휴학 한정 |
| Q002 | 복학 | primary | full / current / match | |
| Q003 | 장학제도(enter) | primary | ★ partial / current / mismatch | 신청처(한국장학재단) 미기재, 신입생 장학제도 중심 |
| Q003 | 장학/학자금 5249 (신규) | — | ★ full / current / match | 2026-2학기 국가장학금 신청 안내(전교 공통), 신청처 명시. 3모드 풀 1위 — v2는 시한부 공지 불인정 원칙으로 gold에서 제외했던 문서 |
| Q004 | 장학금 종류 | primary | full / current / match | |
| Q007 | 수강신청 | primary | full / current / match | |
| Q008 | 수강신청 | primary | full / current / match | |
| Q009 | 졸업학점 2025 | primary | full / current / match | |
| Q009 | 졸업학점(진입) | secondary | ★ invalid / current / match | 본문에 학점표 없음(리뷰 4 치명 2의 MRR 부풀림 행) |
| Q009 | 졸업학점 2024 | secondary | partial / current / match | 해당 입학년도 한정 |
| Q009 | 졸업 | secondary | partial / current / match | 130~140 학점 명시 |
| Q010 | 조기졸업 | primary | full / current / match | |
| Q010 | 졸업 | secondary | partial / current / match | 요건 일부 |
| Q011 | 시험/성적 | primary | full / current / match | |
| Q012 | 학사일정 | primary | full / current / match | |
| Q013 | 증명발급안내 | primary | full / current / match | |
| Q013 | 증명발급신청 | secondary | ★ full / current / match | 발급 방법·장소를 직접 답함(내용 기준 상향) |
| Q014 | 증명발급신청 | primary | full / current / match | |
| Q017 | 학사일정 | primary | full / current / match | |
| Q018 | 학사일정 | primary | full / current / match | |
| Q019 | 교내전화번호 | primary | full / current / match | 휴·복학 담당(단과대학 교학팀) 연락처 포함 |
| Q019 | 일반휴학 | secondary | ★ full / current / match | 신청처(단과대학 교학과)를 직접 답함(상향) |
| Q020 | 교내전화번호 | primary | full / current / match | |
| Q025 | 졸업학점 2025 | primary | full / current / match | |
| Q025 | 졸업학점 2024~2021 (4행) | secondary | ★ partial / current / match | 해당 입학년도 한정 |
| Q027 | 입대휴학 | primary | full / current / match | |
| Q027 | 일반휴학 | secondary | partial / current / match | 변경 절차만 |
| Q028 | 일반휴학 | primary | full / current / match | |
| Q029 | 장학금 종류 | primary | full / current / match | |
| Q033 | 수강신청 | primary | full / current / match | |
| Q033 | 학점인정 | secondary | partial / current / match | 기준학점(18/19)+성적우수 +3으로 상한(21/22)을 유추할 수 있으나 "최대" 명시는 아님. 유추가 필요한 지지는 partial(저자 지적으로 상향 철회, 2026-07-13 논의) |
| Q034 | 학사일정 | primary | full / current / match | |
| Q035 | 시험/성적 | primary | full / current / match | Q011과 동일 문항 |
| Q036 | 시험/성적 | primary | full / current / match | |
| Q037 | 증명발급신청 | primary | full / current / match | |
| Q037 | 증명발급안내 | secondary | ★ full / current / match | 졸업증명서 행에 "인터넷증명발급 가능" 명시를 본문 확인(상향, Q033과 달리 초점 직접 답변) |
| Q037 | 드림라이프 FAQ 29 | secondary | ★ partial / current / match | 홈페이지 발급 가능 목록에 졸업증명서 없음(재학·휴학·제적·성적만). 공식 안내와 어긋나는 문서 간 충돌 사례로 노트 |
| Q038 | 증명발급신청 | primary | full / current / match | |
| Q041 | 학사일정 | primary | full / current / match | |
| Q041 | 계절학기 | secondary | partial / current / match | 제도·규정, 구체 일정 없음 |
| Q042 | 학사일정 | primary | full / current / match | |
| Q044 | 교내전화번호 | primary | full / current / match | |
| Q046 | 교내식당/식단 | primary | full / current / match | |
| Q047 | 통학버스 안내 | primary | full / current / match | |
| Q048 | 입사신청/합격조회 | primary | full / current / match | |
| Q048 | 입사안내 | secondary | partial / current / match | 주의사항·제출 서류 중심 |
| Q015 | 모집요강(transPDF) (신규) | — | full / current / match | 위치 질문 기준(§4 재분류 반영) |
| Q030 | 학과공지 beauty 236 (신규) | — | full / current / match | 신청처(kosaf) 명시, 2026-2학기 대상 |
| Q030 | 장학/학자금 5254 (신규) | — | partial / current / match | 제목만 텍스트, 본문 이미지 |
| Q032 | 드림라이프 FAQ 19 (신규) | — | full / current / match | HUIS 고지서 조회 경로(상시 FAQ) |
| Q032 | 학과공지 inc 2369 (신규) | — | ★ full / stale / match | 경로 안내 완전하나 2025-2학기 공지 |

집계(확정, 생성 스크립트로 교차 검증): 총 55행 = v2 재등급 49 + 신규 6(재분류 3문항의 gold 5행 + Q003 보강 1행).
support_grade는 full 39 / partial 15 / invalid 1.
저자 검토에서 조정 1건: Q033 학점인정 상향 철회(유추 지지는 partial — "명시된 지지 = full, 조립이 필요한 지지 = partial" 기준 확립).
질문 수준(answerable 32건)은 전 문항 corpus_support full·deployment answer로 둔다. Q003은 full 근거가 신규 gold(5249)에서 나왔다.

## 6. v3 발행 (2026-07-13)

- `eval/question_judgments_v3.csv` — 질문 수준 판정 50건. support full 36 / partial 6 / none 8, deployment answer 35 / abstain 15.
- `eval/gold_sources_v3.csv` — 문서 수준 등급 55행(위 §5 표와 일치, v2_relevance 열로 계보 보존).
- v2 파일(gold_sources.csv, questions.csv의 answerability 열)은 불변 보존한다. v2의 insufficient 자리표시 18행은 문서가 아니므로 v3 gold 파일로 이관하지 않는다(질문 수준 파일이 대체).
- 이로써 qrel v3 동결. 이후 변경은 v4 발행으로만 한다.
