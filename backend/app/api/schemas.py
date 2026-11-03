"""Pydantic schemas for request validation and response models."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class SourceInput(BaseModel):
    id: str | None = None
    text: str
    title: str | None = None
    url: str | None = None


class VerifierConfigInput(BaseModel):
    verifier_type: Literal["rule_based", "mock", "llm"] = "rule_based"
    max_concurrency: int = Field(default=4, ge=1, le=20)
    mock_responses: list[str] | None = None
    # LLM verifier options (only used when verifier_type == "llm")
    provider_id: str | None = Field(default=None, description="Provider ID: gemini, groq, openrouter, ollama")
    model_id: str | None = Field(default=None, description="Override the configured model for this request")


class EvaluationCreateRequest(BaseModel):
    question: str
    answer: str
    sources: list[SourceInput]
    config: VerifierConfigInput | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


class ProviderItem(BaseModel):
    provider: str
    configured: bool
    key_preview: str | None = None
    model: str | None = None
    adapter_available: bool
    setup_hint: str


class ProvidersResponse(BaseModel):
    providers: list[ProviderItem]
