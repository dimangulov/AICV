---
phase: 01-infra-wiring-local-smoke-test
plan: 02
subsystem: testing
tags: [smoke-test, liveavatar, sandbox, httpx, python, operator-tooling]

# Dependency graph
requires:
  - phase: 01-infra-wiring-local-smoke-test
    provides: Plan 01 Terraform wiring for LIVEAVATAR_IS_SANDBOX / LIVEAVATAR_SESSION_MODE (consumed in production; Plan 02 exercises the local analogue via `backend/.env`).
provides:
  - Standalone smoke-test CLI at scripts/smoke-liveavatar.py that drives the local FastAPI backend under sandbox config.
  - Paste-ready `## Sandbox Behavior Baseline (observed YYYY-MM-DD)` markdown emitter for Plan 03's rollback runbook appendix (D-14 contract).
  - SSRF-guarded operator tooling that cannot be pointed outside localhost.
  - Empirical gate (SMOKE-01) plus three OBSERVED-only probes (SMOKE-02/03/04) covering ws_url presence, end-to-end Q&A + post-cap reconnect, and two-session concurrency.
affects: [01-03 (rollback-runbook authoring — consumes the baseline block verbatim), 02-* (Stage 1 deploy — baseline must exist before push)]

# Tech tracking
tech-stack:
  added: []   # No new dependencies — reuses httpx (already pinned in backend/requirements.txt).
  patterns:
    - "Operator-tooling lives under scripts/ (new directory this plan)."
    - "SSRF allowlist guard via ALLOWED_BASE_URL_PREFIXES at script entry."
    - "Exception-safe summary emission: never str(exc), only type(exc).__name__ (threat T-02-03 mitigation)."
    - "Single markdown block emitted on stdout, designed to be copy-pasted verbatim into ops docs."

key-files:
  created:
    - scripts/smoke-liveavatar.py   # 512-line single-file CLI; no backend imports.
  modified: []   # Zero backend/*.py modifications (scope discipline per D-13).

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

requirements-completed: [SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04]  # Tooling is SHIPPED; empirical validation of Task 2 is gated on operator run (see below).

# Metrics
duration: ~5 min (script authoring; operator runtime is ~2.5 min separately)
completed: 2026-04-22
---

# Phase 1 Plan 02: Local Smoke-Test Tool Summary

**Standalone Python CLI at `scripts/smoke-liveavatar.py` that drives the local FastAPI backend's `/session`, `/speak`, and `/interrupt` endpoints under sandbox config and emits a paste-ready `## Sandbox Behavior Baseline` markdown block mapping SMOKE-01 (hard gate) and SMOKE-02/03/04 (OBSERVED) for Plan 03's runbook.**

## Performance

- **Duration:** ~5 min (authoring); operator run is ~2.5 min wall-clock (SMOKE-03 sleeps ~130 s for the cap-wait probe).
- **Started:** 2026-04-22T09:26:00Z (approx — executor invoke)
- **Completed:** 2026-04-22T09:26:41Z (Task 1 committed; Task 2 awaiting operator action — see below)
- **Tasks:** 1/2 fully complete on-agent (Task 2 is a `checkpoint:human-verify` requiring the operator to run the tool against a live backend)
- **Files modified:** 1 (scripts/smoke-liveavatar.py created; zero backend/*.py touched)

## Accomplishments

- Created `scripts/` directory (new) and `scripts/smoke-liveavatar.py` (single-file, 512 lines).
- Script implements the plan's 13-point structure exactly: module docstring + prerequisites, SSRF-guarded base-URL validation, `/health` preflight, four SMOKE checks, argparse CLI with `--base-url` / `--json`, markdown + JSON emitters, and exit-code-0-iff-SMOKE-01-PASS hard gate.
- All five observation sets from D-07 are captured in the script's output logic: (a) HTTP status + elapsed on `/session`, (b) `ws_url` presence check, (c) elapsed-to-first-session, (d) two-session concurrency probe, (e) post-cap reconnect on a fresh UUID.
- Zero new dependencies — reuses the `httpx` pin already in `backend/requirements.txt` so the script runs from the existing backend venv.
- Threat-model mitigations implemented: T-02-01 (allowlisted summary fields only), T-02-02 (SSRF allowlist), T-02-03 (type-name-only exception summaries), T-02-04 (exit-1 hard gate on SMOKE-01 FAIL).

## Task Commits

1. **Task 1: Create `scripts/smoke-liveavatar.py`** — `387e8b1` (feat)

**Plan metadata:** (written by orchestrator after this SUMMARY is finalised.)

_Note: Task 2 is a `checkpoint:human-verify` requiring an operator-run against a live local backend with a real LiveAvatar paid API key. It produces no source commit — the acceptance signal is the pasted `## Sandbox Behavior Baseline` block delivered via the resume-signal. See [Task 2 Status](#task-2-status--awaiting-operator-action) below._

## Files Created/Modified

- `scripts/smoke-liveavatar.py` (created) — Single-file CLI smoke tool. Imports stdlib + `httpx` only; no backend imports. Contains four `run_smoke_NN` coroutines, a CheckResult dataclass, SSRF-guarded `_validate_base_url`, `_preflight` against `/health`, markdown + JSON summary emitters, and argparse-driven `main()` coroutine.
- No other files touched.

## Decisions Made

- **Filename: `smoke-liveavatar.py`** (kebab-case) — matches the existing `setup-local.ps1` naming convention at the repo root (per Claude's Discretion in D-14).
- **Output: markdown by default, JSON via `--json`** — gives the operator ergonomic paste-into-runbook (the common path) while still supporting a machine-readable form (per D-14 "Claude's Discretion" allowance for both shapes).
- **SMOKE-02 reuses SMOKE-01's body** — avoids a second `/session` call that would double-consume sandbox credits and could itself trigger the concurrency cap SMOKE-04 is trying to measure cleanly.
- **SMOKE-04 runs after SMOKE-01/03** — per the plan's note that the concurrency probe must not race 01-03. After the ~130 s cap-wait in SMOKE-03, the backend session dict has aged out, giving SMOKE-04 a clean slate.
- **Exception handling: log traceback via `logger.exception`, summarize via `type(exc).__name__` only** — prevents exception messages (which the backend may have enriched with provider response text) from leaking into the pasted summary.

## Deviations from Plan

None — plan executed exactly as written. All 13 structural points of the Task 1 `<action>` block (imports, constants, logging, dataclass, SSRF guard, preflight, four SMOKE coroutines, summary emitter, main, entrypoint) implemented verbatim. All acceptance criteria satisfied by mechanical verification (see [Self-Check](#self-check--passed)).

**Total deviations:** 0
**Impact on plan:** None — scope-discipline boundary (D-13, zero `backend/*.py` edits) held.

## Issues Encountered

None during authoring. Operator may encounter D-10 cases (a/b/c) at runtime — those are captured explicitly by the script's output rather than by this summary:
- D-10 (a) — paid key rejects `is_sandbox=true`: SMOKE-01 reports FAIL with a `"Possible D-10 case (a)"` note in `CheckResult.details` (internal-only; informs the operator's escalation decision).
- D-10 (b) — paid key silently accepts and consumes paid credits: not detectable client-side; operator must verify via LiveAvatar dashboard post-run (tracked in Plan 03 runbook).
- D-10 (c) — paid key accepts and routes to sandbox: SMOKE-01 = PASS; this is the expected happy path for Phase 1.

## Task 2 Status — Awaiting Operator Action

**Task 2 is a `checkpoint:human-verify` gate and is NOT complete on this executor pass.** Per the orchestrator's explicit constraint ("`checkpoint:human-action` state — not fabricated PASS"), no baseline block has been written here. The operator must:

1. Start the backend locally with the sandbox env per Task 2 step 1 (see `01-02-PLAN.md`).
2. Run `python scripts/smoke-liveavatar.py` from the backend venv.
3. Paste the emitted `## Sandbox Behavior Baseline (observed YYYY-MM-DD)` block into the resume-signal.
4. That pasted block — verbatim — becomes the input for Plan 03's `docs/rollback.md` appendix (D-14 contract: the pasted block is the SOURCE OF TRUTH; do not edit it).

**Escalation path if SMOKE-01 FAILs** (D-10 case a): planner/operator jointly decide per D-10 whether to provision a free-tier key mid-phase or proceed to Phase 2 with the observed behavior documented. The decision itself must be recorded in the Plan 03 runbook.

Until Task 2 is signalled approved with a pasted baseline, Phase 1 success criterion "empirical sandbox code-path validation" remains unmet.

## Threat Flags

None. The new surface introduced by this plan is a localhost-only CLI guarded by `ALLOWED_BASE_URL_PREFIXES`; no network endpoints, auth paths, file-access patterns, or trust-boundary schema changes were added.

## Next Phase Readiness

- **Tool ready:** `scripts/smoke-liveavatar.py` is syntactically valid, convention-compliant, and callable from the backend venv with no additional setup.
- **Blocker:** Plan 03 (`docs/rollback.md` authoring) cannot fill its "Sandbox Behavior Baseline" appendix until the operator runs Task 2 and delivers the pasted block.
- **Scope-discipline verified:** `git diff --name-only HEAD~1 HEAD` shows only `scripts/smoke-liveavatar.py` added; zero `backend/*.py` entries.

## Self-Check — PASSED

Mechanical verification of every acceptance criterion from Task 1:

- [x] `scripts/` directory exists (created fresh by `git add`).
- [x] `scripts/smoke-liveavatar.py` exists — `git show HEAD:scripts/smoke-liveavatar.py` succeeds.
- [x] Python syntax valid — `python -c "import ast; ast.parse(open('scripts/smoke-liveavatar.py', encoding='utf-8').read())"` exits 0 (confirmed during execution).
- [x] First non-blank line is `from __future__ import annotations` (line 1).
- [x] Module docstring present — triple-quoted block on lines 3–23, before any real `import`.
- [x] Contains `def main(` — async form at line 446 (`async def main() -> int:`).
- [x] Contains all four tokens `SMOKE-01`, `SMOKE-02`, `SMOKE-03`, `SMOKE-04` — verified via grep (multiple matches each).
- [x] Contains literal `## Sandbox Behavior Baseline` — present in the markdown emitter at line 426.
- [x] Contains `ALLOWED_BASE_URL_PREFIXES` (SSRF guard) — declared line 45, enforced in `_validate_base_url`.
- [x] Contains CLI flag `--base-url` (argparse) — line 452.
- [x] Does NOT contain `^from backend` or `^import backend` — grep returned 0 matches.
- [x] Does NOT leak `LIVEAVATAR_API_KEY` in any `print(...)` or `logger.*(...)` call — grep of `(print|logger\.(info|warning|error|exception)).*LIVEAVATAR_API_KEY` returned 0 matches. The only textual occurrence of the name is in the docstring's prerequisites listing, which is documentation not runtime output.
- [x] Zero `backend/*.py` files modified — `git show --stat HEAD` shows only `scripts/smoke-liveavatar.py`.
- [x] Commit exists for Task 1 — `387e8b1` present in `git log`.

All automated verification commands from the plan's `<verify><automated>` block succeed.

---

*Phase: 01-infra-wiring-local-smoke-test*
*Plan: 02 — Local smoke-test tool*
*Completed: 2026-04-22 (tool authored; operator-run Task 2 pending)*
