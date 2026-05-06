import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QuestionBar } from "./QuestionBar";

describe("QuestionBar", () => {
  it("renders question and home action", () => {
    const onHome = vi.fn();
    render(<QuestionBar onHome={onHome} question="휴학 신청 방법" />);

    expect(screen.getByText("휴학 신청 방법")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /처음으로/ }));
    expect(onHome).toHaveBeenCalledTimes(1);
  });
});
