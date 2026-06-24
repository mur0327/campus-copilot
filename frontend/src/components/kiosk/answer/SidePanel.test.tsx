import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ko } from "../../../lang/ko";
import { SidePanel } from "./SidePanel";

describe("SidePanel", () => {
  it("assembles source list, conflict warning, and action bar", () => {
    render(<SidePanel answer="답변" conflictWarning={null} question="질문" sources={[]} />);

    expect(screen.getByText(ko.source.title)).toBeInTheDocument();
    expect(screen.getByText(ko.source.empty)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: ko.action.print })).toBeInTheDocument();
  });
});
