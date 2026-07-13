# qrel v3 판정 기록 (2026-07-13)

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
