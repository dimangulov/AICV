"use client";

import { useState, useEffect } from "react";
import { Layers, Box, Cpu, Code2, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import Mermaid from "@/components/Mermaid";

// ── Diagram definitions ────────────────────────────────────────────────────────────────────────────────

type C4Level = "context" | "container" | "frontend" | "backend";

const LEVELS: { id: C4Level; label: string; icon: React.FC<{ className?: string }>; mmdFile: string }[] = [
  { id: "context",   label: "L1 · Context",   icon: Layers, mmdFile: "structurizr-L1_SystemContext.mmd" },
  { id: "container", label: "L2 · Container", icon: Box,    mmdFile: "structurizr-L2_Containers.mmd"    },
  { id: "frontend",  label: "L3 · Frontend",  icon: Cpu,    mmdFile: "structurizr-L3_Frontend.mmd"      },
  { id: "backend",   label: "L3 · Backend",   icon: Cpu,    mmdFile: "structurizr-L3_Backend.mmd"       },
];

const DESC_MAP: Record<C4Level, string> = {
  context:
    "Top-level view: the system and its external dependencies — Ollama (local LLM) and LiveAvatar.com (avatar SaaS).",
  container:
    "Deployable units: Next.js frontend (browser), FastAPI backend (Docker/Azure), and Qdrant vector database (Docker).",
  frontend:
    "Internal wiring of the Next.js application: VideoPlayer, ChatInterface, DevConsole, and the API Client.",
  backend:
    "Internal wiring of the FastAPI server: RAG Chain (LangChain LCEL), LLM/Embeddings factories, and the LiveAvatar Proxy.",
};

const DSL_SNIPPET = `workspace "Digital Twin CV" "AI-powered interactive portfolio by Damir Imangulov" {
  model {
    visitor = person "Recruiter / Visitor" "..."

    digitalTwin = softwareSystem "Digital Twin CV" "..." {
      frontend = container "Next.js Frontend" "TypeScript / React 19" "Browser" { ... }
      backend  = container "FastAPI Backend"  "Python 3.12" "Docker" { ... }
      qdrant   = container "Qdrant Vector DB" "768-dim cosine vectors" "Docker" { tags "Database" }
    }

    ollama     = softwareSystem "Ollama"         "Local LLM runtime" "External Software"
    liveAvatar = softwareSystem "LiveAvatar.com" "WebRTC avatar SaaS" "External Software"

    visitor  -> digitalTwin "Asks questions"              "HTTPS"
    frontend -> backend     "POST /ask, POST /session"    "HTTP JSON"
    backend  -> qdrant      "Vector similarity search"    "HTTP"
    backend  -> ollama      "Chat completion & embeddings" "HTTP REST"
    backend  -> liveAvatar  "Session proxy"               "HTTPS"
  }

  views {
    systemContext digitalTwin "L1_SystemContext" { include * autoLayout lr }
    container     digitalTwin "L2_Containers"   { include * autoLayout lr }
    component     backend     "L3_Backend"      { include * autoLayout lr }
    component     frontend    "L3_Frontend"     { include * autoLayout lr }

    styles { ... }
    theme default
  }
}`;

// ── Component ─────────────────────────────────────────────────────────────────

export default function C4DiagramsSection() {
  const [activeLevel, setActiveLevel] = useState<C4Level>("context");
  const [dslOpen, setDslOpen] = useState(false);
  const [chart, setChart] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);

  const activeEntry = LEVELS.find((l) => l.id === activeLevel)!;

  useEffect(() => {
    setChart(null);
    setLoadError(false);
    fetch(`/diagrams/${activeEntry.mmdFile}`)
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.text();
      })
      .then(setChart)
      .catch(() => setLoadError(true));
  }, [activeEntry.mmdFile]);

  return (
    <section className="py-10 px-6 md:px-8 lg:px-10 flex flex-col gap-8">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 bg-gray-800/60 border border-gray-700 rounded-full px-3 py-1 text-xs text-gray-400 mb-3">
          <Layers className="w-3.5 h-3.5 text-blue-400" />
          C4 Model
        </div>
        <h2 className="text-2xl font-bold text-white mb-1">C4 Architecture Diagrams</h2>
        <p className="text-gray-400 text-sm leading-relaxed max-w-xl">
          Four-level C4 model sourced from{" "}
          <code className="text-blue-400 font-mono text-xs bg-blue-950/40 px-1.5 py-0.5 rounded">
            c4/workspace.dsl
          </code>{" "}
          and exported as Mermaid diagrams via Structurizr CLI (Docker).
        </p>
      </div>

      {/* Level selector tabs */}
      <div className="flex flex-wrap gap-2">
        {LEVELS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveLevel(id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              activeLevel === id
                ? "bg-blue-600/20 border-blue-500/60 text-blue-300"
                : "bg-gray-800/40 border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-600"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Active diagram */}
      <div className="rounded-xl border border-gray-700/60 bg-gray-900/40 overflow-hidden">
        {/* Description bar */}
        <div className="px-5 py-3 border-b border-gray-700/60 bg-gray-900/60">
          <p className="text-gray-400 text-xs leading-relaxed">{DESC_MAP[activeLevel]}</p>
        </div>

        {/* Mermaid diagram */}
        <div className="p-4">
          {loadError && (
            <div className="p-8 flex flex-col items-center gap-4 text-center">
              <p className="text-gray-400 text-sm">Diagram not found. Run the export script first:</p>
              <code className="text-green-400 font-mono text-xs bg-gray-950 border border-gray-700 rounded px-4 py-2">
                pwsh c4/export-diagrams.ps1
              </code>
            </div>
          )}
          {!loadError && !chart && (
            <div className="flex items-center justify-center gap-2 text-gray-500 py-16 text-xs">
              <span className="w-3.5 h-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              Loading…
            </div>
          )}
          {!loadError && chart && (
            <Mermaid id={activeLevel} chart={chart} />
          )}
        </div>
      </div>

      {/* C4 DSL collapsible */}
      <div className="rounded-xl border border-gray-700/60 bg-gray-900/40 overflow-hidden">
        <button
          onClick={() => setDslOpen((v) => !v)}
          className="w-full flex items-center justify-between px-5 py-3 text-sm text-gray-300 hover:bg-gray-800/40 transition-colors"
        >
          <span className="flex items-center gap-2 font-medium">
            <Code2 className="w-4 h-4 text-blue-400" />
            C4 DSL — workspace.dsl
          </span>
          <span className="flex items-center gap-2 text-gray-500 text-xs">
            <span>c4/workspace.dsl</span>
            {dslOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </span>
        </button>
        {dslOpen && (
          <div className="border-t border-gray-700/60">
            <div className="px-4 py-3 bg-gray-950/60 flex items-center justify-between text-xs text-gray-500">
              <span>
                Abbreviated — see{" "}
                <code className="text-blue-400">c4/workspace.dsl</code> for the full model
              </span>
              <a
                href="https://c4model.com"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-blue-400 hover:text-blue-300"
              >
                C4 model <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <pre className="overflow-x-auto p-4 text-xs text-gray-300 font-mono leading-relaxed bg-gray-950/40">
              {DSL_SNIPPET}
            </pre>
          </div>
        )}
      </div>
    </section>
  );
}

