import { fetchEventSource } from "@microsoft/fetch-event-source";

import type {
  ChatErrorPayload,
  ChatRequestPayload,
  ChatResponsePayload,
  ChatStatusPayload,
} from "../types/kiosk";

export interface ChatStreamHandlers {
  onStatus: (step: ChatStatusPayload["step"]) => void;
  onDone: (payload: ChatResponsePayload) => void;
  onError: (message: string) => void;
}

export async function postChat(payload: ChatRequestPayload): Promise<ChatResponsePayload> {
  const response = await fetch("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`chat fetch failed: ${response.status}`);
  }

  return response.json() as Promise<ChatResponsePayload>;
}

export async function streamChat(
  payload: ChatRequestPayload,
  handlers: ChatStreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  let receivedDone = false;

  await fetchEventSource("/api/v1/chat", {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
    openWhenHidden: true,
    async onopen(response) {
      if (!response.ok) {
        throw new Error(`chat stream failed: ${response.status}`);
      }
    },
    onmessage(message) {
      try {
        switch (message.event) {
          case "status":
            handlers.onStatus(parseEventData<ChatStatusPayload>(message.data, "status").step);
            return;
          case "done":
            receivedDone = true;
            handlers.onDone(parseEventData<ChatResponsePayload>(message.data, "done"));
            return;
          case "error": {
            const payload = parseEventData<ChatErrorPayload>(message.data, "error");
            const error = new HandledChatStreamError(payload.message || "chat stream error");
            handlers.onError(error.message);
            throw error;
          }
          default:
            if (message.event) {
              throw new Error(`unknown chat stream event: ${message.event}`);
            }
        }
      } catch (error) {
        throw toError(error, "chat stream event parse failed");
      }
    },
    onclose() {
      if (!receivedDone) {
        throw new Error("chat stream closed before done event");
      }
    },
    onerror(error) {
      const normalized = toError(error, "chat stream failed");
      if (normalized instanceof HandledChatStreamError) {
        throw normalized;
      }
      handlers.onError(normalized.message);
      throw normalized;
    },
  });
}

function parseEventData<T>(data: string, eventName: string): T {
  try {
    return JSON.parse(data) as T;
  } catch (error) {
    throw new Error(`invalid ${eventName} event data`, { cause: error });
  }
}

function toError(error: unknown, fallbackMessage: string): Error {
  return error instanceof Error ? error : new Error(fallbackMessage);
}

class HandledChatStreamError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "HandledChatStreamError";
  }
}
