관리자님, 원고는 이미 투고 가능한 수준으로 정돈돼 있지만, 아직 “술술 읽히는 산문”까지는 한 차례 더 다듬는 편이 좋아요. 문장이 거칠어서가 아니라, 통제 조건과 판정 용어를 한 문장에 많이 담아 초록·4.1·5.1이 감사 기록처럼 빽빽하게 읽히는 것이 주된 문제예요.

주장·수치·사실관계는 검토하지 않았고, 파일도 수정하지 않았어요.

## 주요 검토 결과

1. **[높음] 결론의 문단 구조가 확정 규칙과 다릅니다.**

   현재 결론은 [요약 문단](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:244)과 [한계·산출물·향후 연구가 합쳐진 문단](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:246)의 2문단이에요. 반면 정본은 `요약 → 보완할 점 → 향후 연구`의 3문단을 명시하고 있어요([19-paper-master.md](/home/mur0327/services/campus-copilot/docs/paper/19-paper-master.md:670)). 3차 피드백도 같은 방향이에요([99-meeting-notes.md](/home/mur0327/services/campus-copilot/docs/paper/99-meeting-notes.md:129)).

   가장 자연스러운 배치는 다음과 같아요.

   - 1문단: 결과 요약 + 산출물 수준 감사 지원
   - 2문단: 단일 기관·목적 선정 문항·pool·단일 저자 감사의 보완점
   - 3문단: 향후 연구

   현재 246행은 네 주제가 한 문단에 들어가 마지막 인상이 급하게 마무리돼요.

2. **[높음] 5.1의 장 안내 문단과 표·그림 위치가 어긋나 있어요.**

   [5장 전체의 안내 문단](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:178)이 `5.1` 아래에 들어가 있어, 5.1이 다른 소절의 역할까지 설명하는 모양이 됐어요. 이 문단은 `5장 제목`과 `5.1 제목` 사이에 두는 것이 구조상 정확해요.

   또한 [Table 4와 Fig. 4를 소개한 문단](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:182) 뒤에 민감도 분석과 고찰 두 문단이 끼고, 실제 [Table 4](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:188)와 [Fig. 4](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:196)가 늦게 나와요. 정본의 “참조 문단 바로 뒤에 표·그림을 둔다”는 규칙과도 맞지 않아요([19-paper-master.md](/home/mur0327/services/campus-copilot/docs/paper/19-paper-master.md:681)).

   `182행 → Table 4 → Fig. 4 → 민감도 분석 → 고찰` 순서가 가장 잘 읽혀요.

3. **[높음] 영문 초록은 낯선 압축 표현이 너무 많아요.**

   [Abstract](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:47)에서 다음 표현들이 설명 없이 한꺼번에 등장해요.

   - `three-level evaluation qrel`
   - `post-reveal adjudication`
   - `restricted-expectation questions`
   - `artifact-level auditing`
   - `operational post-processing`

   특히 세 번째·네 번째 문장은 평가 축과 판정 절차를 각각 한 문장에 모두 담고 있어요. `restricted-expectation questions`는 본문에서 다시 사용하지 않는 즉석 표현이라 가장 낯설어요. `questions expected to receive a qualified answer or abstention`처럼 풀어 쓰는 편이 즉시 이해돼요. `qrel`도 `a three-level relevance-judgment set (qrel)`처럼 첫 등장에 풀어 주는 것이 좋아요.

4. **[중간] 핵심 개념 몇 개가 정의보다 먼저 등장합니다.**

   - [pooled qrel과 pool](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:83): 한국어 설명 없이 처음 등장하고, 실제 구성 설명은 142행까지 미뤄져요. `상위 검색 결과를 합친 판정 후보 집합(pool)`으로 첫 등장에 설명하는 편이 좋아요.
   - [Best Bets](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:101): `큐레이션 고정 결과`도 다소 추상적이에요. `미리 지정한 우선 검색 결과`가 더 바로 이해돼요.
   - [67묶음·20묶음](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:144): 무엇을 한 묶음으로 세는지 알 수 없어요. 뒤에서는 `페이지 쌍`, `근거 쌍`이라는 단위도 나와 단위가 흔들려요. `질문-페이지 판정쌍`, `질문-청크 판정쌍`처럼 단위를 밝혀야 해요.
   - [nDCG](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:180): 약어를 풀지 않은 채 여섯 가지 지표가 동시에 등장해요. 먼저 `@5`의 의미와 PageHit·nDCG·EvidenceHit의 세 지표군을 설명한 뒤 세부 변형을 소개하면 훨씬 수월해요.
   - [결합 근거 축](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:210): 앞에서는 `근거 축`이라고 부르다가 여기서 `결합 근거 축`이 새로 등장해요. 같은 개념이라면 하나로 통일하고, 다른 개념이라면 “내용 지지와 표시 출처를 합친 결합 근거 축”이라고 처음 한 번 정의해야 해요.

5. **[중간] 몇몇 문단은 논문 본문보다 방법 기록처럼 읽혀요.**

   대표적으로 다음 구간이에요.

   - [서론의 연구 개요](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:61): qrel 구성, LLM 판정, 세 검색 구성, 통제 화면, 세 번 실행을 모두 설명해 4장 내용을 미리 반복해요. 서론에서는 연구 범위와 분리 평가의 방향만 남겨도 충분해요.
   - [실험 환경 첫 문단](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:101): `동결`이 한 문단에서 다섯 번 반복되고, Table 1을 보기 전에 Table 2 각주가 먼저 예고돼요. 동결 조건은 한두 문장으로 묶고 Table 2의 전방 참조를 평가 방법으로 옮기면 흐름이 좋아져요.
   - [qrel 라벨 설명](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:124): 모든 enum을 산문으로 나열한 직후 Table 2에서 그대로 반복해요. 산문은 각 수준이 “무엇을 판단하는지”만 설명하고, 영문 라벨은 표에 맡기는 편이 좋아요.
   - [반복 일치도 설명](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:238): 하나의 긴 문장에 변수 정의, 사람 판정과의 구별, 내용 안정성과의 구별, 세 번 실행 조건이 모두 들어가요. 세 문장으로 나누면 의미가 훨씬 선명해져요.

6. **[중간] 표의 내용을 산문에서 다시 읽어 주는 중복이 있어요.**

   [Table 5 소개 문장](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:212)은 네 사례의 내용을 한 문장으로 모두 요약한 뒤 표에서 같은 내용을 다시 보여 줘요. 다음 정도면 충분해요.

   > 서로 다른 평가 축에서 포착된 대표 사례 네 건을 Table 5에 정리하였다. 사례들은 표시 출처, 시점, 대상자와 조건 누락이 서로 다른 실패로 나타남을 보여 준다.

   [5.3 마지막 문단](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:240)도 5.2의 실패 집합과 5.3의 과잉답변 결과를 다시 한 차례 나열해요. 종합 문단 자체는 필요하지만, 앞의 결과를 한 문장으로 압축하고 마지막 해석을 살리는 편이 좋아요.

7. **[중간] 용어와 수 단위의 작은 불일치가 남아 있어요.**

   - [밀집 검색](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:71)과 [Semantic 검색](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:91)이 섞여 있어요. 이론 설명과 시스템 이름을 구분하려는 의도라면 첫 등장에 둘의 관계를 밝히고, 그렇지 않다면 하나로 통일하는 편이 좋아요.
   - `질문 50개의 기대 행동`은 [50문항의 기대 행동](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:144)으로, `질문은 45개·39개·38개`는 [45문항·39문항·38문항](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:180)으로 쓰는 것이 정본 규칙과 맞아요([19-paper-master.md](/home/mur0327/services/campus-copilot/docs/paper/19-paper-master.md:698)).
   - [사유 분포](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:158)의 `필수 주장 부족 8, 수집 실패 5…`도 각 수치에 `문항`을 붙이면 독자가 단위를 추론하지 않아도 돼요.
   - `내용 정확성, 근거 축과 배포 적합성 실패` 같은 병렬 구조는 `내용 정확성·근거·배포 적합성의 실패`로 바꾸면 무엇이 세 항목인지 바로 보여요([4.1](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:120), [결론](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:244)).

8. **[낮음] 몇몇 표현만 더 평이하게 바꾸면 좋아요.**

   - `하위 생성 품질` → `이후 생성 단계의 품질`([서론](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:59))
   - `본 연구의 신규성 주장과 가장 가까운 경계` → `본 연구와 가장 가까운 선행 연구`([관련 연구](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:79))
   - `해시 지문` → `해시값`([실험 환경](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:101))
   - `고정 50문항 사례 연구` → `고정된 50문항을 대상으로 한 사례 연구`([제목](/home/mur0327/services/campus-copilot/docs/paper/21-manuscript.md:18))

## 잘된 부분

- 장과 소절의 단계가 얕고 제목만으로 내용을 알 수 있어요. 교수님의 “책처럼 세분화하지 않는다”는 피드백이 잘 반영돼 있어요.
- 5.1을 제외하면 표·그림을 산문으로 먼저 설명하고 바로 배치하는 흐름이 안정적이에요.
- 구어체나 갑작스러운 수사적 표현은 거의 없고, 논문 전체의 격식과 시제가 일관돼요.
- 5.2의 `분포 → 해당 없음 설명 → 실패 집합 → 대표 사례` 전개와 5.3의 `행동 행렬 → 오류 방향 → 반복 진단 → 함의` 전개는 논리적으로 잘 이어져요.
- `표집`, `병기한다`, 본문의 `키오스크`, 괄호형 표·그림 참조 같은 최근 금지 표현은 남아 있지 않아요.
- 참고 HWP는 구조 준거로만 확인했어요. 현재 원고가 그 샘플보다 용어와 주장 범위는 훨씬 절제돼 있고, 샘플에서 실제로 가져올 만한 것은 명확한 장 제목과 3문단 결론 호흡 정도예요.

전면 재작성은 필요 없어요. **결론 재배치, 5.1 표·그림 이동, 낯선 용어 첫 등장 보완, 과밀 문장 6~8개 분할, 표 중복 서술 축소** 정도의 좁은 산문 수정이면 읽는 속도가 확실히 좋아질 원고예요.
