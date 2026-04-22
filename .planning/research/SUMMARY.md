# Project Research Summary

**Project:** Interactive Digital Twin CV — LiveAvatar Free/Sandbox Tier Switch
**Domain:** Brownfield Azure deployment — SaaS AI-avatar tier migration + EU AI Act disclosure UI
**Researched:** 2026-04-22
**Confidence:** HIGH (backend code path, architecture, disclaimer best practices) / MEDIUM (LiveAvatar sandbox edge behavior — `ws_url` in LITE, exact concurrency/rate limits)

---

## Executive Summary

**Top-line conclusion: this is a config-only swap plus a small UI addition, estimated at 1–2 hours of focused implementation work.** The backend code path is already 100% wired — `backend/avatar.py:275` already sends `is_sandbox: LIVEAVATAR_IS_SANDBOX` to `POST /v1/sessions/token`, and the existing Terraform default for `live_avatar_avatar_id` is already the LiveAvatar sandbox "Wayne" UUID (`dd73ea75-1218-4ef3-92ce-606d5f7fbc0a`). No Python changes are required. The milestone reduces to: (a) close a confirmed 3-point Terraform/workflow wiring gap for `LIVEAVATAR_IS_SANDBOX`, (b) add a persistent UI disclaimer on the frontend, (c) reword the first-person intro that currently impersonates the author with a generic face, and (d) bust a stale `localStorage` intro-played flag so returning visitors actually see the new experience.

The recommended approach is a **single-phase milestone with a strict pre-deploy local smoke test**. Stack stays unchanged: LiveAvatar LITE mode (do NOT switch to FULL — the current token payload is LITE-shaped and FULL would 422). Session mode stays `LITE`, sandbox flag flips to `true`, avatar UUID stays Wayne. On the UI side, a new `LiveAvatarDisclaimer.tsx` mounts as a sibling of `<VideoPlayer/>` in `page.tsx` with a primary badge on the video and a one-line banner above it; the `AVATAR_INTRO` constant is rewritten from "Meet Damir Imangulov. He is…" (first-person impersonation) to third-person framing; `INTRO_PLAYED_KEY` bumps to `_v2`.

**Key risks are well-bounded and mitigable.** The single biggest infra risk is the three-point wiring gap (Terraform variable + `main.tf` env block + workflow `TF_VAR_*`) — without it, production still runs with `LIVEAVATAR_IS_SANDBOX=false` regardless of GitHub env vars, meaning the switch silently does not happen. The single biggest legal/UX risk is shipping the tier swap without the disclaimer AND without rewording the intro — an unmodified intro spoken by a stranger's face (with `aicv_intro_played=1` suppressing the replay) is precisely the deepfake-impersonation pattern the EU AI Act Art. 50(4) targets. The unknown-behavior risk (sandbox `ws_url` in LITE mode, concurrent-session cap, rate limits) is confined to a 30-minute local smoke test that must precede production deploy.

---

## Key Findings

### Recommended Stack

Stack is essentially unchanged — the milestone is purely configuration and a minor frontend addition. LiveAvatar v1 SaaS (sandbox tier), LITE session mode, Wayne sandbox avatar. LiveKit WebRTC transport handles video identically in sandbox. Azure Speech TTS remains the LITE-mode audio source. No new libraries, no version bumps, no provider swap.

**Core technologies:**
- **LiveAvatar API v1 (sandbox)** — `is_sandbox=true` + LITE mode, Wayne UUID `dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` (only avatar allowed in sandbox per docs), 0 credits consumed, ~60–120 s session cap.
- **Azure Container Apps** — unchanged; revision mode `Single` means env-var changes trigger a new revision automatically.
- **Terraform `azurerm ~> 3.116`** — add two variables (`live_avatar_is_sandbox` bool default true, `live_avatar_session_mode` string default "LITE") and two corresponding `env {}` blocks in `main.tf`.
- **GitHub Actions** — add `TF_VAR_live_avatar_is_sandbox` to the `terraform-infra` job env block; optionally `TF_VAR_live_avatar_session_mode`.
- **Next.js 16 / React 19 / Tailwind v4** — one new small client component (`LiveAvatarDisclaimer.tsx`, ~20 lines); `lucide-react` `Info` icon already imported in `page.tsx`.

**Critical version / mode note:** Keep `LIVEAVATAR_SESSION_MODE=LITE`. Switching to FULL would 422 because the current token-request payload omits the required `avatar_persona` object.

### Expected Features

The milestone's scope is deliberately narrow: enable sustainable public deployment with legal-grade transparency. Feature research surfaced a concrete must-have / defer split.

**Must have (table stakes — all ship in this milestone):**
- TS-1: Sandbox config wiring end-to-end (close the 3-point gap).
- TS-2: Verify free-tier credentials work in LITE mode (local smoke test before deploy).
- TS-3: Clear-and-distinguishable disclaimer — badge on video + one-line banner above it (EU AI Act Art. 50(4) creative-works standard).
- TS-4: Explicit "LiveAvatar free tier" attribution in the same disclaimer copy.
- TS-5: Graceful reconnect after the ~60–120 s sandbox session cap (existing `session.stopped` → `invalidate` → recreate flow already handles this; verify the frontend "Live" badge reflects state).
- TS-6: Ship via the existing 4-job GitHub Actions pipeline.
- TS-7: **Reword `AVATAR_INTRO`** from first-person ("Meet Damir Imangulov. He is…") to third-person ("I'm an AI assistant trained on Damir's CV…"). Fix the `anyhting` typo in the same pass.

**Should have (cheap wins worth including):**
- ARIA / alt-text on the `<video>` element describing "AI-generated avatar" — strengthens Art. 50(5) accessibility posture; one-line change.
- `aicv_intro_played_v2` cache-bust so returning visitors hear the rewritten intro exactly once.

**Defer (v2+):**
- Session-remaining countdown UI ("1:45 / 2:00") — only worth building if real traffic shows confusion.
- Dedicated `/ai-disclosure` page linked from footer — fold into footer note for now.
- Graceful fallback to mock canvas on sandbox quota exhaustion — only if free-tier concurrency becomes a real operational issue.
- `avatar_tier: "sandbox"` GA4 event property — trivial but cosmetic.
- Per-`end_reason` differentiation in `session.stopped` handling.
- Redis-backed cross-replica session state (Phase 3 roadmap item).

### Architecture Approach

Config-only backend; single-component frontend addition. The existing architecture already has every hook needed — `backend/config.py` parses the env vars, `backend/avatar.py::get_or_create_liveavatar_session` already passes `is_sandbox` to `/v1/sessions/token`, and the Container App resource already wires `LIVEAVATAR_API_KEY` (secret) and `LIVEAVATAR_AVATAR_ID` (variable). The only gap is three config surfaces for the sandbox flag and one frontend component.

**Major components (with required changes):**
1. **GitHub Secrets/Variables** — rotate `LIVEAVATAR_API_KEY` to the free-account key; verify `LIVE_AVATAR_AVATAR_ID` is Wayne; user has already set `LIVEAVATAR_IS_SANDBOX=true` in GitHub env vars (but it doesn't propagate — see #3).
2. **`infra/terraform/variables.tf`** — add `live_avatar_is_sandbox` and `live_avatar_session_mode` variable declarations.
3. **`infra/terraform/main.tf`** — add two `env {}` blocks inside `azurerm_container_app.backend.template.container` (around line 269) mirroring the existing `LIVEAVATAR_AVATAR_ID` block pattern.
4. **`.github/workflows/deploy-azure.yml`** — add `TF_VAR_live_avatar_is_sandbox` (and optionally `TF_VAR_live_avatar_session_mode`) in the `terraform-infra` job env block (around lines 67–74).
5. **`frontend/components/LiveAvatarDisclaimer.tsx`** — NEW file (~20 lines); `absolute` positioned over the lower portion of the video, amber-accented info badge. Sibling of `<VideoPlayer/>`, not nested inside it (keeps `VideoPlayer.tsx` focused on WebRTC plumbing).
6. **`frontend/app/page.tsx`** — import + mount `<LiveAvatarDisclaimer/>` (2 lines); rewrite `AVATAR_INTRO` constant (TS-7); bump `INTRO_PLAYED_KEY` to `aicv_intro_played_v2`.

**Zero changes** to `backend/avatar.py`, `backend/config.py`, `backend/main.py`, `frontend/components/VideoPlayer.tsx`, `backend/tts.py`.

### Critical Pitfalls

Four high-risk items must be planned for:

1. **Confirmed infra gap — `LIVEAVATAR_IS_SANDBOX` is not propagated to production.** The flag is read correctly in `backend/config.py:60` and applied at `backend/avatar.py:275`, but (a) no Terraform variable is declared, (b) no `main.tf` env block emits it to the Container App, (c) no `TF_VAR_live_avatar_is_sandbox` line exists in the deploy workflow. Production today runs with `LIVEAVATAR_IS_SANDBOX=false` regardless of what GitHub env vars say. **Fix: mirror the 3-point wiring that already exists for `live_avatar_avatar_id`.**

2. **First-person intro impersonation with a generic face.** `frontend/app/page.tsx:20` has `AVATAR_INTRO = "Meet Damir Imangulov. He is a Senior Full-Stack Engineer…"` — spoken by the avatar. Paired with a stock face, this is the textbook deepfake-style impersonation Art. 50(4) targets. **Fix: reword to third-person BEFORE production deploy.** This is a ship-blocker, not a nice-to-have.

3. **`localStorage['aicv_intro_played']=1` masks the new experience for returning visitors.** Hiring managers who bookmarked the site last month return, see a stranger's face, and never hear the rewritten intro. **Fix: bump the key to `aicv_intro_played_v2` (or `_stock_avatar`).** The disclaimer itself must also be a persistent UI element — never gated on first-visit logic.

4. **Unverified sandbox edge behaviors.** Three items have LOW confidence and require a local smoke test: (a) does sandbox LITE return a usable `ws_url` from `/v1/sessions/start` — if not, TTS pushing over the persistent WS silently no-ops and the avatar renders without synced speech; (b) exact concurrent-session cap (docs say 1, undocumented otherwise); (c) rate limits on `/v1/sessions/token` and `/v1/sessions/start` (no `x-rate-limit` headers, no 429 in OpenAPI). **Fix: 30-minute local smoke test with free-tier creds before pushing the deploy commit.**

Secondary pitfalls worth planning for: Terraform drift if the operator hand-edits the Container App in Azure Portal (never do this — pipeline is source of truth); stale paid-tier session cached in `_user_sessions` crossing the tier boundary during rolling deploy (mitigation: rotate the old paid API key at the LiveAvatar provider AFTER the new revision is healthy); mock-mode silently activating if env propagation fails (frontend watermark "[ POC — Connect LiveAvatar API ]" appears in prod).

---

## Implications for Roadmap

**Recommended: a single-phase milestone delivered in two commits (Stage 1 config + Stage 2 UI).** The work is too small and too tightly coupled to justify splitting into multiple phases. Architecture research and pitfalls research converge on this conclusion independently.

### Phase 1: LiveAvatar Free-Tier Swap + Disclosure UI

**Rationale:** All work is on the critical path for the same user-visible outcome (sustainable public deployment with legal-grade transparency). The config change and the UI change are mutually dependent: shipping the tier swap without the disclaimer is a legal/UX risk; shipping the disclaimer without the tier swap is a no-op. Splitting phases would fragment a 1–2 hour job.

**Delivers:**
- `dimangulov.space` rendering the Wayne sandbox avatar with zero credit consumption.
- Persistent "stock avatar, free tier" disclaimer visible above the fold on desktop and mobile.
- Rewritten intro that no longer first-person-impersonates the author.
- Returning visitors hear the new intro exactly once (cache-bust).
- Documented runbook for tier-swap rollback (GitHub Variable flip → redeploy).

**Addresses (features from FEATURES.md):** TS-1 through TS-7, plus OPT-7 (ARIA alt-text) as a cheap win.

**Avoids (pitfalls from PITFALLS.md):** #1 infra gap (by adding the 3-point wiring), #2 impersonation (by rewording intro before deploy), #3 stale cache (by bumping the localStorage key), #4 sandbox unknowns (by mandating a local smoke test as a sub-task).

**Sub-deliverable split within the phase:**
- **Stage 1 — Config deploy (validation):** TF variables + `main.tf` env + workflow `TF_VAR_*` + GitHub Secret/Variable updates. Verify live site renders the Wayne avatar before proceeding.
- **Stage 2 — UI deploy (disclosure):** `LiveAvatarDisclaimer.tsx` + `page.tsx` mount + `AVATAR_INTRO` rewrite + `INTRO_PLAYED_KEY` bump. Verify disclaimer renders on mobile and desktop.
- Single-commit delivery is acceptable IF the local smoke test passed; otherwise two commits give a clean rollback point between backend and frontend.

### Phase Ordering Rationale

- **Single phase is correct** because the two sub-deliverables share the same user outcome and the same risk surface; separating them would invite the anti-pattern "deploy backend now, disclaimer next sprint" which is precisely the EU AI Act compliance gap.
- **Config before UI within the phase** because the backend revision must prove the sandbox tier works before the frontend disclaimer starts claiming it does. Stage 1 validation is the forcing function that catches Pitfall #4 (sandbox `ws_url` / concurrency unknowns) before a hard-to-revert UI commit.
- **Local smoke test before any push** because that is cheaper than a failed production deploy + 3–4 minute rollback pipeline, and it is the only way to resolve the LOW-confidence items identified in STACK.md and ARCHITECTURE.md.

### Research Flags

**Phases needing deeper research during planning:**
- *None.* This milestone is well-characterized across all four research docs. Architecture is trivial, stack changes are declarative, features are frozen, pitfalls are enumerated with prevention steps.

**Standard patterns (skip `/gsd-research-phase`):**
- Phase 1 — follows the existing `LIVE_AVATAR_AVATAR_ID` three-point wiring pattern already in the codebase. No novel research needed.

**Open questions resolved by local smoke test (NOT by more research):**
1. Does LITE mode + `is_sandbox=true` return a usable `ws_url` from `/v1/sessions/start`? If no, the persistent WS speech pump is a silent no-op and UX degrades to "avatar visible, no TTS" — acceptable fallback but worth knowing.
2. What is the actual concurrent-session cap? Docs imply 1; verify empirically by opening two browsers.
3. Are there undocumented rate limits on `/v1/sessions/token`? Verify by running 3 quick-fire session creations.
4. Does the sandbox `session.stopped` event carry an `end_reason` field distinguishing `duration_limit` from `user_disconnect`? If yes, future UX can show a tailored "Reconnecting — free tier 60s limit" banner (deferred).

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | LiveAvatar OpenAPI spec + official sandbox docs are explicit on Wayne UUID, 0-credit rule, LITE vs FULL schema, `is_sandbox` field on both schemas. Cross-referenced with LiveKit plugin docs and Pipecat reference. |
| Features | HIGH | Sandbox capabilities well-documented; disclaimer best practices grounded in EU AI Act Art. 50(4)/(5) text, Usercentrics dual-pattern guidance, shapeof.ai avatar-badge pattern, FTC AI endorsement guidance. |
| Architecture | HIGH | Every claim grounded in actual file reads — `backend/avatar.py:267-277` token payload confirmed, `main.tf` env-block pattern confirmed, workflow `TF_VAR_*` pattern confirmed, `page.tsx` left-column `relative` positioning confirmed. |
| Pitfalls | HIGH (for code-level), MEDIUM (for sandbox runtime edge cases) | Every code-level pitfall anchored to file:line. Sandbox-specific runtime limits (concurrency, rate, `ws_url` in LITE) are LOW-confidence and **require local smoke test** before deploy. |

**Overall: HIGH** — the only residual uncertainty is three empirical questions about LiveAvatar sandbox runtime behavior, all resolvable by a 30-minute local run against free-tier credentials before pushing the deploy commit.

**Gaps that couldn't be resolved (require smoke test, not more research):**
1. LiveAvatar sandbox `ws_url` presence in LITE mode `/sessions/start` response.
2. Exact concurrent-session cap (assume 1, verify).
3. Rate limits on token/start endpoints (assume strict, verify).
4. Whether free accounts have an implicit daily session cap beyond the 0-credit rule.

---

## Sources

**LiveAvatar (HIGH confidence):**
- https://docs.liveavatar.com/docs/developing-in-sandbox-mode — Wayne UUID, 60 s cap, 0 credits
- https://docs.liveavatar.com/docs/api-key-configuration
- https://docs.liveavatar.com/openapi.json — LITE vs FULL schema, `is_sandbox` field
- https://docs.liveavatar.com/docs/lite-mode
- https://docs.liveavatar.com/docs/getting-started
- https://docs.livekit.io/agents/models/avatar/plugins/liveavatar/
- https://help.heygen.com/en/articles/10060327-heygen-api-liveavatar-pricing-subscriptions-explained
- https://help.heygen.com/en/articles/12758866-liveavatar-faq

**Legal / Regulatory (MEDIUM-HIGH confidence):**
- https://artificialintelligenceact.eu/article/50/
- https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content
- https://www.jonesday.com/en/insights/2026/01/european-commission-publishes-draft-code-of-practice-on-ai-labelling-and-transparency
- https://www.twobirds.com/en/insights/2026/taking-the-eu-ai-act-to-practice-understanding-the-draft-transparency-code-of-practice
- https://www.afslaw.com/perspectives/alerts/the-business-ai-avatars-key-legal-risks-and-best-practices

**Disclaimer UX patterns (HIGH confidence):**
- https://usercentrics.com/guides/website-disclaimers/ai-disclaimer/
- https://www.shapeof.ai/patterns/avatar
- https://www.feisworld.com/blog/disclaimer-templates-for-ai-generated-content
- https://sproutsocial.com/insights/ai-disclaimer/

**Codebase (HIGH confidence — all claims file:line anchored):**
- c:\w\aicv\backend\avatar.py — lines 31–42 (imports), 267–277 (token POST body with `is_sandbox`), 259 (cache reuse log), 100–126 (session validity + TTL), 226–233 (`session.stopped` handler)
- c:\w\aicv\backend\config.py — line 60 (`LIVEAVATAR_IS_SANDBOX` parse), 82 (`SESSION_IDLE_TTL`)
- c:\w\aicv\infra\terraform\variables.tf — existing `live_avatar_*` variable pattern
- c:\w\aicv\infra\terraform\main.tf — lines 157–306 (Container App resource), 262–269 (env block gap)
- c:\w\aicv\.github\workflows\deploy-azure.yml — lines 63–86 (Terraform Apply env injection)
- c:\w\aicv\frontend\app\page.tsx — lines 15 (`INTRO_PLAYED_KEY`), 17–20 (`AVATAR_INTRO`), 62–82 (left-column layout)
- c:\w\aicv\frontend\components\VideoPlayer.tsx — lines 70–78 (mock watermark), 123–166 (retry logic), 128 (`resetSessionId` stranding)
- c:\w\aicv\.planning\codebase\CONCERNS.md
- c:\w\aicv\.planning\PROJECT.md

---

*Synthesis research: 2026-04-22*
