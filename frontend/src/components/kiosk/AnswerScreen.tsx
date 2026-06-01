import { useKioskStore } from "../../store/kioskStore";
import { ActionBar } from "./answer/ActionBar";
import { AnswerPanel } from "./answer/AnswerPanel";
import { ConflictWarning } from "./answer/ConflictWarning";
import { ProcedureSteps } from "./answer/ProcedureSteps";
import { QuestionBar } from "./answer/QuestionBar";
import { SourceList } from "./answer/SourceList";

export function AnswerScreen() {
  const currentQuery = useKioskStore((state) => state.currentQuery);
  const answerData = useKioskStore((state) => state.answerData);
  const resetToMain = useKioskStore((state) => state.resetToMain);
  const isStreaming = answerData?.isStreaming ?? true;

  return (
    <div className="flex h-screen flex-col bg-[#f6f8fc] text-slate-950">
      <QuestionBar onHome={resetToMain} question={currentQuery} />

      <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_26rem] gap-5 overflow-hidden p-6">
        <AnswerPanel
          answer={answerData?.answer ?? ""}
          answerability={answerData?.answerability}
          isStreaming={isStreaming}
          limitations={answerData?.limitations}
          notes={answerData?.notes}
          question={currentQuery}
          summary={answerData?.summary}
          statusMessage={answerData?.statusMessage}
        />
        <div className="answer-side-grid min-h-0 overflow-hidden">
          <ProcedureSteps isStreaming={isStreaming} steps={answerData?.procedureSteps ?? []} />
          <div className="h-full min-h-0">
            <SourceList
              isLoading={isStreaming && (answerData?.sources ?? []).length === 0}
              sources={answerData?.sources ?? []}
            />
            <ConflictWarning warning={answerData?.conflictWarning ?? null} />
          </div>
          <ActionBar
            answer={answerData?.answer ?? ""}
            question={currentQuery}
            sources={answerData?.sources ?? []}
          />
        </div>
      </main>
    </div>
  );
}
