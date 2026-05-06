import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchCategories } from "./categories";
import { fetchFAQ } from "./faq";
import { fetchPopular } from "./popular";
import { postChat } from "./chat";
import type { Category, FAQItem, PopularItem } from "../types/kiosk";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("kiosk API adapters", () => {
  it("returns categories from GET /api/v1/categories when present", async () => {
    const categories: Category[] = [{ id: "academic", name: "학사행정" }];
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => categories,
    } as Response);

    await expect(fetchCategories()).resolves.toEqual(categories);
    expect(fetch).toHaveBeenCalledWith("/api/v1/categories");
  });

  it("falls back for categories on empty response, 404, and network failure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] } as Response);
    await expect(fetchCategories()).resolves.not.toEqual([]);

    fetchMock.mockResolvedValueOnce({ ok: false, status: 404 } as Response);
    await expect(fetchCategories()).resolves.not.toEqual([]);

    fetchMock.mockRejectedValueOnce(new Error("network"));
    await expect(fetchCategories()).resolves.not.toEqual([]);
  });

  it("logs a visible server warning before falling back on 500 categories response", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 500 } as Response);

    await expect(fetchCategories()).resolves.not.toEqual([]);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("categories"));
  });

  it("requests FAQ with an encoded category and returns API data when present", async () => {
    const faqs: FAQItem[] = [{ id: "faq-1", question: "휴학 신청?", category_id: "academic" }];
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => faqs,
    } as Response);

    await expect(fetchFAQ("장학 등록")).resolves.toEqual(faqs);
    expect(fetch).toHaveBeenCalledWith("/api/v1/faq?category=%EC%9E%A5%ED%95%99%20%EB%93%B1%EB%A1%9D");
  });

  it("limits API FAQ data to six items for the fixed kiosk grid", async () => {
    const faqs: FAQItem[] = Array.from({ length: 7 }, (_, index) => ({
      id: `faq-${index}`,
      question: `질문 ${index}`,
      category_id: "academic",
    }));
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => faqs,
    } as Response);

    await expect(fetchFAQ(null)).resolves.toHaveLength(6);
  });

  it("returns category-filtered FAQ fallback on empty response, 404, and network failure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] } as Response);
    const emptyFallback = await fetchFAQ("academic");
    expect(emptyFallback.length).toBeGreaterThan(0);
    expect(emptyFallback.every((item) => item.category_id === "academic")).toBe(true);

    fetchMock.mockResolvedValueOnce({ ok: false, status: 404 } as Response);
    await expect(fetchFAQ(null)).resolves.not.toEqual([]);

    fetchMock.mockRejectedValueOnce(new Error("network"));
    await expect(fetchFAQ("academic")).resolves.not.toEqual([]);
  });

  it("requests popular questions and falls back on empty response or 404", async () => {
    const popular: PopularItem[] = [{ rank: 1, question: "등록금 납부 기간?", view_count: 10 }];
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => popular } as Response);
    await expect(fetchPopular()).resolves.toEqual(popular);
    expect(fetch).toHaveBeenCalledWith("/api/v1/popular");

    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => [] } as Response);
    await expect(fetchPopular()).resolves.not.toEqual([]);

    fetchMock.mockResolvedValueOnce({ ok: false, status: 404 } as Response);
    await expect(fetchPopular()).resolves.not.toEqual([]);
  });

  it("posts JSON chat payload to POST /api/v1/chat", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        answer: "stub",
        sources: [],
        procedure_steps: [],
        conflict_warning: { exists: false },
        freshness: "recent",
      }),
    } as Response);

    await postChat({ question: "휴학 신청" });

    expect(fetch).toHaveBeenCalledWith("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "휴학 신청" }),
    });
  });
});
