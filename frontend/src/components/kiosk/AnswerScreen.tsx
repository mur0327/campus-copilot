import { useKioskStore } from "../../store/kioskStore";
import { AnswerPanel } from "./answer/AnswerPanel";
import { AnswerSidebar } from "./answer/AnswerSidebar";
import { QuestionBar } from "./answer/QuestionBar";

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
          procedureSteps={answerData?.procedureSteps}
          question={currentQuery}
          summary={answerData?.summary}
          statusMessage={answerData?.statusMessage}
        />
        <AnswerSidebar
          answer={answerData?.answer ?? ""}
          conflictWarning={answerData?.conflictWarning ?? null}
          isStreaming={isStreaming}
          procedureSteps={answerData?.procedureSteps ?? []}
          question={currentQuery}
          sources={answerData?.sources ?? []}
        />
      </main>
    </div>
  );
}
