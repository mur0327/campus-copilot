import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VirtualKeyboard } from "./VirtualKeyboard";

const keyboardMock = vi.hoisted(() => ({
  setInput: vi.fn(),
}));

vi.mock("react-simple-keyboard", () => ({
  default: ({
    keyboardRef,
    onChange,
    onKeyPress,
  }: {
    keyboardRef: (keyboard: { setInput: typeof keyboardMock.setInput }) => void;
    onChange: (input: string) => void;
    onKeyPress: (button: string) => void;
  }) => {
    keyboardRef({ setInput: keyboardMock.setInput });

    return (
      <div data-testid="virtual-keyboard">
        <button onClick={() => onChange("ㅎㅏㄱ")} type="button">
          assemble
        </button>
        <button onClick={() => onKeyPress("{enter}")} type="button">
          enter
        </button>
      </div>
    );
  },
}));

describe("VirtualKeyboard", () => {
  it("syncs current value into keyboard input", () => {
    render(<VirtualKeyboard onChange={vi.fn()} onSubmit={vi.fn()} value="학" />);

    expect(screen.getByTestId("virtual-keyboard")).toBeInTheDocument();
    expect(keyboardMock.setInput).toHaveBeenCalledWith("ㅎㅏㄱ", "default", true);
  });

  it("assembles Hangul input and submits from enter key only when non-empty", () => {
    const onChange = vi.fn();
    const onSubmit = vi.fn();
    render(<VirtualKeyboard onChange={onChange} onSubmit={onSubmit} value="학" />);

    fireEvent.click(screen.getByText("assemble"));
    fireEvent.click(screen.getByText("enter"));

    expect(onChange).toHaveBeenCalledWith("학");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
