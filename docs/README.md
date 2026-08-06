# Campus Copilot 문서

문서는 다루는 대상에 따라 네 갈래로 나눈다. 서비스 자체는 `kiosk/`, 논문은 `paper/`, 결정이 내려진 맥락은 `sessions/`, 밖으로 낸 보고는 `reports/`에서 관리한다.

## 디렉터리

- [kiosk/](kiosk/): 키오스크 서비스의 설계서(`specs/`), 구현 계획(`plans/`), 런타임 흐름 도식(`diagram/`)이다.
- [paper/](paper/): 논문의 정본, 투고 원고, 외부 리뷰와 투고 자료다. 논문 쪽 작업은 [paper/README.md](paper/README.md)부터 본다.
- [sessions/](sessions/): 설계서나 계획서에 담기 어려운 의사결정 맥락과 운영 판단을 도메인별로 보존한 기록이다.
- [reports/](reports/): 특정 시점의 진행과 성능을 외부에 설명하기 위해 쓴 보고다.

## reports

- [evaluation-report.md](reports/evaluation-report.md): 2026-06-28 기준 검색 성능 1차 보고다.
- [evaluation-report-2.md](reports/evaluation-report-2.md): 2026-07-05 기준 검색 성능 2차 보고다.

두 보고의 수치는 작성 시점 기준이며 논문의 최종 수치와 다르다. 인용할 값은 `paper/19-paper-master.md`에서 확인한다.

## 읽을 때 주의

`kiosk/plans/`의 체크박스는 계획을 세우던 당시 상태로 남아 있어 현재 구현 진행도를 뜻하지 않는다. 해당 작업은 대부분 완료되었으므로 실제 동작은 코드와 `kiosk/specs/`를 기준으로 확인한다.

각 문서는 작성 당시 확인한 사실을 보존한다. 이후 코드가 바뀌었을 수 있으므로 인용하기 전에 링크된 코드와 커밋을 다시 확인한다.
