import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PopularItem } from "../../../types/kiosk";
import { PopularList } from "./PopularList";

const items: PopularItem[] = [
  { rank: 1, question: "등록금 납부 기간은?", view_count: 312 },
];

describe("PopularList", () => {
  it("renders popular question rows and selects question text", () => {
    const onSelect = vi.fn();
    render(<PopularList items={items} onSelect={onSelect} />);

    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("등록금 납부 기간은?")).toBeInTheDocument();
    expect(screen.getByText("312회")).toBeInTheDocument();

    fireEvent.click(screen.getByText("등록금 납부 기간은?"));
    expect(onSelect).toHaveBeenCalledWith("등록금 납부 기간은?");
  });
});
