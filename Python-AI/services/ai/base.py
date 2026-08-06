# services/ai/base.py
"""Abstract Base AI Provider for Brahmastra AI.

This module defines the foundational Strategy contract and shared utility methods
for all AI provider implementations (Gemini, Groq, OpenAI, OpenRouter, Ollama).
"""

from __future__ import annotations

import abc
import asyncio
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, TypeVar

import httpx

from core.config import Settings
from schemas.chat import ChatRequest, TokenUsage
from services.ai.exceptions import (
    AIServiceException,
    APIKeyMissingException,
    InvalidModelException,
    NetworkErrorException,
    ProviderErrorException,
    RateLimitException,
    TimeoutException,
)
from utils.logger import get_logger

T = TypeVar("T")


class BaseAIProvider(abc.ABC):
    """Abstract Base Class for all AI Providers.

    Provides shared messaging formatting, HTTP client lifecycle management,
    token estimation, model resolution, and resilient retry logic.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize base provider settings and logging configuration.

        Args:
            settings: Loaded application settings instance.
        """
        self.settings: Settings = settings
        self.logger = get_logger(self.__class__.__module__)
        self.provider_id: str = "base"
        self.display_name: str = "Base Provider"
        self.default_model: str = ""
        self.supported_models: List[str] = []
        self._http_client: Optional[httpx.AsyncClient] = None

    def prepare_messages(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Format input prompt and history into OpenAI-compatible message list.

        Args:
            request: Incoming chat completion request.
            history: List of prior message dicts with 'role' and 'content'.

        Returns:
            List of structured message dictionaries containing role and content.
        """
        messages: List[Dict[str, str]] = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        for msg in history:
            role = str(msg.get("role", "user")).lower()
            content = str(msg.get("content", ""))
            messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": request.message})
        return messages

    def prepare_prompt(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> str:
        """Format input prompt and history into a single concatenated string prompt.

        Args:
            request: Incoming chat completion request.
            history: List of prior message dicts with 'role' and 'content'.

        Returns:
            Formatted multi-turn prompt string.
        """
        prompt_parts: List[str] = []

        if request.system_prompt:
            prompt_parts.append(f"System: {request.system_prompt}\n")

        for msg in history:
            role_raw = str(msg.get("role", "user")).lower()
            role_label = "Assistant" if role_raw in ("assistant", "model") else "User"
            content = str(msg.get("content", ""))
            prompt_parts.append(f"{role_label}: {content}")

        prompt_parts.append(f"User: {request.message}")
        return "\n".join(prompt_parts)

    def resolve_model(self, request: ChatRequest) -> str:
        """Determine the model name to use for request execution.

        Checks request override first, then provider default, then system default.

        Args:
            request: Incoming chat completion request.

        Returns:
            Resolved model identifier string.
        """
        requested_model = getattr(request, "model", None)
        if requested_model and isinstance(requested_model, str) and requested_model.strip():
            model = requested_model.strip()
        elif self.default_model and self.default_model.strip():
            model = self.default_model.strip()
        else:
            model = self.settings.ai.model_name or "gemini-2.5-flash"

        return model

    def extract_token_usage(
        self,
        usage_metadata: Optional[Any] = None,
        prompt_text: str = "",
        response_text: str = "",
    ) -> TokenUsage:
        """Extract or estimate token usage statistics.

        Args:
            usage_metadata: Raw provider token usage object/dict if provided.
            prompt_text: Input prompt text for fallback token estimation.
            response_text: Output response text for fallback token estimation.

        Returns:
            TokenUsage pydantic instance.
        """
        if usage_metadata is not None:
            if isinstance(usage_metadata, dict):
                p_tokens = usage_metadata.get("prompt_tokens") or usage_metadata.get("prompt_token_count")
                c_tokens = usage_metadata.get("completion_tokens") or usage_metadata.get("candidates_token_count")
                t_tokens = usage_metadata.get("total_tokens") or usage_metadata.get("total_token_count")

                if p_tokens is not None and c_tokens is not None:
                    return TokenUsage(
                        prompt_tokens=int(p_tokens),
                        completion_tokens=int(c_tokens),
                        total_tokens=int(t_tokens if t_tokens is not None else p_tokens + c_tokens),
                    )
            elif hasattr(usage_metadata, "prompt_token_count"):
                p_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
                c_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0
                t_tokens = getattr(usage_metadata, "total_token_count", 0) or (p_tokens + c_tokens)
                return TokenUsage(
                    prompt_tokens=int(p_tokens),
                    completion_tokens=int(c_tokens),
                    total_tokens=int(t_tokens),
                )
            elif hasattr(usage_metadata, "prompt_tokens"):
                p_tokens = getattr(usage_metadata, "prompt_tokens", 0) or 0
                c_tokens = getattr(usage_metadata, "completion_tokens", 0) or 0
                t_tokens = getattr(usage_metadata, "total_tokens", 0) or (p_tokens + c_tokens)
                return TokenUsage(
                    prompt_tokens=int(p_tokens),
                    completion_tokens=int(c_tokens),
                    total_tokens=int(t_tokens),
                )

        # Fallback heuristic: ~4 characters per token
        p_est = max(1, len(prompt_text) // 4) if prompt_text else 0
        c_est = max(1, len(response_text) // 4) if response_text else 0
        return TokenUsage(
            prompt_tokens=p_est,
            completion_tokens=c_est,
            total_tokens=p_est + c_est,
        )

    def create_http_client(
        self,
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.AsyncClient:
        """Create or return existing singleton HTTPX AsyncClient.

        Args:
            base_url: Base URL string for HTTP calls.
            headers: HTTP header key-value pairs.

        Returns:
            Reused singleton httpx.AsyncClient.
        """
        if self._http_client is None or self._http_client.is_closed:
            timeout_val = float(self.settings.ai.timeout_seconds)
            self._http_client = httpx.AsyncClient(
                base_url=base_url or "",
                headers=headers or {},
                timeout=httpx.Timeout(timeout_val),
            )
            self.logger.info(
                "Created HTTP client singleton",
                extra={"provider": self.provider_id, "base_url": base_url},
            )
        return self._http_client

    async def close(self) -> None:
        """Gracefully close the underlying HTTP client session."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
            self.logger.info("Closed HTTP client connection", extra={"provider": self.provider_id})

    async def startup(self) -> None:
        """Initialize provider resources during application startup."""
        pass

    async def shutdown(self) -> None:
        """Clean up provider resources during application shutdown."""
        await self.close()

    async def retry(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute async function with exponential backoff retries.

        Retries on TimeoutException, NetworkErrorException, and RateLimitException.
        Does NOT retry APIKeyMissingException or InvalidModelException.

        Args:
            func: Async callable to execute.
            *args: Positional arguments for func.
            **kwargs: Keyword arguments for func.

        Returns:
            Return value of func execution.
        """
        max_attempts = max(1, self.settings.ai.retry_attempts)
        backoff = max(0.0, self.settings.ai.retry_backoff_seconds)
        start_time = time.perf_counter()

        for attempt in range(1, max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                self.logger.info(
                    "Execution successful",
                    extra={
                        "provider": self.provider_id,
                        "attempt": attempt,
                        "elapsed_seconds": round(elapsed, 4),
                    },
                )
                return result
            except (TimeoutException, NetworkErrorException, RateLimitException) as exc:
                elapsed = time.perf_counter() - start_time
                if attempt < max_attempts:
                    sleep_time = backoff * (2 ** (attempt - 1))
                    self.logger.warning(
                        "Retryable error encountered",
                        extra={
                            "provider": self.provider_id,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "sleep_time_seconds": sleep_time,
                            "error": str(exc),
                        },
                    )
                    await asyncio.sleep(sleep_time)
                else:
                    self.logger.error(
                        "Max retry attempts exhausted",
                        extra={
                            "provider": self.provider_id,
                            "attempts": max_attempts,
                            "elapsed_seconds": round(elapsed, 4),
                            "error": str(exc),
                        },
                    )
                    raise exc
            except (APIKeyMissingException, InvalidModelException) as exc:
                self.logger.error(
                    "Non-retryable client error",
                    extra={"provider": self.provider_id, "error": str(exc)},
                )
                raise exc
            except Exception as exc:
                self.logger.error(
                    "Unexpected provider execution error",
                    extra={"provider": self.provider_id, "error": str(exc)},
                )
                raise ProviderErrorException(self.provider_id, str(exc))

    @abc.abstractmethod
    async def generate_response(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> Tuple[str, TokenUsage]:
        """Generate a complete text response and token usage stats.

        Args:
            request: Input chat request containing prompt and settings.
            history: List of past conversation message dictionaries.

        Returns:
            Tuple of (generated_response_text, token_usage_instance).
        """
        pass

    @abc.abstractmethod
    async def generate_stream(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming token response as an async generator.

        Args:
            request: Input chat request containing prompt and settings.
            history: List of past conversation message dictionaries.

        Yields:
            Text content chunks as they are received from the AI provider.
        """
        pass

    @abc.abstractmethod
    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        """Perform a health diagnostic check on the provider connection.

        Returns:
            Tuple of (is_healthy, latency_in_ms, status_message).
        """
        pass
