import type { Category } from "../../../types/kiosk";

interface CategoryBarProps {
  categories: Category[];
  selectedCategory: string | null;
  onSelect: (categoryId: string | null) => void;
}

export function CategoryBar({ categories, selectedCategory, onSelect }: CategoryBarProps) {
  const buttonClass = (active: boolean) =>
    `min-h-14 rounded-full px-6 text-lg font-semibold transition ${
      active ? "bg-sky-800 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
    }`;

  return (
    <nav className="flex min-h-20 shrink-0 flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-10 py-3">
      <button
        aria-pressed={selectedCategory === null}
        className={buttonClass(selectedCategory === null)}
        onClick={() => onSelect(null)}
        type="button"
      >
        전체
      </button>
      {categories.map((category) => (
        <button
          aria-pressed={selectedCategory === category.id}
          className={buttonClass(selectedCategory === category.id)}
          key={category.id}
          onClick={() => onSelect(category.id)}
          type="button"
        >
          {category.name}
        </button>
      ))}
    </nav>
  );
}
