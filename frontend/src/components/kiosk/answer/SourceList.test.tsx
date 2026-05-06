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
});
