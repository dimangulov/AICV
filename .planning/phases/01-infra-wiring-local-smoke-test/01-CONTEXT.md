# Phase 1: Infra Wiring + Local Smoke Test - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the confirmed 3-point Terraform/workflow wiring gap so `LIVEAVATAR_IS_SANDBOX` and `LIVEAVATAR_SESSION_MODE` propagate from GitHub repository variables through Terraform into the backend Container App env, and empirically prove the sandbox code path (`is_sandbox=true`, LITE mode, Wayne avatar UUID) works end-to-end locally before any push to `main`. Covers requirements INFRA-01…07, CONFIG-01, CONFIG-03, and SMOKE-01…04. CONFIG-02 (API-key rotation) is deferred to Phase 2 per the decision below.

</domain>

<decisions>
## Implementation Decisions

### Infrastructure Wiring (INFRA-01…07)

- **D-01:** Mirror the existing `live_avatar_avatar_id` 3-point wiring pattern already in the codebase (TF variable declaration → `main.tf` `env {}` block on `azurerm_container_app.backend.template.container` → workflow `TF_VAR_*` in the `terraform-infra` job). No novel Terraform patterns introduced.
- **D-02:** `live_avatar_is_sandbox` is `bool` with default `true`; `live_avatar_session_mode` is `string` with default `"LITE"` and a validation block constraining values to `LITE | FULL | CUSTOM`. Defaults match the intended production configuration so a missing GitHub variable does not silently regress.
- **D-03:** Workflow fallbacks in `.github/workflows/deploy-azure.yml` for the two new `TF_VAR_*` entries are `'true'` and `'LITE'` respectively — matching the Terraform defaults so GitHub-variable absence never flips the tier.
- **D-04:** `infra/terraform/terraform.tfvars.example` is updated with both new variables so local operators running `terraform plan` outside CI see the intended values.

### Smoke Test Methodology (SMOKE-01…04)

- **D-05:** Smoke test is a checked-in Python script at `scripts/smoke-liveavatar.py` that drives the **running local FastAPI backend's endpoints** (`/session`, `/speak`, `/interrupt`) — NOT LiveAvatar's API directly. Rationale: exercises the exact code path production runs (`config.py` → `avatar.py` → LiveAvatar), matches backend language, and proves our wiring, not just the provider's auth.
- **D-06:** Prerequisite for smoke execution: operator first runs `setup-local.ps1` (or equivalent) to start backend on `localhost:8000` with the sandbox-flagged env. Script is idempotent and produces pass/fail output plus a summary block ready to paste into the runbook.
- **D-07:** Script captures, at minimum: (a) HTTP status + non-secret body from `/session`, (b) presence/absence of `ws_url` in the response, (c) elapsed time to first successful session, (d) result of a two-session concurrency probe (launch two in parallel, record whether both succeed, 409, or second silently overrides), (e) behavior after ~60–120 s sandbox cap (session re-creates cleanly on next call).

### API Key Strategy (CONFIG-02 scope change)

- **D-08:** **Phase 1 smoke test uses the existing paid LiveAvatar API key with `LIVEAVATAR_IS_SANDBOX=true`** — NOT a freshly-provisioned free-tier key. Rationale: accelerates Phase 1 completion, proves the sandbox code path is reachable, and avoids the account-provisioning dependency. Explicit tradeoff: this does NOT prove free-tier account auth works — that proof moves to Phase 2's DEPLOY-02 success criterion ("LiveAvatar provider dashboard shows 0 credits consumed").
- **D-09:** **CONFIG-02 (rotate `LIVEAVATAR_API_KEY` GitHub secret to the free-tier account key) is removed from Phase 1 scope and deferred to Phase 2.** The rollback runbook (D-11) must explicitly document this ordering: key rotation is a Phase 2 pre-deploy step, not a Phase 1 gate. REQUIREMENTS.md and ROADMAP.md need to reflect this move at phase-plan time.
- **D-10:** Risk to monitor during smoke test execution: LiveAvatar provider may (a) reject `is_sandbox=true` on a paid-tier key with 4xx, (b) accept it but silently consume paid credits, or (c) accept it and route to sandbox. If (a) or (b) is observed, planner must surface the finding and planner/user jointly decide whether to provision a free-tier key mid-phase or proceed to Phase 2 with the observed behavior documented.

### Rollback Runbook (CONFIG-03)

- **D-11:** Rollback runbook lives at `docs/rollback.md` (new file). Referenced from the root `README.md` with a one-line pointer under an "Operations" or "Rollback" subsection to preserve discoverability without bloating the README itself.
- **D-12:** Runbook content covers: (a) tier-swap rollback (flip `LIVE_AVATAR_IS_SANDBOX` GitHub Variable to `false` → rerun workflow, expected duration, verification steps), (b) Phase 2 key-rotation procedure (cancel in-flight runs → update `LIVEAVATAR_API_KEY` secret → push no-op → verify), (c) pointer to the sandbox-behavior appendix (D-13).

### Scope Discipline (Pitfalls #9 and #11)

- **D-13:** **Phase 1 stays scope-strict — no backend Python changes.** `SESSION_IDLE_TTL` bump, `resetSessionId` stranding fix, narrowed exception catches, `speak_ws` race → `asyncio.Event`, and mock-mode prod-fail-fast guard are ALL deferred to a follow-up hardening milestone. Rationale: REQUIREMENTS.md explicitly lists `backend/avatar.py`, `backend/config.py`, `backend/main.py`, `backend/tts.py` as Out of Scope; honoring that keeps the tier-switch blast radius minimal. Deferred items preserved in `<deferred>` below so a future milestone finds them.

### Smoke-Observation Capture

- **D-14:** Sandbox-behavior observations (`ws_url` presence in LITE, concurrent-session cap, rate-limit behavior, `end_reason` values, per-session duration cap) are captured as a dated "Sandbox Behavior Baseline (observed YYYY-MM-DD)" appendix inside `docs/rollback.md`. Single operations doc keeps the rollback procedure and the empirical baseline together. Research files (`.planning/research/PITFALLS.md`) are NOT mutated.

### Claude's Discretion

- Exact filename casing under `scripts/` (`smoke-liveavatar.py` vs `smoke_liveavatar.py`) — planner picks per project convention (project uses `setup-local.ps1` kebab-case).
- Whether the smoke script emits JSON + human-readable output, plain text, or both — planner decides based on paste-into-runbook ergonomics.
- Commit granularity within Phase 1 (one commit per requirement cluster vs one commit per file edit) — planner/executor decides per GSD atomic-commit norms.
- Exact wording of the README pointer to `docs/rollback.md`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Intent & Scope
- `.planning/PROJECT.md` — Milestone goal, what must be delivered, Out-of-Scope list, Key Decisions table
- `.planning/REQUIREMENTS.md` — All 25 v1 requirement IDs (INFRA-01…07, CONFIG-01…03, SMOKE-01…04 in Phase 1; others later), traceability table, deferred v2 list, Out-of-Scope list
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 items), dependencies, ordering constraints
- `.planning/STATE.md` — Current progress and open todos

### Research (consumed before planning)
- `.planning/research/SUMMARY.md` — HIGH-confidence synthesis; confirms config-only swap, 3-point wiring gap, `backend/avatar.py:275` already sends `is_sandbox`, keep LITE mode
- `.planning/research/ARCHITECTURE.md` — Component-by-component required changes
- `.planning/research/STACK.md` — Stack unchanged; LiveAvatar v1 SaaS + Wayne UUID sandbox constraint
- `.planning/research/FEATURES.md` — TS-1…TS-7 must-have scope (TS-1/TS-2 apply to Phase 1)
- `.planning/research/PITFALLS.md` — 14 pitfalls; Pitfalls #1-#11 have Phase 1/2 mappings; Pitfall #9 and #11 explicitly deferred per D-13

### Codebase Maps
- `.planning/codebase/STACK.md` — Confirms Terraform `azurerm ~> 3.116`, Python 3.12, pinned deps
- `.planning/codebase/ARCHITECTURE.md` — Where LiveAvatar config lives (`backend/config.py:60` reads `LIVEAVATAR_IS_SANDBOX`, `backend/avatar.py:275` sends it)
- `.planning/codebase/STRUCTURE.md` — Directory conventions (`scripts/` for operator tooling, `docs/` for ops docs, `infra/terraform/` for TF)
- `.planning/codebase/CONVENTIONS.md` — Python/TypeScript naming, no linter configs, module-level docstrings mandatory
- `.planning/codebase/INTEGRATIONS.md` — LiveAvatar API integration points
- `.planning/codebase/CONCERNS.md` — Source of Pitfalls #9 items (deferred this phase per D-13)
- `.planning/codebase/TESTING.md` — No test infra (relevant: smoke script is NOT a pytest test; it's a standalone operator tool)

### Source Files to Modify (Phase 1)
- `infra/terraform/variables.tf` — add 2 variable declarations (INFRA-01, INFRA-02)
- `infra/terraform/main.tf` — lines ~262-269 (`azurerm_container_app.backend.template.container` env block); add 2 new `env {}` entries (INFRA-03, INFRA-04)
- `infra/terraform/terraform.tfvars.example` — document both new variables (INFRA-07)
- `.github/workflows/deploy-azure.yml` — lines ~67-74 (`terraform-infra` job env); add 2 new `TF_VAR_*` entries with fallbacks (INFRA-05, INFRA-06)

### Source Files to Create (Phase 1)
- `scripts/smoke-liveavatar.py` — new Python smoke-test tool (D-05, D-06, D-07)
- `docs/rollback.md` — new operations runbook (D-11, D-12, D-14)

### Source Files to Read-Only Reference (Phase 1)
- `backend/config.py:60` — confirms `LIVEAVATAR_IS_SANDBOX` parsing (no change this phase)
- `backend/avatar.py:275` — confirms `is_sandbox` is already in the token POST payload (no change this phase)
- `infra/terraform/variables.tf` (existing `live_avatar_avatar_id` entry) — template for D-01 mirroring

### External References (Research, already captured in SUMMARY.md)
- LiveAvatar sandbox docs — `https://docs.liveavatar.com/docs/developing-in-sandbox-mode`
- LiveAvatar API key docs — `https://docs.liveavatar.com/docs/api-key-configuration`
- LiveAvatar OpenAPI — `https://docs.liveavatar.com/openapi.json`
- LiveAvatar LITE mode — `https://docs.liveavatar.com/docs/lite-mode`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`infra/terraform/variables.tf` — `live_avatar_avatar_id` block** — Template for both new variable declarations (D-01). Same `type = string`, `description`, `default` structure; the sandbox-bool variant swaps `type = bool` and drops the validation block, while the session-mode variant adds a `validation { ... }` block for the `LITE|FULL|CUSTOM` constraint.
- **`infra/terraform/main.tf` — existing `LIVEAVATAR_AVATAR_ID` `env {}` block** — Line-level template for the two new env blocks. Mirror the `name`/`value = var.<name>` shape inside `azurerm_container_app.backend.template.container`.
- **`.github/workflows/deploy-azure.yml` — existing `TF_VAR_live_avatar_avatar_id: ${{ vars.LIVE_AVATAR_AVATAR_ID || 'dd73ea75-...' }}` line in the `terraform-infra` job** — Template for the two new `TF_VAR_*` fallback entries.
- **`setup-local.ps1`** — existing local bootstrap script; smoke test assumes this has been run (backend listening on `localhost:8000` with the appropriate `.env`).
- **`httpx.AsyncClient` already a pinned dep in `backend/requirements.txt`** — Reusable from the backend; smoke script can rely on it being installed when the Python venv is active (or installed via `pip install httpx` in an isolated smoke-test venv).

### Established Patterns
- **Three-point wiring** (variable → env block → workflow TF_VAR) is the existing convention for every LiveAvatar-related config. Every new var must hit all three surfaces or silently no-ops in production.
- **Workflow env fallbacks** (`${{ vars.X || 'default' }}`) are used throughout `deploy-azure.yml` — use the same shape for the two new entries.
- **No pytest / no test infra** — smoke script is a standalone executable tool, not a test fixture. It prints results; it does not assert into a test runner.
- **Python module convention** — every `.py` file opens with `from __future__ import annotations` and a module docstring. Smoke script should follow this even though it's under `scripts/` not `backend/`.
- **Operator tooling under `scripts/`** — `setup-local.ps1` lives at the repo root, not under `scripts/`. Planner should confirm the preferred location for new tooling (root vs `scripts/`); if `scripts/` doesn't exist yet, creating it is a minor decision.

### Integration Points
- **Smoke script → FastAPI `/session` endpoint** — main probe; exercises `backend/avatar.py::get_or_create_liveavatar_session` which itself calls LiveAvatar `/v1/sessions/token` + `/v1/sessions/start`.
- **Smoke script → FastAPI `/speak` endpoint** — secondary probe; proves the persistent WebSocket audio pump works (or degrades gracefully per the `ws_url` observation).
- **Smoke script → FastAPI `/interrupt` endpoint** — tertiary probe; proves interrupt path still works under sandbox.
- **Terraform → Container App env** — the tested path; production runs through the same TF-emitted env block.
- **GitHub Actions workflow → Terraform → Azure** — the CI chain that carries the new vars. Phase 2 exercises it; Phase 1 only prepares it.

</code_context>

<specifics>
## Specific Ideas

- Rollback-runbook heading order preference: Overview → Trigger criteria → Procedure (tier flip) → Verification → Phase 2 key-rotation procedure → Sandbox-behavior baseline appendix (D-11, D-12, D-14).
- The smoke-test script should print a final summary block with check/cross marks for each of SMOKE-01 through SMOKE-04 so the operator can copy-paste it directly into the rollback runbook appendix.
- Validation on the `live_avatar_session_mode` variable is preferred (D-02) over accepting any string because FULL mode would 422 without payload work — hard-failing at `terraform plan` is better than 422ing in prod.

</specifics>

<deferred>
## Deferred Ideas

These items came up in research (`.planning/research/PITFALLS.md`) and were considered for Phase 1 but held out per D-13. They belong in a follow-up hardening milestone, not a Phase 2 slip-in.

### Pre-deploy backend hardening (deferred from Phase 1)
- **Bump `SESSION_IDLE_TTL` from 120 s to ~600 s** (Pitfall #9) — users pausing to read the new Phase 3 disclaimer trigger the retry path; bumping TTL dampens the symptom. Backend change, out of scope this milestone.
- **Fix `resetSessionId` stranding in `frontend/components/VideoPlayer.tsx:128`** (Pitfall #9) — add `closeSession(oldId)` before `resetSessionId()` to prevent free-tier credit leak during retries. Frontend change; currently listed Out-of-Scope in REQUIREMENTS.md (VideoPlayer changes limited to `aria-label` in Phase 3).
- **Narrow broad `except Exception` catches in `backend/avatar.py`** (Pitfall #9) — so 401/402/403/429 from LiveAvatar surface as distinct HTTPExceptions, making tier-switch failures diagnosable. Backend change.
- **Replace `speak_ws` 0.5s×6 poll with `asyncio.Event`** (Pitfall #9 / CONCERNS.md) — eliminates a known race. Backend change.
- **Mock-mode prod-fail-fast guard** (Pitfall #11) — refuse to start if `APP_ENV=production` and `LIVEAVATAR_API_KEY` empty. Backend change.

### Error-handling for sandbox-specific failure modes
- **Map 402/403/429 from LiveAvatar to HTTP 503 + `Retry-After`** (Pitfall #3) — user-friendly "free avatar busy" messaging instead of generic "Session setup failed". Backend change.
- **Lower `MAX_SESSIONS` to match sandbox concurrent cap** (Pitfall #3) — reject at our edge rather than letting LiveAvatar 429 us mid-flow. Config change; depends on D-07 findings.

### Observability
- **Extend `/health` to optionally probe LiveAvatar reachability** (Pitfall #6) — catches env-propagation failures that `/health` currently hides. Backend change.
- **Add `DEPLOY_NONCE` env var bumped per deploy** (Pitfall #6) — forces Container App revision cycling on every deploy so secret-only changes propagate. Infra change; viable to slip into Phase 2 if key-rotation misbehaves.
- **Add `avatar_tier: "sandbox"` property to GA4 events** (Pitfall #14) — one-line change in `frontend/lib/analytics.ts`. Cosmetic; deferred to v2.

### Rejected mid-discussion (not deferred — wrong phase entirely)
- CONFIG-02 full free-tier-key rotation in Phase 1 → moved to Phase 2 per D-09.

### Reviewed Todos (not folded)
None — todo-match returned zero matches for Phase 1.

</deferred>

---

*Phase: 01-infra-wiring-local-smoke-test*
*Context gathered: 2026-04-22*
</content>
</invoke>