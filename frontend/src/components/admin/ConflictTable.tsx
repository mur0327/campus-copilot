import type { AdminConflict } from "../../api/admin";
import { Panel } from "../ui/Panel";

interface ConflictTableProps {
  conflicts?: AdminConflict[];
  isLoading: boolean;
  isError: boolean;
}

function valueOrDash(value: string | boolean | undefined) {
  if (typeof value === "boolean") return value ? "해결됨" : "미해결";

  return value || "-";
}

export default function ConflictTable({
  conflicts,
  isLoading,
  isError,
}: ConflictTableProps) {
  return (
    <Panel bordered padding="md">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500">검수 대상</p>
          <h2 className="mt-1 text-xl font-semibold">충돌 탐지 목록</h2>
        </div>
        <span className="text-sm text-slate-500">{conflicts?.length ?? 0}건</span>
      </div>

      {isError ? (
        <p className="mt-5 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">
          충돌 목록을 불러오지 못했습니다.
        </p>
      ) : null}

      {!isError && isLoading ? (
        <p className="mt-5 text-sm text-slate-500">불러오는 중</p>
      ) : null}

      {!isError && !isLoading && conflicts?.length === 0 ? (
        <p className="mt-5 rounded-md bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
          표시할 충돌 없음
        </p>
      ) : null}

      {!isError && !isLoading && conflicts && conflicts.length > 0 ? (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th className="py-2 pr-4 font-medium">유형</th>
                <th className="py-2 pr-4 font-medium">중요도</th>
                <th className="py-2 pr-4 font-medium">상태</th>
                <th className="py-2 pr-4 font-medium">요약</th>
                <th className="py-2 font-medium">청크</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {conflicts.map((conflict) => (
                <tr key={conflict.id}>
                  <td className="py-3 pr-4">{valueOrDash(conflict.conflict_type)}</td>
                  <td className="py-3 pr-4">{valueOrDash(conflict.severity)}</td>
                  <td className="py-3 pr-4">
                    {valueOrDash(conflict.is_resolved)}
                  </td>
                  <td className="py-3 pr-4">{valueOrDash(conflict.summary)}</td>
                  <td className="py-3 text-slate-500">
                    {valueOrDash(conflict.chunk_a_id)} /{" "}
                    {valueOrDash(conflict.chunk_b_id)}
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
