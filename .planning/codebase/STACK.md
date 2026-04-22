# Technology Stack

**Analysis Date:** 2026-04-22

## Languages

**Primary:**
- Python 3.12 — Backend FastAPI service (`backend/`)
- TypeScript 5 — Next.js frontend (`frontend/`)

**Secondary:**
- HCL (Terraform ~1.9) — Infrastructure as code (`infra/terraform/`)
- PowerShell — Local setup script (`setup-local.ps1`)
- Dockerfile — Container definitions (`backend/Dockerfile`, `frontend/Dockerfile`)
- YAML — CI/CD (`.github/workflows/deploy-azure.yml`) and Docker Compose (`docker-compose.yml`)

## Runtime

**Environment:**
- Python 3.12 (slim base image in `backend/Dockerfile`) — FastAPI served by Uvicorn single worker on port 8000
- Node.js 20 Alpine (per `frontend/Dockerfile`) — Next.js 16 SSR / static export on port 3000
- Docker Engine — Qdrant (`qdrant/qdrant:latest`) via `docker-compose.yml`

**Package Managers:**
- pip (Python) — `backend/requirements.txt` (pinned versions, no lockfile)
- pnpm (Node.js) — `frontend/pnpm-lock.yaml` present; enabled via corepack in Dockerfile
- npm — `frontend/package-lock.json` also present (dual lockfiles)

## Frameworks

**Core Backend:**
- FastAPI 0.115.6 — HTTP API (`backend/main.py`)
- Uvicorn 0.32.1 `[standard]` — ASGI server
- Pydantic 2.10.4 — Request/response models (`backend/models.py`)
- SlowAPI 0.1.9 — Rate limiting middleware (`20/minute` default in `backend/main.py`)

**Core Frontend:**
- Next.js 16.1.6 — React framework (`frontend/next.config.ts`); supports `output: "export"` static mode via `NEXT_OUTPUT=export`
- React 19 + React-DOM 19
- Tailwind CSS 3.4.1 — styling (`frontend/tailwind.config.ts`)
- PostCSS 8 + Autoprefixer 10.4.20

**AI / RAG:**
- LangChain 0.3.13 (`langchain`, `langchain-core` 0.3.63, `langchain-community` 0.3.13, `langchain-text-splitters` 0.3.4)
- `langchain-ollama` 0.2.3 — local LLM path (`backend/rag.py`)
- `langchain-openai` 0.3.7 — Azure OpenAI path (`backend/rag.py`)

**Testing:**
- Not detected. No pytest, vitest, jest, or equivalent in dependency manifests.

**Build/Dev:**
- TypeScript 5 — `frontend/tsconfig.json` (strict mode, `@/*` path alias, `moduleResolution: bundler`)
- Next ESLint — `next lint` script
- `@tailwindcss/typography` 0.5.19 — prose plugin

## Key Dependencies

**Critical Backend:**
- `httpx` 0.28.1 — Async HTTP client (LiveAvatar, Azure TTS, Ollama health checks)
- `qdrant-client` 1.12.1 — Vector DB client (in-memory / Docker / Qdrant Cloud modes)
- `websockets` 13.1 — WebSocket client for LiveAvatar LITE audio stream
- `python-dotenv` 1.0.1 — `.env` loading in `backend/config.py`
- `azure-identity` 1.19.0 — `DefaultAzureCredential` / Managed Identity for keyless Azure OpenAI

**TTS Pipeline:**
- `gTTS` 2.5.3 — Google TTS fallback for local dev (no credentials)
- `miniaudio` 1.2 — MP3 → PCM (16-bit 24 kHz) without ffmpeg; requires `-Wno-implicit-function-declaration` CFLAG on gcc 14
- Azure Cognitive Services Speech — used via `httpx` REST call, no extra SDK package

**Critical Frontend:**
- `livekit-client` 2.17.3 — WebRTC client for LiveAvatar rooms (`frontend/components/VideoPlayer.tsx`)
- `lucide-react` 0.468.0 — Icon set
- `react-markdown` 10.1.0 + `remark-gfm` 4.0.1 + `rehype-highlight` 7.0.2 + `highlight.js` 11.11.1 — DESIGN.md rendering
- `mermaid` 11.13.0 — C4 diagram rendering (`frontend/components/Mermaid.tsx`, `DiagramViewer.tsx`)

**Infrastructure:**
- `azurerm` provider ~3.116 — Terraform Azure provider (`infra/terraform/versions.tf`)

## Configuration

**Environment files:**
- `backend/.env` — loaded by `python-dotenv` in `backend/config.py` (contents never read; existence only noted). Template: `backend/.env.example`.
- `frontend/.env.local` — Next.js public vars. Template: `frontend/.env.local.example`.

**Backend config module:**
- `backend/config.py` — Centralised `os.getenv` calls. Other modules import constants from here.
- Key variables: `LLM_PROVIDER` (ollama|azure_openai), `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (llama3.2), `EMBED_MODEL` (nomic-embed-text), `AZURE_OPENAI_ENDPOINT/API_KEY/API_VERSION/CHAT_DEPLOYMENT/EMBED_DEPLOYMENT`, `QDRANT_MODE` (memory|docker|cloud), `QDRANT_URL`, `QDRANT_CLOUD_URL/API_KEY`, `LIVEAVATAR_API_KEY/AVATAR_ID/SESSION_MODE/IS_SANDBOX/VOICE`, `AZURE_SPEECH_KEY/REGION`, `ALLOWED_ORIGINS`, `MAX_SESSIONS`, `ENABLE_FILLERS`.

**Frontend public vars:**
- `NEXT_PUBLIC_API_URL` — backend origin (`frontend/lib/api.ts`)
- `NEXT_PUBLIC_GA_MEASUREMENT_ID` — Google Analytics 4 ID (`frontend/app/layout.tsx`)
- `NEXT_OUTPUT` — switches to static export mode (`frontend/next.config.ts`)

**TypeScript config:**
- `frontend/tsconfig.json` — `strict: true`, `target: ES2017`, `jsx: react-jsx`, `paths: { "@/*": ["./*"] }`

**Tailwind config:**
- `frontend/tailwind.config.ts` — `darkMode: "class"`, custom `brand` palette, custom keyframes (`fadeIn`), `@tailwindcss/typography` plugin.

**Next.js config:**
- `frontend/next.config.ts` — conditional static export, security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`), image `remotePatterns` allowing `*.liveavatar.com`.

## Build Tools

**Backend image build:**
- `backend/Dockerfile` — single-stage `python:3.12-slim` with `curl`, `build-essential`; pip installs `requirements.txt` with miniaudio CFLAG workaround; `HEALTHCHECK` hits `/health`.

**Frontend image build:**
- `frontend/Dockerfile` — 3-stage (deps → builder → runner) on `node:20-alpine`, corepack + pnpm frozen lockfile, runs as non-root `nextjs:1001`.

**Prebuild scripts:**
- `frontend/package.json` `predev`/`prebuild` — copies root `DESIGN.md` into `frontend/public/DESIGN.md` for in-app rendering.

## Platform Requirements

**Development (per `README.md`):**
- Node.js ≥ 20
- pnpm ≥ 9
- Python ≥ 3.11 (3.12 used in container)
- Docker Desktop
- Ollama (local LLM runtime, pulls `llama3.2` and `nomic-embed-text`)
- Chrome or Edge browser required — `webkitSpeechRecognition` not supported in Firefox (`frontend/hooks/useSpeechRecognition.ts`)

**Production:**
- Azure Container Apps (consumption plan, scale-to-zero, min 0 / max 3 replicas) — backend
- Azure Static Web Apps (Free tier) — frontend static export, custom domain `dimangulov.space`
- Azure Container Registry Basic — image hosting
- Azure OpenAI (Sweden Central) — `gpt-4o-mini` chat + `text-embedding-3-small`
- Azure Cognitive Services Speech (F0 free tier, default region `westeurope`)
- Azure Log Analytics (PerGB2018, 30-day retention)
- Qdrant Cloud (free 1-cluster tier)
- Azure Blob Storage — Terraform remote state (`rg-aicv-tfstate` / container `tfstate` / key `prod.terraform.tfstate`)

---

*Stack analysis: 2026-04-22*
