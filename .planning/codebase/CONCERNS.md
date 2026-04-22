# Codebase Concerns

**Analysis Date:** 2026-04-22

**Overall assessment:** The codebase is small (~3.7k LOC across backend + frontend), recently refactored, and generally clean. `.env` files exist locally but are properly gitignored and not committed. No hard-coded secrets were detected in source. The primary concerns are (1) complete absence of automated tests, (2) single-instance in-process session state that precludes horizontal scaling, (3) a handful of fragile async patterns around the avatar WebSocket, and (4) an aggressive session idle TTL reduced to 2 minutes in a recent commit that may evict active users.

---

## Tech Debt

**Duplicated retry logic in VideoPlayer:**
- Issue: The "stale session → reset → retry" branch in `VideoPlayer.connect()` is a near-complete copy-paste of the main connect flow — track subscription, event handlers, and room connection are all duplicated.
- Files: `frontend/components/VideoPlayer.tsx:123-166` (retry block) mirrors `frontend/components/VideoPlayer.tsx:60-122` (main block)
- Impact: Two sites must be kept in sync; bug fixes and event-handler additions can drift. `onConnected` is not called in the `mock-session-id` branch of the retry path (line 138) while it IS implicitly called via `RoomEvent.Connected` in the primary path — inconsistent behaviour.
- Fix approach: Extract an internal `attachRoomAndConnect(session)` helper that both paths invoke.

**Outdated `// TODO` in README:**
- Issue: README still instructs the reader to "Complete the SDP exchange in `frontend/components/VideoPlayer.tsx` (see the `// TODO: exchange SDP with LiveAvatar` comment)" but the component already uses `livekit-client`'s `Room.connect()` and no such TODO comment exists in the source.
- Files: `README.md:194-195`
- Impact: Misleading documentation; makes the project appear less complete than it is.
- Fix approach: Remove step 5 from the "LiveAvatar Integration" section.

**Typo in user-facing intro text:**
- Issue: `"Ask me anyhting about backends..."` — "anyhting" should be "anything"; also missing space/period before it.
- Files: `frontend/app/page.tsx:20` (`AVATAR_INTRO` constant — this is spoken by the avatar on first visit).
- Impact: First impression for every new visitor to the live site at `dimangulov.space`.
- Fix approach: Fix spelling and add proper punctuation.

**`assert` used for runtime invariant:**
- Issue: `assert start_data is not None` used to narrow types after the retry loop. Assertions are stripped when Python runs with `-O` / `PYTHONOPTIMIZE=1`, which would let `None` leak into the dict access on the next line.
- Files: `backend/avatar.py:312`
- Impact: Low risk in practice (Dockerfile does not set `-O`), but defensive-programming anti-pattern. If `MAX_START_ATTEMPTS` is ever raised without care, the loop could exit with `start_data` still `None`.
- Fix approach: Replace with explicit `if start_data is None: raise HTTPException(502, ...)`.

**Deprecated `version` field in docker-compose.yml:**
- Issue: `version: "3.9"` is obsolete in modern Docker Compose (v2+); the Compose spec no longer requires or uses it and emits a warning on every `docker compose up`.
- Files: `docker-compose.yml:1`
- Impact: Warning noise only; no functional issue.
- Fix approach: Delete the `version: "3.9"` line.

**Nested async IIFE inside `setMessages` callback:**
- Issue: `handleQuestion` appends the user message inside a `setMessages` updater, then immediately reads `messagesRef.current` — but that ref is updated by a separate `useEffect` that only fires after render commits, so the history snapshot excludes the just-appended user message (and possibly the assistant message from the very previous turn on fast consecutive submits).
- Files: `frontend/components/ChatInterface.tsx:89-101`
- Impact: Subtle history-off-by-one on the first turn; probably benign because RAG pipeline tolerates missing context, but confusing pattern.
- Fix approach: Compute the snapshot array explicitly before calling `setMessages`, pass it into the IIFE by value.

**Broad exception catches swallow failures silently:**
- Issue: Several `except Exception` blocks in `avatar.py` log a warning and continue, obscuring root cause on intermittent LiveAvatar or WebSocket failures. Specifically `speak_on_avatar` line 474 catches WS errors and invalidates the session — but the message is one of dozens of possible causes and no retry happens.
- Files: `backend/avatar.py:241, 377, 395, 405, 474`; `backend/main.py:77, 261, 336`
- Impact: Degraded avatar speech without a user-visible error; hard to diagnose from logs alone.
- Fix approach: Narrow exception types (`websockets.exceptions.ConnectionClosed`, `httpx.HTTPError`, etc.); preserve full `exc_info=True` on error-level logs.

**No linter/formatter configuration committed:**
- Issue: No `.ruff.toml`, `.flake8`, `pyproject.toml` (Python config), or `.eslintrc.*` / `eslint.config.*` in the repo; only `next lint` script in `package.json`. Code style consistency relies on editor defaults.
- Files: repo root; `backend/`; `frontend/`
- Impact: Style drift as the codebase grows; no CI enforcement.
- Fix approach: Add `pyproject.toml` with ruff config for backend; add `eslint.config.mjs` with Next.js + React rules for frontend.

---

## Known Bugs

**Session eviction can kill an active chat:**
- Symptoms: After reducing `SESSION_IDLE_TTL` to 120 s in commit `5a73374`, a user who reads a long answer (or switches tabs for 2+ minutes while the avatar is idle) will have their LiveAvatar session stopped and then fail to speak on the next question.
- Files: `backend/config.py:82` (`SESSION_IDLE_TTL: float = 120.0`); eviction in `backend/avatar.py:150-169`
- Trigger: Any user pause > 2 min between questions.
- Workaround: Frontend catches the failure in `VideoPlayer` and retries with a fresh session (`frontend/components/VideoPlayer.tsx:123-166`), but the retry restarts the avatar video and plays the intro again on browsers that haven't set `aicv_intro_played`.
- Fix approach: Either (a) bump idle TTL back to ~10 min for human-interactive sessions, (b) treat POST /ask, /ask/stream, /speak, /interrupt as activity (`last_active` is only updated in `get_or_create_user_session` which is called from `/session` and `speak_on_avatar`, not on every `/ask`).

**`speak_ws` None-check race on first question:**
- Symptoms: Very first `/ask/stream` after `/session` can hit a 3-second wait loop because `_avatar_ws_loop` is still connecting when the first sentence completes.
- Files: `backend/avatar.py:410-422`
- Trigger: Cold-started Container App + user who types immediately after the avatar connects.
- Workaround: The 0.5 s × 6 poll mitigates most cases.
- Fix approach: Replace the poll with an `asyncio.Event` set inside `_avatar_ws_loop` once `entry.speak_ws = ws`; await it with a timeout.

**Streaming token sentence detection misses abbreviations:**
- Symptoms: `_SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')` (main.py:58) fires on periods after abbreviations like "10+ yrs." or "Inc." causing premature TTS synthesis of a partial sentence.
- Files: `backend/main.py:58, 198`
- Trigger: LLM output containing `"e.g."`, `"i.e."`, `"Inc."`, `"v1."`.
- Workaround: None; the avatar speaks an oddly-cut first chunk.
- Fix approach: Use a simple lookahead that requires a capital letter after the boundary, or accumulate until min-length threshold.

**`resetSessionId` on retry can strand server-side session:**
- Symptoms: When the frontend retries with `resetSessionId()` at `frontend/components/VideoPlayer.tsx:128`, the old `sessionId` is overwritten in `localStorage` without calling `DELETE /session`. The old backend `UserSession` lingers until idle eviction (2 min) and may still be holding a real LiveAvatar session that consumes sandbox credits.
- Files: `frontend/lib/api.ts:28-34`; `frontend/components/VideoPlayer.tsx:128`
- Trigger: Any retry path.
- Fix approach: Call `closeSession()` with the OLD sessionId before calling `resetSessionId()`.

---

## Security Considerations

**`.env` exists locally but not committed — verified:**
- Risk: Secret exposure if `.gitignore` coverage breaks.
- Files: `backend/.env` (exists, 3688 bytes — NOT committed); `frontend/.env` (exists, 356 bytes — NOT committed); `.gitignore` correctly excludes `.env`, `.env.local`, `.env.*.local`, `backend/.env`.
- Current mitigation: Broad `.gitignore` rules; `git ls-files` confirms no `.env` file is tracked.
- Recommendations: Add a repo-root `.gitattributes` or pre-commit hook that blocks staging of `.env*` by accident. Consider `trufflehog` or `gitleaks` in CI.

**CORS `allow_origins` accepts comma-split env var without validation:**
- Risk: Operator typo in `ALLOWED_ORIGINS` (e.g. `https://foo.com,https://*.evil.com`) would be accepted verbatim — FastAPI does not validate origin format.
- Files: `backend/config.py:75-79`; `backend/main.py:112-118`
- Current mitigation: Default is `http://localhost:3000`; production value is set via Terraform.
- Recommendations: Add URL-format validation at startup; log the resolved list at INFO level.

**No Content-Security-Policy header:**
- Risk: Design doc §8.3 mentions CSP as "Future" but `frontend/next.config.ts:22-42` only sets `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`. `DiagramViewer` and `Mermaid` both use `dangerouslySetInnerHTML` with `eslint-disable` markers.
- Files: `frontend/next.config.ts:22-42`; `frontend/components/DiagramViewer.tsx:203`; `frontend/components/Mermaid.tsx:105`
- Current mitigation: SVGs served are statically exported from a controlled Structurizr DSL; no user input ever reaches the innerHTML.
- Recommendations: Add a strict CSP header in `next.config.ts` as documented in DESIGN.md §8.3 (`script-src 'self' www.googletagmanager.com`, `connect-src` for API + LiveKit + Azure Speech, `img-src 'self' data:`).

**GA measurement ID inlined in HTML:**
- Risk: `NEXT_PUBLIC_GA_MEASUREMENT_ID` is inlined into `gtag('config', '${GA_ID}')` in `frontend/app/layout.tsx:43`. This is fine for GA (IDs are public) but should be documented to avoid confusion with secret env vars.
- Files: `frontend/app/layout.tsx:6, 33-45`
- Current mitigation: Prefixed `NEXT_PUBLIC_` — correctly treated as public build-time constant.
- Recommendations: Note in README that this value is public and safe to commit for reference if desired.

**Rate limit key is remote IP:**
- Risk: `Limiter(key_func=get_remote_address, default_limits=["20/minute"])` will collapse all users behind a single NAT / corporate proxy into one bucket; attacker bypass via proxy rotation.
- Files: `backend/main.py:107-110`
- Current mitigation: 20 req/min is generous for genuine single-user interactions.
- Recommendations: Include `X-Session-ID` in the limiter key for per-session buckets; trust `X-Forwarded-For` only when behind Azure Front Door / SWA.

**No authentication on any endpoint:**
- Risk: `/ask`, `/ask/stream`, `/session`, `/speak`, `/interrupt`, `/session DELETE` are fully public. Anyone who knows the production API URL can burn through Azure OpenAI tokens and LiveAvatar session credits up to the rate limit.
- Files: `backend/main.py:125-315`
- Current mitigation: Rate limiter + LiveAvatar sandbox flag + low per-token cost of `gpt-4o-mini`.
- Recommendations: Acceptable for a portfolio/demo; document the risk. For production, add an origin check (verify `Origin` header matches `ALLOWED_ORIGINS`) or a lightweight client challenge (hCaptcha / Cloudflare Turnstile).

**`miniaudio` build flag hides C warnings:**
- Risk: `CFLAGS="-Wno-implicit-function-declaration"` in `backend/Dockerfile:13-14` silences a real GCC 14 diagnostic about missing function prototypes in the `miniaudio` C extension; this is a pinned workaround for `miniaudio==1.2`.
- Files: `backend/Dockerfile:11-14`; `backend/requirements.txt:25`
- Current mitigation: Dependency is pinned to a tested version.
- Recommendations: Track `miniaudio` upstream for a release that compiles cleanly on gcc 14; remove the flag when available.

---

## Performance Bottlenecks

**`bio.txt` re-embedded on every cold start:**
- Problem: `build_rag_chain()` re-reads `bio.txt`, re-chunks it, and calls `embeddings.embed_documents(...)` on every container start because `QDRANT_MODE=memory` (default) has no persistence. On Azure Container Apps with `minReplicas: 0`, every cold start pays the embedding latency.
- Files: `backend/rag.py:191-272`
- Cause: In-memory Qdrant is the configured default; Azure production uses `QDRANT_MODE=cloud` but that path also re-runs `QdrantVectorStore.from_documents()` which recreates the collection and embeds every chunk again.
- Improvement path: (1) With cloud Qdrant, check if the collection exists and has current doc count; skip embedding if it matches a content hash. (2) Add a `bio.txt.sha256` check and store it as collection metadata.

**gTTS fallback runs synchronously in executor:**
- Problem: `_synthesize_pcm_gtts` calls `gTTS(...).write_to_fp(buf)` via `run_in_executor(None, ...)` — uses the default thread-pool executor, contends with other blocking calls (httpx timeouts, miniaudio decode).
- Files: `backend/tts.py:93-107`
- Cause: Single shared default executor (typically 32 threads on Python 3.12).
- Improvement path: Create a dedicated `ThreadPoolExecutor(max_workers=4)` for TTS at app startup; bound concurrency.

**`len(_user_sessions) >= MAX_SESSIONS` O(n) lock held:**
- Problem: Admission control while holding the global `_user_sessions_lock` serialises every new session request. With 50 concurrent first-time visitors, requests queue behind each other.
- Files: `backend/avatar.py:129-141`
- Cause: In-process dict + single asyncio lock.
- Improvement path: Acceptable at current scale. For higher concurrency, move to Redis for shared state + a sliding-window semaphore.

**Mermaid + highlight.js ship in the main bundle:**
- Problem: `mermaid@^11.13.0` (~1.2 MB minified) and `highlight.js@^11.11.1` are imported for the Architecture and Design tabs but are loaded regardless of which tab the user selects.
- Files: `frontend/package.json:17-24`; `frontend/components/Mermaid.tsx`; `frontend/components/DesignSection.tsx`
- Cause: Static imports.
- Improvement path: Use `next/dynamic` to lazy-load `Mermaid` and syntax highlighting only when their tab activates.

---

## Fragile Areas

**Avatar WebSocket lifecycle is spread across four places:**
- Files: `backend/avatar.py:208-245` (`_avatar_ws_loop` sets `entry.speak_ws`), `backend/avatar.py:329-334` (task creation), `backend/avatar.py:410-422` (speak_on_avatar wait-poll), `backend/main.py:252-263` (interrupt send).
- Why fragile: State transitions (connect / disconnect / session.stopped / keep-alive timeout) interleave with concurrent `speak_on_avatar` calls guarded by `entry.speak_lock`. A disconnect that sets `entry.speak_ws = None` in the `finally` block can race with a speak call that has already captured the old reference.
- Safe modification: Always acquire `entry.speak_lock` before touching `entry.speak_ws`; add a state enum (`CONNECTING | OPEN | CLOSED`) to the `UserSession` dataclass.
- Test coverage: **Zero** — no tests exercise this path at all.

**`filler_cache` is a process-global dict:**
- Files: `backend/avatar.py:61`
- Why fragile: Populated once at startup by `warm_fillers()`, never invalidated. If `LIVEAVATAR_VOICE` is changed at runtime (via env), the cache continues serving old voice. Fine for single-tenant deployments.
- Safe modification: Key the cache by `(voice, phrase)`.

**Sentence boundary detection in streaming path:**
- Files: `backend/main.py:58, 198-207`
- Why fragile: See "Streaming token sentence detection misses abbreviations" above; also a buffered remainder is flushed at stream end, but if the LLM ends without a terminal punctuation the remainder is spoken as one giant sentence which hurts TTS prosody.

**`crypto.randomUUID()` called in module-scope on client:**
- Files: `frontend/lib/api.ts:22-23, 29`
- Why fragile: `initSessionId()` is safe (guarded by `typeof window !== "undefined"`), but the module top-level `export let sessionId = ""` means any import before `initSessionId` runs will see an empty string. `api.ts` functions that read `sessionId` would then send `X-Session-ID: ""` and fall through to the `"anonymous"` default in `backend/main.py:139` — breaking per-session isolation silently.
- Safe modification: Replace `export let sessionId` with a `getSessionId()` function that lazily initialises.

---

## Scaling Limits

**Single-instance in-process state:**
- Resource: `_user_sessions: dict[str, UserSession]` in `backend/avatar.py:124` + `filler_cache: dict[str, bytes]` in `backend/avatar.py:61`.
- Current capacity: `MAX_SESSIONS=50` (env-configurable, default 50).
- Limit: Any Container Apps scale-out beyond 1 replica breaks: each replica has its own session dict, and the per-session WebSocket to LiveAvatar lives in one replica's memory. Subsequent `/ask/stream` requests routed to a different replica will not find the session and will silently skip avatar speech.
- Scaling path: Move session state to Redis (listed in DESIGN.md §9.6 Phase 3 roadmap). This also enables the LLM response caching mentioned there.

**Single `uvicorn` worker:**
- Resource: Dockerfile `CMD ["uvicorn", ..., "--workers", "1"]`
- Current capacity: All async; can handle hundreds of concurrent streams on one replica.
- Limit: CPU-bound work (embedding at startup, miniaudio decode) blocks the single event loop.
- Scaling path: Acceptable; horizontal scale-out via Container Apps is the intended model, but this needs shared session state first.

**LiveAvatar account-level limits:**
- Resource: LiveAvatar concurrent-session quota.
- Current capacity: Unknown (commercial SaaS).
- Limit: Each unique `X-Session-ID` can create its own LiveAvatar session; `MAX_SESSIONS=50` sets the backend cap but does not coordinate with the LiveAvatar account quota.
- Scaling path: Expose the LiveAvatar quota as `MAX_LIVEAVATAR_SESSIONS` env var; return HTTP 503 with `Retry-After` instead of the generic message when exceeded.

---

## Dependencies at Risk

**LangChain version pin stack is coherent but aging:**
- Package: `langchain==0.3.13`, `langchain-core==0.3.63`, `langchain-community==0.3.13`, `langchain-ollama==0.2.3`, `langchain-openai==0.3.7`.
- Risk: LangChain 0.3.x line receives frequent patch releases; the pinned minors are from late 2024 / early 2025. Security advisories or LCEL behaviour changes may have landed since.
- Impact: Dependabot alerts; possible CVE exposure.
- Migration plan: Review LangChain changelog, update to latest 0.3.x, run smoke test of `/ask/stream` end-to-end.

**`websockets==13.1`:**
- Package: `websockets==13.1` (Oct 2024).
- Risk: The project targets the `websockets.connect()` high-level API; v14 made small breaking changes (`websockets.asyncio.client` is the new import path). Upgrading requires a code change.
- Impact: Blocks Python 3.13 adoption when that becomes the default `python:3.12-slim` base.
- Migration plan: Pin to `websockets~=13.1` for now; schedule a focused PR to migrate to v14 API when the ecosystem stabilises.

**`miniaudio==1.2`:**
- Package: `miniaudio==1.2`.
- Risk: Requires `CFLAGS=-Wno-implicit-function-declaration` to compile on gcc 14 (Dockerfile:13). Upstream may or may not publish wheels for newer Python versions.
- Impact: Build breakage if the Dockerfile base image moves to a gcc that tightens this further.
- Migration plan: Track miniaudio releases; consider switching to `pydub + ffmpeg` (DESIGN.md already references pydub as an alternative).

**Next.js 16 pre-release:**
- Package: `next ^16.1.6`.
- Risk: Next.js 16 is the latest major; caret range will auto-bump on `pnpm install`. Major-version auto-bumps via caret are generally unsafe.
- Impact: Unexpected breaking changes on CI rebuild.
- Migration plan: Pin to `~16.1.6` (minor-only) or exact version.

---

## Missing Critical Features

**No tests of any kind:**
- Problem: No `tests/`, no `__tests__/`, no `*.test.*`, no `*.spec.*` files anywhere in `backend/` or `frontend/`. No test framework in `requirements.txt` (no pytest) or `frontend/package.json` (no vitest/jest).
- Blocks: Safe refactors of the WebSocket/session logic; PR reviewers have no automated signal; regression risk on every change.
- Priority: **High.**

**No CI status / coverage enforcement:**
- Problem: `.github/workflows/deploy-azure.yml` is mentioned in DESIGN.md §9.5 but no test-running workflow exists (nothing in requirements for pytest or coverage).
- Blocks: "Green build" guarantees.
- Priority: High, follows directly from test gap.

**No structured logging / tracing:**
- Problem: `logging.basicConfig(level=logging.INFO, format="...")` in `backend/config.py:20-23` produces plain-text logs. DESIGN.md §9.6 lists "OpenTelemetry → Application Insights" as Phase 3 future work.
- Blocks: Root-cause analysis in production; correlation of a single user's request across `/session`, `/ask/stream`, `/speak`, `/interrupt`.
- Priority: Medium.

**No health check for LiveAvatar or Azure Speech:**
- Problem: `/health` endpoint (`backend/main.py:328-356`) only probes Ollama + Qdrant + RAG chain. LiveAvatar API reachability and Azure Speech endpoint are not checked.
- Blocks: Blind spot on the two most important external dependencies.
- Priority: Medium.

**No persistence for conversation history:**
- Problem: `AskRequest.history` is client-supplied (`frontend/components/ChatInterface.tsx:69-72` truncates to last 6 messages from `messagesRef.current`). If the user refreshes, history is lost.
- Blocks: Multi-turn coherence across reloads.
- Priority: Low — design trade-off; note explicitly in README if the behaviour is intentional.

---

## Test Coverage Gaps

**All backend modules — 0% coverage:**
- What's not tested: Every function in `backend/main.py`, `backend/rag.py`, `backend/tts.py`, `backend/avatar.py`, `backend/config.py`, `backend/models.py`.
- Files: `backend/*.py` (6 modules, ~1200 LOC).
- Risk: WebSocket reconnect logic, session eviction races, sentence boundary parsing, TTS fallback chain, CORS origin parsing, rate-limit handling — all untested.
- Priority: **High.** Start with `pytest` + `httpx.AsyncClient(app=app)` unit tests for `/ask`, `/health`, `/ping`; mock the RAG chain for speed.

**All frontend modules — 0% coverage:**
- What's not tested: Every `.tsx` component, every hook, `lib/api.ts`, `lib/analytics.ts`.
- Files: `frontend/app/*.tsx`, `frontend/components/*.tsx`, `frontend/hooks/*.ts`, `frontend/lib/*.ts`.
- Risk: The speech-recognition hook has tricky ref-juggling (`frontend/hooks/useSpeechRecognition.ts:96-104`); SSE parsing in `askQuestionStream` (`frontend/lib/api.ts:89-110`) is untested against malformed server output.
- Priority: High. Start with `vitest` + React Testing Library for `ChatInterface` happy path and `useSpeechRecognition` state transitions.

**Integration / e2e tests:**
- What's not tested: End-to-end flow Browser → `/ask/stream` → RAG → Qdrant → LLM → TTS → avatar WebSocket.
- Files: N/A — no test harness exists.
- Risk: Any change to one layer can silently break the pipeline.
- Priority: Medium. Playwright + a stubbed LiveAvatar sandbox would cover the critical path.

**Terraform plan-check in CI:**
- What's not tested: `terraform validate` and `terraform plan` on PR.
- Files: `infra/terraform/*.tf`.
- Risk: Infrastructure drift or variable typos reach production via `deploy-azure.yml` without review.
- Priority: Low-Medium. Add a `terraform-lint` job to CI that runs `fmt -check` + `validate` + `tfsec`.

---

*Concerns audit: 2026-04-22*
