# 문서 재배치·다이어그램·커밋 전략

## 도메인

프로젝트 문서 구조, 설계/계획 문서의 canonical path, 다이어그램 산출물, 커밋 단위 정리 영역입니다. 기능 구현은 아니지만 포트폴리오와 논문 재료를 정돈하는 데 직접 연결됩니다.

## 목표

현재 변경사항을 확인하고 커밋 전략을 정리하는 것이 목표였습니다. 별도의 기능 구현보다, 기존 문서 이동과 신규 RAG 품질 문서를 어떤 단위로 나눠 커밋할지 판단하는 작업이었습니다.

추가로 untracked 상태의 `docs/diagrams/`와 Mermaid 관련 파일을 확인하고, 커밋 가능한 상태인지 점검했습니다.

## 문제 1: 문서 경로가 이동 중이었음

기존 문서 일부는 `docs/superpowers/{specs,plans}` 아래에 있었고, 새 구조는 `docs/{specs,plans}`였습니다.

확인된 변경 성격:

- 2026-04-08, 2026-04-12, 2026-04-19, 2026-05-06 관련 spec/plan 문서 이동
- `docs/specs`와 `docs/plans`를 canonical path로 사용
- 2026-06-01 RAG answer-quality spec/plan 신규 추가

## 비교한 커밋 전략

하나의 큰 docs commit으로 묶을 수도 있었지만, 의미상 두 커밋으로 나누는 전략을 검토했습니다.

1. `docs: relocate project planning documents`
   - 기존 문서 경로 정규화
   - stale link 정리

2. `docs(rag): define answer quality contract`
   - RAG answer-quality spec/plan 신규 추가
   - source display, answerability, JSON output, final-only UX 계약 정리

이 분리는 “문서 위치 변경”과 “새 품질 계약 추가”를 구분하기 위한 선택입니다.

## 문제 2: stale reference

문서 파일을 이동하면 오래된 경로 문자열이 남을 수 있습니다.

확인해야 할 검색:

```bash
rg -n "docs/superpowers/(specs|plans)" .
```

`AGENTS.md`와 이동된 문서 내부에 stale reference가 남아 있을 가능성을 확인했습니다.

## 문제 3: 다이어그램 산출물의 로컬 절대 경로

untracked `docs/diagram` 작업에서는 다음 파일들이 확인됐습니다.

- `docs/diagrams/mermaid.css`
- `docs/diagrams/system-overview.mmd`
- `docs/diagrams/system-overview.svg`
- root `package.json`
- root `package-lock.json`

`system-overview.mmd` 흐름은 다음과 같이 정리됐습니다.

```text
호남대 문서 수집 → 파싱·청킹 → 인덱싱 → 검색·RAG → 키오스크 답변 표시
```

문제는 generated SVG/CSS에 로컬 절대 font path가 들어갈 수 있다는 점이었습니다.

예:

```text
file:///home/mur0327/services/campus-copilot/node_modules/pretendard/...
```

이런 경로는 다른 환경에서 재현성이 낮고, 공개 저장소에 포함할 때 불필요한 local path 노출로 해석될 수 있습니다.

## 선택

다이어그램 파일은 포트폴리오에 유용하지만, 커밋 전에 portability check가 필요하다고 판단했습니다.

확인 기준:

- local absolute path 제거 또는 상대/웹폰트/inline 처리
- generated SVG가 특정 사용자 홈 경로에 의존하지 않는지 확인
- `package.json`/`package-lock.json`이 다이어그램 생성 도구만 위한 것인지, frontend package와 충돌하지 않는지 확인
- untracked-only worktree에서는 `git diff`가 비어 보일 수 있으므로 `git status --short --untracked-files=all`을 사용

## 결과

문서 구조는 `docs/specs`와 `docs/plans`를 중심으로 정리하는 방향이 canonical로 남았습니다. 다이어그램은 시스템 흐름 설명에 유용하지만, 세션 데이터 기준으로는 “커밋 전 점검 필요” 상태로 남았습니다.

## 포트폴리오/논문 포인트

- 구현 결과뿐 아니라 설계 문서와 계획 문서를 분리 관리했습니다.
- RAG answer-quality 문서를 기존 phase 문서와 분리해 품질 계약으로 정리했습니다.
- 시스템 다이어그램은 “수집 → 파싱·청킹 → 인덱싱 → 검색·답변” end-to-end pipeline 설명에 사용할 수 있습니다.

## 관련 자료

- [docs/kiosk/specs](../kiosk/specs/)
- [docs/kiosk/plans](../kiosk/plans/)
- [RAG 답변 품질 지침서](../kiosk/specs/2026-06-01-rag-answer-quality-design.md)
- [RAG 답변 품질 구현 계획](../kiosk/plans/2026-06-01-rag-answer-quality-implementation.md)
- 관련 커밋:
  - `2d95c87 docs: relocate project planning documents`
  - `69066fb docs(rag): define answer quality contract`

## 공란/미확인

- `docs/diagrams/` 산출물이 최종적으로 커밋됐는지는 이 세션 데이터만으로 확정하지 않았습니다.
- 시스템 다이어그램의 최종 스타일, 폰트, 렌더링 도구는 미정입니다.
