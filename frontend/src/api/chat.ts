import type { ChatRequestPayload, ChatResponsePayload } from "../types/kiosk";

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
