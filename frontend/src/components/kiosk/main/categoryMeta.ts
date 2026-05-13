import {
  BookOpenText,
  BriefcaseBusiness,
  Building2,
  CircleHelp,
  CreditCard,
  FileText,
  type LucideIcon,
} from "lucide-react";

interface CategoryMeta {
  Icon: LucideIcon;
  label: string;
  tone: string;
}

const categoryMeta: Record<string, CategoryMeta> = {
  academic: {
    Icon: FileText,
    label: "신청 · 증명 · 수업",
    tone: "bg-sky-50 text-sky-800",
  },
  scholarship: {
    Icon: CreditCard,
    label: "등록금 · 장학",
    tone: "bg-emerald-50 text-emerald-800",
  },
  campus: {
    Icon: Building2,
    label: "시설 · 부서 안내",
    tone: "bg-slate-100 text-slate-700",
  },
  career: {
    Icon: BriefcaseBusiness,
    label: "상담 · 진로",
    tone: "bg-amber-50 text-amber-800",
  },
};

export function getCategoryMeta(categoryId: string | null): CategoryMeta {
  if (categoryId === null) {
    return {
      Icon: BookOpenText,
      label: "전체 안내",
      tone: "bg-sky-800 text-white",
    };
  }

  return (
    categoryMeta[categoryId] ?? {
      Icon: CircleHelp,
      label: "학사 안내",
      tone: "bg-slate-100 text-slate-700",
    }
  );
}
