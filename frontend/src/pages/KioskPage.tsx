import { AnswerScreen } from "../components/kiosk/AnswerScreen";
import { InputMode } from "../components/kiosk/InputMode";
import { MainScreen } from "../components/kiosk/MainScreen";
import { useIdleTimer } from "../hooks/useIdleTimer";
import { useKioskStore } from "../store/kioskStore";

export default function KioskPage() {
  const mode = useKioskStore((state) => state.mode);
  const resetToMain = useKioskStore((state) => state.resetToMain);

  useIdleTimer(() => {
    // Future TTS integration should stop active speech as part of idle reset.
    resetToMain();
  });

  return (
    <main className="h-screen w-screen overflow-hidden">
      {mode === "main" ? <MainScreen /> : null}
      {mode === "input" ? <InputMode /> : null}
      {mode === "answer" ? <AnswerScreen /> : null}
    </main>
  );
}
