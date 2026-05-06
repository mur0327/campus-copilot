import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useKioskStore } from "../store/kioskStore";
import type { ChatStreamHandlers } from "../api/chat";
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

describe("useChat", () => {
  it("appends streamed tokens and finalizes the done payload", async () => {
    vi.mocked(streamChat).mockImplementation(async (_payload, handlers) => {
      handlers.onMetadata({
        sources: [
          {
            title: "학사안내",
            url: "https://example.edu",
            crawled_at: "2026-04-19",
            freshness: "stale",
            chunk_id: "chunk-1",
          },
        ],
        conflict_warning: { exists: false },
        freshness: "recent",
      });
      handlers.onToken("휴학은 ");
      handlers.onToken("포털에서 신청합니다.");
      handlers.onDone({
        answer: "휴학은 포털에서 신청합니다.",
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
        conflict_warning: { exists: false },
        freshness: "recent",
      });
    });

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("휴학 신청");
    });

    expect(useKioskStore.getState().currentQuery).toBe("휴학 신청");
    expect(useKioskStore.getState().mode).toBe("answer");
    expect(useKioskStore.getState().answerData).toEqual({
      answer: "휴학은 포털에서 신청합니다.",
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
      conflictWarning: { exists: false },
      isStreaming: false,
    });
  });

  it("updates procedure steps from the procedure_steps stream event before done", async () => {
    let capturedHandlers: ChatStreamHandlers | null = null;
    vi.mocked(streamChat).mockImplementation(
      (_payload, handlers) =>
        new Promise((resolve) => {
          capturedHandlers = handlers;
          handlers.onProcedureSteps(["포털 접속", "휴학 신청"]);
          resolve();
        }),
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("휴학 신청");
    });

    expect(capturedHandlers).not.toBeNull();
    expect(useKioskStore.getState().answerData).toMatchObject({
      procedureSteps: ["포털 접속", "휴학 신청"],
      isStreaming: true,
    });
  });

  it("treats unknown freshness as stale and logs for developers", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.mocked(streamChat).mockImplementation(async (_payload, handlers) => {
      handlers.onDone({
        answer: "확인된 답변입니다.",
        sources: [{ title: "학사안내", url: "https://example.edu", crawled_at: "2026-04-19" }],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: "fresh" as "recent",
      });
    });

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("졸업 요건");
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
      capturedHandlers?.onDone({
        answer: "늦게 도착한 답변",
        sources: [],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: "recent",
      });
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
      secondHandlers?.onDone({
        answer: "최신 답변",
        sources: [],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: "recent",
      });
      resolveSecond();
    });

    expect(vi.mocked(streamChat).mock.calls[0]?.[2]?.aborted).toBe(true);

    await act(async () => {
      firstHandlers?.onToken("이전 토큰");
      firstHandlers?.onDone({
        answer: "이전 답변",
        sources: [],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: "recent",
      });
      resolveFirst();
    });

    expect(useKioskStore.getState().answerData?.answer).toBe("최신 답변");
  });
});
