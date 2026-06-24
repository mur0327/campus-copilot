import { ko } from "../../../lang/ko";
import type { ConflictWarning as ConflictWarningType } from "../../../types/kiosk";

interface ConflictWarningProps {
  warning: ConflictWarningType | null;
}

export function ConflictWarning({ warning }: ConflictWarningProps) {
  if (!warning?.exists) return null;

  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-5 text-amber-950">
      <h2 className="font-semibold">{ko.conflict.title}</h2>
      <p className="mt-2 text-sm">{warning.description}</p>
    </section>
  );
}
