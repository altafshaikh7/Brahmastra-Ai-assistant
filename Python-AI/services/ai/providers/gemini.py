# services/ai/providers/gemini.py
"""Google Gemini AI Provider for Brahmastra AI.

This module implements the production-grade GeminiProvider using the official Google GenAI SDK
(google.genai), providing non-blocking execution, streaming, token extraction, and error mapping.
"""

from __future__ import annotations

import asyncio
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
    TimeoutException,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI Provider Implementation.

    Utilizes the official Google GenAI SDK (from google import genai) to provide
    asynchronous text generation, streaming, token usage tracking, and health pings.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the GeminiProvider instance.

        Args:
            settings: Centralized application configuration.
        """
        super().__init__(settings)
        self.provider_id: str = "gemini"
        self.display_name: str = "Google Gemini"
        self.default_model: str = (
            getattr(settings.ai, "gemini_model", None)
            or (settings.ai.model_name if settings.ai.provider == "gemini" else "gemini-2.5-flash")
        )
        self.supported_models: List[str] = [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Singleton accessor for the Google GenAI Client.

        Returns:
            Configured genai.Client instance.

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
                from google import genai
                self._client = genai.Client(api_key=api_key)
                self.logger.info("Initialized Google GenAI singleton client", extra={"provider": self.provider_id})
            except APIKeyMissingException:
                raise
            except Exception as exc:
                self.logger.error("Failed to initialize Google GenAI SDK client", extra={"error": str(exc)})
                raise ProviderErrorException(self.provider_id, f"Client initialization failed: {str(exc)}")
        return self._client

    def _map_sdk_exception(self, exc: Exception, model_name: str) -> Exception:
        """Map raw Google GenAI SDK exceptions to project domain exceptions.

        Args:
            exc: Caught exception.
            model_name: Model identifier used during call.

        Returns:
            Mapped AIServiceException subclass instance.
        """
        err_msg = str(exc)
        err_lower = err_msg.lower()

        if "api_key" in err_lower or "unauthorized" in err_lower or "401" in err_lower:
            return APIKeyMissingException(self.provider_id)
        elif "not found" in err_lower or "invalid model" in err_lower or "404" in err_lower:
            return InvalidModelException(model_name, self.provider_id)
        elif "timeout" in err_lower or "deadline" in err_lower:
            return TimeoutException(self.provider_id, float(self.settings.ai.timeout_seconds))
        elif "connection" in err_lower or "network" in err_lower or "dns" in err_lower:
            return NetworkErrorException(self.provider_id, err_msg)

        return ProviderErrorException(self.provider_id, err_msg)

    async def generate_response(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> Tuple[str, TokenUsage]:
        """Generate a complete text response and token usage stats using Gemini.

        Args:
            request: Input chat request payload.
            history: Previous conversation message history.

        Returns:
            Tuple of (response_text, token_usage_instance).
        """
        client = self._get_client()
        model_name = self.resolve_model(request)
        full_prompt = self.prepare_prompt(request, history)

        async def _call_gemini() -> Tuple[str, TokenUsage]:
            def _sync_generate():
                return client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                )

            try:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, _sync_generate)
                response_text = getattr(response, "text", "") or ""
                usage_metadata = getattr(response, "usage_metadata", None)
                tokens = self.extract_token_usage(usage_metadata, full_prompt, response_text)
                return response_text, tokens
            except Exception as exc:
                raise self._map_sdk_exception(exc, model_name)

        return await self.retry(_call_gemini)

    async def generate_stream(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Stream generated token chunks using Gemini generate_content_stream.

        Args:
            request: Input chat request payload.
            history: Previous conversation message history.

        Yields:
            Non-empty text content chunks as received.
        """
        client = self._get_client()
        model_name = self.resolve_model(request)
        full_prompt = self.prepare_prompt(request, history)

        def _sync_stream():
            return client.models.generate_content_stream(
                model=model_name,
                contents=full_prompt,
            )

        try:
            loop = asyncio.get_running_loop()
            stream_obj = await loop.run_in_executor(None, _sync_stream)
            for chunk in stream_obj:
                chunk_text = getattr(chunk, "text", None)
                if chunk_text:
                    yield chunk_text
        except Exception as exc:
            raise self._map_sdk_exception(exc, model_name)

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        """Perform a quick health ping test against Google Gemini.

        Returns:
            Tuple of (is_healthy, latency_ms, status_message).
        """
        start = time.perf_counter()
        try:
            client = self._get_client()

            def _sync_ping():
                return client.models.generate_content(
                    model=self.default_model,
                    contents="ping",
                )

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _sync_ping)
            latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
            return True, latency_ms, "Healthy"
        except Exception as exc:
            err_mapped = self._map_sdk_exception(exc, self.default_model)
            return False, None, f"Gemini health check failed: {str(err_mapped)}"

    async def startup(self) -> None:
        """Initialize client lazily during startup."""
        try:
            self._get_client()
        except Exception as exc:
            self.logger.warning("Gemini startup client init deferred", extra={"error": str(exc)})

    async def shutdown(self) -> None:
        """Clean up provider resources during shutdown."""
        await super().shutdown()
