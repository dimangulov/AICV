# Technology Stack — Switch to LiveAvatar Free/Sandbox Tier

**Project:** Interactive Digital Twin CV
**Milestone:** Swap paid LiveAvatar → free/sandbox tier for public deployment
**Researched:** 2026-04-22
**Overall confidence:** HIGH (LiveAvatar sandbox spec) / MEDIUM (free-tier credit mechanics)

---

## TL;DR

**Good news:** The existing codebase is already 95 % ready for the swap. `backend/avatar.py` reads `LIVEAVATAR_IS_SANDBOX` and `LIVEAVATAR_SESSION_MODE`, and the Terraform default `live_avatar_avatar_id` is **already** the LiveAvatar sandbox "Wayne" UUID (`dd73ea75-1218-4ef3-92ce-606d5f7fbc0a`).

**The work is purely config:**
1. Wire two env vars (`LIVEAVATAR_IS_SANDBOX`, `LIVEAVATAR_SESSION_MODE`) through Terraform to the Container App (they are **not currently wired**).
2. Set `LIVEAVATAR_IS_SANDBOX=true` and keep `LIVEAVATAR_SESSION_MODE=LITE` in production.
3. Keep `LIVEAVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` (Wayne — the only sandbox-approved avatar).
4. Handle the **~1-minute sandbox session cap** — the avatar disconnects after ≈60 s and must reconnect. Existing `session.stopped` handler already invalidates and `get_or_create_liveavatar_session()` re-creates on next speak call, so **no backend code change required** to tolerate it, but UX should be reviewed.
5. No backend Python source changes needed to `avatar.py` / `tts.py`. **Do not** change `LIVEAVATAR_SESSION_MODE` to `FULL` — the current token-request payload is a LITE-shape payload (no `avatar_persona`) and would fail validation against FULL.

---

## Current vs Target Configuration

| Env var | Current prod value | Target (free tier) | Where set today | Where it must be set |
|---|---|---|---|---|
| `LIVEAVATAR_API_KEY` | Custom paid key (GH secret `LIVEAVATAR_API_KEY`) | **Free-account key from [app.liveavatar.com/developers](https://app.liveavatar.com/developers)** | GH secret → TF var `live_avatar_api_key` → Container App secret `liveavatar-api-key` | Same path — just rotate the secret value |
| `LIVEAVATAR_AVATAR_ID` | Custom UUID (author's likeness) | `dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` (Wayne, the **only** sandbox avatar per LiveAvatar docs) | GH `vars.LIVE_AVATAR_AVATAR_ID` (fallback default is already Wayne) | Same path — set GH Actions variable to the Wayne UUID or leave unset (fallback applies) |
| `LIVEAVATAR_SESSION_MODE` | `LITE` (backend default; **never actually set in prod env**) | `LITE` (keep) | **Not set in TF/Container App** — backend falls back to hard-coded `"LITE"` default in `config.py` | Optional: add explicit env in `main.tf` for clarity; behaviour unchanged |
| `LIVEAVATAR_IS_SANDBOX` | `false` (backend default; **never actually set in prod env**) | **`true`** | **Not set in TF/Container App** — backend falls back to `false` in `config.py` | **MUST be added** to Terraform Container App env block and plumbed via a new `live_avatar_is_sandbox` variable |
| `LIVEAVATAR_VOICE` | `en-US-AndrewMultilingualNeural` (backend default) | Keep (unused in LiveAvatar API — this is an Azure Speech voice label for TTS) | `config.py` default only | Unchanged — not a LiveAvatar API param |

### The single required infrastructure change

`infra/terraform/main.tf` (container env block around line 261–269) currently passes only `LIVEAVATAR_API_KEY` and `LIVEAVATAR_AVATAR_ID`. To move to sandbox, **add**:

```hcl
env {
  name  = "LIVEAVATAR_IS_SANDBOX"
  value = tostring(var.live_avatar_is_sandbox)   # new variable, default true
}
env {
  name  = "LIVEAVATAR_SESSION_MODE"
  value = var.live_avatar_session_mode           # new variable, default "LITE"
}
```

And in `variables.tf`:

```hcl
variable "live_avatar_is_sandbox" {
  description = "Use LiveAvatar sandbox tier (free, Wayne avatar only, ~60s sessions)."
  type        = bool
  default     = true
}

variable "live_avatar_session_mode" {
  description = "LiveAvatar session mode. Must be LITE for the existing backend token payload."
  type        = string
  default     = "LITE"
  validation {
    condition     = contains(["LITE", "FULL", "CUSTOM"], var.live_avatar_session_mode)
    error_message = "Must be LITE, FULL, or CUSTOM."
  }
}
```

No GitHub Actions changes strictly required (defaults suffice), but optionally add `TF_VAR_live_avatar_is_sandbox: "true"` to `deploy-azure.yml` job `terraform-infra` for explicitness.

---

## LiveAvatar Sandbox Tier — Hard Facts (from official docs)

| Fact | Value | Source | Confidence |
|---|---|---|---|
| Sandbox demo avatar | **Wayne**, UUID `dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` — the **only** avatar allowed in sandbox | docs.liveavatar.com/docs/developing-in-sandbox-mode | HIGH |
| Sandbox credit cost | **0** (no credits consumed) | docs.liveavatar.com | HIGH |
| Sandbox session duration | Terminates automatically at **≈ 1 minute** | docs.liveavatar.com | HIGH |
| API key needed for sandbox? | **Yes** — standard `X-API-KEY` header, retrieved from app.liveavatar.com/developers. No separate sandbox key. | docs.liveavatar.com/docs/api-key-configuration | HIGH |
| Free account availability | Free sign-up at app.liveavatar.com; "sample LiveAvatars" free to test. No recurring free credits (HeyGen FAQ: "HeyGen does not offer free API credits starting Feb 2026" — affects the parent co., likely applies here) | liveavatar.com, help.heygen.com | MEDIUM |
| `is_sandbox` supported in LITE mode? | **Yes** — OpenAPI spec declares `is_sandbox: boolean` on both `FullSDKSessionTokenConfigDataSchema` and `LiteSDKSessionTokenConfigDataSchema` | docs.liveavatar.com/openapi.json | HIGH |
| Concurrent sandbox sessions limit | **Not documented**. No `x-rate-limit` headers, no 429 responses in OpenAPI spec. Assume conservative low limit (1–5). | docs.liveavatar.com/openapi.json (absence of) | LOW — verify empirically |
| Rate limits on `/v1/sessions/token` and `/v1/sessions/start` | **Not documented** | docs.liveavatar.com/openapi.json | LOW — verify empirically |
| Watermark on sandbox stream? | Not documented / not mentioned | docs.liveavatar.com | LOW |
| Credit cost comparison | FULL = 2 credits/min, LITE = 1 credit/min (non-sandbox). Sandbox = 0 regardless of mode. | docs.liveavatar.com | HIGH |

### Why LITE (not FULL) is the required mode for this codebase

The existing token-request payload in `backend/avatar.py:272-276`:

```python
json={
    "avatar_id": LIVEAVATAR_AVATAR_ID,
    "mode": LIVEAVATAR_SESSION_MODE,
    "is_sandbox": LIVEAVATAR_IS_SANDBOX,
},
```

OpenAPI spec says:

- **LITE** schema — requires only `avatar_id`. `mode`, `is_sandbox`, `livekit_config`, `agora_config`, etc. are optional. ✅ Matches current payload.
- **FULL** schema — requires `avatar_id` **and** `avatar_persona` (an `AvatarPersonaSchema` object with voice/context/language). ❌ Current payload does NOT send this — switching to FULL would 422.

The existing backend has always been a LITE-mode client driving its own TTS (Azure Speech) and WebSocket audio pump via `agent.speak` frames. This is correct architecture and nothing needs to change.

---

## The ~60-second session cap — how the existing code handles it

The sandbox tier auto-closes sessions at roughly 60 seconds. The existing code already has the plumbing to recover:

1. LiveAvatar emits a `session.stopped` WS event on termination.
2. `_avatar_ws_loop()` (avatar.py:226–233) catches it and calls `entry.invalidate("session.stopped received")`.
3. `invalidate()` (avatar.py:103–117) clears `liveavatar_data`, fires remote `/v1/sessions/stop` cleanup, and frees the WS.
4. The next `speak_on_avatar()` call sees `entry.is_valid() == False`, enters `get_or_create_liveavatar_session()` and re-creates.

**Net effect:** mid-answer re-connection adds ~1–3 s latency (token + /start + WS handshake). Cold-start cost on a brand-new visit is already present; this just adds repeat cost every ~1 minute.

**UX consideration (not a blocker for this milestone, but note it):**
- If a visitor asks a question and the session dies mid-speak, audio will stutter or cut. Current code invalidates on WS error, which will drop the in-flight `agent.speak` frame.
- The 2-minute `SESSION_IDLE_TTL` (config.py:82) is longer than the sandbox session TTL, which is harmless but means idle-eviction is now overridden by sandbox TTL.
- **Recommended:** the disclaimer UI should mention "the avatar session is ~1 minute for the free tier and will reconnect automatically."

---

## Core Stack (unchanged by this milestone)

| Technology | Version | Purpose | Why |
|---|---|---|---|
| LiveAvatar API | v1 | Photorealistic WebRTC avatar | Only the tier changes; provider & integration code stays |
| LiveKit | client-side, driven by LiveAvatar | WebRTC transport for avatar video/audio | LiveAvatar hands back `livekit_url` + `livekit_client_token`; sandbox uses the same transport |
| FastAPI | 3.12 / current | Backend | Unchanged |
| Azure Container Apps | Consumption | Backend runtime | Unchanged |
| Terraform | azurerm ~> 3.116 | IaC | Unchanged — only two new variables |
| Azure Speech | REST, neural voices | TTS (drives LITE mode audio) | Unchanged — LiveAvatar LITE mode expects dev-supplied audio over WS, exactly what we do |

---

## Supporting Libraries (unchanged)

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| `httpx` | current | LiveAvatar REST calls | Already in use — no change |
| `websockets` | current | Persistent avatar `speak_ws` | Already in use — no change |
| `python-dotenv` | current | Env loading | Already in use — no change |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| Mode for sandbox | **LITE + is_sandbox=true** | FULL + is_sandbox=true | FULL requires `avatar_persona` in request body; would require a code change in `avatar.py`. LITE is already wired and free-tier-compatible. |
| Avatar ID | **Wayne UUID** | Any other UUID with is_sandbox=true | Docs explicitly say only Wayne is allowed in sandbox — other UUIDs will fail. |
| Provider | **Stay on LiveAvatar sandbox** | Switch to Heygen Interactive Avatar / Tavus / D-ID free tier | Out of scope per PROJECT.md; existing WebRTC/WebSocket integration works; minimizes churn. |
| Fallback if sandbox fails | **Existing canvas mock** | Retry loop on session termination | Backend already falls back to mock when `LIVEAVATAR_API_KEY` is empty; for sandbox failures mid-session the existing invalidate-and-recreate flow is sufficient. |

---

## Where each env var is set — authoritative map

```
┌──────────────────────────────────┐
│  GitHub repository               │
│                                  │
│  Secrets:                        │
│    LIVEAVATAR_API_KEY   ◄──── rotate to free-account key
│                                  │
│  Variables:                      │
│    LIVE_AVATAR_AVATAR_ID  ◄───── set to Wayne UUID
│                       (or leave unset → default applies)
└──────────────────┬───────────────┘
                   │ injected as TF_VAR_* by deploy-azure.yml lines 68–74
                   ▼
┌──────────────────────────────────┐
│  Terraform variables.tf           │
│                                  │
│  live_avatar_api_key (sensitive)  │
│  live_avatar_avatar_id            │
│  live_avatar_is_sandbox  ◄─── NEW, default true
│  live_avatar_session_mode ◄─── NEW, default "LITE"
└──────────────────┬───────────────┘
                   │ main.tf container env block
                   ▼
┌──────────────────────────────────┐
│  Azure Container App env          │
│                                  │
│  LIVEAVATAR_API_KEY    (secretRef)│
│  LIVEAVATAR_AVATAR_ID  (value)    │
│  LIVEAVATAR_IS_SANDBOX (value) ◄──── NEW
│  LIVEAVATAR_SESSION_MODE (value) ◄──── NEW (optional — defaults to LITE in code)
└──────────────────┬───────────────┘
                   │ os.getenv() in backend/config.py
                   ▼
┌──────────────────────────────────┐
│  Python backend (running)         │
│    config.LIVEAVATAR_* constants  │
│    → avatar.py _fetch_token()     │
└──────────────────────────────────┘
```

---

## Implementation changes summary

### Required (blocks the milestone)

1. **`infra/terraform/variables.tf`** — add `live_avatar_is_sandbox` (bool, default true) and `live_avatar_session_mode` (string, default "LITE") variables.
2. **`infra/terraform/main.tf`** — add two `env {}` blocks inside the container template for the new variables.
3. **GitHub secret `LIVEAVATAR_API_KEY`** — rotate to the free-account API key.
4. **GitHub variable `LIVE_AVATAR_AVATAR_ID`** — set to `dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` (or delete the variable — the TF workflow fallback default is already Wayne).

### Optional (quality-of-life)

5. **`backend/.env.example`** — update the comment on `LIVEAVATAR_IS_SANDBOX=false` to document the Wayne UUID and the ~60 s session limit.
6. **`README.md` §LiveAvatar Integration** — document free tier configuration and link to LiveAvatar sandbox docs.
7. **`.github/workflows/deploy-azure.yml`** — explicitly pass `TF_VAR_live_avatar_is_sandbox: "true"` in the `terraform-infra` job for clarity (optional — default already covers it).

### NOT required (verified unnecessary)

- **No change** to `backend/avatar.py`, `backend/tts.py`, `backend/config.py`, `backend/main.py`.
- **No change** to `frontend/components/VideoPlayer.tsx` — WebRTC/LiveKit client flow is identical in sandbox.
- **No change** to the persistent WebSocket pump, `agent.speak` framing, or `session.keep_alive` logic.

---

## Installation / rollout steps

```bash
# 1. Create/verify LiveAvatar free account, generate API key
#    → https://app.liveavatar.com/developers

# 2. Update GitHub secrets & variables
gh secret set LIVEAVATAR_API_KEY --body "<new-free-tier-key>"
gh variable set LIVE_AVATAR_AVATAR_ID --body "dd73ea75-1218-4ef3-92ce-606d5f7fbc0a"

# 3. Patch Terraform (see diffs above), commit and push
# 4. GitHub Actions auto-runs: terraform-infra → build-backend → deploy-backend → deploy-frontend
# 5. Smoke test at https://dimangulov.space — confirm Wayne avatar renders and reconnects after ~60s
```

---

## Sources

**HIGH confidence (official LiveAvatar docs / OpenAPI spec):**
- [LiveAvatar docs — main](https://docs.liveavatar.com)
- [Developing in Sandbox Mode](https://docs.liveavatar.com/docs/developing-in-sandbox-mode) — Wayne avatar UUID, 60 s limit, zero-credit rule
- [API Key Configuration](https://docs.liveavatar.com/docs/api-key-configuration) — X-API-KEY header, HeyGen keys not compatible
- [OpenAPI spec](https://docs.liveavatar.com/openapi.json) — LITE vs FULL schemas, `is_sandbox` field on both, required/optional fields, absence of documented rate limits
- [LITE Mode](https://docs.liveavatar.com/docs/lite-mode) — dev-managed STT/LLM/TTS
- [Getting Started](https://docs.liveavatar.com/docs/getting-started)

**MEDIUM confidence (cross-referenced third-party docs):**
- [LiveKit LiveAvatar plugin](https://docs.livekit.io/agents/models/avatar/plugins/liveavatar/) — confirms `avatar_id` + `LIVEAVATAR_API_KEY` are the only required inputs
- [HeyGen API / LiveAvatar pricing FAQ](https://help.heygen.com/en/articles/10060327-heygen-api-liveavatar-pricing-subscriptions-explained) — parent-company free-tier stance (no free API credits as of Feb 2026)
- [Pipecat LiveAvatar service reference](https://reference-server.pipecat.ai/en/stable/api/pipecat.services.heygen.api_liveavatar.html) — confirms `LiveAvatarNewSessionRequest` shape

**LOW confidence (noted gaps requiring empirical verification during deploy):**
- Exact concurrent-sandbox-session limit (not documented)
- Rate limits on `/v1/sessions/token` and `/v1/sessions/start` (no headers, no 429 documented)
- Whether sandbox stream carries a watermark (not documented either way)
- Whether a free-tier account without any paid credit top-up can create sandbox sessions indefinitely, or whether there's an implicit daily cap

**Recommend:** during the first production deploy, tail Container App logs for `LiveAvatar` errors; if 429s or auth failures appear, fall back briefly to the existing canvas mock mode (empty `LIVEAVATAR_API_KEY`) while escalating with LiveAvatar support.
