import type { ConflictWarning as ConflictWarningType, Source } from "../../../types/kiosk";
import { ActionBar } from "./ActionBar";
import { ConflictWarning } from "./ConflictWarning";
import { SourceList } from "./SourceList";

interface SidePanelProps {
  question: string;
  answer: string;
  sources: Source[];
  conflictWarning: ConflictWarningType | null;
  isStreaming?: boolean;
}

export function SidePanel({ question, answer, sources, conflictWarning, isStreaming = false }: SidePanelProps) {
  return (
    <aside className="flex min-h-0 flex-col gap-4">
      <SourceList isLoading={isStreaming && sources.length === 0} sources={sources} />
      <ConflictWarning warning={conflictWarning} />
      <ActionBar answer={answer} question={question} sources={sources} />
    </aside>
  );
}
