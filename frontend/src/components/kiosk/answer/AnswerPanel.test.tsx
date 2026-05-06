import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerPanel } from "./AnswerPanel";

describe("AnswerPanel", () => {
  it("assembles answer text and procedure steps", () => {
    render(<AnswerPanel answer="답변 내용" isStreaming={false} procedureSteps={["1단계"]} />);

    expect(screen.getByText("답변 내용")).toBeInTheDocument();
    expect(screen.getByText("1단계")).toBeInTheDocument();
  });
});
