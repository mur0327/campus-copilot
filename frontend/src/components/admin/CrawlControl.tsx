import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { triggerAdminCrawl } from "../../api/admin";

export default function CrawlControl() {
  const queryClient = useQueryClient();
  const crawlMutation = useMutation({
    mutationFn: triggerAdminCrawl,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-status"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-logs"] });
    },
  });

  const isPending = crawlMutation.isPending;
  const crawlStatus = crawlMutation.data?.status;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 text-slate-950 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">수동 작업</p>
          <h2 className="mt-1 text-xl font-semibold">크롤링 요청</h2>
        </div>
        <button
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
          disabled={isPending}
          onClick={() => crawlMutation.mutate()}
          type="button"
        >
          <RefreshCw
            aria-hidden="true"
            className={`h-4 w-4 ${isPending ? "animate-spin" : ""}`}
          />
          수동 크롤링 요청
        </button>
      </div>

      <div className="mt-5 min-h-6 text-sm">
        {isPending ? <p className="text-slate-600">요청 중</p> : null}
        {crawlStatus === "triggered" ? (
          <p className="font-medium text-emerald-700">
            크롤링 작업이 시작되었습니다. 수집 상태가 자동으로 갱신됩니다.
          </p>
        ) : null}
        {crawlStatus === "already_running" ? (
          <p className="font-medium text-sky-700">이미 크롤링이 진행 중입니다.</p>
        ) : null}
        {crawlMutation.isError ? (
          <p className="rounded-md bg-rose-50 px-3 py-2 text-rose-700">
            크롤링 요청에 실패했습니다.
          </p>
        ) : null}
      </div>
    </section>
  );
}
