# services/ai_service.py
"""Multi-provider AI Service for Brahmastra AI.

This module implements a clean, SOLID-compliant, async-first AI orchestration layer supporting
Google Gemini, Groq, OpenAI, OpenRouter, and Ollama providers with singleton client reuse,
resilient retry logic, streaming execution, token extraction, structured logging, MongoDB
conversation memory persistence, and standardized exception handling.
"""

from __future__ import annotations

import abc
import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Type

import httpx

from core.config import Settings, get_settings
from core.exceptions import ApplicationError, ErrorCode
from dependencies.database import get_database
from schemas.chat import (
    AIHealthResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ModelsResponse,
    ProviderInfo,
    ProvidersResponse,
    TokenUsage,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Custom Exception Hierarchy (Task 13)
# =============================================================================


class AIServiceException(ApplicationError):
    """Base exception for all AI Service failures."""

    def __init__(
        self,
        message: str = "AI service error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.APPLICATION_ERROR,
            status_code=status_code,
            details=details,
        )


class APIKeyMissingException(AIServiceException):
    """Raised when a provider API key is missing or invalid."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            message=f"API key for provider '{provider}' is missing or unconfigured.",
            status_code=401,
            details={"provider": provider},
        )


class TimeoutException(AIServiceException):
    """Raised when an AI provider request times out."""

    def __init__(self, provider: str, timeout_seconds: float) -> None:
        super().__init__(
            message=f"AI request to provider '{provider}' timed out after {timeout_seconds} seconds.",
            status_code=504,
            details={"provider": provider, "timeout_seconds": timeout_seconds},
        )


class RateLimitException(AIServiceException):
    """Raised when an AI provider rate limit is exceeded."""

    def __init__(self, provider: str, details: Optional[str] = None) -> None:
        super().__init__(
            message=f"Rate limit exceeded for AI provider '{provider}'. {details or ''}".strip(),
            status_code=429,
            details={"provider": provider, "error": details},
        )


class NetworkErrorException(AIServiceException):
    """Raised when a network communication error occurs with an AI provider."""

    def __init__(self, provider: str, details: str) -> None:
        super().__init__(
            message=f"Network error communicating with AI provider '{provider}': {details}",
            status_code=502,
            details={"provider": provider, "network_error": details},
        )


class ProviderErrorException(AIServiceException):
    """Raised when an AI provider returns an API error response."""

    def __init__(self, provider: str, error_message: str, status_code: int = 502) -> None:
        super().__init__(
            message=f"AI provider '{provider}' error: {error_message}",
            status_code=status_code,
            details={"provider": provider, "error_message": error_message},
        )


class InvalidModelException(AIServiceException):
    """Raised when an unsupported or invalid model is requested."""

    def __init__(self, model: str, provider: str) -> None:
        super().__init__(
            message=f"Model '{model}' is invalid or unsupported for provider '{provider}'.",
            status_code=400,
            details={"model": model, "provider": provider},
        )


# =============================================================================
# Abstract Base Provider
# =============================================================================


class BaseAIProvider(abc.ABC):
    """Abstract Base Class for all AI Providers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider_id: str = "base"
        self.display_name: str = "Base Provider"
        self.default_model: str = ""
        self.supported_models: List[str] = []

    @abc.abstractmethod
    async def generate_response(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> Tuple[str, TokenUsage]:
        """Generate a complete text response and token usage stats."""
        pass

    @abc.abstractmethod
    async def generate_stream(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming SSE response token stream."""
        pass

    @abc.abstractmethod
    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        """Perform a quick health ping test. Returns (is_healthy, latency_ms, status_message)."""
        pass


# =============================================================================
# Provider Implementations
# =============================================================================


class GeminiProvider(BaseAIProvider):
    """Google Gemini Provider using latest google.genai SDK."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.provider_id = "gemini"
        self.display_name = "Google Gemini"
        self.default_model = (
            settings.ai.gemini_model
            or (settings.ai.model_name if settings.ai.provider == "gemini" else "gemini-2.5-flash")
        )
        self.supported_models = [
            "gemini-2.5-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash-exp",
        ]
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Singleton accessor for Google GenAI Client."""
        if self._client is None:
            api_key = self.settings.ai.api_key.get_secret_value() if self.settings.ai.api_key else None
            if not api_key:
                raise APIKeyMissingException(self.provider_id)
            try:
                from google import genai
                self._client = genai.Client(api_key=api_key)
            except Exception as exc:
                logger.error("Failed to initialize Google GenAI client", extra={"error": str(exc)})
                raise ProviderErrorException(self.provider_id, f"Client initialization failed: {str(exc)}")
        return self._client

    def _resolve_model(self, requested_model: Optional[str]) -> str:
        model = requested_model or self.default_model
        return model

    async def generate_response(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> Tuple[str, TokenUsage]:
        client = self._get_client()
        model_name = self._resolve_model(None)

        prompt_parts = []
        if request.system_prompt:
            prompt_parts.append(f"System: {request.system_prompt}\n")
        for msg in conversation_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            prompt_parts.append(f"{role}: {msg['content']}")
        prompt_parts.append(f"User: {request.message}")

        full_prompt = "\n".join(prompt_parts)

        def _call_gemini():
            return client.models.generate_content(
                model=model_name,
                contents=full_prompt,
            )

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, _call_gemini)
            response_text = response.text or ""
            
            # Extract token stats if present
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) if hasattr(response, "usage_metadata") and response.usage_metadata else len(full_prompt) // 4
            completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) if hasattr(response, "usage_metadata") and response.usage_metadata else len(response_text) // 4
            total_tokens = getattr(response.usage_metadata, "total_token_count", 0) if hasattr(response, "usage_metadata") and response.usage_metadata else (prompt_tokens + completion_tokens)

            tokens = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            return response_text, tokens
        except Exception as exc:
            logger.error("Gemini API call failed", extra={"error": str(exc), "model": model_name})
            raise ProviderErrorException(self.provider_id, str(exc))

    async def generate_stream(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        model_name = self._resolve_model(None)

        prompt_parts = []
        if request.system_prompt:
            prompt_parts.append(f"System: {request.system_prompt}\n")
        for msg in conversation_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            prompt_parts.append(f"{role}: {msg['content']}")
        prompt_parts.append(f"User: {request.message}")

        full_prompt = "\n".join(prompt_parts)

        def _call_stream():
            return client.models.generate_content_stream(
                model=model_name,
                contents=full_prompt,
            )

        try:
            loop = asyncio.get_running_loop()
            response_stream = await loop.run_in_executor(None, _call_stream)
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.error("Gemini streaming call failed", extra={"error": str(exc)})
            raise ProviderErrorException(self.provider_id, str(exc))

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        start = time.perf_counter()
        try:
            client = self._get_client()
            def _ping():
                return client.models.generate_content(
                    model=self.default_model,
                    contents="ping",
                )
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _ping)
            latency = (time.perf_counter() - start) * 1000.0
            return True, round(latency, 2), "Healthy"
        except Exception as exc:
            return False, None, f"Gemini ping failed: {str(exc)}"


class GroqProvider(BaseAIProvider):
    """Groq Provider using AsyncGroq client."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.provider_id = "groq"
        self.display_name = "Groq AI"
        self.default_model = "llama-3.3-70b-versatile"
        self.supported_models = [
            "llama-3.3-70b-versatile",
            "deepseek-r1-distill-llama-70b",
            "qwen/qwen3-32b",
            "mixtral-8x7b-32768",
        ]
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        if self._client is None:
            api_key = self.settings.ai.api_key.get_secret_value() if self.settings.ai.api_key else None
            if not api_key:
                raise APIKeyMissingException(self.provider_id)
            try:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=api_key)
            except Exception as exc:
                logger.error("Failed to initialize Groq client", extra={"error": str(exc)})
                raise ProviderErrorException(self.provider_id, f"Groq client init failed: {str(exc)}")
        return self._client

    def _prepare_messages(self, request: ChatRequest, conversation_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": request.message})
        return messages

    async def generate_response(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> Tuple[str, TokenUsage]:
        client = self._get_client()
        model_name = request.max_tokens or self.default_model
        model_name = self.default_model
        messages = self._prepare_messages(request, conversation_history)

        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=request.temperature if request.temperature is not None else self.settings.ai.temperature,
                max_tokens=request.max_tokens or self.settings.ai.max_output_tokens,
            )
            content = response.choices[0].message.content or ""
            usage = getattr(response, "usage", None)
            tokens = TokenUsage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
            )
            return content, tokens
        except Exception as exc:
            logger.error("Groq API call failed", extra={"error": str(exc), "model": model_name})
            raise ProviderErrorException(self.provider_id, str(exc))

    async def generate_stream(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        messages = self._prepare_messages(request, conversation_history)

        try:
            stream = await client.chat.completions.create(
                model=self.default_model,
                messages=messages,
                temperature=request.temperature if request.temperature is not None else self.settings.ai.temperature,
                max_tokens=request.max_tokens or self.settings.ai.max_output_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:
            logger.error("Groq streaming call failed", extra={"error": str(exc)})
            raise ProviderErrorException(self.provider_id, str(exc))

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        start = time.perf_counter()
        try:
            client = self._get_client()
            await client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            latency = (time.perf_counter() - start) * 1000.0
            return True, round(latency, 2), "Healthy"
        except Exception as exc:
            return False, None, f"Groq ping failed: {str(exc)}"


class OpenAIProvider(BaseAIProvider):
    """OpenAI Provider via singleton HTTPX client."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.provider_id = "openai"
        self.display_name = "OpenAI"
        self.default_model = "gpt-4o"
        self.supported_models = ["gpt-4.1", "gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4o-mini"]
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            api_key = self.settings.ai.api_key.get_secret_value() if self.settings.ai.api_key else None
            if not api_key:
                raise APIKeyMissingException(self.provider_id)
            self._http_client = httpx.AsyncClient(
                base_url="https://api.openai.com/v1",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(float(self.settings.ai.timeout_seconds)),
            )
        return self._http_client

    def _prepare_messages(self, request: ChatRequest, conversation_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": request.message})
        return messages

    async def generate_response(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> Tuple[str, TokenUsage]:
        client = self._get_http_client()
        messages = self._prepare_messages(request, conversation_history)
        payload = {
            "model": self.default_model,
            "messages": messages,
            "temperature": request.temperature if request.temperature is not None else self.settings.ai.temperature,
            "max_tokens": request.max_tokens or self.settings.ai.max_output_tokens,
        }

        try:
            res = await client.post("/chat/completions", json=payload)
            if res.status_code == 401:
                raise APIKeyMissingException(self.provider_id)
            elif res.status_code == 429:
                raise RateLimitException(self.provider_id, res.text)
            elif res.status_code != 200:
                raise ProviderErrorException(self.provider_id, res.text, status_code=res.status_code)

            data = res.json()
            content = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage", {})
            tokens = TokenUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
            return content, tokens
        except httpx.TimeoutException:
            raise TimeoutException(self.provider_id, float(self.settings.ai.timeout_seconds))
        except httpx.RequestError as exc:
            raise NetworkErrorException(self.provider_id, str(exc))

    async def generate_stream(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        client = self._get_http_client()
        messages = self._prepare_messages(request, conversation_history)
        payload = {
            "model": self.default_model,
            "messages": messages,
            "temperature": request.temperature if request.temperature is not None else self.settings.ai.temperature,
            "max_tokens": request.max_tokens or self.settings.ai.max_output_tokens,
            "stream": True,
        }

        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise ProviderErrorException(self.provider_id, error_body.decode("utf-8"), response.status_code)

                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_json = json.loads(data_str)
                            delta = chunk_json["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue
        except httpx.TimeoutException:
            raise TimeoutException(self.provider_id, float(self.settings.ai.timeout_seconds))
        except httpx.RequestError as exc:
            raise NetworkErrorException(self.provider_id, str(exc))

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        start = time.perf_counter()
        try:
            client = self._get_http_client()
            res = await client.get("/models")
            latency = (time.perf_counter() - start) * 1000.0
            if res.status_code == 200:
                return True, round(latency, 2), "Healthy"
            return False, None, f"Status code {res.status_code}"
        except Exception as exc:
            return False, None, f"OpenAI health check failed: {str(exc)}"


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter Provider supporting any model via OpenRouter API."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.provider_id = "openrouter"
        self.display_name = "OpenRouter"
        self.default_model = settings.ai.openrouter_model or "meta-llama/llama-3.3-70b-instruct"
        self.supported_models = [
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-r1",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "google/gemini-2.5-flash",
        ]
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            api_key = self.settings.ai.api_key.get_secret_value() if self.settings.ai.api_key else None
            if not api_key:
                raise APIKeyMissingException(self.provider_id)
            self._http_client = httpx.AsyncClient(
                base_url="https://openrouter.ai/api/v1",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/brahmastra-ai",
                    "X-Title": "Brahmastra AI",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(float(self.settings.ai.timeout_seconds)),
            )
        return self._http_client

    def _prepare_messages(self, request: ChatRequest, conversation_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": request.message})
        return messages

    async def generate_response(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> Tuple[str, TokenUsage]:
        client = self._get_http_client()
        messages = self._prepare_messages(request, conversation_history)
        payload = {
            "model": self.default_model,
            "messages": messages,
            "temperature": request.temperature if request.temperature is not None else self.settings.ai.temperature,
            "max_tokens": request.max_tokens or self.settings.ai.max_output_tokens,
        }

        try:
            res = await client.post("/chat/completions", json=payload)
            if res.status_code == 401:
                raise APIKeyMissingException(self.provider_id)
            elif res.status_code == 429:
                raise RateLimitException(self.provider_id, res.text)
            elif res.status_code != 200:
                raise ProviderErrorException(self.provider_id, res.text, status_code=res.status_code)

            data = res.json()
            content = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage", {})
            tokens = TokenUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
            return content, tokens
        except httpx.TimeoutException:
            raise TimeoutException(self.provider_id, float(self.settings.ai.timeout_seconds))
        except httpx.RequestError as exc:
            raise NetworkErrorException(self.provider_id, str(exc))

    async def generate_stream(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        client = self._get_http_client()
        messages = self._prepare_messages(request, conversation_history)
        payload = {
            "model": self.default_model,
            "messages": messages,
            "temperature": request.temperature if request.temperature is not None else self.settings.ai.temperature,
            "max_tokens": request.max_tokens or self.settings.ai.max_output_tokens,
            "stream": True,
        }

        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise ProviderErrorException(self.provider_id, error_body.decode("utf-8"), response.status_code)

                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_json = json.loads(data_str)
                            delta = chunk_json["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue
        except httpx.TimeoutException:
            raise TimeoutException(self.provider_id, float(self.settings.ai.timeout_seconds))
        except httpx.RequestError as exc:
            raise NetworkErrorException(self.provider_id, str(exc))

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        start = time.perf_counter()
        try:
            client = self._get_http_client()
            res = await client.get("/auth/key")
            latency = (time.perf_counter() - start) * 1000.0
            if res.status_code == 200:
                return True, round(latency, 2), "Healthy"
            return False, None, f"Status code {res.status_code}"
        except Exception as exc:
            return False, None, f"OpenRouter health check failed: {str(exc)}"


class OllamaProvider(BaseAIProvider):
    """Local Ollama Provider via HTTP REST client."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.provider_id = "ollama"
        self.display_name = "Ollama Local AI"
        self.default_model = "llama3"
        self.supported_models = ["llama3", "phi3", "mistral", "deepseek"]
        self.base_url = str(settings.ai.base_url) if settings.ai.base_url else "http://localhost:11434"
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(float(self.settings.ai.timeout_seconds)),
            )
        return self._http_client

    def _prepare_messages(self, request: ChatRequest, conversation_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": request.message})
        return messages

    async def generate_response(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> Tuple[str, TokenUsage]:
        client = self._get_http_client()
        messages = self._prepare_messages(request, conversation_history)
        payload = {
            "model": self.default_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature if request.temperature is not None else self.settings.ai.temperature,
                "num_predict": request.max_tokens or self.settings.ai.max_output_tokens,
            },
        }

        try:
            res = await client.post("/api/chat", json=payload)
            if res.status_code != 200:
                raise ProviderErrorException(self.provider_id, res.text, status_code=res.status_code)

            data = res.json()
            content = data.get("message", {}).get("content", "")
            prompt_eval_count = data.get("prompt_eval_count", 0)
            eval_count = data.get("eval_count", 0)
            tokens = TokenUsage(
                prompt_tokens=prompt_eval_count,
                completion_tokens=eval_count,
                total_tokens=prompt_eval_count + eval_count,
            )
            return content, tokens
        except httpx.TimeoutException:
            raise TimeoutException(self.provider_id, float(self.settings.ai.timeout_seconds))
        except httpx.RequestError as exc:
            raise NetworkErrorException(self.provider_id, str(exc))

    async def generate_stream(
        self,
        request: ChatRequest,
        conversation_history: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        client = self._get_http_client()
        messages = self._prepare_messages(request, conversation_history)
        payload = {
            "model": self.default_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": request.temperature if request.temperature is not None else self.settings.ai.temperature,
                "num_predict": request.max_tokens or self.settings.ai.max_output_tokens,
            },
        }

        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise ProviderErrorException(self.provider_id, error_body.decode("utf-8"), response.status_code)

                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            chunk_json = json.loads(line)
                            delta = chunk_json.get("message", {}).get("content", "")
                            if delta:
                                yield delta
                        except json.JSONDecodeError:
                            continue
        except httpx.TimeoutException:
            raise TimeoutException(self.provider_id, float(self.settings.ai.timeout_seconds))
        except httpx.RequestError as exc:
            raise NetworkErrorException(self.provider_id, str(exc))

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        start = time.perf_counter()
        try:
            client = self._get_http_client()
            res = await client.get("/api/tags")
            latency = (time.perf_counter() - start) * 1000.0
            if res.status_code == 200:
                return True, round(latency, 2), "Healthy"
            return False, None, f"Status code {res.status_code}"
        except Exception as exc:
            return False, None, f"Ollama ping failed: {str(exc)}"


# =============================================================================
# Provider Factory (Task 1 & Task 15)
# =============================================================================


class AIProviderFactory:
    """Factory for instantiating and caching singleton AI provider strategies."""

    _instances: Dict[str, BaseAIProvider] = {}
    _provider_map: Dict[str, Type[BaseAIProvider]] = {
        "gemini": GeminiProvider,
        "groq": GroqProvider,
        "openai": OpenAIProvider,
        "openrouter": OpenRouterProvider,
        "ollama": OllamaProvider,
    }

    @classmethod
    def get_provider(cls, provider_id: Optional[str] = None, settings: Optional[Settings] = None) -> BaseAIProvider:
        """Get or initialize singleton instance of requested AI provider."""
        cfg = settings or get_settings()
        target_provider = (provider_id or cfg.ai.provider or "gemini").lower()

        if target_provider not in cls._provider_map:
            raise InvalidModelException(model="N/A", provider=target_provider)

        if target_provider not in cls._instances:
            provider_cls = cls._provider_map[target_provider]
            cls._instances[target_provider] = provider_cls(cfg)
            logger.info("Initialized AI Provider singleton", extra={"provider": target_provider})

        return cls._instances[target_provider]

    @classmethod
    def get_all_providers_info(cls, settings: Optional[Settings] = None) -> List[ProviderInfo]:
        """Enumerate information for all supported AI providers."""
        cfg = settings or get_settings()
        active_provider = cfg.ai.provider.lower()
        provider_infos = []

        for pid in cls._provider_map.keys():
            provider_inst = cls.get_provider(pid, cfg)
            provider_infos.append(
                ProviderInfo(
                    id=provider_inst.provider_id,
                    name=provider_inst.display_name,
                    default_model=provider_inst.default_model,
                    supported_models=provider_inst.supported_models,
                    is_active=(pid == active_provider),
                )
            )
        return provider_infos


# =============================================================================
# Main AI Service Class (Task 1, 9, 10, 11, 12, 13, 14, 15)
# =============================================================================


class AIService:
    """Core AI Service orchestrating chat completion, streaming, and conversation memory."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def _load_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Fetch past messages for a conversation ID from MongoDB."""
        try:
            db = get_database()
            doc = await db.conversations.find_one({"conversation_id": conversation_id})
            if doc and "messages" in doc:
                return [{"role": m["role"], "content": m["content"]} for m in doc["messages"]]
        except Exception as exc:
            logger.warning(
                "Failed to fetch conversation history from MongoDB",
                extra={"conversation_id": conversation_id, "error": str(exc)},
            )
        return []

    async def _save_conversation_messages(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Persist new user and assistant messages into MongoDB conversation history."""
        try:
            db = get_database()
            now = time.time()
            new_msgs = [
                {"role": "user", "content": user_message, "timestamp": now},
                {"role": "assistant", "content": assistant_message, "timestamp": now},
            ]
            await db.conversations.update_one(
                {"conversation_id": conversation_id},
                {
                    "$push": {"messages": {"$each": new_msgs}},
                    "$setOnInsert": {"created_at": now},
                    "$set": {"updated_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.warning(
                "Failed to save conversation message to MongoDB",
                extra={"conversation_id": conversation_id, "error": str(exc)},
            )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Execute a non-streaming AI completion request with retries and logging."""
        start_time = time.perf_counter()
        provider = AIProviderFactory.get_provider(settings=self.settings)
        conversation_id = request.conversation_id or f"conv_{int(time.time() * 1000)}"

        logger.info(
            "Executing AI Chat Request",
            extra={
                "provider": provider.provider_id,
                "model": provider.default_model,
                "conversation_id": conversation_id,
                "stream": request.stream,
            },
        )

        history = await self._load_conversation_history(conversation_id)

        # Retry loop for resiliency (Task 14)
        attempts = self.settings.ai.retry_attempts
        backoff = self.settings.ai.retry_backoff_seconds
        last_exception: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                response_text, tokens = await provider.generate_response(request, history)
                execution_time = round(time.perf_counter() - start_time, 4)

                # Persist to MongoDB memory (Task 10)
                await self._save_conversation_messages(conversation_id, request.message, response_text)

                logger.info(
                    "AI Chat Request Completed Successfully",
                    extra={
                        "provider": provider.provider_id,
                        "model": provider.default_model,
                        "execution_time_seconds": execution_time,
                        "total_tokens": tokens.total_tokens,
                        "conversation_id": conversation_id,
                    },
                )

                return ChatResponse(
                    success=True,
                    provider=provider.provider_id,
                    model=provider.default_model,
                    response=response_text,
                    tokens=tokens,
                    execution_time=execution_time,
                    conversation_id=conversation_id,
                )
            except (RateLimitException, NetworkErrorException, TimeoutException) as exc:
                last_exception = exc
                if attempt < attempts:
                    await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    continue
                break
            except Exception as exc:
                last_exception = exc
                break

        execution_time = round(time.perf_counter() - start_time, 4)
        logger.error(
            "AI Chat Request Failed",
            extra={
                "provider": provider.provider_id,
                "execution_time_seconds": execution_time,
                "error": str(last_exception),
            },
        )
        if isinstance(last_exception, AIServiceException):
            raise last_exception
        raise ProviderErrorException(provider.provider_id, str(last_exception or "Unknown error"))

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Execute a streaming SSE AI completion request."""
        provider = AIProviderFactory.get_provider(settings=self.settings)
        conversation_id = request.conversation_id or f"conv_{int(time.time() * 1000)}"

        logger.info(
            "Executing AI Stream Request",
            extra={
                "provider": provider.provider_id,
                "model": provider.default_model,
                "conversation_id": conversation_id,
            },
        )

        history = await self._load_conversation_history(conversation_id)
        accumulated_response: List[str] = []

        try:
            async for chunk in provider.generate_stream(request, history):
                accumulated_response.append(chunk)
                yield chunk

            full_text = "".join(accumulated_response)
            if full_text:
                await self._save_conversation_messages(conversation_id, request.message, full_text)
        except Exception as exc:
            logger.error(
                "AI Stream Request Failed",
                extra={"provider": provider.provider_id, "error": str(exc)},
            )
            if isinstance(exc, AIServiceException):
                raise exc
            raise ProviderErrorException(provider.provider_id, str(exc))

    async def get_providers(self) -> ProvidersResponse:
        """List all supported AI providers."""
        providers_info = AIProviderFactory.get_all_providers_info(self.settings)
        active_provider = self.settings.ai.provider.lower()
        return ProvidersResponse(
            active_provider=active_provider,
            providers=providers_info,
        )

    async def get_models(self) -> ModelsResponse:
        """List models supported by the currently active AI provider."""
        provider = AIProviderFactory.get_provider(settings=self.settings)
        model_infos = [
            ModelInfo(
                id=m,
                name=m,
                provider=provider.provider_id,
                context_window=128000,
            )
            for m in provider.supported_models
        ]
        return ModelsResponse(
            provider=provider.provider_id,
            models=model_infos,
        )

    async def check_health(self) -> AIHealthResponse:
        """Perform health diagnostic check on active provider."""
        provider = AIProviderFactory.get_provider(settings=self.settings)
        is_healthy, latency_ms, status_msg = await provider.check_health()
        return AIHealthResponse(
            status="ok" if is_healthy else "error",
            provider=provider.provider_id,
            model=provider.default_model,
            latency_ms=latency_ms,
            details={"message": status_msg},
        )


# =============================================================================
# Singleton Accessor (Task 15)
# =============================================================================

_ai_service_instance: Optional[AIService] = None


def get_ai_service() -> AIService:
    """Return singleton instance of AIService."""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
