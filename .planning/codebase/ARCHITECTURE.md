# Architecture

**Analysis Date:** 2026-04-22

## Pattern Overview

**Overall:** Two-tier client/server web application with a RAG (Retrieval-Augmented Generation) AI backend. The backend is a modular-monolith FastAPI service composed of focused Python modules; the frontend is a Next.js 16 App Router single-page application. An external WebRTC SaaS (LiveAvatar / LiveKit) delivers the photorealistic avatar video stream; the backend proxies session creation and streams TTS audio to LiveAvatar over a persistent per-user WebSocket.

**Key Characteristics:**
- Decoupled frontend (`frontend/`) and backend (`backend/`) talk only via HTTP/SSE; no shared runtime.
- Dual-mode LLM provider pattern: swap local Ollama for cloud Azure OpenAI via the single `LLM_PROVIDER` env var in `backend/config.py`.
- RAG pipeline implemented as a LangChain LCEL chain: retriever → prompt → LLM → parser. Built once at startup in `backend/rag.py`.
- Streaming-first: `/ask/stream` emits SSE tokens while simultaneously fanning out sentence-level TTS tasks, minimising perceived latency.
- Per-user session state held in-memory on the backend (no shared DB for sessions); sessions keyed by `X-Session-ID` UUID header.
- Authoritative C4 diagrams defined in DSL at `c4/workspace.dsl`; exported artefacts consumed by the frontend for the "C4 Diagrams" tab.
- Infrastructure-as-code: Terraform (`infra/terraform/`) provisions all Azure resources; GitHub Actions (`.github/workflows/deploy-azure.yml`) orchestrates the pipeline.

## Layers

**Presentation / UI (Frontend):**
- Purpose: React components, hooks, and browser-side state; WebRTC/WebSpeech integration.
- Location: `frontend/app/`, `frontend/components/`, `frontend/hooks/`
- Contains: React Client Components (`"use client"`), tab navigation, chat UI, video player, dev console, C4/design viewers.
- Depends on: `frontend/lib/api.ts` (API client), `frontend/types/index.ts` (shared types), `livekit-client` SDK, browser APIs (`webkitSpeechRecognition`, `localStorage`, `crypto.randomUUID`).
- Used by: The user's browser only.

**Client API Layer (Frontend):**
- Purpose: Typed `fetch` wrappers that front every backend endpoint and manage the per-tab session UUID.
- Location: `frontend/lib/api.ts`
- Contains: `askQuestion`, `askQuestionStream` (SSE reader), `getSession`, `speakText`, `interruptSpeech`, `closeSession`, `ping`, `getHealth`; `initSessionId`/`resetSessionId` managing `aicv_session_id` in `localStorage`.
- Depends on: `process.env.NEXT_PUBLIC_API_URL`, `frontend/types/index.ts`.
- Used by: Every component that touches the backend (`VideoPlayer`, `ChatInterface`, `page.tsx`).

**HTTP/API Layer (Backend):**
- Purpose: FastAPI route handlers, validation, CORS, rate limiting, session-header parsing.
- Location: `backend/main.py`
- Contains: `/ask`, `/ask/stream`, `/speak`, `/interrupt`, `/session` (GET and DELETE), `/ping`, `/health`. `lifespan` context manager wires startup/shutdown.
- Depends on: `backend/models.py` (Pydantic), `backend/rag.py`, `backend/avatar.py`, `backend/tts.py`, `backend/config.py`.
- Used by: Browser via `frontend/lib/api.ts`.

**Domain / RAG Layer (Backend):**
- Purpose: Load `backend/bio.txt`, chunk/embed/index, build the LCEL chain, execute retrieval and generation.
- Location: `backend/rag.py`
- Contains: `_create_llm()`, `_create_embeddings()`, `_create_vectorstore()`, `_format_docs()`, `format_history()`, `build_rag_chain()`.
- Depends on: `langchain`, `langchain-ollama`, `langchain-openai`, `qdrant-client`, constants from `backend/config.py`.
- Used by: `backend/main.py` (chain invoked in `/ask` and streamed in `/ask/stream`).

**Avatar / Session Layer (Backend):**
- Purpose: Per-user LiveAvatar session lifecycle, persistent WebSocket audio delivery, interrupts, idle eviction.
- Location: `backend/avatar.py`
- Contains: `UserSession` dataclass, `_user_sessions` in-memory store (with `_user_sessions_lock`), `get_or_create_user_session`, `get_or_create_liveavatar_session`, `speak_on_avatar`, `evict_idle_sessions`, `warm_fillers`, `pick_filler`, filler phrase cache.
- Depends on: `backend/tts.py`, `backend/config.py`, `httpx`, `websockets`.
- Used by: `/session`, `/speak`, `/interrupt`, `/ask` (background task), `/ask/stream` (per-sentence tasks).

**TTS Layer (Backend):**
- Purpose: Synthesise text to 16-bit mono 24 kHz PCM for LiveAvatar ingestion.
- Location: `backend/tts.py`
- Contains: `_stream_tts_azure()` (SSML → Azure Cognitive Services REST streaming), `_synthesize_pcm_azure`, `_synthesize_pcm_gtts` (gTTS+miniaudio fallback), `synthesize_pcm` dispatcher, module-level `http_client: httpx.AsyncClient` initialised in `main.lifespan`.
- Depends on: `backend/config.py` (`AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `LIVEAVATAR_VOICE`), `httpx`, `miniaudio`, optional `gtts`.
- Used by: `backend/avatar.py`.

**Configuration Layer (Backend):**
- Purpose: Central, single-source env-var resolution and logging setup.
- Location: `backend/config.py`
- Contains: All `os.getenv(...)` reads, `load_dotenv()`, `BIO_FILE_PATH`, `COLLECTION_NAME`, `ALLOWED_ORIGINS`, `UUID_RE`, `MAX_SESSIONS`, `SESSION_IDLE_TTL`.
- Depends on: `python-dotenv`.
- Used by: Every other backend module (the module comment forbids `os.getenv` elsewhere).

**Data / Vector Layer:**
- Purpose: Store and retrieve embedded chunks of `backend/bio.txt`.
- Location: Qdrant in three modes, selected via `QDRANT_MODE`:
  - `memory` — in-process (default local dev)
  - `docker` — local Docker container defined in `docker-compose.yml`
  - `cloud` — Qdrant Cloud cluster
- Collection: `cv_knowledge_base` (cosine; 768-dim Ollama or 1536-dim Azure).

**Infrastructure / Deployment:**
- Purpose: Provision and deploy Azure resources.
- Location: `infra/terraform/` (+ bootstrap at `infra/terraform/bootstrap/`), `.github/workflows/deploy-azure.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `setup-local.ps1`.
- Contains: `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `terraform.tfvars`, plus the `enable_container_apps` gating flag.

## Data Flow

**Streaming Q&A (primary user flow):**

1. User types or speaks a question in `ChatInterface` (`frontend/components/ChatInterface.tsx`). Speech uses `frontend/hooks/useSpeechRecognition.ts`.
2. `ChatInterface` calls `askQuestionStream()` in `frontend/lib/api.ts`, which POSTs to `/ask/stream` with the `X-Session-ID` header and `{question, history}` body.
3. `backend/main.py::ask_stream` validates the session header against `UUID_RE`, then iterates `_rag_chain.astream(...)` yielding SSE `data: <token>` frames.
4. For each sentence boundary (`_SENTENCE_ENDINGS` regex), `main.py` spawns `asyncio.create_task(avatar_module.speak_on_avatar(sentence, sid))` so TTS runs in parallel with further token streaming.
5. `avatar.speak_on_avatar` calls `tts.synthesize_pcm` (Azure → gTTS fallback) and streams the PCM bytes over the session's persistent LiveAvatar WebSocket.
6. Browser's `askQuestionStream` reader parses the SSE stream, calls `onToken` per token for live rendering and `onDone(latency_ms)` on `[DONE]`.
7. Audio arrives in the browser via LiveKit's WebRTC room managed by `frontend/components/VideoPlayer.tsx`.

**Session bootstrap (WebRTC):**

1. On first render, `frontend/app/page.tsx` calls `initSessionId()` and `ping()`.
2. `VideoPlayer` calls `getSession()` → backend `/session` → `avatar.get_or_create_user_session` → `avatar.get_or_create_liveavatar_session` (which hits LiveAvatar REST API).
3. Backend returns `{session_id, livekit_url, livekit_client_token}` to the browser.
4. `VideoPlayer` uses `livekit-client` `Room.connect(url, token)` and subscribes to track events to attach `<video muted>` and `<audio>` elements.
5. On `beforeunload`, `page.tsx` calls `closeSession()` with `keepalive:true`, triggering DELETE `/session` → `avatar.pop_user_session` cleanup.

**State Management:**
- Frontend: React component state (`useState`, `useRef`) in `page.tsx` (logs, active tab) and `ChatInterface.tsx` (messages, streaming text). No Redux/Zustand.
- Backend: In-memory dict `_user_sessions` in `backend/avatar.py` guarded by `_user_sessions_lock` (asyncio). Per-session `speak_lock` serialises WebSocket writes. Evicted after `SESSION_IDLE_TTL` (120s) by background `evict_idle_sessions` task.
- Persistence across reloads: `localStorage` keys `aicv_session_id` (session UUID) and `aicv_intro_played` (intro-video flag) — defined in `frontend/lib/api.ts` and `frontend/app/page.tsx`.

## Key Abstractions

**`UserSession` dataclass:**
- Purpose: Per-tab avatar session state (LiveAvatar creds, WS handle, locks, activity timestamp, interrupted flag).
- Location: `backend/avatar.py`
- Pattern: Dataclass + asyncio.Lock; stored in module-level `_user_sessions` dict.

**LangChain LCEL RAG chain (`_rag_chain`):**
- Purpose: The unit of inference. `dict → prompt → llm → parser`.
- Location: `backend/rag.py::build_rag_chain()`
- Pattern: `RunnableSerializable`; supports both `.invoke()` (sync Q&A) and `.astream()` (SSE token stream).

**Provider Factory pattern:**
- Purpose: Select chat LLM and embedding model at startup based on `LLM_PROVIDER`.
- Location: `backend/rag.py::_create_llm()`, `_create_embeddings()`, `_create_vectorstore()`
- Pattern: Strategy/factory functions returning concrete LangChain primitives; Azure path optionally uses `azure-identity` `DefaultAzureCredential` when API key absent.

**Pydantic request/response models:**
- Purpose: Validation + OpenAPI schema generation.
- Location: `backend/models.py`
- Examples: `AskRequest`, `AskResponse`, `HealthResponse`, `SpeakRequest`, `HistoryMessage`.

**Typed API client:**
- Purpose: Single surface for every backend call from the browser, with SSE parsing built in.
- Location: `frontend/lib/api.ts`
- Pattern: Module-level functions sharing a top-level `sessionId` variable initialised in `initSessionId()`.

**Diagram viewer abstraction:**
- Purpose: Pan/zoom inline SVG rendering for C4 diagrams.
- Location: `frontend/components/DiagramViewer.tsx` (consumed by `frontend/components/C4DiagramsSection.tsx`).
- Source of truth: `c4/workspace.dsl` → `pwsh c4/export-diagrams.ps1` → `frontend/public/diagrams/*.mmd/svg`.

## Entry Points

**Frontend root (browser):**
- Location: `frontend/app/layout.tsx` (metadata, GA injection, `<html>` shell) → `frontend/app/page.tsx` (Home client component with tab router).
- Triggers: Browser navigation to `/`.
- Responsibilities: Mount `VideoPlayer`, `ChatInterface`, `DevConsole`, `ArchitectureSection`, `C4DiagramsSection`, `DesignSection`; initialise session ID; wire `beforeunload` cleanup.

**Backend ASGI app:**
- Location: `backend/main.py::app` (FastAPI instance).
- Triggers: `uvicorn main:app --reload --port 8000` (local) or container start on Azure Container Apps.
- Responsibilities: `lifespan` bootstraps `tts.http_client`, builds `_rag_chain`, optionally pre-synthesises filler phrases, starts `evict_idle_sessions` background task. Registers `SlowAPIMiddleware` (20 req/min/IP) and `CORSMiddleware` (origins from `ALLOWED_ORIGINS`).

**Container images:**
- Backend: `backend/Dockerfile`
- Frontend: `frontend/Dockerfile` (optional; production uses Azure Static Web Apps static export via `NEXT_OUTPUT=export` in `frontend/next.config.ts`).

**Local-dev orchestrator:**
- Location: `setup-local.ps1`, `docker-compose.yml` (Qdrant only; Ollama commented out).

**Infra bootstrap:**
- Location: `infra/terraform/bootstrap/main.tf` (creates TF state storage) → `infra/terraform/main.tf` (all Azure resources).

## Error Handling

**Strategy:** FastAPI `HTTPException` for request errors; broad `except` with `logger.error(..., exc_info=True)` for background/streaming paths; graceful degradation to mock mode when keys are absent.

**Patterns:**
- Route handlers raise `HTTPException(status_code=..., detail=...)`. See `backend/main.py::ask` (503 when `_rag_chain is None`, 500 on inference error) and `get_session` (502 mapping for `httpx.HTTPStatusError` / `httpx.RequestError`).
- SSE error frames: `ask_stream` yields `data: [ERROR] <json-message>\n\n` on exceptions, leaving the connection open long enough to flush.
- `avatar.py` invalidates `UserSession` on 401/403 via `entry.invalidate(...)` to force re-auth on next request.
- Frontend `frontend/lib/api.ts::handleResponse` throws `Error(detail)` parsed from JSON `detail` field; components catch and push to `DevConsole` via `onLog`.
- Mock fallbacks: `/session` returns a mock when `LIVEAVATAR_API_KEY` is empty; `/speak` returns `{"status":"mock"}`. TTS falls back from Azure to gTTS when `AZURE_SPEECH_KEY` absent.

## Cross-Cutting Concerns

**Logging:**
- Configured once in `backend/config.py` with `logging.basicConfig(level=INFO, format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s")`.
- Each module uses `logger = logging.getLogger(__name__)`.
- Frontend logging: user-facing events flow through `DevConsole` via an `onLog(message, level, step)` callback defined in `frontend/app/page.tsx`; analytics via `frontend/lib/analytics.ts` (Google Analytics 4 `gtag`).

**Validation:**
- Pydantic v2 models in `backend/models.py` validate all request bodies (`min_length`, `max_length`, `pattern`, `field_validator`).
- Session ID header validated against `UUID_RE` regex in `backend/config.py`; invalid IDs fall back to the string `"anonymous"`.

**Authentication / Authorisation:**
- Public service; there is no end-user auth. Abuse mitigated by `SlowAPIMiddleware` rate limit (20 req/min/IP, `backend/main.py`).
- Server-to-cloud auth: Azure OpenAI via API key or `DefaultAzureCredential` Managed Identity (`backend/rag.py`); Azure Speech via `Ocp-Apim-Subscription-Key` header (`backend/tts.py`); LiveAvatar via API key in config.
- CORS: `backend/main.py` allows only origins listed in `ALLOWED_ORIGINS` env var (default `http://localhost:3000`), methods restricted to `GET, POST, DELETE`, headers to `Content-Type, X-Session-ID`.

**Security headers:** Set by Next.js in `frontend/next.config.ts::headers()` — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.

**Concurrency:**
- Backend is fully async (FastAPI + `httpx.AsyncClient` + `websockets` + `asyncio.Lock`).
- Persistent outbound HTTP: `tts.http_client` (module-level `httpx.AsyncClient`) with connection pool `max_connections=20`.
- Background work: `asyncio.create_task` for per-sentence TTS, session eviction loop, filler pre-warming.

---

*Architecture analysis: 2026-04-22*
