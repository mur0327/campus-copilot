import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerText } from "./AnswerText";

describe("AnswerText", () => {
  it("renders streamed answer without a cursor", () => {
    render(<AnswerText isStreaming={true} text="답변" />);

    expect(screen.getByText("답변")).toBeInTheDocument();
    expect(screen.queryByText("|")).not.toBeInTheDocument();
  });

  it("renders shimmer loading text while waiting for the first answer chunk", () => {
    render(<AnswerText isStreaming={true} text="" />);

    expect(screen.getByTestId("answer-loading-text")).toHaveTextContent("답변을 준비하고 있습니다.");
    expect(screen.queryByText("|")).not.toBeInTheDocument();
  });

  it("renders markdown emphasis instead of raw markdown markers", () => {
    render(<AnswerText isStreaming={false} text="**중요** 안내입니다." />);

    const emphasized = screen.getByText("중요");
    expect(emphasized.tagName).toBe("STRONG");
    expect(screen.queryByText("**중요** 안내입니다.")).not.toBeInTheDocument();
  });
});
