import type { Category } from "../types/kiosk";
import { isKioskFallbackEnabled } from "./kioskFallback";
import { fallbackCategories } from "./mockKioskData";

export async function fetchCategories(): Promise<Category[]> {
  try {
    const response = await fetch("/api/v1/categories");

    if (!response.ok) {
      warnOnServerError("categories", response.status);
      if (!isKioskFallbackEnabled()) {
        throw new Error(`categories fetch failed: ${response.status}`);
      }
      return fallbackCategories;
    }

    const data = (await response.json()) as Category[];
    if (data.length > 0) {
      return data;
    }
    if (!isKioskFallbackEnabled()) {
      throw new Error("categories response was empty");
    }
    return fallbackCategories;
  } catch (error) {
    if (!isKioskFallbackEnabled()) {
      throw error;
    }
    return fallbackCategories;
  }
}

function warnOnServerError(resource: string, status: number): void {
  if (status >= 500) {
    console.warn(`${resource} fetch failed with server status ${status}; using fallback data.`);
  }
}
