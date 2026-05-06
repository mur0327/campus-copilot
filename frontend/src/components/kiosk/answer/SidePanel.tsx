import type { ConflictWarning as ConflictWarningType, Source } from "../../../types/kiosk";
import { ActionBar } from "./ActionBar";
import { ConflictWarning } from "./ConflictWarning";
import { SourceList } from "./SourceList";

interface SidePanelProps {
  question: string;
  answer: string;
  sources: Source[];
  conflictWarning: ConflictWarningType | null;
}

export function SidePanel({ question, answer, sources, conflictWarning }: SidePanelProps) {
  return (
    <aside className="flex min-h-0 flex-col gap-4 overflow-auto">
      <SourceList sources={sources} />
      <ConflictWarning warning={conflictWarning} />
      <ActionBar answer={answer} question={question} sources={sources} />
    </aside>
  );
}
