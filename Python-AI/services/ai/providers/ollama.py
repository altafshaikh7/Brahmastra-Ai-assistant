# services/ai/providers/ollama.py
"""Local Ollama AI Provider for Brahmastra AI.

This module implements the production-grade OllamaProvider using HTTPX,
providing text generation, streaming, token extraction, and health diagnostics
against local Ollama instances.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx

from core.config import Settings
from schemas.chat import ChatRequest, TokenUsage
from services.ai.base import BaseAIProvider
from services.ai.exceptions import (
    NetworkErrorException,
    ProviderErrorException,
    TimeoutException,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider(BaseAIProvider):
    """Local Ollama Provider via HTTP REST client."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the OllamaProvider instance.

        Args:
            settings: Centralized application configuration.
        """
        super().__init__(settings)
        self.provider_id: str = "ollama"
        self.display_name: str = "Ollama Local AI"
        self.default_model: str = "llama3"
        self.supported_models: List[str] = [
            "llama3",
            "llama3.1",
            "llama3.2",
            "mistral",
            "phi3",
            "deepseek-r1",
            "qwen2.5",
            "gemma2",
            "codellama",
        ]
        self.base_url: str = (
            str(settings.ai.base_url) if settings.ai.base_url else "http://localhost:11434"
        )

    def _get_client(self) -> httpx.AsyncClient:
        """Return singleton HTTPX AsyncClient using BaseAIProvider method."""
        return self.create_http_client(base_url=self.base_url)

    async def generate_response(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> Tuple[str, TokenUsage]:
        """Generate a complete text response and token usage stats using Ollama.

        Args:
            request: Input chat request payload.
            history: Previous conversation message history.

        Returns:
            Tuple of (response_text, token_usage_instance).
        """
        client = self._get_client()
        model_name = self.resolve_model(request)
        messages = self.prepare_messages(request, history)
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": (
                    request.temperature
                    if request.temperature is not None
                    else self.settings.ai.temperature
                ),
                "num_predict": request.max_tokens or self.settings.ai.max_output_tokens,
            },
        }

        async def _call_ollama() -> Tuple[str, TokenUsage]:
            try:
                res = await client.post("/api/chat", json=payload)
                if res.status_code != 200:
                    raise ProviderErrorException(
                        self.provider_id, res.text, status_code=res.status_code
                    )

                data = res.json()
                content = data.get("message", {}).get("content", "")
                prompt_eval_count = data.get("prompt_eval_count", 0)
                eval_count = data.get("eval_count", 0)

                usage_dict = {
                    "prompt_tokens": prompt_eval_count,
                    "completion_tokens": eval_count,
                    "total_tokens": prompt_eval_count + eval_count,
                }
                tokens = self.extract_token_usage(usage_dict)
                return content, tokens
            except httpx.TimeoutException:
                raise TimeoutException(
                    self.provider_id, float(self.settings.ai.timeout_seconds)
                )
            except httpx.RequestError as exc:
                raise NetworkErrorException(self.provider_id, str(exc))

        return await self.retry(_call_ollama)

    async def generate_stream(
        self,
        request: ChatRequest,
        history: List[Dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Stream generated token chunks using Ollama streaming API.

        Args:
            request: Input chat request payload.
            history: Previous conversation message history.

        Yields:
            Text content chunks as received.
        """
        client = self._get_client()
        model_name = self.resolve_model(request)
        messages = self.prepare_messages(request, history)
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": (
                    request.temperature
                    if request.temperature is not None
                    else self.settings.ai.temperature
                ),
                "num_predict": request.max_tokens or self.settings.ai.max_output_tokens,
            },
        }

        try:
            async with client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise ProviderErrorException(
                        self.provider_id,
                        error_body.decode("utf-8"),
                        response.status_code,
                    )

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
            raise TimeoutException(
                self.provider_id, float(self.settings.ai.timeout_seconds)
            )
        except httpx.RequestError as exc:
            raise NetworkErrorException(self.provider_id, str(exc))

    async def check_health(self) -> Tuple[bool, Optional[float], str]:
        """Perform a health ping test against local Ollama server.

        Returns:
            Tuple of (is_healthy, latency_ms, status_message).
        """
        start = time.perf_counter()
        try:
            client = self._get_client()
            res = await client.get("/api/tags")
            latency = (time.perf_counter() - start) * 1000.0
            if res.status_code == 200:
                return True, round(latency, 2), "Healthy"
            return False, None, f"Status code {res.status_code}"
        except Exception as exc:
            return False, None, f"Ollama ping failed: {str(exc)}"
