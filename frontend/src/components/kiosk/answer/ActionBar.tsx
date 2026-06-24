import { Printer, QrCode, Volume2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ko } from "../../../lang/ko";
import type { Source } from "../../../types/kiosk";
import { QRModal } from "./QRModal";

interface ActionBarProps {
  question: string;
  answer: string;
  sources: Source[];
}

export function ActionBar({ question, answer, sources }: ActionBarProps) {
  const [qrOpen, setQrOpen] = useState(false);
  const [printStatus, setPrintStatus] = useState<"idle" | "pending" | "failed" | "sent">("idle");
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const qrValue = useMemo(
    () =>
      JSON.stringify({
        question,
        answerPreview: answer.slice(0, 280),
      }),
    [answer, question],
  );

  const printAnswer = async () => {
    setPrintStatus("pending");
    try {
      const response = await fetch("http://localhost:6310/print", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, answer, sources }),
      });
      if (mountedRef.current) setPrintStatus(response.ok ? "sent" : "failed");
    } catch {
      if (mountedRef.current) setPrintStatus("failed");
    }
  };

  const showTtsPlaceholder = () => {
    // Future TTS integration starts here after kiosk browser support is verified.
  };

  return (
    <section className="h-full min-h-26 shrink-0 rounded-lg bg-white p-4 shadow-sm">
      <div className="grid h-full grid-cols-3 gap-3">
        <button
          className="flex flex-col items-center justify-center gap-1.5 rounded-md bg-slate-100 py-3 font-semibold disabled:text-slate-400"
          disabled={printStatus === "pending"}
          onClick={printAnswer}
          type="button"
        >
          <Printer aria-hidden="true" className="h-6 w-6" />
          {ko.action.print}
        </button>
        <button
          className="flex flex-col items-center justify-center gap-1.5 rounded-md bg-slate-100 py-3 font-semibold"
          onClick={() => setQrOpen(true)}
          type="button"
        >
          <QrCode aria-hidden="true" className="h-6 w-6" />
          {ko.action.qr}
        </button>
        <button
          className="flex flex-col items-center justify-center gap-1.5 rounded-md bg-slate-100 py-3 font-semibold"
          onClick={showTtsPlaceholder}
          type="button"
        >
          <Volume2 aria-hidden="true" className="h-6 w-6" />
          {ko.action.ttsPending}
        </button>
      </div>
      {printStatus === "pending" ? <p className="mt-2 text-sm text-slate-500">{ko.action.printPending}</p> : null}
      {printStatus === "failed" ? <p className="mt-2 text-sm text-rose-700">{ko.action.printFailed}</p> : null}
      {printStatus === "sent" ? <p className="mt-2 text-sm text-emerald-700">{ko.action.printSent}</p> : null}
      {qrOpen ? <QRModal onClose={() => setQrOpen(false)} value={qrValue} /> : null}
    </section>
  );
}
