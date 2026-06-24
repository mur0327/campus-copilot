import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ko } from "../../../lang/ko";
import { AnswerSidebar } from "./AnswerSidebar";

describe("AnswerSidebar", () => {
  it("assembles procedure steps, source list, conflict warning, and action bar", () => {
    render(<AnswerSidebar answer="답변" conflictWarning={null} procedureSteps={[]} question="질문" sources={[]} />);

    expect(screen.getByText(ko.procedure.title)).toBeInTheDocument();
    expect(screen.getByText(ko.source.title)).toBeInTheDocument();
    expect(screen.getByText(ko.source.empty)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: ko.action.print })).toBeInTheDocument();
  });
});
