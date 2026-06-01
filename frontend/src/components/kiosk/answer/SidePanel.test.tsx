import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SidePanel } from "./SidePanel";

describe("SidePanel", () => {
  it("assembles source list, conflict warning, and action bar", () => {
    render(<SidePanel answer="답변" conflictWarning={null} question="질문" sources={[]} />);

    expect(screen.getByText("답변에 사용된 공식 문서")).toBeInTheDocument();
    expect(screen.getByText("답변에 사용된 공식 문서가 없습니다")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /인쇄/ })).toBeInTheDocument();
  });
});
