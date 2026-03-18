declare global {
  interface Window {
    gtag: (...args: unknown[]) => void;
    dataLayer: unknown[];
  }
}

export const EVENTS = {
  TAB_VIEW: "tab_view",
  CHAT_SENT: "chat_message_sent",
  VIDEO_PLAY: "video_play",
  VIDEO_DISCONNECT: "video_disconnect",
} as const;

export function trackEvent(
  name: string,
  params?: Record<string, unknown>,
): void {
  if (typeof window === "undefined" || typeof window.gtag !== "function") return;
  window.gtag("event", name, params);
}
