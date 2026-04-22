# Codebase Structure

**Analysis Date:** 2026-04-22

## Directory Layout

```
aicv/
├── DESIGN.md                         # Canonical architecture design (C4, API, data models)
├── README.md                         # Quick-start, deployment, tech stack
├── docker-compose.yml                # Local Qdrant (+ optional Ollama) service definitions
├── setup-local.ps1                   # Windows PowerShell dev bootstrap script
├── .gitattributes
├── .gitignore
│
├── .github/
│   └── workflows/
│       └── deploy-azure.yml          # Terraform → ACR → Container Apps → SWA pipeline
│
├── backend/                          # FastAPI Python service
│   ├── Dockerfile
│   ├── main.py                       # FastAPI app, routes, lifespan
│   ├── config.py                     # Centralised env-var config + logging setup
│   ├── models.py                     # Pydantic request/response models
│   ├── rag.py                        # LangChain LCEL RAG chain + provider factories
│   ├── tts.py                        # Azure Speech + gTTS TTS pipeline
│   ├── avatar.py                     # LiveAvatar session management + WS streaming
│   ├── bio.txt                       # CV knowledge base (chunked & embedded at startup)
│   ├── damir_imangulov_cv.pdf        # Source PDF for bio
│   ├── generate_cv.py                # Helper to regenerate bio.txt from PDF
│   └── requirements.txt              # Python dependencies
│
├── frontend/                         # Next.js 16 App Router TypeScript app
│   ├── Dockerfile
│   ├── package.json                  # pnpm-managed deps (React 19, next 16, livekit-client…)
│   ├── pnpm-lock.yaml
│   ├── package-lock.json
│   ├── next.config.ts                # Static-export toggle, security headers, image config
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── tsconfig.json
│   ├── next-env.d.ts
│   ├── app/
│   │   ├── layout.tsx                # Root layout, GA script, metadata
│   │   ├── page.tsx                  # Home (tabbed: Chat / Architecture / C4 / Design)
│   │   └── globals.css               # Tailwind base + custom scrollbar/mermaid styles
│   ├── components/
│   │   ├── VideoPlayer.tsx           # LiveKit WebRTC avatar room + mock canvas stream
│   │   ├── ChatInterface.tsx         # PTT + text input + SSE streaming renderer
│   │   ├── DevConsole.tsx            # Collapsible log panel
│   │   ├── ArchitectureSection.tsx   # Tech-stack / layer overview tab
│   │   ├── C4DiagramsSection.tsx     # Hosts the four C4 diagrams via DiagramViewer
│   │   ├── DiagramViewer.tsx         # Pan/zoom inline SVG viewer
│   │   ├── DesignSection.tsx         # Renders DESIGN.md (react-markdown + highlight.js)
│   │   └── Mermaid.tsx               # Mermaid diagram renderer
│   ├── hooks/
│   │   ├── useSpeechRecognition.ts   # webkitSpeechRecognition wrapper
│   │   └── useAvatarAudioGate.ts     # Unlocks audio after first user gesture
│   ├── lib/
│   │   ├── api.ts                    # Typed fetch wrappers + SSE reader + session mgmt
│   │   └── analytics.ts              # GA4 tracking helpers
│   ├── types/
│   │   └── index.ts                  # Shared TypeScript interfaces
│   └── public/
│       ├── DESIGN.md                 # Auto-copied from ../DESIGN.md at pre-build/pre-dev
│       ├── staticwebapp.config.json  # Azure SWA routing / security headers
│       └── diagrams/
│           ├── structurizr-L1_SystemContext.mmd
│           ├── structurizr-L2_Containers.mmd
│           ├── structurizr-L3_Backend.mmd
│           └── structurizr-L3_Frontend.mmd
│
├── c4/                               # C4 model source-of-truth
│   ├── workspace.dsl                 # Structurizr DSL — containers, components, views
│   └── export-diagrams.ps1           # Docker-based SVG/Mermaid export script
│
└── infra/
    └── terraform/
        ├── versions.tf               # azurerm ~> 3.116, remote state backend (Azure Blob)
        ├── variables.tf              # All inputs (sensitive flagged)
        ├── main.tf                   # ACR, SWA, OpenAI, Speech, Container Apps, Log Analytics
        ├── outputs.tf                # backend_url, acr_login_server, speech_key, swa_api_key…
        ├── terraform.tfvars          # Non-committed concrete values
        ├── terraform.tfvars.example  # Template / defaults
        └── bootstrap/
            ├── main.tf               # One-time: resource group + TF state storage account
            └── terraform.tfstate     # Local bootstrap state (gitignored)
```

## Directory Purposes

**`backend/`:**
- Purpose: Python 3.12 FastAPI service implementing the RAG pipeline, LiveAvatar session proxy, and TTS audio delivery.
- Contains: One module per concern (`main.py`, `rag.py`, `avatar.py`, `tts.py`, `config.py`, `models.py`), the CV knowledge base (`bio.txt`), and container build definition.
- Key files: `backend/main.py`, `backend/rag.py`, `backend/avatar.py`, `backend/tts.py`, `backend/config.py`, `backend/bio.txt`.

**`frontend/`:**
- Purpose: Next.js 16 App Router single-page TypeScript UI with Tailwind styling.
- Contains: Client components, hooks, API client, analytics, static assets.
- Key files: `frontend/app/page.tsx`, `frontend/lib/api.ts`, `frontend/components/ChatInterface.tsx`, `frontend/components/VideoPlayer.tsx`, `frontend/next.config.ts`, `frontend/package.json`.

**`frontend/app/`:**
- Purpose: Next.js App Router routes; each file is either a `layout.tsx`, `page.tsx`, or nested route.
- Contains: Only three files — root layout, root page, global CSS. No nested routes (single-page app).

**`frontend/components/`:**
- Purpose: React Client Components (every file begins with `"use client"`).
- Contains: One `.tsx` per UI widget; no sub-directories.

**`frontend/hooks/`:**
- Purpose: Custom React hooks encapsulating browser-API integrations.
- Contains: `useSpeechRecognition.ts`, `useAvatarAudioGate.ts`.

**`frontend/lib/`:**
- Purpose: Non-React utilities and the API client.
- Contains: `api.ts` (backend fetch wrappers + SSE parser), `analytics.ts` (GA4 wrappers).

**`frontend/types/`:**
- Purpose: Shared TypeScript interfaces re-exported via `@/types`.
- Contains: `index.ts` with `LogEntry`, `HistoryMessage`, `ConversationMessage`, `AskRequest`, `AskResponse`, `SessionResponse`.

**`frontend/public/`:**
- Purpose: Static assets served verbatim by Next.js.
- Contains: Pre-rendered C4 diagrams in `diagrams/`, copy of `DESIGN.md`, Azure SWA routing config.
- Generated: `DESIGN.md` is copied in `package.json` `prebuild`/`predev` scripts. `diagrams/*.mmd` are exported by `c4/export-diagrams.ps1`. Committed: Yes.

**`c4/`:**
- Purpose: Authoritative architecture diagrams (Structurizr DSL).
- Contains: `workspace.dsl`, `export-diagrams.ps1`. Requires Docker to export.

**`infra/terraform/`:**
- Purpose: Azure infrastructure-as-code (azurerm provider ~> 3.116).
- Contains: Top-level TF config for all app resources; `bootstrap/` sub-directory for the one-time TF state storage account.
- Special: `terraform.tfvars` is gitignored (sensitive values). `terraform.tfvars.example` is committed. `bootstrap/terraform.tfstate` is gitignored.

**`.github/workflows/`:**
- Purpose: GitHub Actions CI/CD.
- Contains: `deploy-azure.yml` with 4-job pipeline (terraform-infra → build-backend → deploy-backend → deploy-frontend).

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI ASGI app (`app = FastAPI(...)`). Started via `uvicorn main:app --reload --port 8000`.
- `frontend/app/layout.tsx`: Root layout (metadata, GA script).
- `frontend/app/page.tsx`: Root page (`export default function Home()`). Tab router for Chat / Architecture / C4 / Design.
- `docker-compose.yml`: Local Qdrant (+ optional Ollama) startup.
- `setup-local.ps1`: Windows dev bootstrap orchestrator.
- `infra/terraform/main.tf`: Azure resource graph.
- `infra/terraform/bootstrap/main.tf`: TF state storage bootstrap.
- `.github/workflows/deploy-azure.yml`: CI/CD pipeline.

**Configuration:**
- `backend/config.py`: Single source of truth for env vars. Rule: never call `os.getenv()` outside this file.
- `backend/.env.example`: Template for backend env (not read — `.env` gitignored).
- `frontend/.env.local.example`: Template for `NEXT_PUBLIC_API_URL` etc.
- `frontend/next.config.ts`: Next.js config (static-export toggle, security headers).
- `frontend/tailwind.config.ts`, `frontend/postcss.config.js`: Styling pipeline.
- `frontend/tsconfig.json`: TypeScript config + `@/*` path alias.
- `backend/requirements.txt`: Pinned Python deps.
- `frontend/package.json`: Node deps + `prebuild`/`predev` copy-DESIGN scripts.
- `infra/terraform/variables.tf`, `terraform.tfvars.example`: TF inputs.

**Core Logic:**
- `backend/main.py`: Routes, lifespan, middleware.
- `backend/rag.py`: RAG chain, LLM/embeddings/vectorstore factories.
- `backend/avatar.py`: Session store, LiveAvatar lifecycle, WS streaming, fillers.
- `backend/tts.py`: Azure Speech + gTTS synthesis.
- `backend/models.py`: Pydantic schemas.
- `frontend/lib/api.ts`: All backend calls.
- `frontend/components/ChatInterface.tsx`: Chat UX + SSE consumption.
- `frontend/components/VideoPlayer.tsx`: LiveKit `Room` lifecycle and video/audio attachment.
- `frontend/hooks/useSpeechRecognition.ts`: STT.

**Data / Knowledge Base:**
- `backend/bio.txt`: Text that is chunked & embedded on startup (`RecursiveCharacterTextSplitter` in `rag.py`, size=500, overlap=50).
- `backend/damir_imangulov_cv.pdf`: Source document.
- `backend/generate_cv.py`: Regenerate `bio.txt` when the PDF changes.

**Testing:**
- No test directories or test files present in this repo. `pytest`/`jest`/`vitest` not configured.

**Diagrams:**
- Source: `c4/workspace.dsl`.
- Export script: `c4/export-diagrams.ps1` (requires Docker + `structurizr/cli`).
- Output: `frontend/public/diagrams/structurizr-L{1,2,3}_*.mmd`.
- Consumer: `frontend/components/C4DiagramsSection.tsx` → `frontend/components/DiagramViewer.tsx`.

## Naming Conventions

**Files:**
- Python modules: lower_snake_case (`rag.py`, `avatar.py`, `tts.py`, `generate_cv.py`).
- React components: PascalCase with `.tsx` (`VideoPlayer.tsx`, `ChatInterface.tsx`, `DiagramViewer.tsx`).
- Hooks: camelCase starting with `use` (`useSpeechRecognition.ts`, `useAvatarAudioGate.ts`).
- Non-component TS modules: camelCase (`api.ts`, `analytics.ts`).
- Type barrel: `index.ts` inside the `types/` directory.
- Terraform: lowercase snake_case (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`).
- Docs: UPPERCASE root docs (`DESIGN.md`, `README.md`).
- Diagrams output: `structurizr-<ViewKey>.mmd` matching the DSL view `name` in `c4/workspace.dsl`.

**Directories:**
- Lowercase: `backend/`, `frontend/`, `infra/`, `c4/`, `components/`, `hooks/`, `lib/`, `types/`, `public/`, `diagrams/`.
- Next.js App Router conventions: `app/`.
- Terraform nested stage: `bootstrap/`.

**Python:**
- Functions/variables: `snake_case`. Private/internal helpers prefixed `_` (`_create_llm`, `_format_docs`, `_SENTENCE_ENDINGS`, `_rag_chain`).
- Constants: `UPPER_SNAKE_CASE` in `backend/config.py`.
- Classes: `PascalCase` (`UserSession`, `AskRequest`).
- Module-level shared state: `_user_sessions`, `_user_sessions_lock`, `filler_cache`, `http_client`.

**TypeScript / React:**
- Components: `PascalCase`. Hooks: `useXxx` camelCase. Props interfaces: `<Component>Props` (see `ChatInterfaceProps`, `VideoPlayerProps`).
- Types/interfaces: `PascalCase` (`LogEntry`, `HistoryMessage`, `AskResponse`).
- Local variables / functions: `camelCase`.
- Module-scoped counters: underscore-prefixed (`_logId`, `_msgId`).

**Path alias:**
- `@/*` is defined in `frontend/tsconfig.json` and used for every import (e.g. `@/components/VideoPlayer`, `@/lib/api`, `@/types`).

## Where to Add New Code

**New backend endpoint:**
- Add route handler in `backend/main.py` following the `/ask`, `/speak`, `/session` style.
- Add Pydantic request/response models in `backend/models.py`.
- If it needs new config, add env-var constants to `backend/config.py` (never call `os.getenv` elsewhere).
- If it touches the LLM/retrieval, extend `backend/rag.py`.
- If it touches avatars/sessions, extend `backend/avatar.py`.
- If it touches TTS, extend `backend/tts.py`.
- Add a matching typed function in `frontend/lib/api.ts`.

**New frontend component:**
- Place under `frontend/components/` as `<PascalCaseName>.tsx` with `"use client"` directive.
- Import shared types from `@/types`; cross-call the backend via `@/lib/api`.
- If it wraps a browser API, prefer a hook at `frontend/hooks/use<Name>.ts`.
- Register it in `frontend/app/page.tsx` (tab or sidebar) if it needs a top-level mount.

**New tab in the main UI:**
- Add an entry to the `TABS` array and the `Tab` union in `frontend/app/page.tsx`.
- Add a conditional panel `{activeTab === "..." && <Component />}`.

**New shared TypeScript type:**
- Add to `frontend/types/index.ts` (barrel file — everything is re-exported from here).

**New environment variable:**
- Declare a typed constant in `backend/config.py` with a sensible default.
- Document it in `DESIGN.md` §10 and `README.md` if user-facing.
- For frontend, prefix with `NEXT_PUBLIC_` and read via `process.env.NEXT_PUBLIC_...`.

**New C4 element / diagram:**
- Edit `c4/workspace.dsl` (add container/component/view).
- Run `pwsh c4/export-diagrams.ps1` to regenerate `frontend/public/diagrams/*.mmd`.
- If a new view is added, wire it into `frontend/components/C4DiagramsSection.tsx`.

**New Azure resource:**
- Declare it in `infra/terraform/main.tf`.
- Add inputs to `infra/terraform/variables.tf` and example values to `terraform.tfvars.example`.
- Expose outputs the CI pipeline needs in `infra/terraform/outputs.tf`.
- Reference those outputs from `.github/workflows/deploy-azure.yml` job steps.

**New CV content:**
- Edit `backend/bio.txt` (or regenerate from the PDF via `backend/generate_cv.py`).
- Restart the backend — chunks are embedded once during `lifespan` startup.

**New test suite:**
- No testing framework is currently set up. Adding one means: install `pytest` (+ `pytest-asyncio`, `httpx` test client) for backend under `backend/tests/`, and Vitest/Jest + Testing Library for frontend under `frontend/__tests__/` or colocated `*.test.tsx`. Wire into `.github/workflows/deploy-azure.yml` as a pre-build step.

## Special Directories

**`frontend/public/diagrams/`:**
- Purpose: Static Mermaid (`.mmd`) / SVG diagram outputs consumed by `DiagramViewer`.
- Generated: Yes — by `c4/export-diagrams.ps1` via Docker `structurizr/cli`.
- Committed: Yes — so deploys do not require Docker at build time.

**`frontend/public/DESIGN.md`:**
- Purpose: Copy of the root `DESIGN.md` so the Design tab can `fetch()` it at runtime.
- Generated: Yes — `package.json` `prebuild` and `predev` scripts run `node -e "require('fs').copyFileSync('../DESIGN.md', 'public/DESIGN.md')"`.
- Committed: Yes.

**`frontend/node_modules/`:**
- Purpose: pnpm-installed dependencies.
- Generated: Yes. Committed: No (gitignored).

**`backend/__pycache__/`:**
- Purpose: CPython bytecode cache.
- Generated: Yes. Committed: No.

**`infra/terraform/bootstrap/`:**
- Purpose: One-time creation of TF state storage (chicken-and-egg pattern). Its own state (`terraform.tfstate`) stays local.
- Generated: `terraform.tfstate` is generated locally.
- Committed: `main.tf` yes; `terraform.tfstate` no (gitignored).

**`.planning/`:**
- Purpose: Workspace for GSD planning agents (this directory contains the current mapping output).
- Generated: Yes — by planning tooling. Committed: per project preference.

---

*Structure analysis: 2026-04-22*
