import { Maximize2, X } from "lucide-react";
import { useState } from "react";

import { ko } from "../../../lang/ko";
import { AnswerText } from "./AnswerText";

interface AnswerPanelProps {
  answer: string;
  answerability?: "answerable" | "partial" | "insufficient";
  isStreaming: boolean;
  limitations?: string[];
  notes?: string[];
  procedureSteps?: string[];
  question: string;
  summary?: string;
  statusMessage?: string;
}

export function AnswerPanel({
  answer,
  answerability = "answerable",
  isStreaming,
  limitations = [],
  notes = [],
  procedureSteps = [],
  question,
  summary = "",
  statusMessage,
}: AnswerPanelProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const canOpenFullAnswer = answer.trim().length > 0;
  const previewText = buildStructuredPreview({ answer, summary, procedureSteps, notes, limitations });

  return (
    <>
      <section className="flex min-h-0 flex-col overflow-hidden rounded-lg bg-white p-7 shadow-sm">
        <div className="flex items-start justify-between gap-6">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{ko.answer.title}</h2>
            {!isStreaming && answerability !== "answerable" ? (
              <p className="mt-2 inline-flex rounded-full bg-amber-50 px-3 py-1 text-sm font-semibold text-amber-800">
                {answerability === "partial" ? ko.answer.partialBadge : ko.answer.insufficientBadge}
              </p>
            ) : null}
          </div>
          {canOpenFullAnswer ? (
            <button
              className="flex min-h-12 shrink-0 items-center gap-2 rounded-md bg-slate-950 px-5 text-base font-semibold text-white transition active:scale-[0.98]"
              onClick={() => setIsModalOpen(true)}
              type="button"
            >
              <Maximize2 aria-hidden="true" size={20} strokeWidth={1.8} />
              {ko.answer.openFullAnswer}
            </button>
          ) : null}
        </div>

        <div aria-label={ko.answer.contentLabel} className="mt-5 min-h-0 flex-1 overflow-auto pr-2">
          <AnswerText isStreaming={isStreaming} statusMessage={statusMessage} text={previewText} />
        </div>

        {canOpenFullAnswer ? (
          <button
            className="mt-5 flex min-h-16 w-full items-center justify-center gap-3 rounded-md border border-sky-100 bg-sky-50 text-xl font-bold text-sky-800 transition hover:bg-sky-100 active:scale-[0.99]"
            onClick={() => setIsModalOpen(true)}
            type="button"
          >
            <Maximize2 aria-hidden="true" size={24} strokeWidth={1.8} />
            {ko.answer.enlargeAnswer}
          </button>
        ) : null}
      </section>

      {isModalOpen ? (
        <div
          aria-modal="true"
          className="fixed inset-0 flex items-center justify-center bg-slate-950/55 p-8"
          onClick={() => setIsModalOpen(false)}
          role="dialog"
        >
          <section
            aria-label={ko.answer.fullAnswerTitle}
            className="flex max-h-[86vh] w-full max-w-5xl flex-col rounded-xl bg-white p-8 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex shrink-0 items-start justify-between gap-6 border-b border-slate-200 pb-5">
              <div>
                <p className="text-lg font-semibold text-sky-800">{ko.answer.fullAnswerTitle}</p>
                <h2 className="mt-1 text-3xl font-bold tracking-tight">{question}</h2>
              </div>
              <button
                aria-label={ko.answer.closeFullAnswer}
                className="flex h-14 w-14 items-center justify-center rounded-md bg-slate-100 text-slate-700 transition hover:bg-slate-200 active:scale-[0.98]"
                onClick={() => setIsModalOpen(false)}
                type="button"
              >
                <X aria-hidden="true" size={30} strokeWidth={1.8} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-auto pt-5">
              <AnswerText isStreaming={false} text={answer} />
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}

function buildStructuredPreview({
  answer,
  summary,
  procedureSteps,
  notes,
  limitations,
}: {
  answer: string;
  summary: string;
  procedureSteps: string[];
  notes: string[];
  limitations: string[];
}) {
  const sections = [summary.trim()];
  if (procedureSteps.length > 0) {
    sections.push(
      `**${ko.answer.section.procedure}**\n${procedureSteps.map((step, index) => `${index + 1}. ${step}`).join("\n")}`,
    );
  }
  if (notes.length > 0) {
    sections.push(`**${ko.answer.section.notes}**\n${notes.map((note) => `- ${note}`).join("\n")}`);
  }
  if (limitations.length > 0) {
    sections.push(`**${ko.answer.section.limitations}**\n${limitations.map((item) => `- ${item}`).join("\n")}`);
  }
  const structured = sections.filter(Boolean).join("\n\n");
  return structured || answer;
}
