"""
Centralised configuration — all values sourced from environment variables.
Import from here; never call os.getenv() in other modules.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

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
# LLM / Embeddings provider
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Qdrant vector database
# ---------------------------------------------------------------------------
QDRANT_MODE: str = os.getenv("QDRANT_MODE", "memory")
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_CLOUD_URL: str = os.getenv("QDRANT_CLOUD_URL", "")
QDRANT_CLOUD_API_KEY: str = os.getenv("QDRANT_CLOUD_API_KEY", "")
COLLECTION_NAME: str = "cv_knowledge_base"

# ---------------------------------------------------------------------------
# LiveAvatar
# ---------------------------------------------------------------------------
# Fixed URL — never derived from user input to prevent SSRF
LIVEAVATAR_BASE_URL: str = "https://api.liveavatar.com"
LIVEAVATAR_API_KEY: str = os.getenv("LIVEAVATAR_API_KEY", "")
LIVEAVATAR_AVATAR_ID: str = os.getenv("LIVEAVATAR_AVATAR_ID", "default")
LIVEAVATAR_SESSION_MODE: str = os.getenv("LIVEAVATAR_SESSION_MODE", "LITE")
LIVEAVATAR_IS_SANDBOX: bool = os.getenv("LIVEAVATAR_IS_SANDBOX", "false").lower() == "true"
LIVEAVATAR_VOICE: str = os.getenv("LIVEAVATAR_VOICE", "en-US-AndrewMultilingualNeural")
ENABLE_FILLERS: bool = os.getenv("ENABLE_FILLERS", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Azure Cognitive Services Speech (TTS)
# ---------------------------------------------------------------------------
AZURE_SPEECH_KEY: str = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION: str = os.getenv("AZURE_SPEECH_REGION", "westeurope")

# ---------------------------------------------------------------------------
# App / server
# ---------------------------------------------------------------------------
BIO_FILE_PATH: Path = Path(__file__).parent / "bio.txt"

ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

MAX_SESSIONS: int = int(os.getenv("MAX_SESSIONS", "50"))
SESSION_IDLE_TTL: float = 120.0  # evict sessions idle > 2 min

# Validates X-Session-ID header — must be UUID v4 format
UUID_RE: re.Pattern[str] = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
