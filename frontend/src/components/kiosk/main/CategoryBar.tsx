import type { Category } from "../../../types/kiosk";
import { getCategoryMeta } from "./categoryMeta";

interface CategoryBarProps {
  categories: Category[];
  selectedCategory: string | null;
  onSelect: (categoryId: string | null) => void;
}

export function CategoryBar({ categories, selectedCategory, onSelect }: CategoryBarProps) {
  const buttonClass = (active: boolean) =>
    `flex min-h-14 items-center gap-3 rounded-2xl px-5 text-lg font-semibold transition active:scale-[0.98] ${
      active ? "bg-sky-800 text-white shadow-sm" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
    }`;

  const AllIcon = getCategoryMeta(null).Icon;

  return (
    <nav className="flex min-h-[4.75rem] shrink-0 flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-10 py-2.5">
      <button
        aria-pressed={selectedCategory === null}
        className={buttonClass(selectedCategory === null)}
        onClick={() => onSelect(null)}
        type="button"
      >
        <AllIcon aria-hidden="true" size={23} strokeWidth={1.8} />
        전체
      </button>
      {categories.map((category) => {
        const CategoryIcon = getCategoryMeta(category.id).Icon;

        return (
          <button
            aria-pressed={selectedCategory === category.id}
            className={buttonClass(selectedCategory === category.id)}
            key={category.id}
            onClick={() => onSelect(category.id)}
            type="button"
          >
            <CategoryIcon aria-hidden="true" size={23} strokeWidth={1.8} />
            {category.name}
          </button>
        );
      })}
    </nav>
  );
}
