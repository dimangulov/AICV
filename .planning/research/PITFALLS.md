# Pitfalls Research — LiveAvatar Tier Switch (Paid → Free/Sandbox)

**Domain:** SaaS AI-avatar tier migration on an existing live production deployment (`dimangulov.space`)
**Researched:** 2026-04-22
**Confidence:** HIGH (grounded in the actual codebase; cross-referenced with `CONCERNS.md` audit)

This document catalogs pitfalls specific to switching the deployed site from a paid LiveAvatar plan (custom avatar) to the free/sandbox tier (stock avatar), plus the associated disclaimer and deploy work. Generic "SaaS migration" advice is omitted — every pitfall below is anchored to a file/line in this repo or a concrete behaviour of this system.

---

## Critical Pitfalls

### Pitfall 1: Intro-played flag masks the new avatar for returning visitors

**What goes wrong:**
Returning visitors already have `localStorage["aicv_intro_played"] === "1"` from the paid-avatar era. On the redeployed site, `page.tsx` skips `speakText(AVATAR_INTRO)` for them. They see a different face, hear no explanatory intro, and the disclaimer (if only rendered on first-visit) never fires. Worst case: a hiring manager who bookmarked the site last month returns, sees a stranger's face speaking as "Damir", and concludes the site is broken or deceptive.

**Why it happens:**
`INTRO_PLAYED_KEY = "aicv_intro_played"` (`frontend/app/page.tsx:15`) is a static string with no versioning. `localStorage` persists indefinitely. The intro text itself is hard-coded (`AVATAR_INTRO` line 17-20) and does not currently mention that the avatar is a stock likeness — so even if the intro DID play for returning visitors, the disclaimer would still need to be in the UI, not only in speech.

**How to avoid:**
1. Bump the key: `INTRO_PLAYED_KEY = "aicv_intro_played_v2"` (or `_stock_avatar`). Every returning visitor will hear the new intro exactly once.
2. Make the disclaimer a persistent UI element (banner / badge under the video) that renders unconditionally — do NOT gate it on first-visit logic. LocalStorage flags must never be the sole carrier of a legally/ethically meaningful notice.
3. Update `AVATAR_INTRO` to explicitly mention the stock avatar, e.g. "You're seeing a generic avatar — I'm Damir's digital twin, not his likeness."

**Warning signs:**
- QA tester using a "fresh profile" sees the intro; QA tester using their normal browser does not.
- Analytics shows a drop in `VIDEO_PLAY` → chat engagement ratio after deploy (users bouncing in confusion).
- Support/LinkedIn messages asking "is this your real face?"

**Phase to address:**
Phase 1 (config + UI). Must ship together with the disclaimer, not deferred.

---

### Pitfall 2: Stale cached LiveAvatar session crosses the tier boundary

**What goes wrong:**
A UserSession lingering in `_user_sessions` at deploy time holds `liveavatar_data`, `liveavatar_session_id`, and `liveavatar_session_token` that were minted against the **paid** API key / custom avatar. After deploy, `is_valid()` (`backend/avatar.py:100`) returns True for up to 30 minutes (`_LIVEAVATAR_SESSION_TTL = 1800.0`, line 126), and `get_or_create_liveavatar_session` happily **reuses the old cached session**. For that session's TTL the user speaks through a custom-avatar WebRTC room authenticated with the old JWT — even though the backend now has the free-tier API key.

**Why it happens:**
- Azure Container Apps rolling deploys create a new revision; old replicas drain over ~30 s. But `_user_sessions` is in-process per replica (known single-replica scaling limit, `CONCERNS.md` §Scaling). On a `minReplicas: 0` scale-to-0 setup the dict usually goes empty on redeploy, BUT if traffic keeps at least one replica warm during the rollout, the old revision keeps serving with old secrets until it drains.
- The frontend's `aicv_session_id` in `localStorage` outlives the deploy entirely. A returning user hits the new backend carrying the old `X-Session-ID` — but since session state is in-process, the new revision creates a fresh UserSession. **However**, the old revision (if still draining) may still have the session alive and be holding a live LiveAvatar WS consuming paid credits until `_avatar_ws_loop`'s 180 s keep-alive or `SESSION_IDLE_TTL = 120 s` evicts it.
- Redis/shared session state is explicitly Phase 3 future work (not this milestone), so there is no clean cross-revision invalidation primitive.

**How to avoid:**
1. **Deploy during a low-traffic window** (site is a personal CV — most hours are low traffic). Reduces the chance of mid-session crossover.
2. **Force a cold restart** by setting `minReplicas: 0` briefly, or bump a no-op env var (e.g. `DEPLOY_NONCE=<timestamp>`) so the Container App revision image is clearly different and old replicas get SIGTERM'd promptly.
3. **Rotate the old paid API key at the LiveAvatar provider AFTER the new revision is confirmed healthy.** This guarantees any lingering old replica attempting to mint NEW sessions will 401; existing sessions expire within the LiveAvatar TTL.
4. **Add a one-time client-side flag bump** (see Pitfall 1) so returning users' `aicv_session_id` is also rotated, sidestepping any backend `UserSession` that happens to survive.

**Warning signs:**
- Post-deploy logs show `"Reusing cached LiveAvatar session"` (`avatar.py:259`) shortly after revision start — should be rare if the new replica is truly fresh.
- LiveAvatar billing dashboard shows paid-tier usage AFTER the key rotation timestamp.
- User reports seeing the old avatar briefly then the new one swap in.

**Phase to address:**
Phase 2 (deploy). Rollout procedure must explicitly order: (a) deploy code → (b) wait for health green → (c) rotate old paid key.

---

### Pitfall 3: Sandbox rate / concurrency limits fire under any non-trivial load

**What goes wrong:**
LiveAvatar's free/sandbox tier is certain to have tighter limits than the paid plan — typical SaaS sandbox patterns include: low concurrent-session cap (often 1–5), short per-session duration (e.g. 3–10 minutes max, after which `session.stopped` fires regardless of activity), monthly minute quota, and stricter per-minute request rate. The site currently allows `MAX_SESSIONS=50` and imposes no coordination with the upstream LiveAvatar quota (`CONCERNS.md` §Scaling). A LinkedIn share spike → several concurrent visitors → second-or-third visitor hits LiveAvatar 429/403 → backend surfaces a generic error → avatar never connects → site looks broken.

**Why it happens:**
- `backend/avatar.py:287-310` has retry logic for HTTP 500 on `/sessions/start` but NOT for 402/403/429. A "quota exceeded" response will bubble as `HTTPStatusError` caught by the broad `except Exception as exc` at line 395, logged, and returned as a generic "Session setup failed".
- `_avatar_ws_loop` treats `session.stopped` as terminal (`avatar.py:227-234`) — good — but does NOT distinguish "ended because max duration reached (sandbox limit)" from "user closed tab". Users mid-conversation who hit the sandbox duration cap will see the avatar freeze.
- Frontend `VideoPlayer.tsx:123-166` retries once on connection failure but the retry uses the same `getSession` path — which will also fail if the quota is the cause. The user sees "Retry failed" with the raw error string.

**How to avoid:**
1. **Look up the actual sandbox limits** in LiveAvatar's documentation BEFORE switching. Document them in PROJECT.md. At minimum: max concurrent sessions, max session duration, max monthly minutes, rate limits.
2. **Handle 402/403/429 from `/sessions/token` and `/sessions/start` explicitly.** Map them to HTTP 503 from our backend with a user-friendly message ("The free avatar has hit its concurrency limit — please try again in a minute"). Set `Retry-After` header.
3. **Consider lowering `MAX_SESSIONS`** to match (or slightly undershoot) the sandbox concurrent-session cap so we reject at the edge rather than letting LiveAvatar 429 us mid-flow.
4. **Frontend: show a dedicated "busy, try again" state** when the backend returns 503 with a specific reason code. Don't retry automatically on 503 — that makes the problem worse.
5. **Graceful duration-cap handling**: when `session.stopped` arrives with an end_reason indicating duration limit, surface a banner: "Free-tier session limit reached — click to reconnect." Rather than silently breaking.

**Warning signs:**
- Post-deploy, multiple concurrent visitors (even 2–3) see "Connection failed".
- Container App logs show `LiveAvatar /start returned <non-500>` or `401/402/403/429`.
- `session.stopped` events arrive with `end_reason: "duration_limit"` or similar.

**Phase to address:**
Phase 1 (config investigation — confirm actual limits), reinforced in Phase 2 (add specific error handling before deploy).

---

### Pitfall 4: Endpoint URL or payload differs between paid and sandbox tiers

**What goes wrong:**
Backend assumes `LIVEAVATAR_BASE_URL` (`backend/config.py`) is the same for both tiers and that `is_sandbox: true` in the `/sessions/token` body is all that's needed. If LiveAvatar's sandbox actually requires (a) a different base URL, (b) a different `avatar_id` format, (c) a different `mode` (sandbox may not support `CUSTOM`, may force `LITE`), or (d) a different auth header — the token call silently fails or returns a different response shape. The current code does `r.json()["data"]["session_token"]` (`avatar.py:279-281`) — a missing `data` field or different key names raises `KeyError` caught by the broad except → generic "Session setup failed".

**Why it happens:**
SaaS vendors commonly bifurcate sandbox endpoints (`sandbox.api.liveavatar.com` vs `api.liveavatar.com`), or change the required body parameters at tier boundaries. Training data on LiveAvatar specifically is thin (LiveAvatar is a less-documented provider than HeyGen/D-ID), so assumptions are especially risky.

**How to avoid:**
1. **Before changing deployed config, run the free-tier credentials locally** with `LIVEAVATAR_IS_SANDBOX=true`, the free API key, and the expected stock `LIVEAVATAR_AVATAR_ID`. Verify end-to-end: token → start → LiveKit video → WebSocket keep-alive → speak.
2. **Check LiveAvatar's sandbox documentation explicitly for:** base URL differences, allowed `mode` values, required `avatar_id` prefixes, whether `is_sandbox` is still the right flag name.
3. **Add an env var** `LIVEAVATAR_BASE_URL` override if it isn't already (spot-check: `config.py` line reference required) so the base URL can be switched without code changes.
4. **Log the full non-secret request body** at DEBUG for `/sessions/token` and `/sessions/start` — makes misconfig diagnosable in prod without redeploying with more logging.

**Warning signs:**
- Local smoke test against free-tier credentials succeeds; deploy-to-prod fails with 404 or 401 on `/sessions/token`.
- `r.raise_for_status()` raises with body mentioning unknown field / unsupported mode.
- LiveKit client in frontend receives a token but cannot join the room (mismatched livekit_url shape).

**Phase to address:**
Phase 1 — local free-tier validation is a prerequisite to starting Phase 2 (deploy).

---

### Pitfall 5: Terraform drift — secrets managed outside TF diverge on re-apply

**What goes wrong:**
If the operator sets `LIVEAVATAR_API_KEY` directly in Azure Portal / `az containerapp update` to rotate the key quickly, the next `terraform apply` in CI sees the TF-declared value (or TF-declared reference to a tfvar) and OVERWRITES the manually-set key — reverting to the old paid key or setting it empty. The backend on the next revision then has the wrong credentials, and if the portal-set value WAS the free-tier key, the paid key returns and we're back to paying / AuthZ mismatched.

**Why it happens:**
Pipeline (`.github/workflows/deploy-azure.yml`) runs `terraform-infra` as job 1. Secrets can be sourced in TF via (a) `var` from GitHub Secret → tfvars, (b) Key Vault data source, or (c) ignored entirely with `lifecycle { ignore_changes = [secret] }`. Without inspecting the TF config (out of scope here) the operator cannot assume which model is in use. "I'll just update the env var in portal for now" is a very common mistake with Container Apps.

**How to avoid:**
1. **Single source of truth for secrets**: either (a) put the free-tier API key in the GitHub Secret that TF reads and redeploy through the pipeline, OR (b) move secrets to Azure Key Vault and have TF reference by name with `ignore_changes` so portal edits stick.
2. **Never hand-edit Container App env vars** for values TF manages. Always flow through the pipeline.
3. **Run `terraform plan`** after any rotation and BEFORE the next apply to spot drift. The pipeline should surface plan output.
4. **Tag the GitHub Secret with tier info** (e.g. `LIVEAVATAR_API_KEY_FREE` vs `LIVEAVATAR_API_KEY_PAID`) so the wrong key cannot be selected by accident during rotation.

**Warning signs:**
- `terraform plan` shows a change to a secret env var you thought was already set.
- Post-`terraform apply`, health check fails with 401 from LiveAvatar.
- Two team members disagree about where a secret "really" lives.

**Phase to address:**
Phase 2 (deploy) — decide the TF/secret model BEFORE the first tier-switch deploy, not during an incident.

---

### Pitfall 6: Container App revision caches old env → secrets not picked up

**What goes wrong:**
You update `LIVEAVATAR_API_KEY` via TF, `terraform apply` succeeds, but the running Container App revision continues to serve with the old value. Common cause: Container Apps **require a new revision** for env-var changes to take effect on running containers; simply updating the app spec without triggering a revision does not restart containers. If the TF resource uses `azurerm_container_app` with `revision_mode = "Single"`, changing an env var DOES create a new revision — but if there's no traffic weight change, ingress might still route to the old revision until it drains. In `revision_mode = "Multiple"`, new revisions don't automatically get traffic.

**Why it happens:**
Developers from AKS / VM backgrounds expect `env` changes to hot-reload. Container Apps' revision model is subtler. Additionally, if the env var references a secret via `secretRef`, and ONLY the secret value changed (not the reference), some TF provider versions do not detect drift — the app spec hash is unchanged.

**How to avoid:**
1. **Always bump something that guarantees a new revision** when rotating a secret: add a `DEPLOY_NONCE` or `CONFIG_VERSION` env var that TF sets to the git SHA. Any secret rotation bumps this → new revision → fresh env.
2. **Verify revision mode**: if `Single`, TF should force replacement on secret-only changes. If `Multiple`, the pipeline must explicitly shift traffic: `az containerapp ingress traffic set --revision-weight <new>=100`.
3. **Post-deploy health probe** that does NOT just hit `/health` (which only checks Ollama/Qdrant/RAG per `CONCERNS.md`) — hit `/session` actually, which exercises the LiveAvatar token call with the new key. If `/session` returns 500, the env didn't propagate.
4. **Extend `/health`** to optionally probe LiveAvatar reachability — flagged as missing in `CONCERNS.md` §Missing Critical Features.

**Warning signs:**
- `terraform apply` completes cleanly, deploy pipeline goes green, but `/session` returns 500 in prod.
- `az containerapp revision list` shows multiple revisions and the latest has 0% traffic.
- Backend logs show LiveAvatar 401 but the key in portal looks correct.

**Phase to address:**
Phase 2 (deploy). Add `DEPLOY_NONCE` env var in TF and deep-probe as part of the rollout checklist.

---

### Pitfall 7: Disclaimer wording exposes legal / reputational risk

**What goes wrong:**
Several failure modes cluster here:

**7a — AI-washing complaint:** An overly coy disclaimer ("powered by AI") that doesn't clearly state the avatar is not the author's likeness invites criticism under emerging AI-transparency norms (EU AI Act Art. 50 disclosure obligations for AI-generated content / deepfakes apply to EU visitors; FTC guidance in the US targets deceptive AI endorsements). The free-tier announcement is not the legal risk — the author's-likeness-ambiguity is.

**7b — Implied endorsement by LiveAvatar:** Wording like "Official LiveAvatar integration" or "Certified by LiveAvatar" or even unattributed use of the LiveAvatar logo/trademark can breach the LiveAvatar ToS (most SaaS ToS restrict brand usage) and imply a commercial relationship that doesn't exist. Pure attribution ("uses LiveAvatar") is usually fine — marketing-style language is not.

**7c — Misleads about content:** If the disclaimer says "This site uses AI" without scoping, visitors may assume the résumé/bio/code claims are also AI-generated or hallucinated. The bio is human-authored; only the avatar rendering and LLM answer synthesis are AI. Scope matters.

**7d — Insufficient prominence:** Disclaimer inside a tab ("Design Doc" tab — who reads that?), inside a footer, or only in `AVATAR_INTRO` speech (which fires once, is non-persistent, and users often mute autoplay audio) fails the "clear and conspicuous" standard that FTC/EU regs and common ethical practice expect.

**7e — Accidentally disclaims the person:** Wording like "the avatar is AI-generated and does not represent a real person" could be read as saying Damir isn't a real person / the CV is fake. Subtle but harmful.

**Why it happens:**
Writing legally-defensible, ethically-clear, audience-appropriate disclaimer text is a distinct skill from writing UI copy. Developers default to either boilerplate ("Powered by AI") or over-disclosure ("WARNING: AI CONTENT") — both miss the mark.

**How to avoid:**
1. **Scope the disclaimer precisely**: disclose what is AI (the stock avatar appearance + the avatar's spoken voice + the LLM-composed answers) and what is NOT (the bio facts, the author's identity, the résumé).
2. **Use plain-language attribution, not marketing words**: "The avatar video is a generic likeness provided by LiveAvatar's free tier — it is not Damir's face." Avoid "official", "certified", "powered by", branded logos.
3. **Place prominently**: directly under or over the video element, visible in the default viewport. Not in a tab, not in a collapsed footer. Ideally, a small persistent badge ("Stock avatar — not a real photo") overlaid on the video corner, plus a single explanatory sentence near the header.
4. **Scope to AI output, affirm human-authored content**: one line that anchors truth ("Bio and answers are based on Damir's real experience; the avatar face and voice are AI-generated stock assets.").
5. **Review for tone**: peer-review the exact string with at least one non-developer before deploy. Read it aloud.
6. **Check LiveAvatar ToS** on trademark/logo usage before including the brand name or logo. Plain text name attribution is almost always allowed; logos and marketing-style phrasing often are not.

**Warning signs:**
- The wording mentions "powered by" / "official" / "certified" → rewrite.
- The wording is inside a tab/footer → move above the fold.
- The wording says "AI content" without scoping → scope it.
- A reader asks "wait, is the person real?" after reading it → rewrite.

**Phase to address:**
Phase 1 (UI copy). Treat disclaimer text as a reviewed artefact, not a TODO string.

---

## Moderate Pitfalls

### Pitfall 8: Mid-session failover during rolling deploy orphans live WS

**What goes wrong:**
A user is mid-conversation when the deploy rolls. Their `speak_ws` (held in `UserSession` on a specific replica) goes dark when that replica is terminated. `_avatar_ws_loop`'s `finally` sets `entry.speak_ws = None` and `invalidate()` is called — but the user's next question arrives at the NEW replica (via the `X-Session-ID` header) where no session exists yet. The new replica creates a fresh LiveAvatar session (costing a free-tier credit) and the user sees a new avatar connect mid-conversation.

**Why it happens:**
In-process session state (`CONCERNS.md` §Scaling) + no graceful-drain hook that pre-notifies clients to reconnect + Container App SIGTERM gives 30s by default, which is often not enough for a long LLM stream to finish.

**How to avoid:**
1. Deploy during low-traffic windows (human-hours-based; traffic to a personal CV is easy to predict).
2. Add a SIGTERM handler in `main.py` that marks new sessions as "draining" and returns HTTP 503 with `Retry-After` so clients retry against the new revision.
3. Frontend: on getting mid-conversation 5xx from `/ask/stream`, automatically `resetSessionId()` and show a toast "Reconnecting…" — partially exists but is coupled to video retry, not chat retry.

**Phase to address:** Phase 2 (deploy procedure), with a future Phase 3 improvement to graceful-drain.

---

### Pitfall 9: Session-state fragility compounds at tier switch (references CONCERNS.md)

**What goes wrong:**
Known existing issues from `CONCERNS.md` become visible during the tier switch because ANY small disruption (brief connectivity blip, key rotation in flight, slow `/sessions/start` on sandbox) exercises the fragile paths:

- **`speak_ws` None-check race** (`CONCERNS.md` §Known Bugs "speak_ws None-check race on first question" — `avatar.py:410-422`) — sandbox tier may have slower `/sessions/start`, so the 3 s poll is more likely to exhaust than on the paid tier.
- **`resetSessionId` stranding server-side session** (`CONCERNS.md` §Known Bugs — `VideoPlayer.tsx:128` + `api.ts:28-34`) — during the tier switch, retries will be MORE frequent as users hit provisioning errors, so stranded sessions consuming sandbox credits multiply.
- **Session eviction killing active chat** (`CONCERNS.md` §Known Bugs — `SESSION_IDLE_TTL=120 s`) — if a user reads the new disclaimer for 2+ minutes before asking a question, their session is evicted and the retry path runs on EVERY returning user.
- **Avatar WebSocket lifecycle spread across four places** (`CONCERNS.md` §Fragile Areas) — more race conditions surface under sandbox-tier slowness / tighter limits.
- **Broad exception catches swallow failures** (`CONCERNS.md` §Tech Debt) — the root cause of a failed tier switch may be invisible because multiple `except Exception` sites log a warning and continue, masking 401/402/403 from the new key.

**Why it happens:**
Pre-existing fragility that was masked by a reliable paid-tier provider surfaces when the underlying SaaS becomes slower / more constrained / more prone to reject.

**How to avoid:**
1. **Before deploy**: bump `SESSION_IDLE_TTL` back to ~600 s (10 min) for this milestone. The 120 s value is an unrelated recent optimisation that makes tier-switch symptoms worse.
2. **Before deploy**: fix the `resetSessionId` stranding — add `closeSession(oldId)` before `resetSessionId()` in `VideoPlayer.tsx:128`. One-line fix, prevents free-tier credit leak during retries.
3. **Narrow the exception catches** in `_get_or_create_liveavatar_session` so 401/402/403/429 surface as distinct HTTPExceptions — operator can see in logs exactly why the tier switch broke.
4. **Fix `speak_ws` race** — replace the 0.5s×6 poll with an `asyncio.Event` (CONCERNS.md already specifies the fix).

**Phase to address:**
Phase 1 (pre-deploy hardening). These are not scope creep — they are blockers to a smooth tier switch and each is a ~10-line change.

---

### Pitfall 10: GitHub secret rotation race

**What goes wrong:**
Operator updates the GitHub Secret `LIVEAVATAR_API_KEY` via GitHub UI to the new free-tier value. A pipeline run already in-flight (triggered by a previous push) reads the OLD secret into its workflow env because GitHub Secrets are captured at workflow-run-start. That in-flight deploy lands the OLD key into prod, overwriting whatever state was there. Confusion ensues.

**Why it happens:**
GitHub Actions workflow-level `secrets:` context is resolved when the workflow starts, not when each step runs. Rotation is not atomic across concurrent workflow runs.

**How to avoid:**
1. **Cancel in-flight workflow runs** before updating a secret.
2. **Push a no-op commit AFTER secret rotation** to trigger a fresh pipeline run that picks up the new value — this is the canonical pattern.
3. **Do not rotate secrets mid-deploy.** Sequence: rotate → push → deploy → verify.

**Phase to address:** Phase 2 (deploy procedure).

---

### Pitfall 11: Mock-mode accidentally activates in prod

**What goes wrong:**
`backend/avatar.py:361` — `if not LIVEAVATAR_API_KEY: return`. If the tier-switch botches the env propagation and `LIVEAVATAR_API_KEY` ends up empty, the backend silently falls into mock mode. Frontend `VideoPlayer.tsx:70-78` then renders the canvas placeholder with the "[ POC — Connect LiveAvatar API for live stream ]" watermark — a clearly unprofessional state on a live portfolio site.

**Why it happens:**
Graceful-degradation was designed for local dev without credentials. It's now also the "misconfigured prod" failure mode — indistinguishable from intentional.

**How to avoid:**
1. Make mock-mode opt-in explicit: only fall through if `LIVEAVATAR_ALLOW_MOCK=true` (defaults false). Absent API key + no explicit opt-in = HTTP 503 from `/session`, not silent mock.
2. Prod startup assertion: if `APP_ENV=production` and `LIVEAVATAR_API_KEY` is empty, fail fast at app startup.

**Phase to address:** Phase 1 (config hardening).

---

## Minor Pitfalls

### Pitfall 12: Intro text still references a specific avatar

**What goes wrong:**
`AVATAR_INTRO` (`page.tsx:17-20`) starts "Meet Damir Imangulov. He is a Senior Full-Stack Engineer…" — spoken in the first person as the avatar. With a generic stock face speaking, the phrasing "Meet Damir" paired with a stranger's face is uncanny. Also contains the existing typo "anyhting" (`CONCERNS.md` §Tech Debt).

**How to avoid:** Rewrite the intro to clearly frame the avatar as a digital twin / interface, not as Damir himself: "Hi — I'm a digital twin representing Damir Imangulov. The face you see is a generic stock avatar, not Damir's likeness. I can answer questions about his backend, cloud, and architecture experience." Fix "anyhting" → "anything" in the same pass.

**Phase to address:** Phase 1 (UI copy).

---

### Pitfall 13: Filler cache keyed by phrase only, not voice

**What goes wrong:** `filler_cache` (`avatar.py:61`) keys PCM audio by phrase, not by `(voice, phrase)` (`CONCERNS.md` §Fragile Areas). If the tier switch also changes `LIVEAVATAR_VOICE`, fillers spoken in the old voice persist until process restart.

**How to avoid:** (a) Confirm `LIVEAVATAR_VOICE` is NOT changing in this milestone. (b) Force a cold restart on deploy (covered by Pitfall 2's `DEPLOY_NONCE` strategy).

**Phase to address:** Phase 2 (rollout).

---

### Pitfall 14: Analytics events don't distinguish tier

**What goes wrong:** `trackEvent(EVENTS.VIDEO_PLAY)` fires identically pre and post switch. No way in GA4 to compare engagement before/after.

**How to avoid:** Add a global property `avatar_tier: "sandbox"` to `trackEvent` from deploy-time. One-line change in `analytics.ts`.

**Phase to address:** Phase 1 (UI) or deferred — cosmetic but cheap.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hand-edit Container App env vars in Azure portal to rotate the key fast | Avoids a 10-min pipeline wait | Terraform drift, secret overwrites on next apply, no audit trail | Never for this project — pipeline is the source of truth |
| Keep `aicv_intro_played` key unchanged to avoid re-triggering intro for users | Zero frontend change | Returning visitors never see disclaimer context, never hear new intro | Never — returning visitors are the highest-risk audience |
| Use only `AVATAR_INTRO` speech as the disclaimer (no UI text) | No layout work | Fails for muted/autoplay-blocked users; no legal defensibility | Never for an AI-avatar-likeness disclosure |
| Leave broad `except Exception` as-is because "it doesn't crash the app" | No code change | Root cause of tier-switch failures invisible, debugging takes hours | Never during a tier migration — this is when observability matters most |
| Deploy without rotating the old paid API key | One less step | Unknown billing exposure until credit card bill | Only if rotation is confirmed scheduled within 24 h of deploy |
| Skip local free-tier smoke test because "it's just a config change" | Saves 30 min | Any API-shape difference bricks prod; on-call debugging 10× worse | Never — always smoke-test tier boundaries locally first |
| Keep 120 s `SESSION_IDLE_TTL` during the switch | No config change | Every user pausing to read the new disclaimer triggers the retry path | Never during this milestone — bump to 600 s |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LiveAvatar sandbox `/sessions/token` | Assume same base URL / payload as paid tier | Verify sandbox endpoint + required fields in LiveAvatar docs; test locally before deploy |
| LiveAvatar sandbox concurrency | Ignore `MAX_SESSIONS` vs upstream quota mismatch | Set backend `MAX_SESSIONS` ≤ sandbox concurrent-session cap; reject at edge |
| LiveAvatar session.stopped events | Treat all stops as "user closed tab" | Distinguish `end_reason: duration_limit / quota_exceeded / user_disconnect`; show tailored UI |
| Azure Container Apps env var changes | Expect hot-reload | Force new revision via `DEPLOY_NONCE` env var bumped each deploy |
| Azure Container Apps secret-only changes | TF provider may not detect drift | Use `lifecycle` blocks carefully; verify `terraform plan` shows the change |
| GitHub Secrets rotation | Update while a pipeline run is in flight | Cancel in-flight runs, update secret, push no-op to trigger fresh run |
| Terraform + portal co-management | Edit env vars in portal "temporarily" | Never — always flow secrets through TF, or use `ignore_changes` with Key Vault |
| LiveAvatar trademark / brand in UI | Use logo / "powered by" / "official" | Plain-text name attribution only; check ToS before using logo |
| `crypto.randomUUID()` session ID outliving tier switch | Trust the old `aicv_session_id` in localStorage | Pair any tier-switch with a cache-busting key bump |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sandbox concurrent-session cap | 2nd-Nth visitor sees "Connection failed" | Set `MAX_SESSIONS` to sandbox cap; return 503 + Retry-After | Any LinkedIn share / Reddit post / HN mention |
| Sandbox per-session duration cap | Avatar freezes mid-conversation | Surface `session.stopped duration_limit` → "Reconnect" UI | Any conversation >~3-10 min (tier-specific) |
| Sandbox monthly minute quota exhaustion | Avatar works for days then stops working on 28th of month | Track total session-minutes in GA4 or Log Analytics; alert at 80% | Sustained traffic toward end of billing cycle |
| Free-tier credit leak via stranded sessions | LiveAvatar billing/quota higher than expected | Fix `resetSessionId` to call `closeSession(oldId)` first | Every retry burst (deploy, flaky network) |
| Session idle TTL = 120 s evicting readers | User reads disclaimer > 2 min → retry path → cold-start latency | Bump TTL to 600 s for this milestone | Any user who pauses to read new content |
| Cold-start delay compounding with sandbox slowness | First visitor after scale-to-0 waits 15+ s for avatar | Keep `minReplicas: 1` for the tier-switch deploy window; revert after | Scale-to-0 + sandbox tier latency |

---

## Security / Legal Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Old paid API key not rotated after switch | Old key in git history / logs / backup could authenticate paid sessions | Rotate at provider immediately after new revision is confirmed healthy |
| Disclaimer implies LiveAvatar endorsement | ToS violation; cease-and-desist risk; embarrassment | Use plain-text attribution only; no logo/marketing language; check ToS |
| Disclaimer insufficient for EU AI Act Art. 50 | Potential regulatory exposure for EU visitors; deepfake-disclosure obligations | Clear, above-the-fold statement that avatar face/voice are AI-generated |
| Disclaimer ambiguous about bio facts | User distrusts the whole site, not just the avatar | Scope explicitly: "bio and answers are real; avatar face/voice are stock/AI" |
| AI-washing / over-claiming | FTC "AI endorsement" guidance concerns | Accurate, specific language — don't say "cutting-edge AI" when you mean "stock avatar" |
| Logging `session_token` or `LIVEAVATAR_API_KEY` at INFO/WARNING | Secret exposure in Log Analytics | Grep logs before deploy; confirm `exc_info=True` in narrowed excepts doesn't serialise the request body |
| Hardcoding free-tier API key assumption into code | Can't easily rotate or switch back | Keep all tier-specific values in env; no literals in code |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Intro skipped for returning visitors → confused by new face | User thinks site is broken or deceptive | Bump `aicv_intro_played` → `aicv_intro_played_v2` to force one-time replay |
| Disclaimer buried in a tab / footer | User never sees it; ethical/legal exposure | Persistent visible badge near video; one-line statement above the fold |
| Error messages expose raw `HTTPStatusError` text | User sees "Retry failed: 403 Forbidden" — useless | Map backend errors to human messages: "Free avatar busy — try again soon" |
| Generic "Connecting…" spinner with no escape | User waits 30s, gives up | After 10 s, show "This is taking longer than usual on the free tier — [Try Again]" |
| Stock avatar suddenly speaks with "Meet Damir. He is…" | Uncanny valley; trust-eroding | Rewrite intro to frame the avatar explicitly as a stand-in/interface |
| No visual distinction between "real photo" and "stock avatar" | Users who mute audio and skip disclaimer still assume it's Damir | Add a small persistent label/badge visible over the video: "Stock avatar" |
| Mock-mode canvas "[ POC — Connect LiveAvatar API ]" watermark visible in prod | Looks like a broken dev site | Fail fast at startup if API key missing in production env |

---

## "Looks Done But Isn't" Checklist

- [ ] **Disclaimer:** Placed above the fold (not in a tab/footer) — verify on mobile viewport, not only desktop.
- [ ] **Disclaimer:** Visible to users who mute audio — text UI, not audio-only.
- [ ] **Disclaimer:** Scoped to AI-generated content (avatar face + voice + LLM answers), explicitly NOT disclaiming the bio facts or the author's identity.
- [ ] **Disclaimer:** No use of "powered by", "official", "certified", LiveAvatar logo, or marketing-style phrasing. Plain attribution only.
- [ ] **Intro cache-bust:** `INTRO_PLAYED_KEY` version bumped so returning visitors replay the new intro exactly once.
- [ ] **Intro text:** Rewritten to frame the avatar as a digital twin / stock face, not as the author himself. "anyhting" typo fixed.
- [ ] **Local smoke test:** Free-tier credentials verified end-to-end (token → start → WebKit → speak) BEFORE deploying.
- [ ] **Sandbox limits:** Actual concurrent-session cap, duration cap, monthly quota, rate limits documented in PROJECT.md.
- [ ] **Error handling:** 402/403/429 from LiveAvatar API surface as HTTP 503 with `Retry-After` and a human message, not generic "Session setup failed".
- [ ] **Old paid API key:** Rotated at LiveAvatar provider AFTER new revision is confirmed healthy.
- [ ] **Deploy nonce:** `DEPLOY_NONCE` or similar env var bumped so Container App forces a new revision on every deploy.
- [ ] **Health probe:** Post-deploy check hits `/session` (exercises LiveAvatar token call), not only `/health`.
- [ ] **Revision traffic:** If `revision_mode = Multiple`, verify 100% traffic is on the new revision.
- [ ] **Stranded-session fix:** `resetSessionId` in `VideoPlayer.tsx:128` calls `closeSession(oldId)` first.
- [ ] **Idle TTL:** `SESSION_IDLE_TTL` bumped from 120 s to ≥600 s for this milestone (see Pitfall 9).
- [ ] **Mock-mode guard:** Prod startup fails fast if `LIVEAVATAR_API_KEY` is empty (prevents silent POC watermark in prod).
- [ ] **Analytics:** `avatar_tier: "sandbox"` property added to GA4 events for before/after comparison.
- [ ] **Logs:** Secrets not leaked in any narrowed exception stack — grep `journalctl`/Log Analytics post-deploy.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Stale paid-tier session served after deploy | LOW | Bump `DEPLOY_NONCE`, redeploy to force cold replicas; rotate paid key at provider |
| Returning visitors miss disclaimer | LOW | Ship a follow-up deploy that bumps `INTRO_PLAYED_KEY` version; costs ~1 confused-user-day |
| Sandbox limits fire under load | MEDIUM | Temporarily lower `MAX_SESSIONS`; add 503 handling; consider gating avatar behind a click (already is via Connect button) |
| Endpoint / payload mismatch | MEDIUM | Revert env vars to paid tier, redeploy; research correct sandbox endpoint; retry |
| TF drift overwrites key | LOW | Re-run TF apply with correct var; update GitHub Secret; push no-op to trigger pipeline |
| Revision didn't pick up new secret | LOW | Force new revision: `az containerapp revision restart`, or bump `DEPLOY_NONCE` |
| GitHub secret rotation race | LOW | Cancel stale runs, re-update secret if needed, push no-op |
| Mock-mode in prod (watermark visible) | LOW | Emergency: set dummy non-empty key + 503 at `/session`; fix env; redeploy |
| Disclaimer legally/ethically insufficient | MEDIUM-HIGH | Emergency frontend hotfix (SWA deploys fast); consult before deploying more |
| Stranded free-tier sessions burning credits | LOW-MEDIUM | Deploy the `resetSessionId` fix; wait for existing stranded sessions to age out (2 min idle TTL) |
| Cross-revision session leakage (old replica still serving) | LOW | Force scale-in: `az containerapp update --min-replicas 0 --max-replicas 1` briefly |
| Mid-conversation disruption during deploy | LOW | Unavoidable without shared session state — keep deploys short and off-peak |

---

## Pitfall-to-Phase Mapping

Assuming a two-phase roadmap: **Phase 1 = local + code + UI prep**; **Phase 2 = production deploy + verify + rotate**.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 — Intro-played flag masks new avatar | Phase 1 | Test in an incognito window AND a window with the old `aicv_intro_played=1` key set — both should see the disclaimer; only the first should trigger the new intro speech |
| 2 — Stale cached LiveAvatar session crosses tier | Phase 2 | Post-deploy log check: no `Reusing cached LiveAvatar session` lines within 5 min of revision start; billing dashboard shows no paid-tier usage after key rotation |
| 3 — Sandbox rate / concurrency limits | Phase 1 (investigation), Phase 2 (handling) | Load-test with 3 concurrent sessions locally against sandbox; verify 503 + Retry-After on limit hit, not generic error |
| 4 — Endpoint / payload differences | Phase 1 | Local free-tier smoke test passes end-to-end before any Phase 2 work begins |
| 5 — Terraform drift from out-of-band secret edits | Phase 2 | `terraform plan` after deploy shows zero diff; documented runbook forbids portal edits |
| 6 — Container App revision doesn't pick up new secret | Phase 2 | `az containerapp revision list` shows the new revision with 100% traffic; `/session` returns 200 |
| 7 — Disclaimer wording (5 sub-variants) | Phase 1 | Peer-reviewed copy; checked against LiveAvatar ToS; legal language review; rendered and screenshotted on mobile + desktop |
| 8 — Mid-session failover during rolling deploy | Phase 2 | Deploy during low-traffic window; documented runbook |
| 9 — Compounding existing fragility | Phase 1 | `SESSION_IDLE_TTL` bumped; `resetSessionId` fix shipped; exception catches narrowed; `speak_ws` race event-based |
| 10 — GitHub secret rotation race | Phase 2 | Documented order: cancel in-flight runs → update secret → push no-op → verify |
| 11 — Mock-mode in prod | Phase 1 | Startup assertion: prod env + empty key = refuse to start |
| 12 — Intro text references specific avatar | Phase 1 | Copy rewritten, typo fixed, peer review |
| 13 — Filler cache keyed by phrase only | Phase 2 | Cold-restart verified on deploy (`DEPLOY_NONCE`) |
| 14 — Analytics doesn't distinguish tier | Phase 1 (optional) | GA4 event shows `avatar_tier: "sandbox"` property |

---

## Sources

- `c:\w\aicv\.planning\PROJECT.md` — milestone scope, existing env vars, key decisions
- `c:\w\aicv\.planning\codebase\CONCERNS.md` — pre-existing known bugs, fragile areas, scaling limits that this milestone compounds
- `c:\w\aicv\backend\avatar.py` — session state model, `_avatar_ws_loop`, `get_or_create_liveavatar_session`, `speak_on_avatar`
- `c:\w\aicv\backend\config.py` — `SESSION_IDLE_TTL`, `MAX_SESSIONS`, LiveAvatar env vars
- `c:\w\aicv\frontend\app\page.tsx` — `AVATAR_INTRO`, `INTRO_PLAYED_KEY`, intro-gating logic
- `c:\w\aicv\frontend\components\VideoPlayer.tsx` — connect flow, retry-on-failure branch, `resetSessionId` stranding
- `c:\w\aicv\frontend\lib\api.ts` (referenced via CONCERNS.md) — `sessionId` localStorage lifecycle, `closeSession`, `resetSessionId`
- Azure Container Apps revision model (official docs, general knowledge HIGH confidence) — revision_mode Single/Multiple, SIGTERM drain, env-var propagation
- EU AI Act Article 50 (MEDIUM confidence, general policy awareness) — transparency obligations for AI-generated content including deepfakes; scopes the disclaimer-prominence requirement
- FTC guidance on AI endorsements and disclosures (MEDIUM confidence) — prohibits deceptive AI-related claims; informs disclaimer wording norms
- LiveAvatar-specific sandbox limits and endpoints — **LOW confidence, NOT VERIFIED**; Phase 1 MUST include explicit doc review and local smoke test to establish ground truth

---

*Pitfalls research for: SaaS AI-avatar tier switch (paid → free/sandbox) in production*
*Researched: 2026-04-22*
