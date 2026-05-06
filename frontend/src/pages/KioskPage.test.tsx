import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useKioskStore } from "../store/kioskStore";
import KioskPage from "./KioskPage";

function renderKioskPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <KioskPage />
    </QueryClientProvider>,
  );
}

describe("KioskPage", () => {
  beforeEach(() => {
    useKioskStore.setState({
      mode: "main",
      selectedCategory: null,
      currentQuery: "",
      answerData: null,
    });
  });

  it("renders the main kiosk screen by default", () => {
    renderKioskPage();

    expect(screen.getByText("Campus Copilot")).toBeInTheDocument();
    expect(screen.getByText("궁금한 내용을 입력하세요")).toBeInTheDocument();
  });

  it("renders input mode from store state", () => {
    useKioskStore.setState({ mode: "input" });
    renderKioskPage();

    expect(screen.getByPlaceholderText("질문을 입력하세요")).toBeInTheDocument();
    expect(screen.getByText("인기 질문")).toBeInTheDocument();
  });

  it("renders answer mode from store state", () => {
    useKioskStore.setState({
      mode: "answer",
      currentQuery: "휴학 신청 방법",
      answerData: {
        answer: "휴학은 포털에서 신청합니다.",
        sources: [],
        procedureSteps: [],
        conflictWarning: null,
        isStreaming: false,
      },
    });
    renderKioskPage();

    expect(screen.getByText("휴학 신청 방법")).toBeInTheDocument();
    expect(screen.getByText("휴학은 포털에서 신청합니다.")).toBeInTheDocument();
  });
});
