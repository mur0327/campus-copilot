import { useKioskStore } from "../../store/kioskStore";
import { AnswerPanel } from "./answer/AnswerPanel";
import { QuestionBar } from "./answer/QuestionBar";
import { SidePanel } from "./answer/SidePanel";

export function AnswerScreen() {
  const currentQuery = useKioskStore((state) => state.currentQuery);
  const answerData = useKioskStore((state) => state.answerData);
  const resetToMain = useKioskStore((state) => state.resetToMain);

  return (
    <div className="flex h-screen flex-col bg-[#f6f8fc] text-slate-950">
      <QuestionBar onHome={resetToMain} question={currentQuery} />

      <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,3fr)_minmax(22rem,2fr)] gap-6 p-8">
        <AnswerPanel
          answer={answerData?.answer ?? ""}
          isStreaming={answerData?.isStreaming ?? true}
          procedureSteps={answerData?.procedureSteps ?? []}
        />
        <SidePanel
          answer={answerData?.answer ?? ""}
          conflictWarning={answerData?.conflictWarning ?? null}
          question={currentQuery}
          sources={answerData?.sources ?? []}
        />
      </main>
    </div>
  );
}
