# Architecture Patterns

**Domain:** Brownfield Azure deployment — LiveAvatar tier swap + disclaimer UI
**Researched:** 2026-04-22
**Scope:** Minimal-change architecture for switching LiveAvatar from paid to free/sandbox tier with a visible frontend disclaimer, delivered through the existing 4-job GitHub Actions pipeline.

---

## Executive Verdict

**This is a config-only change on the backend, plus a single-component addition on the frontend. No `backend/avatar.py` code changes are required.** The existing codebase already has every hook needed:

- `backend/config.py` already reads `LIVEAVATAR_IS_SANDBOX`, `LIVEAVATAR_AVATAR_ID`, `LIVEAVATAR_SESSION_MODE`, `LIVEAVATAR_API_KEY`.
- `backend/avatar.py::get_or_create_liveavatar_session` already sends `is_sandbox` in the `/v1/sessions/token` POST body (line 275 of `backend/avatar.py`).
- The Terraform `azurerm_container_app.backend` resource already wires `LIVEAVATAR_API_KEY` (as a secret) and `LIVEAVATAR_AVATAR_ID` (as a var) into the Container App env block.
- The GitHub Actions pipeline already injects `TF_VAR_live_avatar_api_key` from the `LIVEAVATAR_API_KEY` GitHub secret and `TF_VAR_live_avatar_avatar_id` from the `LIVE_AVATAR_AVATAR_ID` variable.

What is missing is:
1. **Three Terraform variables** for `is_sandbox`, `session_mode`, and optionally `voice` — plus matching Container App `env {}` blocks.
2. **One GitHub Actions TF_VAR line** for `TF_VAR_live_avatar_is_sandbox`.
3. **One new React component** `LiveAvatarDisclaimer.tsx` mounted in `frontend/app/page.tsx` over (or below) the video column.

Everything else is a value change in GitHub Secrets/Variables.

---

## Recommended Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│  GitHub Repository                                                        │
│    Secrets:  LIVEAVATAR_API_KEY          (← rotate to free-tier key)      │
│    Vars:     LIVE_AVATAR_AVATAR_ID       (← change to sandbox avatar)     │
│              LIVE_AVATAR_IS_SANDBOX      (NEW — "true")                   │
│              LIVE_AVATAR_SESSION_MODE    (NEW — e.g. "LITE")              │
└──────────────┬────────────────────────────────────────────────────────────┘
               │   injected as TF_VAR_* in deploy-azure.yml
               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  infra/terraform/variables.tf      (NEW vars declared)                    │
│  infra/terraform/main.tf                                                  │
│     azurerm_container_app.backend                                         │
│       secret  liveavatar-api-key      (existing)                          │
│       env     LIVEAVATAR_API_KEY      (existing)                          │
│       env     LIVEAVATAR_AVATAR_ID    (existing)                          │
│       env     LIVEAVATAR_IS_SANDBOX   (NEW)                               │
│       env     LIVEAVATAR_SESSION_MODE (NEW)                               │
└──────────────┬────────────────────────────────────────────────────────────┘
               │   Container App revision created on apply
               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Azure Container App (aicv-prod-backend)                                  │
│  backend/config.py reads env → backend/avatar.py uses is_sandbox in       │
│  POST /v1/sessions/token   (code path already exists, no change)          │
└──────────────┬────────────────────────────────────────────────────────────┘
               │   WebRTC stream returns generic sandbox avatar
               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Azure Static Web App (frontend)                                          │
│  frontend/app/page.tsx                                                    │
│     <VideoPlayer/>                                                        │
│     <LiveAvatarDisclaimer/>  (NEW — sibling of VideoPlayer)               │
└───────────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Changes Needed |
|-----------|----------------|----------------|
| GitHub Secrets/Variables | Source of truth for env-specific config | Rotate `LIVEAVATAR_API_KEY`, change `LIVE_AVATAR_AVATAR_ID`, add `LIVE_AVATAR_IS_SANDBOX`, `LIVE_AVATAR_SESSION_MODE` |
| `.github/workflows/deploy-azure.yml` | Inject vars into Terraform | Add 2 `TF_VAR_*` lines under `terraform-infra` env block |
| `infra/terraform/variables.tf` | Declare all TF inputs | Add `live_avatar_is_sandbox`, `live_avatar_session_mode` (optional `live_avatar_voice`) |
| `infra/terraform/main.tf` → `azurerm_container_app.backend` | Wire env into backend | Add 2–3 `env {}` blocks |
| `backend/config.py` | Env-var parsing | **No change** — already reads these vars |
| `backend/avatar.py` | LiveAvatar REST/WS client | **No change** — already passes `is_sandbox`, `mode` |
| `frontend/components/LiveAvatarDisclaimer.tsx` | Render the "not the author / free tier" notice | **NEW file** (~40 lines) |
| `frontend/app/page.tsx` | Mount disclaimer in the video column | Insert one `<LiveAvatarDisclaimer/>` JSX line |
| `frontend/components/VideoPlayer.tsx` | WebRTC render | **No change** — does not own the disclaimer |

### Data Flow — First Visit After Deploy

1. User loads `https://dimangulov.space/` (Azure Static Web App).
2. `frontend/app/layout.tsx` renders root HTML + GA script.
3. `frontend/app/page.tsx` mounts: left column hosts `<VideoPlayer/>` **and** the new `<LiveAvatarDisclaimer/>`; right column hosts the tabbed chat/arch/c4/design panels.
4. `LiveAvatarDisclaimer` renders immediately (static content, no network). User sees: *"The avatar shown is a generic stock likeness (LiveAvatar free tier), not the actual author."*
5. `useEffect` in `page.tsx` calls `initSessionId()` + `ping()` → Container App wakes from scale-to-zero (~3–5 s cold start).
6. `VideoPlayer` calls `GET /session` → backend `avatar.get_or_create_liveavatar_session` POSTs `/v1/sessions/token` with `{ avatar_id: <sandbox UUID>, mode: "LITE", is_sandbox: true }`.
7. LiveAvatar returns sandbox JWT + session_id → backend POSTs `/v1/sessions/start` → returns `{ livekit_url, livekit_client_token, ws_url }`.
8. Browser connects to LiveKit room → generic avatar video attaches to `<video>` element.
9. `onConnected` fires → `speakText(AVATAR_INTRO)` plays the intro on the generic avatar.
10. User reads disclaimer while avatar is speaking → zero ambiguity about who is on screen.

---

## Exact Files to Edit

### 1. `infra/terraform/variables.tf` — ADD

```hcl
variable "live_avatar_is_sandbox" {
  description = "Use LiveAvatar sandbox/free tier. Set true for public demo, false for paid/custom avatar."
  type        = bool
  default     = true
}

variable "live_avatar_session_mode" {
  description = "LiveAvatar session mode: LITE | FULL | CUSTOM. Sandbox tier requires LITE."
  type        = string
  default     = "LITE"
  validation {
    condition     = contains(["LITE", "FULL", "CUSTOM"], var.live_avatar_session_mode)
    error_message = "Must be one of LITE, FULL, CUSTOM."
  }
}
```

**Change type:** Config-only (declarative).

### 2. `infra/terraform/main.tf` — ADD env blocks inside `azurerm_container_app.backend.template.container`

Insert right after the existing `LIVEAVATAR_AVATAR_ID` block (around line 269):

```hcl
env {
  name  = "LIVEAVATAR_IS_SANDBOX"
  value = tostring(var.live_avatar_is_sandbox)
}
env {
  name  = "LIVEAVATAR_SESSION_MODE"
  value = var.live_avatar_session_mode
}
```

**Note:** `backend/config.py` reads `LIVEAVATAR_IS_SANDBOX` as a string and compares case-insensitively against `"true"` (standard Python pattern). Verify in `config.py` — if it uses strict bool parsing, pass `"true"`/`"false"` lowercase. `tostring()` on a Terraform bool yields lowercase `"true"`/`"false"`, which is the correct idiom.

**Change type:** Config-only (declarative).

### 3. `.github/workflows/deploy-azure.yml` — ADD two `TF_VAR_` lines

Inside the `terraform-infra` job, `Terraform Apply` step `env:` block (around line 74):

```yaml
TF_VAR_live_avatar_is_sandbox:   ${{ vars.LIVE_AVATAR_IS_SANDBOX || 'true' }}
TF_VAR_live_avatar_session_mode: ${{ vars.LIVE_AVATAR_SESSION_MODE || 'LITE' }}
```

**Change type:** Config-only.

### 4. GitHub Repository Configuration — UI CHANGE (no commit)

| What | Where | Action |
|------|-------|--------|
| `LIVEAVATAR_API_KEY` | Settings → Secrets → Actions | Update value to free-tier key |
| `LIVE_AVATAR_AVATAR_ID` | Settings → Variables → Actions | Update to sandbox avatar UUID |
| `LIVE_AVATAR_IS_SANDBOX` | Settings → Variables → Actions | New — value `true` |
| `LIVE_AVATAR_SESSION_MODE` | Settings → Variables → Actions | New — value `LITE` |

**Rationale for secret vs variable placement:**
- **API key → Secret** — it is credentials; Terraform already declares `sensitive = true` and stores as a Container App secret reference.
- **Avatar ID, is_sandbox, session_mode → Variable** — they are non-sensitive configuration knobs visible in logs. This matches the existing convention (line 74 of the workflow uses `vars.LIVE_AVATAR_AVATAR_ID`).
- **Do not set in both.** A second source is a drift vector.

### 5. `frontend/components/LiveAvatarDisclaimer.tsx` — NEW FILE

```tsx
"use client";

import { Info } from "lucide-react";

export default function LiveAvatarDisclaimer() {
  return (
    <div className="absolute bottom-3 left-3 right-3 z-20 rounded-lg bg-gray-900/85 backdrop-blur border border-amber-500/40 px-3 py-2 text-xs text-amber-100 flex items-start gap-2 shadow-lg">
      <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-amber-400" aria-hidden />
      <p className="leading-snug">
        The avatar shown is a <strong>generic stock likeness</strong> provided by
        LiveAvatar&apos;s <strong>free tier</strong>. It is <strong>not</strong> the
        author&apos;s real appearance — it is used here to keep the portfolio
        publicly accessible at no ongoing cost.
      </p>
    </div>
  );
}
```

**Design rationale:**
- Positioned `absolute bottom-3` inside the left video column so it overlays the lower portion of the avatar — impossible to miss, but does not obscure the face.
- `amber` border/text gives it a "notice" visual weight without screaming "error".
- `lucide-react` `Info` icon matches the existing icon library (already imported in `page.tsx`).
- Pure static component — no props, no hooks, no API calls — zero failure modes.
- Mobile-safe: uses `right-3`/`left-3` so it wraps on narrow viewports.

**Change type:** Code change (new component, ~20 lines).

### 6. `frontend/app/page.tsx` — 2-line edit

Add the import at the top with the other component imports:

```tsx
import LiveAvatarDisclaimer from "@/components/LiveAvatarDisclaimer";
```

Inside the left column div (after the existing `<VideoPlayer/>`, around line 82):

```tsx
<VideoPlayer … />
<LiveAvatarDisclaimer />
```

The existing left-column div is already `relative` (line 65), so the new absolute-positioned disclaimer anchors to it correctly.

**Change type:** Code change (2 lines).

---

## Change Summary Table

| Change | File | Type | Risk |
|--------|------|------|------|
| Declare TF variables | `infra/terraform/variables.tf` | Config | None — adds optional inputs |
| Wire env into Container App | `infra/terraform/main.tf` | Config | None — additive env vars |
| Inject TF_VARs in CI | `.github/workflows/deploy-azure.yml` | Config | None — additive env entries |
| Rotate GitHub secret/vars | Repo settings | Config | Bookkeeping — test locally first |
| Add disclaimer component | `frontend/components/LiveAvatarDisclaimer.tsx` | Code (new) | Minimal — static JSX |
| Mount disclaimer | `frontend/app/page.tsx` | Code (2 lines) | Minimal |
| **`backend/avatar.py`** | — | **No change** | — |
| **`backend/config.py`** | — | **No change** | — |
| **`frontend/components/VideoPlayer.tsx`** | — | **No change** | — |

---

## Backend Code: Why No Changes Are Needed

From `backend/avatar.py` lines 267–277 (reconfirmed from the file read):

```python
async def _fetch_token() -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.post(
            f"{LIVEAVATAR_BASE_URL}/v1/sessions/token",
            headers={**base_headers, "X-Api-Key": LIVEAVATAR_API_KEY},
            json={
                "avatar_id": LIVEAVATAR_AVATAR_ID,
                "mode": LIVEAVATAR_SESSION_MODE,
                "is_sandbox": LIVEAVATAR_IS_SANDBOX,   # ← already here
            },
        )
```

And all three identifiers are imported from `config.py` at the top of `avatar.py` (lines 31–42). The code path is already tier-agnostic; only the values change.

**One caveat:** The free tier may enforce `mode == "LITE"` and return an empty `ws_url` on `/v1/sessions/start`. The existing code handles this gracefully — line 322 logs `"<empty — LITE ws_url not returned>"` and line 329 only spawns `_avatar_ws_loop` when `ws_url` is truthy. If LITE does not return `ws_url`, `entry.speak_ws` stays `None`, and `speak_on_avatar` will time out after 3 s (line 419: `logger.error("[speak] WebSocket unavailable…")`). This is a graceful no-op for the user — the avatar still renders via LiveKit WebRTC, just without backend-pushed TTS.

**Action:** Verify the free tier returns a usable `ws_url` in your LiveAvatar sandbox account **before** deploying. If it does not, a separate backend fix is needed (out of scope for this milestone — flag as a pitfall). This is the single uncertainty; treat as a pre-deploy smoke test.

---

## Patterns to Follow

### Pattern 1: Config-over-Code for External-SaaS Tier Flags
**What:** Encode provider tier, mode, and IDs as env vars in Terraform; never hardcode in Python or TypeScript.
**When:** Any change that swaps SaaS tier, region, or pricing plan.
**Why:** Keeps `backend/avatar.py` tier-agnostic, permits local dev against sandbox while prod uses paid (or vice versa), and makes rollback a 1-variable change instead of a revert-commit.

### Pattern 2: Terraform Var + GitHub Variable + Container App Env — Three-Tier Binding
**What:** Every runtime knob traverses GitHub Variable → `TF_VAR_*` env in workflow → `var.*` in Terraform → `env {}` in `azurerm_container_app` → `os.getenv` in `backend/config.py`.
**When:** Introducing any new backend env var.
**Example:** Existing pattern for `LIVE_AVATAR_AVATAR_ID` (workflow line 74 → `variables.tf` line 60 → `main.tf` line 267 → `config.py`).
**Why:** Single audit trail; the workflow acts as the source of truth, Terraform is idempotent, Container App gets a new revision automatically.

### Pattern 3: Disclaimer as a Sibling Component, Not a VideoPlayer Prop
**What:** Put the disclaimer next to `<VideoPlayer/>`, not inside it.
**When:** Cross-cutting UI concerns (legal, trust, meta-info about a subsystem).
**Why:** Keeps `VideoPlayer.tsx` focused on WebRTC plumbing — its sole responsibility. The disclaimer is a page-level concern (the user's understanding of the site), not a video-player concern. Also makes future disclaimer tweaks (copy, styling, A/B test) a one-file edit.

### Pattern 4: Pre-Deploy Smoke Test in Local Dev
**What:** Before pushing the deploy-triggering commit, set `LIVEAVATAR_IS_SANDBOX=true` in `backend/.env` and run the local stack to confirm the sandbox flow works end-to-end.
**When:** Any time free-tier behaviour might diverge from paid.
**Why:** A 2-minute local test is cheaper than a failed production deploy + a 3–4 minute rollback pipeline.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Putting `LIVEAVATAR_IS_SANDBOX` in GitHub Secrets
**What:** Classifying a boolean tier flag as a "secret".
**Why bad:** Secrets are opaque in logs, harder to change, and imply confidentiality that does not exist for a public-knowledge flag. Also inconsistent with existing `LIVE_AVATAR_AVATAR_ID` classification (a variable).
**Instead:** GitHub Variable (non-secret). Only the API key is a secret.

### Anti-Pattern 2: Changing `tfvars` Files Instead of GitHub Variables
**What:** Editing `infra/terraform/terraform.tfvars` with sandbox values.
**Why bad:** `terraform.tfvars` is gitignored (per `.gitignore` and confirmed in `codebase/STRUCTURE.md` line 134) — this file is a local-dev convenience, not the production source of truth. Changes made there never reach CI.
**Instead:** Set values in GitHub Variables / Secrets. CI injects them as `TF_VAR_*`.

### Anti-Pattern 3: Hard-coding the Disclaimer Text in `page.tsx`
**What:** Dropping a `<p className="...">The avatar is not real…</p>` into `page.tsx` inline.
**Why bad:** Pollutes the page layout file with marketing copy; makes it harder to localise later; violates the existing convention (every UI widget is its own component in `frontend/components/`, per `codebase/STRUCTURE.md` line 107).
**Instead:** A standalone `LiveAvatarDisclaimer.tsx`.

### Anti-Pattern 4: Gating the Disclaimer on `LIVEAVATAR_IS_SANDBOX`
**What:** Having the frontend fetch the tier from the backend and conditionally render the disclaimer.
**Why bad:** Adds a network dependency for legal/transparency text; risks the disclaimer disappearing on a backend error; requires a new endpoint just to publish a boolean.
**Instead:** Render the disclaimer unconditionally. For this milestone the site is always on the free tier; if that ever changes, it is a one-file edit.

### Anti-Pattern 5: Deploying Backend and Frontend in the Same Commit Without Staging
**What:** Push one commit that contains backend env changes AND frontend disclaimer, wait for all 4 jobs to finish, pray.
**Why bad:** If the sandbox avatar renders wrong or breaks, the disclaimer is already live — confusing for users, and forces a full rollback instead of a partial one.
**Instead:** See "Build-and-Deploy Order" below.

---

## Build-and-Deploy Order — Recommended

**Two-stage delivery across TWO PR / commits. Config first, then UI.**

### Stage 1 — Config-only deploy (validation)

Single PR containing:
- `infra/terraform/variables.tf` additions
- `infra/terraform/main.tf` env block additions
- `.github/workflows/deploy-azure.yml` `TF_VAR_*` additions
- (Separately, in the GitHub UI) rotate `LIVEAVATAR_API_KEY`, update `LIVE_AVATAR_AVATAR_ID`, add `LIVE_AVATAR_IS_SANDBOX=true`, add `LIVE_AVATAR_SESSION_MODE=LITE`.

Merge → pipeline runs:
- `terraform-infra` creates a new Container App revision with new env
- `build-backend` rebuilds image (unchanged code, same SHA behaviour) — actually, with no backend code change the image hash is identical, but the pipeline still runs and the `az containerapp update` call creates a new revision due to env differences
- `deploy-backend` ensures the latest image is on the new revision
- `deploy-frontend` redeploys the existing frontend (no change)

**Validation:** Open `https://dimangulov.space/`, observe the new generic avatar renders; existing disclaimer is NOT YET on the page, but the tier is now sandbox. Confirm:
- Avatar intro plays (or at least the video stream attaches)
- `/ask` returns 200, streaming tokens arrive
- Container App logs show `[session] LiveAvatar session started: …` with the new session ID

**If broken** — rollback is a Container App revision switch (single `az` command, see below). No frontend churn.

### Stage 2 — UI deploy (disclaimer)

Second PR:
- `frontend/components/LiveAvatarDisclaimer.tsx` (new file)
- `frontend/app/page.tsx` (2 lines: import + JSX)

Merge → only `deploy-frontend` job materially changes the site (the 3 backend jobs still run but produce no-ops since code and env are unchanged; that is expected given the current 4-job pipeline has no `paths:` filter).

**Validation:** Refresh `https://dimangulov.space/`, confirm disclaimer renders over the avatar, is legible on mobile, and does not block the video.

### Alternative: Single Commit (acceptable if confident)

If the sandbox tier has been smoke-tested locally and you are confident the avatar + WebSocket work, a single PR containing all six changes is acceptable. The pipeline deploys backend first (jobs 2–3) and frontend last (job 4) by design (`needs: deploy-backend`), so even in a single commit the backend is fully live before the disclaimer appears. This matches the existing dependency graph and is the minimum-latency path if risk tolerance allows.

**Recommendation:** Stage 1 + Stage 2 for a first-time tier swap. Single-commit only if you have verified free tier behaviour beforehand in a local or dev environment.

---

## Phase Breakdown Recommendation

**This is a single-phase milestone.** One phase, two sub-deliverables, delivered in two commits (or one if confident). Do NOT split into multiple phases; the work is too small and too tightly coupled.

Suggested phase structure:

- **Phase 1 — LiveAvatar free-tier swap + disclaimer**
  - Task 1.1: Terraform var + main.tf env wiring
  - Task 1.2: Workflow TF_VAR injection
  - Task 1.3: Update GitHub Secrets/Variables
  - Task 1.4: Local smoke test with sandbox creds
  - Task 1.5: Deploy Stage 1 (config) and verify live site avatar
  - Task 1.6: Implement `LiveAvatarDisclaimer` component
  - Task 1.7: Mount disclaimer in `page.tsx`
  - Task 1.8: Deploy Stage 2 (UI) and verify disclaimer renders
  - Task 1.9: Update `PROJECT.md` key-decisions table and requirement status

Total estimated effort: 1–2 hours of focused work, 20–30 minutes of pipeline time per deploy.

---

## Rollback Strategy

### Layer 1 — Revision revert (fastest, <2 minutes)

Azure Container Apps keeps prior revisions by default. If the sandbox deploy renders a broken avatar:

```bash
# List revisions
az containerapp revision list \
  --name aicv-prod-backend \
  --resource-group rg-aicv-prod \
  --query "[].{name:name, active:properties.active, created:properties.createdTime}" \
  -o table

# Reactivate the previous revision (traffic shifts instantly)
az containerapp revision activate \
  --name aicv-prod-backend \
  --resource-group rg-aicv-prod \
  --revision <prev-revision-name>

# Deactivate the broken one
az containerapp revision deactivate \
  --name aicv-prod-backend \
  --resource-group rg-aicv-prod \
  --revision <broken-revision-name>
```

**Caveat:** The Container App is in `Single` revision mode (per `main.tf` line 162). In Single mode, only one revision runs at a time and traffic always goes to the latest. To use revision revert, you would need to temporarily switch to `Multiple` mode, OR use the simpler method below.

### Layer 2 — Revert via GitHub Variable (recommended, 3–5 minutes)

The cleanest rollback for Single-mode Container Apps:

1. In GitHub Repo → Settings → Variables, change `LIVE_AVATAR_IS_SANDBOX` to `false` and restore original `LIVE_AVATAR_AVATAR_ID` (the paid custom UUID). Also restore the paid `LIVEAVATAR_API_KEY` secret.
2. Trigger `workflow_dispatch` on `deploy-azure.yml` (or push an empty commit to `main`).
3. Terraform creates a new revision with restored env; Single-mode cuts traffic over instantly.

**Pre-requisite:** Keep a note of the previous `LIVEAVATAR_API_KEY` and `LIVE_AVATAR_AVATAR_ID` values before rotating. The paid-tier credentials remain valid even when not used — they are not deleted by this milestone.

### Layer 3 — Git revert (slowest, ~8 minutes)

If a code change is at fault (frontend disclaimer bug, for example):

```bash
git revert <commit-sha>
git push origin main
```

This triggers the full 4-job pipeline. Use only if the issue is in committed code, not in runtime config.

### Layer 4 — Frontend-only rollback

The `deploy-frontend` job deploys a static export. Azure Static Web Apps keeps previous deploys under the "Environments" blade. If only the disclaimer is buggy:

- Azure Portal → SWA resource → Environments → select the last known good deploy → "Set as production".
- Or revert the UI commit and push, letting only `deploy-frontend` re-run.

### Rollback Decision Matrix

| Symptom | Cause | Best Rollback |
|---------|-------|---------------|
| Avatar does not render at all | Sandbox credentials wrong or tier misconfigured | Layer 2 — revert GitHub vars |
| Avatar renders but `/ask` fails | Unrelated backend regression | Layer 3 — git revert |
| Disclaimer overlaps content or is misaligned | UI bug | Layer 4 — SWA previous deploy |
| Avatar renders wrong face (unexpected sandbox avatar) | Wrong `LIVE_AVATAR_AVATAR_ID` | Layer 2 — update var, re-deploy |
| WebSocket fails, no TTS | Free tier doesn't return `ws_url` (LITE mode limitation) | Accept (graceful fallback) OR Layer 2 (revert to FULL mode + paid) |

---

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| LiveAvatar free-tier quota | Likely fine | Likely blocked — sandbox has per-account concurrency/rate limits | Not viable on free tier |
| Container App `max_replicas=3` (from `main.tf` line 206) | Fine | Needs bump to 10–20 | Needs bump + premium SKU |
| `MAX_SESSIONS` in `backend/config.py` | Fine | Bump required | Bump + sticky routing required |
| Azure Speech F0 (5 hr/mo free) | Fine | Exhausted — move to S0 | S0 required |

**For this milestone:** Portfolio traffic is ≤100 users/day realistic. Free-tier capacity is not a near-term scalability concern. Document this in `PITFALLS.md` as a "known ceiling" rather than an active risk.

---

## Quality Gate Verification

- [x] Minimal-change path identified — config-only backend, 2 new frontend files, 0 changes to `backend/avatar.py` / `backend/config.py` / `VideoPlayer.tsx`
- [x] Terraform variable names and locations specified — `live_avatar_is_sandbox`, `live_avatar_session_mode` in `infra/terraform/variables.tf`; env blocks in `infra/terraform/main.tf` under `azurerm_container_app.backend.template.container`
- [x] Frontend component ownership decided — new `frontend/components/LiveAvatarDisclaimer.tsx`, mounted as sibling of `<VideoPlayer/>` in `frontend/app/page.tsx`; does NOT live inside `VideoPlayer.tsx`
- [x] Build-and-deploy order explicit — Stage 1 (config) → validate → Stage 2 (UI); single-commit acceptable if sandbox was smoke-tested
- [x] Rollback plan named — 4-layer strategy: revision revert (if Multiple mode), GitHub-var revert (primary for Single mode), git revert, SWA previous-deploy

---

## Sources

- `c:\w\aicv\backend\avatar.py` — lines 31–42 (config imports), 267–277 (token POST body already includes `is_sandbox`)
- `c:\w\aicv\infra\terraform\variables.tf` — existing `live_avatar_*` variable pattern
- `c:\w\aicv\infra\terraform\main.tf` — lines 157–306 (Container App resource with existing env/secret pattern)
- `c:\w\aicv\.github\workflows\deploy-azure.yml` — lines 63–86 (Terraform Apply env injection), lines 129–149 (deploy-backend image update), lines 151–177 (deploy-frontend)
- `c:\w\aicv\frontend\app\page.tsx` — lines 62–82 (left-column layout with `relative` positioning ready for an absolute-positioned child)
- `c:\w\aicv\.planning\codebase\ARCHITECTURE.md` — Avatar/Session layer description confirms `avatar.py` is the sole owner of LiveAvatar lifecycle
- `c:\w\aicv\.planning\codebase\STRUCTURE.md` — lines 232–247 (conventions for adding new components and env vars)
- `c:\w\aicv\.planning\PROJECT.md` — Key Decisions table confirming "config-only swap" as the guiding principle

Confidence: **HIGH** — all claims grounded in the actual file contents read in this research pass. The only MEDIUM-confidence item is the assumption that the free tier returns a usable `ws_url` in LITE mode; this must be smoke-tested before Stage 1 deploy (flagged in PITFALLS.md).

---

*Architecture research: 2026-04-22*
