"use client";

import { useState, useCallback } from "react";
import VideoPlayer from "@/components/VideoPlayer";
import ChatInterface from "@/components/ChatInterface";
import DevConsole from "@/components/DevConsole";
import ArchitectureSection from "@/components/ArchitectureSection";
import DesignSection from "@/components/DesignSection";
import C4DiagramsSection from "@/components/C4DiagramsSection";
import { speakText } from "@/lib/api";
import type { LogEntry } from "@/types";

const AVATAR_INTRO =
  "Meet Damir Imangulov. He is a Senior Full-Stack Engineer with a deep-seated focus on " +
  "cloud-native solution design. Damir doesn't just write code; he builds scalable ecosystems. " +
  "By architecting robust backends in .NET and Python and crafting seamless frontends, he bridges " +
  "the gap between complex infrastructure and the end-user. Whether it's optimizing a cloud " +
  "environment for high availability or designing a sleek, reactive UI, Damir's goal is to ensure " +
  "that technical complexity never gets in the way of a great user experience.";

let _logId = 0;

type Tab = "chat" | "architecture" | "c4" | "design";

const TABS: { id: Tab; label: string }[] = [
  { id: "chat",         label: "Chat" },
  { id: "architecture", label: "Architecture" },
  { id: "c4",           label: "C4 Diagrams" },
  { id: "design",       label: "Design Doc" },
];

export default function Home() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  const addLog = useCallback(
    (message: string, level: LogEntry["level"] = "info", step = 0) => {
      const entry: LogEntry = {
        id: String(++_logId),
        timestamp: new Date(),
        level,
        step,
        message,
      };
      setLogs((prev: LogEntry[]) => [entry, ...prev].slice(0, 200));
    },
    [],
  );

  return (
    <div className="min-h-screen lg:h-screen lg:overflow-hidden flex flex-col lg:flex-row bg-gray-950">

      {/* ── Left column — Digital Twin Video (always visible) ────── */}
      <div className="w-full lg:w-1/2 h-[50vh] lg:h-full flex-shrink-0 relative bg-gradient-to-br from-gray-900 via-gray-950 to-slate-900">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(59,130,246,0.08)_0%,transparent_70%)] pointer-events-none" />
        <VideoPlayer
          onLog={(msg, lvl) => addLog(msg, lvl ?? "info")}
          onConnected={() => {
            addLog("[Avatar] Playing intro...", "info");
            //speakText(AVATAR_INTRO).catch(() => {});
          }}
        />
      </div>

      {/* ── Right column — Tabbed content (scrollable) ───────────── */}
      <div className="w-full lg:w-1/2 flex flex-col lg:h-full border-l border-gray-800">

        {/* Tab navigation */}
        <nav className="flex-shrink-0 bg-gray-950/90 backdrop-blur border-b border-gray-800 px-4 flex items-center h-12 gap-1 overflow-x-auto sticky top-0 z-10">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab panels */}
        <div className="flex-1 overflow-y-auto">

          {/* ── Chat tab ───────────────────────────────────────────── */}
          {activeTab === "chat" && (
            <div className="flex flex-col gap-6 p-6 md:p-8 lg:p-10">
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

              <ChatInterface onLog={addLog} />
              <DevConsole logs={logs} />
            </div>
          )}

          {/* ── Architecture tab ───────────────────────────────────── */}
          {activeTab === "architecture" && <ArchitectureSection />}

          {/* ── C4 Diagrams tab ────────────────────────────────────── */}
          {activeTab === "c4" && <C4DiagramsSection />}

          {/* ── Design Doc tab ─────────────────────────────────────── */}
          {activeTab === "design" && <DesignSection />}

        </div>
      </div>
    </div>
  );
}

const SKILL_TAGS = [
  ".NET Core · C#",
  "Python · FastAPI",
  "Angular · React (NextJS) · TypeScript",
  "Azure  · Serverless",
  "Docker · Kubernetes · Helm",
  "GitOps · CI/CD · Azure DevOps",
  "SQL Server · MongoDB · Redis",
  "LangChain · RAG · LLMs",
  "Qdrant · Vector Search",
  "Clean Architecture · SOLID",
];
