import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InputMode } from "./InputMode";

function renderInputMode() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <InputMode />
    </QueryClientProvider>,
  );
}

describe("InputMode", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline fallback")));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the mic button as a future STT entry point without Web Speech calls", () => {
    const speechRecognition = vi.fn();
    vi.stubGlobal("SpeechRecognition", speechRecognition);
    vi.stubGlobal("webkitSpeechRecognition", speechRecognition);

    renderInputMode();
    fireEvent.click(screen.getByRole("button", { name: "음성 입력" }));

    expect(screen.getByText("음성 입력은 추후 운영 환경에서 사용할 예정입니다.")).toBeInTheDocument();
    expect(speechRecognition).not.toHaveBeenCalled();
  });
});
