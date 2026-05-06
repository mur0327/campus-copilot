interface ProcedureStepsProps {
  steps: string[];
}

export function ProcedureSteps({ steps }: ProcedureStepsProps) {
  if (steps.length === 0) return null;

  return (
    <ol className="mt-8 grid gap-3">
      {steps.map((step, index) => (
        <li className="flex gap-3 rounded-md bg-slate-50 p-4 text-lg" key={step}>
          <span className="font-bold text-sky-800">{index + 1}</span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  );
}
