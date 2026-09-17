"""routers/ai.py — AI Chat and Embeddings router.

Exposes:
  POST /ai/chat         — Full agent orchestration (Agent Brain)
  POST /ai/embeddings   — Real embeddings for RAG pipeline
  GET  /ai/health       — Provider health check
  GET  /ai/providers    — List available providers
  GET  /ai/models       — List supported models for active provider
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dependencies.internal_auth import verify_internal_api_key
from schemas.chat import ChatMessage, ChatRequest
from services.ai_service import AIService, AIServiceException
from services.agent_brain import get_agent_brain
from services.embedding_service import get_embedding_service
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

_ai_service: AIService | None = None


def _get_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OrchestratedChatRequest(BaseModel):
    """Request body for the orchestrated AI chat endpoint."""

    message: str = Field(..., min_length=1, description="User message or query.")
    conversation_id: str | None = Field(
        default=None, description="Optional conversation ID for memory continuity."
    )
    context: list[ChatMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Bounded canonical conversation context supplied by Node.",
    )
    system_prompt: str | None = Field(
        default=None, description="Optional system prompt override."
    )
    temperature: float | None = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature."
    )
    max_tokens: int | None = Field(
        default=None, ge=1, le=32768, description="Max completion tokens."
    )
    # JWT token forwarded from Node so the Agent Brain can call
    # authenticated memory/document APIs back on the Node Backend.
    user_token: str | None = Field(
        default=None, description="Authenticated user JWT (forwarded from Node)."
    )


class OrchestratedChatResponse(BaseModel):
    """Response body from the orchestrated AI chat endpoint."""

    success: bool
    provider: str
    model: str
    response: str
    tokens: dict[str, Any]
    execution_time: float
    conversation_id: str
    agent_status: str = "RESPONDING"
    capabilities_used: list[str] = Field(default_factory=list)
    steps_taken: int = 0


class EmbeddingsRequest(BaseModel):
    """Request body for the embeddings endpoint."""

    texts: list[str] = Field(..., min_length=1, description="List of texts to embed.")


class EmbeddingsResponse(BaseModel):
    """Response body from the embeddings endpoint."""

    success: bool
    embeddings: list[list[float]]
    model: str
    dimension: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=OrchestratedChatResponse, tags=["AI"])
async def orchestrated_chat(
    body: OrchestratedChatRequest,
    _: None = Depends(verify_internal_api_key),
) -> OrchestratedChatResponse:
    """Execute a chat request through the Agent Brain orchestrator.

    The Agent Brain will:
    1. Classify intent (conversational / tool / memory / RAG / web research).
    2. Retrieve relevant memory and documents when needed.
    3. Perform web research when current external information is required.
    4. Execute deterministic tools (calculator, current_time, etc.).
    5. Assemble context and generate a final LLM response.
    """
    brain = get_agent_brain()

    history = [
        {"role": msg.role, "content": msg.content}
        for msg in body.context[-20:]
    ]

    try:
        result = await brain.process(
            message=body.message,
            conversation_id=body.conversation_id or f"conv_{int(__import__('time').time() * 1000)}",
            history=history,
            system_prompt_override=body.system_prompt,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            user_token=body.user_token,
        )
        return OrchestratedChatResponse(
            success=True,
            provider=result["provider"],
            model=result["model"],
            response=result["response"],
            tokens=result["tokens"],
            execution_time=result["execution_time"],
            conversation_id=result["conversation_id"],
            agent_status=result.get("agent_status", "RESPONDING"),
            capabilities_used=result.get("capabilities_used", []),
            steps_taken=result.get("steps_taken", 0),
        )
    except AIServiceException as exc:
        logger.error("AI Service error in orchestrated chat", extra={"error": str(exc)})
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error in orchestrated chat", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/embeddings", response_model=EmbeddingsResponse, tags=["AI"])
async def generate_embeddings(
    body: EmbeddingsRequest,
    _: None = Depends(verify_internal_api_key),
) -> EmbeddingsResponse:
    """Generate real semantic embeddings for a list of texts.

    Used by the Node Backend RAG pipeline for document indexing and
    similarity search. Returns actual embedding vectors from the
    configured AI provider, with deterministic fallback if unavailable.
    """
    if len(body.texts) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 texts per request")

    # Filter empty texts
    clean_texts = [t.strip() for t in body.texts if t and t.strip()]
    if not clean_texts:
        raise HTTPException(status_code=400, detail="All texts are empty")

    embedding_svc = get_embedding_service()

    try:
        embeddings = await embedding_svc.generate(clean_texts)

        if not embeddings:
            raise HTTPException(status_code=500, detail="Embedding generation returned empty result")

        dimension = len(embeddings[0]) if embeddings else 0

        return EmbeddingsResponse(
            success=True,
            embeddings=embeddings,
            model="provider_embeddings",
            dimension=dimension,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Embedding generation failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Embedding generation failed") from exc


@router.get("/health", tags=["AI"])
async def ai_health(
    _: None = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """Perform a health diagnostic on the active AI provider."""
    service = _get_service()
    try:
        health = await service.check_health()
        return health.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/providers", tags=["AI"])
async def list_providers(
    _: None = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """List all supported AI providers."""
    service = _get_service()
    providers = await service.get_providers()
    return providers.model_dump()


@router.get("/models", tags=["AI"])
async def list_models(
    _: None = Depends(verify_internal_api_key),
) -> dict[str, Any]:
    """List models available for the currently active AI provider."""
    service = _get_service()
    models = await service.get_models()
    return models.model_dump()
