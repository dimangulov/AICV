"use client";

import { useState, useCallback } from "react";
import {
  Mic,
  MicOff,
  Send,
  Loader2,
  MessageSquare,
  ChevronRight,
  Zap,
} from "lucide-react";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { askQuestion } from "@/lib/api";
import type { LogEntry } from "@/types";

interface ChatInterfaceProps {
  onLog: (message: string, level?: LogEntry["level"], step?: number) => void;
  /** Called with each RAG answer so the avatar can speak it. */
  onAnswer?: (text: string) => void;
}

export default function ChatInterface({ onLog, onAnswer }: ChatInterfaceProps) {
  const [textInput, setTextInput] = useState("");
  const [answer, setAnswer] = useState("");
  const [latency, setLatency] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleQuestion = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isLoading) return;

      setIsLoading(true);
      setAnswer("");
      setLatency(null);

      onLog(`Step 1: Question received — "${trimmed}"`, "info", 1);

      try {
        onLog("Step 2: RAG Retrieval — searching CV knowledge base…", "info", 2);
        // Short artificial delay so the log is visible before the network round-trip
        // resolves. In production this would be a streaming SSE response.
        await delay(80);

        onLog("Step 3: Ollama Inference — generating response with llama3.2…", "info", 3);

        const result = await askQuestion(trimmed);

        setAnswer(result.answer);
        setLatency(result.latency_ms);
        onAnswer?.(result.answer);
        onLog(
          `Step 4: Response ready — ${result.latency_ms}ms ✓`,
          "success",
          4,
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Request failed";
        setAnswer(`⚠ Error: ${msg}`);
        onLog(`Error: ${msg}`, "error", 0);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, onLog],
  );

  const { isListening, startListening, stopListening, transcript, isSupported } =
    useSpeechRecognition({
      onResult: (text) => {
        onLog(`Step 1: Listening — captured: "${text}"`, "success", 1);
        handleQuestion(text);
      },
      onError: (err) => onLog(`Speech recognition error: ${err}`, "error"),
    });

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (textInput.trim()) {
      handleQuestion(textInput);
      setTextInput("");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* ── Push to Talk ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        {isSupported ? (
          <button
            onMouseDown={startListening}
            onMouseUp={stopListening}
            onTouchStart={(e) => {
              e.preventDefault();
              startListening();
            }}
            onTouchEnd={(e) => {
              e.preventDefault();
              stopListening();
            }}
            aria-label={isListening ? "Release to send" : "Hold to speak"}
            className={`
              flex items-center gap-2 px-5 py-2.5 rounded-full font-semibold
              text-sm transition-all duration-150 select-none touch-none
              ${
                isListening
                  ? "bg-red-500 text-white shadow-lg shadow-red-500/30 scale-105"
                  : "bg-blue-600 hover:bg-blue-700 active:scale-95 text-white shadow-lg shadow-blue-500/20"
              }
            `}
          >
            {isListening ? (
              <MicOff className="w-4 h-4" />
            ) : (
              <Mic className="w-4 h-4" />
            )}
            {isListening ? "Release to Send" : "Push to Talk"}
          </button>
        ) : (
          <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-800/50 px-3 py-2 rounded-full">
            <MicOff className="w-3 h-3" />
            Speech input requires Chrome or Edge
          </div>
        )}

        {isListening && (
          <span className="flex items-center gap-1.5 text-xs text-red-400 animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400 inline-block" />
            Recording…
          </span>
        )}
        {transcript && !isListening && (
          <span className="text-xs text-gray-400 italic truncate max-w-xs">
            "{transcript}"
          </span>
        )}
      </div>

      {/* ── Text input ───────────────────────────────────────────────────── */}
      <form onSubmit={handleTextSubmit} className="flex gap-2">
        <input
          type="text"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          placeholder="Or type a question about Alex…"
          disabled={isLoading}
          aria-label="Type your question"
          className="
            flex-1 bg-gray-800 border border-gray-700 rounded-lg
            px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
            disabled:opacity-60 disabled:cursor-not-allowed transition-colors
          "
        />
        <button
          type="submit"
          disabled={isLoading || !textInput.trim()}
          aria-label="Send question"
          className="
            flex items-center justify-center px-4 py-2.5 bg-blue-600
            hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed
            text-white rounded-lg transition-colors
          "
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </form>

      {/* ── Response display ─────────────────────────────────────────────── */}
      {(isLoading || answer) && (
        <div className="glass-card p-4 animate-fade-in">
          <div className="flex items-center gap-2 mb-2">
            <MessageSquare className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-xs text-blue-400 font-medium">
              DI responds
            </span>
            {latency !== null && (
              <span className="ml-auto flex items-center gap-1 text-xs text-gray-500">
                <Zap className="w-3 h-3" />
                {latency}ms
              </span>
            )}
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 text-gray-400">
              <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
              <span className="text-sm">Thinking…</span>
            </div>
          ) : (
            <p className="text-gray-200 text-sm leading-relaxed">{answer}</p>
          )}
        </div>
      )}

      {/* ── Suggested questions ──────────────────────────────────────────── */}
      {!answer && !isLoading && (
        <div>
          <p className="text-xs text-gray-500 mb-2">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleQuestion(q)}
                className="
                  flex items-center gap-1 text-xs
                  bg-gray-800/80 hover:bg-gray-700 active:scale-95
                  border border-gray-700 hover:border-gray-600
                  text-gray-300 px-3 py-1.5 rounded-full transition-all
                "
              >
                <ChevronRight className="w-3 h-3 text-blue-400 flex-shrink-0" />
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const SUGGESTED_QUESTIONS = [
  "What cloud platforms do you specialise in?",
  "Tell me about your AI/ML projects",
  "Describe your leadership experience",
  "What is the most impactful project you delivered?",
  "What certifications do you hold?",
  "How did you reduce infrastructure costs at TechNova?",
];

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
