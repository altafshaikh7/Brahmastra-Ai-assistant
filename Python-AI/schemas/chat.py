# schemas/chat.py
"""Pydantic schemas for the AI Chat Service.

This module defines request and response data models for single and streaming chat completion,
provider selection, model enumeration, token statistics, and conversation history.
"""

from __future__ import annotations

try:
    from datetime import UTC, datetime
except ImportError:  # Python < 3.11
    from datetime import datetime
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    """Represents a single message within a conversation."""

    role: str = Field(
        ...,
        description="The role of the message sender (e.g., 'user', 'assistant', 'system').",
        examples=["user"],
    )
    content: str = Field(
        ...,
        description="The textual content of the message.",
        examples=["Hello! How can you help me today?"],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the message was recorded.",
    )

    model_config = ConfigDict(
        strict=False,
        json_encoders={datetime: lambda v: v.isoformat()},
    )


class ChatRequest(BaseModel):
    """Request payload for triggering an AI chat completion."""

    message: str = Field(
        ...,
        min_length=1,
        description="User input prompt or question.",
        examples=["Explain quantum computing in simple terms."],
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional unique identifier for persisting and linking conversation context.",
        examples=["conv_9f8a7b6c5d"],
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional instructions to guide model behavior and personality.",
        examples=["You are a helpful and concise technical assistant."],
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for randomness (0.0 = deterministic, 2.0 = creative).",
        examples=[0.7],
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        le=32768,
        description="Maximum number of tokens to generate in the completion.",
        examples=[1024],
    )
    stream: bool = Field(
        default=False,
        description="If True, the response will be streamed via Server-Sent Events (SSE).",
        examples=[False],
    )

    model_config = ConfigDict(
        strict=False,
        json_schema_extra={
            "example": {
                "message": "What are the core features of Brahmastra AI?",
                "conversation_id": "conv_1234567890",
                "system_prompt": "You are Brahmastra AI assistant.",
                "temperature": 0.7,
                "max_tokens": 1024,
                "stream": False,
            }
        },
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        """Ensure message is not purely whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty or contain only whitespace.")
        return stripped


class TokenUsage(BaseModel):
    """Token consumption statistics for an AI request."""

    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Number of tokens in the prompt / input message.",
        examples=[42],
    )
    completion_tokens: int = Field(
        default=0,
        ge=0,
        description="Number of tokens generated in the response completion.",
        examples=[128],
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total tokens consumed (prompt + completion).",
        examples=[170],
    )

    model_config = ConfigDict(strict=False)


class ChatResponse(BaseModel):
    """Response payload returned for a non-streaming AI chat completion."""

    success: bool = Field(
        default=True,
        description="Indicates whether the request completed successfully.",
        examples=[True],
    )
    provider: str = Field(
        ...,
        description="AI provider that processed the request (e.g., 'gemini', 'groq', 'openai', 'openrouter', 'ollama').",
        examples=["gemini"],
    )
    model: str = Field(
        ...,
        description="Model name used for completion.",
        examples=["gemini-2.5-flash"],
    )
    response: str = Field(
        ...,
        description="Generated AI response content.",
        examples=["Quantum computing uses qubits to perform complex calculations..."],
    )
    tokens: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Token usage breakdown.",
    )
    execution_time: float = Field(
        ...,
        ge=0.0,
        description="Execution wall-clock time in seconds.",
        examples=[0.452],
    )
    conversation_id: str = Field(
        ...,
        description="Conversation ID associated with this interaction.",
        examples=["conv_9f8a7b6c5d"],
    )

    model_config = ConfigDict(
        strict=False,
        json_schema_extra={
            "example": {
                "success": True,
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "response": "Brahmastra AI provides multi-provider LLM orchestration.",
                "tokens": {
                    "prompt_tokens": 25,
                    "completion_tokens": 12,
                    "total_tokens": 37,
                },
                "execution_time": 0.384,
                "conversation_id": "conv_1234567890",
            }
        },
    )


class ProviderInfo(BaseModel):
    """Metadata describing a supported AI provider."""

    id: str = Field(..., description="Provider identifier slug.", examples=["gemini"])
    name: str = Field(
        ..., description="Display name of the provider.", examples=["Google Gemini"]
    )
    default_model: str = Field(
        ...,
        description="Default model for this provider.",
        examples=["gemini-2.5-flash"],
    )
    supported_models: list[str] = Field(
        ..., description="List of supported model identifiers."
    )
    is_active: bool = Field(
        ...,
        description="Whether this provider is currently active/selected in configuration.",
    )

    model_config = ConfigDict(strict=False)


class ProvidersResponse(BaseModel):
    """Response model for enumerating available AI providers."""

    active_provider: str = Field(
        ..., description="Currently selected active provider slug.", examples=["gemini"]
    )
    providers: list[ProviderInfo] = Field(
        ..., description="List of all supported AI providers."
    )

    model_config = ConfigDict(strict=False)


class ModelInfo(BaseModel):
    """Metadata describing an AI model."""

    id: str = Field(..., description="Model identifier.", examples=["gemini-2.5-flash"])
    name: str = Field(
        ..., description="Display name of the model.", examples=["Gemini 2.5 Flash"]
    )
    provider: str = Field(..., description="Provider slug.", examples=["gemini"])
    context_window: int = Field(
        ..., description="Maximum context window size in tokens.", examples=[1048576]
    )

    model_config = ConfigDict(strict=False)


class ModelsResponse(BaseModel):
    """Response model for enumerating available models."""

    provider: str = Field(..., description="Provider slug.", examples=["gemini"])
    models: list[ModelInfo] = Field(
        ..., description="List of supported models for the provider."
    )

    model_config = ConfigDict(strict=False)


class AIHealthResponse(BaseModel):
    """Health check response model for the AI service."""

    status: str = Field(
        ..., description="Health status ('ok', 'degraded', 'error').", examples=["ok"]
    )
    provider: str = Field(
        ..., description="Currently active provider slug.", examples=["gemini"]
    )
    model: str = Field(
        ..., description="Currently active model name.", examples=["gemini-2.5-flash"]
    )
    latency_ms: float | None = Field(
        default=None, description="Ping latency in milliseconds to provider API."
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional health diagnostic details."
    )

    model_config = ConfigDict(strict=False)
