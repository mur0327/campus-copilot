import type { PopularItem } from "../types/kiosk";
import { isKioskFallbackEnabled } from "./kioskFallback";
import { fallbackPopular } from "./mockKioskData";

export async function fetchPopular(): Promise<PopularItem[]> {
  try {
    const response = await fetch("/api/v1/popular");

    if (!response.ok) {
      warnOnServerError("popular", response.status);
      if (!isKioskFallbackEnabled()) {
        throw new Error(`popular fetch failed: ${response.status}`);
      }
      return fallbackPopular;
    }

    const data = (await response.json()) as PopularItem[];
    return data.length > 0 || !isKioskFallbackEnabled() ? data : fallbackPopular;
  } catch (error) {
    if (!isKioskFallbackEnabled()) {
      throw error;
    }
    return fallbackPopular;
  }
}

function warnOnServerError(resource: string, status: number): void {
  if (status >= 500) {
    console.warn(`${resource} fetch failed with server status ${status}; using fallback data.`);
  }
}
