import { Panel } from "../../ui/Panel";
import { ko } from "../../../lang/ko";
import type { Source } from "../../../types/kiosk";

interface SourceListProps {
  sources: Source[];
  isLoading?: boolean;
}

function freshnessLabel(source: Source) {
  return source.freshness === "recent" ? ko.source.recent : ko.source.stale;
}

function freshnessClass(source: Source) {
  return source.freshness === "recent" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700";
}

function sourceKey(source: Source, index: number) {
  return source.chunk_id ?? `${source.url}-${index}`;
}

function formatSourceTitle(title: string) {
  return title
    .replace(/!\[([^\]]*)]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)]\([^)]+\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/[*_`~]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function SourceList({ sources, isLoading = false }: SourceListProps) {
  return (
    <Panel className="flex h-full min-h-0 flex-col overflow-hidden">
      <h2 className="shrink-0 text-xl font-bold tracking-tight">{ko.source.title}</h2>
      <div className="mt-3 grid min-h-0 gap-3 overflow-auto pr-1">
        {sources.length ? (
          sources.map((source, index) => (
            <article
              className="min-h-20 rounded-md border border-slate-200 p-3 transition-colors hover:border-slate-300"
              key={sourceKey(source, index)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1 text-base font-bold text-slate-950 line-clamp-1" title={source.title}>
                  {formatSourceTitle(source.title)}
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${freshnessClass(source)}`}>
                  {freshnessLabel(source)}
                </span>
              </div>
              <div className="mt-2 flex items-center justify-between gap-3 text-sm text-slate-500">
                <span>{source.crawled_at}</span>
                <a className="shrink-0 font-semibold text-blue-700 underline" href={source.url} rel="noreferrer" target="_blank">
                  {ko.source.openOriginal}
                </a>
              </div>
            </article>
          ))
        ) : isLoading ? (
          <div aria-label={ko.source.loadingLabel} className="grid gap-3" data-testid="source-loading-skeleton">
            {[0, 1, 2].map((item) => (
              <div className="min-h-20 rounded-md border border-slate-100 p-3" key={item}>
                <span className="source-skeleton-line w-2/3" />
                <span className="source-skeleton-line mt-3 w-full" />
                <span className="source-skeleton-line mt-2 w-11/12" />
              </div>
            ))}
          </div>
        ) : (
          <p className="min-h-20 rounded-md bg-slate-50 p-4 text-base text-slate-500">
            {ko.source.empty}
          </p>
        )}
      </div>
    </Panel>
  );
}
