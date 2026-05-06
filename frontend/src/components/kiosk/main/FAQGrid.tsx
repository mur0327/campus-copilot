import type { FAQItem } from "../../../types/kiosk";

interface FAQGridProps {
  faqs: FAQItem[];
  onSelect: (item: FAQItem) => void;
}

const MAX_FAQ_ITEMS = 6;

export function FAQGrid({ faqs, onSelect }: FAQGridProps) {
  return (
    <main className="grid flex-1 grid-cols-3 grid-rows-2 gap-4 overflow-hidden p-8">
      {faqs.slice(0, MAX_FAQ_ITEMS).map((item) => (
        <button
          className="flex min-h-32 flex-col justify-between rounded-lg border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:border-sky-300 hover:shadow-md"
          key={item.id}
          onClick={() => onSelect(item)}
          type="button"
        >
          <span className="text-sm font-medium text-slate-500">자주 묻는 질문</span>
          <strong className="line-clamp-2 text-2xl font-semibold leading-snug">
            {item.question}
          </strong>
        </button>
      ))}
    </main>
  );
}
