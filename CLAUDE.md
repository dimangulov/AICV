<!-- GSD:project-start source:PROJECT.md -->
## Project

**Interactive Digital Twin CV — Project Context**

A web-based interactive résumé where a photorealistic digital twin (LiveAvatar.com WebRTC stream) answers questions about the candidate using a RAG pipeline over `backend/bio.txt`. Dual-mode LLM backend: Ollama (local) or Azure OpenAI (cloud). Streams answers via SSE with sentence-level TTS to the avatar WebSocket.

**Stack:**
- Frontend: Next.js 16 (App Router), React 19, Tailwind v4, TypeScript strict, deployed to Azure Static Web Apps
- Backend: FastAPI / Python 3.12, LangChain LCEL, Azure Container Apps (scale-to-0)
- Data: Qdrant vector DB (`cv_knowledge_base` collection)
- LLM: Ollama (local, `llama3.2` + `nomic-embed-text`) or Azure OpenAI (`gpt-4o-mini` + `text-embedding-3-small`)
- Avatar: LiveAvatar.com WebRTC (SaaS); mock mode when `LIVEAVATAR_API_KEY` empty
- TTS: Azure Speech REST (neural voice) with gTTS fallback
- IaC: Terraform (`azurerm ~> 3.116`) — SWA, Container Apps, Azure OpenAI, Speech, Log Analytics, ACR, Managed Identity
- CI/CD: GitHub Actions with OIDC federated credentials, 4-job deploy pipeline

Full architecture: `DESIGN.md` (C4 diagrams) and `.planning/codebase/` maps.

---
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 — Backend FastAPI service (`backend/`)
- TypeScript 5 — Next.js frontend (`frontend/`)
- HCL (Terraform ~1.9) — Infrastructure as code (`infra/terraform/`)
- PowerShell — Local setup script (`setup-local.ps1`)
- Dockerfile — Container definitions (`backend/Dockerfile`, `frontend/Dockerfile`)
- YAML — CI/CD (`.github/workflows/deploy-azure.yml`) and Docker Compose (`docker-compose.yml`)
## Runtime
- Python 3.12 (slim base image in `backend/Dockerfile`) — FastAPI served by Uvicorn single worker on port 8000
- Node.js 20 Alpine (per `frontend/Dockerfile`) — Next.js 16 SSR / static export on port 3000
- Docker Engine — Qdrant (`qdrant/qdrant:latest`) via `docker-compose.yml`
- pip (Python) — `backend/requirements.txt` (pinned versions, no lockfile)
- pnpm (Node.js) — `frontend/pnpm-lock.yaml` present; enabled via corepack in Dockerfile
- npm — `frontend/package-lock.json` also present (dual lockfiles)
## Frameworks
- FastAPI 0.115.6 — HTTP API (`backend/main.py`)
- Uvicorn 0.32.1 `[standard]` — ASGI server
- Pydantic 2.10.4 — Request/response models (`backend/models.py`)
- SlowAPI 0.1.9 — Rate limiting middleware (`20/minute` default in `backend/main.py`)
- Next.js 16.1.6 — React framework (`frontend/next.config.ts`); supports `output: "export"` static mode via `NEXT_OUTPUT=export`
- React 19 + React-DOM 19
- Tailwind CSS 3.4.1 — styling (`frontend/tailwind.config.ts`)
- PostCSS 8 + Autoprefixer 10.4.20
- LangChain 0.3.13 (`langchain`, `langchain-core` 0.3.63, `langchain-community` 0.3.13, `langchain-text-splitters` 0.3.4)
- `langchain-ollama` 0.2.3 — local LLM path (`backend/rag.py`)
- `langchain-openai` 0.3.7 — Azure OpenAI path (`backend/rag.py`)
- Not detected. No pytest, vitest, jest, or equivalent in dependency manifests.
- TypeScript 5 — `frontend/tsconfig.json` (strict mode, `@/*` path alias, `moduleResolution: bundler`)
- Next ESLint — `next lint` script
- `@tailwindcss/typography` 0.5.19 — prose plugin
## Key Dependencies
- `httpx` 0.28.1 — Async HTTP client (LiveAvatar, Azure TTS, Ollama health checks)
- `qdrant-client` 1.12.1 — Vector DB client (in-memory / Docker / Qdrant Cloud modes)
- `websockets` 13.1 — WebSocket client for LiveAvatar LITE audio stream
- `python-dotenv` 1.0.1 — `.env` loading in `backend/config.py`
- `azure-identity` 1.19.0 — `DefaultAzureCredential` / Managed Identity for keyless Azure OpenAI
- `gTTS` 2.5.3 — Google TTS fallback for local dev (no credentials)
- `miniaudio` 1.2 — MP3 → PCM (16-bit 24 kHz) without ffmpeg; requires `-Wno-implicit-function-declaration` CFLAG on gcc 14
- Azure Cognitive Services Speech — used via `httpx` REST call, no extra SDK package
- `livekit-client` 2.17.3 — WebRTC client for LiveAvatar rooms (`frontend/components/VideoPlayer.tsx`)
- `lucide-react` 0.468.0 — Icon set
- `react-markdown` 10.1.0 + `remark-gfm` 4.0.1 + `rehype-highlight` 7.0.2 + `highlight.js` 11.11.1 — DESIGN.md rendering
- `mermaid` 11.13.0 — C4 diagram rendering (`frontend/components/Mermaid.tsx`, `DiagramViewer.tsx`)
- `azurerm` provider ~3.116 — Terraform Azure provider (`infra/terraform/versions.tf`)
## Configuration
- `backend/.env` — loaded by `python-dotenv` in `backend/config.py` (contents never read; existence only noted). Template: `backend/.env.example`.
- `frontend/.env.local` — Next.js public vars. Template: `frontend/.env.local.example`.
- `backend/config.py` — Centralised `os.getenv` calls. Other modules import constants from here.
- Key variables: `LLM_PROVIDER` (ollama|azure_openai), `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (llama3.2), `EMBED_MODEL` (nomic-embed-text), `AZURE_OPENAI_ENDPOINT/API_KEY/API_VERSION/CHAT_DEPLOYMENT/EMBED_DEPLOYMENT`, `QDRANT_MODE` (memory|docker|cloud), `QDRANT_URL`, `QDRANT_CLOUD_URL/API_KEY`, `LIVEAVATAR_API_KEY/AVATAR_ID/SESSION_MODE/IS_SANDBOX/VOICE`, `AZURE_SPEECH_KEY/REGION`, `ALLOWED_ORIGINS`, `MAX_SESSIONS`, `ENABLE_FILLERS`.
- `NEXT_PUBLIC_API_URL` — backend origin (`frontend/lib/api.ts`)
- `NEXT_PUBLIC_GA_MEASUREMENT_ID` — Google Analytics 4 ID (`frontend/app/layout.tsx`)
- `NEXT_OUTPUT` — switches to static export mode (`frontend/next.config.ts`)
- `frontend/tsconfig.json` — `strict: true`, `target: ES2017`, `jsx: react-jsx`, `paths: { "@/*": ["./*"] }`
- `frontend/tailwind.config.ts` — `darkMode: "class"`, custom `brand` palette, custom keyframes (`fadeIn`), `@tailwindcss/typography` plugin.
- `frontend/next.config.ts` — conditional static export, security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`), image `remotePatterns` allowing `*.liveavatar.com`.
## Build Tools
- `backend/Dockerfile` — single-stage `python:3.12-slim` with `curl`, `build-essential`; pip installs `requirements.txt` with miniaudio CFLAG workaround; `HEALTHCHECK` hits `/health`.
- `frontend/Dockerfile` — 3-stage (deps → builder → runner) on `node:20-alpine`, corepack + pnpm frozen lockfile, runs as non-root `nextjs:1001`.
- `frontend/package.json` `predev`/`prebuild` — copies root `DESIGN.md` into `frontend/public/DESIGN.md` for in-app rendering.
## Platform Requirements
- Node.js ≥ 20
- pnpm ≥ 9
- Python ≥ 3.11 (3.12 used in container)
- Docker Desktop
- Ollama (local LLM runtime, pulls `llama3.2` and `nomic-embed-text`)
- Chrome or Edge browser required — `webkitSpeechRecognition` not supported in Firefox (`frontend/hooks/useSpeechRecognition.ts`)
- Azure Container Apps (consumption plan, scale-to-zero, min 0 / max 3 replicas) — backend
- Azure Static Web Apps (Free tier) — frontend static export, custom domain `dimangulov.space`
- Azure Container Registry Basic — image hosting
- Azure OpenAI (Sweden Central) — `gpt-4o-mini` chat + `text-embedding-3-small`
- Azure Cognitive Services Speech (F0 free tier, default region `westeurope`)
- Azure Log Analytics (PerGB2018, 30-day retention)
- Qdrant Cloud (free 1-cluster tier)
- Azure Blob Storage — Terraform remote state (`rg-aicv-tfstate` / container `tfstate` / key `prod.terraform.tfstate`)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Linter & Formatter Configuration
### Frontend (TypeScript / React / Next.js)
- Next.js built-in ESLint via `next lint` (script defined in `frontend/package.json`)
- No `.eslintrc*` or `eslint.config.*` file present — relies entirely on the default Next.js preset (`next/core-web-vitals` etc.)
- No custom rule overrides
- No Prettier configuration (`.prettierrc*` or `prettier.config.*`) present
- No EditorConfig (`.editorconfig`) file present
- Code style is enforced implicitly by editor defaults and the shared Next.js ESLint preset
- `strict: true` — all strict type-checking flags enabled
- `target: "ES2017"`, `module: "esnext"`, `moduleResolution: "bundler"`
- `jsx: "react-jsx"` — no explicit React import required
- `noEmit: true` — Next.js handles emission
- Path alias: `@/*` → project root (enables `@/components/...`, `@/lib/...`, `@/hooks/...`, `@/types`)
### Backend (Python)
- No `pyproject.toml`, `ruff.toml`, `setup.cfg`, `.flake8`, `pyright.json`, or `mypy.ini` present
- No Black, Ruff, isort, Flake8, or mypy configured
- Dependencies managed via `backend/requirements.txt` (flat, pinned versions) — not Poetry/uv/Hatch
- PEP 8 spacing, 4-space indentation
- Line length generally < 100 chars, occasional long log strings broken with implicit concatenation
- `from __future__ import annotations` at the top of every module (`backend/main.py`, `backend/config.py`, `backend/rag.py`, `backend/tts.py`, `backend/avatar.py`, `backend/models.py`)
- Module-level docstring describing responsibilities on every Python file
## Naming Patterns
### Frontend
- React components: `PascalCase.tsx` (e.g., `ChatInterface.tsx`, `VideoPlayer.tsx`, `DevConsole.tsx`, `Mermaid.tsx`) in `frontend/components/`
- Hooks: `useCamelCase.ts` (e.g., `useSpeechRecognition.ts`, `useAvatarAudioGate.ts`) in `frontend/hooks/`
- Library modules: `camelCase.ts` (e.g., `api.ts`, `analytics.ts`) in `frontend/lib/`
- Type barrel: `frontend/types/index.ts`
- Next.js App Router: `page.tsx`, `layout.tsx`, `globals.css` in `frontend/app/`
- Functions and variables: `camelCase` (`handleQuestion`, `buildHistory`, `askQuestionStream`)
- React components: `PascalCase` default exports
- Constants: `SCREAMING_SNAKE_CASE` at module top (`const SUGGESTED_QUESTIONS`, `const INTRO_PLAYED_KEY`, `const SESSION_STORAGE_KEY`, `const PAGE_SIZE`)
- Private module mutables: leading underscore (`let _msgId = 0;`, `let _logId = 0;` in `frontend/app/page.tsx`, `frontend/components/ChatInterface.tsx`)
- Ref variables: suffix `Ref` (`messagesRef`, `isSubmittingRef`, `threadRef`, `handleQuestionRef`)
- `PascalCase` (`LogEntry`, `HistoryMessage`, `ConversationMessage`, `AskRequest`, `AskResponse`, `SessionResponse`)
- Component props: `<ComponentName>Props` (`ChatInterfaceProps`, `VideoPlayerProps`, `DevConsoleProps`)
- Hook return types exported as `Use<Name>Return` (e.g., `UseSpeechRecognitionReturn` in `frontend/hooks/useSpeechRecognition.ts`)
- Hook option types: `Use<Name>Options`
### Backend
- Lowercase single-word module names per responsibility: `main.py`, `config.py`, `models.py`, `rag.py`, `tts.py`, `avatar.py`, `generate_cv.py`
- Functions: `snake_case` (`build_rag_chain`, `format_history`, `speak_on_avatar`, `evict_idle_sessions`, `get_or_create_liveavatar_session`)
- Private helpers: leading underscore (`_create_llm`, `_create_embeddings`, `_format_docs`, `_stream_tts_azure`, `_avatar_ws_loop`, `_stop_liveavatar_session`)
- Constants: `SCREAMING_SNAKE_CASE` (`LIVEAVATAR_BASE_URL`, `MAX_SESSIONS`, `SESSION_IDLE_TTL`, `FILLER_PHRASES`, `UUID_RE`)
- Module-level mutable state: leading underscore (`_rag_chain`, `_user_sessions`, `_user_sessions_lock`, `_LIVEAVATAR_SESSION_TTL`)
- `PascalCase` (`UserSession`, `HistoryMessage`, `AskRequest`, `AskResponse`, `HealthResponse`, `SpeakRequest`)
- Pydantic models live in `backend/models.py` and inherit `BaseModel`
- Dataclasses use `@dataclass` (`UserSession` in `backend/avatar.py`)
## Import Organization
### Frontend
### Backend
## Error Handling
### Frontend (`frontend/lib/api.ts`)
- All fetch wrappers route through a single `handleResponse<T>()` helper that:
- Callers decide whether to `.catch()` (fire-and-forget, e.g., `interruptSpeech().catch(() => {});`) or surface the error to the UI
- Streaming endpoints (`askQuestionStream`) accept explicit `onError` callbacks instead of throwing, allowing partial-response UX
- Ambient safety calls use `.catch(() => {})` to silence expected failures (e.g., keepalive pings)
### Backend (`backend/main.py`)
- Every endpoint wraps business logic in `try/except` and raises `HTTPException` with:
- Always preserves the exception chain with `from exc`
- Logs the exception with `exc_info=True` before raising
- Rate-limiting handled declaratively via `slowapi` (`limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])`)
- Streaming endpoints yield SSE `[ERROR]` events on exception instead of raising (preserves connection)
- Background tasks use bare `try/except Exception` and swallow errors after logging (`# noqa: BLE001` on broad excepts in `backend/avatar.py`)
## Logging
### Frontend
- No logging library — uses `console` indirectly via a custom `DevConsole` component (`frontend/components/DevConsole.tsx`)
- Log entries flow through parent-passed `onLog(message, level, step)` callbacks typed as `LogEntry` in `frontend/types/index.ts`
- Levels: `"info" | "success" | "warning" | "error"`
- Pipeline step numbers (0–4) tagged on each log to represent Listening / RAG / Inference / Response
- Analytics events emitted via `trackEvent()` in `frontend/lib/analytics.ts` when GA4 is configured
### Backend
- Python stdlib `logging` configured once in `backend/config.py`:
- Every module creates its own logger: `logger = logging.getLogger(__name__)`
- Log prefix convention: `[subsystem]` bracket tag, e.g., `[speak]`, `[filler]`, `[session]`, `[evict]`, `[interrupt]`, `[avatar_ws]`
- Use `%`-style formatting in log calls (`logger.info("Stream answered in %dms: %r", elapsed_ms, ...)`) — never f-strings in log calls
- Errors log with `exc_info=True` to capture tracebacks
## Comments & Docstrings
### Frontend
- JSDoc-style block comments on exported hooks, types, and API functions (see `frontend/hooks/useSpeechRecognition.ts`, `frontend/lib/api.ts`)
- Inline section dividers using `/* ── Section name ──... ─ */` for visually segmenting long JSX trees
- Inline comments explain non-obvious rationale (e.g., stale-closure guards, iOS autoplay workarounds, keepalive:true on unload)
### Backend
- Module-level triple-quoted docstring on every file describing responsibilities
- Function docstrings describe behavior, parameters, and important edge cases
- Section dividers: `# ------...` followed by a title then another divider
- Security-relevant constants flagged in comments (e.g., "Fixed URL — never derived from user input to prevent SSRF" in `backend/config.py`)
## Function & Module Design
### Frontend
- Functional React components only — no class components
- Components are default-exported; supporting types/interfaces are named-exported or colocated
- Hooks heavily favoured for side-effect management; refs used to break stale-closure traps (see `handleQuestionRef` pattern in `frontend/components/ChatInterface.tsx`)
- Callbacks wrapped in `useCallback` when passed to other hooks
- State updates use functional form `(prev) => ...` when reading previous state
- No barrel index files for components — each component imported directly from its path
- `frontend/types/index.ts` is the only barrel — central shared types
### Backend
- Async-first: every I/O-bound function is `async def`
- Module-level singletons (`_rag_chain`, `_user_sessions`, `http_client`) initialised in FastAPI `lifespan`
- `asyncio.Lock` guards mutable shared state (`_user_sessions_lock`, `UserSession.session_lock`, `UserSession.speak_lock`)
- Pydantic models with `Field(..., min_length=1, max_length=N)` validate all user input
- `@field_validator` decorators strip and truncate user-supplied strings (`AskRequest.strip_and_truncate`)
- Factory functions (prefix `_create_*`) encapsulate provider branching (Ollama vs Azure OpenAI)
- Dispatcher pattern for TTS: `synthesize_pcm()` → Azure → gTTS → error
## Dependency Organization
### Frontend (`frontend/package.json`)
- Runtime deps under `dependencies`, build/types under `devDependencies`
- Lockfile: `pnpm-lock.yaml` is the authoritative lockfile (committed); `package-lock.json` also present
- Scripts: `dev`, `build`, `start`, `lint`, plus `predev` / `prebuild` that copy `DESIGN.md` into `public/` for markdown rendering
- Versions pinned with `^` (caret ranges)
### Backend (`backend/requirements.txt`)
- Single flat, pinned file (`==` exact pins, no ranges)
- Grouped with comments: FastAPI core, LangChain ecosystem, Qdrant, Azure identity, TTS pipeline
- Optional providers (Ollama vs Azure OpenAI) both installed; chosen at runtime by `LLM_PROVIDER` env var
## Security & Input Validation
- All session IDs validated against `UUID_RE` regex in `backend/config.py` before use; invalid values fall back to `"anonymous"`
- External hostnames hardcoded as constants (`LIVEAVATAR_BASE_URL`) to prevent SSRF
- CORS configured explicitly via `ALLOWED_ORIGINS` env var parsed in `backend/config.py`
- Rate limit enforced globally at `20/minute` via `slowapi`
- Frontend response headers hardened in `frontend/next.config.ts`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`
- Secrets sourced exclusively from env vars / `.env` (gitignored); managed-identity preferred over API keys in Azure deployment
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Decoupled frontend (`frontend/`) and backend (`backend/`) talk only via HTTP/SSE; no shared runtime.
- Dual-mode LLM provider pattern: swap local Ollama for cloud Azure OpenAI via the single `LLM_PROVIDER` env var in `backend/config.py`.
- RAG pipeline implemented as a LangChain LCEL chain: retriever → prompt → LLM → parser. Built once at startup in `backend/rag.py`.
- Streaming-first: `/ask/stream` emits SSE tokens while simultaneously fanning out sentence-level TTS tasks, minimising perceived latency.
- Per-user session state held in-memory on the backend (no shared DB for sessions); sessions keyed by `X-Session-ID` UUID header.
- Authoritative C4 diagrams defined in DSL at `c4/workspace.dsl`; exported artefacts consumed by the frontend for the "C4 Diagrams" tab.
- Infrastructure-as-code: Terraform (`infra/terraform/`) provisions all Azure resources; GitHub Actions (`.github/workflows/deploy-azure.yml`) orchestrates the pipeline.
## Layers
- Purpose: React components, hooks, and browser-side state; WebRTC/WebSpeech integration.
- Location: `frontend/app/`, `frontend/components/`, `frontend/hooks/`
- Contains: React Client Components (`"use client"`), tab navigation, chat UI, video player, dev console, C4/design viewers.
- Depends on: `frontend/lib/api.ts` (API client), `frontend/types/index.ts` (shared types), `livekit-client` SDK, browser APIs (`webkitSpeechRecognition`, `localStorage`, `crypto.randomUUID`).
- Used by: The user's browser only.
- Purpose: Typed `fetch` wrappers that front every backend endpoint and manage the per-tab session UUID.
- Location: `frontend/lib/api.ts`
- Contains: `askQuestion`, `askQuestionStream` (SSE reader), `getSession`, `speakText`, `interruptSpeech`, `closeSession`, `ping`, `getHealth`; `initSessionId`/`resetSessionId` managing `aicv_session_id` in `localStorage`.
- Depends on: `process.env.NEXT_PUBLIC_API_URL`, `frontend/types/index.ts`.
- Used by: Every component that touches the backend (`VideoPlayer`, `ChatInterface`, `page.tsx`).
- Purpose: FastAPI route handlers, validation, CORS, rate limiting, session-header parsing.
- Location: `backend/main.py`
- Contains: `/ask`, `/ask/stream`, `/speak`, `/interrupt`, `/session` (GET and DELETE), `/ping`, `/health`. `lifespan` context manager wires startup/shutdown.
- Depends on: `backend/models.py` (Pydantic), `backend/rag.py`, `backend/avatar.py`, `backend/tts.py`, `backend/config.py`.
- Used by: Browser via `frontend/lib/api.ts`.
- Purpose: Load `backend/bio.txt`, chunk/embed/index, build the LCEL chain, execute retrieval and generation.
- Location: `backend/rag.py`
- Contains: `_create_llm()`, `_create_embeddings()`, `_create_vectorstore()`, `_format_docs()`, `format_history()`, `build_rag_chain()`.
- Depends on: `langchain`, `langchain-ollama`, `langchain-openai`, `qdrant-client`, constants from `backend/config.py`.
- Used by: `backend/main.py` (chain invoked in `/ask` and streamed in `/ask/stream`).
- Purpose: Per-user LiveAvatar session lifecycle, persistent WebSocket audio delivery, interrupts, idle eviction.
- Location: `backend/avatar.py`
- Contains: `UserSession` dataclass, `_user_sessions` in-memory store (with `_user_sessions_lock`), `get_or_create_user_session`, `get_or_create_liveavatar_session`, `speak_on_avatar`, `evict_idle_sessions`, `warm_fillers`, `pick_filler`, filler phrase cache.
- Depends on: `backend/tts.py`, `backend/config.py`, `httpx`, `websockets`.
- Used by: `/session`, `/speak`, `/interrupt`, `/ask` (background task), `/ask/stream` (per-sentence tasks).
- Purpose: Synthesise text to 16-bit mono 24 kHz PCM for LiveAvatar ingestion.
- Location: `backend/tts.py`
- Contains: `_stream_tts_azure()` (SSML → Azure Cognitive Services REST streaming), `_synthesize_pcm_azure`, `_synthesize_pcm_gtts` (gTTS+miniaudio fallback), `synthesize_pcm` dispatcher, module-level `http_client: httpx.AsyncClient` initialised in `main.lifespan`.
- Depends on: `backend/config.py` (`AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `LIVEAVATAR_VOICE`), `httpx`, `miniaudio`, optional `gtts`.
- Used by: `backend/avatar.py`.
- Purpose: Central, single-source env-var resolution and logging setup.
- Location: `backend/config.py`
- Contains: All `os.getenv(...)` reads, `load_dotenv()`, `BIO_FILE_PATH`, `COLLECTION_NAME`, `ALLOWED_ORIGINS`, `UUID_RE`, `MAX_SESSIONS`, `SESSION_IDLE_TTL`.
- Depends on: `python-dotenv`.
- Used by: Every other backend module (the module comment forbids `os.getenv` elsewhere).
- Purpose: Store and retrieve embedded chunks of `backend/bio.txt`.
- Location: Qdrant in three modes, selected via `QDRANT_MODE`:
- Collection: `cv_knowledge_base` (cosine; 768-dim Ollama or 1536-dim Azure).
- Purpose: Provision and deploy Azure resources.
- Location: `infra/terraform/` (+ bootstrap at `infra/terraform/bootstrap/`), `.github/workflows/deploy-azure.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `setup-local.ps1`.
- Contains: `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `terraform.tfvars`, plus the `enable_container_apps` gating flag.
## Data Flow
- Frontend: React component state (`useState`, `useRef`) in `page.tsx` (logs, active tab) and `ChatInterface.tsx` (messages, streaming text). No Redux/Zustand.
- Backend: In-memory dict `_user_sessions` in `backend/avatar.py` guarded by `_user_sessions_lock` (asyncio). Per-session `speak_lock` serialises WebSocket writes. Evicted after `SESSION_IDLE_TTL` (120s) by background `evict_idle_sessions` task.
- Persistence across reloads: `localStorage` keys `aicv_session_id` (session UUID) and `aicv_intro_played` (intro-video flag) — defined in `frontend/lib/api.ts` and `frontend/app/page.tsx`.
## Key Abstractions
- Purpose: Per-tab avatar session state (LiveAvatar creds, WS handle, locks, activity timestamp, interrupted flag).
- Location: `backend/avatar.py`
- Pattern: Dataclass + asyncio.Lock; stored in module-level `_user_sessions` dict.
- Purpose: The unit of inference. `dict → prompt → llm → parser`.
- Location: `backend/rag.py::build_rag_chain()`
- Pattern: `RunnableSerializable`; supports both `.invoke()` (sync Q&A) and `.astream()` (SSE token stream).
- Purpose: Select chat LLM and embedding model at startup based on `LLM_PROVIDER`.
- Location: `backend/rag.py::_create_llm()`, `_create_embeddings()`, `_create_vectorstore()`
- Pattern: Strategy/factory functions returning concrete LangChain primitives; Azure path optionally uses `azure-identity` `DefaultAzureCredential` when API key absent.
- Purpose: Validation + OpenAPI schema generation.
- Location: `backend/models.py`
- Examples: `AskRequest`, `AskResponse`, `HealthResponse`, `SpeakRequest`, `HistoryMessage`.
- Purpose: Single surface for every backend call from the browser, with SSE parsing built in.
- Location: `frontend/lib/api.ts`
- Pattern: Module-level functions sharing a top-level `sessionId` variable initialised in `initSessionId()`.
- Purpose: Pan/zoom inline SVG rendering for C4 diagrams.
- Location: `frontend/components/DiagramViewer.tsx` (consumed by `frontend/components/C4DiagramsSection.tsx`).
- Source of truth: `c4/workspace.dsl` → `pwsh c4/export-diagrams.ps1` → `frontend/public/diagrams/*.mmd/svg`.
## Entry Points
- Location: `frontend/app/layout.tsx` (metadata, GA injection, `<html>` shell) → `frontend/app/page.tsx` (Home client component with tab router).
- Triggers: Browser navigation to `/`.
- Responsibilities: Mount `VideoPlayer`, `ChatInterface`, `DevConsole`, `ArchitectureSection`, `C4DiagramsSection`, `DesignSection`; initialise session ID; wire `beforeunload` cleanup.
- Location: `backend/main.py::app` (FastAPI instance).
- Triggers: `uvicorn main:app --reload --port 8000` (local) or container start on Azure Container Apps.
- Responsibilities: `lifespan` bootstraps `tts.http_client`, builds `_rag_chain`, optionally pre-synthesises filler phrases, starts `evict_idle_sessions` background task. Registers `SlowAPIMiddleware` (20 req/min/IP) and `CORSMiddleware` (origins from `ALLOWED_ORIGINS`).
- Backend: `backend/Dockerfile`
- Frontend: `frontend/Dockerfile` (optional; production uses Azure Static Web Apps static export via `NEXT_OUTPUT=export` in `frontend/next.config.ts`).
- Location: `setup-local.ps1`, `docker-compose.yml` (Qdrant only; Ollama commented out).
- Location: `infra/terraform/bootstrap/main.tf` (creates TF state storage) → `infra/terraform/main.tf` (all Azure resources).
## Error Handling
- Route handlers raise `HTTPException(status_code=..., detail=...)`. See `backend/main.py::ask` (503 when `_rag_chain is None`, 500 on inference error) and `get_session` (502 mapping for `httpx.HTTPStatusError` / `httpx.RequestError`).
- SSE error frames: `ask_stream` yields `data: [ERROR] <json-message>\n\n` on exceptions, leaving the connection open long enough to flush.
- `avatar.py` invalidates `UserSession` on 401/403 via `entry.invalidate(...)` to force re-auth on next request.
- Frontend `frontend/lib/api.ts::handleResponse` throws `Error(detail)` parsed from JSON `detail` field; components catch and push to `DevConsole` via `onLog`.
- Mock fallbacks: `/session` returns a mock when `LIVEAVATAR_API_KEY` is empty; `/speak` returns `{"status":"mock"}`. TTS falls back from Azure to gTTS when `AZURE_SPEECH_KEY` absent.
## Cross-Cutting Concerns
- Configured once in `backend/config.py` with `logging.basicConfig(level=INFO, format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s")`.
- Each module uses `logger = logging.getLogger(__name__)`.
- Frontend logging: user-facing events flow through `DevConsole` via an `onLog(message, level, step)` callback defined in `frontend/app/page.tsx`; analytics via `frontend/lib/analytics.ts` (Google Analytics 4 `gtag`).
- Pydantic v2 models in `backend/models.py` validate all request bodies (`min_length`, `max_length`, `pattern`, `field_validator`).
- Session ID header validated against `UUID_RE` regex in `backend/config.py`; invalid IDs fall back to the string `"anonymous"`.
- Public service; there is no end-user auth. Abuse mitigated by `SlowAPIMiddleware` rate limit (20 req/min/IP, `backend/main.py`).
- Server-to-cloud auth: Azure OpenAI via API key or `DefaultAzureCredential` Managed Identity (`backend/rag.py`); Azure Speech via `Ocp-Apim-Subscription-Key` header (`backend/tts.py`); LiveAvatar via API key in config.
- CORS: `backend/main.py` allows only origins listed in `ALLOWED_ORIGINS` env var (default `http://localhost:3000`), methods restricted to `GET, POST, DELETE`, headers to `Content-Type, X-Session-ID`.
- Backend is fully async (FastAPI + `httpx.AsyncClient` + `websockets` + `asyncio.Lock`).
- Persistent outbound HTTP: `tts.http_client` (module-level `httpx.AsyncClient`) with connection pool `max_connections=20`.
- Background work: `asyncio.create_task` for per-sentence TTS, session eviction loop, filler pre-warming.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
