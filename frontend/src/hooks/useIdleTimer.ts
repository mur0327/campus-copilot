import { useCallback, useEffect, useRef } from "react";

const DEFAULT_IDLE_TIMEOUT_MS = 30_000;
const ACTIVITY_EVENTS = ["touchstart", "click", "keydown"] as const;

export function useIdleTimer(onReset: () => void, timeoutMs = DEFAULT_IDLE_TIMEOUT_MS): void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onResetRef = useRef(onReset);

  onResetRef.current = onReset;

  const resetTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(() => {
      onResetRef.current();
    }, timeoutMs);
  }, [timeoutMs]);

  useEffect(() => {
    resetTimer();

    ACTIVITY_EVENTS.forEach((eventName) => {
      document.addEventListener(eventName, resetTimer);
    });

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      ACTIVITY_EVENTS.forEach((eventName) => {
        document.removeEventListener(eventName, resetTimer);
      });
    };
  }, [resetTimer]);
}
