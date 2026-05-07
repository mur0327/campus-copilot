import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerText } from "./AnswerText";

describe("AnswerText", () => {
  it("renders answer and streaming cursor", () => {
    render(<AnswerText isStreaming={true} text="답변" />);

    expect(screen.getByText("답변")).toBeInTheDocument();
    expect(screen.getByTestId("streaming-cursor")).toBeInTheDocument();
  });

  it("renders markdown emphasis instead of raw markdown markers", () => {
    render(<AnswerText isStreaming={false} text="**중요** 안내입니다." />);

    const emphasized = screen.getByText("중요");
    expect(emphasized.tagName).toBe("STRONG");
    expect(screen.queryByText("**중요** 안내입니다.")).not.toBeInTheDocument();
  });
});
