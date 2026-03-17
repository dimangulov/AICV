"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import {
  Mic,
  MicOff,
  Send,
  Loader2,
  ChevronRight,
  Zap,
  Radio,
} from "lucide-react";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { askQuestionStream, interruptSpeech } from "@/lib/api";
import type { LogEntry, ConversationMessage, HistoryMessage } from "@/types";

interface ChatInterfaceProps {
  onLog: (message: string, level?: LogEntry["level"], step?: number) => void;
}

let _msgId = 0;

export default function ChatInterface({ onLog }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<ConversationMessage[]>([]);
    const [streamingText, setStreamingText] = useState("");   // assistant bubble being built
    const [textInput, setTextInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const threadRef = useRef<HTMLDivElement>(null);
    // Ref-based guard — unlike isLoading state, this is never stale inside callbacks
    const isSubmittingRef = useRef(false);
    // Mirror of messages for synchronous reads outside state updaters
    const messagesRef = useRef<ConversationMessage[]>([]);

    // Keep a stable ref to the latest handleQuestion to break the stale closure in onResult
    const handleQuestionRef = useRef<(q: string) => void>(() => {});

    const {
      isListening,
      interimTranscript,
      isSupported,
      startListening,
      stopListening,
    } = useSpeechRecognition({

      onResult: useCallback(
        (text: string) => {
          onLog(`Listening — captured: "${text}"`, "success", 1);
          handleQuestionRef.current(text);
        },
        [onLog],
      ),
      onSpeechStart: useCallback(() => {
        interruptSpeech().catch(() => {});
      }, []),
      onError: (err) => onLog(`Speech recognition error: ${err}`, "error"),
    });

    // Auto-scroll on new messages / streaming update
    useEffect(() => {
      const el = threadRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    }, [messages, streamingText]);

    // Keep messagesRef in sync for synchronous reads in handleQuestion
    useEffect(() => { messagesRef.current = messages; }, [messages]);

    /** Derive last-N history for backend context. */
    const buildHistory = (msgs: ConversationMessage[]): HistoryMessage[] =>
      msgs
        .slice(-6) // last 3 turns (user + assistant pairs)
        .map((m) => ({ role: m.role, content: m.text }));

    const handleQuestion = useCallback(
      async (question: string) => {
        const trimmed = question.trim();
        if (!trimmed || isSubmittingRef.current) return;
        isSubmittingRef.current = true;

        // Interrupt avatar immediately whenever a question is submitted.
        interruptSpeech().catch(() => {});

        setIsLoading(true);
        setStreamingText("");

        // Snapshot history synchronously from current messages before appending
        // the user bubble (functional updater would run during render — forbidden).
        setMessages((prev) => {
          // Only append — no side-effects here.
          const userMsg: ConversationMessage = {
            id: String(++_msgId),
            role: "user",
            text: trimmed,
          };
          return [...prev, userMsg];
        });

        // Build history from current messages (pre-append snapshot via functional read)
        // We need messages as they are right now; use a ref snapshot instead.
        const history = buildHistory(messagesRef.current);

        // Kick off async work fully outside any state updater
        (async () => {
            onLog(`Question: "${trimmed}"`, "info", 1);
            onLog("RAG Retrieval — searching CV knowledge base…", "info", 2);
            onLog("Streaming response…", "info", 3);

            let fullAnswer = "";
            let latencyMs = 0;

            try {
              await askQuestionStream(
                trimmed,
                history,
                (token) => {
                  fullAnswer += token;
                  setStreamingText(fullAnswer);
                },
                (ms) => {
                  latencyMs = ms;
                  onLog(`Response complete — ${ms}ms ✓`, "success", 4);
                },
                (msg) => {
                  fullAnswer = `⚠ Error: ${msg}`;
                  onLog(`Error: ${msg}`, "error", 0);
                },
              );
            } catch (err) {
              const msg = err instanceof Error ? err.message : "Request failed";
              fullAnswer = `⚠ Error: ${msg}`;
              onLog(`Error: ${msg}`, "error", 0);
            }

            const assistantMsg: ConversationMessage = {
              id: String(++_msgId),
              role: "assistant",
              text: fullAnswer,
              latency_ms: latencyMs,
            };
            setMessages((cur) => [...cur, assistantMsg]);
            setStreamingText("");
            setIsLoading(false);
            isSubmittingRef.current = false;
        })();
      },
      [onLog],
    );

    // Keep handleQuestionRef in sync so onResult always calls the latest version
    useEffect(() => { handleQuestionRef.current = handleQuestion; }, [handleQuestion]);

    const handleTextSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      if (textInput.trim()) {
        handleQuestion(textInput);
        setTextInput("");
      }
    };

    const isEmpty = messages.length === 0 && !streamingText;

    return (
      <div className="flex flex-col h-full min-h-0 gap-0">

        {/* ── Message thread ──────────────────────────────────────────────── */}
        <div
          ref={threadRef}
          className="flex-1 overflow-y-auto px-1 py-2 flex flex-col gap-3 min-h-[180px] max-h-[40vh] lg:max-h-none"
        >
          {isEmpty ? (
            /* Suggested questions shown when thread is empty */
            <div className="py-2">
              <p className="text-xs text-gray-500 mb-2">Try asking:</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleQuestion(q)}
                    className="flex items-center gap-1 text-xs bg-gray-800/80 hover:bg-gray-700
                      border border-gray-700 hover:border-gray-600 text-gray-300
                      px-3 py-1.5 rounded-full transition-all active:scale-95"
                  >
                    <ChevronRight className="w-3 h-3 text-blue-400 flex-shrink-0" />
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed
                      ${msg.role === "user"
                        ? "bg-blue-600 text-white rounded-br-sm"
                        : "bg-gray-800 border border-gray-700 text-gray-200 rounded-bl-sm"
                      }`}
                  >
                    {msg.text}
                    {msg.role === "assistant" && msg.latency_ms !== undefined && (
                      <span className="ml-2 text-xs text-gray-500 inline-flex items-center gap-0.5">
                        <Zap className="w-2.5 h-2.5" />{msg.latency_ms}ms
                      </span>
                    )}
                  </div>
                </div>
              ))}

              {/* Streaming assistant bubble */}
              {streamingText && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-bl-sm text-sm
                    leading-relaxed bg-gray-800 border border-gray-700 text-gray-200">
                    {streamingText}
                    <span className="inline-block w-1 h-3.5 ml-0.5 bg-blue-400 animate-pulse align-middle" />
                  </div>
                </div>
              )}

              {/* Thinking indicator (before first token) */}
              {isLoading && !streamingText && (
                <div className="flex justify-start">
                  <div className="px-3.5 py-2.5 rounded-2xl rounded-bl-sm bg-gray-800 border border-gray-700">
                    <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* ── Interim transcript chip ─────────────────────────────────────── */}
        {interimTranscript && (
          <div className="px-1 py-1">
            <span className="inline-flex items-center gap-1.5 text-xs text-blue-300
              bg-blue-950/60 border border-blue-800/50 px-3 py-1 rounded-full animate-pulse">
              <Radio className="w-3 h-3" />
              {interimTranscript}
            </span>
          </div>
        )}

        {/* ── Input bar ───────────────────────────────────────────────────── */}
        <div className="pt-2 border-t border-gray-800 flex items-center gap-2">

          {/* Mic toggle — press to talk */}
          {isSupported && (
            <button
              onClick={() => {
                if (isListening) {
                  stopListening();
                } else {
                  interruptSpeech().catch(() => {});
                  startListening();
                }
              }}
              disabled={isLoading}
              aria-label={isListening ? "Stop recording" : "Press to speak"}
              title={isListening ? "Stop recording" : isLoading ? "Processing…" : "Press to speak"}
              className={`relative flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center
                transition-all duration-200
                ${isListening
                  ? "bg-red-500/20 border border-red-500/60 text-red-400"
                  : isLoading
                    ? "bg-gray-800 border border-gray-700 text-gray-600 opacity-50 cursor-not-allowed"
                    : "bg-gray-800 border border-gray-700 text-gray-400 hover:border-gray-500"
                }`}
            >
              {isListening
                ? <Mic className="w-4 h-4" />
                : <MicOff className="w-4 h-4" />
              }
              {isListening && (
                <span className="absolute inset-0 rounded-full border border-red-400/50 animate-ping" />
              )}
            </button>
          )}

          {/* Text input */}
          <form onSubmit={handleTextSubmit} className="flex-1 flex gap-2">
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onFocus={() => interruptSpeech().catch(() => {})}
              placeholder="Ask Damir anything…"
              disabled={isLoading}
              aria-label="Type your question"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                text-sm text-gray-100 placeholder-gray-500
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            />
            <button
              type="submit"
              disabled={isLoading || !textInput.trim()}
              aria-label="Send"
              className="flex-shrink-0 flex items-center justify-center w-9 h-9 bg-blue-600
                hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
                text-white rounded-lg transition-colors"
            >
              {isLoading
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Send className="w-4 h-4" />
              }
            </button>
          </form>
        </div>

        {/* Status line */}
        {isListening && !interimTranscript && (
          <p className="text-xs text-gray-500 text-center pt-1 animate-pulse">Listening…</p>
        )}
      </div>
    );
}

const SUGGESTED_QUESTIONS = [
  "AI CV project",
  "What cloud platforms do you specialise in?",
  "Tell me about your AI/ML projects",
  "Describe your backend stack",
  "What is the most impactful project you delivered?",
  "How do you approach system scalability?",
  "Walk me through your DevOps practices",
];


