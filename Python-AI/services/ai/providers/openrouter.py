# services/ai/providers/openrouter.py
"""OpenRouter AI Provider for Brahmastra AI.

This module implements the production-grade OpenRouterProvider using the official AsyncOpenAI SDK
pointed at the OpenRouter API base URL, providing native async execution, streaming, token usage
extraction, retry resiliency, and domain exception mapping.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from openai import AsyncOpenAI


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

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter AI Provider Implementation.

    Uses the AsyncOpenAI SDK with OpenRouter's OpenAI-compatible API endpoint,
    providing async multi-model LLM access, streaming token delivery, and health monitoring.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the OpenRouterProvider instance.

        Args:
            settings: Centralized application configuration.
        """
        super().__init__(settings)
        self.provider_id: str = "openrouter"
        self.display_name: str = "OpenRouter"
        self.default_model: str = (
            getattr(settings.ai, "openrouter_model", None)
            or "meta-llama/llama-3.3-70b-instruct"
        )
        self.supported_models: List[str] = [
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-r1",
            "google/gemini-2.5-flash",
            "anthropic/claude-sonnet-4",
            "openai/gpt-5-mini",
            "openai/gpt-5",
        ]
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Singleton accessor for the AsyncOpenAI Client pointed at OpenRouter.

        Returns:
            Configured AsyncOpenAI client instance with OpenRouter base URL.

        Raises:
            APIKeyMissingException: If the OpenRouter API key is absent or blank.
            ProviderErrorException: If client initialization fails for any other reason.
        """
        if self._client is None:
            # Validate key BEFORE constructing the client — never pass empty key to SDK
            raw_key: str = (
                self.settings.ai.api_key.get_secret_value()
                if self.settings.ai.api_key
                else ""
            )
            if not raw_key.strip():
                raise APIKeyMissingException(self.provider_id)

            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=raw_key,
                    base_url=_OPENROUTER_BASE_URL,
                    # Disable SDK-level retries — BaseAIProvider.retry() handles all retry logic.
                    max_retries=0,
                    default_headers={
                        # OpenRouter-recommended identity headers
                        "HTTP-Referer": "https://github.com/brahmastra-ai",
                        "X-Title": "Brahmastra AI",
                    },
                )
                self.logger.info(
                    "Initialized AsyncOpenAI singleton client for OpenRouter",
                    extra={"provider": self.provider_id, "base_url": _OPENROUTER_BASE_URL},
                )
            except ImportError:
                self.logger.error(
                    "openai package not installed", extra={"provider": self.provider_id}
                )
                raise ProviderErrorException(
                    self.provider_id,
                    "openai package is not installed. Run 'pip install openai'.",
                )
            except Exception as exc:
                self.logger.error(
                    "Failed to initialize AsyncOpenAI client for OpenRouter",
                    extra={"error": str(exc)},
                )
                raise ProviderErrorException(
                    self.provider_id, f"Client initialization failed: {str(exc)}"
                )
        return self._client

    def _map_sdk_exception(self, exc: Exception, model_name: str) -> Exception:
        """Map raw OpenAI SDK exceptions to project domain exceptions.

        Uses official SDK exception classes exclusively — no string matching for
        known SDK exception types.

        Args:
            exc: Caught exception from the OpenAI SDK.
            model_name: Model identifier used during the call.

        Returns:
            Mapped AIServiceException subclass instance.
        """
        try:
            from openai import (
                APIConnectionError,
                APITimeoutError,
                AuthenticationError,
                BadRequestError,
                LengthFinishReasonError,
                NotFoundError,
                PermissionDeniedError,
                RateLimitError,
            )
        except ImportError:
            return ProviderErrorException(self.provider_id, str(exc))

        # LengthFinishReasonError: context/output token limit hit — SDK raises this directly
        if isinstance(exc, LengthFinishReasonError):
            return ProviderErrorException(
                self.provider_id,
                "Input or output exceeded the model's maximum context length.",
                status_code=400,
            )

        if isinstance(exc, AuthenticationError):
            return APIKeyMissingException(self.provider_id)

        if isinstance(exc, PermissionDeniedError):
            return APIKeyMissingException(self.provider_id)

        if isinstance(exc, RateLimitError):
            return RateLimitException(self.provider_id, str(exc))

        if isinstance(exc, APITimeoutError):
            return TimeoutException(
                self.provider_id,
                float(getattr(self.settings.ai, "timeout_seconds", 60)),
            )

        if isinstance(exc, APIConnectionError):
            return NetworkErrorException(self.provider_id, str(exc))

        # Context length via BadRequestError.body.error.code — no string matching on message
        if isinstance(exc, BadRequestError):
            error_code: Optional[str] = None
            if exc.body and isinstance(exc.body, dict):
                err_body = exc.body.get("error")  # type: ignore[union-attr]
                if isinstance(err_body, dict):
                    error_code = err_body.get("code", "")
            if error_code in ("context_length_exceeded", "string_above_max_length"):
                return ProviderErrorException(
                    self.provider_id,
                    "Input exceeded the model's maximum context length.",
                    status_code=400,
                )
            return ProviderErrorException(
                self.provider_id, str(exc), status_code=exc.status_code
            )

        if isinstance(exc, NotFoundError):
            return InvalidModelException(model_name, self.provider_id)

        if isinstance(exc, ConflictError):
            return ProviderErrorException(
                self.provider_id, str(exc), status_code=exc.status_code
            )

        if isinstance(exc, UnprocessableEntityError):
            return ProviderErrorException(
                self.provider_id, str(exc), status_code=exc.status_code
            )

        if isinstance(exc, InternalServerError):
            return ProviderErrorException(
                self.provider_id, str(exc), status_code=exc.status_code
            )

        # Remaining APIStatusError subclasses (e.g. raw 404 before typed SDK path)
        if isinstance(exc, APIStatusError):
            status_code: int = exc.status_code
            if status_code == 404:
                return InvalidModelException(model_name, self.provider_id)
            return ProviderErrorException(self.provider_id, str(exc), status_code=status_code)

        # Last-resort fallback for entirely unexpected exceptions
        return ProviderErrorException(self.provider_id, str(exc), status_code=502)

    def _parse_usage(
        self,
        usage: Optional[CompletionUsage],
        messages: List[Dict[str, str]],
        content: str,
    ) -> TokenUsage:
        """Parse SDK CompletionUsage into TokenUsage, with heuristic fallback.

        Args:
            usage: Typed CompletionUsage from the SDK response (may be None).
            messages: Formatted request messages (used for fallback estimation only).
            content: Response text (used for fallback estimation only).

        Returns:
            Populated TokenUsage instance.
        """
        if usage is not None:
            prompt = usage.prompt_tokens or 0
            completion = usage.completion_tokens or 0
            return TokenUsage(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=usage.total_tokens or (prompt + completion),
            )
        # Fallback: estimate from concatenated message text via base class heuristic
        prompt_text = " ".join(m.get("content", "") for m in messages)
        return self.extract_token_usage(None, prompt_text, content)

    async def generate_response(
        self,
        request: ChatRequest,
        history: List[Dict[str, str]],
    ) -> Tuple[str, TokenUsage]:
        """Generate a complete text response and token usage stats via OpenRouter.

        Args:
            request: Input chat request payload.
            history: Previous conversation message history.

        Returns:
            Tuple of (response_text, token_usage_instance).
        """
        client = self._get_client()
        model_name = self.resolve_model(request)
        messages = self.prepare_messages(request, history)
        start_time = time.perf_counter()

        async def _call_openrouter() -> ChatCompletion:
            return await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=(
                    request.temperature
                    if request.temperature is not None
                    else self.settings.ai.temperature
                ),
                max_tokens=request.max_tokens or self.settings.ai.max_output_tokens,
            )

        try:
            response: ChatCompletion = await self.retry(_call_openrouter)
        except Exception as exc:
            raise self._map_sdk_exception(exc, model_name)

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        execution_time = round(time.perf_counter() - start_time, 4)

        choices = response.choices
        content: str = choices[0].message.content or "" if choices else ""
        tokens = self._parse_usage(response.usage, messages, content)

        self.logger.info(
            "OpenRouter response received",
            extra={
                "provider": self.provider_id,
                "model": model_name,
                "latency_ms": latency_ms,
                "execution_time": execution_time,
                "prompt_tokens": tokens.prompt_tokens,
                "completion_tokens": tokens.completion_tokens,
                "total_tokens": tokens.total_tokens,
            },
        )
        return content, tokens

    async def generate_stream(
        self,
        request: ChatRequest,
        history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Stream generated token chunks via OpenRouter streaming completions.

        Args:
            request: Input chat request payload.
            history: Previous conversation message history.

        Yields:
            Non-empty text content chunks as received.

        Notes:
            - Skips chunks with missing or empty delta content.
            - Exits cleanly on terminal finish_reason values.
            - Handles asyncio.CancelledError without leaking the connection.
            - Guarantees stream closure via the finally block.
        """
        client = self._get_client()
        model_name = self.resolve_model(request)
        messages = self.prepare_messages(request, history)

        # Retry covers only stream creation; chunk iteration is never retried
        async def _create_stream() -> AsyncStream[ChatCompletionChunk]:
            return await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=(
                    request.temperature
                    if request.temperature is not None
                    else self.settings.ai.temperature
                ),
                max_tokens=request.max_tokens or self.settings.ai.max_output_tokens,
                stream=True,
            )

        start_time = time.perf_counter()
        self.logger.info(
            "OpenRouter stream started",
            extra={"provider": self.provider_id, "model": model_name},
        )

        try:
            stream: AsyncStream[ChatCompletionChunk] = await self.retry(_create_stream)
        except Exception as exc:
            self.logger.error(
                "OpenRouter stream creation failed",
                extra={"provider": self.provider_id, "model": model_name, "error": str(exc)},
            )
            raise self._map_sdk_exception(exc, model_name)

        try:
            async for chunk in stream:
                choices = chunk.choices
                if not choices:
                    # Empty chunk — skip silently
                    continue

                choice = choices[0]
                finish_reason = choice.finish_reason

                # Graceful exit on any terminal finish reason
                if finish_reason in ("stop", "length", "content_filter", "tool_calls"):
                    break

                delta = choice.delta
                if delta is None:
                    # None delta — skip silently
                    continue

                delta_content = delta.content
                if delta_content:
                    yield delta_content

        except asyncio.CancelledError:
            # Client disconnected or task cancelled — propagate cleanly
            self.logger.warning(
                "OpenRouter stream cancelled",
                extra={"provider": self.provider_id, "model": model_name},
            )
            raise
        except Exception as exc:
            self.logger.error(
                "OpenRouter stream iteration error",
                extra={"provider": self.provider_id, "model": model_name, "error": str(exc)},
            )
            raise self._map_sdk_exception(exc, model_name)
        finally:
            # Always release the underlying connection — no leaks on any exit path
            await stream.close()
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            self.logger.info(
                "OpenRouter stream completed",
                extra={
                    "provider": self.provider_id,
                    "model": model_name,
                    "latency_ms": latency_ms,
                },
            )

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        """Perform a quick health ping test against OpenRouter.

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
                temperature=0,
            )
            latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
            self.logger.info(
                "OpenRouter health check passed",
                extra={"provider": self.provider_id, "latency_ms": latency_ms},
            )
            return True, latency_ms, "Healthy"
        except Exception as exc:
            err_mapped = self._map_sdk_exception(exc, self.default_model)
            return False, None, f"OpenRouter health check failed: {str(err_mapped)}"

    async def startup(self) -> None:
        """Initialize client lazily during application startup."""
        try:
            self._get_client()
        except Exception as exc:
            self.logger.warning(
                "OpenRouter startup client init deferred",
                extra={"error": str(exc)},
            )

    async def shutdown(self) -> None:
        """Clean up provider resources during application shutdown.

        AsyncOpenAI.close() calls httpx.AsyncClient.aclose() internally.
        This is the correct and verified shutdown path for openai>=1.x.
        """
        if self._client is not None:
            await self._client.close()
            self._client = None
        await super().shutdown()