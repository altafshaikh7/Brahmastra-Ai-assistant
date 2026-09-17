"""services/embedding_service.py

Real embedding service for Brahmastra AI.

Generates semantic embeddings using the configured AI provider.
Currently supports:
  - Google Gemini text-embedding-004 (via google-genai SDK)
  - OpenAI text-embedding-3-small (via httpx)
  - Groq (no native embedding API — falls back to TF-IDF hash)

Falls back gracefully to a deterministic sparse TF-IDF hash vector when
the embedding provider is unavailable so the system is always usable.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

import httpx

from core.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Embedding dimension returned when the provider supports real embeddings.
GEMINI_EMBED_DIM = 768
OPENAI_EMBED_DIM = 1536
FALLBACK_EMBED_DIM = 256



async def _embed_gemini(texts: list[str], api_key: str) -> list[list[float]] | None:
    """Generate embeddings using Google Gemini text-embedding-004."""
    try:
        from google import genai  # type: ignore[import]

        client = genai.Client(api_key=api_key)

        loop = __import__("asyncio").get_running_loop()

        def _call() -> list[list[float]]:
            results = []
            for text in texts:
                resp = client.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                # resp.embeddings is a list[ContentEmbedding], each has .values
                embedding = resp.embeddings[0].values if resp.embeddings else []
                results.append(list(embedding))
            return results

        return await loop.run_in_executor(None, _call)
    except Exception as exc:
        logger.warning(
            "Gemini embedding failed",
            extra={"error": str(exc)},
        )
        return None


async def _embed_openai(
    texts: list[str], api_key: str, base_url: str = "https://api.openai.com/v1"
) -> list[list[float]] | None:
    """Generate embeddings via OpenAI-compatible /embeddings endpoint."""
    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        ) as client:
            resp = await client.post(
                "/embeddings",
                json={"input": texts, "model": "text-embedding-3-small"},
            )
            if resp.status_code != 200:
                logger.warning("OpenAI embedding API error", extra={"status": resp.status_code})
                return None
            data = resp.json()
            embeddings_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in embeddings_data]
    except Exception as exc:
        logger.warning("OpenAI embedding request failed", extra={"error": str(exc)})
        return None


class EmbeddingService:
    """Provider-agnostic embedding service.

    Call ``generate(texts)`` to receive real semantic embeddings when the
    active provider supports them, or a deterministic fallback vector
    otherwise.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def generate(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Returns a list of float vectors, one per input text.
        On provider failure, returns deterministic fallback vectors.
        """
        if not texts:
            return []

        # Clean texts
        clean = [t.strip() for t in texts]

        provider = self._settings.ai.provider.lower()
        api_key = (
            self._settings.ai.api_key.get_secret_value()
            if self._settings.ai.api_key
            else None
        )

        result: list[list[float]] | None = None

        if provider == "gemini" and api_key:
            result = await _embed_gemini(clean, api_key)
        elif provider in {"openai", "openrouter"} and api_key:
            base_url = (
                "https://openrouter.ai/api/v1"
                if provider == "openrouter"
                else "https://api.openai.com/v1"
            )
            result = await _embed_openai(clean, api_key, base_url=base_url)
        # Groq and Ollama do not have native embedding APIs.

        if result is None or len(result) != len(clean):
            raise Exception(f"Embedding generation failed for provider '{provider}'. Required API keys might be missing.")

        return result

    async def generate_single(self, text: str) -> list[float]:
        """Convenience wrapper for single-text embedding."""
        results = await self.generate([text])
        return results[0] if results else []


_embedding_service_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Singleton accessor for EmbeddingService."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
