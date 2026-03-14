"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { Layers, Box, Cpu, Code2, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

// Mermaid is client-only (no SSR) — dynamic import prevents hydration errors
const Mermaid = dynamic(() => import("@/components/Mermaid"), { ssr: false });

// ── C4 diagram definitions (Mermaid C4 syntax) ───────────────────────────────

const LEVEL1_CHART = `C4Context
  title Level 1 — System Context
  Person(visitor, "Recruiter / Visitor", "Explores the interactive digital twin CV portfolio")
  System(app, "Digital Twin CV", "AI-powered interactive portfolio. A WebRTC avatar answers natural-language questions via a RAG pipeline.")
  System_Ext(ollama, "Ollama", "Local LLM runtime. llama3.2 chat and nomic-embed-text embeddings. No data leaves the machine.")
  System_Ext(liveavatar, "LiveAvatar.com", "SaaS WebRTC avatar streaming. Provides the photorealistic digital twin video stream.")
  Rel(visitor, app, "Visits and asks questions", "HTTPS / WebRTC")
  Rel(app, ollama, "LLM inference and embeddings", "HTTP REST")
  Rel(app, liveavatar, "Avatar session management", "HTTPS")`;

const LEVEL2_CHART = `C4Container
  title Level 2 — Container Diagram
  Person(visitor, "Recruiter / Visitor", "")
  Container_Boundary(b, "Digital Twin CV") {
    Container(frontend, "Next.js Frontend", "TypeScript / React 19", "WebRTC avatar player, chat UI, dev console. Runs in the browser.")
    Container(backend, "FastAPI Backend", "Python 3.12", "RAG pipeline orchestration. Exposes /ask, /session, /health endpoints.")
    ContainerDb(qdrant, "Qdrant Vector DB", "Docker", "cv_knowledge_base collection. 768-dim cosine-similarity vectors from bio.txt.")
  }
  System_Ext(ollama, "Ollama", "Local LLM runtime")
  System_Ext(liveavatar, "LiveAvatar.com", "WebRTC avatar SaaS")
  Rel(visitor, frontend, "Uses", "HTTPS / WebRTC")
  Rel(frontend, backend, "POST /ask, POST /session", "HTTP REST")
  Rel(backend, qdrant, "Vector similarity search", "HTTP")
  Rel(backend, ollama, "Chat completion and embeddings", "HTTP")
  Rel(backend, liveavatar, "Session proxy", "HTTPS")`;

const LEVEL3_FRONTEND_CHART = `C4Component
  title Level 3 — Next.js Frontend Components
  Container_Boundary(b, "Next.js Frontend") {
    Component(video, "VideoPlayer", "React Component", "Manages LiveKit WebRTC room, renders avatar stream, falls back to mock canvas")
    Component(chat, "ChatInterface", "React Component", "Text and voice input, calls POST /ask, displays answer and latency")
    Component(console, "DevConsole", "React Component", "Real-time log panel showing RAG pipeline steps")
    Component(speech, "useSpeechRecognition", "React Hook", "Wraps Web Speech API, provides transcript and listening state")
    Component(api, "API Client", "TypeScript fetch", "Typed wrappers for /ask, /session, /health endpoints")
  }
  Container(backend, "FastAPI Backend", "Python 3.12", "")
  System_Ext(liveavatar, "LiveAvatar.com", "WebRTC SaaS")
  Rel(video, api, "getSession()")
  Rel(chat, api, "askQuestion(question)")
  Rel(chat, speech, "uses transcript")
  Rel(api, backend, "HTTP fetch")
  Rel(video, liveavatar, "WebRTC stream", "WSS / SRTP")`;

const LEVEL3_BACKEND_CHART = `C4Component
  title Level 3 — FastAPI Backend Components
  Container(frontend, "Next.js Frontend", "TypeScript", "")
  Container_Boundary(b, "FastAPI Backend") {
    Component(ask, "/ask", "FastAPI Route", "Validates input, invokes RAG chain, returns answer + latency_ms")
    Component(session, "/session", "FastAPI Route", "Proxies LiveAvatar session creation, injects API key server-side")
    Component(health, "/health", "FastAPI Route", "Reports Qdrant, Ollama, and RAG chain readiness")
    Component(rag, "RAG Chain", "LangChain LCEL", "retrieve -> format_docs -> ChatPromptTemplate -> LLM -> StrOutputParser")
    Component(llm, "LLM Factory", "Python", "Returns ChatOllama or AzureChatOpenAI based on LLM_PROVIDER env")
    Component(embed, "Embeddings Factory", "Python", "Returns OllamaEmbeddings or AzureOpenAIEmbeddings")
    Component(vs, "Vector Store Manager", "Qdrant Client", "Startup: loads bio.txt, chunks 500 tokens, embeds, upserts to Qdrant")
    Component(proxy, "LiveAvatar Proxy", "httpx", "Stateless proxy, injects auth headers, never logs credentials")
  }
  ContainerDb(qdrant, "Qdrant Vector DB", "Docker", "")
  System_Ext(ollama, "Ollama", "")
  System_Ext(liveavatar, "LiveAvatar.com", "")
  Rel(frontend, ask, "POST /ask", "HTTP")
  Rel(frontend, session, "POST /session", "HTTP")
  Rel(frontend, health, "GET /health", "HTTP")
  Rel(ask, rag, "invoke(question)")
  Rel(rag, llm, "createLLM()")
  Rel(rag, vs, "retrieve(k=3)")
  Rel(vs, embed, "createEmbeddings()")
  Rel(vs, qdrant, "similarity_search()", "HTTP")
  Rel(llm, ollama, "chat_completion()", "HTTP")
  Rel(embed, ollama, "embed_documents()", "HTTP")
  Rel(session, proxy, "delegate()")
  Rel(proxy, liveavatar, "POST /session", "HTTPS")`;

// ── DSL snippet shown in the collapsible section ──────────────────────────────

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

// ── Sub-tab type ──────────────────────────────────────────────────────────────

type C4Level = "context" | "container" | "frontend" | "backend";

const LEVELS: { id: C4Level; label: string; icon: React.FC<{ className?: string }> }[] = [
  { id: "context",   label: "L1 · Context",   icon: Layers },
  { id: "container", label: "L2 · Container", icon: Box },
  { id: "frontend",  label: "L3 · Frontend",  icon: Cpu },
  { id: "backend",   label: "L3 · Backend",   icon: Cpu },
];

const CHART_MAP: Record<C4Level, string> = {
  context:   LEVEL1_CHART,
  container: LEVEL2_CHART,
  frontend:  LEVEL3_FRONTEND_CHART,
  backend:   LEVEL3_BACKEND_CHART,
};

const DESC_MAP: Record<C4Level, string> = {
  context:
    "Top-level view: the system and its external dependencies — Ollama (local LLM) and LiveAvatar.com (avatar SaaS). " +
    "The user interacts with the Digital Twin CV over HTTPS/WebRTC.",
  container:
    "Shows how the system is decomposed into deployable units: the Next.js frontend (browser), FastAPI backend (Docker/Azure), " +
    "and Qdrant vector database (Docker). External callouts go to Ollama and LiveAvatar.",
  frontend:
    "Internal wiring of the Next.js application: VideoPlayer manages the WebRTC room, ChatInterface handles input+output, " +
    "DevConsole surfaces pipeline logs, and the API Client owns all backend communication.",
  backend:
    "Internal wiring of the FastAPI server: the RAG Chain (LangChain LCEL) composes retrieval, prompting, and LLM inference. " +
    "Provider factories switch between local Ollama and Azure OpenAI. The LiveAvatar Proxy injects credentials server-side.",
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function C4DiagramsSection() {
  const [activeLevel, setActiveLevel] = useState<C4Level>("context");
  const [dslOpen, setDslOpen] = useState(false);

  return (
    <section className="py-10 px-6 md:px-8 lg:px-10 flex flex-col gap-8">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 bg-gray-800/60 border border-gray-700 rounded-full px-3 py-1 text-xs text-gray-400 mb-3">
          <Layers className="w-3.5 h-3.5 text-blue-400" />
          Structurizr C4 Model
        </div>
        <h2 className="text-2xl font-bold text-white mb-1">C4 Architecture Diagrams</h2>
        <p className="text-gray-400 text-sm leading-relaxed max-w-xl">
          Four-level C4 model of the Digital Twin CV system, generated from the{" "}
          <code className="text-blue-400 font-mono text-xs bg-blue-950/40 px-1.5 py-0.5 rounded">
            c4/workspace.dsl
          </code>{" "}
          Structurizr DSL workspace and rendered via Mermaid.
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
        {/* Diagram description */}
        <div className="px-5 py-3 border-b border-gray-700/60 bg-gray-900/60">
          <p className="text-gray-400 text-xs leading-relaxed">{DESC_MAP[activeLevel]}</p>
        </div>
        {/* Mermaid output */}
        <div className="p-4 min-h-[280px] flex items-center justify-center">
          <Mermaid id={activeLevel} chart={CHART_MAP[activeLevel]} />
        </div>
      </div>

      {/* Structurizr DSL collapsible */}
      <div className="rounded-xl border border-gray-700/60 bg-gray-900/40 overflow-hidden">
        <button
          onClick={() => setDslOpen((v) => !v)}
          className="w-full flex items-center justify-between px-5 py-3 text-sm text-gray-300 hover:bg-gray-800/40 transition-colors"
        >
          <span className="flex items-center gap-2 font-medium">
            <Code2 className="w-4 h-4 text-blue-400" />
            Structurizr DSL — workspace.dsl
          </span>
          <span className="flex items-center gap-2 text-gray-500 text-xs">
            <span>c4/workspace.dsl</span>
            {dslOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </span>
        </button>
        {dslOpen && (
          <div className="border-t border-gray-700/60">
            <div className="px-4 py-3 bg-gray-950/60 flex items-center justify-between text-xs text-gray-500">
              <span>Abbreviated — see <code className="text-blue-400">c4/workspace.dsl</code> for the full model</span>
              <a
                href="https://structurizr.com/help/lite"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-blue-400 hover:text-blue-300"
              >
                Run with Structurizr Lite <ExternalLink className="w-3 h-3" />
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
