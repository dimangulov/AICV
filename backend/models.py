"""
Pydantic request / response models used across the API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class HistoryMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10_000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=12)

    @field_validator("question")
    @classmethod
    def strip_and_truncate(cls, v: str) -> str:
        v = v.strip()
        return v[:500] if len(v) > 500 else v


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    latency_ms: int


class HealthResponse(BaseModel):
    status: str
    ollama: str
    qdrant: str
    rag_chain: str


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
