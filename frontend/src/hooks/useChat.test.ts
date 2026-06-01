import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useKioskStore } from "../store/kioskStore";
import type { ChatStreamHandlers } from "../api/chat";
import type { ChatResponsePayload } from "../types/kiosk";
import { useChat } from "./useChat";

vi.mock("../api/chat", () => ({
  streamChat: vi.fn(),
}));

import { streamChat } from "../api/chat";

beforeEach(() => {
  useKioskStore.setState({
    mode: "main",
    selectedCategory: null,
    currentQuery: "",
    answerData: null,
  });
  vi.clearAllMocks();
});

function makeDonePayload(overrides: Partial<ChatResponsePayload> = {}): ChatResponsePayload {
  return {
    answerability: "answerable",
    answer: "휴학은 포털에서 신청합니다.",
    summary: "휴학은 포털에서 신청합니다.",
    sources: [],
    procedure_steps: [],
    notes: [],
    limitations: [],
    conflict_warning: { exists: false },
    freshness: "recent",
    ...overrides,
  };
}

describe("useChat", () => {
  it("shows status messages and finalizes the done payload", async () => {
    vi.mocked(streamChat).mockImplementation(async (_payload, handlers) => {
      handlers.onStatus("retrieving");
      handlers.onDone(
        makeDonePayload({
          sources: [
            {
              title: "학사안내",
              url: "https://example.edu",
              crawled_at: "2026-04-19",
              freshness: "stale",
              chunk_id: "chunk-1",
            },
          ],
          procedure_steps: ["포털 접속", "휴학 신청"],
        }),
      );
    });

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("휴학 신청");
    });

    expect(useKioskStore.getState().currentQuery).toBe("휴학 신청");
    expect(useKioskStore.getState().mode).toBe("answer");
    expect(useKioskStore.getState().answerData).toEqual({
      answerability: "answerable",
      answer: "휴학은 포털에서 신청합니다.",
      summary: "휴학은 포털에서 신청합니다.",
      sources: [
        {
          title: "학사안내",
          url: "https://example.edu",
          crawled_at: "2026-04-19",
          freshness: "stale",
          chunk_id: "chunk-1",
        },
      ],
      procedureSteps: ["포털 접속", "휴학 신청"],
      notes: [],
      limitations: [],
      conflictWarning: { exists: false },
      isStreaming: false,
    });
  });

  it("updates progress from status stream events before done", async () => {
    let capturedHandlers: ChatStreamHandlers | null = null;
    vi.mocked(streamChat).mockImplementation(
      (_payload, handlers) =>
        new Promise((resolve) => {
          capturedHandlers = handlers;
          handlers.onStatus("checking_evidence");
          resolve();
        }),
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("휴학 신청");
    });

    expect(capturedHandlers).not.toBeNull();
    expect(useKioskStore.getState().answerData).toMatchObject({
      statusMessage: "근거 확인 중",
      isStreaming: true,
    });
  });

  it("treats unknown freshness as stale and logs for developers", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.mocked(streamChat).mockImplementation(async (_payload, handlers) => {
      handlers.onDone(
        makeDonePayload({
          answer: "확인된 답변입니다.",
          summary: "확인된 답변입니다.",
          sources: [
            {
              title: "학사안내",
              url: "https://example.edu",
              crawled_at: "2026-04-19",
              freshness: "fresh" as "recent",
            },
          ],
        }),
      );
    });

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("휴학 신청");
    });

    expect(useKioskStore.getState().answerData?.sources[0]?.freshness).toBe("stale");
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("Unknown source freshness"));
  });

  it("stores a visible fallback answer when chat request fails", async () => {
    vi.mocked(streamChat).mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("휴학 신청");
    });

    expect(useKioskStore.getState().answerData?.isStreaming).toBe(false);
    expect(useKioskStore.getState().answerData?.answer).toContain("답변을 불러오지 못했습니다");
  });

  it("keeps the backend safe error message for handled stream errors", async () => {
    vi.mocked(streamChat).mockImplementation(async (_payload, handlers) => {
      handlers.onError("답변을 확인하는 중 문제가 발생했습니다. 다시 질문해 주세요.");
      const error = new Error("답변을 확인하는 중 문제가 발생했습니다. 다시 질문해 주세요.");
      error.name = "HandledChatStreamError";
      throw error;
    });

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("휴학 신청");
    });

    expect(useKioskStore.getState().answerData).toMatchObject({
      answer: "답변을 확인하는 중 문제가 발생했습니다. 다시 질문해 주세요.",
      isStreaming: false,
    });
  });

  it("ignores a stale chat response after reset", async () => {
    let resolveChat: () => void = () => {};
    let capturedHandlers: ChatStreamHandlers | null = null;
    vi.mocked(streamChat).mockImplementation(
      (_payload, handlers) =>
        new Promise((resolve) => {
          capturedHandlers = handlers;
          resolveChat = resolve;
        }),
    );

    const { result } = renderHook(() => useChat());
    void act(() => {
      void result.current.submit("휴학 신청");
    });

    act(() => {
      useKioskStore.getState().resetToMain();
    });

    await act(async () => {
      capturedHandlers?.onDone(makeDonePayload({
        answer: "늦게 도착한 답변",
        summary: "늦게 도착한 답변",
      }));
      resolveChat();
    });

    expect(useKioskStore.getState()).toMatchObject({
      mode: "main",
      currentQuery: "",
      answerData: null,
    });
  });

  it("ignores an older same-question response from a previous hook instance", async () => {
    let resolveFirst: () => void = () => {};
    let resolveSecond: () => void = () => {};
    let firstHandlers: ChatStreamHandlers | null = null;
    let secondHandlers: ChatStreamHandlers | null = null;
    vi.mocked(streamChat)
      .mockImplementationOnce(
        (_payload, handlers, signal) =>
          new Promise((resolve) => {
            firstHandlers = handlers;
            resolveFirst = resolve;
            expect(signal?.aborted).toBe(false);
          }),
      )
      .mockImplementationOnce(
        (_payload, handlers) =>
          new Promise((resolve) => {
            secondHandlers = handlers;
            resolveSecond = resolve;
          }),
      );

    const first = renderHook(() => useChat());
    void act(() => {
      void first.result.current.submit("휴학 신청");
    });
    first.unmount();

    const second = renderHook(() => useChat());
    void act(() => {
      void second.result.current.submit("휴학 신청");
    });

    await act(async () => {
      secondHandlers?.onDone(makeDonePayload({
        answer: "최신 답변",
        summary: "최신 답변",
      }));
      resolveSecond();
    });

    expect(vi.mocked(streamChat).mock.calls[0]?.[2]?.aborted).toBe(true);

    await act(async () => {
      firstHandlers?.onDone(makeDonePayload({
        answer: "이전 답변",
        summary: "이전 답변",
      }));
      resolveFirst();
    });

    expect(useKioskStore.getState().answerData?.answer).toBe("최신 답변");
  });
});
