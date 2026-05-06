import { X } from "lucide-react";
import QRCode from "react-qr-code";

interface QRModalProps {
  value: string;
  onClose: () => void;
}

export function QRModal({ value, onClose }: QRModalProps) {
  return (
    <div
      aria-modal="true"
      className="fixed inset-0 flex items-center justify-center bg-slate-950/45 p-8"
      role="dialog"
    >
      <section className="w-full max-w-sm rounded-lg bg-white p-6 text-center shadow-xl">
        <button
          aria-label="QR 닫기"
          className="ml-auto flex h-10 w-10 items-center justify-center rounded-full bg-slate-100"
          onClick={onClose}
          type="button"
        >
          <X aria-hidden="true" className="h-5 w-5" />
        </button>
        <div className="mx-auto mt-3 max-w-64 bg-white p-4">
          <QRCode size={256} style={{ height: "auto", maxWidth: "100%", width: "100%" }} value={value} viewBox="0 0 256 256" />
        </div>
        <p className="mt-4 text-sm text-slate-500">질문과 답변 요약을 확인할 수 있습니다.</p>
      </section>
    </div>
  );
}
