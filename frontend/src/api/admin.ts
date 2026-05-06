export interface AdminStatus {
  documents: number;
  last_crawled: string | null;
}

export interface AdminConflict {
  id: string;
  chunk_a_id?: string;
  chunk_b_id?: string;
  conflict_type?: string;
  severity?: string;
  is_resolved?: boolean;
  summary?: string;
}

export interface AdminLog {
  id: string;
  query?: string;
  answer?: string;
  has_conflict?: boolean;
  response_ms?: number;
  created_at?: string | null;
}

export interface AdminCrawlResult {
  status: string;
}

async function readJson<T>(response: Response, failureMessage: string): Promise<T> {
  if (!response.ok) {
    throw new Error(`${failureMessage}: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchAdminStatus(): Promise<AdminStatus> {
  const response = await fetch("/api/v1/admin/status");

  return readJson<AdminStatus>(response, "admin status fetch failed");
}

export async function triggerAdminCrawl(): Promise<AdminCrawlResult> {
  const response = await fetch("/api/v1/admin/crawl", { method: "POST" });

  return readJson<AdminCrawlResult>(response, "admin crawl failed");
}

export async function fetchAdminConflicts(): Promise<AdminConflict[]> {
  const response = await fetch("/api/v1/admin/conflicts");

  return readJson<AdminConflict[]>(response, "admin conflicts fetch failed");
}

export async function fetchAdminLogs(): Promise<AdminLog[]> {
  const response = await fetch("/api/v1/admin/logs");

  return readJson<AdminLog[]>(response, "admin logs fetch failed");
}
