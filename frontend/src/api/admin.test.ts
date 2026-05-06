import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchAdminConflicts,
  fetchAdminLogs,
  fetchAdminStatus,
  triggerAdminCrawl,
} from "./admin";

describe("admin api", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("fetches the status stub with nullable last_crawled", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ documents: 0, last_crawled: null })),
    );

    await expect(fetchAdminStatus()).resolves.toEqual({
      documents: 0,
      last_crawled: null,
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/admin/status");
  });

  it("triggers crawl with POST and returns the backend status", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "triggered" })),
    );

    await expect(triggerAdminCrawl()).resolves.toEqual({ status: "triggered" });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/admin/crawl", {
      method: "POST",
    });
  });

  it("treats empty conflicts and logs arrays as normal responses", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify([])))
      .mockResolvedValueOnce(new Response(JSON.stringify([])));

    await expect(fetchAdminConflicts()).resolves.toEqual([]);
    await expect(fetchAdminLogs()).resolves.toEqual([]);
  });

  it("throws an error when an admin endpoint fails", async () => {
    fetchMock.mockResolvedValueOnce(new Response("nope", { status: 503 }));

    await expect(fetchAdminStatus()).rejects.toThrow(
      "admin status fetch failed: 503",
    );
  });
});
