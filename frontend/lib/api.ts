/**
 * Typed fetch wrappers for the FastAPI backend.
 * All functions throw a descriptive Error on non-2xx responses.
 */

import type { AskResponse, SessionResponse } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
export async function askQuestion(question: string): Promise<AskResponse> {
  const res = await fetch(`${API_BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return handleResponse<AskResponse>(res);
}

/**
 * GET /session
 * Fetches a LiveAvatar WebRTC session (real or mock depending on server config).
 */
export async function getSession(): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE_URL}/session`);
  return handleResponse<SessionResponse>(res);
}

/**
 * GET /health
 * Returns the backend health status object.
 */
export async function getHealth(): Promise<Record<string, string>> {
  const res = await fetch(`${API_BASE_URL}/health`);
  return handleResponse<Record<string, string>>(res);
}
