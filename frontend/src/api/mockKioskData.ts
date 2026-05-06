import type { Category, FAQItem, PopularItem } from "../types/kiosk";

export const fallbackCategories: Category[] = [
  { id: "academic", name: "학사행정" },
  { id: "scholarship", name: "장학/등록" },
  { id: "campus", name: "시설/부서" },
  { id: "career", name: "취업/진로" },
];

export const fallbackFAQ: FAQItem[] = [
  { id: "faq-academic-1", question: "휴학 신청은 어디에서 하나요?", category_id: "academic", priority: 1 },
  { id: "faq-academic-2", question: "증명서는 어디에서 발급하나요?", category_id: "academic", priority: 2 },
  { id: "faq-academic-3", question: "수강 정정 기간은 언제 확인하나요?", category_id: "academic", priority: 3 },
  { id: "faq-scholarship-1", question: "등록금 납부 기간은 언제인가요?", category_id: "scholarship", priority: 1 },
  { id: "faq-scholarship-2", question: "장학금 신청 조건은 무엇인가요?", category_id: "scholarship", priority: 2 },
  { id: "faq-campus-1", question: "생활관 문의는 어디로 하나요?", category_id: "campus", priority: 1 },
  { id: "faq-career-1", question: "취업 상담은 어떻게 신청하나요?", category_id: "career", priority: 1 },
];

export const fallbackPopular: PopularItem[] = [
  { rank: 1, question: "휴학 신청 방법은?", view_count: 312 },
  { rank: 2, question: "등록금 납부 기간은?", view_count: 251 },
  { rank: 3, question: "증명서 발급 위치는?", view_count: 198 },
  { rank: 4, question: "장학금 신청 조건은?", view_count: 156 },
  { rank: 5, question: "취업 상담 예약은 어디서 하나요?", view_count: 103 },
];

export function fallbackFAQForCategory(categoryId: string | null): FAQItem[] {
  return fallbackFAQ
    .filter((item) => categoryId === null || item.category_id === categoryId)
    .sort((left, right) => (left.priority ?? 999) - (right.priority ?? 999))
    .slice(0, 6);
}
