import type { FAQItem } from "../types/kiosk";
import { isKioskFallbackEnabled } from "./kioskFallback";
import { fallbackFAQForCategory } from "./mockKioskData";

export async function fetchFAQ(categoryId: string | null): Promise<FAQItem[]> {
  const url = categoryId
    ? `/api/v1/faq?category=${encodeURIComponent(categoryId)}`
    : "/api/v1/faq";

  try {
    const response = await fetch(url);
    const fallback = fallbackFAQForCategory(categoryId);

    if (!response.ok) {
      warnOnServerError("faq", response.status);
      if (!isKioskFallbackEnabled()) {
        throw new Error(`faq fetch failed: ${response.status}`);
      }
      return fallback;
    }

    const data = (await response.json()) as FAQItem[];
    if (data.length > 0) {
      return data.slice(0, 6);
    }
    return isKioskFallbackEnabled() ? fallback : [];
  } catch (error) {
    if (!isKioskFallbackEnabled()) {
      throw error;
    }
    return fallbackFAQForCategory(categoryId);
  }
}

function warnOnServerError(resource: string, status: number): void {
  if (status >= 500) {
    console.warn(`${resource} fetch failed with server status ${status}; using fallback data.`);
  }
}
