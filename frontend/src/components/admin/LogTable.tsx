import type { AdminLog } from "../../api/admin";
import { Panel } from "../ui/Panel";

interface LogTableProps {
  logs?: AdminLog[];
  isLoading: boolean;
  isError: boolean;
}

function formatCreatedAt(value: string | null | undefined) {
  if (!value) return "-";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function valueOrDash(value: string | number | undefined) {
  return value === undefined || value === "" ? "-" : value;
}

export default function LogTable({ logs, isLoading, isError }: LogTableProps) {
  return (
    <Panel bordered padding="md">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">최근 질의</p>
          <h2 className="mt-1 text-xl font-semibold">질문 로그</h2>
        </div>
        <span className="text-sm text-slate-500">{logs?.length ?? 0}건</span>
      </div>

      {isError ? (
        <p className="mt-5 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">
          로그를 불러오지 못했습니다.
        </p>
      ) : null}

      {!isError && isLoading ? (
        <p className="mt-5 text-sm text-slate-500">불러오는 중</p>
      ) : null}

      {!isError && !isLoading && logs?.length === 0 ? (
        <p className="mt-5 rounded-md bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
          표시할 로그 없음
        </p>
      ) : null}

      {!isError && !isLoading && logs && logs.length > 0 ? (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th className="py-2 pr-4 font-medium">질문</th>
                <th className="py-2 pr-4 font-medium">충돌</th>
                <th className="py-2 pr-4 font-medium">응답 시간</th>
                <th className="py-2 font-medium">생성 시각</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.map((log) => (
                <tr key={log.id}>
                  <td className="max-w-[28rem] py-3 pr-4">
                    <p className="truncate">{valueOrDash(log.query)}</p>
                  </td>
                  <td className="py-3 pr-4">
                    {log.has_conflict === undefined
                      ? "-"
                      : log.has_conflict
                        ? "있음"
                        : "없음"}
                  </td>
                  <td className="py-3 pr-4">
                    {log.response_ms === undefined ? "-" : `${log.response_ms}ms`}
                  </td>
                  <td className="py-3 text-slate-500">
                    {formatCreatedAt(log.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Panel>
  );
}
