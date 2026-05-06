import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerText } from "./AnswerText";

describe("AnswerText", () => {
  it("renders answer and streaming cursor", () => {
    render(<AnswerText isStreaming={true} text="답변" />);

    expect(screen.getByText("답변")).toBeInTheDocument();
    expect(screen.getByTestId("streaming-cursor")).toBeInTheDocument();
  });
});
