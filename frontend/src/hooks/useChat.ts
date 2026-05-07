import { useCallback, useRef } from "react";

import { streamChat } from "../api/chat";
import { useKioskStore } from "../store/kioskStore";
import {
  mapChatResponseToAnswerData,
  normalizeSourceFreshness,
  type ChatMetadataPayload,
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
        answer: "",
        sources: [],
        procedureSteps: [],
        conflictWarning: null,
        isStreaming: true,
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

      const setFallbackAnswer = () => {
        setAnswerData({
          answer: "답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
          sources: [],
          procedureSteps: [],
          conflictWarning: null,
          isStreaming: false,
        });
      };

      try {
        await streamChat(
          { question },
          {
            onMetadata: (payload) => {
              if (!isCurrentRequest()) {
                return;
              }

              setAnswerData((current) => applyMetadata(current, payload));
            },
            onToken: (text) => {
              if (!isCurrentRequest()) {
                return;
              }

              setAnswerData((current) => ({
                answer: `${current?.answer ?? ""}${text}`,
                sources: current?.sources ?? [],
                procedureSteps: current?.procedureSteps ?? [],
                conflictWarning: current?.conflictWarning ?? null,
                isStreaming: true,
              }));
            },
            onProcedureSteps: (procedureSteps) => {
              if (!isCurrentRequest()) {
                return;
              }

              setAnswerData((current) => ({
                answer: current?.answer ?? "",
                sources: current?.sources ?? [],
                procedureSteps,
                conflictWarning: current?.conflictWarning ?? null,
                isStreaming: true,
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
              setFallbackAnswer();
            },
          },
          abortController.signal,
        );
      } catch (error) {
        if (!isCurrentRequest()) {
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

function applyMetadata(
  current: ReturnType<typeof useKioskStore.getState>["answerData"],
  payload: ChatMetadataPayload,
) {
  const topLevelFreshness = payload.freshness
    ? normalizeSourceFreshness(payload.freshness)
    : undefined;

  return {
    answer: current?.answer ?? "",
    sources:
      payload.sources?.map(({ title, url, crawled_at, freshness, chunk_id }) => ({
        title,
        url,
        crawled_at,
        freshness: freshness
          ? normalizeSourceFreshness(freshness)
          : (topLevelFreshness ?? "stale"),
        chunk_id,
      })) ??
      current?.sources ??
      [],
    procedureSteps: payload.procedure_steps ?? current?.procedureSteps ?? [],
    conflictWarning: payload.conflict_warning ?? current?.conflictWarning ?? null,
    isStreaming: true,
  };
}
