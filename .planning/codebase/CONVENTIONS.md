# Coding Conventions

**Analysis Date:** 2026-04-22

## Linter & Formatter Configuration

### Frontend (TypeScript / React / Next.js)

**Linting:**
- Next.js built-in ESLint via `next lint` (script defined in `frontend/package.json`)
- No `.eslintrc*` or `eslint.config.*` file present — relies entirely on the default Next.js preset (`next/core-web-vitals` etc.)
- No custom rule overrides

**Formatting:**
- No Prettier configuration (`.prettierrc*` or `prettier.config.*`) present
- No EditorConfig (`.editorconfig`) file present
- Code style is enforced implicitly by editor defaults and the shared Next.js ESLint preset

**TypeScript Configuration:** `frontend/tsconfig.json`
- `strict: true` — all strict type-checking flags enabled
- `target: "ES2017"`, `module: "esnext"`, `moduleResolution: "bundler"`
- `jsx: "react-jsx"` — no explicit React import required
- `noEmit: true` — Next.js handles emission
- Path alias: `@/*` → project root (enables `@/components/...`, `@/lib/...`, `@/hooks/...`, `@/types`)

### Backend (Python)

**Linting / Formatting:**
- No `pyproject.toml`, `ruff.toml`, `setup.cfg`, `.flake8`, `pyright.json`, or `mypy.ini` present
- No Black, Ruff, isort, Flake8, or mypy configured
- Dependencies managed via `backend/requirements.txt` (flat, pinned versions) — not Poetry/uv/Hatch

**Style observed in source files:**
- PEP 8 spacing, 4-space indentation
- Line length generally < 100 chars, occasional long log strings broken with implicit concatenation
- `from __future__ import annotations` at the top of every module (`backend/main.py`, `backend/config.py`, `backend/rag.py`, `backend/tts.py`, `backend/avatar.py`, `backend/models.py`)
- Module-level docstring describing responsibilities on every Python file

## Naming Patterns

### Frontend

**Files:**
- React components: `PascalCase.tsx` (e.g., `ChatInterface.tsx`, `VideoPlayer.tsx`, `DevConsole.tsx`, `Mermaid.tsx`) in `frontend/components/`
- Hooks: `useCamelCase.ts` (e.g., `useSpeechRecognition.ts`, `useAvatarAudioGate.ts`) in `frontend/hooks/`
- Library modules: `camelCase.ts` (e.g., `api.ts`, `analytics.ts`) in `frontend/lib/`
- Type barrel: `frontend/types/index.ts`
- Next.js App Router: `page.tsx`, `layout.tsx`, `globals.css` in `frontend/app/`

**Functions / Variables:**
- Functions and variables: `camelCase` (`handleQuestion`, `buildHistory`, `askQuestionStream`)
- React components: `PascalCase` default exports
- Constants: `SCREAMING_SNAKE_CASE` at module top (`const SUGGESTED_QUESTIONS`, `const INTRO_PLAYED_KEY`, `const SESSION_STORAGE_KEY`, `const PAGE_SIZE`)
- Private module mutables: leading underscore (`let _msgId = 0;`, `let _logId = 0;` in `frontend/app/page.tsx`, `frontend/components/ChatInterface.tsx`)
- Ref variables: suffix `Ref` (`messagesRef`, `isSubmittingRef`, `threadRef`, `handleQuestionRef`)

**Types / Interfaces:**
- `PascalCase` (`LogEntry`, `HistoryMessage`, `ConversationMessage`, `AskRequest`, `AskResponse`, `SessionResponse`)
- Component props: `<ComponentName>Props` (`ChatInterfaceProps`, `VideoPlayerProps`, `DevConsoleProps`)
- Hook return types exported as `Use<Name>Return` (e.g., `UseSpeechRecognitionReturn` in `frontend/hooks/useSpeechRecognition.ts`)
- Hook option types: `Use<Name>Options`

### Backend

**Files:**
- Lowercase single-word module names per responsibility: `main.py`, `config.py`, `models.py`, `rag.py`, `tts.py`, `avatar.py`, `generate_cv.py`

**Functions / Variables:**
- Functions: `snake_case` (`build_rag_chain`, `format_history`, `speak_on_avatar`, `evict_idle_sessions`, `get_or_create_liveavatar_session`)
- Private helpers: leading underscore (`_create_llm`, `_create_embeddings`, `_format_docs`, `_stream_tts_azure`, `_avatar_ws_loop`, `_stop_liveavatar_session`)
- Constants: `SCREAMING_SNAKE_CASE` (`LIVEAVATAR_BASE_URL`, `MAX_SESSIONS`, `SESSION_IDLE_TTL`, `FILLER_PHRASES`, `UUID_RE`)
- Module-level mutable state: leading underscore (`_rag_chain`, `_user_sessions`, `_user_sessions_lock`, `_LIVEAVATAR_SESSION_TTL`)

**Classes:**
- `PascalCase` (`UserSession`, `HistoryMessage`, `AskRequest`, `AskResponse`, `HealthResponse`, `SpeakRequest`)
- Pydantic models live in `backend/models.py` and inherit `BaseModel`
- Dataclasses use `@dataclass` (`UserSession` in `backend/avatar.py`)

## Import Organization

### Frontend
Order observed in source files (e.g., `frontend/components/ChatInterface.tsx`, `frontend/app/page.tsx`):

1. React / Next.js built-ins (`"use client"` directive first when applicable)
2. Third-party packages (`lucide-react`, `livekit-client`, `react-markdown`)
3. Local imports via `@/` path alias:
   - `@/hooks/...`
   - `@/lib/...`
   - `@/components/...`
   - `@/types` (barrel, always with `import type`)
4. `"use client";` directive is mandatory on any file using hooks, event handlers, or browser APIs

Type-only imports use `import type { ... } from "..."` (enforced by `isolatedModules: true`).

### Backend
Order observed in `backend/main.py`, `backend/rag.py`, `backend/avatar.py`:

1. `from __future__ import annotations`
2. Stdlib imports (`asyncio`, `json`, `logging`, `re`, `time`, `uuid`, `pathlib`)
3. Third-party imports (`httpx`, `fastapi`, `langchain_*`, `pydantic`, `slowapi`, `websockets`)
4. Local imports grouped last:
   - `import avatar as avatar_module`
   - `import tts as tts_module`
   - `from config import (...)` — always an explicit, alphabetically-ordered tuple
   - `from models import (...)`
   - `from rag import (...)`

Config imports are centralised — **never call `os.getenv()` outside `backend/config.py`** (documented as a rule in the module docstring).

## Error Handling

### Frontend (`frontend/lib/api.ts`)
- All fetch wrappers route through a single `handleResponse<T>()` helper that:
  - Returns `res.json() as Promise<T>` on 2xx
  - Throws `new Error(detail)` with the backend's `detail` field on non-2xx
- Callers decide whether to `.catch()` (fire-and-forget, e.g., `interruptSpeech().catch(() => {});`) or surface the error to the UI
- Streaming endpoints (`askQuestionStream`) accept explicit `onError` callbacks instead of throwing, allowing partial-response UX
- Ambient safety calls use `.catch(() => {})` to silence expected failures (e.g., keepalive pings)

### Backend (`backend/main.py`)
- Every endpoint wraps business logic in `try/except` and raises `HTTPException` with:
  - `status.HTTP_503_SERVICE_UNAVAILABLE` for missing dependencies (RAG chain not initialised)
  - `status.HTTP_500_INTERNAL_SERVER_ERROR` for inference failures
  - `status.HTTP_502_BAD_GATEWAY` for upstream API failures
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
  ```python
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
  )
  ```
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

---

*Convention analysis: 2026-04-22*
