import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Category } from "../../../types/kiosk";
import { CategoryBar } from "./CategoryBar";

const categories: Category[] = [
  { id: "academic", name: "학사행정" },
  { id: "scholarship", name: "장학" },
];

describe("CategoryBar", () => {
  it("renders all categories and selects values", () => {
    const onSelect = vi.fn();
    render(<CategoryBar categories={categories} onSelect={onSelect} selectedCategory={null} />);

    expect(screen.getByRole("button", { name: "전체" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByText("학사행정"));
    fireEvent.click(screen.getByText("전체"));

    expect(onSelect).toHaveBeenCalledWith("academic");
    expect(onSelect).toHaveBeenCalledWith(null);
  });
});
