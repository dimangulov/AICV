# Interactive Digital Twin CV — Design Document

**Version:** 1.0.0  
**Date:** 2026-03-14  
**Author:** Senior Full-Stack AI Engineer  
**Status:** Proof of Concept  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [C4 Architecture Model](#3-c4-architecture-model)
4. [Component Design](#4-component-design)
5. [API Specification](#5-api-specification)
6. [Data Models](#6-data-models)
7. [Sequence Diagrams](#7-sequence-diagrams)
8. [Security Design](#8-security-design)
9. [Infrastructure Design](#9-infrastructure-design)
10. [Technology Decisions](#10-technology-decisions)
11. [Development Phases](#11-development-phases)

---

## 1. Executive Summary

The **Interactive Digital Twin CV** is a next-generation portfolio experience where a photorealistic digital avatar (powered by LiveAvatar.com) answers questions about the candidate in real time. The system uses Retrieval-Augmented Generation (RAG) with a local Large Language Model to ensure accurate, factual responses grounded in the candidate's actual experience.

**Key Value Propositions:**
- Memorable, interactive candidate presentation that stands out from static PDFs
- Accurate AI responses via RAG over structured CV data — the LLM cannot hallucinate facts it doesn't have
- Complete privacy — LLM runs locally via Ollama; no CV data is sent to cloud AI services
- Real-time speech interaction via browser-native Web Speech API (zero extra cost)
- Developer-friendly architecture with a fully observable "Dev Console" widget

---

## 2. Problem Statement

Traditional CVs are static, one-dimensional documents. Recruiters spend an average of 7 seconds reviewing a PDF, and candidates cannot demonstrate communication skills or depth of knowledge through a document.

**Goals:**
- Create an engaging, interactive experience that stands out in a competitive marketplace
- Allow visitors to ask any natural-language question about the candidate's experience
- Provide instant, accurate, and contextual answers without requiring manual scripting
- Maintain a professional aesthetic aligned with a Senior Architect profile

---

## 3. C4 Architecture Model

### Level 1 — System Context

```
┌──────────────────────────────────────────────────────────────────────┐
│                         SYSTEM CONTEXT                               │
│                                                                      │
│   ┌──────────────┐                                                   │
│   │  Recruiter / │──── visits ──────────►┌────────────────────────┐ │
│   │  Visitor     │                       │  Digital Twin CV       │ │
│   └──────────────┘                       │  (Web Application)     │ │
│                                          └──────────┬─────────────┘ │
│                                                     │               │
│                                       ┌─────────────┴───────────┐  │
│                                       │                         │  │
│                             ┌─────────▼──────┐   ┌─────────────▼┐ │
│                             │  Ollama (local) │   │ LiveAvatar   │ │
│                             │  LLM Inference  │   │ WebRTC SaaS  │ │
│                             └─────────────────┘   └─────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

**External Systems:**
| System | Role | Notes |
|--------|------|-------|
| Ollama | Local LLM runtime | Runs llama3.2 + nomic-embed-text; no data leaves the machine |
| LiveAvatar.com | Photorealistic avatar WebRTC stream | Requires API key; provides the visual face |
| Browser Web Speech API | Speech-to-Text | Client-side only; Chrome/Edge |

---

### Level 2 — Container Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CONTAINERS                                    │
│                                                                          │
│  ┌───────────────────────────┐      ┌──────────────────────────────┐   │
│  │   Next.js Frontend        │      │   FastAPI Backend             │   │
│  │   (Browser / Vercel)      │─────►│   (Python / Docker)          │   │
│  │                           │ HTTP │                               │   │
│  │  • React 19 components    │      │  • RAG Chain (LangChain LCEL) │   │
│  │  • WebRTC client          │      │  • ChatOllama LLM client      │   │
│  │  • Web Speech API (STT)   │      │  • Qdrant vector client       │   │
│  │  • Tailwind CSS / Lucide  │      │  • LiveAvatar proxy endpoint  │   │
│  └───────────────────────────┘      └─────────────┬────────────────┘   │
│                                                    │                    │
│                               ┌────────────────────┴──────────────┐    │
│                               │                                   │    │
│                     ┌─────────▼──────────┐  ┌────────────────────▼┐   │
│                     │  Qdrant Vector DB  │  │  Ollama Runtime      │   │
│                     │  (Docker)          │  │  (Local / Docker)    │   │
│                     │                    │  │                      │   │
│                     │  Collection:       │  │  Models:             │   │
│                     │  cv_knowledge_base │  │  • llama3.2 (chat)   │   │
│                     │  (cosine, 768-dim) │  │  • nomic-embed-text  │   │
│                     └────────────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Level 3 — Component Diagram: Next.js Frontend

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      NEXT.JS FRONTEND COMPONENTS                          │
│                                                                           │
│   ┌──────────────────────────────────────────────────────────────────┐   │
│   │                      page.tsx (root)                              │   │
│   │   State: logs: LogEntry[], manages addLog() callback             │   │
│   │                                                                   │   │
│   │  ┌────────────────────┐   ┌─────────────────────────────────┐   │   │
│   │  │   VideoPlayer      │   │        ChatInterface             │   │   │
│   │  │                    │   │                                  │   │   │
│   │  │ • RTCPeerConnection│   │ • useSpeechRecognition hook     │   │   │
│   │  │ • Session fetch    │   │ • Push-to-Talk button           │   │   │
│   │  │ • <video> element  │   │ • Text input field              │   │   │
│   │  │ • Status overlay   │   │ • Response display              │   │   │
│   │  │ • Mock stream (dev)│   │ • Suggested questions           │   │   │
│   │  └────────────────────┘   └─────────────────────────────────┘   │   │
│   │                                                                   │   │
│   │  ┌────────────────────────────────────────────────────────────┐  │   │
│   │  │                     DevConsole                              │  │   │
│   │  │  • Collapsible panel  • Step number badges                 │  │   │
│   │  │  • Color-coded levels • Timestamps per entry               │  │   │
│   │  │  • Auto-scroll        • Paginated load-more                │  │   │
│   │  └────────────────────────────────────────────────────────────┘  │   │
│   │                                                                   │   │
│   │  ┌────────────────────────────────────────────────────────────┐  │   │
│   │  │                 ArchitectureSection                         │  │   │
│   │  │  • C4 Level-2 visual   • Tech stack badges                 │  │   │
│   │  │  • Component cards     • Data-flow arrows                  │  │   │
│   │  │  • Layer annotations   • Hover details                     │  │   │
│   │  └────────────────────────────────────────────────────────────┘  │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│   Shared Libraries:                                                       │
│   • lib/api.ts          — typed fetch wrappers for /ask, /session        │
│   • hooks/useSpeechRecognition.ts  — webkitSpeechRecognition hook        │
│   • types/index.ts      — shared TypeScript interfaces                   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

### Level 3 — Component Diagram: FastAPI Backend

```
┌──────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND (main.py)                    │
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │           @asynccontextmanager lifespan()         │  │
│   │                                                   │  │
│   │  1. Read  bio.txt                                 │  │
│   │  2. Chunk with RecursiveCharacterTextSplitter     │  │
│   │  3. Embed with OllamaEmbeddings                   │  │
│   │  4. Store in Qdrant (in-memory or Docker)         │  │
│   │  5. Build LCEL RAG chain                          │  │
│   └──────────────────────────────────────────────────┘  │
│                                                          │
│   ┌──────────────────────┐  ┌───────────────────────┐   │
│   │   POST /ask           │  │   GET /session         │   │
│   │                       │  │                        │   │
│   │  1. Validate question │  │  1. Check LIVEAVATAR   │   │
│   │  2. Invoke RAG chain  │  │     API_KEY env        │   │
│   │  3. Return answer +   │  │  2. Proxy POST to      │   │
│   │     latency_ms        │  │     api.liveavatar.com │   │
│   └──────────────────────┘  │  3. Return session +   │   │
│                              │     ICE servers        │   │
│   ┌──────────────────────┐  └───────────────────────┘   │
│   │   GET /health         │                              │
│   │  Ollama + Qdrant ping │                              │
│   └──────────────────────┘                              │
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │                  LCEL RAG Chain                   │  │
│   │                                                   │  │
│   │  Question                                         │  │
│   │     │                                             │  │
│   │     ├──► retriever (Qdrant top-k=3) ─► format    │  │
│   │     │                                    │        │  │
│   │     └──────────────────────────────────►│        │  │
│   │                                          ▼        │  │
│   │                                    ChatPromptTemplate  │
│   │                                          │        │  │
│   │                                          ▼        │  │
│   │                                    ChatOllama     │  │
│   │                                    (llama3.2)     │  │
│   │                                          │        │  │
│   │                                          ▼        │  │
│   │                                    StrOutputParser│  │
│   │                                          │        │  │
│   │                                       answer      │  │
│   └──────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Component Design

### 4.1 RAG Pipeline

The Retrieval-Augmented Generation pipeline is the core intelligence layer:

```
bio.txt
   │
   ▼
RecursiveCharacterTextSplitter
   chunk_size=500, chunk_overlap=50
   │
   ▼ (list of Document objects)
OllamaEmbeddings (nomic-embed-text, 768-dim)
   │
   ▼
Qdrant Collection "cv_knowledge_base"
   (cosine similarity index)
   │
   ┌──────────────────────────────────────────┐
   │        At query time:                    │
   │                                          │
   │  Question ──► embed ──► similarity search│
   │                              │           │
   │                              ▼           │
   │                        top-3 Documents   │
   │                              │           │
   │                              ▼           │
   │                       ChatPromptTemplate │
   │                     context + question   │
   │                              │           │
   │                              ▼           │
   │                    ChatOllama (llama3.2) │
   │                              │           │
   │                              ▼           │
   │                        String Answer     │
   └──────────────────────────────────────────┘
```

**Chunking Strategy:**
- Chunk size: 500 chars — balances semantic coherence with retrieval precision
- Overlap: 50 chars — prevents context loss at chunk boundaries
- `RecursiveCharacterTextSplitter` respects paragraph → sentence → word boundaries

**Retrieval Strategy:**
- `k=3` most similar chunks per query
- Cosine similarity (normalized vectors) — robust to document length variation

---

### 4.2 WebRTC Integration

```
Browser                   FastAPI                  LiveAvatar
  │                          │                          │
  │── GET /session ─────────►│                          │
  │                          │── POST /v1/sessions ────►│
  │                          │◄── {session_id, token} ──│
  │◄── {session_id, token} ──│                          │
  │                          │                          │
  │── RTCPeerConnection ─────────────────────────────── │
  │   addTransceiver(video, recvonly)                   │
  │   addTransceiver(audio, recvonly)                   │
  │   createOffer()                                     │
  │── SDP Offer ────────────────────────────────────────►│
  │◄─ SDP Answer ───────────────────────────────────────│
  │   setRemoteDescription(answer)                      │
  │◄═══════════ H.264 Video / Opus Audio Stream ════════│
```

**POC Note:** The SDP exchange step is stubbed in this POC. A canvas-based mock stream is used in development mode. Replace the `// TODO: exchange SDP` block in `VideoPlayer.tsx` with the actual LiveAvatar SDK integration once credentials are available.

---

### 4.3 Speech Interaction Flow

```
User presses [Push to Talk]
        │
        ▼
  SpeechRecognition.start()
  Log: "Step 1: Listening..."
        │
        ▼ (user speaks question)
  SpeechRecognitionResult.transcript captured
  Log: 'Step 1: Captured — "What is your cloud experience?"'
        │
        ▼
  POST /ask { question }
  Log: "Step 2: RAG Retrieval — searching knowledge base..."
        │
        ▼ (Qdrant similarity search)
  Log: "Step 3: Ollama Inference — generating response..."
        │
        ▼ (llama3.2 generates answer)
  Log: "Step 4: Response generated in 1234ms"
        │
        ▼
  Display answer in ChatInterface  
  (Future: POST answer text to LiveAvatar TTS → avatar speaks)
```

---

## 5. API Specification

### 5.1 POST /ask

Performs RAG over the CV knowledge base and returns a grounded answer.

**Request body:**
```json
{
  "question": "string (1–500 characters)"
}
```

**200 Response:**
```json
{
  "answer": "I have 10+ years of cloud architecture experience across Azure ...",
  "sources": ["./bio.txt"],
  "latency_ms": 1842
}
```

**Error Responses:**

| Code | Scenario |
|------|----------|
| `422` | Validation error — question empty or over 500 chars |
| `503` | RAG chain not initialized (Ollama unreachable at startup) |
| `500` | Inference error — Ollama stopped mid-request |

---

### 5.2 GET /session

Proxies a WebRTC session request to LiveAvatar. Returns a mock session when `LIVEAVATAR_API_KEY` is not set.

**200 Response (real):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "token": "<jwt>",
  "ice_servers": [
    { "urls": "stun:stun.liveavatar.com:3478" },
    { "urls": "turn:turn.liveavatar.com:3478", "username": "u", "credential": "c" }
  ],
  "ws_url": "wss://stream.liveavatar.com/session/550e8400..."
}
```

**200 Response (mock — no API key):**
```json
{
  "session_id": "mock-session-id",
  "token": "mock-token",
  "ice_servers": [{ "urls": "stun:stun.l.google.com:19302" }],
  "ws_url": "wss://mock.liveavatar.com/session/mock-session-id"
}
```

**Error Responses:**

| Code | Scenario |
|------|----------|
| `502` | LiveAvatar API unreachable or returned non-2xx |

---

### 5.3 GET /health

**200 Response:**
```json
{
  "status": "healthy",
  "ollama": "connected",
  "qdrant": "in-memory",
  "rag_chain": "initialized"
}
```

---

## 6. Data Models

### 6.1 LogEntry (Frontend)

```typescript
interface LogEntry {
  id: string;                                          // unique monotonic ID
  timestamp: Date;                                     // time of event
  level: 'info' | 'success' | 'warning' | 'error';    // severity
  step: number;                                        // 0 = no step, 1–4 = interaction steps
  message: string;                                     // human-readable message
}
```

### 6.2 AskRequest / AskResponse

```typescript
interface AskRequest  { question: string }             // max 500 chars
interface AskResponse { answer: string; sources: string[]; latency_ms: number }
```

### 6.3 SessionResponse

```typescript
interface SessionResponse {
  session_id: string;
  token: string;
  ice_servers: RTCIceServer[];
  ws_url: string;
}
```

### 6.4 Document Chunk (Backend)

```python
Document(
    page_content="I am Damir Imangulov, a Principal Architect with 15+ years...",
    metadata={"source": "./bio.txt"}
)
```

---

## 7. Sequence Diagrams

### 7.1 Full Question-Answer Sequence

```
User     Browser    ChatInterface    lib/api.ts    FastAPI    Qdrant    Ollama
  │         │             │               │            │          │         │
  │ PTT     │             │               │            │          │         │
  │────────►│             │               │            │          │         │
  │         │ STT starts  │               │            │          │         │
  │ speaks  │             │               │            │          │         │
  │────────►│             │               │            │          │         │
  │         │ transcript  │               │            │          │         │
  │         │────────────►│               │            │          │         │
  │         │             │ askQuestion() │            │          │         │
  │         │             │──────────────►│            │          │         │
  │         │             │               │ POST /ask  │          │         │
  │         │             │               │───────────►│          │         │
  │         │             │               │            │ embed Q  │         │
  │         │             │               │            │─────────►│         │
  │         │             │               │            │◄─ vec ───│         │
  │         │             │               │            │ search   │         │
  │         │             │               │            │─────────►│         │
  │         │             │               │            │◄─ top-3 ─│         │
  │         │             │               │            │ prompt   │         │
  │         │             │               │            │─────────────────── ►│
  │         │             │               │            │◄── answer ──────────│
  │         │             │               │◄── 200 ────│          │         │
  │         │             │◄─────────────►│            │          │         │
  │         │ show answer │               │            │          │         │
  │◄────────│             │               │            │          │         │
```

### 7.2 WebRTC Session Sequence

```
Browser          FastAPI            LiveAvatar.com
  │                 │                     │
  │ GET /session    │                     │
  │────────────────►│                     │
  │                 │ POST /v1/sessions   │
  │                 │────────────────────►│
  │                 │◄── {session_id...} ─│
  │◄── {session...} │                     │
  │                 │                     │
  │ createOffer()   │                     │
  │ POST SDP offer ─────────────────────►│
  │◄── SDP answer ───────────────────────│
  │ setRemoteDesc() │                     │
  │←═══ Video / Audio Stream ════════════│
```

---

## 8. Security Design

### 8.1 Threat Model

| Threat | Risk | Mitigation |
|--------|------|-----------|
| Prompt Injection via question field | Medium | Max 500-char limit, input sanitized by Pydantic; LLM told to answer only from provided context |
| SSRF via /session proxy | High | `LIVEAVATAR_BASE_URL` is a hard-coded constant, never derived from user input |
| API Key Exposure | High | Keys stored in env vars only; never returned to frontend; not logged |
| XSS | Low | React's default JSX escaping; no dangerouslySetInnerHTML used |
| Excessive inference calls | Low | Add `slowapi` rate limiter in Phase 2 (10 req/min per IP) |
| CORS abuse | Low | `ALLOWED_ORIGINS` env var, defaults to `localhost:3000` only |

### 8.2 Secrets Management

```
.env (backend)
├── LIVEAVATAR_API_KEY     — never committed, never returned to client
├── LIVEAVATAR_AVATAR_ID   — never committed
└── ALLOWED_ORIGINS        — explicit allowlist
```

`.gitignore` must exclude `.env` and `.env.local` files.

### 8.3 Content Security Policy (Future)

Set via Next.js `headers()` in `next.config.ts`:
```
Content-Security-Policy: default-src 'self'; connect-src 'self' https://api.liveavatar.com wss://stream.liveavatar.com http://localhost:8000
```

---

## 9. Infrastructure Design

### 9.1 Local Development Stack

```
┌──────────────────────────────────────────────────────────────────┐
│                     Developer Machine                             │
│                                                                  │
│  ┌───────────────────┐    ┌────────────────────┐                │
│  │  Next.js Dev      │    │   FastAPI Dev       │                │
│  │  localhost:3000   │    │   localhost:8000    │                │
│  │  `pnpm dev`       │    │   `uvicorn ...`     │                │
│  └───────────────────┘    └────────────────────┘                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Docker Compose                         │   │
│  │   ┌─────────────────────┐   ┌──────────────────────┐   │   │
│  │   │  Qdrant             │   │  Ollama (optional)    │   │   │
│  │   │  :6333 REST API     │   │  :11434               │   │   │
│  │   └─────────────────────┘   └──────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Environment (backend/.env):                                     │
│    LLM_PROVIDER=ollama                                           │
│    QDRANT_MODE=memory  (or docker)                               │
└──────────────────────────────────────────────────────────────────┘
```

---

### 9.2 Azure Production Architecture (Budget-Friendly)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         AZURE SUBSCRIPTION                                        │
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                   Resource Group: rg-aicv-prod                            │    │
│  │                                                                           │    │
│  │  ┌─────────────────────┐        ┌──────────────────────────────────┐    │    │
│  │  │ Azure Static Web    │        │   Azure Container Apps           │    │    │
│  │  │ Apps (FREE tier)    │──REST──►   (Consumption Plan)             │    │    │
│  │  │                     │        │                                  │    │    │
│  │  │  Next.js (static    │        │  FastAPI backend container       │    │    │
│  │  │  export)            │        │  • minReplicas: 0 (scale-to-0)  │    │    │
│  │  │  CDN-backed         │        │  • 0.5 vCPU / 1 GB RAM          │    │    │
│  │  └─────────────────────┘        └───────────┬──────────────────┘    │    │
│  │                                              │                        │    │
│  │                          ┌───────────────────┼──────────────────┐    │    │
│  │                          │                   │                  │    │    │
│  │             ┌────────────▼──────┐  ┌─────────▼────────────┐    │    │
│  │             │  Azure OpenAI     │  │  Qdrant Cloud        │    │    │
│  │             │  (Pay-per-use)    │  │  (Free 1-cluster)    │    │    │
│  │             │                   │  │                      │    │    │
│  │             │  • gpt-4o-mini    │  │  cv_knowledge_base   │    │    │
│  │             │  • embed-3-small  │  │  768-dim / cosine    │    │    │
│  │             └───────────────────┘  └──────────────────────┘    │    │
│  │                                                                   │    │
│  │  Supporting resources:                                            │    │
│  │  • Azure Container Registry (Basic) — image storage              │    │
│  │  • Log Analytics Workspace — observability                        │    │
│  │  • User-Assigned Managed Identity — keyless Azure OpenAI auth    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────────┘

External (SaaS):
  • Qdrant Cloud  —  https://cloud.qdrant.io   (free 1-cluster tier)
  • LiveAvatar    —  https://liveavatar.com     (commercial; mock mode available)
  • GitHub        —  OIDC CI/CD, Container image build
```

---

### 9.3 Dual-Mode Configuration Matrix

| Setting | Local Dev | Azure Production |
|---------|-----------|-----------------|
| `LLM_PROVIDER` | `ollama` | `azure_openai` |
| Chat model | `llama3.2` (Ollama) | `gpt-4o-mini` (Azure OpenAI) |
| Embedding model | `nomic-embed-text` (Ollama) | `text-embedding-3-small` (Azure OpenAI) |
| `QDRANT_MODE` | `memory` or `docker` | `cloud` |
| Vector DB | In-memory / Docker Qdrant | Qdrant Cloud (free tier) |
| Authentication | API keys in `.env` | Managed Identity (no stored secrets) |
| Frontend | `pnpm dev` (SSR) | Azure SWA Free (static export) |
| Backend | `uvicorn --reload` | Container Apps (scales to 0) |
| Cost | ~$0 | ~$8–13 / month |

**Switching environments locally** — copy the Azure OpenAI section in `.env.example` and set:
```bash
LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=<your-key>     # for local-to-Azure-OpenAI testing
QDRANT_MODE=cloud
QDRANT_CLOUD_URL=https://your-cluster.azure.qdrant.io:6333
QDRANT_CLOUD_API_KEY=<your-key>
```

---

### 9.4 Cost Breakdown (Monthly Estimate — Low Traffic POC)

| Resource | Tier | Estimated Cost |
|----------|------|---------------|
| Azure Static Web Apps | Free | **$0** |
| Azure Container Apps (consumption) | ~20K req/month, 0.5 vCPU/1 GB | **~$2–5** |
| Azure Container Registry | Basic | **~$5** |
| Azure OpenAI — gpt-4o-mini | ~500 Q&A × 2K tokens = 1M tokens | **~$0.30** |
| Azure OpenAI — text-embedding-3-small | One-time embed at startup | **<$0.01** |
| Log Analytics Workspace | First 5 GB/month free | **$0** |
| Qdrant Cloud | Free 1-cluster (1 GB RAM) | **$0** |
| **Total** | | **~$7–10 / month** |

**Cost optimisations applied:**
- `minReplicas: 0` — Container App scales to zero when idle; cold start ~3–5 s (acceptable for a portfolio)
- `gpt-4o-mini` over `gpt-4o` — comparable reasoning for Q&A use case, 15× cheaper
- `text-embedding-3-small` — highest quality/cost ratio; embeddings only computed once at startup
- Qdrant Cloud free tier — sufficient for a single-collection CV knowledge base
- SWA Free tier — fully covers a static Next.js export with global CDN
- `azure-identity` Managed Identity — eliminates Azure Key Vault cost for secret storage

---

### 9.5 Infrastructure as Code — Terraform

All Azure resources are defined in `infra/terraform/` using HashiCorp Terraform with the `azurerm` provider (`~> 3.116`).

**File layout:**
```
infra/terraform/
├── versions.tf              # required_providers, azurerm backend (commented)
├── variables.tf             # all input variables (sensitive vars marked sensitive=true)
├── main.tf                  # all Azure resources
├── outputs.tf               # backend_url, acr_login_server, swa_api_key, etc.
└── terraform.tfvars.example # non-sensitive defaults; copy → terraform.tfvars
```

**Local first deployment:**
```bash
cd infra/terraform

# Authenticate
az login

# (Optional) Set up remote state storage first — see versions.tf for instructions
# Without this, state is stored locally (fine for solo dev, not for CI/CD)

# Initialise providers
terraform init

# Preview changes
terraform plan \
  -var="qdrant_cloud_url=https://your-cluster.azure.qdrant.io:6333" \
  -var="qdrant_cloud_api_key=<secret>"

# Apply
terraform apply \
  -var="qdrant_cloud_url=https://your-cluster.azure.qdrant.io:6333" \
  -var="qdrant_cloud_api_key=<secret>"

# Retrieve the SWA deploy token for GitHub Actions
terraform output -raw static_web_app_api_key
```

**CI/CD pipeline** (`.github/workflows/deploy-azure.yml`):

| Job | Depends on | What it does |
|-----|-----------|-------------|
| `terraform-infra` | — | `terraform init` + `apply`; exposes outputs (ACR name, backend URL) as job outputs |
| `build-backend` | `terraform-infra` | Docker build → push to ACR (login server from TF output) |
| `deploy-backend` | `build-backend` | Updates Container App revision (name from TF output) |
| `deploy-frontend` | `deploy-backend` | Next.js static export → Azure Static Web Apps |

All sensitive values flow through `TF_VAR_*` environment variables set from GitHub repository secrets — no tfvars file with secrets ever touches the repository.

---

### 9.6 Production Deployment — Phase 3 Hardening

| Concern | Phase 2 MVP | Phase 3 Production |
|---------|-------------|-------------------|
| Secrets | Container App secrets | Azure Key Vault references |
| Auth | Managed Identity | Managed Identity + Key Vault RBAC |
| Observability | Log Analytics | OpenTelemetry → Application Insights |
| Rate limiting | Not implemented | `slowapi` 10 req/min/IP |
| CDN | SWA built-in | Azure Front Door (global WAF) |
| Scale | 0–3 replicas | KEDA HTTP scaler, 0–10 replicas |
| LLM caching | None | Redis Cache (Azure Cache for Redis Basic, ~$16/mo) |

---

## 10. Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend Framework | Next.js 15 (App Router) | SSR/SSG, file-based routing, TypeScript-first |
| Styling | Tailwind CSS v3 | Rapid prototyping, utility classes, dark mode |
| Icons | Lucide-react | Lightweight, tree-shakeable, MIT licence |
| Backend Framework | FastAPI | Async, auto OpenAPI docs, Pydantic validation |
| LLM Runtime | Ollama | Local inference, privacy, no token cost |
| LLM Chat Model | llama3.2 (3B) | Good instruction following, low VRAM |
| Embedding Model | nomic-embed-text | 768-dim, best-in-class quality for size |
| Orchestration | LangChain LCEL | Composable chains, built-in RAG primitives |
| Vector Database | Qdrant | Fast cosine search, Python SDK, in-memory mode |
| Digital Avatar | LiveAvatar.com | WebRTC photorealistic digital twin as a service |
| STT | Web Speech API | Zero setup, browser-native, no API cost for POC |
| Container Runtime | Docker Compose | Reproducible local environment |

---

## 11. Development Phases

### Phase 1 — POC (Current)
- [x] Static `bio.txt` as knowledge base
- [x] In-memory Qdrant vector store
- [x] Basic RAG chain: `retriever | prompt | ChatOllama | StrOutputParser`
- [x] `/ask` endpoint with latency tracking
- [x] `/session` endpoint with LiveAvatar proxy + mock fallback
- [x] Next.js UI: VideoPlayer (WebRTC + mock), ChatInterface, DevConsole
- [x] Push-to-Talk via `webkitSpeechRecognition`
- [x] Architecture visualization section
- [x] Docker Compose for Qdrant

### Phase 2 — MVP
- [ ] Streaming LLM responses via Server-Sent Events (SSE)
- [ ] LiveAvatar TTS integration (avatar speaks the answer)
- [ ] Structured JSON CV with semantic section chunking
- [ ] Rate limiting with `slowapi` (10 req/min per IP)
- [ ] Redis caching for frequently asked questions
- [ ] `/health` endpoint integration in CI health checks
- [ ] Unit tests: pytest for backend, Vitest for frontend hooks

### Phase 3 — Production
- [ ] Multi-language support (EN / UA / DE)
- [ ] Analytics dashboard — question frequency, latency percentiles
- [ ] CMS integration (Notion or Sanity) for CV data management
- [ ] Authentication layer for private CV variant
- [ ] CI/CD pipeline (GitHub Actions → Vercel + Fly.io)
- [ ] Observability: OpenTelemetry tracing through the RAG chain
