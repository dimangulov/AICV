# Feature Landscape — LiveAvatar Free/Sandbox Tier Switch + UI Disclaimer

**Domain:** Public portfolio site using SaaS AI avatar (LiveAvatar/HeyGen), switching paid custom-avatar plan to free/sandbox tier
**Researched:** 2026-04-22
**Overall confidence:** MEDIUM (LiveAvatar sandbox limits partially documented; disclaimer patterns well-established)

---

## 1. LiveAvatar Free/Sandbox Tier — What It Exposes

### Summary of capabilities (HIGH confidence where cited, MEDIUM otherwise)

| Capability | Value | Source / Confidence |
|------------|-------|---------------------|
| **Sandbox flag** | `is_sandbox=true` when creating the LiveAvatar session token — orthogonal to session mode | HIGH — LiveAvatar official docs, matches existing env var `LIVEAVATAR_IS_SANDBOX` in `backend/config.py` |
| **Credit consumption in sandbox** | **Zero credits consumed** — sandbox sessions do not bill | HIGH — official sandbox docs ("does not consume any credits") |
| **Session duration cap** | **~1–2 minutes** per session, then auto-terminates | MEDIUM — one source says "around 1 minute", another says "2 minute max session limit"; treat **2 min as upper bound** |
| **Concurrency** | **1 concurrent session** | MEDIUM — single source; assume 1 until verified |
| **Available avatars** | Only a **select subset of production public avatars** — custom/paid avatars NOT available | HIGH — official docs state "select subset of production avatars" |
| **Session modes** | FULL, LITE, and CUSTOM all work with `is_sandbox=true` | HIGH — `is_sandbox` is an orthogonal flag, not a mode |
| **TTS voices** | ElevenLabs Flash v2.5 (LiveAvatar's built-in TTS for FULL mode); LITE mode uses caller-supplied audio, so Azure Speech TTS (already used in this codebase) remains unaffected | HIGH — this repo uses LITE/CUSTOM with its own TTS per `backend/avatar.py`, bypassing LiveAvatar TTS |
| **Free account signup** | Free account exists, provides "free credits with zero commitment" for initial exploration; sandbox remains free indefinitely | MEDIUM — FAQ language ambiguous; sandbox is explicitly credit-free |
| **Custom avatar creation** | Requires paid Essential plan — **not available on free tier** | HIGH — per HeyGen FAQ |

### Session mode recap (relevant to this codebase)

| Mode | What LiveAvatar does | What your app does | Current project uses? |
|------|---------------------|-------------------|----------------------|
| **FULL** | ASR + LLM + TTS + avatar all in LiveAvatar's WebRTC room | App sends user turns; LiveAvatar responds end-to-end | No (we want our own RAG) |
| **LITE** | Avatar WebRTC stream driven by audio you push in | App handles ASR/LLM/TTS; pushes audio buffers | **Likely** — matches existing Azure Speech TTS pipeline |
| **CUSTOM** | WebSocket for sending arbitrary avatar events | App drives everything via custom events | Possibly — per `LIVEAVATAR_SESSION_MODE` env |

> **Code compatibility check**: `backend/avatar.py` + `backend/config.py` already support `LIVEAVATAR_IS_SANDBOX` and a configurable `LIVEAVATAR_SESSION_MODE` (LITE/FULL/CUSTOM). Switching tiers should be **config-only** — no source changes expected unless the free tier rejects the current session mode for a specific public avatar ID.

### Known free-tier pitfalls for this project

- **2-minute auto-termination** vs the current UX (persistent WebSocket, long Q&A sessions): every ~2 min the avatar disconnects. `VideoPlayer.tsx` already handles `RoomEvent.Disconnected` and has retry logic — we need to verify it reconnects gracefully and the user-visible "Live" badge reflects state.
- **Intro speech length**: `AVATAR_INTRO` in `app/page.tsx` is ~2 sentences (~10–15 s at neural-voice rate) — fits in a 2-min window, no change needed.
- **Concurrency = 1**: if two browsers hit the site at once they'll contend for the single sandbox session slot. This is **acceptable for a personal portfolio** but should be logged/monitored.
- **Generic stock avatar**: the visual identity shifts from "photorealistic Damir" to a generic person. This is exactly what the disclaimer must address.

---

## 2. Disclaimer — Best Practices for "This is not the real person" + "Free tier"

### Legal/regulatory context (HIGH confidence)

| Regime | Requirement | Applies to this site? |
|--------|-------------|----------------------|
| **EU AI Act, Article 50(4)** — deepfake transparency | Deployer must disclose that video content is AI-generated; creative/artistic works exemption allows "disclosure of the existence of such content in an appropriate manner" | **Yes** (EU-accessible site, author in Sofia/BG). Portfolio likely qualifies for the creative-works softer standard, but disclosure is still mandatory. Enforcement: **Aug 2026** |
| **EU AI Act, Article 50(2)** — machine-readable marking | Providers mark outputs; this is the **provider's** (HeyGen/LiveAvatar's) obligation, not ours | Not our direct obligation; passthrough |
| **GDPR** | Transparency in automated processing; applies because chat logs may contain personal data | Already addressed by existing session model; disclaimer reinforces transparency |
| **FTC (US) endorsement rules** | AI "endorsements" need clear-and-conspicuous disclosure | Low relevance — site is informational, not endorsing products |
| **Maine / NY / CA chatbot & likeness laws** | Some states require chatbot disclosure and/or likeness consent | If avatar no longer resembles the author, likeness-consent risk drops to zero — **actually safer than the paid tier** |

**Key takeaway:** the disclaimer must make two facts "clear and distinguishable" at the **first exposure**:
1. The video/voice is AI-generated.
2. The avatar's visual identity is **not** the author's likeness.

A third fact ("free tier of LiveAvatar") is requested by the PROJECT.md stakeholder but is **not legally required** — it's transparency/trust signalling.

### Placement options — comparison

| Pattern | Where | Pros | Cons | Fit for this site |
|---------|-------|------|------|-------------------|
| **A. Inline badge on video** (caption overlay) | Bottom-left/right of `VideoPlayer.tsx`, always visible over the stream | Collocated with the content being disclosed → maximum "clear and distinguishable"; hard to miss; AI UX best practice | Small text, may look cluttered next to existing "Live" badge | **Recommended primary** — satisfies Art. 50(4) first-exposure test |
| **B. One-line banner above/below video** | Top of left column or just under video frame in `page.tsx` | Readable, explicit, doesn't overlap video | Uses vertical space; could be dismissed visually | **Recommended secondary** — pair with A |
| **C. Info "i" icon → tooltip/popover** | Small icon near the avatar, expands on hover/tap | Unobtrusive; full text available | Hidden by default → may fail "clear and distinguishable" test; bad on mobile | Good *supplement* but NOT sufficient alone |
| **D. Footer note** | Page footer | Standard pattern; "site-wide policy" best practice | Far from the content being disclosed; easily missed | Good **tertiary** (site-wide policy) but NOT sufficient alone |
| **E. First-visit modal / intro splash** | One-time overlay on first visit | Forces acknowledgement; strong legal posture | Friction; annoying on a portfolio; re-visits miss it | Overkill for personal portfolio |
| **F. In-chat system message** | First bot message in `ChatInterface` | Natural conversational context | Easy to scroll past; only appears after interaction | Weak supplement |

**Recommended composition**: **A + B + D** (badge on video + banner strip + footer note). Satisfies the EU AI Act "clear and distinguishable at first exposure" requirement, matches the Usercentrics dual-pattern recommendation (in-content + site-wide), and aligns with shapeof.ai's "disclosure badge directly on the avatar" pattern.

### Draft copy — three variants

**Variant 1 — Friendly / conversational** (recommended for portfolio tone)

> Badge (on video, compact):
> `AI avatar · not Damir's likeness`
>
> Banner (one line):
> `The face and voice above are AI-generated using LiveAvatar's free tier — this is a stock avatar, not a recording of Damir. The answers come from Damir's CV via a RAG pipeline.`
>
> Footer:
> `Avatar video is AI-synthesised (LiveAvatar sandbox). It does not visually represent the author. Voice is AI TTS. Answers are retrieved from a curated CV knowledge base.`

**Variant 2 — Concise / legal-leaning**

> Badge:
> `AI-generated · not a real person`
>
> Banner:
> `Disclosure: the avatar shown is AI-generated and does not depict Damir Imangulov. Powered by LiveAvatar (free tier). Transcript and replies are produced by an LLM over a CV knowledge base.`
>
> Footer:
> `All video, audio, and text output on this page is AI-generated. Likeness: generic stock avatar, not the author. Provider: LiveAvatar.com (sandbox mode).`

**Variant 3 — Technical / developer-audience** (fits the existing site's dev-focused vibe, DevConsole, C4 diagrams)

> Badge:
> `AI avatar (sandbox)`
>
> Banner:
> `Heads up — this is a generic LiveAvatar sandbox avatar, not the author's likeness. Running on the free tier, so sessions cap at ~2 min and may reconnect. Full stack in the Architecture tab.`
>
> Footer:
> `Avatar: LiveAvatar free/sandbox tier (generic public avatar). TTS: Azure Speech Neural. LLM: Azure OpenAI / Ollama via RAG over bio.txt.`

**Recommendation: Variant 1 or Variant 3.** Variant 1 reads well for recruiters; Variant 3 matches the existing tone (see the "POC watermark" text in `VideoPlayer.tsx` mock stream and the DevConsole aesthetic). Variant 2 is needlessly stiff for a personal site.

---

## 3. Table Stakes (Must-have — else we can't ship)

Features that **must** be present to meet the milestone acceptance criteria in PROJECT.md.

| # | Feature | Why required | Complexity | Notes |
|---|---------|--------------|------------|-------|
| TS-1 | Swap backend config to free/sandbox tier (`LIVEAVATAR_IS_SANDBOX=true`, valid sandbox-eligible `LIVEAVATAR_AVATAR_ID`, session-mode that works in sandbox) | PROJECT.md §"What must be delivered" #1 | Low | Config-only; already supported by `backend/config.py` + `backend/avatar.py` |
| TS-2 | Verify free-tier API key works against chosen `LIVEAVATAR_SESSION_MODE` (likely LITE) | Free tier may reject unsupported mode+avatar combos | Low-Med | Test locally before Terraform push |
| TS-3 | Visible, "clear and distinguishable" disclaimer that the avatar is **not** the author's likeness | EU AI Act Art. 50(4) + PROJECT.md | Low | Variant-1 badge + banner in `page.tsx` / `VideoPlayer.tsx` |
| TS-4 | Visible note that the site uses LiveAvatar **free** tier | PROJECT.md explicit requirement (trust signalling) | Low | Fold into same banner/footer copy |
| TS-5 | Graceful reconnect after sandbox 2-min auto-termination | UX would be broken otherwise — user mid-question when avatar vanishes | Low | `VideoPlayer.tsx` already has `RoomEvent.Disconnected` + retry; verify it auto-reconnects rather than requiring a click |
| TS-6 | Production deploy via existing GitHub Actions pipeline | PROJECT.md acceptance criterion | Low | No pipeline changes; just env var update in Terraform + secret rotation |
| TS-7 | Do **not** keep `AVATAR_INTRO` wording that implies the avatar IS Damir | Intro currently says "Meet Damir Imangulov. He is..." spoken BY the avatar — this creates the exact misrepresentation the disclaimer denies | Low | Reword intro to third-person framing e.g. "Welcome. I'm an AI assistant trained on Damir Imangulov's CV..." |

---

## 4. Optional / Differentiators (Nice-to-have, not blocking)

| # | Feature | Value | Complexity | Notes |
|---|---------|-------|------------|-------|
| OPT-1 | Auto-reconnect countdown UI ("Avatar will reconnect in 3s — free-tier limit") | Turns a limitation into a transparent UX moment | Low-Med | Extend `VideoPlayer.tsx` status states |
| OPT-2 | First-visit dismissible tooltip pointing at the disclaimer badge | Ensures first-time visitors notice the badge | Low | `localStorage` gate like existing `aicv_intro_played` |
| OPT-3 | Dedicated `/ai-disclosure` page linked from footer | Mirrors Usercentrics "site-wide policy" best practice; signals maturity | Low | Plain MDX page |
| OPT-4 | Session-remaining indicator (e.g. "1:45 / 2:00") | Visible accounting for the sandbox window | Med | Requires timer in `VideoPlayer.tsx` |
| OPT-5 | Fallback to mock canvas stream when sandbox quota/concurrency is exhausted | Keeps site functional on launch-day traffic spikes | Low | Code already has `startMockStream` — wire it in as graceful fallback |
| OPT-6 | Log disclosure event to GA4 (`disclaimer_viewed`) | Measure whether badge is seen | Low | `trackEvent` util exists |
| OPT-7 | Alt-text / ARIA label on video describing "AI-generated avatar" | Accessibility + screen-reader disclosure | Low | Satisfies Art. 50(5) accessibility clause |

---

## 5. Anti-Features (DO NOT build)

Things that would violate the milestone intent, legal posture, or trust.

| # | Anti-feature | Why avoid | What to do instead |
|---|--------------|-----------|--------------------|
| AF-1 | Script the sandbox avatar to say "I am Damir Imangulov" in first-person | Creates a deepfake-style impersonation — precisely what Art. 50(4) flags; misleading even if the avatar doesn't look like him | Use third-person "AI assistant for Damir's CV" framing; intro speech describes Damir, does not claim to be him |
| AF-2 | Style the generic avatar with name-card overlay "Damir Imangulov" over the video | Visually re-attaches identity the disclaimer is trying to detach | Keep the name in the right column (text bio) only, not overlaid on the video |
| AF-3 | Hide or downplay the disclaimer (tiny grey text, below-fold, collapsed by default) | Fails "clear and distinguishable" under Art. 50(5); bad-faith optics | Badge on video + banner visible above fold |
| AF-4 | Use non-sandbox paid avatar endpoint with a free-tier key as a "stealth" workaround | Breaks ToS and violates the milestone's sustainability rationale | Commit to sandbox; own the limitation in UX |
| AF-5 | Use a photorealistic female/male avatar closely resembling the author by accident | Reintroduces likeness confusion; defeats the tier-switch rationale | Pick a clearly distinct stock avatar — different gender/ethnicity/style is fine and reinforces "this is obviously not him" |
| AF-6 | Add a "Try the real Damir avatar — upgrade!" CTA | Mixes personal portfolio with commercial upsell; confuses visitors | Keep portfolio focus; if paid avatar returns later, it's a product decision not a UX hook |
| AF-7 | Silently retry on sandbox termination without telling the user | Surprising disconnect mid-sentence erodes trust | Log it to DevConsole (already does) AND show brief "Reconnecting…" overlay |
| AF-8 | Require click-through modal accepting AI disclosure before site loads | Overkill for a portfolio; adds friction recruiters hate | Passive banner + badge is sufficient for Art. 50(4) creative-works standard |

---

## 6. Feature Dependencies

```
TS-1 (sandbox config)  ────┐
                           ├──►  TS-2 (verify API key works)  ────►  TS-5 (reconnect UX)
TS-7 (fix intro wording) ──┘                                          │
                                                                       ▼
TS-3 (disclaimer badge) ───►  TS-4 (free-tier note, same copy) ────►  TS-6 (prod deploy)

OPT-1, OPT-4 depend on TS-5 (reconnect behavior must be known first)
OPT-5 depends on TS-2 (knowing sandbox failure modes)
OPT-3, OPT-6, OPT-7 are independent and can ship in a follow-up
```

---

## 7. MVP Recommendation for This Milestone

**Ship (minimum viable):**
1. TS-1 through TS-7 — all seven table stakes
2. OPT-7 (ARIA/alt-text) — trivial effort, strengthens Art. 50(5) posture

**Defer to a follow-up milestone:**
- OPT-1, OPT-4 (session-timer UX polish) — only worth building if analytics show users confused by 2-min disconnects
- OPT-3 (dedicated disclosure page) — overkill for first launch; fold into footer note
- OPT-5 (mock fallback) — only needed if free tier concurrency becomes a real issue in traffic

**Rationale:** The milestone's core value is *not* a richer avatar experience — it's **sustainable public deployment with legal-grade transparency**. Ship the minimum that satisfies the PROJECT.md acceptance criteria, then iterate based on real traffic.

---

## 8. Concrete Placement Plan for This Codebase

Given `frontend/app/page.tsx` layout (left col = video, right col = tabs) and `frontend/components/VideoPlayer.tsx` (existing top-left "Live" badge, top-right Disconnect button):

| Element | File | Location | Content (Variant 1) |
|---------|------|----------|---------------------|
| Badge | `VideoPlayer.tsx` | New element bottom-left of video, mirroring the existing "Live" top-left badge | `AI avatar · not Damir's likeness` with small info icon |
| Banner | `page.tsx` | New strip immediately **above** the `<VideoPlayer>` in the left column (or just below on mobile where video is 45vh) | One-line copy from Variant 1 banner |
| Footer note | `page.tsx` | New small `<p>` at bottom of the chat tab content, below `<DevConsole>` | Variant 1 footer copy |
| Intro rewording | `page.tsx` | `AVATAR_INTRO` constant | Rewrite to third-person: `"Welcome. I'm an AI assistant trained on Damir Imangulov's CV. Ask me about his backends, cloud architecture, or technical challenges."` |
| Alt-text | `VideoPlayer.tsx` | `<video aria-label="...">` | `"AI-generated avatar video, not depicting Damir Imangulov"` |

---

## Sources

- [LiveAvatar: Developing in Sandbox Mode (official docs)](https://docs.liveavatar.com/docs/developing-in-sandbox-mode)
- [LiveAvatar FAQ — HeyGen Help Center](https://help.heygen.com/en/articles/12758866-liveavatar-faq)
- [Introducing LiveAvatar — HeyGen Help Center](https://help.heygen.com/en/articles/12758516-introducing-liveavatar)
- [HeyGen API / LiveAvatar Pricing & Subscriptions Explained](https://help.heygen.com/en/articles/10060327-heygen-api-liveavatar-pricing-subscriptions-explained)
- [LiveAvatar overview / getting started](https://docs.liveavatar.com/docs/getting-started)
- [LiveAvatar × LiveKit integration guide](https://docs.livekit.io/agents/models/avatar/plugins/liveavatar/)
- [EU AI Act Article 50 — Transparency Obligations (full text)](https://artificialintelligenceact.eu/article/50/)
- [European Commission — Code of Practice on AI-Generated Content](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content)
- [Jones Day — Draft Code of Practice on AI Labelling and Transparency (Jan 2026)](https://www.jonesday.com/en/insights/2026/01/european-commission-publishes-draft-code-of-practice-on-ai-labelling-and-transparency)
- [Bird & Bird — Taking the EU AI Act to Practice: Draft Transparency Code (2026)](https://www.twobirds.com/en/insights/2026/taking-the-eu-ai-act-to-practice-understanding-the-draft-transparency-code-of-practice)
- [ArentFox Schiff — Business of AI Avatars: Legal Risks and Best Practices](https://www.afslaw.com/perspectives/alerts/the-business-ai-avatars-key-legal-risks-and-best-practices)
- [Traverse Legal — AI Twins and Avatars: Legal Risks](https://www.traverselegal.com/blog/ai-avatar-legal-risks/)
- [Usercentrics — Guide to AI Disclaimers (copy examples + placement)](https://usercentrics.com/guides/website-disclaimers/ai-disclaimer/)
- [Feisworld — AI Content Disclaimer Templates (2026 ready)](https://www.feisworld.com/blog/disclaimer-templates-for-ai-generated-content)
- [ShapeOfAI — Avatar UX Patterns (disclosure badge pattern)](https://www.shapeof.ai/patterns/avatar)
- [Sprout Social — AI Disclaimers: What Marketing Leaders Need to Know](https://sproutsocial.com/insights/ai-disclaimer/)
