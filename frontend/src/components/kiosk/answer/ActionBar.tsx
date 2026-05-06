import { Printer, QrCode, Volume2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

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
    <section className="rounded-lg bg-white p-5 shadow-sm">
      <div className="grid grid-cols-3 gap-3">
        <button
          className="min-h-16 rounded-md bg-slate-100 font-semibold disabled:text-slate-400"
          disabled={printStatus === "pending"}
          onClick={printAnswer}
          type="button"
        >
          <Printer aria-hidden="true" className="mx-auto mb-1 h-5 w-5" />
          인쇄
        </button>
        <button className="min-h-16 rounded-md bg-slate-100 font-semibold" onClick={() => setQrOpen(true)} type="button">
          <QrCode aria-hidden="true" className="mx-auto mb-1 h-5 w-5" />
          QR
        </button>
        <button className="min-h-16 rounded-md bg-slate-100 font-semibold" onClick={showTtsPlaceholder} type="button">
          <Volume2 aria-hidden="true" className="mx-auto mb-1 h-5 w-5" />
          읽기 예정
        </button>
      </div>
      {printStatus === "pending" ? <p className="mt-3 text-sm text-slate-500">인쇄 요청 중</p> : null}
      {printStatus === "failed" ? <p className="mt-3 text-sm text-rose-700">인쇄 서비스에 연결하지 못했습니다.</p> : null}
      {printStatus === "sent" ? <p className="mt-3 text-sm text-emerald-700">인쇄 요청을 보냈습니다.</p> : null}
      <p className="mt-3 text-sm text-slate-500">TTS는 추후 운영 환경에서 사용할 예정입니다.</p>
      {qrOpen ? <QRModal onClose={() => setQrOpen(false)} value={qrValue} /> : null}
    </section>
  );
}
