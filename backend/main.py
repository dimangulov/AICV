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
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
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
async def ask(payload: AskRequest) -> AskResponse:
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
# LiveAvatar session cache
# A single avatar session is shared across all visitors and reused until it
# expires or the server restarts.  The cache is invalidated on 401/403 so a
# fresh session is transparently obtained on the next request.
# ---------------------------------------------------------------------------
_liveavatar_session: dict[str, Any] | None = None
_liveavatar_session_expires: float = 0.0          # monotonic time
_liveavatar_session_lock: asyncio.Lock = asyncio.Lock()
_LIVEAVATAR_SESSION_TTL: float = 1800.0           # 30 min conservative TTL


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
        }
        _liveavatar_session = result
        _liveavatar_session_expires = now + _LIVEAVATAR_SESSION_TTL
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
            global _liveavatar_session, _liveavatar_session_expires
            _liveavatar_session = None
            _liveavatar_session_expires = 0.0
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
