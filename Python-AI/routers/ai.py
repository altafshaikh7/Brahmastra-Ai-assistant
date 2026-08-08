"""AI Chat router — exposes the AIService orchestration endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from schemas.chat import ChatRequest
from services.ai_service import AIService, AIServiceException
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

_ai_service: AIService | None = None


def _get_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service


class OrchestratedChatRequest(BaseModel):
    """Request body for the orchestrated AI chat endpoint."""

    message: str = Field(..., min_length=1, description="User message or query.")
    conversation_id: str | None = Field(
        default=None, description="Optional conversation ID for memory continuity."
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


class OrchestratedChatResponse(BaseModel):
    """Response body from the orchestrated AI chat endpoint."""

    success: bool
    provider: str
    model: str
    response: str
    tokens: dict[str, Any]
    execution_time: float
    conversation_id: str


@router.post("/chat", response_model=OrchestratedChatResponse, tags=["AI"])
async def orchestrated_chat(body: OrchestratedChatRequest) -> OrchestratedChatResponse:
    """Execute a chat request through the AI Tool Orchestrator.

    The orchestrator will:
    1. Inject available tools into the system prompt.
    2. Let the AI decide whether a tool is required.
    3. Execute any selected tool via ToolRegistry + ToolExecutor.
    4. Return a final natural-language response.
    """
    service = _get_service()
    chat_req = ChatRequest(
        message=body.message,
        conversation_id=body.conversation_id,
        system_prompt=body.system_prompt,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        stream=False,
    )

    try:
        result = await service.chat(chat_req)
        return OrchestratedChatResponse(
            success=result.success,
            provider=result.provider,
            model=result.model,
            response=result.response,
            tokens=result.tokens.model_dump(),
            execution_time=result.execution_time,
            conversation_id=result.conversation_id,
        )
    except AIServiceException as exc:
        logger.error("AI Service error in orchestrated chat", extra={"error": str(exc)})
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error in orchestrated chat", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc)) from exc
