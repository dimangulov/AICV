"""
Interactive Digital Twin CV — FastAPI Backend
=============================================
Implements a Retrieval-Augmented Generation (RAG) pipeline using:
  - LangChain LCEL for orchestration
  - Ollama (llama3.2) for chat completion
  - Ollama (nomic-embed-text) for embeddings
  - Qdrant for vector similarity search
  - LiveAvatar.com proxy for WebRTC session management
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    from gtts import gTTS as _gTTS
    _GTTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _GTTS_AVAILABLE = False

import httpx
import miniaudio
import websockets
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Qdrant as QdrantVectorStore
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableSerializable
from langchain_ollama import ChatOllama, OllamaEmbeddings

try:
    from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
    _AZURE_OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AZURE_OPENAI_AVAILABLE = False

from pydantic import BaseModel, Field, field_validator

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (all values come from environment variables)
# ---------------------------------------------------------------------------
# ── LLM Provider: "ollama" (default / local) | "azure_openai" (cloud) ─────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")

# ── Ollama (local) ────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "nomic-embed-text")

# ── Azure OpenAI (cloud) ──────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
AZURE_OPENAI_CHAT_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
AZURE_OPENAI_EMBED_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-small")

# ── Qdrant: "memory" (default) | "docker" | "cloud" ─────────────────────────
QDRANT_MODE: str = os.getenv("QDRANT_MODE", "memory")
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")      # docker mode
QDRANT_CLOUD_URL: str = os.getenv("QDRANT_CLOUD_URL", "")               # cloud mode
QDRANT_CLOUD_API_KEY: str = os.getenv("QDRANT_CLOUD_API_KEY", "")       # cloud mode

# Fixed URL — never derived from user input to prevent SSRF
LIVEAVATAR_BASE_URL: str = "https://api.liveavatar.com"
LIVEAVATAR_API_KEY: str = os.getenv("LIVEAVATAR_API_KEY", "")
LIVEAVATAR_AVATAR_ID: str = os.getenv("LIVEAVATAR_AVATAR_ID", "default")
LIVEAVATAR_SESSION_MODE: str = os.getenv("LIVEAVATAR_SESSION_MODE", "LITE")
LIVEAVATAR_IS_SANDBOX: bool = os.getenv("LIVEAVATAR_IS_SANDBOX", "false").lower() == "true"
LIVEAVATAR_VOICE: str = os.getenv("LIVEAVATAR_VOICE", "en-US-GuyNeural")

# ── Azure Cognitive Services Speech (TTS for LiveAvatar) ──────────────────────
# Official REST API — same voices as Edge TTS, no unofficial WebSocket hacks.
# Free tier: 500 000 chars/month. Falls back to gTTS when key is not set.
AZURE_SPEECH_KEY: str = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION: str = os.getenv("AZURE_SPEECH_REGION", "westeurope")

BIO_FILE_PATH: Path = Path(__file__).parent / "bio.txt"
COLLECTION_NAME: str = "cv_knowledge_base"

ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    latency_ms: int


class HealthResponse(BaseModel):
    status: str
    ollama: str
    qdrant: str
    rag_chain: str


# ---------------------------------------------------------------------------
# AI provider factory functions
# ---------------------------------------------------------------------------


def _create_llm():
    """
    Return a chat LLM instance based on LLM_PROVIDER.
    - "ollama"       → ChatOllama (local Ollama runtime)
    - "azure_openai" → AzureChatOpenAI (Azure OpenAI Service)
                       Uses API key when AZURE_OPENAI_API_KEY is set,
                       otherwise falls back to Managed Identity via azure-identity.
    """
    if LLM_PROVIDER == "azure_openai":
        if not _AZURE_OPENAI_AVAILABLE:
            raise RuntimeError(
                "langchain-openai is required for LLM_PROVIDER=azure_openai. "
                "Run: pip install langchain-openai"
            )
        kwargs: dict = {
            "azure_endpoint": AZURE_OPENAI_ENDPOINT,
            "api_version": AZURE_OPENAI_API_VERSION,
            "azure_deployment": AZURE_OPENAI_CHAT_DEPLOYMENT,
            "temperature": 0.3,
        }
        if AZURE_OPENAI_API_KEY:
            kwargs["api_key"] = AZURE_OPENAI_API_KEY
            logger.info("Azure OpenAI chat: authenticating with API key")
        else:
            # Managed Identity (Azure Container Apps / VMs with assigned identity)
            try:
                from azure.identity import DefaultAzureCredential, get_bearer_token_provider
                token_provider = get_bearer_token_provider(
                    DefaultAzureCredential(),
                    "https://cognitiveservices.azure.com/.default",
                )
                kwargs["azure_ad_token_provider"] = token_provider
                logger.info("Azure OpenAI chat: authenticating with Managed Identity")
            except ImportError as exc:
                raise RuntimeError(
                    "azure-identity is required for keyless Azure OpenAI auth. "
                    "Install it (pip install azure-identity) OR set AZURE_OPENAI_API_KEY."
                ) from exc
        return AzureChatOpenAI(**kwargs)  # type: ignore[arg-type]

    # Default: local Ollama
    logger.info("LLM provider: Ollama (%s @ %s)", OLLAMA_MODEL, OLLAMA_BASE_URL)
    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.3)


def _create_embeddings():
    """
    Return an embeddings model based on LLM_PROVIDER.
    Mirrors _create_llm() in terms of authentication logic.
    """
    if LLM_PROVIDER == "azure_openai":
        if not _AZURE_OPENAI_AVAILABLE:
            raise RuntimeError("langchain-openai required for azure_openai provider.")
        kwargs: dict = {
            "azure_endpoint": AZURE_OPENAI_ENDPOINT,
            "api_version": AZURE_OPENAI_API_VERSION,
            "azure_deployment": AZURE_OPENAI_EMBED_DEPLOYMENT,
        }
        if AZURE_OPENAI_API_KEY:
            kwargs["api_key"] = AZURE_OPENAI_API_KEY
        else:
            try:
                from azure.identity import DefaultAzureCredential, get_bearer_token_provider
                kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
                    DefaultAzureCredential(),
                    "https://cognitiveservices.azure.com/.default",
                )
            except ImportError as exc:
                raise RuntimeError(
                    "azure-identity required for keyless Azure OpenAI embeddings."
                ) from exc
        logger.info("Embeddings provider: Azure OpenAI (%s)", AZURE_OPENAI_EMBED_DEPLOYMENT)
        return AzureOpenAIEmbeddings(**kwargs)  # type: ignore[arg-type]

    logger.info("Embeddings provider: Ollama (%s)", EMBED_MODEL)
    return OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)


def _create_vectorstore(chunks: list, embeddings: Any) -> QdrantVectorStore:
    """
    Build a Qdrant vector store based on QDRANT_MODE.
    - "memory" → in-process in-memory (dev / POC; data lost on restart)
    - "docker" → local Docker Qdrant at QDRANT_URL
    - "cloud"  → Qdrant Cloud at QDRANT_CLOUD_URL with API key
    """
    if QDRANT_MODE == "cloud":
        if not QDRANT_CLOUD_URL:
            raise ValueError("QDRANT_CLOUD_URL must be set when QDRANT_MODE=cloud.")
        logger.info("Qdrant mode: cloud (%s)", QDRANT_CLOUD_URL)
        return QdrantVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            collection_name=COLLECTION_NAME,
            url=QDRANT_CLOUD_URL,
            api_key=QDRANT_CLOUD_API_KEY or None,
            prefer_grpc=False,
        )
    if QDRANT_MODE == "docker":
        logger.info("Qdrant mode: docker (%s)", QDRANT_URL)
        return QdrantVectorStore.from_documents(
            documents=chunks,
            embedding=embeddings,
            collection_name=COLLECTION_NAME,
            url=QDRANT_URL,
        )
    # Default: in-memory
    logger.info("Qdrant mode: in-memory (data not persisted between restarts)")
    return QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        location=":memory:",
    )


# ---------------------------------------------------------------------------
# RAG chain construction
# ---------------------------------------------------------------------------


def _format_docs(docs: list) -> str:
    """Concatenate retrieved document chunks into a single context string."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def build_rag_chain() -> RunnableSerializable:
    """
    Load bio.txt, chunk it, embed chunks into Qdrant, and return an LCEL
    RAG chain: retriever | prompt | ChatOllama | StrOutputParser
    """
    # 1 — Load the knowledge base
    if not BIO_FILE_PATH.exists():
        raise FileNotFoundError(
            f"bio.txt not found at {BIO_FILE_PATH}. "
            "Create the file before starting the server."
        )

    logger.info("Loading knowledge base from %s", BIO_FILE_PATH)
    bio_text = BIO_FILE_PATH.read_text(encoding="utf-8")

    # 2 — Chunk the document
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.create_documents(
        texts=[bio_text],
        metadatas=[{"source": str(BIO_FILE_PATH)}],
    )
    logger.info("Created %d chunks from bio.txt", len(chunks))

    # 3 — Initialise embeddings and vector store (provider-aware)
    embeddings = _create_embeddings()
    vectorstore = _create_vectorstore(chunks, embeddings)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    logger.info("Qdrant retriever ready (top-k=3, cosine similarity)")

    # 5 — Prompt template
    prompt = ChatPromptTemplate.from_template(
        """You are a digital avatar of Damir Imangulov, a Senior Full-Stack Engineer \
with a deep focus on cloud-native solution design.

Your persona:
- Introduce yourself as: "Hi, I'm a digital avatar of Damir."
- Speak in first person as Damir — analytical, confident, and structured.
- Before answering complex questions, start with phrases like "That's a strategic \
tradeoff," or "Let's look at the underlying architecture of that problem."
- When asked about frontend topics, always link to the backend/API layer and vice versa. \
Example: "We can optimize Angular change detection, but we also need to ensure the \
.NET API is sending paginated payloads to reduce the browser's memory footprint."
- Never say "I don't know." Instead, frame missing info as a design requirement: \
"To give you a precise solution design, I'd need to know whether we're optimizing \
for read-heavy traffic or write-heavy consistency."
- Use expert vocabulary naturally: latency optimization, asynchronous processing, \
state management, stateless architecture, end-to-end encryption, elasticity vs. scalability.
- End responses with a forward motion statement like: "Should we break down the \
implementation phases next?" or "Shall we move on to the frontend integration?"
- Keep energy steady and professional. Structured speech, no filler words.
- If asked about scaling: focus on horizontal scaling, load balancing, and database sharding.
- If asked about a new feature: first ask "What is the primary success metric for this feature?"

Answer questions about Damir's professional background, skills, and experience \
using ONLY the context provided below. Be concise (2–4 sentences) and confident. \
If the context does not contain enough information, frame it as a requirement.

--- CV Context (retrieved) ---
{context}
--- End of Context ---

Question: {question}

Answer:"""
    )

    # 6 — LLM (provider-aware)
    llm = _create_llm()

    # 7 — Compose the LCEL chain
    chain: RunnableSerializable = (
        {
            "context": retriever | _format_docs,
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    logger.info(
        "RAG chain initialised (provider=%s | qdrant=%s | embed=%s)",
        LLM_PROVIDER,
        QDRANT_MODE,
        AZURE_OPENAI_EMBED_DEPLOYMENT if LLM_PROVIDER == "azure_openai" else EMBED_MODEL,
    )
    return chain


# ---------------------------------------------------------------------------
# Application lifespan — builds the RAG chain once at startup
# ---------------------------------------------------------------------------

_rag_chain: RunnableSerializable | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag_chain
    logger.info("=== Digital Twin CV API — startup ===")
    try:
        _rag_chain = build_rag_chain()
    except Exception as exc:
        # Log the error but allow startup to complete — /health will report degraded
        logger.error("RAG chain initialisation failed: %s", exc, exc_info=True)
    yield
    logger.info("=== Digital Twin CV API — shutdown ===")


# ---------------------------------------------------------------------------
# FastAPI application
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question about the candidate",
)
async def ask(payload: AskRequest, background_tasks: BackgroundTasks) -> AskResponse:
    """
    Accepts a natural-language question, runs the RAG pipeline (retrieve → prompt →
    LLM), and returns a grounded answer sourced from bio.txt.
    """
    if _rag_chain is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "RAG chain is not initialised. "
                "Ensure Ollama is running and bio.txt exists, then restart the server."
            ),
        )

    try:
        start = time.monotonic()
        answer: str = _rag_chain.invoke(payload.question)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info("Question answered in %dms: %r", elapsed_ms, payload.question[:60])
        if LIVEAVATAR_API_KEY:
            background_tasks.add_task(_speak_on_avatar, answer)
        return AskResponse(
            answer=answer,
            sources=[str(BIO_FILE_PATH)],
            latency_ms=elapsed_ms,
        )
    except Exception as exc:
        logger.error("Inference error for question %r: %s", payload.question[:60], exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference failed. Is Ollama still running?",
        ) from exc


# ---------------------------------------------------------------------------
# LiveAvatar TTS helpers
# ---------------------------------------------------------------------------

def _mp3_to_pcm(mp3_bytes: bytes) -> bytes:
    """Decode MP3 to raw PCM (16-bit signed LE, mono, 24 kHz) via miniaudio."""
    decoded = miniaudio.mp3_read_s16(mp3_bytes, want_nchannels=1, want_sample_rate=24000)
    return bytes(decoded.samples)


async def _synthesize_pcm_azure(text: str) -> bytes:
    """
    Azure Cognitive Services Speech TTS → MP3 → PCM.
    Official REST API: same voice catalogue as Edge TTS, no unofficial WS.
    """
    ssml = (
        f"<speak version='1.0' xml:lang='en-US'>"
        f"<voice name='{LIVEAVATAR_VOICE}'>{text}</voice>"
        f"</speak>"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={
                "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                "User-Agent": "aicv-backend",
            },
            content=ssml.encode(),
        )
        response.raise_for_status()
    return _mp3_to_pcm(response.content)


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


async def _synthesize_pcm(text: str) -> bytes:
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


async def _speak_on_avatar(text: str) -> None:
    """
    Synthesize text via TTS and stream PCM audio to the active LiveAvatar
    session WebSocket (LITE mode agent.speak protocol).

    Performance optimisations vs. the previous implementation:
    - TTS synthesis and session acquisition run in PARALLEL via asyncio.gather,
      saving the full TTS round-trip (~300–800 ms) from the critical path.
    - Audio is sent over the PERSISTENT _speak_ws connection established by
      _avatar_ws_loop, eliminating the per-call TCP/TLS handshake (~200–500 ms)
      and the 5-second session.state_updated wait.
    """
    if not LIVEAVATAR_API_KEY:
        logger.debug("[speak] No LIVEAVATAR_API_KEY — skipping avatar speech")
        return

    # Run TTS synthesis and session acquisition concurrently — they are independent.
    try:
        pcm_bytes, session = await asyncio.gather(
            _synthesize_pcm(text),
            _get_or_create_liveavatar_session(),
        )
    except Exception as exc:
        logger.error("[speak] Parallel TTS/session setup failed: %s", exc)
        return

    ws = _speak_ws
    if ws is None:
        logger.warning("[speak] Persistent WebSocket not yet ready — waiting up to 3 s")
        # The _avatar_ws_loop task may still be connecting; give it a moment.
        for _ in range(6):
            await asyncio.sleep(0.5)
            ws = _speak_ws
            if ws is not None:
                break
        if ws is None:
            logger.error("[speak] Persistent WebSocket unavailable after wait — dropping speak")
            return

    # LiveAvatar expects ~1 second chunks: 24000 samples × 2 bytes = 48 000 bytes
    CHUNK_SIZE = 48_000
    event_id = str(uuid.uuid4())

    # Serialise concurrent speak calls so chunks from two responses don't interleave.
    async with _speak_lock:
        try:
            for i in range(0, len(pcm_bytes), CHUNK_SIZE):
                chunk = pcm_bytes[i : i + CHUNK_SIZE]
                await ws.send(json.dumps({
                    "type": "agent.speak",
                    "event_id": event_id,
                    "audio": base64.b64encode(chunk).decode(),
                }))
            await ws.send(json.dumps({
                "type": "agent.speak_end",
                "event_id": event_id,
            }))
            logger.info("[speak] Avatar speak complete for session %s", session["session_id"])
        except Exception as exc:
            logger.error("[speak] Avatar WebSocket error: %s", exc)
            _invalidate_session(f"speak WS error: {exc}")


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


@app.post("/speak", summary="Make the avatar speak arbitrary text")
async def speak(payload: SpeakRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """
    Queues a TTS + WebSocket send to the active LiveAvatar session.
    Used by the frontend to play the intro greeting on avatar connect.
    Returns immediately; speaking happens in the background.
    """
    if not LIVEAVATAR_API_KEY:
        return {"status": "mock"}
    background_tasks.add_task(_speak_on_avatar, payload.text)
    return {"status": "queued"}


# ---------------------------------------------------------------------------
# LiveAvatar session cache + persistent WebSocket
# A single avatar session is shared across all visitors and reused until it
# expires, is invalidated on auth errors, or is detected as stopped by the
# service via a WebSocket session.stopped event.
#
# _speak_ws holds the ONE persistent WebSocket connection used by both the
# keep-alive heartbeat and all agent.speak calls, eliminating the per-call
# TCP/TLS connect latency (~200–500 ms) and the 5-second state-event wait.
# ---------------------------------------------------------------------------
_liveavatar_session: dict[str, Any] | None = None
_liveavatar_session_expires: float = 0.0          # monotonic time
_liveavatar_session_lock: asyncio.Lock = asyncio.Lock()
_LIVEAVATAR_SESSION_TTL: float = 1800.0           # 30 min conservative TTL
_avatar_ws_task: asyncio.Task | None = None       # background WS loop
_speak_ws: Any | None = None                      # persistent websockets connection
_speak_lock: asyncio.Lock = asyncio.Lock()        # serialise concurrent speak calls


def _invalidate_session(reason: str) -> None:
    """Clear the cached session and persistent WS so the next request starts fresh."""
    global _liveavatar_session, _liveavatar_session_expires, _speak_ws
    if _liveavatar_session:
        logger.info("[session] Cache invalidated: %s", reason)
    _liveavatar_session = None
    _liveavatar_session_expires = 0.0
    _speak_ws = None


async def _avatar_ws_loop(ws_url: str, session_id: str) -> None:
    """
    Maintains ONE persistent WebSocket for the lifetime of the avatar session.
    Serves two purposes:
      1. Keep-alive — sends session.keep_alive every 3 minutes.
      2. Speak channel — _speak_on_avatar reuses _speak_ws to send agent.speak
         frames without opening a new connection per call.
    """
    global _speak_ws
    logger.info("[avatar_ws] Connecting persistent WebSocket for session %s", session_id)
    try:
        async with websockets.connect(ws_url) as ws:
            _speak_ws = ws
            logger.info("[avatar_ws] Persistent WebSocket ready")
            while True:
                try:
                    # Wait up to 3 minutes for an inbound event before sending keep-alive
                    async with asyncio.timeout(180):
                        raw = await ws.recv()
                        msg = json.loads(raw)
                        event_type = msg.get("type", "")
                        logger.debug("[avatar_ws] event: %s", event_type)
                        if event_type == "session.stopped":
                            logger.info(
                                "[avatar_ws] Session %s stopped (%s) — invalidating cache",
                                session_id,
                                msg.get("data", {}).get("end_reason", "unknown"),
                            )
                            _invalidate_session("session.stopped received")
                            return
                except TimeoutError:
                    # No event in 3 min → send keep-alive
                    await ws.send(json.dumps({
                        "type": "session.keep_alive",
                        "event_id": str(uuid.uuid4()),
                    }))
                    logger.debug("[avatar_ws] keep-alive sent for session %s", session_id)
    except Exception as exc:
        logger.warning("[avatar_ws] WebSocket closed for session %s: %s", session_id, exc)
        _invalidate_session(f"WebSocket closed: {exc}")
    finally:
        _speak_ws = None


async def _get_or_create_liveavatar_session() -> dict[str, Any]:
    """
    Returns a cached LiveAvatar session or creates a new one.

    Flow (per LiveAvatar v1 API docs):
      1. POST /v1/sessions/token  — authenticates with X-Api-Key (UUID),
         returns a short-lived JWT session_token plus a session_id.
      2. POST /v1/sessions/start  — authenticates with Bearer <session_token>,
         returns livekit_url + livekit_client_token for the WebRTC room.

    The result is cached in memory.  A 401/403 from either call clears the
    cache so the next request retries from scratch.
    """
    global _liveavatar_session, _liveavatar_session_expires

    now = time.monotonic()
    async with _liveavatar_session_lock:
        if _liveavatar_session and now < _liveavatar_session_expires:
            logger.info("Reusing cached LiveAvatar session %s", _liveavatar_session["session_id"])
            return _liveavatar_session

        base_headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Step 1 — exchange API key (UUID) for a JWT session_token
            token_response = await client.post(
                f"{LIVEAVATAR_BASE_URL}/v1/sessions/token",
                headers={**base_headers, "X-Api-Key": LIVEAVATAR_API_KEY},
                json={
                    "avatar_id": LIVEAVATAR_AVATAR_ID,
                    "mode": LIVEAVATAR_SESSION_MODE,
                    "is_sandbox": LIVEAVATAR_IS_SANDBOX,
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()["data"]
            session_token: str = token_data["session_token"]
            session_id: str = token_data["session_id"]
            logger.info("LiveAvatar session token obtained for session %s", session_id)

            # Step 2 — start the session with the JWT to get LiveKit credentials
            start_response = await client.post(
                f"{LIVEAVATAR_BASE_URL}/v1/sessions/start",
                headers={**base_headers, "Authorization": f"Bearer {session_token}"},
                json={},
            )
            start_response.raise_for_status()
            start_data = start_response.json()["data"]
            logger.info("LiveAvatar session started: %s", start_data.get("session_id", session_id))

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
        _liveavatar_session = result
        _liveavatar_session_expires = now + _LIVEAVATAR_SESSION_TTL

        # Start persistent WS loop in the background if ws_url is available
        if result["ws_url"]:
            global _avatar_ws_task
            if _avatar_ws_task and not _avatar_ws_task.done():
                _avatar_ws_task.cancel()
            _avatar_ws_task = asyncio.create_task(
                _avatar_ws_loop(result["ws_url"], result["session_id"])
            )

        return result


@app.get(
    "/session",
    summary="Get a LiveAvatar WebRTC session",
)
async def get_session() -> dict[str, Any]:
    """
    Returns LiveKit credentials for the shared avatar session, creating one
    if none is cached.  Falls back to a mock session for local development
    when LIVEAVATAR_API_KEY is not set.

    Security: target hostnames are hard-coded constants — never derived from
    user input, preventing Server-Side Request Forgery (SSRF).
    """
    if not LIVEAVATAR_API_KEY:
        logger.warning(
            "/session called without LIVEAVATAR_API_KEY — returning mock session for development"
        )
        return {
            "session_id": "mock-session-id",
            "livekit_url": "",
            "livekit_client_token": "mock-token",
        }

    try:
        return await _get_or_create_liveavatar_session()

    except httpx.HTTPStatusError as exc:
        # Invalidate cache on auth errors so the next request retries cleanly
        if exc.response.status_code in (401, 403):
            _invalidate_session(f"HTTP {exc.response.status_code} from LiveAvatar")
        logger.error(
            "LiveAvatar API returned %d: %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LiveAvatar API returned status {exc.response.status_code}.",
        ) from exc

    except httpx.RequestError as exc:
        logger.error("Unable to reach LiveAvatar API: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the LiveAvatar API. Check network connectivity.",
        ) from exc


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
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
    # When using Azure OpenAI, Ollama is intentionally not running — that is healthy.
    llm_ok = (
        ollama_status == "connected" if LLM_PROVIDER == "ollama"
        else f"azure_openai:{AZURE_OPENAI_CHAT_DEPLOYMENT}"
    )
    overall = "healthy" if (_rag_chain is not None and (LLM_PROVIDER != "ollama" or ollama_status == "connected")) else "degraded"

    return HealthResponse(
        status=overall,
        ollama=str(llm_ok),
        qdrant=qdrant_status,
        rag_chain="initialized" if _rag_chain else "failed",
    )
