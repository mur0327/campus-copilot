import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SearchBar } from "./SearchBar";

describe("SearchBar", () => {
  it("handles back, voice, text changes, and non-empty submit", () => {
    const onBack = vi.fn();
    const onVoice = vi.fn();
    const onChange = vi.fn();
    const onSubmit = vi.fn();
    render(<SearchBar onBack={onBack} onChange={onChange} onSubmit={onSubmit} onVoice={onVoice} value="휴학" />);

    fireEvent.click(screen.getByRole("button", { name: "뒤로" }));
    fireEvent.click(screen.getByRole("button", { name: "음성 입력" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "등록" } });
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

    expect(onBack).toHaveBeenCalledTimes(1);
    expect(onVoice).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("등록");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
