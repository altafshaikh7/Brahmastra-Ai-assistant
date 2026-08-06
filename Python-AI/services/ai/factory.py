# services/ai/factory.py
"""Factory for instantiating and caching singleton AI provider strategies.

This module implements a thread-safe and async-safe AIProviderFactory that lazily
initializes and caches BaseAIProvider singletons for Gemini, Groq, OpenAI,
OpenRouter, and Ollama providers.
"""

from __future__ import annotations

import asyncio
import importlib
import threading
from typing import ClassVar

from core.config import Settings, get_settings
from services.ai.base import BaseAIProvider
from services.ai.exceptions import InvalidModelException
from utils.logger import get_logger

logger = get_logger(__name__)


class AIProviderFactory:
    """Thread-safe and async-safe factory for AI Provider singletons."""

    _instances: ClassVar[dict[str, BaseAIProvider]] = {}
    _lock: threading.Lock = threading.Lock()
    _async_lock: asyncio.Lock | None = None

    _registered_classes: ClassVar[dict[str, type[BaseAIProvider]]] = {}
    _provider_map: ClassVar[dict[str, str]] = {
        "gemini": "services.ai.providers.gemini.GeminiProvider",
        "groq": "services.ai.providers.groq.GroqProvider",
        "openai": "services.ai.providers.openai.OpenAIProvider",
        "openrouter": "services.ai.providers.openrouter.OpenRouterProvider",
        "ollama": "services.ai.providers.ollama.OllamaProvider",
    }

    @classmethod
    def _get_async_lock(cls) -> asyncio.Lock:
        """Lazy accessor for asyncio.Lock to avoid event-loop binding issues."""
        if cls._async_lock is None:
            cls._async_lock = asyncio.Lock()
        return cls._async_lock

    @classmethod
    def _get_provider_class(cls, target: str) -> type[BaseAIProvider]:
        """Dynamically load and cache provider strategy class.

        Args:
            target: Provider slug.

        Returns:
            Type[BaseAIProvider] class object.

        Raises:
            InvalidModelException: If provider class cannot be loaded or found.
        """
        if target in cls._registered_classes:
            return cls._registered_classes[target]

        import_path = cls._provider_map.get(target)
        if not import_path:
            logger.error("Unknown AI provider requested", extra={"provider": target})
            raise InvalidModelException(model="N/A", provider=target)

        module_path, class_name = import_path.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_path)
            cls_obj = getattr(mod, class_name)
            cls._registered_classes[target] = cls_obj
            return cls_obj
        except Exception as exc:
            logger.error(
                "Failed to import provider class",
                extra={"provider": target, "path": import_path, "error": str(exc)},
            )
            raise InvalidModelException(model="N/A", provider=target)

    @classmethod
    def get_provider(
        cls,
        provider_id: str | None = None,
        settings: Settings | None = None,
    ) -> BaseAIProvider:
        """Get or initialize singleton instance of requested AI provider.

        Args:
            provider_id: Slug identifier of provider ('gemini', 'groq', etc.).
            settings: Optional app settings instance.

        Returns:
            BaseAIProvider singleton instance.

        Raises:
            InvalidModelException: If provider_id is unsupported.
        """
        cfg = settings or get_settings()
        target = (provider_id or cfg.ai.provider or "gemini").lower().strip()

        if target not in cls._instances:
            with cls._lock:
                if target not in cls._instances:
                    provider_cls = cls._get_provider_class(target)
                    logger.info(
                        "Instantiating provider singleton", extra={"provider": target}
                    )
                    cls._instances[target] = provider_cls(cfg)

        return cls._instances[target]

    @classmethod
    async def get_provider_async(
        cls,
        provider_id: str | None = None,
        settings: Settings | None = None,
    ) -> BaseAIProvider:
        """Async-safe accessor for provider singleton."""
        async_lock = cls._get_async_lock()
        async with async_lock:
            return cls.get_provider(provider_id=provider_id, settings=settings)

    @classmethod
    def register_provider(
        cls,
        provider_id: str,
        provider_cls: type[BaseAIProvider],
    ) -> None:
        """Register a new provider strategy dynamically."""
        with cls._lock:
            slug = provider_id.lower().strip()
            cls._registered_classes[slug] = provider_cls
            logger.info("Registered provider class", extra={"provider": slug})

    @classmethod
    def list_supported_providers(cls) -> list[str]:
        """Return list of supported provider slugs."""
        return list(cls._provider_map.keys())

    @classmethod
    def get_all_instantiated(cls) -> dict[str, BaseAIProvider]:
        """Return dict of currently cached provider singletons."""
        with cls._lock:
            return dict(cls._instances)

    @classmethod
    async def shutdown_all(cls) -> None:
        """Shutdown all cached providers and clear the factory instance cache."""
        async_lock = cls._get_async_lock()
        async with async_lock:
            with cls._lock:
                instances = list(cls._instances.items())
                cls._instances.clear()

            for p_id, provider in instances:
                try:
                    await provider.shutdown()
                    logger.info("Shutdown provider succeeded", extra={"provider": p_id})
                except Exception as exc:
                    logger.error(
                        "Error shutting down provider",
                        extra={"provider": p_id, "error": str(exc)},
                    )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear singleton cache without shutdown hooks (for testing)."""
        with cls._lock:
            cls._instances.clear()
            cls._registered_classes.clear()
