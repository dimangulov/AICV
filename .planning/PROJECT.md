# Interactive Digital Twin CV — Project Context

**Status:** Brownfield — Phase 2 Complete + Phase 3 partial (rate limiting shipped)
**Live site:** https://dimangulov.space/
**Current milestone:** Switch LiveAvatar to free/dev tier for public deployment

---

## What This Is

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

## Current Milestone Goal

**Switch from paid LiveAvatar account to LiveAvatar's free/sandbox tier and redeploy.**

The public site currently uses a paid LiveAvatar plan with a custom avatar representing the author. This must change because:
1. The paid plan is not sustainable for a public portfolio site
2. The free/sandbox tier of LiveAvatar uses a generic/stock avatar — not the author's likeness

### What must be delivered

1. **Config already set by user** (2026-04-22):
   - `LIVEAVATAR_IS_SANDBOX=true` added to GitHub environment variables
   - `LIVEAVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` set in GitHub environment variables (replacing the paid custom avatar ID)
   - Code path verified: `backend/avatar.py:275` sends `is_sandbox: LIVEAVATAR_IS_SANDBOX` in the POST `/v1/sessions/token` payload — no backend code change required for the switch itself
   - Still to verify: Terraform variable wiring for `LIVEAVATAR_IS_SANDBOX` and the new `LIVEAVATAR_AVATAR_ID` (values must flow GitHub secret/var → Terraform → Container App env at deploy time)

2. **UI disclaimer** — add a clearly-visible note on the site stating:
   - The avatar does **not** represent the actual author
   - The site uses LiveAvatar's **free** version

3. **Deploy to production** — push through the existing GitHub Actions pipeline; verify the live site at `dimangulov.space` shows the new avatar and disclaimer.

### Out of scope for this milestone
- Any backend code changes beyond env/config (unless the free tier requires a different API shape — investigate first)
- Redis caching, OpenTelemetry, Key Vault, Front Door, multi-language — these belong to a later Phase 3 milestone
- Test infrastructure — separate milestone per CONCERNS.md
- Auth / CSP / session-state rework — separate milestone

---

## Requirements

### Validated (existing, shipped in Phase 1 & 2)

- ✓ Streaming Q&A via `POST /ask/stream` (SSE, ~200ms TTFB) — existing
- ✓ RAG chain over `bio.txt` (Qdrant top-k=3, LangChain LCEL) — existing
- ✓ Dual-mode LLM: Ollama local + Azure OpenAI cloud — existing
- ✓ Azure Speech TTS with gTTS fallback — existing
- ✓ Persistent LiveAvatar WebSocket with sentence-pipelined speech — existing
- ✓ WebRTC avatar video in `VideoPlayer.tsx` — existing
- ✓ DevConsole live log panel — existing
- ✓ C4 diagrams (Structurizr DSL → SVG → DiagramViewer pan/zoom) — existing
- ✓ Rate limiting (`slowapi` 20 req/min per IP) — existing
- ✓ Azure deployment (SWA + Container Apps + Terraform + GitHub Actions OIDC) — existing
- ✓ Custom domain `dimangulov.space` — existing
- ✓ Session persistence via `localStorage` (`aicv_session_id`, `aicv_intro_played`) — existing
- ✓ Mock avatar mode when `LIVEAVATAR_API_KEY` absent — existing

### Active (this milestone)

- [x] GitHub env vars set by user: `LIVEAVATAR_IS_SANDBOX=true`, `LIVEAVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a`
- [x] Code path verified: `backend/avatar.py:275` already sends `is_sandbox` to LiveAvatar `/v1/sessions/token`
- [ ] Verify Terraform + deploy pipeline propagate `LIVEAVATAR_IS_SANDBOX` and the new `LIVEAVATAR_AVATAR_ID` from GitHub env into Container App env at runtime (currently `LIVEAVATAR_IS_SANDBOX` may not be declared as a Terraform variable or wired through `.github/workflows/deploy-azure.yml`)
- [ ] Confirm free-tier behavior end-to-end against the live API (session start succeeds, WebSocket streams, latency acceptable)
- [ ] Add disclaimer notice on the frontend page: avatar is not the author's likeness and LiveAvatar free tier is in use
- [ ] Invalidate stale `aicv_session_id` / intro-cache for returning visitors so the new avatar renders immediately
- [ ] Deploy to production and verify the live site renders the new avatar and disclaimer

### Out of Scope

- Custom/paid avatar restoration — product decision to stay on free tier
- Removing LiveAvatar entirely / switching providers — not requested
- Tests, auth, CSP, Redis, OTel, i18n — deferred to later milestones

---

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Stay on LiveAvatar (switch tier, not provider) | Existing WebSocket/WebRTC integration works; minimize churn | Pending |
| Minimize backend code changes | Existing `backend/avatar.py` already supports `LIVEAVATAR_IS_SANDBOX` flag — prefer config-only swap | Validated — `avatar.py:275` sends `is_sandbox` to `/v1/sessions/token`; no backend code change needed for the flag itself |
| New sandbox avatar ID | User provided `dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` as the free-tier avatar replacing the paid custom one | Set in GitHub env vars 2026-04-22 |
| Disclaimer on main page (visible, not buried) | Users must immediately understand the avatar ≠ author and the tier is free | Pending — placement TBD during planning |

---

## Context

- Brownfield codebase mapped in `.planning/codebase/` (STACK, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, INTEGRATIONS, CONCERNS)
- No automated test infrastructure exists (CONCERNS.md) — this milestone will not add tests but should not make testing harder
- LiveAvatar code: `backend/avatar.py`, `backend/config.py`, `frontend/components/VideoPlayer.tsx`
- Existing env vars: `LIVEAVATAR_API_KEY`, `LIVEAVATAR_AVATAR_ID`, `LIVEAVATAR_SESSION_MODE` (LITE/FULL/CUSTOM), `LIVEAVATAR_IS_SANDBOX`, `LIVEAVATAR_VOICE`
- Azure production backend reads secrets from Container App env (and eventually Key Vault per DESIGN.md §9.6)
- Deploy pipeline: `.github/workflows/deploy-azure.yml` (4 jobs: terraform-infra → build-backend → deploy-backend → deploy-frontend)

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-04-22 after initialization*
