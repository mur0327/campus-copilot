import { useCallback, useRef } from "react";

import { streamChat } from "../api/chat";
import { useKioskStore } from "../store/kioskStore";
import {
  mapChatResponseToAnswerData,
  type ChatStatusStep,
} from "../types/kiosk";

let latestChatRequestId = 0;
let activeChatAbortController: AbortController | null = null;

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
      activeChatAbortController?.abort();
      const abortController = new AbortController();
      activeChatAbortController = abortController;

      submitQuery(question);
      setAnswerData({
        answerability: "insufficient",
        answer: "",
        summary: "",
        sources: [],
        procedureSteps: [],
        notes: [],
        limitations: [],
        conflictWarning: null,
        isStreaming: true,
        statusMessage: statusMessageForStep("retrieving"),
      });

      const isCurrentRequest = () => {
        const state = useKioskStore.getState();
        return (
          requestId === requestIdRef.current &&
          globalRequestId === latestChatRequestId &&
          state.mode === "answer" &&
          state.currentQuery === question
        );
      };

      const setFallbackAnswer = (
        message = "답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      ) => {
        setAnswerData({
          answerability: "insufficient",
          answer: message,
          summary: message,
          sources: [],
          procedureSteps: [],
          notes: [],
          limitations: [],
          conflictWarning: null,
          isStreaming: false,
        });
      };

      try {
        await streamChat(
          { question },
          {
            onStatus: (step) => {
              if (!isCurrentRequest()) {
                return;
              }

              setAnswerData((current) => ({
                answerability: current?.answerability ?? "insufficient",
                answer: "",
                summary: "",
                sources: current?.sources ?? [],
                procedureSteps: current?.procedureSteps ?? [],
                notes: current?.notes ?? [],
                limitations: current?.limitations ?? [],
                conflictWarning: current?.conflictWarning ?? null,
                isStreaming: true,
                statusMessage: statusMessageForStep(step),
              }));
            },
            onDone: (payload) => {
              if (!isCurrentRequest()) {
                return;
              }

              setAnswerData(mapChatResponseToAnswerData(payload));
            },
            onError: (message) => {
              if (!isCurrentRequest()) {
                return;
              }

              console.warn("chat stream failed; using fallback answer.", message);
              setFallbackAnswer(message);
            },
          },
          abortController.signal,
        );
      } catch (error) {
        if (!isCurrentRequest()) {
          return;
        }
        if (error instanceof Error && error.name === "HandledChatStreamError") {
          return;
        }
        console.warn("chat request failed; using fallback answer.", error);
        setFallbackAnswer();
      } finally {
        if (activeChatAbortController === abortController) {
          activeChatAbortController = null;
        }
      }
    },
    [setAnswerData, submitQuery],
  );

  return { submit };
}

export function statusMessageForStep(step: ChatStatusStep): string {
  switch (step) {
    case "retrieving":
      return "공식 문서 검색 중";
    case "checking_evidence":
      return "근거 확인 중";
    case "generating":
      return "답변 작성 중";
    case "validating":
      return "답변 검증 중";
  }
}
