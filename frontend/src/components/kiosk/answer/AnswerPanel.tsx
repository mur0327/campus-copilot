import { AnswerText } from "./AnswerText";
import { ProcedureSteps } from "./ProcedureSteps";

interface AnswerPanelProps {
  answer: string;
  procedureSteps: string[];
  isStreaming: boolean;
}

export function AnswerPanel({ answer, procedureSteps, isStreaming }: AnswerPanelProps) {
  return (
    <section className="min-h-0 overflow-auto rounded-lg bg-white p-7 shadow-sm">
      <h2 className="text-xl font-semibold">답변</h2>
      <AnswerText isStreaming={isStreaming} text={answer} />
      <ProcedureSteps steps={procedureSteps} />
    </section>
  );
}
