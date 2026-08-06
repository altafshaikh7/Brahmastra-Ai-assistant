# services/ai/providers/groq.py
"""Groq AI Provider for Brahmastra AI.

This module implements the production-grade GroqProvider using the official AsyncGroq SDK,
providing native async execution, streaming, token extraction, retry resiliency, and error mapping.
"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from core.config import Settings
from schemas.chat import ChatRequest, TokenUsage
from services.ai.base import BaseAIProvider
from services.ai.exceptions import (
    APIKeyMissingException,
    InvalidModelException,
    NetworkErrorException,
    ProviderErrorException,
    RateLimitException,
    TimeoutException,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class GroqProvider(BaseAIProvider):
    """Groq AI Provider Implementation.

    Utilizes the official AsyncGroq SDK (from groq import AsyncGroq) to provide
    asynchronous text generation, streaming token delivery, usage metrics, and health pings.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the GroqProvider instance.

        Args:
            settings: Centralized application configuration.
        """
        super().__init__(settings)
        self.provider_id: str = "groq"
        self.display_name: str = "Groq AI"
        self.default_model: str = (
            getattr(settings.ai, "groq_model", None)
            or "llama-3.3-70b-versatile"
        )
        self.supported_models: List[str] = [
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            "qwen/qwen3-32b",
            "mixtral-8x7b-32768",
        ]
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Singleton accessor for the AsyncGroq Client.

        Returns:
            Configured AsyncGroq client instance.

        Raises:
            APIKeyMissingException: If API key is not configured.
            ProviderErrorException: If client initialization fails.
        """
        if self._client is None:
            api_key = (
                self.settings.ai.api_key.get_secret_value()
                if self.settings.ai.api_key
                else None
            )
            if not api_key:
                raise APIKeyMissingException(self.provider_id)
            try:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=api_key)
                self.logger.info("Initialized AsyncGroq singleton client", extra={"provider": self.provider_id})
            except APIKeyMissingException:
                raise
            except Exception as exc:
                self.logger.error("Failed to initialize AsyncGroq client", extra={"error": str(exc)})
                raise ProviderErrorException(self.provider_id, f"Client initialization failed: {str(exc)}")
        return self._client

    def _map_sdk_exception(self, exc: Exception, model_name: str) -> Exception:
        """Map raw Groq SDK exceptions to project domain exceptions.

        Args:
            exc: Caught exception.
            model_name: Model identifier used during call.

        Returns:
            Mapped AIServiceException subclass instance.
        """
        err_msg = str(exc)
        err_lower = err_msg.lower()

        status_code = getattr(exc, "status_code", None)
        if status_code == 401 or "unauthorized" in err_lower or "api_key" in err_lower:
            return APIKeyMissingException(self.provider_id)
        elif status_code == 429 or "rate limit" in err_lower:
            return RateLimitException(self.provider_id, err_msg)
        elif status_code == 404 or "model_not_found" in err_lower or "invalid model" in err_lower:
            return InvalidModelException(model_name, self.provider_id)
        elif "timeout" in err_lower or "timed out" in err_lower:
            return TimeoutException(self.provider_id, float(self.settings.ai.timeout_seconds))
        elif "connection" in err_lower or "network" in err_lower or "dns" in err_lower:
            return NetworkErrorException(self.provider_id, err_msg)

        return ProviderErrorException(self.provider_id, err_msg, status_code=status_code or 502)

    async def generate_response(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> Tuple[str, TokenUsage]:
        """Generate a complete text response and token usage stats using Groq.

        Args:
            request: Input chat request payload.
            history: Previous conversation message history.

        Returns:
            Tuple of (response_text, token_usage_instance).
        """
        client = self._get_client()
        model_name = self.resolve_model(request)
        messages = self.prepare_messages(request, history)

        async def _call_groq() -> Tuple[str, TokenUsage]:
            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=request.temperature if request.temperature is not None else self.settings.ai.temperature,
                    max_tokens=request.max_tokens or self.settings.ai.max_output_tokens,
                )
                choices = getattr(response, "choices", [])
                content = choices[0].message.content or "" if choices else ""
                usage = getattr(response, "usage", None)
                tokens = self.extract_token_usage(usage, str(messages), content)
                return content, tokens
            except Exception as exc:
                raise self._map_sdk_exception(exc, model_name)

        return await self.retry(_call_groq)

    async def generate_stream(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Stream generated token chunks using Groq streaming completions.

        Args:
            request: Input chat request payload.
            history: Previous conversation message history.

        Yields:
            Non-empty text content chunks as received.
        """
        client = self._get_client()
        model_name = self.resolve_model(request)
        messages = self.prepare_messages(request, history)

        try:
            stream = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=request.temperature if request.temperature is not None else self.settings.ai.temperature,
                max_tokens=request.max_tokens or self.settings.ai.max_output_tokens,
                stream=True,
            )
            async for chunk in stream:
                choices = getattr(chunk, "choices", [])
                if choices:
                    delta_content = getattr(choices[0].delta, "content", None)
                    if delta_content:
                        yield delta_content
        except Exception as exc:
            raise self._map_sdk_exception(exc, model_name)

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        """Perform a quick health ping test against Groq AI.

        Returns:
            Tuple of (is_healthy, latency_ms, status_message).
        """
        start = time.perf_counter()
        try:
            client = self._get_client()
            await client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
            return True, latency_ms, "Healthy"
        except Exception as exc:
            err_mapped = self._map_sdk_exception(exc, self.default_model)
            return False, None, f"Groq health check failed: {str(err_mapped)}"

    async def startup(self) -> None:
        """Initialize client lazily during startup."""
        try:
            self._get_client()
        except Exception as exc:
            self.logger.warning("Groq startup client init deferred", extra={"error": str(exc)})

    async def shutdown(self) -> None:
        """Clean up provider resources during shutdown."""
        await super().shutdown()
