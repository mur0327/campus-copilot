import type { ConflictWarning as ConflictWarningType, Source } from "../../../types/kiosk";
import { ActionBar } from "./ActionBar";
import { ConflictWarning } from "./ConflictWarning";
import { ProcedureSteps } from "./ProcedureSteps";
import { SourceList } from "./SourceList";

interface AnswerSidebarProps {
  question: string;
  answer: string;
  procedureSteps: string[];
  sources: Source[];
  conflictWarning: ConflictWarningType | null;
  isStreaming?: boolean;
}

export function AnswerSidebar({
  question,
  answer,
  procedureSteps,
  sources,
  conflictWarning,
  isStreaming = false,
}: AnswerSidebarProps) {
  return (
    <aside className="answer-side-grid min-h-0 overflow-hidden">
      <ProcedureSteps isStreaming={isStreaming} steps={procedureSteps} />
      <div className="h-full min-h-0">
        <SourceList isLoading={isStreaming && sources.length === 0} sources={sources} />
        <ConflictWarning warning={conflictWarning} />
      </div>
      <ActionBar answer={answer} question={question} sources={sources} />
    </aside>
  );
}
