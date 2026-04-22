# Roadmap — LiveAvatar Free-Tier Switch

**Milestone:** Switch production `dimangulov.space` from paid LiveAvatar tier to the free/sandbox tier, add EU AI Act-compliant disclosure UI, deploy.
**Granularity:** Standard (right-sized — 3 phases for ~1-2 h narrow-scope milestone)
**Created:** 2026-04-22

---

## Phases

- [x] **Phase 1: Infra Wiring + Local Smoke Test** — Close the 3-point Terraform/workflow wiring gap and prove sandbox credentials work locally before any production deploy. (completed 2026-04-22)
- [ ] **Phase 2: Stage 1 Deploy — Backend Tier Swap** — Ship the config change to production via existing 4-job pipeline and verify the Wayne sandbox avatar renders live with zero credit consumption.
- [ ] **Phase 3: Stage 2 Deploy — Disclosure UI + Intro Rewrite + Key Revocation** — Ship the persistent disclaimer, third-person intro, cache-bust, and revoke the paid API key after Stage 2 is healthy.

---

## Phase Details

### Phase 1: Infra Wiring + Local Smoke Test
**Goal**: Sandbox configuration flows end-to-end from GitHub variables through Terraform to the Container App env, and free-tier credentials are empirically proven to work in LITE mode before any push to `main`.
**Depends on**: Nothing (first phase — starts from user's already-set GitHub env vars)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07, CONFIG-01, CONFIG-02, CONFIG-03, SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04
**Success Criteria** (what must be TRUE):
  1. `infra/terraform/variables.tf` declares `live_avatar_is_sandbox` (bool, default `true`) and `live_avatar_session_mode` (string, default `"LITE"` with LITE|FULL|CUSTOM validation); `main.tf` emits both as `env {}` blocks on the backend Container App; `deploy-azure.yml` passes both as `TF_VAR_*` from GitHub repo variables — verified by reading the three files.
  2. `LIVE_AVATAR_IS_SANDBOX=true` and `LIVE_AVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` are confirmed present in GitHub repository variables, and `LIVEAVATAR_API_KEY` GitHub secret has been rotated to the free-tier account key.
  3. Local backend run with the free-tier key + sandbox config successfully calls `POST /v1/sessions/token` (HTTP 200 with `session_id` + `session_token`) and `POST /v1/sessions/start` — `ws_url` presence documented either way.
  4. Local end-to-end Q&A flow works — ask a question, hear avatar respond, confirm clean reconnect after the ~60-120 s sandbox cap; concurrent-session behavior observed and recorded.
  5. Rollback runbook committed (flip `LIVE_AVATAR_IS_SANDBOX` GitHub Variable to `false` → rerun workflow) — discoverable in README or dedicated `docs/rollback.md`.
**Plans**: 3 plans
  - [x] 01-01-PLAN.md — Terraform + workflow wiring (INFRA-01 to INFRA-07)
  - [x] 01-02-PLAN.md — Smoke test tooling (SMOKE-01 to SMOKE-04)
  - [x] 01-03-PLAN.md — Rollback runbook + CONFIG verification (CONFIG-01, CONFIG-02 deferral, CONFIG-03)

### Phase 2: Stage 1 Deploy — Backend Tier Swap
**Goal**: Production `dimangulov.space` runs on the free sandbox tier, rendering the Wayne avatar with zero LiveAvatar credits consumed per session.
**Depends on**: Phase 1 (smoke test must pass before pushing this commit — Stage 1 deploy is gated on proven-working local sandbox credentials)
**Requirements**: DEPLOY-01, DEPLOY-02
**Success Criteria** (what must be TRUE):
  1. Stage 1 commit (Terraform + workflow + tfvars.example changes from Phase 1) is pushed to `main` and the full 4-job GitHub Actions pipeline (terraform-infra → build-backend → deploy-backend → deploy-frontend) completes green.
  2. Visiting `https://dimangulov.space` renders the Wayne sandbox avatar (not the paid custom avatar, not the mock canvas watermark).
  3. Backend `/health` returns 200 and `/session` returns a real (non-mock) LiveAvatar session with a live WebSocket URL.
  4. LiveAvatar provider dashboard shows 0 credits consumed by the new session (proves `is_sandbox=true` is actually reaching the provider).
**Plans**: TBD

### Phase 3: Stage 2 Deploy — Disclosure UI + Intro Rewrite + Key Revocation
**Goal**: The public site carries persistent EU AI Act-compliant disclosure, the avatar no longer impersonates the author in first person, returning visitors see the rewritten intro exactly once, and the stale paid API key is revoked at the provider.
**Depends on**: Phase 2 (Stage 2 UI commit must only land after Stage 1 is confirmed healthy — avoids the "first-person intro spoken by stranger's face" Art. 50(4) window; paid-key revocation must be the final step to avoid stale-session credit burn during rollout)
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, DEPLOY-03, DEPLOY-04, DEPLOY-05
**Success Criteria** (what must be TRUE):
  1. New `frontend/components/LiveAvatarDisclaimer.tsx` client component renders a persistent "AI avatar — not the author's likeness · LiveAvatar free tier" notice on every page load (NOT gated by `localStorage`), placed as a primary badge on the video + secondary one-line banner above the video, with `lucide-react` `Info` icon, amber Tailwind accent, and appropriate ARIA labelling.
  2. `AVATAR_INTRO` in `frontend/app/page.tsx` is rewritten from first-person ("Meet Damir Imangulov. He is…") to third-person ("I'm an AI assistant trained on Damir Imangulov's CV — ask me anything about his experience."), the `anyhting` typo is fixed, and `INTRO_PLAYED_KEY` is bumped to `aicv_intro_played_v2` so a returning visitor with the old `aicv_intro_played=1` cookie hears the new intro exactly once.
  3. The `<video>` element in `VideoPlayer.tsx` carries a descriptive `aria-label="AI-generated avatar"` (only permitted change to that file per scope).
  4. Stage 2 commit is pushed, 4-job pipeline goes green, and the live-site probe confirms the disclaimer is visible above the fold on desktop and mobile, and returning-visitor path replays the new intro exactly once.
  5. Paid LiveAvatar API key is rotated/revoked at the LiveAvatar provider dashboard as the final step, only after Stage 2 is confirmed healthy.
**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infra Wiring + Local Smoke Test | 3/3 | Complete   | 2026-04-22 |
| 2. Stage 1 Deploy — Backend Tier Swap | 0/? | Not started | - |
| 3. Stage 2 Deploy — Disclosure UI + Intro Rewrite + Key Revocation | 0/? | Not started | - |

---

## Coverage Validation

**Total v1 requirements:** 25 (INFRA-01…07, CONFIG-01…03, SMOKE-01…04, UI-01…06, DEPLOY-01…05)
**Mapped:** 25/25 ✓
**Orphans:** None ✓

| REQ-ID | Phase |
|--------|-------|
| INFRA-01…07 | Phase 1 |
| CONFIG-01…03 | Phase 1 |
| SMOKE-01…04 | Phase 1 |
| DEPLOY-01, DEPLOY-02 | Phase 2 |
| UI-01…06 | Phase 3 |
| DEPLOY-03, DEPLOY-04, DEPLOY-05 | Phase 3 |

## Ordering Constraints (honored)

- SMOKE-01…04 run **inside Phase 1**, before DEPLOY-01 (Phase 2). Phase 2 depends on Phase 1.
- DEPLOY-02 (Stage 1 live-site probe) is a Phase 2 success criterion and must pass before Phase 3 starts.
- UI-01…06 ship together as the Stage 2 commit within Phase 3 — no partial UI deploy that would leave a first-person intro spoken by the sandbox face.
- DEPLOY-05 (paid-key revocation) is the final success criterion of Phase 3 — executed last.

---

*Last updated: 2026-04-22*
