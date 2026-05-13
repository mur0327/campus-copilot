import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Source } from "../../../types/kiosk";
import { SourceList } from "./SourceList";

const sources: Source[] = [
  { title: "학사안내", url: "https://example.edu", crawled_at: "2026-04-19", freshness: "recent" },
  { title: "공지사항", url: "https://example.edu/notice", crawled_at: "2025-01-01", freshness: "stale" },
];

describe("SourceList", () => {
  it("renders sources with freshness labels", () => {
    render(<SourceList sources={sources} />);

    expect(screen.getByText("학사안내")).toBeInTheDocument();
    expect(screen.getByText(/최신/)).toBeInTheDocument();
    expect(screen.getByText(/오래됨/)).toBeInTheDocument();
  });

  it("renders markdown syntax in source titles instead of raw markdown markers", () => {
    render(
      <SourceList
        sources={[
          {
            title: "**중요** 공지\n\n- [학사 안내](https://example.edu/guide)",
            url: "https://example.edu",
            crawled_at: "2026-04-19",
            freshness: "recent",
          },
        ]}
      />,
    );

    const emphasized = screen.getByText("중요");
    expect(emphasized.tagName).toBe("STRONG");
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "학사 안내" })).toHaveAttribute("href", "https://example.edu/guide");
    expect(screen.getByRole("link", { name: "원문 열기" })).toHaveAttribute("href", "https://example.edu");
    expect(screen.queryByText(/\*\*중요\*\*/)).not.toBeInTheDocument();
  });

  it("renders loading skeleton while sources are pending", () => {
    render(<SourceList isLoading={true} sources={[]} />);

    expect(screen.getByLabelText("출처를 불러오는 중")).toBeInTheDocument();
    expect(screen.queryByText("표시할 출처 없음")).not.toBeInTheDocument();
  });
});
