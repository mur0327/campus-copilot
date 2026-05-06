import type { PopularItem } from "../../../types/kiosk";

interface PopularListProps {
  items: PopularItem[];
  onSelect: (question: string) => void;
}

export function PopularList({ items, onSelect }: PopularListProps) {
  return (
    <main className="flex-1 overflow-auto px-10 py-7">
      <h2 className="text-xl font-semibold">인기 질문</h2>
      <div className="mt-4 grid gap-3">
        {items.map((item) => (
          <button
            className="flex min-h-16 items-center gap-5 rounded-lg border border-slate-200 bg-white px-5 text-left shadow-sm"
            key={`${item.rank}-${item.question}`}
            onClick={() => onSelect(item.question)}
            type="button"
          >
            <span className="w-10 text-center text-xl font-bold text-sky-800">{item.rank}</span>
            <span className="flex-1 text-xl font-medium">{item.question}</span>
            <span className="text-sm text-slate-500">{item.view_count}회</span>
          </button>
        ))}
      </div>
    </main>
  );
}
