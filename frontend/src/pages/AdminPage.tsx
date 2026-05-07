import { useQuery } from "@tanstack/react-query";

import {
  fetchAdminConflicts,
  fetchAdminLogs,
  fetchAdminStatus,
} from "../api/admin";
import ConflictTable from "../components/admin/ConflictTable";
import CrawlControl from "../components/admin/CrawlControl";
import LogTable from "../components/admin/LogTable";
import StatusPanel from "../components/admin/StatusPanel";

export default function AdminPage() {
  const statusQuery = useQuery({
    queryKey: ["admin-status"],
    queryFn: fetchAdminStatus,
    refetchInterval: 3_000,
  });
  const conflictsQuery = useQuery({
    queryKey: ["admin-conflicts"],
    queryFn: fetchAdminConflicts,
  });
  const logsQuery = useQuery({
    queryKey: ["admin-logs"],
    queryFn: fetchAdminLogs,
  });

  return (
    <main className="min-h-screen bg-slate-100 px-5 py-6 text-slate-950 sm:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="flex flex-col gap-2 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Campus Copilot</p>
            <h1 className="mt-1 text-2xl font-semibold">운영자 화면</h1>
          </div>
          <p className="text-sm text-slate-500">관리자 API 기준 상태 모니터링</p>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <StatusPanel
            isError={statusQuery.isError}
            isLoading={statusQuery.isLoading}
            status={statusQuery.data}
          />
          <CrawlControl />
        </div>

        <ConflictTable
          conflicts={conflictsQuery.data}
          isError={conflictsQuery.isError}
          isLoading={conflictsQuery.isLoading}
        />

        <LogTable
          isError={logsQuery.isError}
          isLoading={logsQuery.isLoading}
          logs={logsQuery.data}
        />
      </div>
    </main>
  );
}
