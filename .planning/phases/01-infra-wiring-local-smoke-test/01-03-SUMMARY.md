---
phase: 01-infra-wiring-local-smoke-test
plan: 03
subsystem: documentation
tags: [runbook, rollback, config-verification, operations]

# Dependency graph
requires:
  - phase: 01-infra-wiring-local-smoke-test
    provides: Plan 01 landed the TF_VAR_live_avatar_is_sandbox / TF_VAR_live_avatar_session_mode wiring that the rollback procedure references; Plan 02 produced the Sandbox Behavior Baseline block pasted verbatim into the appendix.
provides:
  - New operations runbook at docs/rollback.md covering tier-flip rollback, Phase 2 key-rotation procedure (CONFIG-02 deferral per D-09), verification steps, and the empirical Sandbox Behavior Baseline appendix (D-14).
  - One-line "Operations" pointer in README.md linking to docs/rollback.md.
  - Operator-confirmed CONFIG-01 status (GitHub repository variables LIVE_AVATAR_IS_SANDBOX=true and LIVE_AVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a present per user confirmation 2026-04-22).
affects: [02-* (Phase 2 executor inherits written key-rotation procedure; rollback procedure available if Phase 2 sandbox behavior regresses)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "New docs/ directory convention for operational runbooks (distinct from .planning/ for planning artifacts)."
    - "README one-liner pointer under new '## Operations' section (minimal footprint, discoverable)."
    - "Runbook baseline appendix is a verbatim paste of smoke-script stdout between HTML comment markers — never fabricated."
    - "Deferred work (CONFIG-02 key rotation) documented in-runbook with explicit deferral note referencing D-09."

key-files:
  created:
    - docs/rollback.md                                            # 6-section runbook + empirical baseline appendix
    - .planning/phases/01-infra-wiring-local-smoke-test/01-03-SUMMARY.md  # this file
  modified:
    - README.md                                                    # one-line Operations pointer

key-decisions:
  - "CONFIG-02 is documented as DEFERRED from Phase 1 to Phase 2 inside the runbook — not silently dropped, and not executed in this phase per D-09."
  - "Sandbox Behavior Baseline appendix uses HTML-comment markers (<!-- BASELINE-PLACEHOLDER-START --> / END) so the verbatim script output can be swapped in without touching surrounding prose."
  - "Runbook references GitHub repository variables (LIVE_AVATAR_*) and TF_VAR names (TF_VAR_live_avatar_*) exactly as landed in Plan 01 — no drift risk."
  - "CONFIG-01 verification done by operator against GitHub UI on 2026-04-22 (no gh CLI available locally); variables confirmed present."
  - "README pointer added under new '## Operations' section (single line, lucid) rather than scattered across existing sections."

patterns-established:
  - "Runbook heading order: Overview → Trigger criteria → Rollback procedure → Verification → Phase 2 key-rotation procedure → Sandbox Behavior Baseline appendix (per D-12)."
  - "Placeholder-then-verbatim-swap pattern: new runbooks may ship with a clearly-marked placeholder block that gets replaced once the empirical data arrives, avoiding the 'ship with fake observations' anti-pattern."

requirements-completed: [CONFIG-01, CONFIG-02, CONFIG-03]   # CONFIG-02 covered as DOCUMENTED DEFERRAL per D-09 (rotation ships in Phase 2)

# Metrics
duration: ~6 min (runbook authoring) + ~1 min (placeholder → verbatim baseline swap after Plan 02 run)
completed: 2026-04-22
---

# Phase 1 Plan 03: Rollback Runbook + CONFIG Verification Summary

**New `docs/rollback.md` operations runbook covering tier-flip rollback, Phase 2 key-rotation procedure (CONFIG-02 deferral), verification steps, and an empirical Sandbox Behavior Baseline appendix populated verbatim from Plan 02's smoke run. One-line pointer added to `README.md` under a new `## Operations` section. Operator confirmed CONFIG-01 (GitHub repository variables present) via the GitHub UI on 2026-04-22.**

## Performance

- **Task 1 duration:** ~6 min (runbook authoring + README pointer; committed 2026-04-22 as `46ee4b3`, merged via `1a088c7`)
- **Task 2 duration:** ~1 min (operator GitHub UI verification + orchestrator baseline swap after Plan 02 run)
- **Tasks:** 2/2 complete
- **Files modified:** 2 (`docs/rollback.md` created, `README.md` edited with one-line pointer)

## Accomplishments

- Authored `docs/rollback.md` with all 6 required sections (Overview, Trigger criteria, Rollback procedure, Verification, Phase 2 key-rotation procedure, Sandbox Behavior Baseline appendix).
- Runbook references exact landed names: `TF_VAR_live_avatar_is_sandbox`, `TF_VAR_live_avatar_session_mode`, `LIVE_AVATAR_IS_SANDBOX`, `LIVE_AVATAR_AVATAR_ID`, `LIVE_AVATAR_SESSION_MODE`, `LIVEAVATAR_API_KEY`. No drift from Plan 01's actual changes.
- CONFIG-02 handled as a **documented deferral** (D-09) — dedicated section titled "Phase 2 key-rotation procedure (CONFIG-02 — deferred from Phase 1)" documents the procedure without executing it in Phase 1. Uses `<PASTE-NEW-FREE-TIER-KEY-HERE>` placeholder in example (no real keys in runbook).
- Added a single-line README pointer under a new `## Operations` section. Minimal footprint; discoverable.
- Operator (dimangulov) confirmed via the GitHub UI that:
  - Repository variable `LIVE_AVATAR_IS_SANDBOX=true` is present.
  - Repository variable `LIVE_AVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` is present.
  - `LIVEAVATAR_API_KEY` secret remains the existing paid key (per D-09, not rotated in Phase 1).
- After Plan 02's smoke run completed with observed output, the runbook's `<!-- BASELINE-PLACEHOLDER-START -->` / `<!-- ... -END -->` placeholder block was replaced verbatim with the script's stdout summary + operator-interpretation subsection. This preserves D-14's contract (appendix is verbatim paste, research files unmutated).

## Task 2 Observed Results (2026-04-22)

**CONFIG-01 verification (GitHub UI — operator-confirmed):**

| Variable | Location | Value | Status |
|----------|----------|-------|--------|
| `LIVE_AVATAR_IS_SANDBOX` | Repository variable | `true` | ✓ Confirmed present |
| `LIVE_AVATAR_AVATAR_ID` | Repository variable | `dd73ea75-1218-4ef3-92ce-606d5f7fbc0a` | ✓ Confirmed present |
| `LIVE_AVATAR_SESSION_MODE` | Repository variable | (optional — fallback `'LITE'` applies if absent) | Non-blocking for Phase 1 |
| `LIVEAVATAR_API_KEY` | Repository secret | existing paid key (per D-09) | ✓ Present, NOT rotated in Phase 1 |

CONFIG-01 = satisfied. CONFIG-02 = deferred to Phase 2 per D-09 (documented in runbook § "Phase 2 key-rotation procedure"). CONFIG-03 = satisfied by `docs/rollback.md` existing and being discoverable from README.

## Task Commits

1. **Task 1:** `46ee4b3` — `docs(01-03): add rollback runbook and README Operations pointer` (worktree commit, merged via `1a088c7`)
2. **Baseline verbatim swap + SUMMARY finalization:** committed with this SUMMARY.md (see orchestrator commit after this plan completes)

## Files Created/Modified

- `docs/rollback.md` — created, ~175 lines (149 initial + baseline block swap + interpretation subsection)
- `README.md` — modified, new `## Operations` section with one-line pointer
- `.planning/phases/01-infra-wiring-local-smoke-test/01-03-SUMMARY.md` — created, this file

## Scope-Discipline Self-Check

- [x] Zero `backend/*.py` modifications
- [x] Zero `infra/terraform/*` modifications (Plan 01's domain)
- [x] Zero `.github/workflows/*` modifications (Plan 01's domain)
- [x] Zero `scripts/*` modifications (Plan 02's domain)
- [x] Zero research-file mutations in `.planning/research/*` (D-14 preserves PITFALLS.md)
- [x] No real API keys, session tokens, Bearer headers, or `sk-` prefixes in the runbook (threat T-03-02 grep verified)
- [x] CONFIG-02 explicitly labelled as deferred from Phase 1 to Phase 2 — runbook does not claim it was rotated
- [x] All D-XX decisions governing this plan (D-09, D-11, D-12, D-14) honored

## Notes for Downstream Phases

- **Phase 2 first step** should be the key-rotation procedure documented in `docs/rollback.md` § "Phase 2 key-rotation procedure". The executor has a written-down procedure and does not need to re-discover it.
- **Phase 2 DEPLOY-01 rollback path** is the procedure in `docs/rollback.md` § "Rollback procedure" — reusable without modification.
- **Deferred hardening items** from D-13 (SESSION_IDLE_TTL bump, resetSessionId fix, mock-mode guard, etc.) are tracked in CONTEXT.md's `<deferred>` section. Future hardening milestone picks them up.

## Self-Check: PASSED
