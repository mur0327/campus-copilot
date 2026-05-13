import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActionBar } from "./ActionBar";

describe("ActionBar", () => {
  it("renders print, QR, and future TTS entry actions", () => {
    render(<ActionBar answer="답변" question="질문" sources={[]} />);

    expect(screen.getByRole("button", { name: /인쇄/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /QR/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /읽기 예정/ })).toBeInTheDocument();
  });
});
