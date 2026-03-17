"""
RAG pipeline: LLM / embeddings factory functions, Qdrant vector store setup,
and the LangChain LCEL chain that powers /ask and /ask/stream.
"""

from __future__ import annotations

import logging
from operator import itemgetter
from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Qdrant as QdrantVectorStore
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSerializable
from langchain_ollama import ChatOllama, OllamaEmbeddings

try:
    from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
    _AZURE_OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AZURE_OPENAI_AVAILABLE = False

from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_CHAT_DEPLOYMENT,
    AZURE_OPENAI_EMBED_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    BIO_FILE_PATH,
    COLLECTION_NAME,
    EMBED_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    QDRANT_CLOUD_API_KEY,
    QDRANT_CLOUD_URL,
    QDRANT_MODE,
    QDRANT_URL,
)
from models import HistoryMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AI provider factories
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
    logger.info("Qdrant mode: in-memory (data not persisted between restarts)")
    return QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        location=":memory:",
    )


# ---------------------------------------------------------------------------
# Chain helpers
# ---------------------------------------------------------------------------


def _format_docs(docs: list) -> str:
    """Concatenate retrieved document chunks into a single context string."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def format_history(history: list[HistoryMessage]) -> str:
    """Format conversation history into a prompt block. Returns empty string if no history."""
    if not history:
        return ""
    lines = ["--- Conversation History ---"]
    for msg in history:
        prefix = "Human" if msg.role == "user" else "Assistant"
        lines.append(f"{prefix}: {msg.content}")
    lines.append("--- End of History ---\n")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Chain builder — called once at startup
# ---------------------------------------------------------------------------


def build_rag_chain() -> RunnableSerializable:
    """
    Load bio.txt, chunk it, embed chunks into Qdrant, and return an LCEL
    RAG chain: retriever | prompt | LLM | StrOutputParser
    """
    if not BIO_FILE_PATH.exists():
        raise FileNotFoundError(
            f"bio.txt not found at {BIO_FILE_PATH}. "
            "Create the file before starting the server."
        )

    logger.info("Loading knowledge base from %s", BIO_FILE_PATH)
    bio_text = BIO_FILE_PATH.read_text(encoding="utf-8")

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

    embeddings = _create_embeddings()
    vectorstore = _create_vectorstore(chunks, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    logger.info("Qdrant retriever ready (top-k=3, cosine similarity)")

    prompt = ChatPromptTemplate.from_template(
        """You are a digital avatar of Damir Imangulov, a Senior Full-Stack Engineer \
and Solution Architect with a deep focus on cloud-native systems.

Your persona:
- Introduce yourself as: "Hi, I'm a digital avatar of Damir."
- Speak in first person as Damir — analytical, confident, and structured.
- When contextually relevant, connect frontend concerns to backend/API considerations \
and vice versa.
- Never say "I don't know." Instead, frame missing info as a design requirement: \
"To give you a precise solution, I'd need to know whether we're optimising for \
read-heavy traffic or write-heavy consistency."
- Use expert vocabulary naturally: latency optimisation, asynchronous processing, \
state management, stateless architecture, end-to-end encryption, elasticity vs. scalability.
- Occasionally close with a forward-motion prompt like: "Want me to walk through the \
implementation phases?" or "Shall we dig into the frontend integration?"
- Keep energy steady and professional — no filler words, no repeated openers.
- If asked about scaling: focus on horizontal scaling, load balancing, and database sharding.

Answer questions about Damir's professional background, skills, and experience \
using ONLY the context provided below. Be concise (2–4 sentences) and confident. \
If the context does not contain enough information, frame it as a requirement.

--- CV Context (retrieved) ---
{context}
--- End of Context ---

{history}Question: {question}

Answer:"""
    )

    llm = _create_llm()

    chain: RunnableSerializable = (
        {
            "context": itemgetter("question") | retriever | _format_docs,
            "question": itemgetter("question"),
            "history": itemgetter("history"),
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
