import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerPanel } from "./AnswerPanel";

describe("AnswerPanel", () => {
  it("renders answer text in the answer section", () => {
    render(<AnswerPanel answer="답변 내용" isStreaming={false} question="질문 내용" />);

    expect(screen.getByText("답변 내용")).toBeInTheDocument();
    expect(screen.queryByText("객관적 안내")).not.toBeInTheDocument();
  });

  it("makes the answer preview scrollable", () => {
    render(<AnswerPanel answer="답변 내용" isStreaming={false} question="질문 내용" />);

    expect(screen.getByLabelText("답변 내용")).toHaveClass("overflow-auto");
  });

  it("opens a full answer dialog", () => {
    render(<AnswerPanel answer="긴 답변 내용" isStreaming={false} question="교양학점은 몇 학점을 이수해야 하나요" />);

    fireEvent.click(screen.getByRole("button", { name: "답변을 크게 보기" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("교양학점은 몇 학점을 이수해야 하나요")).toBeInTheDocument();
    expect(screen.queryByText("답변을 크게 표시합니다")).not.toBeInTheDocument();
  });
});
