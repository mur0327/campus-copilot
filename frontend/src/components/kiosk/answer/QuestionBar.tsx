import { Home } from "lucide-react";

interface QuestionBarProps {
  question: string;
  onHome: () => void;
}

export function QuestionBar({ question, onHome }: QuestionBarProps) {
  return (
    <header className="flex h-24 shrink-0 items-center gap-5 border-b border-slate-200 bg-white px-8">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-slate-500">질문</p>
        <h1 className="truncate text-2xl font-semibold">{question}</h1>
      </div>
      <button
        className="flex h-14 items-center gap-2 rounded-lg bg-slate-900 px-5 font-semibold text-white"
        onClick={onHome}
        type="button"
      >
        <Home aria-hidden="true" className="h-5 w-5" />
        처음으로
      </button>
    </header>
  );
}
