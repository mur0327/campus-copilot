import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { FAQItem } from "../../../types/kiosk";
import { FAQGrid } from "./FAQGrid";

const faqs: FAQItem[] = Array.from({ length: 8 }, (_, index) => ({
  id: `faq-${index}`,
  question: `질문 ${index}`,
  category_id: "academic",
}));

describe("FAQGrid", () => {
  it("renders up to six questions and selects the full item", () => {
    const onSelect = vi.fn();
    render(<FAQGrid faqs={faqs} onSelect={onSelect} />);

    expect(screen.getAllByRole("button")).toHaveLength(6);
    fireEvent.click(screen.getByText("질문 1"));

    expect(onSelect).toHaveBeenCalledWith(faqs[1]);
  });
});
