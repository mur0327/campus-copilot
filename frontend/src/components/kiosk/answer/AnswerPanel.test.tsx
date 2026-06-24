import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerPanel } from "./AnswerPanel";

describe("AnswerPanel", () => {
  it("renders answer text in the answer section", () => {
    render(<AnswerPanel answer="답변 내용" isStreaming={false} question="질문 내용" />);

    expect(screen.getByText("답변 내용")).toBeInTheDocument();
    expect(screen.queryByText("객관적 안내")).not.toBeInTheDocument();
  });

  it("renders structured summary, procedure steps, notes, and limitations before the legacy answer", () => {
    render(
      <AnswerPanel
        answer="legacy answer"
        isStreaming={false}
        limitations={["제출 서류는 확인되지 않았습니다."]}
        notes={["학사지원팀이 관련 부서로 확인됩니다."]}
        procedureSteps={["단과대학 교학과를 방문합니다.", "휴학원을 제출합니다."]}
        question="질문 내용"
        summary="확인된 요약입니다."
      />,
    );

    expect(screen.getByText("확인된 요약입니다.")).toBeInTheDocument();
    expect(screen.getByText("확인된 절차")).toBeInTheDocument();
    expect(screen.getByText("단과대학 교학과를 방문합니다.")).toBeInTheDocument();
    expect(screen.getByText("휴학원을 제출합니다.")).toBeInTheDocument();
    expect(screen.getByText("준비/주의사항")).toBeInTheDocument();
    expect(screen.getByText("확인이 필요한 점")).toBeInTheDocument();
    expect(screen.queryByText("legacy answer")).not.toBeInTheDocument();
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
