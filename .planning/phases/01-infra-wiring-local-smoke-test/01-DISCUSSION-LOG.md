# Phase 1: Infra Wiring + Local Smoke Test - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 1-Infra-Wiring-Local-Smoke-Test
**Areas discussed:** Rollback runbook location, Smoke test driver, Scope discipline (Pitfalls #9 & #11), Smoke observation capture, Smoke script impl, API key provisioning

---

## Rollback Runbook Location (CONFIG-03)

| Option | Description | Selected |
|--------|-------------|----------|
| docs/rollback.md (Recommended) | Dedicated file under docs/ — discoverable, survives README churn, can expand with more runbooks later. Referenced from README with a one-liner. | ✓ |
| README.md section | Append '## Rollback' section to root README. Single surface, but README is already long (~250 lines) and mixes setup + ops. | |
| .planning/runbooks/rollback.md | Co-located with planning artifacts. Keeps ops docs out of public README, but less discoverable for future operators. | |

**User's choice:** docs/rollback.md (Recommended)
**Notes:** Standard ops-doc location; README gets a one-line pointer.

---

## Smoke Test Driver & Recording (SMOKE-01…04)

| Option | Description | Selected |
|--------|-------------|----------|
| Checked-in script + markdown log (Recommended) | scripts/smoke-liveavatar.py (or .sh) that hits /v1/sessions/token + /v1/sessions/start and prints pass/fail. Observed findings (ws_url presence, concurrency, end_reason) recorded in docs/rollback.md or a sibling SMOKE-TEST.md. Reusable for future tier changes. | ✓ |
| curl commands in runbook only | Manual curl/Invoke-RestMethod commands documented in the runbook. Operator runs them, pastes output into a 'Smoke observations' section. Zero script maintenance, but easy to skip steps. | |
| Browser-driven via setup-local.ps1 | Use existing setup-local.ps1 + frontend + manual Q&A flow. Closest to real UX, but endpoint-level observations (ws_url presence, 401/402/429) are harder to capture without network tab notes. | |

**User's choice:** Checked-in script + markdown log (Recommended)
**Notes:** Re-runnable tool; reduces operator error on future tier changes.

---

## Pre-Deploy Hardening Scope (Pitfalls #9, #11)

| Option | Description | Selected |
|--------|-------------|----------|
| Stay scope-strict (Recommended) | Honor REQUIREMENTS.md Out of Scope (no backend/*.py changes this milestone). Hardening items captured as deferred ideas for a follow-up milestone. Ship the tier switch cleanly first. | ✓ |
| Expand to critical-only | Ship just the two highest-leverage hardening items: resetSessionId fix + mock-mode prod guard. Both <20 LOC. | |
| Expand to full Pitfall #9 + #11 set | Ship all 5 hardening items: SESSION_IDLE_TTL bump, resetSessionId fix, narrowed excepts, speak_ws asyncio.Event, mock-mode guard. Contradicts REQUIREMENTS.md Out of Scope. | |

**User's choice:** Stay scope-strict (Recommended)
**Notes:** Deferred items preserved in CONTEXT.md `<deferred>` for future milestone surfacing.

---

## Smoke Observation Capture

| Option | Description | Selected |
|--------|-------------|----------|
| Single appendix in the runbook doc (Recommended) | Observations appended to docs/rollback.md as a dated 'Sandbox behavior baseline' section. One file to update, lives alongside the rollback procedure so operators see both together. | ✓ |
| Update research/PITFALLS.md in place | Resolve the LOW-confidence items in PITFALLS.md by editing that file directly. Keeps research docs as source of truth but mutates 'frozen' artifacts. | |
| New .planning/research/SANDBOX-BEHAVIOR.md | Dedicated research artifact for empirically-observed sandbox limits. More file overhead for a small baseline. | |

**User's choice:** Single appendix in the runbook doc (Recommended)
**Notes:** Research artifacts stay frozen; ops baseline lives with ops runbook.

---

## Smoke Script Implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Python, drives backend endpoints (Recommended) | scripts/smoke-liveavatar.py uses httpx to hit the running FastAPI's /session + /speak + /interrupt endpoints. Exercises the actual code path that production runs. Matches backend language. Requires backend running locally. | ✓ |
| Python, hits LiveAvatar directly | scripts/smoke-liveavatar.py calls LiveAvatar /v1/sessions/token + /v1/sessions/start directly with httpx, bypassing FastAPI. Isolates 'provider auth' from 'backend wiring'. Cleaner gate but not end-to-end. | |
| PowerShell, drives backend endpoints | scripts/smoke-liveavatar.ps1 matches the existing setup-local.ps1 convention. Windows-first. Simpler to chain after setup-local.ps1, but less cross-platform for future CI. | |
| Both: pwsh wrapper → python core | setup-local.ps1 pattern for the runner, Python for the actual HTTP work. Doubles the surface area. | |

**User's choice:** Python, drives backend endpoints (Recommended)
**Notes:** Proves the wiring end-to-end, not just provider auth.

---

## Free-Tier API Key Provisioning (CONFIG-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Already obtained, just needs rotation (Recommended) | User has a free-tier LiveAvatar account + API key in hand. Phase 1 work: smoke test locally with it, then rotate GitHub secret LIVEAVATAR_API_KEY to the new value. CONFIG-02 marked complete during Phase 1 execution. | |
| Not yet obtained — provisioning is a Phase 1 task | Planner must add an explicit 'Create free-tier LiveAvatar account, obtain API key' step before SMOKE-01. Blocks smoke test start until user completes it out-of-band. | |
| Existing paid key with is_sandbox=true is sufficient | Smoke test uses the current paid-tier key but sets is_sandbox=true to exercise the sandbox code path. Defers actual free-tier key rotation to Phase 2. Risk: doesn't prove free-tier auth works — provider may treat sandbox calls on paid keys differently. | ✓ |

**User's choice:** Existing paid key with is_sandbox=true is sufficient
**Notes:** Explicit scope reduction — CONFIG-02 moves to Phase 2. Real free-tier auth verification is deferred to Phase 2 DEPLOY-02 "0 credits consumed" check. Risk (provider may reject or silently bill) is captured in CONTEXT.md D-10 as an execution-time monitoring item.

---

## Claude's Discretion

- Filename casing convention for the smoke script (kebab vs snake)
- Smoke script output format (JSON + text, plain text only, or both)
- Phase 1 commit granularity (per requirement cluster vs per file)
- Exact wording of the README → rollback.md pointer

## Deferred Ideas

See CONTEXT.md `<deferred>` section for the full list. Highlights:
- All backend Python hardening items (SESSION_IDLE_TTL, exception narrowing, speak_ws race, mock-mode guard) → follow-up hardening milestone
- resetSessionId stranding fix → follow-up milestone (VideoPlayer also locked by Phase 3 scope rules)
- MAX_SESSIONS / sandbox cap alignment → conditional on smoke findings
- DEPLOY_NONCE, /health extension, avatar_tier GA4 property → observability follow-up
- CONFIG-02 free-tier key rotation → Phase 2 (not deferred — relocated)
</content>
</invoke>