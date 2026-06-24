import { CheckCircle2, ClipboardList } from "lucide-react";

import { ko } from "../../../lang/ko";

interface ProcedureStepsProps {
  steps: string[];
  isStreaming?: boolean;
}

export function ProcedureSteps({ steps, isStreaming = false }: ProcedureStepsProps) {
  const hasSteps = steps.length > 0;

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg bg-white p-4 shadow-sm">
      <div className="flex shrink-0 items-center justify-between gap-4">
        <div>
          <p className="text-base font-semibold text-sky-800">{ko.procedure.eyebrow}</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight">{ko.procedure.title}</h2>
        </div>
        <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-50 text-sky-800">
          <ClipboardList aria-hidden="true" size={24} strokeWidth={1.8} />
        </span>
      </div>

      {hasSteps ? (
        <ol className="mt-4 grid min-h-0 gap-2 overflow-auto pr-1">
          {steps.map((step, index) => (
            <li className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3 rounded-md bg-slate-50 p-2.5 text-base" key={step}>
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white font-bold text-sky-800 shadow-sm">
                {index + 1}
              </span>
              <span className="self-center leading-snug">{step}</span>
            </li>
          ))}
        </ol>
      ) : (
        <div className="mt-5 flex items-center gap-3 rounded-md bg-slate-50 p-4 text-lg text-slate-600">
          <CheckCircle2 aria-hidden="true" className="shrink-0 text-slate-500" size={24} strokeWidth={1.8} />
          <span>{isStreaming ? ko.procedure.loading : ko.procedure.empty}</span>
        </div>
      )}
    </section>
  );
}
