"use client";

import {
  Globe,
  Server,
  Cpu,
  Database,
  Radio,
  ArrowRight,
  ArrowDown,
  Layers,
  GitBranch,
  Zap,
  Lock,
  Box,
} from "lucide-react";

// ── Component definitions ─────────────────────────────────────────────────────

interface ArchComponent {
  id: string;
  icon: React.FC<{ className?: string }>;
  title: string;
  subtitle: string;
  description: string;
  tags: string[];
  colorScheme: "blue" | "purple" | "orange" | "green" | "pink";
  layer: string;
}

const COMPONENTS: ArchComponent[] = [
  {
    id: "browser",
    icon: Globe,
    title: "Next.js Frontend",
    subtitle: "Browser / Vercel",
    description:
      "React 19 application with a WebRTC avatar player, Push-to-Talk using the Web Speech API, a text chat input, and a live Dev Console log panel.",
    tags: ["Next.js 16", "React 19", "Tailwind CSS", "Lucide-react", "WebRTC Client", "Web Speech API", "SSE Streaming"],
    colorScheme: "blue",
    layer: "Frontend",
  },
  {
    id: "fastapi",
    icon: Server,
    title: "FastAPI Backend",
    subtitle: "Python 3.12 / Docker",
    description:
      "Orchestrates the RAG pipeline with LangChain LCEL. Streams answers token-by-token via SSE (/ask/stream). Synthesises speech via Azure Speech TTS (gTTS fallback) and sends audio to the avatar over a persistent WebSocket.",
    tags: ["FastAPI", "LangChain LCEL", "Python 3.12", "Pydantic v2", "SSE", "Azure Speech", "httpx"],
    colorScheme: "purple",
    layer: "Backend",
  },
  {
    id: "ollama",
    icon: Cpu,
    title: "Ollama LLM",
    subtitle: "Local Inference",
    description:
      "Dual-mode LLM backend: Ollama (llama3.2 + nomic-embed-text) for fully local inference, or Azure OpenAI (gpt-4o-mini + text-embedding-3-small) for cloud deployment. Switch via LLM_PROVIDER env var.",
    tags: ["llama3.2", "nomic-embed-text", "Ollama (local)", "Azure OpenAI (cloud)", "gpt-4o-mini"],
    colorScheme: "orange",
    layer: "AI",
  },
  {
    id: "qdrant",
    icon: Database,
    title: "Qdrant Vector DB",
    subtitle: "Docker / In-Memory",
    description:
      "Stores and retrieves embedded CV chunks using cosine similarity search. Runs in Docker for persistence or in-memory for zero-setup development.",
    tags: ["Qdrant", "Cosine Similarity", "768-dim vectors", "Docker", "In-Memory"],
    colorScheme: "green",
    layer: "Storage",
  },
  {
    id: "liveavatar",
    icon: Radio,
    title: "LiveAvatar.com",
    subtitle: "WebRTC SaaS",
    description:
      "Provides a photorealistic digital twin avatar via WebRTC. The backend proxies session creation; the browser streams video directly over an RTCPeerConnection.",
    tags: ["WebRTC", "H.264 Video", "Opus Audio", "LiveAvatar API", "ICE/STUN/TURN"],
    colorScheme: "pink",
    layer: "External",
  },
];

const COLOR_MAP: Record<
  ArchComponent["colorScheme"],
  { bg: string; border: string; icon: string; badge: string; glow: string }
> = {
  blue:   { bg: "bg-blue-500/8",   border: "border-blue-500/30",  icon: "text-blue-400",   badge: "bg-blue-900/40 text-blue-300 border border-blue-800/60",   glow: "shadow-blue-500/10" },
  purple: { bg: "bg-purple-500/8", border: "border-purple-500/30",icon: "text-purple-400", badge: "bg-purple-900/40 text-purple-300 border border-purple-800/60", glow: "shadow-purple-500/10" },
  orange: { bg: "bg-orange-500/8", border: "border-orange-500/30",icon: "text-orange-400", badge: "bg-orange-900/40 text-orange-300 border border-orange-800/60", glow: "shadow-orange-500/10" },
  green:  { bg: "bg-green-500/8",  border: "border-green-500/30", icon: "text-green-400",  badge: "bg-green-900/40 text-green-300 border border-green-800/60",  glow: "shadow-green-500/10" },
  pink:   { bg: "bg-pink-500/8",   border: "border-pink-500/30",  icon: "text-pink-400",   badge: "bg-pink-900/40 text-pink-300 border border-pink-800/60",   glow: "shadow-pink-500/10" },
};

// ── Data-flow steps ───────────────────────────────────────────────────────────

const FLOW_STEPS = [
  { step: 1, icon: Globe,     color: "text-blue-400",   text: "User speaks or types a question in the browser" },
  { step: 2, icon: Server,    color: "text-purple-400", text: "FastAPI receives POST /ask and invokes the LCEL chain" },
  { step: 3, icon: Database,  color: "text-green-400",  text: "Qdrant returns the 3 most relevant bio.txt chunks" },
  { step: 4, icon: Cpu,       color: "text-orange-400", text: "llama3.2 (Ollama) generates a grounded answer" },
  { step: 5, icon: Globe,     color: "text-blue-400",   text: "Tokens stream to the browser via SSE; each sentence is synthesised by Azure Speech TTS and spoken by the avatar" },
];

// ── Design principles ─────────────────────────────────────────────────────────

const PRINCIPLES = [
  { icon: Lock,      title: "Privacy-First",    desc: "Ollama mode runs fully offline; Azure mode uses Managed Identity — no plaintext secrets in code" },
  { icon: Zap,       title: "RAG-Grounded",     desc: "Answers are sourced from bio.txt; no hallucination" },
  { icon: Layers,    title: "Modular LCEL",     desc: "LangChain chain is composable and easy to extend" },
  { icon: GitBranch, title: "Observable",       desc: "Dev Console exposes every pipeline step in real time" },
  { icon: Box,       title: "Docker-Ready",     desc: "Qdrant (and optionally Ollama) run in Docker Compose" },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ArchitectureSection() {
  return (
    <section className="bg-gray-950 border-t border-gray-800 py-20 px-6 md:px-10 lg:px-16">
      <div className="max-w-6xl mx-auto">
        {/* Section header */}
        <div className="mb-14 text-center">
          <div className="inline-flex items-center gap-2 bg-gray-800/60 border border-gray-700 rounded-full px-4 py-1.5 text-xs text-gray-400 mb-4">
            <Layers className="w-3.5 h-3.5 text-blue-400" />
            C4 Level 2 — Container Diagram
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            System Architecture
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto text-sm leading-relaxed">
            A local-first, privacy-preserving AI stack. The LLM and vector database
            run entirely on your hardware — zero CV data is sent to external AI services.
          </p>
        </div>

        {/* ── Container cards ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-16">
          {COMPONENTS.map((comp) => {
            const c = COLOR_MAP[comp.colorScheme];
            const Icon = comp.icon;
            return (
              <div
                key={comp.id}
                className={`
                  rounded-xl border p-5 flex flex-col gap-3 transition-all duration-200
                  hover:shadow-lg ${c.bg} ${c.border} ${c.glow}
                `}
              >
                {/* Header */}
                <div className="flex items-start gap-3">
                  <div
                    className={`
                      w-9 h-9 rounded-lg ${c.bg} border ${c.border}
                      flex items-center justify-center flex-shrink-0
                    `}
                  >
                    <Icon className={`w-5 h-5 ${c.icon}`} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white text-sm leading-tight">
                      {comp.title}
                    </h3>
                    <p className={`text-xs ${c.icon} font-mono`}>{comp.subtitle}</p>
                  </div>
                  <span className="ml-auto text-xs bg-gray-800 border border-gray-700 text-gray-400 px-2 py-0.5 rounded-full font-mono whitespace-nowrap">
                    {comp.layer}
                  </span>
                </div>

                {/* Description */}
                <p className="text-xs text-gray-400 leading-relaxed flex-1">
                  {comp.description}
                </p>

                {/* Tags */}
                <div className="flex flex-wrap gap-1.5">
                  {comp.tags.map((tag) => (
                    <span
                      key={tag}
                      className={`text-xs px-2 py-0.5 rounded-full font-mono ${c.badge}`}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Data Flow ───────────────────────────────────────────────────── */}
        <div className="mb-16">
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <ArrowRight className="w-5 h-5 text-blue-400" />
            Request Data Flow
          </h3>

          <div className="relative">
            {/* Vertical connector line */}
            <div className="absolute left-5 top-5 bottom-5 w-px bg-gradient-to-b from-blue-500/40 via-purple-500/40 to-blue-500/20 hidden sm:block" />

            <div className="flex flex-col gap-3">
              {FLOW_STEPS.map(({ step, icon: StepIcon, color, text }, idx) => (
                <div key={step} className="flex items-start gap-4">
                  {/* Step indicator */}
                  <div className="relative flex-shrink-0 w-10 h-10 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center z-10">
                    <StepIcon className={`w-4 h-4 ${color}`} />
                    <span className="absolute -top-1 -right-1 w-4 h-4 bg-gray-900 border border-gray-700 rounded-full text-xs text-gray-400 flex items-center justify-center font-mono leading-none">
                      {step}
                    </span>
                  </div>

                  {/* Text */}
                  <div className="flex-1 pt-2.5">
                    <p className="text-sm text-gray-300">{text}</p>
                  </div>

                  {/* Arrow between steps */}
                  {idx < FLOW_STEPS.length - 1 && (
                    <ArrowDown className="w-3 h-3 text-gray-600 flex-shrink-0 mt-3 hidden sm:block" />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Design Principles ───────────────────────────────────────────── */}
        <div>
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <Box className="w-5 h-5 text-blue-400" />
            Design Principles
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {PRINCIPLES.map(({ icon: PIcon, title, desc }) => (
              <div
                key={title}
                className="glass-card p-4 flex flex-col gap-2 hover:border-gray-600 transition-colors"
              >
                <PIcon className="w-5 h-5 text-blue-400" />
                <h4 className="text-sm font-semibold text-white">{title}</h4>
                <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Footer attribution ──────────────────────────────────────────── */}
        <div className="mt-16 pt-8 border-t border-gray-800 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-gray-600">
          <span>
            Interactive Digital Twin CV — POC v1.0 · Built with Next.js, FastAPI, LangChain & Ollama
          </span>
          <div className="flex items-center gap-4">
            <a
              href="https://github.com/alexmorganarch"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-400 transition-colors"
            >
              GitHub
            </a>
            <a
              href="https://alexmorgan.dev"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-400 transition-colors"
            >
              Blog
            </a>
            <span>alex.morgan@example.com</span>
          </div>
        </div>
      </div>
    </section>
  );
}
