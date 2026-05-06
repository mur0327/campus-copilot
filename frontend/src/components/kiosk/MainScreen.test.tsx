import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useKioskStore } from "../../store/kioskStore";
import { MainScreen } from "./MainScreen";

function renderMainScreen() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MainScreen />
    </QueryClientProvider>,
  );
}

describe("MainScreen", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline fallback")));
    useKioskStore.setState({
      mode: "main",
      selectedCategory: null,
      currentQuery: "",
      answerData: null,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses the mic button as an input-mode entry point only", () => {
    renderMainScreen();

    fireEvent.click(screen.getByRole("button", { name: "음성 입력" }));

    expect(useKioskStore.getState().mode).toBe("input");
  });
});
