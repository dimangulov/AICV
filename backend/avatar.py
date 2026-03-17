"""
LiveAvatar session management and avatar speech pipeline.

Responsibilities:
  - UserSession dataclass — per-browser-tab state
  - In-process session store + idle eviction
  - _get_or_create_liveavatar_session() — token + start flow with retry
  - _avatar_ws_loop() — persistent WebSocket keep-alive per session
  - _stop_liveavatar_session() — remote cleanup call on teardown
  - speak_on_avatar() — TTS → PCM → LiveAvatar WebSocket (streaming)
  - Filler phrase cache (FILLER_PHRASES, filler_cache, warm_fillers())
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import websockets
from fastapi import HTTPException, status

import tts as tts_module
from config import (
    AZURE_SPEECH_KEY,
    ENABLE_FILLERS,
    LIVEAVATAR_API_KEY,
    LIVEAVATAR_AVATAR_ID,
    LIVEAVATAR_BASE_URL,
    LIVEAVATAR_IS_SANDBOX,
    LIVEAVATAR_SESSION_MODE,
    MAX_SESSIONS,
    SESSION_IDLE_TTL,
    UUID_RE,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Filler phrase cache
# ---------------------------------------------------------------------------

FILLER_PHRASES: list[str] = [
    "Sure, let me think about that.",
    "Good question — give me just a moment.",
    "Interesting — let me pull that up for you.",
    "Absolutely, one second.",
    "Let me check that for you.",
    "Great question, I'll look into that right now.",
    "Of course — just a moment while I think through that.",
    "Sure thing, I'm on it.",
]

filler_cache: dict[str, bytes] = {}  # phrase → PCM bytes


async def warm_fillers() -> None:
    """Pre-synthesise all filler phrases at startup so they play with zero TTS latency."""
    for phrase in FILLER_PHRASES:
        try:
            filler_cache[phrase] = await tts_module.synthesize_pcm(phrase)
            logger.debug("[filler] Cached: %r", phrase[:40])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[filler] Failed to cache %r: %s", phrase[:40], exc)
    logger.info("[filler] Pre-synthesised %d/%d phrases", len(filler_cache), len(FILLER_PHRASES))


def pick_filler() -> tuple[str, bytes] | None:
    """Return a random (phrase, pcm) pair from the cache, or None if cache is empty."""
    if not filler_cache:
        return None
    phrase = random.choice(list(filler_cache))
    return phrase, filler_cache[phrase]


# ---------------------------------------------------------------------------
# UserSession dataclass
# ---------------------------------------------------------------------------

@dataclass
class UserSession:
    liveavatar_data: dict[str, Any] | None = None
    session_expires: float = 0.0
    session_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    ws_task: asyncio.Task | None = None
    speak_ws: Any | None = None                 # persistent websockets connection
    speak_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_active: float = field(default_factory=time.monotonic)
    interrupted: bool = False
    liveavatar_session_id: str | None = None
    liveavatar_session_token: str | None = None

    def is_valid(self) -> bool:
        return self.liveavatar_data is not None and time.monotonic() < self.session_expires

    def invalidate(self, reason: str, *, stop_remote: bool = True) -> None:
        """Clear cached session state and optionally fire a remote stop."""
        if self.liveavatar_data:
            logger.info("[session] Invalidated: %s", reason)
        session_id_to_stop = self.liveavatar_session_id if stop_remote else None
        token_to_stop = self.liveavatar_session_token if stop_remote else None
        self.liveavatar_data = None
        self.session_expires = 0.0
        self.speak_ws = None
        self.liveavatar_session_id = None
        self.liveavatar_session_token = None
        if session_id_to_stop and token_to_stop:
            asyncio.create_task(
                _stop_liveavatar_session(session_id_to_stop, token_to_stop, reason)
            )


# ---------------------------------------------------------------------------
# In-process session store
# ---------------------------------------------------------------------------

_user_sessions: dict[str, UserSession] = {}
_user_sessions_lock: asyncio.Lock = asyncio.Lock()
_LIVEAVATAR_SESSION_TTL: float = 1800.0  # 30 min conservative TTL


async def get_or_create_user_session(sid: str) -> UserSession:
    """Return the UserSession for this browser tab, creating one if needed."""
    async with _user_sessions_lock:
        if sid not in _user_sessions:
            if len(_user_sessions) >= MAX_SESSIONS:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Maximum concurrent sessions reached. Try again later.",
                )
            _user_sessions[sid] = UserSession()
        entry = _user_sessions[sid]
    entry.last_active = time.monotonic()
    return entry


async def pop_user_session(sid: str) -> UserSession | None:
    """Remove and return the session for sid, or None if it did not exist."""
    async with _user_sessions_lock:
        return _user_sessions.pop(sid, None)


async def evict_idle_sessions() -> None:
    """Background task: remove sessions idle > SESSION_IDLE_TTL every 2 minutes."""
    while True:
        await asyncio.sleep(60)
        now = time.monotonic()
        async with _user_sessions_lock:
            to_remove = [
                sid for sid, e in _user_sessions.items()
                if (now - e.last_active) > SESSION_IDLE_TTL
            ]
            evicted: list[UserSession] = []
            for sid in to_remove:
                entry = _user_sessions.pop(sid)
                if entry.ws_task and not entry.ws_task.done():
                    entry.ws_task.cancel()
                evicted.append(entry)
        for entry in evicted:
            entry.invalidate("idle eviction", stop_remote=True)
        if to_remove:
            logger.info("[evict] Removed %d idle sessions", len(to_remove))


# ---------------------------------------------------------------------------
# Remote cleanup
# ---------------------------------------------------------------------------


async def _stop_liveavatar_session(session_id: str, session_token: str, reason: str) -> None:
    """
    Call POST /v1/sessions/stop on the LiveAvatar API to release server-side
    WebRTC resources immediately instead of waiting for their TTL to expire.
    Fire-and-forget — errors are logged but never surface to callers.
    """
    stop_headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "Authorization": f"Bearer {session_token}",
    }
    url = f"{LIVEAVATAR_BASE_URL}/v1/sessions/stop"
    try:
        client = tts_module.http_client
        if client is None:
            async with httpx.AsyncClient(timeout=10.0) as tmp:
                r = await tmp.post(url, headers=stop_headers, json={})
                r.raise_for_status()
        else:
            r = await client.post(url, headers=stop_headers, json={})
            r.raise_for_status()
        logger.info("[session] Remote stop OK — session=%s reason=%s", session_id, reason)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[session] Remote stop failed — session=%s: %s", session_id, exc)


# ---------------------------------------------------------------------------
# LiveAvatar session provisioning
# ---------------------------------------------------------------------------


async def _avatar_ws_loop(ws_url: str, liveavatar_session_id: str, entry: UserSession) -> None:
    """
    Maintains a persistent WebSocket for one UserSession.
      1. Keep-alive — sends session.keep_alive every 3 minutes.
      2. Speak channel — speak_on_avatar reuses entry.speak_ws to send agent.speak
         frames without opening a new connection per call.
    """
    logger.info("[avatar_ws] Connecting WebSocket for session %s", liveavatar_session_id)
    try:
        async with websockets.connect(ws_url) as ws:
            entry.speak_ws = ws
            logger.info("[avatar_ws] WebSocket ready for session %s", liveavatar_session_id)
            while True:
                try:
                    async with asyncio.timeout(180):
                        raw = await ws.recv()
                        msg = json.loads(raw)
                        event_type = msg.get("type", "")
                        logger.debug("[avatar_ws] event: %s", event_type)
                        if event_type == "session.stopped":
                            logger.info(
                                "[avatar_ws] Session %s stopped (%s) — invalidating",
                                liveavatar_session_id,
                                msg.get("data", {}).get("end_reason", "unknown"),
                            )
                            entry.invalidate("session.stopped received")
                            return
                except TimeoutError:
                    await ws.send(json.dumps({
                        "type": "session.keep_alive",
                        "event_id": str(uuid.uuid4()),
                    }))
                    logger.debug("[avatar_ws] keep-alive sent for session %s", liveavatar_session_id)
    except Exception as exc:
        logger.warning("[avatar_ws] WebSocket closed for session %s: %s", liveavatar_session_id, exc)
        entry.invalidate(f"WebSocket closed: {exc}")
    finally:
        entry.speak_ws = None


async def get_or_create_liveavatar_session(entry: UserSession) -> dict[str, Any]:
    """
    Returns a cached LiveAvatar session for this UserSession, or creates a new one.

    Flow (per LiveAvatar v1 API docs):
      1. POST /v1/sessions/token — authenticates with X-Api-Key, returns JWT + session_id.
      2. POST /v1/sessions/start — authenticates with Bearer JWT, returns LiveKit credentials.
    """
    now = time.monotonic()
    async with entry.session_lock:
        if entry.is_valid():
            logger.info("Reusing cached LiveAvatar session %s", entry.liveavatar_data["session_id"])  # type: ignore[index]
            return entry.liveavatar_data  # type: ignore[return-value]

        base_headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        async def _fetch_token() -> tuple[str, str]:
            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.post(
                    f"{LIVEAVATAR_BASE_URL}/v1/sessions/token",
                    headers={**base_headers, "X-Api-Key": LIVEAVATAR_API_KEY},
                    json={
                        "avatar_id": LIVEAVATAR_AVATAR_ID,
                        "mode": LIVEAVATAR_SESSION_MODE,
                        "is_sandbox": LIVEAVATAR_IS_SANDBOX,
                    },
                )
                r.raise_for_status()
                d = r.json()["data"]
                logger.info("LiveAvatar token obtained for session %s", d["session_id"])
                return d["session_token"], d["session_id"]

        session_token, session_id = await _fetch_token()

        MAX_START_ATTEMPTS = 2
        start_data: dict[str, Any] | None = None
        for attempt in range(1, MAX_START_ATTEMPTS + 1):
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(
                    "Starting LiveAvatar session %s (attempt %d/%d, up to 60 s)…",
                    session_id, attempt, MAX_START_ATTEMPTS,
                )
                start_response = await client.post(
                    f"{LIVEAVATAR_BASE_URL}/v1/sessions/start",
                    headers={**base_headers, "Authorization": f"Bearer {session_token}"},
                    json={},
                )
                if start_response.status_code == 500 and attempt < MAX_START_ATTEMPTS:
                    logger.warning(
                        "LiveAvatar /start returned 500 for session %s — "
                        "fetching a fresh token and retrying in 3 s…",
                        session_id,
                    )
                    await asyncio.sleep(3)
                    session_token, session_id = await _fetch_token()
                    continue
                start_response.raise_for_status()
                start_data = start_response.json()["data"]
                logger.info("LiveAvatar session started: %s", start_data.get("session_id", session_id))
                break

        assert start_data is not None
        result: dict[str, Any] = {
            "session_id": start_data.get("session_id") or session_id,
            "livekit_url": start_data["livekit_url"],
            "livekit_client_token": start_data["livekit_client_token"],
            "ws_url": start_data.get("ws_url") or "",
        }
        logger.info(
            "LiveAvatar session cached — session_id=%s ws_url=%s",
            result["session_id"],
            result["ws_url"] or "<empty — LITE ws_url not returned>",
        )
        entry.liveavatar_data = result
        entry.session_expires = now + _LIVEAVATAR_SESSION_TTL
        entry.liveavatar_session_id = result["session_id"]
        entry.liveavatar_session_token = session_token

        if result["ws_url"]:
            if entry.ws_task and not entry.ws_task.done():
                entry.ws_task.cancel()
            entry.ws_task = asyncio.create_task(
                _avatar_ws_loop(result["ws_url"], result["session_id"], entry)
            )

        return result


# ---------------------------------------------------------------------------
# Speech pipeline
# ---------------------------------------------------------------------------


async def speak_on_avatar(
    text: str,
    user_session_id: str = "anonymous",
    *,
    pcm_override: bytes | None = None,
) -> None:
    """
    Synthesize text via TTS and stream PCM audio to the user's LiveAvatar
    WebSocket. Pass pcm_override to skip synthesis (e.g. pre-cached filler).
    Each user_session_id has its own per-session WS connection so
    concurrent users never interleave audio.

    When Azure TTS is configured, synthesis is streamed chunk-by-chunk: a
    background producer task fills an asyncio.Queue concurrently with
    LiveAvatar session acquisition so the avatar starts speaking as soon as
    the first PCM bytes arrive (no full-buffer wait).
    """
    if not LIVEAVATAR_API_KEY:
        logger.debug("[speak] No LIVEAVATAR_API_KEY — skipping avatar speech")
        return

    entry = await get_or_create_user_session(user_session_id)
    entry.last_active = time.monotonic()

    event_id = str(uuid.uuid4())
    tts_task: asyncio.Task | None = None
    tts_queue: asyncio.Queue[bytes | None] | None = None
    pcm_bytes: bytes = b""

    # Phase 1: start TTS + session acquisition concurrently
    if pcm_override is not None:
        try:
            liveavatar_session = await get_or_create_liveavatar_session(entry)
        except Exception as exc:
            logger.error("[speak] Session setup failed: %s", exc)
            return
    elif AZURE_SPEECH_KEY:
        tts_queue = asyncio.Queue(maxsize=8)

        async def _tts_producer() -> None:
            try:
                async for chunk in tts_module._stream_tts_azure(text):
                    await tts_queue.put(chunk)
            except Exception as exc:  # noqa: BLE001
                logger.error("[speak] TTS stream error: %s", exc)
            finally:
                await tts_queue.put(None)  # sentinel — end of stream

        tts_task = asyncio.create_task(_tts_producer())
        try:
            liveavatar_session = await get_or_create_liveavatar_session(entry)
        except Exception as exc:
            logger.error("[speak] Session setup failed: %s", exc)
            tts_task.cancel()
            return
    else:
        try:
            pcm_bytes, liveavatar_session = await asyncio.gather(
                tts_module._synthesize_pcm_gtts(text),
                get_or_create_liveavatar_session(entry),
            )
        except Exception as exc:
            logger.error("[speak] Parallel TTS/session setup failed: %s", exc)
            return

    # Phase 2: ensure WebSocket is open
    ws = entry.speak_ws
    if ws is None:
        logger.warning("[speak] WebSocket not yet ready — waiting up to 3 s")
        for _ in range(6):
            await asyncio.sleep(0.5)
            ws = entry.speak_ws
            if ws is not None:
                break
        if ws is None:
            logger.error("[speak] WebSocket unavailable after wait — dropping speak")
            if tts_task is not None:
                tts_task.cancel()
            return

    # Phase 3: serialised WS send
    async with entry.speak_lock:
        try:
            entry.interrupted = False

            if pcm_override is not None:
                for i in range(0, len(pcm_override), 48_000):
                    if entry.interrupted:
                        logger.info("[speak] Interrupted — skipping remaining chunks")
                        return
                    await ws.send(json.dumps({
                        "type": "agent.speak",
                        "event_id": event_id,
                        "audio": base64.b64encode(pcm_override[i : i + 48_000]).decode(),
                    }))
            elif tts_queue is not None:
                while True:
                    chunk = await tts_queue.get()
                    if chunk is None:
                        break
                    if entry.interrupted:
                        logger.info("[speak] Interrupted — stopping TTS stream")
                        if tts_task is not None:
                            tts_task.cancel()
                        return
                    await ws.send(json.dumps({
                        "type": "agent.speak",
                        "event_id": event_id,
                        "audio": base64.b64encode(chunk).decode(),
                    }))
            else:
                for i in range(0, len(pcm_bytes), 48_000):
                    if entry.interrupted:
                        logger.info("[speak] Interrupted — skipping remaining chunks")
                        return
                    await ws.send(json.dumps({
                        "type": "agent.speak",
                        "event_id": event_id,
                        "audio": base64.b64encode(pcm_bytes[i : i + 48_000]).decode(),
                    }))

            if not entry.interrupted:
                await ws.send(json.dumps({
                    "type": "agent.speak_end",
                    "event_id": event_id,
                }))
            logger.info(
                "[speak] Done — user=%s liveav=%s",
                user_session_id, liveavatar_session["session_id"],
            )
        except Exception as exc:
            logger.error("[speak] WebSocket error: %s", exc)
            entry.invalidate(f"speak WS error: {exc}")
