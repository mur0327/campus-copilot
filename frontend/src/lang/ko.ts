export const ko = {
  answer: {
    title: "답변",
    partialBadge: "일부 정보 확인됨",
    insufficientBadge: "공식 문서 근거 부족",
    openFullAnswer: "전체 답변 보기",
    enlargeAnswer: "답변을 크게 보기",
    contentLabel: "답변 내용",
    fullAnswerTitle: "전체 답변",
    closeFullAnswer: "전체 답변 닫기",
    preparing: "답변을 준비하고 있습니다.",
    section: {
      procedure: "확인된 절차",
      notes: "준비/주의사항",
      limitations: "확인이 필요한 점",
    },
  },
  chatStatus: {
    retrieving: "공식 문서 검색 중",
    checkingEvidence: "근거 확인 중",
    generating: "답변 작성 중",
    validating: "답변 검증 중",
  },
  chatError: {
    fallback: "답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
  },
  conflict: {
    title: "충돌 경고",
  },
  procedure: {
    eyebrow: "다음 행동",
    title: "진행 절차",
    loading: "절차를 확인하고 있습니다.",
    empty: "확인된 절차가 없습니다.",
  },
  qr: {
    close: "QR 닫기",
    description: "질문과 답변 요약을 확인할 수 있습니다.",
  },
  question: {
    label: "질문",
    home: "처음으로",
  },
  source: {
    title: "답변에 사용된 공식 문서",
    loadingLabel: "출처를 불러오는 중",
    empty: "답변에 사용된 공식 문서가 없습니다",
    recent: "최신",
    stale: "오래됨",
    openOriginal: "원문 열기",
  },
  action: {
    print: "인쇄",
    qr: "QR",
    ttsPending: "읽기 예정",
    printPending: "인쇄 요청 중",
    printFailed: "인쇄 서비스에 연결하지 못했습니다.",
    printSent: "인쇄 요청을 보냈습니다.",
  },
} as const;
