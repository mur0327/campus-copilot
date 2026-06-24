import { Printer, QrCode, Volume2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Panel } from "../../ui/Panel";
import { TileButton } from "../../ui/TileButton";
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

  const actions = [
    {
      disabled: printStatus === "pending",
      icon: <Printer aria-hidden="true" className="h-6 w-6" />,
      label: ko.action.print,
      onClick: printAnswer,
    },
    {
      icon: <QrCode aria-hidden="true" className="h-6 w-6" />,
      label: ko.action.qr,
      onClick: () => setQrOpen(true),
    },
    {
      icon: <Volume2 aria-hidden="true" className="h-6 w-6" />,
      label: ko.action.ttsPending,
      onClick: showTtsPlaceholder,
    },
  ];

  return (
    <Panel className="h-full min-h-26 shrink-0">
      <div className="grid h-full grid-cols-3 gap-3">
        {actions.map((action) => (
          <TileButton disabled={action.disabled} icon={action.icon} key={action.label} onClick={action.onClick}>
            {action.label}
          </TileButton>
        ))}
      </div>
      {printStatus === "pending" ? <p className="mt-2 text-sm text-slate-500">{ko.action.printPending}</p> : null}
      {printStatus === "failed" ? <p className="mt-2 text-sm text-rose-700">{ko.action.printFailed}</p> : null}
      {printStatus === "sent" ? <p className="mt-2 text-sm text-emerald-700">{ko.action.printSent}</p> : null}
      {qrOpen ? <QRModal onClose={() => setQrOpen(false)} value={qrValue} /> : null}
    </Panel>
  );
}
