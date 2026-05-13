import type { FAQItem } from "../../../types/kiosk";
import { getCategoryMeta } from "./categoryMeta";

interface FAQGridProps {
  faqs: FAQItem[];
  onSelect: (item: FAQItem) => void;
}

const MAX_FAQ_ITEMS = 6;

export function FAQGrid({ faqs, onSelect }: FAQGridProps) {
  return (
    <main className="flex min-h-0 flex-1 flex-col gap-5 overflow-hidden p-8">
      <div className="flex shrink-0 items-end justify-between">
        <div>
          <p className="text-base font-semibold text-sky-800">빠른 안내</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight">많이 찾는 학사 질문</h2>
        </div>
        <p className="text-base text-slate-500">카드를 누르면 답변과 절차를 함께 확인합니다</p>
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-3 grid-rows-2 gap-4">
        {faqs.slice(0, MAX_FAQ_ITEMS).map((item) => {
          const { Icon, label, tone } = getCategoryMeta(item.category_id);

          return (
            <button
              className="group flex min-h-0 flex-col justify-between rounded-lg border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-sky-300 hover:shadow-md active:scale-[0.99]"
              key={item.id}
              onClick={() => onSelect(item)}
              type="button"
            >
              <span className="flex items-start justify-between gap-3">
                <span className={`flex h-12 w-12 items-center justify-center rounded-2xl ${tone}`}>
                  <Icon aria-hidden="true" size={25} strokeWidth={1.8} />
                </span>
                <span className="rounded-full bg-slate-50 px-3 py-1 text-sm font-semibold text-slate-500">
                  자주 묻는 질문
                </span>
              </span>
              <span>
                <span className="mb-3 block text-base font-semibold text-slate-500">{label}</span>
                <strong className="line-clamp-2 text-[1.7rem] font-bold leading-snug tracking-tight">
                  {item.question}
                </strong>
              </span>
            </button>
          );
        })}
      </div>
    </main>
  );
}
