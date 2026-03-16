// Shared TypeScript interfaces used across components and the API layer.

export interface LogEntry {
  /** Unique monotonically-increasing string ID */
  id: string;
  /** Time the event was recorded */
  timestamp: Date;
  /** Visual severity level */
  level: "info" | "success" | "warning" | "error";
  /**
   * Step number in the interaction pipeline (0 = no step label).
   * 1 = Listening, 2 = RAG Retrieval, 3 = Inference, 4 = Response ready
   */
  step: number;
  /** Human-readable log message */
  message: string;
}

/** One turn of conversation history sent to the backend. */
export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

/** One displayed message in the chat thread. */
export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  latency_ms?: number;
}

export interface AskRequest {
  question: string;
  history?: HistoryMessage[];
}

export interface AskResponse {
  answer: string;
  sources: string[];
  latency_ms: number;
}

export interface SessionResponse {
  /** LiveAvatar session identifier */
  session_id: string;
  /** LiveKit server WebSocket URL — pass to livekit-client Room.connect() */
  livekit_url: string;
  /** LiveKit room access token for this client */
  livekit_client_token: string;
}
