import { Maximize2, X } from "lucide-react";
import { useState } from "react";

import { AnswerText } from "./AnswerText";

interface AnswerPanelProps {
  answer: string;
  answerability?: "answerable" | "partial" | "insufficient";
  isStreaming: boolean;
  limitations?: string[];
  notes?: string[];
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
  question,
  summary = "",
  statusMessage,
}: AnswerPanelProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const canOpenFullAnswer = answer.trim().length > 0;
  const previewText = buildStructuredPreview({ answer, summary, notes, limitations });

  return (
    <>
      <section className="flex min-h-0 flex-col overflow-hidden rounded-lg bg-white p-7 shadow-sm">
        <div className="flex items-start justify-between gap-6">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">답변</h2>
            {!isStreaming && answerability !== "answerable" ? (
              <p className="mt-2 inline-flex rounded-full bg-amber-50 px-3 py-1 text-sm font-semibold text-amber-800">
                {answerability === "partial" ? "일부 정보 확인됨" : "공식 문서 근거 부족"}
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
              전체 답변 보기
            </button>
          ) : null}
        </div>

        <div aria-label="답변 내용" className="answer-preview-mask mt-5 min-h-0 flex-1 overflow-auto pr-2">
          <AnswerText isStreaming={isStreaming} statusMessage={statusMessage} text={previewText} />
        </div>

        {canOpenFullAnswer ? (
          <button
            className="mt-5 flex min-h-16 w-full items-center justify-center gap-3 rounded-md border border-sky-100 bg-sky-50 text-xl font-bold text-sky-800 transition hover:bg-sky-100 active:scale-[0.99]"
            onClick={() => setIsModalOpen(true)}
            type="button"
          >
            <Maximize2 aria-hidden="true" size={24} strokeWidth={1.8} />
            답변을 크게 보기
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
            aria-label="전체 답변"
            className="flex max-h-[86vh] w-full max-w-5xl flex-col rounded-xl bg-white p-8 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex shrink-0 items-start justify-between gap-6 border-b border-slate-200 pb-5">
              <div>
                <p className="text-lg font-semibold text-sky-800">전체 답변</p>
                <h2 className="mt-1 text-3xl font-bold tracking-tight">{question}</h2>
              </div>
              <button
                aria-label="전체 답변 닫기"
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
  notes,
  limitations,
}: {
  answer: string;
  summary: string;
  notes: string[];
  limitations: string[];
}) {
  const sections = [summary.trim()];
  if (notes.length > 0) {
    sections.push(`준비/주의사항\n${notes.map((note) => `- ${note}`).join("\n")}`);
  }
  if (limitations.length > 0) {
    sections.push(`확인이 필요한 점\n${limitations.map((item) => `- ${item}`).join("\n")}`);
  }
  const structured = sections.filter(Boolean).join("\n\n");
  return structured || answer;
}
