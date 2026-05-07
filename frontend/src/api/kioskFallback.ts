export function isKioskFallbackEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_KIOSK_FALLBACK === "true";
}
