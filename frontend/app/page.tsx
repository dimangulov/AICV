"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import VideoPlayer from "@/components/VideoPlayer";
import ChatInterface, { type ChatInterfaceHandle } from "@/components/ChatInterface";
import DevConsole from "@/components/DevConsole";
import ArchitectureSection from "@/components/ArchitectureSection";
import DesignSection from "@/components/DesignSection";
import C4DiagramsSection from "@/components/C4DiagramsSection";
import { Github, Mail, Linkedin, MapPin } from "lucide-react";
import { speakText, initSessionId } from "@/lib/api";
import { useAvatarAudioGate } from "@/hooks/useAvatarAudioGate";
import type { LogEntry } from "@/types";

const INTRO_PLAYED_KEY = "aicv_intro_played";

const AVATAR_INTRO =
  "Meet Damir Imangulov. He is a Senior Full-Stack Engineer with a deep-seated focus on " +
  "cloud-native solution design." +
  "Ask me anyhting about backends, cloud architecture, or technical challenges ";

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
  const introSpoken = useRef(false);
  const chatRef = useRef<ChatInterfaceHandle>(null);

  // Restore or create session ID from localStorage
  useEffect(() => {
    initSessionId();
  }, []);  const [avatarAudioEl, setAvatarAudioEl] = useState<HTMLAudioElement | null>(null);
  const isAvatarSpeaking = useAvatarAudioGate(avatarAudioEl);

  // Tracks the intro mic-start lifecycle:
  //   "waiting"  — onConnected hasn't fired yet
  //   "pending"  — intro speech queued; waiting for gate to go active
  //   "speaking" — gate confirmed audio is playing
  //   "done"     — gate went silent; mic started (or fallback fired)
  const introPhaseRef = useRef<"waiting" | "pending" | "speaking" | "done">("waiting");
  const introFallbackRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Start the mic once the intro finishes (gate: speaking → silent).
  // Also guards against mock mode where the gate never fires.
  useEffect(() => {
    const phase = introPhaseRef.current;
    if (phase === "done" || phase === "waiting") return;

    if (phase === "pending" && isAvatarSpeaking) {
      // Gate confirmed audio is live — cancel the fallback timer.
      introPhaseRef.current = "speaking";
      if (introFallbackRef.current) {
        clearTimeout(introFallbackRef.current);
        introFallbackRef.current = null;
      }
    } else if (phase === "speaking" && !isAvatarSpeaking) {
      // Audio finished — safe to open the mic.
      introPhaseRef.current = "done";
      chatRef.current?.startContinuous();
    }
  }, [isAvatarSpeaking]);

  // Restore or create session ID from localStorage (persists across refreshes)
  useEffect(() => {
    initSessionId();
  }, []);

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
      <div className="w-full lg:w-2/5 h-[45vh] lg:h-full flex-shrink-0 relative bg-gradient-to-br from-gray-900 via-gray-950 to-slate-900">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(59,130,246,0.08)_0%,transparent_70%)] pointer-events-none" />
        <VideoPlayer
          onLog={(msg, lvl) => addLog(msg, lvl ?? "info")}
          onAudioReady={setAvatarAudioEl}
          onConnected={() => {
            if (introSpoken.current) return;
            introSpoken.current = true;

            // Only play intro the very first time the visitor opens the site.
            const alreadyPlayed = localStorage.getItem(INTRO_PLAYED_KEY) === "1";
            if (!alreadyPlayed) {
              localStorage.setItem(INTRO_PLAYED_KEY, "1");
              addLog("[Avatar] Playing intro...", "info");
              speakText(AVATAR_INTRO).catch(() => {});
              introPhaseRef.current = "pending";
              const fallbackMs = Math.max(3000, (AVATAR_INTRO.length / 15) * 1000);
              introFallbackRef.current = setTimeout(() => {
                if (introPhaseRef.current !== "done") {
                  introPhaseRef.current = "done";
                  chatRef.current?.startContinuous();
                }
              }, fallbackMs);
            } else {
              // Returning visitor — skip intro, start mic immediately
              addLog("[Avatar] Reconnected (returning visitor — skipping intro)", "info");
              introPhaseRef.current = "done";
              chatRef.current?.startContinuous();
            }
          }}
        />
      </div>

      {/* ── Right column — Tabbed content (scrollable) ───────────── */}
      <div className="w-full lg:w-3/5 flex flex-col lg:h-full border-l border-gray-800">

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
                    AI digital twin about .NET &amp; Python backends, React frontends,
                    cloud-native architecture, or any technical challenge.
                  </p>
                  <a
                    href="https://github.com/dimangulov/AICV"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 mt-3 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 hover:border-gray-500 hover:bg-gray-700 text-gray-300 hover:text-white text-xs font-medium transition-all"
                  >
                    <Github className="w-4 h-4" />
                    dimangulov/AICV
                  </a>
                  <div className="flex flex-wrap items-center gap-2 mt-3">
                    <a
                      href="mailto:dimangulov@gmail.com"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 hover:border-gray-500 hover:bg-gray-700 text-gray-300 hover:text-white text-xs font-medium transition-all"
                    >
                      <Mail className="w-3.5 h-3.5" />
                      dimangulov@gmail.com
                    </a>
                    <a
                      href="https://www.linkedin.com/in/damir-imangulov-5b1346102/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 hover:border-gray-500 hover:bg-gray-700 text-gray-300 hover:text-white text-xs font-medium transition-all"
                    >
                      <Linkedin className="w-3.5 h-3.5" />
                      LinkedIn
                    </a>
                    <a
                      href="https://github.com/dimangulov/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 hover:border-gray-500 hover:bg-gray-700 text-gray-300 hover:text-white text-xs font-medium transition-all"
                    >
                      <Github className="w-3.5 h-3.5" />
                      GitHub
                    </a>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 text-xs font-medium">
                      <MapPin className="w-3.5 h-3.5" />
                      Sofia, BG · open to remote &amp; hybrid
                    </span>
                  </div>
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

              <ChatInterface ref={chatRef} onLog={addLog} isAvatarSpeaking={isAvatarSpeaking} />
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
