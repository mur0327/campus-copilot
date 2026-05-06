import { afterEach, describe, expect, it, vi } from "vitest";

import { streamChat } from "./chat";

const { fetchEventSourceMock } = vi.hoisted(() => ({
  fetchEventSourceMock: vi.fn(),
}));

vi.mock("@microsoft/fetch-event-source", () => ({
  fetchEventSource: fetchEventSourceMock,
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe("streamChat", () => {
  it("keeps POST streams open while hidden and fails if the stream closes before done", async () => {
    fetchEventSourceMock.mockImplementation(async (_url, options) => {
      options.onclose();
    });

    await expect(
      streamChat(
        { question: "휴학 신청" },
        {
          onMetadata: vi.fn(),
          onToken: vi.fn(),
          onProcedureSteps: vi.fn(),
          onDone: vi.fn(),
          onError: vi.fn(),
        },
        new AbortController().signal,
      ),
    ).rejects.toThrow("chat stream closed before done event");

    expect(fetchEventSourceMock).toHaveBeenCalledWith(
      "/api/v1/chat",
      expect.objectContaining({
        method: "POST",
        openWhenHidden: true,
        headers: expect.objectContaining({
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("accepts close after the done event", async () => {
    const onDone = vi.fn();
    fetchEventSourceMock.mockImplementation(async (_url, options) => {
      options.onmessage({
        event: "done",
        data: JSON.stringify({
          answer: "답변",
          sources: [],
          procedure_steps: [],
          conflict_warning: { exists: false },
          freshness: "recent",
        }),
      });
      options.onclose();
    });

    await expect(
      streamChat(
        { question: "휴학 신청" },
        {
          onMetadata: vi.fn(),
          onToken: vi.fn(),
          onProcedureSteps: vi.fn(),
          onDone,
          onError: vi.fn(),
        },
        new AbortController().signal,
      ),
    ).resolves.toBeUndefined();

    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ answer: "답변" }));
  });
});
