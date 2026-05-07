import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useIdleTimer } from "./useIdleTimer";

describe("useIdleTimer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("calls reset callback after the default 30 seconds", () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleTimer(onIdle));

    act(() => vi.advanceTimersByTime(29_999));
    expect(onIdle).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1));
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  it("resets the timer on touchstart, click, and keydown activity", () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleTimer(onIdle));

    act(() => vi.advanceTimersByTime(20_000));
    act(() => document.dispatchEvent(new Event("touchstart")));
    act(() => vi.advanceTimersByTime(20_000));
    act(() => document.dispatchEvent(new MouseEvent("click")));
    act(() => vi.advanceTimersByTime(20_000));
    act(() => document.dispatchEvent(new KeyboardEvent("keydown")));
    act(() => vi.advanceTimersByTime(29_999));

    expect(onIdle).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1));
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  it("cleans up timers and listeners on unmount", () => {
    const onIdle = vi.fn();
    const { unmount } = renderHook(() => useIdleTimer(onIdle));

    unmount();
    act(() => document.dispatchEvent(new Event("touchstart")));
    act(() => vi.advanceTimersByTime(30_000));

    expect(onIdle).not.toHaveBeenCalled();
  });

  it("does not call reset callback while disabled", () => {
    const onIdle = vi.fn();
    const { rerender } = renderHook(({ enabled }) => useIdleTimer(onIdle, 30_000, enabled), {
      initialProps: { enabled: false },
    });

    act(() => vi.advanceTimersByTime(30_000));
    expect(onIdle).not.toHaveBeenCalled();

    rerender({ enabled: true });
    act(() => vi.advanceTimersByTime(30_000));
    expect(onIdle).toHaveBeenCalledTimes(1);
  });
});
