import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ko } from "../../../lang/ko";
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
    expect(screen.getByText(ko.source.recent)).toBeInTheDocument();
    expect(screen.getByText(ko.source.stale)).toBeInTheDocument();
  });

  it("does not warn when the same URL appears for different chunks", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <SourceList
        sources={[
          {
            title: "졸업학점 2025",
            url: "https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
            crawled_at: "2026-05-07",
            freshness: "recent",
            chunk_id: "chunk-1",
          },
          {
            title: "졸업학점 2025",
            url: "https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
            crawled_at: "2026-05-07",
            freshness: "recent",
            chunk_id: "chunk-2",
          },
        ]}
      />,
    );

    expect(consoleError).not.toHaveBeenCalledWith(expect.stringContaining("Encountered two children with the same key"));
    consoleError.mockRestore();
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
    expect(screen.getByRole("link", { name: ko.source.openOriginal })).toHaveAttribute("href", "https://example.edu");
    expect(screen.queryByText(/\*\*중요\*\*/)).not.toBeInTheDocument();
  });

  it("renders loading skeleton while sources are pending", () => {
    render(<SourceList isLoading={true} sources={[]} />);

    expect(screen.getByLabelText(ko.source.loadingLabel)).toBeInTheDocument();
    expect(screen.queryByText("표시할 출처 없음")).not.toBeInTheDocument();
  });
});
