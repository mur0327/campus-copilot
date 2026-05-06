import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InputBar } from "./InputBar";

describe("InputBar", () => {
  it("opens input mode from text area and voice entry", () => {
    const onFocus = vi.fn();
    const onVoice = vi.fn();
    render(<InputBar onFocus={onFocus} onVoice={onVoice} />);

    fireEvent.click(screen.getByRole("button", { name: "궁금한 내용을 입력하세요" }));
    fireEvent.click(screen.getByRole("button", { name: "음성 입력" }));

    expect(onFocus).toHaveBeenCalledTimes(1);
    expect(onVoice).toHaveBeenCalledTimes(1);
  });
});
