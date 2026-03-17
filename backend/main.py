"""
Interactive Digital Twin CV — FastAPI Backend
=============================================
This module contains only the FastAPI application wiring (lifespan, middleware,
and route handlers).  All domain logic lives in focused submodules:

  config.py  — environment-variable constants
  models.py  — Pydantic request / response models
  rag.py     — LLM / embeddings factories + LangChain LCEL chain
  tts.py     — Azure Speech / gTTS helpers + shared HTTP client
  avatar.py  — LiveAvatar session management + speech pipeline
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableSerializable
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

import avatar as avatar_module
import tts as tts_module
from avatar import _user_sessions, _user_sessions_lock
from config import (
    ALLOWED_ORIGINS,
    AZURE_OPENAI_CHAT_DEPLOYMENT,
    AZURE_SPEECH_KEY,
    BIO_FILE_PATH,
    ENABLE_FILLERS,
    LIVEAVATAR_API_KEY,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    QDRANT_CLOUD_URL,
    QDRANT_MODE,
    QDRANT_URL,
    UUID_RE,
)
from models import AskRequest, AskResponse, HealthResponse, SpeakRequest
from rag import build_rag_chain, format_history

logger = logging.getLogger(__name__)

_rag_chain: RunnableSerializable | None = None
_SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag_chain
    logger.info("=== Digital Twin CV API — startup ===")

    tts_module.http_client = httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )

    try:
        _rag_chain = build_rag_chain()
    except Exception as exc:
        logger.error("RAG chain initialisation failed: %s", exc, exc_info=True)

    if ENABLE_FILLERS and (AZURE_SPEECH_KEY or tts_module.gtts_available):
        asyncio.create_task(avatar_module.warm_fillers())
    else:
        logger.info("[filler] Fillers disabled or no TTS backend — skipping pre-synthesis")

    eviction_task = asyncio.create_task(avatar_module.evict_idle_sessions())
    yield
    eviction_task.cancel()
    if tts_module.http_client:
        await tts_module.http_client.aclose()
    logger.info("=== Digital Twin CV API — shutdown ===")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Digital Twin CV API",
    description=(
        "RAG-powered backend for the Interactive Digital Twin CV. "
        "Exposes /ask for question answering and /session for LiveAvatar WebRTC."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Session-ID"],
    allow_credentials=False,
)


# ---------------------------------------------------------------------------
# Routes — RAG
# ---------------------------------------------------------------------------

@app.post("/ask", response_model=AskResponse, summary="Ask a question about the candidate")
async def ask(
    payload: AskRequest,
    background_tasks: BackgroundTasks,
    x_session_id: str = Header(default="anonymous"),
) -> AskResponse:
    if _rag_chain is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "RAG chain is not initialised. "
                "Ensure Ollama is running and bio.txt exists, then restart the server."
            ),
        )
    sid = x_session_id if UUID_RE.match(x_session_id) else "anonymous"
    try:
        start = time.monotonic()
        answer: str = _rag_chain.invoke({
            "question": payload.question,
            "history": format_history(payload.history),
        })
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info("Question answered in %dms: %r", elapsed_ms, payload.question[:60])
        if LIVEAVATAR_API_KEY:
            background_tasks.add_task(avatar_module.speak_on_avatar, answer, sid)
        return AskResponse(answer=answer, sources=[str(BIO_FILE_PATH)], latency_ms=elapsed_ms)
    except Exception as exc:
        logger.error("Inference error for question %r: %s", payload.question[:60], exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference failed. Is Ollama still running?",
        ) from exc


@app.post("/ask/stream", summary="Stream a question answer token by token (SSE)")
async def ask_stream(
    payload: AskRequest,
    x_session_id: str = Header(default="anonymous"),
) -> StreamingResponse:
    """
    Server-Sent Events endpoint.  Streams LLM tokens to the browser as they
    arrive and triggers avatar speech sentence-by-sentence.

    Event format:
      data: <token>\\n\\n
      data: [DONE] <latency_ms>\\n\\n
    """
    if _rag_chain is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG chain is not initialised.",
        )
    sid = x_session_id if UUID_RE.match(x_session_id) else "anonymous"

    async def _generate():
        start = time.monotonic()
        sentence_buf: list[str] = []

        if ENABLE_FILLERS and LIVEAVATAR_API_KEY and avatar_module.filler_cache:
            hit = avatar_module.pick_filler()
            if hit:
                phrase, pcm = hit
                asyncio.create_task(avatar_module.speak_on_avatar(phrase, sid, pcm_override=pcm))
                logger.debug("[filler] Queued: %r", phrase)

        try:
            async for token in _rag_chain.astream({
                "question": payload.question,
                "history": format_history(payload.history),
            }):
                sentence_buf.append(token)
                yield f"data: {json.dumps(token)}\n\n"

                if LIVEAVATAR_API_KEY and _SENTENCE_ENDINGS.search(token):
                    sentence = "".join(sentence_buf).strip()
                    sentence_buf.clear()
                    if sentence:
                        asyncio.create_task(avatar_module.speak_on_avatar(sentence, sid))

            if LIVEAVATAR_API_KEY:
                remainder = "".join(sentence_buf).strip()
                if remainder:
                    asyncio.create_task(avatar_module.speak_on_avatar(remainder, sid))

            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info("Stream answered in %dms: %r", elapsed_ms, payload.question[:60])
            yield f"data: [DONE] {elapsed_ms}\n\n"

        except Exception as exc:
            logger.error("Stream inference error: %s", exc, exc_info=True)
            yield f"data: [ERROR] {json.dumps(str(exc))}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Routes — Avatar
# ---------------------------------------------------------------------------

@app.post("/speak", summary="Make the avatar speak arbitrary text")
async def speak(
    payload: SpeakRequest,
    background_tasks: BackgroundTasks,
    x_session_id: str = Header(default="anonymous"),
) -> dict[str, str]:
    if not LIVEAVATAR_API_KEY:
        return {"status": "mock"}
    sid = x_session_id if UUID_RE.match(x_session_id) else "anonymous"
    background_tasks.add_task(avatar_module.speak_on_avatar, payload.text, sid)
    return {"status": "queued"}


@app.post("/interrupt", summary="Stop the avatar mid-speech (user started talking)")
async def interrupt(
    x_session_id: str = Header(default="anonymous"),
) -> dict[str, str]:
    """
    Sends an agent.interrupt event over the session's WebSocket so LiveAvatar
    stops audio playback immediately.
    """
    sid = x_session_id if UUID_RE.match(x_session_id) else "anonymous"
    async with _user_sessions_lock:
        entry = _user_sessions.get(sid)
    if entry is None:
        return {"status": "no-session"}

    entry.interrupted = True
    ws = entry.speak_ws
    if ws is not None:
        try:
            await ws.send(json.dumps({"type": "agent.interrupt", "event_id": str(uuid.uuid4())}))
            logger.info("[interrupt] agent.interrupt sent for user %s", sid)
        except Exception as exc:
            logger.warning("[interrupt] Failed to send agent.interrupt: %s", exc)
            entry.invalidate(f"interrupt WS error: {exc}")
    else:
        logger.debug("[interrupt] No active WebSocket for user %s — flag set only", sid)
    return {"status": "interrupted"}


@app.get("/session", summary="Get a LiveAvatar WebRTC session")
async def get_session(x_session_id: str = Header(default="anonymous")) -> dict[str, Any]:
    """
    Returns LiveKit credentials for the caller's per-user avatar session.
    Falls back to a mock session for local development when LIVEAVATAR_API_KEY is not set.

    Security: target hostnames are hard-coded constants — never derived from
    user input, preventing Server-Side Request Forgery (SSRF).
    """
    if not LIVEAVATAR_API_KEY:
        logger.warning("/session called without LIVEAVATAR_API_KEY — returning mock session")
        return {"session_id": "mock-session-id", "livekit_url": "", "livekit_client_token": "mock-token"}

    try:
        sid = x_session_id if UUID_RE.match(x_session_id) else "anonymous"
        entry = await avatar_module.get_or_create_user_session(sid)
        return await avatar_module.get_or_create_liveavatar_session(entry)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            entry.invalidate(f"HTTP {exc.response.status_code} from LiveAvatar")  # type: ignore[possibly-undefined]
        logger.error("LiveAvatar API returned %d: %s", exc.response.status_code, exc.response.text[:200])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LiveAvatar API returned status {exc.response.status_code}.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Unable to reach LiveAvatar API (%s): %s", type(exc).__name__, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach the LiveAvatar API ({type(exc).__name__}). Check network connectivity.",
        ) from exc


@app.delete("/session", summary="Stop the LiveAvatar session and release server resources")
async def delete_session(
    x_session_id: str = Header(default="anonymous"),
) -> dict[str, str]:
    """Called by the frontend on page unload to immediately release server-side resources."""
    sid = x_session_id if UUID_RE.match(x_session_id) else "anonymous"
    entry = await avatar_module.pop_user_session(sid)
    if entry is None:
        return {"status": "no-session"}
    if entry.ws_task and not entry.ws_task.done():
        entry.ws_task.cancel()
    entry.invalidate("client disconnect", stop_remote=True)
    logger.info("[session] Deleted by client: %s", sid)
    return {"status": "stopped"}


# ---------------------------------------------------------------------------
# Routes — Utility
# ---------------------------------------------------------------------------

@app.get("/ping", summary="Lightweight liveness probe / warmup endpoint")
async def ping() -> dict[str, str]:
    """Returns immediately — used by the frontend to wake a cold-started container."""
    return {"status": "ok"}


@app.get("/health", response_model=HealthResponse, summary="Health check")
async def health() -> HealthResponse:
    """Checks connectivity to Ollama and Qdrant and reports RAG chain status."""
    ollama_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
        ollama_status = "connected" if r.status_code == 200 else f"error:{r.status_code}"
    except Exception:
        ollama_status = "unreachable"

    qdrant_status = (
        QDRANT_CLOUD_URL if QDRANT_MODE == "cloud"
        else ("in-memory" if QDRANT_MODE == "memory" else QDRANT_URL)
    )
    llm_ok = (
        ollama_status == "connected" if LLM_PROVIDER == "ollama"
        else f"azure_openai:{AZURE_OPENAI_CHAT_DEPLOYMENT}"
    )
    overall = "healthy" if (
        _rag_chain is not None and (LLM_PROVIDER != "ollama" or ollama_status == "connected")
    ) else "degraded"

    return HealthResponse(
        status=overall,
        ollama=str(llm_ok),
        qdrant=qdrant_status,
        rag_chain="initialized" if _rag_chain else "failed",
    )
