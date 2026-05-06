import { Database } from "lucide-react";

import type { AdminStatus } from "../../api/admin";

interface StatusPanelProps {
  status?: AdminStatus;
  isLoading: boolean;
  isError: boolean;
}

function formatCrawledAt(value: string | null | undefined) {
  if (!value) return "아직 수집 기록 없음";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "수집 시각 확인 불가";

  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function StatusPanel({
  status,
  isLoading,
  isError,
}: StatusPanelProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 text-slate-950 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">문서 적재 현황</p>
          <h2 className="mt-1 text-xl font-semibold">수집 상태</h2>
        </div>
        <Database aria-hidden="true" className="h-5 w-5 text-sky-700" />
      </div>

      {isError ? (
        <p className="mt-5 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">
          상태를 불러오지 못했습니다.
        </p>
      ) : (
        <dl className="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm text-slate-500">적재 문서</dt>
            <dd className="mt-1 text-3xl font-semibold tabular-nums">
              {isLoading ? "-" : (status?.documents ?? 0)}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">마지막 수집</dt>
            <dd className="mt-2 text-sm font-medium text-slate-800">
              {isLoading ? "불러오는 중" : formatCrawledAt(status?.last_crawled)}
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}
