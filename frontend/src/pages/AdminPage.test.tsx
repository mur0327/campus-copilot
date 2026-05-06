import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AdminPage from "./AdminPage";

function renderAdminPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AdminPage />
    </QueryClientProvider>,
  );
}

describe("AdminPage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders the status stub and normal empty states", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              documents: 0,
              chunks: 0,
              indexed_chunks: 0,
              last_crawled: null,
              latest_crawl_job: null,
            }),
          ),
        );
      }

      if (url.endsWith("/conflicts") || url.endsWith("/logs")) {
        return Promise.resolve(new Response(JSON.stringify([])));
      }

      return Promise.resolve(new Response("not found", { status: 404 }));
    });

    renderAdminPage();

    expect(await screen.findByText("0")).toBeInTheDocument();
    expect(screen.getByText("아직 수집 기록 없음")).toBeInTheDocument();
    expect(screen.getByText("크롤링 기록 없음")).toBeInTheDocument();
    expect(screen.getByText("표시할 충돌 없음")).toBeInTheDocument();
    expect(screen.getByText("표시할 로그 없음")).toBeInTheDocument();
  });

  it("shows the latest crawl job state and counts", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              documents: 12,
              chunks: 34,
              indexed_chunks: 20,
              last_crawled: null,
              latest_crawl_job: {
                id: "00000000-0000-0000-0000-000000000201",
                status: "running",
                pages_crawled: 42,
                pages_changed: 7,
                total_pages: 50,
                processed_pages: 42,
                current_stage: "문서 수집 중",
                conflicts_found: 1,
                started_at: "2026-05-06T13:06:13Z",
                completed_at: null,
                error: null,
              },
            }),
          ),
        );
      }

      if (url.endsWith("/conflicts") || url.endsWith("/logs")) {
        return Promise.resolve(new Response(JSON.stringify([])));
      }

      return Promise.resolve(new Response("not found", { status: 404 }));
    });

    renderAdminPage();

    expect(await screen.findByText("크롤링 진행 중")).toBeInTheDocument();
    expect(screen.getByText("42건 수집 · 7건 변경 · 1건 충돌")).toBeInTheDocument();
    expect(screen.getByText("문서 수집 중")).toBeInTheDocument();
    expect(screen.getByText("42/50 페이지 · 84%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "크롤링 진행률" })).toHaveAttribute(
      "aria-valuenow",
      "84",
    );
  });

  it("disables crawl while pending and shows success after trigger", async () => {
    let resolveCrawl: (response: Response) => void = () => {};
    const crawlPromise = new Promise<Response>((resolve) => {
      resolveCrawl = resolve;
    });

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              documents: 0,
              chunks: 0,
              indexed_chunks: 0,
              last_crawled: null,
              latest_crawl_job: null,
            }),
          ),
        );
      }

      if (url.endsWith("/conflicts") || url.endsWith("/logs")) {
        return Promise.resolve(new Response(JSON.stringify([])));
      }

      if (url.endsWith("/crawl")) {
        return crawlPromise;
      }

      return Promise.resolve(new Response("not found", { status: 404 }));
    });

    const user = userEvent.setup();
    renderAdminPage();

    const button = await screen.findByRole("button", {
      name: "수동 크롤링 요청",
    });

    await user.click(button);

    expect(button).toBeDisabled();
    expect(screen.getByText("요청 중")).toBeInTheDocument();

    resolveCrawl(new Response(JSON.stringify({ status: "triggered" })));

    expect(
      await screen.findByText("크롤링 작업이 시작되었습니다. 수집 상태가 자동으로 갱신됩니다."),
    ).toBeInTheDocument();
    expect(button).toBeEnabled();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/v1/admin/crawl", {
        method: "POST",
      });
    });
  });

  it("keeps other panels visible when one admin query fails", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/status")) {
        return Promise.resolve(new Response("broken", { status: 500 }));
      }

      if (url.endsWith("/conflicts") || url.endsWith("/logs")) {
        return Promise.resolve(new Response(JSON.stringify([])));
      }

      return Promise.resolve(new Response("not found", { status: 404 }));
    });

    renderAdminPage();

    expect(
      await screen.findByText("상태를 불러오지 못했습니다."),
    ).toBeInTheDocument();
    expect(screen.getByText("표시할 충돌 없음")).toBeInTheDocument();
    expect(screen.getByText("표시할 로그 없음")).toBeInTheDocument();
  });

  it("shows conflict errors inside the conflict panel", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              documents: 0,
              chunks: 0,
              indexed_chunks: 0,
              last_crawled: null,
              latest_crawl_job: null,
            }),
          ),
        );
      }

      if (url.endsWith("/conflicts")) {
        return Promise.resolve(new Response("broken", { status: 500 }));
      }

      if (url.endsWith("/logs")) {
        return Promise.resolve(new Response(JSON.stringify([])));
      }

      return Promise.resolve(new Response("not found", { status: 404 }));
    });

    renderAdminPage();

    expect(
      await screen.findByText("충돌 목록을 불러오지 못했습니다."),
    ).toBeInTheDocument();
    expect(screen.getByText("아직 수집 기록 없음")).toBeInTheDocument();
    expect(screen.getByText("표시할 로그 없음")).toBeInTheDocument();
  });

  it("shows log errors inside the log panel", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith("/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              documents: 0,
              chunks: 0,
              indexed_chunks: 0,
              last_crawled: null,
              latest_crawl_job: null,
            }),
          ),
        );
      }

      if (url.endsWith("/conflicts")) {
        return Promise.resolve(new Response(JSON.stringify([])));
      }

      if (url.endsWith("/logs")) {
        return Promise.resolve(new Response("broken", { status: 500 }));
      }

      return Promise.resolve(new Response("not found", { status: 404 }));
    });

    renderAdminPage();

    expect(
      await screen.findByText("로그를 불러오지 못했습니다."),
    ).toBeInTheDocument();
    expect(screen.getByText("아직 수집 기록 없음")).toBeInTheDocument();
    expect(screen.getByText("표시할 충돌 없음")).toBeInTheDocument();
  });
});
