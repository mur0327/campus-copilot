import type { Category } from "../types/kiosk";
import { fallbackCategories } from "./mockKioskData";

export async function fetchCategories(): Promise<Category[]> {
  try {
    const response = await fetch("/api/v1/categories");

    if (!response.ok) {
      warnOnServerError("categories", response.status);
      return fallbackCategories;
    }

    const data = (await response.json()) as Category[];
    return data.length > 0 ? data : fallbackCategories;
  } catch {
    return fallbackCategories;
  }
}

function warnOnServerError(resource: string, status: number): void {
  if (status >= 500) {
    console.warn(`${resource} fetch failed with server status ${status}; using fallback data.`);
  }
}
