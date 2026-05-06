import type { PopularItem } from "../types/kiosk";
import { fallbackPopular } from "./mockKioskData";

export async function fetchPopular(): Promise<PopularItem[]> {
  try {
    const response = await fetch("/api/v1/popular");

    if (!response.ok) {
      warnOnServerError("popular", response.status);
      return fallbackPopular;
    }

    const data = (await response.json()) as PopularItem[];
    return data.length > 0 ? data : fallbackPopular;
  } catch {
    return fallbackPopular;
  }
}

function warnOnServerError(resource: string, status: number): void {
  if (status >= 500) {
    console.warn(`${resource} fetch failed with server status ${status}; using fallback data.`);
  }
}
