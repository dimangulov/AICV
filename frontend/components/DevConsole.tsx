"use client";

import { useState, useRef, useEffect } from "react";
import { Terminal, ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import type { LogEntry } from "@/types";

interface DevConsoleProps {
  logs: LogEntry[];
}

const LEVEL_CONFIG: Record<
  LogEntry["level"],
  { dotClass: string; labelClass: string; label: string }
> = {
  info:    { dotClass: "bg-blue-400",   labelClass: "text-blue-400",   label: "INFO" },
  success: { dotClass: "bg-green-400",  labelClass: "text-green-400",  label: "OK  " },
  warning: { dotClass: "bg-yellow-400", labelClass: "text-yellow-400", label: "WARN" },
  error:   { dotClass: "bg-red-400",    labelClass: "text-red-400",    label: "ERR " },
};

const PAGE_SIZE = 20;

export default function DevConsole({ logs }: DevConsoleProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [localLogs, setLocalLogs] = useState<LogEntry[]>(logs);
  const listRef = useRef<HTMLUListElement>(null);

  // Sync with parent logs; reset pagination when new logs arrive
  useEffect(() => {
    setLocalLogs(logs);
    setVisibleCount(PAGE_SIZE);
    // Scroll to the top (newest entry) when the list updates
    if (listRef.current) {
      listRef.current.scrollTop = 0;
    }
  }, [logs]);

  const clearLogs = (e: React.MouseEvent) => {
    e.stopPropagation();
    setLocalLogs([]);
  };

  const displayed = localLogs.slice(0, visibleCount);
  const hasMore = localLogs.length > visibleCount;

  return (
    <div className="bg-gray-900/80 border border-gray-700/80 rounded-xl overflow-hidden">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded((v) => !v)}
        onKeyDown={(e) => e.key === "Enter" && setIsExpanded((v) => !v)}
        className="
          flex items-center justify-between px-4 py-2.5
          bg-gray-800/60 cursor-pointer hover:bg-gray-800 transition-colors
        "
      >
        <div className="flex items-center gap-2.5">
          <Terminal className="w-4 h-4 text-green-400" />
          <span className="text-sm font-semibold text-gray-200 font-mono">
            Dev Console
          </span>
          {localLogs.length > 0 && (
            <span className="bg-blue-600 text-white text-xs px-1.5 py-0.5 rounded-full font-mono leading-none">
              {localLogs.length}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {localLogs.length > 0 && (
            <button
              onClick={clearLogs}
              aria-label="Clear logs"
              className="text-gray-600 hover:text-gray-400 transition-colors p-0.5 rounded"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          )}
        </div>
      </div>

      {/* ── Log list ──────────────────────────────────────────────────────── */}
      {isExpanded && (
        <div className="max-h-56 overflow-y-auto scrollbar-thin">
          {localLogs.length === 0 ? (
            <div className="flex items-center gap-2 px-4 py-5 text-gray-600 text-xs font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-gray-700 inline-block" />
              Waiting for activity…
            </div>
          ) : (
            <ul ref={listRef} className="divide-y divide-gray-800/50">
              {displayed.map((entry) => {
                const cfg = LEVEL_CONFIG[entry.level];
                return (
                  <li
                    key={entry.id}
                    className="flex items-start gap-3 px-4 py-2 hover:bg-gray-800/20 transition-colors"
                  >
                    {/* Level dot */}
                    <div
                      className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${cfg.dotClass}`}
                    />

                    <div className="flex-1 min-w-0">
                      {/* Meta row */}
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        {entry.step > 0 && (
                          <span className="text-xs font-mono text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">
                            step:{entry.step}
                          </span>
                        )}
                        <span
                          className={`text-xs font-mono font-semibold ${cfg.labelClass}`}
                        >
                          {cfg.label}
                        </span>
                        <span className="text-xs font-mono text-gray-600 ml-auto">
                          {formatTime(entry.timestamp)}
                        </span>
                      </div>
                      {/* Message */}
                      <p className="text-xs font-mono text-gray-300 break-words leading-relaxed">
                        {entry.message}
                      </p>
                    </div>
                  </li>
                );
              })}

              {/* Load more */}
              {hasMore && (
                <li className="px-4 py-2 text-center">
                  <button
                    onClick={() =>
                      setVisibleCount((c) =>
                        Math.min(c + PAGE_SIZE, localLogs.length),
                      )
                    }
                    className="text-xs text-blue-400 hover:text-blue-300 font-mono transition-colors"
                  >
                    ↓ Load{" "}
                    {Math.min(PAGE_SIZE, localLogs.length - visibleCount)} more…
                  </button>
                </li>
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function formatTime(d: Date): string {
  return d.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
