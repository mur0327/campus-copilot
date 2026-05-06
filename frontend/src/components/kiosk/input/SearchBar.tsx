import { ArrowLeft, Mic, Send } from "lucide-react";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onBack: () => void;
  onSubmit: () => void;
  onVoice: () => void;
}

export function SearchBar({ value, onChange, onBack, onSubmit, onVoice }: SearchBarProps) {
  const canSubmit = value.trim().length > 0;

  return (
    <header className="flex h-24 shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-8">
      <button
        aria-label="뒤로"
        className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-100"
        onClick={onBack}
        type="button"
      >
        <ArrowLeft aria-hidden="true" className="h-7 w-7" />
      </button>
      <input
        autoFocus
        className="h-16 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-5 text-2xl outline-none focus:border-sky-500"
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && canSubmit) onSubmit();
        }}
        placeholder="질문을 입력하세요"
        value={value}
      />
      <button
        aria-label="음성 입력"
        className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-700"
        onClick={onVoice}
        type="button"
      >
        <Mic aria-hidden="true" className="h-7 w-7" />
      </button>
      <button
        className="flex h-14 min-w-28 items-center justify-center gap-2 rounded-lg bg-sky-800 px-5 font-semibold text-white disabled:bg-slate-300 disabled:text-slate-600"
        disabled={!canSubmit}
        onClick={onSubmit}
        type="button"
      >
        <Send aria-hidden="true" className="h-5 w-5" />
        전송
      </button>
    </header>
  );
}
