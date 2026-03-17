/**
 * Typed fetch wrappers for the FastAPI backend.
 * All functions throw a descriptive Error on non-2xx responses.
 */

import type { AskResponse, HistoryMessage, SessionResponse } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SESSION_STORAGE_KEY = "aicv_session_id";

/** Tab-scoped session ID — persisted in localStorage so refreshes reuse the same backend session. */
export let sessionId = "";

export function initSessionId(): string {
  if (typeof window === "undefined") return "";
  const stored = localStorage.getItem(SESSION_STORAGE_KEY);
  if (stored) {
    sessionId = stored;
  } else {
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }
  return sessionId;
}

export function resetSessionId(): string {
  sessionId = crypto.randomUUID();
  if (typeof window !== "undefined") {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }
  return sessionId;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore JSON parse errors on error responses
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

/**
 * POST /ask
 * Sends a question to the RAG pipeline and returns the grounded answer.
 */
export async function askQuestion(
  question: string,
  history: HistoryMessage[] = [],
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-ID": sessionId },
    body: JSON.stringify({ question, history }),
  });
  return handleResponse<AskResponse>(res);
}

/**
 * POST /ask/stream
 * Streams the answer token-by-token via SSE.
 * Calls onToken for each token, onDone(latencyMs) when complete.
 */
export async function askQuestionStream(
  question: string,
  history: HistoryMessage[],
  onToken: (token: string) => void,
  onDone: (latencyMs: number) => void,
  onError: (msg: string) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-ID": sessionId },
    body: JSON.stringify({ question, history }),
  });
  if (!res.ok || !res.body) {
    let detail = `HTTP ${res.status}`;
    try { const b = await res.json(); detail = b?.detail ?? detail; } catch { /* ignore */ }
    onError(detail);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload.startsWith("[DONE]")) {
        const ms = parseInt(payload.slice(7), 10);
        onDone(isNaN(ms) ? 0 : ms);
      } else if (payload.startsWith("[ERROR]")) {
        try { onError(JSON.parse(payload.slice(8))); } catch { onError(payload); }
      } else {
        try { onToken(JSON.parse(payload)); } catch { onToken(payload); }
      }
    }
  }
}

/**
 * GET /session
 * Fetches a LiveAvatar WebRTC session (real or mock depending on server config).
 */
export async function getSession(): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE_URL}/session`, {
    headers: { "X-Session-ID": sessionId },
  });
  return handleResponse<SessionResponse>(res);
}

/**
 * POST /speak
 * Queues TTS synthesis and sends the audio to the active LiveAvatar session.
 */
export async function speakText(text: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-ID": sessionId },
    body: JSON.stringify({ text }),
  });
  await handleResponse<{ status: string }>(res);
}

/**
 * POST /interrupt
 * Signals the backend to stop the avatar's current speech immediately.
 */
export async function interruptSpeech(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/interrupt`, {
    method: "POST",
    headers: { "X-Session-ID": sessionId },
  });
  await handleResponse<{ status: string }>(res);
}

/**
 * GET /ping
 * Lightweight warmup call — wakes a cold-started container with no side-effects.
 */
export async function ping(): Promise<void> {
  await fetch(`${API_BASE_URL}/ping`).catch(() => {});
}

/**
 * GET /health
 * Returns the backend health status object.
 */
export async function getHealth(): Promise<Record<string, string>> {
  const res = await fetch(`${API_BASE_URL}/health`);
  return handleResponse<Record<string, string>>(res);
}
