# Interactive Digital Twin CV — Design Document

**Version:** 2.0.0  
**Date:** 2026-03-16  
**Author:** Senior Full-Stack AI Engineer  
**Status:** Proof of Concept — Phase 2 Complete  

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

The **Interactive Digital Twin CV** is a next-generation portfolio experience where a photorealistic digital avatar (powered by LiveAvatar.com) answers questions about the candidate in real time. The system uses Retrieval-Augmented Generation (RAG) with a dual-mode LLM backend to ensure accurate, factual responses grounded in the candidate's actual experience.

**Key Value Propositions:**
- Memorable, interactive candidate presentation that stands out from static PDFs
- Accurate AI responses via RAG over structured CV data — the LLM cannot hallucinate facts it doesn't have
- Streaming SSE responses with sentence-level avatar speech for minimal perceived latency (~200 ms to first token vs. ~3–8 s previously)
- Persistent WebSocket to LiveAvatar eliminates per-response connection overhead (~200–5500 ms saved per answer)
- Azure Speech TTS integration: high-quality neural voices with gTTS as automatic fallback
- Complete local privacy — Ollama mode runs fully offline; Azure mode used for cloud deployment
- Real-time speech interaction via browser-native Web Speech API (zero extra cost)
- Developer-friendly architecture with a fully observable "Dev Console" widget
- C4 architecture documentation as interactive SVG diagrams with pan/zoom

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

The C4 diagrams are authored in `c4/workspace.dsl` using the [Structurizr DSL](https://structurizr.com/help/dsl) and exported to SVG by running `pwsh c4/export-diagrams.ps1` (requires Docker). Exported SVGs are served statically from `frontend/public/diagrams/` and rendered in the browser with the `DiagramViewer` component (pan, zoom, reset).

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
│                                  ┌──────────────────┼───────────┐  │
│                                  │                  │           │  │
│                        ┌─────────▼──────┐  ┌───────▼─────────┐ │  │
│                        │  Ollama (local) │  │  LiveAvatar.com │ │  │
│                        │  LLM Inference  │  │  WebRTC SaaS    │ │  │
│                        └─────────────────┘  └─────────────────┘ │  │
│                                             ┌─────────────────┐ │  │
│                                             │  Azure OpenAI   │ │  │
│                                             │  (cloud mode)   │ │  │
│                                             └─────────────────┘ │  │
│                                                                  │  │
│                                             ┌─────────────────┐ │  │
│                                             │  Azure Speech   │ │  │
│                                             │  (TTS REST API) │ │  │
│                                             └─────────────────┘ │  │
└──────────────────────────────────────────────────────────────────────┘
```

**External Systems:**

| System | Role | Notes |
|--------|------|-------|
| Ollama | Local LLM runtime | llama3.2 + nomic-embed-text; no data leaves the machine |
| Azure OpenAI | Cloud LLM + embeddings | gpt-4o-mini + text-embedding-3-small; activated via `LLM_PROVIDER=azure_openai` |
| Azure Speech Services | Text-to-Speech REST API | Neural voices (en-US-GuyNeural default); gTTS fallback when key absent |
| LiveAvatar.com | Photorealistic avatar WebRTC stream | Requires API key; provides the visual face; mock mode available |
| Browser Web Speech API | Speech-to-Text | Client-side only; Chrome/Edge |

---

### Level 2 — Container Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                               CONTAINERS                                      │
│                                                                               │
│  ┌────────────────────────────┐      ┌───────────────────────────────────┐  │
│  │   Next.js Frontend         │      │   FastAPI Backend                  │  │
│  │   (Browser / Azure SWA)    │─────►│   (Python 3.12 / Docker)          │  │
│  │                            │ HTTP │                                    │  │
│  │  • React 19 components     │      │  • RAG Chain (LangChain LCEL)     │  │
│  │  • WebRTC + audio client   │      │  • Dual-mode LLM (Ollama/AzureOAI)│  │
│  │  • Web Speech API (STT)    │      │  • Qdrant vector client           │  │
│  │  • DiagramViewer (C4 SVG)  │ SSE  │  • Azure Speech / gTTS TTS       │  │
│  │  • Tailwind CSS / Lucide   │◄─────│  • LiveAvatar WebSocket proxy    │  │
│  └────────────────────────────┘      └──────────────┬────────────────────┘  │
│                                                      │                        │
│                               ┌──────────────────────┼──────────────────┐   │
│                               │                      │                   │   │
│                    ┌──────────▼─────────┐  ┌─────────▼────────────┐    │   │
│                    │  Qdrant Vector DB   │  │  Ollama Runtime       │    │   │
│                    │  (Docker / Cloud)   │  │  (Local / Docker)     │    │   │
│                    │                     │  │                       │    │   │
│                    │  cv_knowledge_base  │  │  • llama3.2 (chat)    │    │   │
│                    │  (cosine, dim varies│  │  • nomic-embed-text   │    │   │
│                    │   768 local / 1536  │  │                       │    │   │
│                    │   Azure)            │  └───────────────────────┘    │   │
│                    └─────────────────────┘                                │   │
└──────────────────────────────────────────────────────────────────────────────┘
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
│   │  │ • <audio> element  │   │ • Push-to-Talk button           │   │   │
│   │  │ • <video> (muted)  │   │ • Text input + streaming display│   │   │
│   │  │ • Status overlay   │   │ • SSE token-by-token rendering  │   │   │
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
│   │  │            SolutionDesignSection                            │  │   │
│   │  │  • ArchitectureSection (tech stack, layer cards)           │  │   │
│   │  │  • C4DiagramsSection → DiagramViewer (pan/zoom SVGs)       │  │   │
│   │  └────────────────────────────────────────────────────────────┘  │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│   Shared Libraries:                                                       │
│   • lib/api.ts          — typed fetch wrappers for /ask, /ask/stream     │
│   • hooks/useSpeechRecognition.ts  — webkitSpeechRecognition hook        │
│   • types/index.ts      — shared TypeScript interfaces                   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

### Level 3 — Component Diagram: FastAPI Backend

```
┌──────────────────────────────────────────────────────────────────┐
│              FASTAPI BACKEND (main.py)                            │
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │           @asynccontextmanager lifespan()                 │   │
│   │                                                           │   │
│   │  1. Read bio.txt → chunk → embed → Qdrant                │   │
│   │  2. Build LCEL RAG chain                                  │   │
│   │  3. Start _avatar_ws_loop() background task              │   │
│   └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│   ┌────────────────────┐  ┌──────────────────┐  ┌────────────┐  │
│   │  POST /ask          │  │ POST /ask/stream  │  │ GET /session│  │
│   │                     │  │                  │  │            │  │
│   │ Invoke RAG chain    │  │ astream() tokens │  │ LiveAvatar │  │
│   │ Trigger avatar speak│  │ SSE text/token   │  │ session    │  │
│   │ (background task)   │  │ Sentence-TTS     │  │ proxy      │  │
│   └────────────────────┘  │ per sentence      │  └────────────┘  │
│                            └──────────────────┘                   │
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │              TTS Pipeline                                 │   │
│   │                                                           │   │
│   │  _synthesize_pcm_azure()   ← AZURE_SPEECH_KEY present    │   │
│   │    POST tts.speech.microsoft.com/cognitiveservices/v1     │   │
│   │    SSML · voice: LIVEAVATAR_VOICE (en-US-GuyNeural)       │   │
│   │                                                           │   │
│   │  _synthesize_pcm_gtts()    ← fallback (no speech key)    │   │
│   │    gTTS → MP3 → pydub → PCM 16-bit / 16 kHz mono         │   │
│   └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │           Avatar WebSocket (_avatar_ws_loop)              │   │
│   │                                                           │   │
│   │  • One persistent WS to LiveAvatar (keep-alive ping)     │   │
│   │  • _speak_ws global — shared by all speak calls          │   │
│   │  • _speak_lock (asyncio.Lock) — serialise TTS sends      │   │
│   │  • _speak_on_avatar(): asyncio.gather(TTS, session)      │   │
│   │    TTS synthesis and session fetch run in parallel        │   │
│   └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │                  LCEL RAG Chain                           │   │
│   │                                                           │   │
│   │  Question                                                 │   │
│   │     ├──► retriever (Qdrant top-k=3) ──► format_docs      │   │
│   │     └──────────────────────────────►ChatPromptTemplate   │   │
│   │                                          │               │   │
│   │                                    ChatOllama /          │   │
│   │                                    AzureChatOpenAI       │   │
│   │                                          │               │   │
│   │                                    StrOutputParser       │   │
│   └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Design

### 4.1 RAG Pipeline

The Retrieval-Augmented Generation pipeline is the core intelligence layer. It runs in two modes, selected by the `LLM_PROVIDER` environment variable.

```
bio.txt
   │
   ▼
RecursiveCharacterTextSplitter
   chunk_size=500, chunk_overlap=50
   │
   ▼
┌─────────────────────────────────────────────┐
│  LLM_PROVIDER=ollama (local)                │
│    Embeddings: OllamaEmbeddings             │
│      model: nomic-embed-text (768-dim)      │
├─────────────────────────────────────────────┤
│  LLM_PROVIDER=azure_openai (cloud)          │
│    Embeddings: AzureOpenAIEmbeddings        │
│      model: text-embedding-3-small (1536-d) │
│      SKU: GlobalStandard (swedencentral)    │
└─────────────────────────────────────────────┘
   │
   ▼
Qdrant Collection "cv_knowledge_base"
   (cosine similarity index)
   │
   ┌────────────────────────────────────────────┐
   │  At query time:                            │
   │                                            │
   │  Question ──► embed ──► similarity search  │
   │                              │             │
   │                        top-3 Documents     │
   │                              │             │
   │                       ChatPromptTemplate   │
   │                     context + question     │
   │                              │             │
   │            ┌─────────────────┴───────────┐ │
   │            │ Ollama: ChatOllama (llama3.2)│ │
   │            │ Azure:  AzureChatOpenAI      │ │
   │            │         (gpt-4o-mini)        │ │
   │            └─────────────────────────────┘ │
   │                              │             │
   │                         StrOutputParser    │
   │                              │             │
   │                         String Answer      │
   └────────────────────────────────────────────┘
```

**Chunking Strategy:**
- Chunk size: 500 chars — balances semantic coherence with retrieval precision
- Overlap: 50 chars — prevents context loss at chunk boundaries
- `RecursiveCharacterTextSplitter` respects paragraph → sentence → word boundaries

**Retrieval Strategy:**
- `k=3` most similar chunks per query
- Cosine similarity (normalized vectors) — robust to document length variation

---

### 4.2 Streaming Architecture (SSE)

`POST /ask/stream` returns a `StreamingResponse` with `Content-Type: text/event-stream`:

```
Client                         FastAPI
  │                              │
  │  POST /ask/stream            │
  │─────────────────────────────►│
  │                              │  _rag_chain.astream()
  │                              │──────────────────────►  Qdrant + LLM
  │  data: {"token":"I "}        │◄── token stream ──────
  │◄─────────────────────────────│
  │  data: {"token":"have "}     │
  │◄─────────────────────────────│
  │  data: {"token":"10+ "}      │
  │◄─────────────────────────────│   sentence boundary detected
  │  data: {"token":"years. "}   │──► create_task(_speak_on_avatar("I have 10+ years."))
  │◄─────────────────────────────│
  │  ...                         │
  │  data: [DONE]                │
  │◄─────────────────────────────│
```

Sentence boundaries are detected with `_SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')`. Each completed sentence triggers an `asyncio.create_task` so TTS fires in parallel with continued token streaming.

---

### 4.3 TTS Pipeline

```
_speak_on_avatar(sentence)
        │
        ▼
asyncio.gather(
    _synthesize_pcm(sentence),     ← TTS runs in parallel with session fetch
    _fetch_session_token()
)
        │
        ▼
async with _speak_lock:            ← serialize sends to one active WebSocket
    _speak_ws.send(pcm_bytes + metadata)

──────────────────────────────────────────────────────────────
_synthesize_pcm(sentence):

    if AZURE_SPEECH_KEY:
        POST https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com
             /cognitiveservices/v1
        Headers: Ocp-Apim-Subscription-Key, X-Microsoft-OutputFormat: raw-16khz-16bit-mono-pcm
        Body: SSML with voice = LIVEAVATAR_VOICE (default: en-US-GuyNeural)
        → returns raw PCM bytes

    else (fallback):
        gTTS(sentence) → MP3 in-memory buffer
        pydub.AudioSegment → resample to 16 kHz, 16-bit, mono
        → returns raw PCM bytes
```

---

### 4.4 Avatar WebSocket Architecture

```
lifespan startup
     │
     ▼
asyncio.create_task(_avatar_ws_loop())
     │
     ▼
_avatar_ws_loop():
    while True:
        ws = await websockets.connect(LIVEAVATAR_WS_URL + session_token)
        _speak_ws = ws                         ← expose globally
        async for msg in ws:
            if msg == "ping": await ws.send("pong")
        # reconnect on disconnect

──────────────────────────────────────────────────────────────
_speak_on_avatar(text):
    async with _speak_lock:
        if _speak_ws and _speak_ws.open:
            await _speak_ws.send(pcm_payload)
```

The persistent loop eliminates a 200–5500 ms TCP+TLS handshake cost on every answer. `_speak_lock` prevents interleaved sentences from concurrent streaming responses.

---

### 4.5 WebRTC Integration

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
  │   <video muted> receives H.264 stream               │
  │   <audio> receives Opus stream (avatar speech)      │
  │◄═══════════ H.264 Video / Opus Audio Stream ════════│
```

Audio is separated from video intentionally: `<video>` remains `muted` (prevents browser auto-play policy issues) while `<audio ref={audioRef}>` carries the avatar speech track.

---

### 4.6 DiagramViewer Component

```
DiagramViewer({ src, alt, height=540 })
  │
  ├─ fetch(src)                 ← GET /diagrams/workspace-L1_SystemContext.svg
  │    SVG text → dangerouslySetInnerHTML  (trusted static files only)
  │
  ├─ onPointerDown/Move/Up      ← drag-to-pan, setPointerCapture
  │
  ├─ wheel (non-passive)        ← zoom-to-cursor, scale [0.15 – 6]
  │    Δscale = ±0.12 per notch
  │    translate adjusted to keep cursor point stationary
  │
  ├─ toolbar: ZoomIn / ZoomOut / Maximize2(reset)
  │
  └─ error state                ← shows `pwsh c4/export-diagrams.ps1` instructions
```

SVG export command: `pwsh c4/export-diagrams.ps1` — requires Docker (pulls `structurizr/cli:latest`, exports `c4/workspace.dsl` to `frontend/public/diagrams/*.svg`).

---

## 5. API Specification

### 5.1 POST /ask

Performs RAG over the CV knowledge base and returns a grounded answer. Also triggers avatar speech as a background task.

**Request body:**
```json
{ "question": "string (1–500 characters)" }
```

**200 Response:**
```json
{
  "answer": "I have 10+ years of cloud architecture experience across Azure...",
  "sources": ["./bio.txt"],
  "latency_ms": 1842
}
```

**Error Responses:**

| Code | Scenario |
|------|----------|
| `422` | Validation error — question empty or over 500 chars |
| `503` | RAG chain not initialized (LLM unreachable at startup) |
| `500` | Inference error |

---

### 5.2 POST /ask/stream

Streams the RAG answer token-by-token as Server-Sent Events and triggers sentence-level avatar speech in parallel.

**Request body:** same as `/ask`

**Response:** `Content-Type: text/event-stream`

```
data: {"token": "I "}

data: {"token": "have "}

data: {"token": "10+"}

data: {"token": " years."}

data: [DONE]
```

Each `data:` line is a JSON object with a single `token` field. The `[DONE]` sentinel signals stream end. Clients accumulate tokens to reconstruct the full answer.

**Performance:** ~200–500 ms to first token (vs. ~3–8 s for `/ask`).

---

### 5.3 GET /session

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

---

### 5.4 GET /health

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

### 7.1 Streaming Question-Answer Sequence

```
User     Browser    ChatInterface    lib/api.ts    FastAPI    Qdrant    LLM
  │         │             │               │            │          │       │
  │ PTT     │             │               │            │          │       │
  │────────►│             │               │            │          │       │
  │         │ STT         │               │            │          │       │
  │ speaks  │             │               │            │          │       │
  │────────►│             │               │            │          │       │
  │         │ transcript  │               │            │          │       │
  │         │────────────►│               │            │          │       │
  │         │             │ askStream()   │            │          │       │
  │         │             │──────────────►│            │          │       │
  │         │             │               │POST /ask/stream       │       │
  │         │             │               │───────────►│          │       │
  │         │             │               │            │ embed    │       │
  │         │             │               │            │─────────►│       │
  │         │             │               │            │◄─ top-3 ─│       │
  │         │             │               │            │ prompt ──────────►│
  │         │  token…     │               │            │◄── stream tokens ─│
  │         │◄────────────│◄──────────────│◄─ SSE ─────│          │       │
  │ sees    │             │               │            │ [sentence complete]
  │ answer  │             │               │            │──► _speak_on_avatar()
  │ grow    │             │               │            │     TTS → WS send
  │◄────────│             │               │            │          │       │
```

### 7.2 Avatar Speak Sequence (persistent WS)

```
FastAPI                   Azure Speech              LiveAvatar WS
  │                            │                         │
  │ _speak_on_avatar(sentence) │                         │
  │                            │                         │
  │ asyncio.gather(            │                         │
  │   POST /cognitiveservices/v1─────────────────────►  │
  │   _fetch_session_token()   │                         │
  │ )                          │◄── PCM bytes ──────────  │
  │                            │                         │
  │ async with _speak_lock:    │                         │
  │   _speak_ws.send(pcm) ─────────────────────────────►│
  │                            │                         │
  │                            │           avatar speaks │
```

### 7.3 WebRTC Session Sequence

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
  │ <video muted>   │                     │
  │ <audio>         │                     │
  │←═══════ H.264 Video / Opus Audio ════│
```

---

## 8. Security Design

### 8.1 Threat Model

| Threat | Risk | Mitigation |
|--------|------|-----------|
| Prompt Injection via question field | Medium | Max 500-char limit; Pydantic validation; LLM instructed to answer only from provided context |
| SSRF via /session proxy | High | `LIVEAVATAR_BASE_URL` is a hard-coded constant, never derived from user input |
| API Key Exposure | High | Keys stored in env vars only; never returned to frontend; not logged |
| XSS via SVG injection | Low | SVGs are statically exported from controlled DSL; served from `public/`; no user-supplied SVG path accepted |
| XSS via dangerouslySetInnerHTML | Low | Only used in `DiagramViewer` for static self-hosted SVG files; no external or user-supplied content |
| CORS abuse | Low | `ALLOWED_ORIGINS` env var, defaults to `localhost:3000` only |
| Excessive inference calls | Low | Add `slowapi` rate limiter (10 req/min per IP) — Phase 3 |

### 8.2 Secrets Management

```
.env (backend)
├── LIVEAVATAR_API_KEY     — never committed, never returned to client
├── LIVEAVATAR_AVATAR_ID   — never committed
├── AZURE_SPEECH_KEY       — never committed
├── AZURE_OPENAI_API_KEY   — never committed (Managed Identity preferred in Azure)
└── ALLOWED_ORIGINS        — explicit allowlist
```

`.gitignore` excludes `.env` and `.env.local`.

### 8.3 Content Security Policy (Future)

Set via Next.js `headers()` in `next.config.ts`:
```
Content-Security-Policy: default-src 'self';
  connect-src 'self' https://api.liveavatar.com wss://stream.liveavatar.com http://localhost:8000;
  img-src 'self' data:;
  script-src 'self' 'unsafe-inline'
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
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Docker (C4 export)                     │   │
│  │   pwsh c4/export-diagrams.ps1                            │   │
│  │   → structurizr/cli:latest → frontend/public/diagrams/   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Environment (backend/.env):                                     │
│    LLM_PROVIDER=ollama                                           │
│    QDRANT_MODE=memory  (or docker)                               │
│    AZURE_SPEECH_KEY=   (optional; gTTS fallback if absent)       │
└──────────────────────────────────────────────────────────────────┘
```

---

### 9.2 Azure Production Architecture

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
│  │  │                     │  + SSE │                                  │    │    │
│  │  │  Next.js (static    │        │  FastAPI backend container       │    │    │
│  │  │  export)            │        │  • minReplicas: 0 (scale-to-0)  │    │    │
│  │  │  CDN-backed         │        │  • 0.5 vCPU / 1 GB RAM          │    │    │
│  │  └─────────────────────┘        └───────────┬──────────────────┘    │    │
│  │    (enable_container_apps TF flag)           │                        │    │
│  │                          ┌───────────────────┼──────────────────┐    │    │
│  │                          │                   │                  │    │    │
│  │             ┌────────────▼──────┐  ┌─────────▼────────────┐    │    │
│  │             │  Azure OpenAI     │  │  Qdrant Cloud        │    │    │
│  │             │  (Pay-per-use)    │  │  (Free 1-cluster)    │    │    │
│  │             │                   │  │                      │    │    │
│  │             │  • gpt-4o-mini    │  │  cv_knowledge_base   │    │    │
│  │             │  • embed-3-small  │  │  1536-dim / cosine   │    │    │
│  │             │  (GlobalStandard) │  └──────────────────────┘    │    │
│  │             └──────────┬────────┘                               │    │
│  │                        │                                        │    │
│  │             ┌──────────▼────────┐                               │    │
│  │             │  Azure Speech     │                               │    │
│  │             │  Services         │                               │    │
│  │             │  (westeurope)     │                               │    │
│  │             │  kind: Speech     │                               │    │
│  │             │  sku: F0 (free)   │                               │    │
│  │             └───────────────────┘                               │    │
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
| Embedding model | `nomic-embed-text` (Ollama, 768-dim) | `text-embedding-3-small` (GlobalStandard, 1536-dim) |
| `QDRANT_MODE` | `memory` or `docker` | `cloud` |
| Vector DB | In-memory / Docker Qdrant | Qdrant Cloud (free tier) |
| TTS | gTTS fallback | Azure Speech (en-US-GuyNeural) |
| Authentication | API keys in `.env` | Managed Identity (no stored secrets) |
| Frontend | `pnpm dev` (SSR) | Azure SWA Free (static export) |
| Backend | `uvicorn --reload` | Container Apps (scales to 0, `enable_container_apps=true`) |
| Cost | ~$0 | ~$8–13 / month |

**Note:** `text-embedding-3-small` requires the `GlobalStandard` SKU in `swedencentral` — `Standard` SKU is not regionally available there.

---

### 9.4 Cost Breakdown (Monthly Estimate — Low Traffic POC)

| Resource | Tier | Estimated Cost |
|----------|------|---------------|
| Azure Static Web Apps | Free | **$0** |
| Azure Container Apps (consumption) | ~20K req/month, 0.5 vCPU/1 GB | **~$2–5** |
| Azure Container Registry | Basic | **~$5** |
| Azure OpenAI — gpt-4o-mini | ~500 Q&A × 2K tokens = 1M tokens | **~$0.30** |
| Azure OpenAI — text-embedding-3-small | One-time embed at startup | **<$0.01** |
| Azure Speech Services | F0 free tier (5h TTS/month) | **$0** |
| Log Analytics Workspace | First 5 GB/month free | **$0** |
| Qdrant Cloud | Free 1-cluster (1 GB RAM) | **$0** |
| **Total** | | **~$7–10 / month** |

**Cost optimisations applied:**
- `minReplicas: 0` — Container App scales to zero when idle; cold start ~3–5 s (acceptable for portfolio)
- `gpt-4o-mini` over `gpt-4o` — comparable reasoning for Q&A, 15× cheaper
- `text-embedding-3-small` — highest quality/cost ratio; embeddings computed once at startup
- Qdrant Cloud free tier — sufficient for single-collection CV knowledge base
- SWA Free tier — static Next.js export with global CDN
- `azure-identity` Managed Identity — eliminates Azure Key Vault cost

---

### 9.5 Infrastructure as Code — Terraform

All Azure resources are defined in `infra/terraform/` using HashiCorp Terraform with `azurerm ~> 3.116`.

**File layout:**
```
infra/terraform/
├── versions.tf              # required_providers, azurerm backend (commented)
├── variables.tf             # all input variables; sensitive vars marked sensitive=true
│                            # enable_container_apps (bool, default false)
├── main.tf                  # all Azure resources
│                            # Includes: azurerm_cognitive_account.speech (kind=SpeechServices)
│                            # Container Apps/CAE gated by count = var.enable_container_apps ? 1 : 0
├── outputs.tf               # backend_url, acr_login_server, swa_api_key, speech_key, etc.
└── terraform.tfvars.example # non-sensitive defaults; copy → terraform.tfvars
```

**`enable_container_apps` flag:** Set to `true` in `terraform.tfvars` once you have confirmed the Azure pass quota allows Container App Environments. When `false`, only the supporting infrastructure (ACR, SWA, OpenAI, Speech, Qdrant) is provisioned.

**Local first deployment:**
```bash
cd infra/terraform
az login
terraform init
terraform plan -var="qdrant_cloud_url=..." -var="qdrant_cloud_api_key=..."
terraform apply -var="qdrant_cloud_url=..." -var="qdrant_cloud_api_key=..."
terraform output -raw static_web_app_api_key
```

**CI/CD pipeline** (`.github/workflows/deploy-azure.yml`):

| Job | Depends on | What it does |
|-----|-----------|-------------|
| `terraform-infra` | — | `terraform init` + `apply`; exposes ACR name, backend URL, speech key as job outputs |
| `build-backend` | `terraform-infra` | Docker build → push to ACR |
| `deploy-backend` | `build-backend` | Updates Container App revision |
| `deploy-frontend` | `deploy-backend` | Next.js static export → Azure Static Web Apps |

---

### 9.6 Production Deployment — Phase 3 Hardening

| Concern | Phase 2 MVP | Phase 3 Production |
|---------|-------------|-------------------|
| Secrets | Container App secrets + env | Azure Key Vault references |
| Auth | Managed Identity | Managed Identity + Key Vault RBAC |
| Observability | Log Analytics | OpenTelemetry → Application Insights |
| Rate limiting | Not implemented | `slowapi` 10 req/min/IP |
| CDN | SWA built-in | Azure Front Door (global WAF) |
| Scale | 0–3 replicas | KEDA HTTP scaler, 0–10 replicas |
| LLM caching | None | Redis Cache — Azure Cache for Redis Basic (~$16/mo) |

---

## 10. Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend Framework | Next.js 16 (App Router) | SSR/SSG, file-based routing, TypeScript-first |
| Styling | Tailwind CSS v4 | Rapid prototyping, utility classes, dark mode |
| Icons | Lucide-react | Lightweight, tree-shakeable, MIT licence |
| Backend Framework | FastAPI | Async, auto OpenAPI docs, Pydantic validation |
| LLM Runtime (local) | Ollama | Local inference, privacy, no token cost |
| LLM Chat Model (local) | llama3.2 (3B) | Good instruction following, low VRAM |
| LLM Chat Model (cloud) | gpt-4o-mini | Quality/cost ratio; GlobalStandard availability |
| Embedding Model (local) | nomic-embed-text | 768-dim, best-in-class quality for size |
| Embedding Model (cloud) | text-embedding-3-small | 1536-dim, GlobalStandard SKU (swedencentral) |
| Orchestration | LangChain LCEL | Composable chains, built-in RAG primitives, `astream()` |
| Vector Database | Qdrant | Fast cosine search, Python SDK, in-memory + cloud modes |
| Digital Avatar | LiveAvatar.com | WebRTC photorealistic digital twin as a service |
| STT | Web Speech API | Zero setup, browser-native, no API cost for POC |
| TTS (primary) | Azure Speech REST API | High-quality neural voices; low latency; same Azure subscription |
| TTS (fallback) | gTTS + pydub | Zero-cost local fallback when `AZURE_SPEECH_KEY` absent |
| TTS voice | en-US-GuyNeural | Configurable via `LIVEAVATAR_VOICE` env var |
| Streaming | Server-Sent Events (SSE) | Simple, HTTP-native, automatic reconnect; no WS overhead |
| C4 Diagramming | Structurizr DSL + CLI | Version-controlled DSL, reproducible SVG export via Docker |
| SVG Viewer | DiagramViewer (custom) | Inline SVG, pointer-events pan, non-passive wheel zoom-to-cursor |
| Container Runtime | Docker Compose | Reproducible local environment |
| IaC | Terraform (azurerm ~> 3.116) | Declarative, Git-tracked infrastructure |

---

## 11. Development Phases

### Phase 1 — POC ✅
- [x] Static `bio.txt` as knowledge base
- [x] In-memory Qdrant vector store
- [x] Basic RAG chain: `retriever | prompt | ChatOllama | StrOutputParser`
- [x] `/ask` endpoint with latency tracking
- [x] `/session` endpoint with LiveAvatar proxy + mock fallback
- [x] Next.js UI: VideoPlayer (WebRTC + mock), ChatInterface, DevConsole
- [x] Push-to-Talk via `webkitSpeechRecognition`
- [x] Architecture visualization section
- [x] Docker Compose for Qdrant

### Phase 2 — MVP ✅
- [x] Streaming LLM responses via Server-Sent Events (`POST /ask/stream`)
- [x] Azure Speech TTS integration with gTTS fallback
- [x] Persistent WebSocket to LiveAvatar (`_avatar_ws_loop` + `_speak_lock`)
- [x] Sentence-level pipelined TTS — avatar speech fires per sentence, not after full answer
- [x] Dual-mode LLM: Ollama (local) + Azure OpenAI (cloud)
- [x] Audio track separated from video (`<audio>` + `<video muted>`)
- [x] C4 architecture diagrams (Structurizr DSL → SVG export → DiagramViewer pan/zoom)
- [x] Terraform IaC: Azure OpenAI, Azure Speech, Container Apps, SWA, ACR, Log Analytics
- [x] GitHub Actions CI/CD: Terraform → Docker build → Container App deploy → SWA deploy
- [x] `enable_container_apps` Terraform flag for quota-safe provisioning

### Phase 3 — Production
- [ ] Structured JSON CV with semantic section chunking
- [ ] Multi-language support (EN / UA / DE)
- [ ] Rate limiting with `slowapi` (10 req/min per IP)
- [ ] Redis caching for frequently asked questions
- [ ] Analytics dashboard — question frequency, latency percentiles
- [ ] Azure Key Vault for secrets management
- [ ] OpenTelemetry tracing through the RAG chain
- [ ] Azure Front Door CDN + WAF
- [ ] KEDA HTTP auto-scaler
