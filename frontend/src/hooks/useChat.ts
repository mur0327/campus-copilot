import { useCallback, useRef } from "react";

import { postChat } from "../api/chat";
import { useKioskStore } from "../store/kioskStore";
import { mapChatResponseToAnswerData } from "../types/kiosk";

let latestChatRequestId = 0;

export function useChat() {
  const requestIdRef = useRef(0);
  const submitQuery = useKioskStore((state) => state.submitQuery);
  const setAnswerData = useKioskStore((state) => state.setAnswerData);

  const submit = useCallback(
    async (question: string) => {
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;
      latestChatRequestId += 1;
      const globalRequestId = latestChatRequestId;

      submitQuery(question);
      setAnswerData({
        answer: "",
        sources: [],
        procedureSteps: [],
        conflictWarning: null,
        isStreaming: true,
      });

      try {
        const response = await postChat({ question });
        const state = useKioskStore.getState();
        if (
          requestId !== requestIdRef.current ||
          globalRequestId !== latestChatRequestId ||
          state.mode !== "answer" ||
          state.currentQuery !== question
        ) {
          return;
        }
        setAnswerData(mapChatResponseToAnswerData(response));
      } catch (error) {
        const state = useKioskStore.getState();
        if (
          requestId !== requestIdRef.current ||
          globalRequestId !== latestChatRequestId ||
          state.mode !== "answer" ||
          state.currentQuery !== question
        ) {
          return;
        }
        console.warn("chat request failed; using fallback answer.", error);
        setAnswerData({
          answer: "답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
          sources: [],
          procedureSteps: [],
          conflictWarning: null,
          isStreaming: false,
        });
      }
    },
    [setAnswerData, submitQuery],
  );

  return { submit };
}
