"use client";

import { useState, useCallback, useRef } from "react";
import VideoPlayer from "@/components/VideoPlayer";
import ChatInterface from "@/components/ChatInterface";
import DevConsole from "@/components/DevConsole";
import ArchitectureSection from "@/components/ArchitectureSection";
import type { LogEntry } from "@/types";

let _logId = 0;

export default function Home() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const speakRef = useRef<((text: string) => void) | null>(null);

  const addLog = useCallback(
    (
      message: string,
      level: LogEntry["level"] = "info",
      step = 0,
    ) => {
      const entry: LogEntry = {
        id: String(++_logId),
        timestamp: new Date(),
        level,
        step,
        message,
      };
      // Prepend newest entry; cap at 200 to avoid memory growth
      setLogs((prev: LogEntry[]) => [entry, ...prev].slice(0, 200));
    },
    [],
  );

  return (
    <div className="min-h-screen bg-gray-950">
      {/* ── Hero Section ─────────────────────────────────────────── */}
      <section className="min-h-screen grid lg:grid-cols-2">
        {/* Left column — Digital Twin Avatar */}
        <div className="relative min-h-[50vh] lg:min-h-screen bg-gradient-to-br from-gray-900 via-gray-950 to-slate-900">
          {/* Background decoration */}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(59,130,246,0.08)_0%,transparent_70%)] pointer-events-none" />
          <VideoPlayer
            onLog={(msg, lvl) => addLog(msg, lvl ?? "info")}
            onSpeakReady={(fn) => { speakRef.current = fn; }}
          />
        </div>

        {/* Right column — Interaction panel */}
        <div className="flex flex-col gap-6 p-6 md:p-10 lg:p-12 overflow-y-auto">
          {/* Personal Brand Header */}
          <header className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-xl flex-shrink-0 shadow-lg shadow-blue-500/20">
              DI
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white tracking-tight leading-tight">
                Damir Imangulov
              </h1>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1">
                <span className="text-blue-400 font-medium">
                  Solution Architect
                </span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-500 text-sm">Cloud-Native Architect</span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-500 text-sm">10+ yrs experience</span>
              </div>
              <p className="text-gray-400 text-sm mt-2 max-w-md leading-relaxed">
                Meet Damir — he builds scalable ecosystems, not just code. Ask his
                AI digital twin about .NET &amp; Python backends, Angular frontends,
                cloud-native architecture, or any technical challenge.
              </p>
            </div>
          </header>

          {/* Skill badges */}
          <div className="flex flex-wrap gap-2">
            {SKILL_TAGS.map((tag) => (
              <span
                key={tag}
                className="text-xs bg-gray-800 border border-gray-700 text-gray-300 px-2.5 py-1 rounded-full"
              >
                {tag}
              </span>
            ))}
          </div>

          {/* Chat Interface */}
          <ChatInterface
            onLog={addLog}
            onAnswer={(text) => speakRef.current?.(text)}
          />

          {/* Developer Console */}
          <DevConsole logs={logs} />
        </div>
      </section>

      {/* ── Architecture Section ──────────────────────────────────── */}
      <ArchitectureSection />
    </div>
  );
}

const SKILL_TAGS = [
  ".NET Core · C#",
  "Python · FastAPI",
  "Angular · TypeScript",
  "Azure · AWS · Serverless",
  "Docker · Kubernetes · Helm",
  "GitOps · CI/CD · Azure DevOps",
  "SQL Server · MongoDB · Redis",
  "LangChain · RAG · LLMs",
  "Qdrant · Vector Search",
  "Clean Architecture · SOLID",
];
