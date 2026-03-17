"""
Text-to-Speech helpers.

Provides:
  - A module-level persistent httpx.AsyncClient (_http_client) that main.py
    initialises in lifespan and other modules import for any outbound HTTP.
  - _stream_tts_azure()  — async generator yielding raw PCM chunks as they arrive
  - _synthesize_pcm_azure() — collects the full stream (for filler pre-caching)
  - _synthesize_pcm_gtts() — gTTS MP3 → PCM fallback (local dev)
  - synthesize_pcm()      — public dispatcher (Azure → gTTS → error)
  - _mp3_to_pcm()         — miniaudio MP3 decoder helper
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import miniaudio

try:
    from gtts import gTTS as _gTTS
    _GTTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _GTTS_AVAILABLE = False

from config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, LIVEAVATAR_VOICE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persistent HTTP client — set by lifespan in main.py at startup.
# Using a module-level client avoids per-call TCP+TLS connection setup overhead.
# ---------------------------------------------------------------------------
http_client: httpx.AsyncClient | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mp3_to_pcm(mp3_bytes: bytes) -> bytes:
    """Decode MP3 to raw PCM (16-bit signed LE, mono, 24 kHz) via miniaudio."""
    decoded = miniaudio.mp3_read_s16(mp3_bytes, want_nchannels=1, want_sample_rate=24000)
    return bytes(decoded.samples)


async def _stream_tts_azure(text: str):
    """
    Stream raw PCM (16-bit signed, mono, 24 kHz) from Azure Cognitive Services
    Speech TTS.  Yields byte chunks as they arrive from the HTTP response so
    callers can start forwarding audio before the full synthesis completes.
    """
    ssml = (
        f"<speak version='1.0' xml:lang='en-US'>"
        f"<voice name='{LIVEAVATAR_VOICE}'>{text}</voice>"
        f"</speak>"
    )
    url = f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "raw-24khz-16bit-mono-pcm",
        "User-Agent": "aicv-backend",
    }
    client = http_client
    if client is not None:
        async with client.stream("POST", url, headers=headers, content=ssml.encode()) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(48_000):
                yield chunk
    else:
        async with httpx.AsyncClient(timeout=30.0) as tmp:
            async with tmp.stream("POST", url, headers=headers, content=ssml.encode()) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(48_000):
                    yield chunk


async def _synthesize_pcm_azure(text: str) -> bytes:
    """
    Azure Cognitive Services Speech TTS → raw PCM (accumulates full stream).
    Used for filler pre-synthesis cache.  Live speech uses _stream_tts_azure.
    """
    chunks: list[bytes] = []
    async for chunk in _stream_tts_azure(text):
        chunks.append(chunk)
    return b"".join(chunks)


async def _synthesize_pcm_gtts(text: str) -> bytes:
    """
    Google TTS fallback → MP3 → PCM.
    Used when AZURE_SPEECH_KEY is not configured (local dev).
    """
    import io
    loop = asyncio.get_event_loop()
    buf = io.BytesIO()

    def _synth() -> None:
        _gTTS(text=text, lang="en").write_to_fp(buf)
        buf.seek(0)

    await loop.run_in_executor(None, _synth)
    return _mp3_to_pcm(buf.read())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def synthesize_pcm(text: str) -> bytes:
    """
    Convert text to raw PCM bytes (16-bit signed, mono, 24 kHz).
    Uses Azure Cognitive Services Speech when AZURE_SPEECH_KEY is set,
    otherwise falls back to gTTS (Google TTS) for local development.
    """
    if AZURE_SPEECH_KEY:
        logger.debug("[tts] Using Azure Speech (region=%s, voice=%s)", AZURE_SPEECH_REGION, LIVEAVATAR_VOICE)
        return await _synthesize_pcm_azure(text)

    if _GTTS_AVAILABLE:
        logger.debug("[tts] AZURE_SPEECH_KEY not set — using gTTS fallback")
        return await _synthesize_pcm_gtts(text)

    raise RuntimeError(
        "No TTS backend available. Set AZURE_SPEECH_KEY or install gTTS."
    )


# Expose for avatar.py (filler warmup checks this flag)
gtts_available: bool = _GTTS_AVAILABLE
