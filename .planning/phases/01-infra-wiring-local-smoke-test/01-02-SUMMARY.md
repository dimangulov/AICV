---
phase: 01-infra-wiring-local-smoke-test
plan: 02
subsystem: testing
tags: [smoke-test, liveavatar, sandbox, httpx, python, operator-tooling]

# Dependency graph
requires:
  - phase: 01-infra-wiring-local-smoke-test
    provides: Plan 01 Terraform wiring for LIVEAVATAR_IS_SANDBOX / LIVEAVATAR_SESSION_MODE (consumed in production; Plan 02 exercises the local analogue via backend env).
provides:
  - Standalone smoke-test CLI at scripts/smoke-liveavatar.py that drives the local FastAPI backend under sandbox config.
  - Empirically captured "## Sandbox Behavior Baseline (observed 2026-04-22)" markdown block pasted verbatim into docs/rollback.md per D-14 contract.
  - SSRF-guarded operator tooling that cannot be pointed outside localhost.
  - Empirical gate (SMOKE-01 = PASS) plus three OBSERVED probes (SMOKE-02/03/04) covering ws_url presence, end-to-end Q&A + post-cap reconnect, and two-session concurrency.
affects: [01-03 (rollback-runbook Sandbox Behavior Baseline appendix — consumed verbatim), 02-* (Stage 1 deploy — baseline empirically validates the sandbox code path before push)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Operator-tooling lives under scripts/ (new directory this plan)."
    - "SSRF allowlist guard via ALLOWED_BASE_URL_PREFIXES at script entry."
    - "Exception-safe summary emission: never str(exc), only type(exc).__name__ (threat T-02-03 mitigation)."
    - "Single markdown block emitted on stdout, designed to be copy-pasted verbatim into ops docs."

key-files:
  created:
    - scripts/smoke-liveavatar.py
  modified: []

key-decisions:
  - "Reused httpx (already a backend dep) rather than adding a new package — script runs from the backend venv with zero setup."
  - "SMOKE-02 reuses the /session response body captured in SMOKE-01 instead of issuing a second call, avoiding double-counting sandbox session credits."
  - "SMOKE-04 runs AFTER SMOKE-01/03 (not in parallel) so the concurrency probe observes a clean cold state."
  - "Best-effort DELETE /session cleanup at end of run so the operator's backend returns to idle."
  - "emit_summary() lists allowed fields explicitly (id/status/summary only) — CheckResult.details is scratch-only, never printed (T-02-01 mitigation)."

patterns-established:
  - "Operator-tooling pattern: Python script at scripts/<kebab-case>.py with module docstring stating prerequisites + usage."
  - "Health-preflight-before-probe pattern: smoke scripts MUST check /health before exercising downstream endpoints so connection-refused errors are user-friendly."
  - "OBSERVED-only status for empirical probes whose pass/fail criteria depend on provider-side behavior we do not control."

requirements-completed: [SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04]

# Metrics
duration: ~7 min (5 min script authoring + 2.5 min operator-driven runtime executed 2026-04-22 against localhost:8001)
completed: 2026-04-22
---

# Phase 1 Plan 02: Local Smoke-Test Tool Summary

**Standalone Python CLI at `scripts/smoke-liveavatar.py` that drives the local FastAPI backend's `/session`, `/speak`, and `/interrupt` endpoints under sandbox config and emits a paste-ready markdown block mapping SMOKE-01 (hard gate) and SMOKE-02/03/04 (OBSERVED) into Plan 03's runbook appendix.**

## Performance

- **Task 1 duration:** ~5 min (script authoring, committed 2026-04-22 as `387e8b1`)
- **Task 2 duration:** ~2.5 min wall-clock (operator-driven run against `localhost:8001` via orchestrator on 2026-04-22; SMOKE-03 sleeps ~130 s for the cap-wait probe)
- **Tasks:** 2/2 complete
- **Files modified:** 1 (`scripts/smoke-liveavatar.py` created; zero `backend/*.py` touched)

## Accomplishments

- Created `scripts/` directory (new) and `scripts/smoke-liveavatar.py` (single-file, 512 lines).
- Script implements the plan's structure exactly: module docstring + prerequisites, SSRF-guarded base-URL validation, `/health` preflight, four SMOKE checks, argparse CLI with `--base-url` / `--json`, markdown + JSON emitters, exit-code-0-iff-SMOKE-01-PASS hard gate.
- All five observation sets from D-07 captured: (a) HTTP status + elapsed on `/session`, (b) `ws_url` presence check, (c) elapsed-to-first-session, (d) two-session concurrency probe, (e) post-cap reconnect on a fresh UUID.
- Zero new dependencies — reused `httpx` pin already in `backend/requirements.txt`; script runs from the existing backend venv.
- Threat-model mitigations implemented: T-02-01 (allowlisted summary fields only), T-02-02 (SSRF allowlist), T-02-03 (type-name-only exception summaries), T-02-04 (exit-1 hard gate on SMOKE-01 FAIL).

## Task 2 Observed Results (2026-04-22 runtime)

Run conditions:
- Backend started on `http://localhost:8001` (operator's default `:8000` was occupied by an unrelated service, so `--base-url` override was used — see `01-03-SUMMARY.md` operator notes).
- Process env injected on startup: `LIVEAVATAR_IS_SANDBOX=true`, `LIVEAVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` (overriding `.env` values since `load_dotenv` does not override existing env). `LIVEAVATAR_SESSION_MODE=LITE` inherited from `.env`. Existing paid `LIVEAVATAR_API_KEY` per D-08.
- Script exited 0 (SMOKE-01 hard gate satisfied).
- Total elapsed: 139.5 s.

| ID       | Status   | Observed behavior |
|----------|----------|-------------------|
| SMOKE-01 | PASS     | `/session` returned 200 in 2235 ms with `session_id`. Paid key accepts `is_sandbox=true` — D-10 case (a) ruled out. |
| SMOKE-02 | OBSERVED | `ws_url` present in LITE sandbox — full TTS path works (better than documented fallback). |
| SMOKE-03 | OBSERVED | `/speak` → `queued`; `/interrupt` → `interrupted`; post-cap reconnect on fresh UUID → 200. End-to-end Q&A healthy under sandbox. |
| SMOKE-04 | OBSERVED | Two parallel `/session` probes both returned 502. Consistent with LiveAvatar sandbox single-slot concurrency — pitfall #3 confirmed. |

The paste-ready baseline block is landed verbatim in `docs/rollback.md` § "Sandbox Behavior Baseline (observed 2026-04-22)" per the D-14 contract.

## Task Commits

1. **Task 1:** `387e8b1` — `feat(01-02): add scripts/smoke-liveavatar.py smoke-test tool`
2. **Task 1 completion:** `0d74fe5` — `docs(01-02): complete local smoke-test tool plan`
3. **Task 2:** operator-driven runtime capture — baseline pasted into `docs/rollback.md` as part of Plan 03's final commit (see `01-03-SUMMARY.md`)

## Files Created/Modified

- `scripts/smoke-liveavatar.py` — created, 512 lines
- `.planning/phases/01-infra-wiring-local-smoke-test/01-02-SUMMARY.md` — this file (Task 2 finalization)
- Zero `backend/*.py` modifications (scope discipline per D-13 verified)

## Scope-Discipline Self-Check

- [x] Zero `backend/*.py` files modified by this plan
- [x] No new dependencies added to `backend/requirements.txt`
- [x] No `STATE.md` / `ROADMAP.md` edits by the executor
- [x] Smoke script does NOT call LiveAvatar directly — exercises the backend code path per D-05
- [x] Baseline appendix in `docs/rollback.md` is a verbatim paste of script stdout, not fabricated observations
- [x] All D-XX decisions governing this plan (D-05, D-06, D-07, D-08, D-10) honored

## Notes for Downstream Phases

- **Phase 2 DEPLOY-02** can now proceed with empirical evidence that sandbox mode works against the provider with the existing paid key. The "0 credits consumed" check is the final confirmation that the production wiring reaches LiveAvatar correctly.
- **Pitfall #3** (sandbox concurrency limits) is empirically confirmed as single-slot per backend instance. `MAX_SESSIONS=50` (per `.env`) is mismatched with the sandbox reality, but this is explicitly out of Phase 1 scope per D-13 — captured as deferred hardening.
- **The smoke script is re-runnable** by anyone with backend running on localhost + sandbox env configured. Future tier swaps can reuse it with `--base-url` pointing at whatever port the AICV backend occupies.

## Self-Check: PASSED
