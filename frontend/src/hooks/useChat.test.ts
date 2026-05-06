import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useKioskStore } from "../store/kioskStore";
import { useChat } from "./useChat";

vi.mock("../api/chat", () => ({
  postChat: vi.fn(),
}));

import { postChat } from "../api/chat";

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
  it("maps ChatResponsePayload into AnswerData with top-level freshness applied to each source", async () => {
    vi.mocked(postChat).mockResolvedValue({
      answer: "휴학은 포털에서 신청합니다.",
      sources: [{ title: "학사안내", url: "https://example.edu", crawled_at: "2026-04-19" }],
      procedure_steps: ["포털 접속", "휴학 신청"],
      conflict_warning: { exists: false },
      freshness: "recent",
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
          freshness: "recent",
        },
      ],
      procedureSteps: ["포털 접속", "휴학 신청"],
      conflictWarning: { exists: false },
      isStreaming: false,
    });
  });

  it("treats unknown freshness as stale and logs for developers", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.mocked(postChat).mockResolvedValue({
      answer: "확인된 답변입니다.",
      sources: [{ title: "학사안내", url: "https://example.edu", crawled_at: "2026-04-19" }],
      procedure_steps: [],
      conflict_warning: { exists: false },
      freshness: "fresh" as "recent",
    });

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("졸업 요건");
    });

    expect(useKioskStore.getState().answerData?.sources[0]?.freshness).toBe("stale");
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("Unknown source freshness"));
  });

  it("stores a visible fallback answer when chat request fails", async () => {
    vi.mocked(postChat).mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submit("휴학 신청");
    });

    expect(useKioskStore.getState().answerData?.isStreaming).toBe(false);
    expect(useKioskStore.getState().answerData?.answer).toContain("답변을 불러오지 못했습니다");
  });

  it("ignores a stale chat response after reset", async () => {
    let resolveChat: (value: Awaited<ReturnType<typeof postChat>>) => void = () => {};
    vi.mocked(postChat).mockReturnValue(
      new Promise((resolve) => {
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
      resolveChat({
        answer: "늦게 도착한 답변",
        sources: [],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: "recent",
      });
    });

    expect(useKioskStore.getState()).toMatchObject({
      mode: "main",
      currentQuery: "",
      answerData: null,
    });
  });

  it("ignores an older same-question response from a previous hook instance", async () => {
    let resolveFirst: (value: Awaited<ReturnType<typeof postChat>>) => void = () => {};
    let resolveSecond: (value: Awaited<ReturnType<typeof postChat>>) => void = () => {};
    vi.mocked(postChat)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
      )
      .mockReturnValueOnce(
        new Promise((resolve) => {
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
      resolveSecond({
        answer: "최신 답변",
        sources: [],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: "recent",
      });
    });

    await act(async () => {
      resolveFirst({
        answer: "이전 답변",
        sources: [],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: "recent",
      });
    });

    expect(useKioskStore.getState().answerData?.answer).toBe("최신 답변");
  });
});
