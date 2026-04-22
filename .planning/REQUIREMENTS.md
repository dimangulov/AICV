# Requirements — LiveAvatar Free-Tier Switch Milestone

**Milestone:** Switch production `dimangulov.space` from paid LiveAvatar tier to the free/sandbox tier, add EU AI Act-compliant disclosure UI, deploy.
**Scope:** Config swap + UI disclosure + intro rewording. No backend Python changes required.
**Created:** 2026-04-22

---

## v1 Requirements

### Infrastructure

- [ ] **INFRA-01**: Declare `live_avatar_is_sandbox` Terraform variable (bool, default `true`) in `infra/terraform/variables.tf` mirroring the existing `live_avatar_avatar_id` pattern
- [ ] **INFRA-02**: Declare `live_avatar_session_mode` Terraform variable (string, default `"LITE"`) with validation constraining values to `LITE | FULL | CUSTOM`
- [ ] **INFRA-03**: Add `LIVEAVATAR_IS_SANDBOX` `env {}` block to `azurerm_container_app.backend.template.container` in `infra/terraform/main.tf` sourcing from `var.live_avatar_is_sandbox`
- [ ] **INFRA-04**: Add `LIVEAVATAR_SESSION_MODE` `env {}` block to the same Container App `template.container` sourcing from `var.live_avatar_session_mode`
- [ ] **INFRA-05**: Add `TF_VAR_live_avatar_is_sandbox` to the `terraform-infra` job env block in `.github/workflows/deploy-azure.yml` reading from `vars.LIVE_AVATAR_IS_SANDBOX` with fallback `'true'`
- [ ] **INFRA-06**: Add `TF_VAR_live_avatar_session_mode` to the same workflow env block with fallback `'LITE'`
- [ ] **INFRA-07**: Update `infra/terraform/terraform.tfvars.example` with the two new variable examples

### Configuration

- [ ] **CONFIG-01**: GitHub repository variables `LIVE_AVATAR_IS_SANDBOX=true` and `LIVE_AVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` set by user — verify in place
- [ ] **CONFIG-02**: `LIVEAVATAR_API_KEY` GitHub secret rotated to the free-tier account API key
- [ ] **CONFIG-03**: Document tier-swap rollback runbook (flip `LIVE_AVATAR_IS_SANDBOX` GitHub Variable to `false` → rerun workflow) in a brief markdown doc or README section

### Smoke Test (Pre-Deploy Gate)

- [ ] **SMOKE-01**: Local run of backend with `LIVEAVATAR_IS_SANDBOX=true`, `LIVEAVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a`, `LIVEAVATAR_SESSION_MODE=LITE`, and free-tier API key — verify `POST /v1/sessions/token` returns 200 with `session_id` and `session_token`
- [ ] **SMOKE-02**: Verify `POST /v1/sessions/start` returns a usable `ws_url` in LITE sandbox mode — if absent, accept the documented "avatar visible, no TTS push" degradation
- [ ] **SMOKE-03**: Verify end-to-end Q&A flow locally — ask a question, hear the avatar respond, confirm session re-creates cleanly after the ~60–120 s sandbox cap
- [ ] **SMOKE-04**: Record observed concurrent-session behavior (open two browsers; document whether second session 409s or silently overrides)

### UI Disclosure

- [ ] **UI-01**: New `frontend/components/LiveAvatarDisclaimer.tsx` client component renders a persistent "AI avatar — not the author's likeness · LiveAvatar free tier" notice visible on every page load (NOT gated by `localStorage`)
- [ ] **UI-02**: Disclaimer is placed above the fold: primary badge overlaid on the video bottom + secondary one-line banner above the video (matches dual-pattern best practice from FEATURES.md)
- [ ] **UI-03**: Disclaimer content is plain text with appropriate ARIA labelling; uses the existing `lucide-react` `Info` icon; styled with Tailwind (amber accent, sufficient contrast)
- [ ] **UI-04**: `AVATAR_INTRO` constant in `frontend/app/page.tsx` rewritten from first-person impersonation ("Meet Damir Imangulov. He is…") to third-person framing ("I'm an AI assistant trained on Damir Imangulov's CV — ask me anything about his experience."); fix `anyhting` typo in same edit
- [ ] **UI-05**: `INTRO_PLAYED_KEY` bumped from `aicv_intro_played` to `aicv_intro_played_v2` so returning visitors hear the rewritten intro exactly once
- [ ] **UI-06**: `<video>` element gets descriptive `aria-label` identifying it as "AI-generated avatar" (Art. 50(5) accessibility posture)

### Deploy & Verify

- [ ] **DEPLOY-01**: Stage 1 commit — Terraform + workflow + tfvars.example changes (INFRA-01…07, CONFIG-01…03) — push to `main`, observe full 4-job pipeline success
- [ ] **DEPLOY-02**: Post-Stage-1 live-site probe — visit `https://dimangulov.space`, verify Wayne sandbox avatar renders, backend `/health` returns 200, `/session` returns a real (non-mock) session, LiveAvatar dashboard shows 0 credits consumed by the new session
- [ ] **DEPLOY-03**: Stage 2 commit — UI changes (UI-01…06) — push, observe pipeline success
- [ ] **DEPLOY-04**: Post-Stage-2 live-site probe — verify disclaimer visible on desktop + mobile + returning-visitor path (test with existing `aicv_intro_played=1` cookie to confirm new key bust works)
- [ ] **DEPLOY-05**: Paid LiveAvatar API key rotated/revoked at the LiveAvatar provider dashboard only AFTER Stage 2 is confirmed healthy (avoids stale-session credit burn during rollout)

---

## v2 Requirements (deferred)

- Session-remaining countdown UI ("Sandbox session · 1:45 remaining")
- Dedicated `/ai-disclosure` page linked from footer
- Graceful fallback to mock canvas when sandbox concurrency limit reached
- GA4 custom event property `avatar_tier: "sandbox"` for analytics segmentation
- Per-`end_reason` differentiation in `session.stopped` handling (distinguish `duration_limit` from `user_disconnect`)
- Redis-backed cross-replica session state (larger Phase 3 scope)

## Out of Scope (this milestone)

- Custom/paid avatar restoration — product decision to stay on free tier
- Provider swap away from LiveAvatar — not requested
- Test infrastructure (pytest/vitest/playwright) — separate milestone per CONCERNS.md
- Authentication, CSP hardening, Redis caching, OpenTelemetry, Azure Key Vault, Front Door, multi-language (EN/UA/DE) — deferred Phase 3 items
- Python backend code changes to `backend/avatar.py`, `backend/config.py`, `backend/main.py`, `backend/tts.py`
- Changes to `frontend/components/VideoPlayer.tsx` beyond adding an `aria-label`

---

## Traceability

(To be populated by roadmapper — maps each REQ-ID to a Phase.)

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| INFRA-01…07 | — | Pending roadmap |
| CONFIG-01…03 | — | Pending roadmap |
| SMOKE-01…04 | — | Pending roadmap |
| UI-01…06 | — | Pending roadmap |
| DEPLOY-01…05 | — | Pending roadmap |

---

*Last updated: 2026-04-22*
