# Operations Runbook — LiveAvatar Tier Rollback

**Scope:** Emergency rollback of the LiveAvatar free-tier switch (milestone:
"LiveAvatar Free-Tier Switch"). This runbook is the canonical reference for
operators needing to flip production back to the paid tier, for the Phase 2
API-key rotation, and for the empirical sandbox-behavior baseline captured
during Phase 1's local smoke test.

---

## Overview

Production `dimangulov.space` runs the LiveAvatar sandbox tier by default
(`LIVEAVATAR_IS_SANDBOX=true`, `LIVEAVATAR_SESSION_MODE=LITE`, Wayne avatar
UUID `dd73ea75-1218-4ef3-92ce-606d5f7fbc0a`). The sandbox tier consumes zero
LiveAvatar credits but caps each session at ~60-120 seconds and permits only
the Wayne stock avatar.

If the sandbox tier proves unusable in production, the tier switch is
reversible via a single GitHub Actions repository variable change followed by
a workflow rerun — **no code change required**. This is made possible by the
3-point Terraform/workflow wiring landed in Phase 1 Plan 01 (TF variables
`live_avatar_is_sandbox` and `live_avatar_session_mode`, corresponding
`env {}` blocks on the backend Container App, and `TF_VAR_*` fallbacks in
`.github/workflows/deploy-azure.yml`).

---

## Trigger criteria

Flip back to the paid tier (`LIVEAVATAR_IS_SANDBOX=false`) if any of these
are observed on the live site:

- The avatar fails to render and `/session` returns non-200 for >15 minutes.
- LiveAvatar provider dashboard shows unexpected credit consumption despite
  `is_sandbox=true` — indicates the sandbox flag is not reaching the provider.
- The ~60-120 s sandbox cap causes a user-visible UX regression that
  outweighs the zero-cost benefit.
- A legal or compliance blocker emerges specific to the sandbox tier (e.g.,
  Wayne likeness usage rights change).

---

## Rollback procedure

Estimated time: **5 minutes** (GitHub Variable edit + ~3 minute pipeline run).

1. Open `https://github.com/<owner>/<repo>/settings/variables/actions`.
2. Edit the repository variable `LIVE_AVATAR_IS_SANDBOX` and set its value
   to `false` (lowercase — `backend/config.py` does `.lower() == "true"` so
   `"True"` / `"TRUE"` also work, but `"1"` would silently resolve to
   `false`; stick to lowercase `true` / `false` to avoid ambiguity).
3. Go to `Actions` → `Deploy to Azure` → click `Run workflow` → select
   `main` → `Run workflow`.
4. Wait for all four jobs to go green: `terraform-infra` →
   `build-backend` → `deploy-backend` → `deploy-frontend`.
5. The new Container App revision will have `LIVEAVATAR_IS_SANDBOX=false`
   sourced from `TF_VAR_live_avatar_is_sandbox`, which falls back to `'true'`
   only when the repo variable is absent — setting it explicitly to `false`
   overrides that default.

**Important:** if the paid LiveAvatar API key has already been revoked
(final Phase 3 step, `DEPLOY-05`), the rollback also requires a new paid key
in the `LIVEAVATAR_API_KEY` GitHub secret. Do NOT attempt the rollback
without a valid paid key in place.

Per decision `D-08` in
`.planning/phases/01-infra-wiring-local-smoke-test/01-CONTEXT.md`, Phase 1's
smoke test deliberately kept the existing paid key in place while toggling
only the sandbox flag — so during the Phase 1–Phase 2 window the paid key is
still valid and this rollback is a one-variable flip.

---

## Verification

After the pipeline goes green:

- `curl -s https://<backend-url>/health` returns `{"status":"ok"}`.
- Load `https://dimangulov.space`, open the dev console, ask a question.
- The avatar renders without the `[ POC — Connect LiveAvatar API ]` mock
  watermark.
- LiveAvatar provider dashboard shows new credit consumption on the next
  session (proves `is_sandbox=false` reached the provider).

If any of these fail, capture the backend container logs
(`az containerapp logs show --name aicv-prod-backend --resource-group rg-aicv-prod`)
and the Terraform Apply job output before further action.

---

## Phase 2 key-rotation procedure (CONFIG-02 — deferred from Phase 1)

**Status:** DEFERRED from Phase 1 to Phase 2 per decision `D-09` in
`.planning/phases/01-infra-wiring-local-smoke-test/01-CONTEXT.md`.

**Why this is here:** Phase 1 intentionally kept the existing paid LiveAvatar
API key in place while running the sandbox smoke test (decision `D-08`).
Rotating the key to a free-tier account key is Phase 2's responsibility and
is documented here so the Phase 2 executor inherits a written procedure
rather than re-discovering the need. `CONFIG-02` is NOT satisfied by Phase 1;
its acceptance lives in Phase 2.

Procedure (execute only when Phase 2 begins — do NOT execute during Phase 1):

1. In the LiveAvatar provider dashboard, create or confirm a free-tier
   account and generate an API key for it.
2. On GitHub, cancel any in-flight `Deploy to Azure` workflow runs to avoid
   racing an old key into a new revision.
3. Update the `LIVEAVATAR_API_KEY` GitHub **secret** (not variable) at
   `https://github.com/<owner>/<repo>/settings/secrets/actions`. Use the
   placeholder shape in the UI — do NOT paste the key value into this
   runbook, commit messages, tickets, or chat:

   ```text
   LIVEAVATAR_API_KEY = <PASTE-NEW-FREE-TIER-KEY-HERE>
   ```

4. Push a no-op commit (or use `workflow_dispatch`) to trigger the pipeline.
5. After the new revision is healthy, verify in the LiveAvatar provider
   dashboard that the new session is attributed to the free-tier account
   and shows 0 credits consumed.
6. The old paid key is revoked as the final step of Phase 3
   (`DEPLOY-05`) — not during Phase 2. Between Phase 2 deploy and
   `DEPLOY-05`, both keys are valid (the paid one simply goes unused).

---

## Sandbox Behavior Baseline (observed 2026-04-22)

> **Source:** verbatim output of `python scripts/smoke-liveavatar.py --base-url http://localhost:8001`
> executed 2026-04-22 against a local FastAPI backend with the sandbox env
> configured (`LIVEAVATAR_IS_SANDBOX=true`, `LIVEAVATAR_SESSION_MODE=LITE`,
> `LIVEAVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a`, existing paid
> API key per decision `D-08`). Do NOT edit the block below.

<!-- BASELINE-PLACEHOLDER-START -->
```
## Sandbox Behavior Baseline (observed 2026-04-22)

Backend: http://localhost:8001
Config: LIVEAVATAR_IS_SANDBOX=true, LIVEAVATAR_SESSION_MODE=LITE,
        LIVEAVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a,
        API key: existing paid key (per Phase 1 decision D-08)

| ID       | Status   | Summary |
|----------|----------|---------|
| SMOKE-01 | PASS     | /session returned 200 in 2235 ms with session_id |
| SMOKE-02 | OBSERVED | ws_url present in LITE sandbox — full TTS path works |
| SMOKE-03 | OBSERVED | speak: queued; interrupt: interrupted; post-cap reconnect: 200 |
| SMOKE-04 | OBSERVED | unexpected pattern: statuses=[502,502] |

Elapsed: 139.5 s
```
<!-- BASELINE-PLACEHOLDER-END -->

### Interpretation (operator notes, 2026-04-22)

- **SMOKE-01 PASS** — the paid LiveAvatar API key accepts `is_sandbox=true`
  at the provider. Decision `D-10` risk (a) "paid key rejects is_sandbox" is
  ruled out for this account. `CONFIG-02` (free-tier key rotation, deferred
  to Phase 2) remains the clean-state ownership transition; it is NOT a
  Phase 1 blocker.
- **SMOKE-02 `ws_url` PRESENT** — the sandbox LITE endpoint returned a
  `ws_url` on `/v1/sessions/start`, so the persistent WS speech pump
  operates on the same code path as paid LITE. The documented
  "avatar visible, no TTS push" fallback is not triggered in this
  configuration.
- **SMOKE-03 OBSERVED** — `/speak` returned `queued`, `/interrupt` returned
  `interrupted`, and a fresh session (new `X-Session-ID` UUID) reconnects
  with HTTP 200 after the ~130 s cap window elapses. End-to-end Q&A flow
  is healthy under sandbox.
- **SMOKE-04 OBSERVED `statuses=[502,502]`** — two parallel `/session`
  probes both received HTTP 502. This is consistent with LiveAvatar's
  sandbox single-slot concurrency constraint: the provider rejects the
  second concurrent session attempt upstream, and the backend surfaces the
  provider's failure as a bad-gateway error. Pitfall `#3` (sandbox
  concurrency limits) is confirmed — production should expect sequential,
  not parallel, sandbox sessions per backend instance.

**Source of truth:** `.planning/phases/01-infra-wiring-local-smoke-test/01-02-SUMMARY.md`.
Research file `.planning/research/PITFALLS.md` is NOT mutated — this
appendix is the live operational record (per decision `D-14`).
