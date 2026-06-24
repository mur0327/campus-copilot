import { Database, Loader2 } from "lucide-react";

import type { AdminStatus } from "../../api/admin";
import { Panel } from "../ui/Panel";

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

function crawlStatusLabel(status: string | undefined) {
  switch (status) {
    case "running":
      return "크롤링 진행 중";
    case "completed":
      return "크롤링 완료";
    case "failed":
      return "크롤링 실패";
    default:
      return "크롤링 기록 없음";
  }
}

function progressPercent(processed: number, total: number) {
  if (total <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((processed / total) * 100)));
}

function timestamp(value: string | null | undefined) {
  if (!value) return null;

  const time = new Date(value).getTime();
  return Number.isNaN(time) ? null : time;
}

function formatCrawlError(error: string) {
  const lines = error.split("\n").filter(Boolean);
  const entries = lines.reduce<string[]>((acc, line) => {
    if (/^(https?:\/\/|indexing:)/.test(line) || acc.length === 0) {
      acc.push(line);
      return acc;
    }

    acc[acc.length - 1] = `${acc[acc.length - 1]}\n${line}`;
    return acc;
  }, []);

  if (entries.length <= 5) return error;

  return `${entries
    .slice(0, 5)
    .map((entry) => entry.split("\n")[0])
    .join("\n")}\n외 ${entries.length - 5}건의 오류가 더 있습니다.`;
}

export default function StatusPanel({
  status,
  isLoading,
  isError,
}: StatusPanelProps) {
  const latestJob = status?.latest_crawl_job;
  const workerStatus = status?.worker_crawl_status;
  const workerStartedAt = timestamp(workerStatus?.started_at);
  const latestJobStartedAt = timestamp(latestJob?.started_at);
  const workerIsNewer =
    workerStartedAt !== null &&
    (latestJobStartedAt === null || workerStartedAt > latestJobStartedAt);
  const useWorkerStatus =
    workerStatus?.status === "running" &&
    (!latestJob || latestJob.status !== "running" || latestJob.total_pages <= 0 || workerIsNewer);
  const effectiveStatus =
    useWorkerStatus ? workerStatus.status : latestJob?.status;
  const effectiveStage =
    (useWorkerStatus ? workerStatus.current_stage : latestJob?.current_stage) ?? null;
  const effectiveError = (useWorkerStatus ? workerStatus.error : latestJob?.error) ?? null;
  const isRunning = effectiveStatus === "running";
  const processedPages = useWorkerStatus
    ? workerStatus.processed_pages
    : (latestJob?.processed_pages ?? 0);
  const totalPages = useWorkerStatus ? workerStatus.total_pages : (latestJob?.total_pages ?? 0);
  const percent = progressPercent(processedPages, totalPages);

  return (
    <Panel bordered padding="md">
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
          <div>
            <dt className="text-sm text-slate-500">현재 크롤링</dt>
            <dd className="mt-2 flex items-center gap-2 text-sm font-semibold text-slate-800">
              {isRunning ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin text-sky-700" /> : null}
              <span>{isLoading ? "불러오는 중" : crawlStatusLabel(effectiveStatus)}</span>
            </dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">처리량</dt>
            <dd className="mt-2 text-sm font-medium text-slate-800">
              {isLoading
                ? "불러오는 중"
                : `${latestJob?.pages_crawled ?? 0}건 수집 · ${latestJob?.pages_changed ?? 0}건 변경 · ${latestJob?.conflicts_found ?? 0}건 충돌`}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-sm text-slate-500">진행 단계</dt>
            <dd className="mt-2 text-sm font-medium text-slate-800">
              {isLoading ? "불러오는 중" : (effectiveStage ?? "대기 중")}
            </dd>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                aria-label="크롤링 진행률"
                aria-valuemax={100}
                aria-valuemin={0}
                aria-valuenow={percent}
                className="h-full rounded-full bg-sky-700 transition-all"
                role="progressbar"
                style={{ width: `${percent}%` }}
              />
            </div>
            <p className="mt-2 text-xs font-medium text-slate-500">
              {totalPages > 0 ? `${processedPages}/${totalPages} 페이지 · ${percent}%` : "대상 수 확인 중"}
            </p>
          </div>
        </dl>
      )}
      {!isError && effectiveError ? (
        <p className="mt-4 whitespace-pre-line rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {formatCrawlError(effectiveError)}
        </p>
      ) : null}
    </Panel>
  );
}
