import type { Source } from "../../../types/kiosk";

interface SourceListProps {
  sources: Source[];
}

function freshnessLabel(source: Source) {
  return source.freshness === "recent" ? "최신" : "오래됨";
}

function freshnessClass(source: Source) {
  return source.freshness === "recent" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700";
}

export function SourceList({ sources }: SourceListProps) {
  return (
    <section className="rounded-lg bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold">출처</h2>
      <div className="mt-4 grid gap-3">
        {sources.length ? (
          sources.map((source) => (
            <a
              className="rounded-md border border-slate-200 p-4 transition-colors hover:border-slate-300"
              href={source.url}
              key={`${source.title}-${source.url}`}
              rel="noreferrer"
              target="_blank"
            >
              <span className="flex items-start justify-between gap-3">
                <strong className="line-clamp-2 min-w-0">{source.title}</strong>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${freshnessClass(source)}`}>
                  {freshnessLabel(source)}
                </span>
              </span>
              <span className="mt-2 block text-sm text-slate-500">{source.crawled_at}</span>
            </a>
          ))
        ) : (
          <p className="rounded-md bg-slate-50 p-4 text-sm text-slate-500">표시할 출처 없음</p>
        )}
      </div>
    </section>
  );
}
