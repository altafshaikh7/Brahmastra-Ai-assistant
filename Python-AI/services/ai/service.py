# services/ai/service.py
"""Production-grade AI Service orchestrator for Brahmastra AI.

This module provides the central AIService class that manages provider selection,
chat response generation, streaming, health monitoring, and lifecycle management
across all configured AI providers via AIProviderFactory.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Type

from core.config import Settings, get_settings
from schemas.chat import (
    AIHealthResponse,
    ChatRequest,
    ChatResponse,
    ProviderInfo,
    ProvidersResponse,
)
from services.ai.base import BaseAIProvider
from services.ai.factory import AIProviderFactory
from utils.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """Production-grade AI Service orchestrator.

    Routes chat generation, streaming, and health check requests to appropriate
    provider strategies managed by AIProviderFactory.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        factory: Optional[Type[AIProviderFactory]] = None,
    ) -> None:
        """Initialize AIService with application settings and provider factory.

        Args:
            settings: Loaded Settings instance or None to use get_settings().
            factory: AIProviderFactory class reference or None to use default.
        """
        self.settings: Settings = settings or get_settings()
        self.factory: Type[AIProviderFactory] = factory or AIProviderFactory

    async def startup(self) -> None:
        """Initialize resources and preload default provider during startup."""
        logger.info("Initializing AIService startup sequence")
        try:
            default_provider = self.factory.get_provider(settings=self.settings)
            await default_provider.startup()
            logger.info(
                "AIService startup complete - preloaded provider",
                extra={"provider": default_provider.provider_id},
            )
        except Exception as exc:
            logger.warning(
                "AIService startup preloading deferred",
                extra={"error": str(exc)},
            )

    async def shutdown(self) -> None:
        """Gracefully close all cached provider HTTP clients during application shutdown."""
        logger.info("Executing AIService shutdown sequence")
        await self.factory.shutdown_all()
        logger.info("AIService shutdown complete")

    def _resolve_provider(self, provider_override: Optional[str] = None) -> BaseAIProvider:
        """Resolve target provider strategy instance.

        Args:
            provider_override: Optional slug override ('gemini', 'groq', etc.).

        Returns:
            BaseAIProvider strategy singleton.
        """
        target = provider_override or self.settings.ai.provider
        return self.factory.get_provider(provider_id=target, settings=self.settings)

    async def generate_response(
        self,
        request: ChatRequest,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        provider_override: Optional[str] = None,
    ) -> ChatResponse:
        """Generate a complete AI response and return standardized ChatResponse payload.

        Args:
            request: ChatRequest model containing user prompt and config.
            conversation_history: Optional list of past message dictionaries.
            provider_override: Optional provider slug override.

        Returns:
            ChatResponse containing generated message, token usage, model, and metadata.
        """
        start_time = time.perf_counter()
        history = conversation_history or []
        provider = self._resolve_provider(provider_override)
        model_name = provider.resolve_model(request)

        logger.info(
            "Generating AI response",
            extra={
                "provider": provider.provider_id,
                "model": model_name,
                "conversation_id": request.conversation_id,
            },
        )

        response_text, tokens = await provider.generate_response(request, history)
        execution_time = round(time.perf_counter() - start_time, 4)

        return ChatResponse(
            success=True,
            provider=provider.provider_id,
            model=model_name,
            response=response_text,
            tokens=tokens,
            execution_time=execution_time,
            conversation_id=request.conversation_id or "default",
        )

    async def generate_stream(
        self,
        request: ChatRequest,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        provider_override: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream generated AI token chunks as an async generator.

        Args:
            request: ChatRequest model containing user prompt and config.
            conversation_history: Optional list of past message dictionaries.
            provider_override: Optional provider slug override.

        Yields:
            Token text chunks as received from the AI provider.
        """
        history = conversation_history or []
        provider = self._resolve_provider(provider_override)
        model_name = provider.resolve_model(request)

        logger.info(
            "Starting AI response stream",
            extra={
                "provider": provider.provider_id,
                "model": model_name,
                "conversation_id": request.conversation_id,
            },
        )

        async for chunk in provider.generate_stream(request, history):
            yield chunk

    async def check_provider_health(
        self,
        provider_id: Optional[str] = None,
    ) -> AIHealthResponse:
        """Check health status and latency of a single AI provider.

        Args:
            provider_id: Target provider slug or None for default active provider.

        Returns:
            AIHealthResponse containing health status and diagnostics.
        """
        target_slug = provider_id or self.settings.ai.provider
        try:
            provider = self.factory.get_provider(provider_id=target_slug, settings=self.settings)
            is_healthy, latency_ms, message = await provider.check_health()
            status = "ok" if is_healthy else "degraded"
            model_name = provider.default_model

            return AIHealthResponse(
                status=status,
                provider=provider.provider_id,
                model=model_name,
                latency_ms=latency_ms,
                details={
                    "display_name": provider.display_name,
                    "supported_models": provider.supported_models,
                    "message": message,
                },
            )
        except Exception as exc:
            logger.error(
                "Health check failed for provider",
                extra={"provider": target_slug, "error": str(exc)},
            )
            return AIHealthResponse(
                status="error",
                provider=target_slug,
                model="unknown",
                latency_ms=None,
                details={"error": str(exc)},
            )

    async def check_all_providers(self) -> Dict[str, AIHealthResponse]:
        """Run health diagnostic checks across all registered providers concurrently.

        Returns:
            Dictionary mapping provider slugs to AIHealthResponse results.
        """
        supported_slugs = self.factory.list_supported_providers()
        tasks = [self.check_provider_health(slug) for slug in supported_slugs]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return {slug: response for slug, response in zip(supported_slugs, results)}

    async def list_available_providers(self) -> ProvidersResponse:
        """List metadata for all supported AI providers and highlight current active provider.

        Returns:
            ProvidersResponse containing active provider slug and list of ProviderInfo models.
        """
        active_slug = self.settings.ai.provider
        provider_infos: List[ProviderInfo] = []

        for slug in self.factory.list_supported_providers():
            try:
                provider = self.factory.get_provider(provider_id=slug, settings=self.settings)
                provider_infos.append(
                    ProviderInfo(
                        id=provider.provider_id,
                        name=provider.display_name,
                        default_model=provider.default_model,
                        supported_models=provider.supported_models,
                        is_active=(slug == active_slug),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Could not load provider info",
                    extra={"provider": slug, "error": str(exc)},
                )

        return ProvidersResponse(
            active_provider=active_slug,
            providers=provider_infos,
        )


_service_instance: Optional[AIService] = None


def get_ai_service(settings: Optional[Settings] = None) -> AIService:
    """Return singleton instance of AIService.

    Args:
        settings: Optional Settings instance.

    Returns:
        Singleton AIService instance.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = AIService(settings=settings)
    return _service_instance
