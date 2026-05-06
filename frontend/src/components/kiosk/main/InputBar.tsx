import { Mic, Send } from "lucide-react";

interface InputBarProps {
  onFocus: () => void;
  onVoice: () => void;
}

export function InputBar({ onFocus, onVoice }: InputBarProps) {
  return (
    <footer className="flex h-24 shrink-0 items-center gap-4 border-t border-slate-200 bg-white px-10">
      <button
        aria-label="음성 입력"
        className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-700"
        onClick={onVoice}
        type="button"
      >
        <Mic aria-hidden="true" className="h-7 w-7" />
      </button>
      <button
        className="flex h-16 flex-1 items-center rounded-lg border border-slate-200 bg-slate-50 px-6 text-left text-xl text-slate-500"
        onClick={onFocus}
        type="button"
      >
        궁금한 내용을 입력하세요
      </button>
      <button
        aria-label="입력 화면 열기"
        className="flex h-16 w-16 items-center justify-center rounded-lg bg-sky-800 text-white"
        onClick={onFocus}
        type="button"
      >
        <Send aria-hidden="true" className="h-7 w-7" />
      </button>
    </footer>
  );
}
