from __future__ import annotations

"""Phase 1 smoke test for the LiveAvatar free-tier/sandbox switch.

Drives the running local FastAPI backend's /session, /speak, and /interrupt
endpoints under the sandbox configuration and prints a paste-ready markdown
summary block mapping SMOKE-01 through SMOKE-04 to PASS / FAIL / OBSERVED.

Prerequisites (see setup-local.ps1):
  1. Backend running on http://localhost:8000 with these env vars set:
       LIVEAVATAR_API_KEY         = <existing paid key — intentional per D-08>
       LIVEAVATAR_AVATAR_ID       = dd73ea75-1218-4ef3-92ce-606d5f7fbc0a
       LIVEAVATAR_IS_SANDBOX      = true
       LIVEAVATAR_SESSION_MODE    = LITE
  2. Python venv with httpx (reuse backend/requirements.txt venv).

Usage:
    python scripts/smoke-liveavatar.py [--base-url http://localhost:8000] [--json]

Exits non-zero if SMOKE-01 fails (hard gate). SMOKE-02 ws_url absence is
reported as OBSERVED, not FAIL (per REQUIREMENTS.md SMOKE-02 degradation
acceptance clause). SMOKE-03 and SMOKE-04 are OBSERVED-only (recorded, not
asserted) per D-07.
"""

import argparse
import asyncio
import datetime
import json
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8000"
# SSRF guard (threat T-02-02) — script may only hit the operator's localhost.
ALLOWED_BASE_URL_PREFIXES = ("http://localhost:", "http://127.0.0.1:")
SANDBOX_CAP_WAIT_SECONDS = 130  # slightly above documented 60–120 s cap
CONCURRENT_SESSION_COUNT = 2  # per D-07 (e)
REQUEST_TIMEOUT_SECONDS = 25.0  # generous — /session can take 5–15 s cold
SPEAK_TEXT = "Smoke test: the quick brown fox jumps over the lazy dog."

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("smoke")


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Result of a single SMOKE-0X check.

    `status` is one of: "PASS", "FAIL", "OBSERVED".
    `summary` is a single line suitable for the markdown table row.
    `details` is internal-only scratch data — NEVER emitted to the markdown
    summary (threat T-02-01 mitigation).
    """

    id: str
    status: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_base_url(url: str) -> None:
    """Raise ValueError if `url` is not an allowed localhost-style prefix.

    SSRF guard (threat T-02-02): script must not be pointed at attacker-
    controlled URLs such as metadata services.
    """
    if not any(url.startswith(p) for p in ALLOWED_BASE_URL_PREFIXES):
        raise ValueError(
            "Refusing to run against non-localhost base URL %r. "
            "Allowed prefixes: %s" % (url, ", ".join(ALLOWED_BASE_URL_PREFIXES))
        )


async def _preflight(client: httpx.AsyncClient, base_url: str) -> None:
    """Confirm the backend is up before running any checks."""
    try:
        r = await client.get(f"{base_url}/health")
    except httpx.RequestError as exc:
        raise RuntimeError(
            "Could not reach backend at %s (%s). "
            "Is the backend running? See setup-local.ps1." % (base_url, type(exc).__name__)
        ) from exc
    if r.status_code != 200:
        raise RuntimeError(
            "Backend /health returned HTTP %d — refusing to run smoke." % r.status_code
        )


def _extract_session_id(body: dict[str, Any]) -> str | None:
    """Handle both top-level and nested SessionResponse shapes."""
    sid = body.get("session_id")
    if sid:
        return str(sid)
    nested = body.get("liveavatar_data")
    if isinstance(nested, dict):
        nsid = nested.get("session_id")
        if nsid:
            return str(nsid)
    return None


def _extract_ws_url(body: dict[str, Any]) -> str | None:
    """Handle both top-level and nested ws_url locations."""
    ws = body.get("ws_url")
    if ws:
        return str(ws)
    nested = body.get("liveavatar_data")
    if isinstance(nested, dict):
        nws = nested.get("ws_url")
        if nws:
            return str(nws)
    return None


# ---------------------------------------------------------------------------
# SMOKE-01 — /session returns 200 + session_id under sandbox config
# ---------------------------------------------------------------------------

async def run_smoke_01(
    client: httpx.AsyncClient,
    base_url: str,
) -> tuple[CheckResult, str | None, dict[str, Any] | None]:
    """Hard gate: drive the backend /session endpoint.

    Returns (result, session_id_used, response_body). The session_id and body
    are reused by SMOKE-02 so we do not double-charge a sandbox session.
    """
    session_id = str(uuid.uuid4())
    result = CheckResult(id="SMOKE-01", status="FAIL", summary="(not run)")
    body: dict[str, Any] | None = None
    try:
        t0 = time.monotonic()
        r = await client.get(
            f"{base_url}/session",
            headers={"X-Session-ID": session_id},
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        status_code = r.status_code
        # Only attempt JSON parse if 2xx; on error, read body text cautiously.
        try:
            body = r.json()
        except Exception:
            body = None

        if status_code == 200 and isinstance(body, dict) and _extract_session_id(body):
            result.status = "PASS"
            result.summary = (
                "/session returned 200 in %d ms with session_id" % elapsed_ms
            )
            result.details = {"elapsed_ms": elapsed_ms}
        else:
            result.status = "FAIL"
            result.summary = (
                "/session returned HTTP %d in %d ms — no session_id in body"
                % (status_code, elapsed_ms)
            )
            # D-10 case (a): provider rejected is_sandbox on paid key
            if status_code >= 400 and r.text:
                lowered = r.text.lower()
                if "is_sandbox" in lowered or "sandbox" in lowered:
                    result.details["note"] = (
                        "Possible D-10 case (a): provider rejected is_sandbox "
                        "on paid-tier key."
                    )
            result.details["http_status"] = status_code
            result.details["elapsed_ms"] = elapsed_ms
    except Exception as exc:
        # Threat T-02-03: never include str(exc) in summary (may echo headers).
        logger.exception("SMOKE-01 failed unexpectedly")
        result.status = "FAIL"
        result.summary = "unexpected error: %s" % type(exc).__name__
    return result, session_id, body


# ---------------------------------------------------------------------------
# SMOKE-02 — ws_url presence in LITE sandbox
# ---------------------------------------------------------------------------

async def run_smoke_02(
    body: dict[str, Any] | None,
) -> CheckResult:
    """Re-inspect the SMOKE-01 body for ws_url presence. OBSERVED-only."""
    result = CheckResult(id="SMOKE-02", status="OBSERVED", summary="(no body captured)")
    try:
        if not isinstance(body, dict):
            result.summary = "ws_url check skipped — no /session body available"
            return result
        ws_url = _extract_ws_url(body)
        if ws_url:
            result.summary = (
                "ws_url present in LITE sandbox — full TTS path works"
            )
        else:
            result.summary = (
                "ws_url absent in LITE sandbox — degraded to "
                "'avatar visible, no TTS push' path (documented acceptable)"
            )
    except Exception as exc:
        logger.exception("SMOKE-02 failed unexpectedly")
        result.summary = "unexpected error: %s" % type(exc).__name__
    return result


# ---------------------------------------------------------------------------
# SMOKE-03 — end-to-end Q&A + post-cap reconnect
# ---------------------------------------------------------------------------

async def run_smoke_03(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
) -> CheckResult:
    """Drive /speak, /interrupt, then wait past the cap and call /session
    again with a fresh UUID to confirm clean reconnect. OBSERVED-only."""
    result = CheckResult(id="SMOKE-03", status="OBSERVED", summary="(not run)")
    speak_status = "?"
    interrupt_status = "?"
    reconnect_status: int | str = "?"

    try:
        # POST /speak
        try:
            r = await client.post(
                f"{base_url}/speak",
                headers={"X-Session-ID": session_id},
                json={"text": SPEAK_TEXT},
            )
            if r.status_code == 200:
                try:
                    payload = r.json()
                    speak_status = str(payload.get("status", "?"))
                except Exception:
                    speak_status = "ok (non-json)"
            else:
                speak_status = "http_%d" % r.status_code
        except Exception as exc:
            logger.warning("/speak call failed: %s", type(exc).__name__)
            speak_status = "err_%s" % type(exc).__name__

        # POST /interrupt
        try:
            r = await client.post(
                f"{base_url}/interrupt",
                headers={"X-Session-ID": session_id},
            )
            if r.status_code == 200:
                try:
                    payload = r.json()
                    interrupt_status = str(payload.get("status", "?"))
                except Exception:
                    interrupt_status = "ok (non-json)"
            else:
                interrupt_status = "http_%d" % r.status_code
        except Exception as exc:
            logger.warning("/interrupt call failed: %s", type(exc).__name__)
            interrupt_status = "err_%s" % type(exc).__name__

        # Wait past the sandbox cap, then try a fresh session.
        logger.info(
            "[SMOKE-03] Sleeping %d s to cross the ~60–120 s sandbox cap…",
            SANDBOX_CAP_WAIT_SECONDS,
        )
        await asyncio.sleep(SANDBOX_CAP_WAIT_SECONDS)
        fresh_sid = str(uuid.uuid4())
        try:
            r = await client.get(
                f"{base_url}/session",
                headers={"X-Session-ID": fresh_sid},
            )
            reconnect_status = r.status_code
        except Exception as exc:
            logger.warning("Post-cap /session call failed: %s", type(exc).__name__)
            reconnect_status = "err_%s" % type(exc).__name__

        result.summary = (
            "speak: %s; interrupt: %s; post-cap reconnect: %s"
            % (speak_status, interrupt_status, reconnect_status)
        )
    except Exception as exc:
        logger.exception("SMOKE-03 failed unexpectedly")
        result.summary = "unexpected error: %s" % type(exc).__name__
    return result


# ---------------------------------------------------------------------------
# SMOKE-04 — concurrent-session probe
# ---------------------------------------------------------------------------

async def run_smoke_04(
    client: httpx.AsyncClient,
    base_url: str,
) -> CheckResult:
    """Fire CONCURRENT_SESSION_COUNT parallel /session calls with fresh UUIDs
    and classify the observed pattern. OBSERVED-only."""
    result = CheckResult(id="SMOKE-04", status="OBSERVED", summary="(not run)")
    try:
        sids = [str(uuid.uuid4()) for _ in range(CONCURRENT_SESSION_COUNT)]

        async def _one(sid: str) -> tuple[str, int | None, bool, int]:
            t0 = time.monotonic()
            try:
                r = await client.get(
                    f"{base_url}/session",
                    headers={"X-Session-ID": sid},
                )
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                has_sid = False
                try:
                    has_sid = bool(_extract_session_id(r.json()))
                except Exception:
                    has_sid = False
                return sid, r.status_code, has_sid, elapsed_ms
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                logger.warning(
                    "Concurrent /session call errored: %s", type(exc).__name__
                )
                return sid, None, False, elapsed_ms

        raw = await asyncio.gather(
            *[_one(sid) for sid in sids], return_exceptions=True
        )
        # Flatten any exception instances (gather w/ return_exceptions=True).
        probes: list[tuple[str, int | None, bool, int]] = []
        for item in raw:
            if isinstance(item, BaseException):
                probes.append(("?", None, False, 0))
            else:
                probes.append(item)  # type: ignore[arg-type]

        statuses = [p[1] for p in probes]
        has_sids = [p[2] for p in probes]
        all_ok = all(s == 200 and ok for s, ok in zip(statuses, has_sids))
        any_409 = any(s == 409 for s in statuses)
        first_ok_second_missing = (
            len(probes) >= 2
            and probes[0][1] == 200
            and probes[0][2]
            and probes[1][1] == 200
            and not probes[1][2]
        )

        if all_ok:
            result.summary = (
                "both sessions succeeded (no observed concurrency cap)"
            )
        elif any_409:
            result.summary = "second session 409ed"
        elif first_ok_second_missing:
            result.summary = "second session silently overrode first"
        else:
            # Summarise the pattern without leaking bodies.
            codes = ",".join(str(s) if s is not None else "err" for s in statuses)
            result.summary = "unexpected pattern: statuses=[%s]" % codes
    except Exception as exc:
        logger.exception("SMOKE-04 failed unexpectedly")
        result.summary = "unexpected error: %s" % type(exc).__name__
    return result


# ---------------------------------------------------------------------------
# Summary emission
# ---------------------------------------------------------------------------

def emit_summary(
    results: list[CheckResult],
    base_url: str,
    total_elapsed_s: float,
    *,
    as_json: bool,
) -> str:
    """Produce the paste-ready ## Sandbox Behavior Baseline block.

    Emits ONLY status codes, elapsed times, and textual categories — NEVER
    raw response bodies, tokens, or header values (threat T-02-01).
    """
    today = datetime.date.today().isoformat()

    if as_json:
        payload = {
            "heading": "Sandbox Behavior Baseline (observed %s)" % today,
            "backend": base_url,
            "config": {
                "LIVEAVATAR_IS_SANDBOX": "true",
                "LIVEAVATAR_SESSION_MODE": "LITE",
                "LIVEAVATAR_AVATAR_ID": "dd73ea75-1218-4ef3-92ce-606d5f7fbc0a",
                "api_key": "existing paid key (per Phase 1 decision D-08)",
            },
            "results": [
                {"id": r.id, "status": r.status, "summary": r.summary}
                for r in results
            ],
            "elapsed_seconds": round(total_elapsed_s, 1),
        }
        return json.dumps(payload, indent=2)

    rows = "\n".join(
        "| %-8s | %-8s | %s |" % (r.id, r.status, r.summary) for r in results
    )
    block = (
        "## Sandbox Behavior Baseline (observed %s)\n"
        "\n"
        "Backend: %s\n"
        "Config: LIVEAVATAR_IS_SANDBOX=true, LIVEAVATAR_SESSION_MODE=LITE,\n"
        "        LIVEAVATAR_AVATAR_ID=dd73ea75-1218-4ef3-92ce-606d5f7fbc0a,\n"
        "        API key: existing paid key (per Phase 1 decision D-08)\n"
        "\n"
        "| ID       | Status   | Summary |\n"
        "|----------|----------|---------|\n"
        "%s\n"
        "\n"
        "Elapsed: %.1f s\n"
    ) % (today, base_url, rows, total_elapsed_s)
    return block


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

async def main() -> int:
    """CLI entry: parse args, validate base URL, preflight, run checks, emit."""
    parser = argparse.ArgumentParser(
        description="Phase 1 smoke test for the LiveAvatar free-tier switch."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Backend base URL (default: %s)" % DEFAULT_BASE_URL,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results as JSON instead of the markdown block.",
    )
    args = parser.parse_args()

    try:
        _validate_base_url(args.base_url)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    t_start = time.monotonic()
    results: list[CheckResult] = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        try:
            await _preflight(client, args.base_url)
        except Exception as exc:
            logger.error("Preflight failed: %s", exc)
            return 2

        # SMOKE-01 — hard gate
        r1, session_id, body = await run_smoke_01(client, args.base_url)
        results.append(r1)
        # SMOKE-02 — observe the same body (no extra /session call)
        r2 = await run_smoke_02(body)
        results.append(r2)
        # SMOKE-03 — speak/interrupt/post-cap reconnect
        r3 = await run_smoke_03(client, args.base_url, session_id)
        results.append(r3)
        # SMOKE-04 — concurrency probe (must run AFTER 01-03 so it is clean)
        r4 = await run_smoke_04(client, args.base_url)
        results.append(r4)

        # Best-effort cleanup: release the session we created for SMOKE-01/03.
        try:
            await client.delete(
                f"{args.base_url}/session",
                headers={"X-Session-ID": session_id},
            )
        except Exception as exc:
            logger.debug("cleanup DELETE /session failed: %s", type(exc).__name__)

    total_elapsed_s = time.monotonic() - t_start
    output = emit_summary(
        results, args.base_url, total_elapsed_s, as_json=args.json
    )
    print(output)

    # Exit code: 0 iff SMOKE-01 PASSed (hard gate per T-02-04).
    return 0 if results and results[0].status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
