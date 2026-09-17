"""services/agent_brain.py

Brahmastra AI — Full Agent Brain / Orchestration Engine.

Implements a bounded, stateful, multi-capability orchestrator that routes
each user request through the appropriate intelligence pipeline:

  1. Direct LLM response (conversational)
  2. Deterministic tool execution (calculator, current_time, etc.)
  3. Long-term memory retrieval (from Node Backend /api/memory)
  4. RAG / Document knowledge retrieval (from Node Backend /api/documents/search)
  5. Web Research (via WebResearchService)
  6. Combinations of the above

Architecture constraints:
  - Maximum MAX_AGENT_STEPS steps per request (prevents infinite loops)
  - Maximum MAX_TOOL_RETRIES retries per tool call
  - Tool timeout enforced per-call
  - Web content treated as UNTRUSTED DATA (cannot modify agent state)
  - Memory retrieval filtered by authenticated user (via Node Backend)
  - Agent state is scoped to a single request (not persisted)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from core.config import get_settings
from schemas.chat import ChatMessage, ChatRequest, ChatResponse, TokenUsage
from services.ai_service import (
    AIProviderFactory,
    AIServiceException,
    ProviderErrorException,
    RateLimitException,
    TimeoutException,
    NetworkErrorException,
    _build_tool_instructions,
    _format_tool_response,
    _is_current_time_query,
)
from services.embedding_service import get_embedding_service
from services.executor import ToolExecutor
from services.registry_service import ToolRegistryService
from services.web_research_service import get_web_research_service
from schemas.tool import ToolExecutionRequest
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_AGENT_STEPS = int(os.getenv("AGENT_MAX_STEPS", "8"))
MAX_TOOL_RETRIES = int(os.getenv("AGENT_MAX_TOOL_RETRIES", "2"))
TOOL_TIMEOUT_SECONDS = float(os.getenv("AGENT_TOOL_TIMEOUT_SECONDS", "15"))
MEMORY_TOP_K = int(os.getenv("AGENT_MEMORY_TOP_K", "5"))
RAG_TOP_K = int(os.getenv("AGENT_RAG_TOP_K", "5"))

# Node Backend URL for memory/document APIs
NODE_BACKEND_URL = os.getenv("NODE_BACKEND_URL", "http://localhost:5000")
# Internal API key for Node→Python (the reverse is not needed here, but
# we may need a shared key if we expose this internally)
NODE_BACKEND_TIMEOUT = float(os.getenv("NODE_BACKEND_TIMEOUT_SECONDS", "10"))


# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------


class AgentStatus(str, Enum):
    READY = "READY"
    THINKING = "THINKING"
    EXECUTING_TOOL = "EXECUTING_TOOL"
    RETRIEVING_MEMORY = "RETRIEVING_MEMORY"
    RETRIEVING_DOCUMENTS = "RETRIEVING_DOCUMENTS"
    RESEARCHING = "RESEARCHING"
    RESPONDING = "RESPONDING"
    ERROR = "ERROR"
    MAX_STEPS_REACHED = "MAX_STEPS_REACHED"


@dataclass
class AgentState:
    """Structured execution state for one agent request."""

    request: str
    conversation_id: str
    user_token: str | None  # JWT for Node Backend calls
    intent: str = ""
    plan: list[str] = field(default_factory=list)
    steps_taken: int = 0
    tool_retries: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)
    memory_context: str = ""
    rag_context: str = ""
    web_context: str = ""
    final_response: str = ""
    status: AgentStatus = AgentStatus.READY
    error: str | None = None
    tokens_used: TokenUsage = field(default_factory=TokenUsage)
    start_time: float = field(default_factory=time.perf_counter)

    @property
    def elapsed_seconds(self) -> float:
        return round(time.perf_counter() - self.start_time, 4)


# ---------------------------------------------------------------------------
# Intent Detection
# ---------------------------------------------------------------------------

_WEB_RESEARCH_PATTERNS = re.compile(
    r"(?:"
    r"latest\s+(?:news|information|update|release|version|data|event|development)"
    r"|what(?:'s|\s+is)\s+happening\s+(?:with|in|about|to)"
    r"|current\s+(?:news|events?|status|state\s+of)"
    r"|today'?s?\s+(?:news|price|update|event|weather)"
    r"|recent\s+(?:news|update|release|event|development|change)"
    r"|right\s+now\s+(?:in|about)"
    r"|breaking\s+news"
    r"|search\s+(?:the\s+)?(?:web|internet|online)\s+for"
    r"|(?:find|look\s+up|research)\s+(?:online|on\s+the\s+internet|on\s+the\s+web)"
    r"|(?:what|who|when|where|why|how)\s+.*?\s+in\s+(?:20[2-9]\d)"  # year references
    r")",
    re.IGNORECASE,
)

_MEMORY_PATTERNS = re.compile(
    r"(?:"
    r"(?:what|do)\s+(?:you\s+)?(?:know|remember)\s+about\s+me"
    r"|(?:my\s+)?name\s+is\b"
    r"|i\s+(?:told|said|mentioned|shared|prefer|like|dislike|hate|love)\s+"
    r"|remember\s+(?:that|when|this)"
    r"|(?:my|our)\s+(?:preference|project|goal|setting|instruction|rule)"
    r"|recall\s+(?:what|that)"
    r"|what\s+(?:did|have)\s+i\s+(?:say|tell|share|mention)"
    r"|(?:my|me)\s+(?:profile|information|data|details)"
    r")",
    re.IGNORECASE,
)

_RAG_PATTERNS = re.compile(
    r"(?:"
    r"(?:in|from|based\s+on|according\s+to|per)\s+(?:my|the|that)\s+document"
    r"|(?:in|from)\s+(?:my|the)\s+(?:file|pdf|upload|notes?|doc)"
    r"|(?:what|according\s+to)\s+(?:the|my)\s+(?:uploaded|attached|provided)\s+(?:document|file)"
    r"|search\s+(?:my|the)\s+documents?"
    r"|(?:find|look\s+(?:up|in))\s+(?:my|the)\s+documents?"
    r"|(?:from|in)\s+(?:my|the)\s+(?:knowledge\s+base|uploaded\s+files?)"
    r")",
    re.IGNORECASE,
)

_CONVERSATIONAL_PATTERNS = re.compile(
    r"^(?:"
    r"(?:hello|hi|hey|greetings|howdy)\b"
    r"|(?:thank(?:s|\s+you))\b"
    r"|(?:bye|goodbye|see\s+you)\b"
    r"|(?:how\s+are\s+you)\b"
    r"|(?:what(?:'s|\s+is)\s+(?:up|good))\b"
    r"|(?:nice\s+to\s+(?:meet|talk))\b"
    r")\W*$",
    re.IGNORECASE,
)


def _classify_intent(message: str, available_tool_names: set[str]) -> dict[str, bool]:
    """Classify which capabilities this message requires."""
    msg = message.strip()

    return {
        "needs_web_research": bool(_WEB_RESEARCH_PATTERNS.search(msg)),
        "needs_memory": bool(_MEMORY_PATTERNS.search(msg)),
        "needs_rag": bool(_RAG_PATTERNS.search(msg)),
        "is_conversational": bool(_CONVERSATIONAL_PATTERNS.match(msg)),
    }


# ---------------------------------------------------------------------------
# Node Backend client (for memory and RAG retrieval)
# ---------------------------------------------------------------------------


async def _fetch_relevant_memories(query: str, user_token: str) -> str:
    """Query Node Backend /api/memory?query=... and return formatted context."""
    if not user_token:
        return ""
    try:
        async with httpx.AsyncClient(timeout=NODE_BACKEND_TIMEOUT) as client:
            resp = await client.get(
                f"{NODE_BACKEND_URL}/api/memory",
                params={"query": query, "limit": MEMORY_TOP_K},
                headers={"Authorization": f"Bearer {user_token}"},
            )
            if resp.status_code != 200:
                logger.warning("Memory fetch returned non-200", extra={"status": resp.status_code})
                return ""
            data = resp.json()
            memories = data.get("data", [])
            if not memories:
                return ""

            lines = ["=== RELEVANT LONG-TERM MEMORY (TRUSTED SYSTEM DATA) ==="]
            for m in memories[:MEMORY_TOP_K]:
                cat = m.get("category", "")
                content = m.get("content", "")
                if content:
                    lines.append(f"[{cat}] {content}")
            lines.append("=== END MEMORY ===")
            return "\n".join(lines)
    except Exception as exc:
        logger.warning("Memory retrieval failed", extra={"error": str(exc)})
        return ""


async def _fetch_rag_context(query: str, user_token: str) -> str:
    """Query Node Backend /api/documents/search and return formatted context."""
    if not user_token:
        return ""
    try:
        async with httpx.AsyncClient(timeout=NODE_BACKEND_TIMEOUT) as client:
            resp = await client.post(
                f"{NODE_BACKEND_URL}/api/documents/search",
                json={"query": query, "topK": RAG_TOP_K},
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            chunks = data.get("data", [])
            if not chunks:
                return ""

            lines = ["=== DOCUMENT KNOWLEDGE (TRUSTED USER DOCUMENTS) ==="]
            for chunk in chunks[:RAG_TOP_K]:
                fname = chunk.get("filename", "unknown")
                content = chunk.get("content", "")
                score = chunk.get("score", 0)
                if content:
                    lines.append(f"[Source: {fname} | Score: {score:.2f}]")
                    lines.append(content[:500])
                    lines.append("")
            lines.append("=== END DOCUMENTS ===")
            return "\n".join(lines)
    except Exception as exc:
        logger.warning("RAG retrieval failed", extra={"error": str(exc)})
        return ""


# ---------------------------------------------------------------------------
# Context Assembly
# ---------------------------------------------------------------------------


def _assemble_system_prompt(
    state: AgentState,
    tools_list: list[Any],
    include_tools: bool,
) -> str:
    """Assemble the complete system prompt from trusted and untrusted sources.

    Priority / order:
      1. Core system instructions (TRUSTED)
      2. User memory context (TRUSTED — from authenticated backend)
      3. Document/RAG context (TRUSTED — user's own documents)
      4. Web research context (UNTRUSTED — clearly labelled)
      5. Tool instructions (if needed)
    """
    sections: list[str] = []

    sections.append(
        "You are BRAHMASTRA AI, an advanced AI assistant. "
        "You are helpful, accurate, and honest. "
        "When you don't know something, say so clearly. "
        "Never fabricate facts, citations, or tool results."
    )

    if state.memory_context:
        sections.append(state.memory_context)

    if state.rag_context:
        sections.append(state.rag_context)

    if state.web_context:
        sections.append(state.web_context)

    if include_tools and tools_list:
        sections.append(_build_tool_instructions(tools_list))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Agent Brain
# ---------------------------------------------------------------------------


class AgentBrain:
    """Full agent orchestration engine for Brahmastra AI."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def process(
        self,
        message: str,
        conversation_id: str,
        history: list[dict[str, str]],
        system_prompt_override: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_token: str | None = None,
    ) -> dict[str, Any]:
        """Process a user message through the full agent pipeline.

        Returns a dict with:
          - response: str
          - conversation_id: str
          - provider: str
          - model: str
          - tokens: dict
          - execution_time: float
          - agent_status: str
          - capabilities_used: list[str]
        """
        state = AgentState(
            request=message,
            conversation_id=conversation_id,
            user_token=user_token,
        )

        # --- Setup ---
        provider = AIProviderFactory.get_provider(settings=self._settings)
        registry_service = ToolRegistryService()
        tools_list = registry_service.list_tools().tools
        available_tool_names = {t.name for t in tools_list}
        capabilities_used: list[str] = []

        # --- Intent Classification ---
        intent = _classify_intent(message, available_tool_names)
        state.intent = str(intent)
        logger.info("Agent intent classified", extra={"intent": intent, "conversation_id": conversation_id})

        # --- Step 2: Parallel capability retrieval ---
        retrieval_tasks = []
        retrieval_labels = []

        if intent["needs_memory"] and user_token:
            state.status = AgentStatus.RETRIEVING_MEMORY
            retrieval_tasks.append(_fetch_relevant_memories(message, user_token))
            retrieval_labels.append("memory")
        else:
            retrieval_tasks.append(asyncio.coroutine(lambda: "")())
            retrieval_labels.append("memory")

        if intent["needs_rag"] and user_token:
            state.status = AgentStatus.RETRIEVING_DOCUMENTS
            retrieval_tasks.append(_fetch_rag_context(message, user_token))
            retrieval_labels.append("rag")
        else:
            retrieval_tasks.append(asyncio.coroutine(lambda: "")())
            retrieval_labels.append("rag")

        if intent["needs_web_research"]:
            state.status = AgentStatus.RESEARCHING
            web_svc = get_web_research_service()

            async def _do_web_research() -> str:
                result = await web_svc.research(message)
                return web_svc.format_context(result)

            retrieval_tasks.append(_do_web_research())
            retrieval_labels.append("web")
        else:
            retrieval_tasks.append(asyncio.coroutine(lambda: "")())
            retrieval_labels.append("web")

        retrieval_results = await asyncio.gather(*retrieval_tasks, return_exceptions=True)

        for label, result in zip(retrieval_labels, retrieval_results):
            if isinstance(result, Exception):
                logger.warning(f"{label} retrieval failed", extra={"error": str(result)})
                result = ""
            if label == "memory" and result:
                state.memory_context = result
                capabilities_used.append("memory")
            elif label == "rag" and result:
                state.rag_context = result
                capabilities_used.append("rag")
            elif label == "web" and result:
                state.web_context = result
                capabilities_used.append("web_research")

        # --- Step 3: Assemble context and run LLM orchestration loop ---
        state.status = AgentStatus.THINKING

        # Build system prompt
        needs_tools = bool(tools_list) and not intent["is_conversational"]
        system_prompt = system_prompt_override or _assemble_system_prompt(
            state, tools_list, include_tools=needs_tools
        )

        chat_req = ChatRequest(
            message=message,
            conversation_id=conversation_id,
            context=[ChatMessage(role=m["role"], content=m["content"]) for m in history],
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        # Tool orchestration loop (bounded by MAX_AGENT_STEPS)
        attempts = max(1, self._settings.ai.retry_attempts)
        backoff = max(0.0, self._settings.ai.retry_backoff_seconds)
        total_prompt_tokens = 0
        total_completion_tokens = 0
        loop_history = list(history)  # mutable copy for tool loop

        for step in range(MAX_AGENT_STEPS):
            state.steps_taken = step + 1
            last_exception: Exception | None = None
            response_text = ""
            tokens = None

            # Retry loop for provider calls
            for attempt in range(1, attempts + 1):
                try:
                    response_text, tokens = await provider.generate_response(
                        chat_req, loop_history
                    )
                    break
                except (RateLimitException, NetworkErrorException, TimeoutException) as exc:
                    last_exception = exc
                    if attempt < attempts:
                        await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    continue
                except ProviderErrorException as exc:
                    last_exception = exc
                    if exc.status_code in {500, 502, 503, 504} and attempt < attempts:
                        await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    continue
                except Exception as exc:
                    last_exception = exc
                    break

            if last_exception and not response_text:
                state.status = AgentStatus.ERROR
                state.error = str(last_exception)
                logger.error("Provider call failed", extra={"error": str(last_exception)})
                if isinstance(last_exception, AIServiceException):
                    raise last_exception
                raise ProviderErrorException(provider.provider_id, str(last_exception))

            if tokens:
                total_prompt_tokens += tokens.prompt_tokens
                total_completion_tokens += tokens.completion_tokens

            # Check for tool call in response
            parsed_tool_call = _parse_tool_call(response_text)

            if not parsed_tool_call:
                # Check if model missed the current_time tool for a time query
                if (
                    step == 0
                    and "current_time" in available_tool_names
                    and _is_current_time_query(message)
                ):
                    parsed_tool_call = {"name": "current_time", "arguments": {}}
                else:
                    # Final response — no tool needed
                    state.final_response = response_text
                    break

            # Execute the tool
            tool_name = parsed_tool_call.get("name", "")
            tool_args = parsed_tool_call.get("arguments", {})

            if tool_name not in available_tool_names:
                state.final_response = (
                    f"I tried to use tool '{tool_name}' but it is not available. "
                    f"Available tools: {', '.join(sorted(available_tool_names))}."
                )
                break

            state.status = AgentStatus.EXECUTING_TOOL
            logger.info("Executing LLM-requested tool", extra={"tool": tool_name, "step": step})

            executor = ToolExecutor()
            exec_req = ToolExecutionRequest(tool_name=tool_name, arguments=tool_args)

            try:
                exec_res = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, executor.execute, exec_req),
                    timeout=TOOL_TIMEOUT_SECONDS,
                )
                tool_output_str = (
                    json.dumps(exec_res.output)
                    if not isinstance(exec_res.output, str)
                    else exec_res.output
                )
                capabilities_used.append(f"tool:{tool_name}")

                # Add to history for next iteration
                loop_history.append({"role": "assistant", "content": response_text})
                loop_history.append({
                    "role": "user",
                    "content": f"Tool '{tool_name}' returned: {tool_output_str}",
                })

                state.observations.append({
                    "step": step,
                    "tool": tool_name,
                    "success": exec_res.success,
                    "output_preview": str(exec_res.output)[:200],
                })

            except asyncio.TimeoutError:
                logger.warning("Tool execution timed out", extra={"tool": tool_name})
                loop_history.append({"role": "assistant", "content": response_text})
                loop_history.append({
                    "role": "user",
                    "content": f"Tool '{tool_name}' timed out after {TOOL_TIMEOUT_SECONDS}s.",
                })

            state.status = AgentStatus.THINKING

        else:
            # MAX_AGENT_STEPS reached without terminal response
            state.final_response = response_text or "I reached the maximum number of steps. Please try a simpler request."
            state.status = AgentStatus.MAX_STEPS_REACHED
            logger.warning("Max agent steps reached", extra={"steps": MAX_AGENT_STEPS})

        if not state.final_response:
            state.final_response = "I encountered an issue generating a response. Please try again."

        state.status = AgentStatus.RESPONDING
        state.tokens_used = TokenUsage(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
        )

        return self._build_result(state, provider, capabilities_used)

    def _build_result(
        self,
        state: AgentState,
        provider: Any,
        capabilities_used: list[str],
    ) -> dict[str, Any]:
        return {
            "response": state.final_response,
            "conversation_id": state.conversation_id,
            "provider": provider.provider_id,
            "model": provider.default_model,
            "tokens": state.tokens_used.model_dump(),
            "execution_time": state.elapsed_seconds,
            "agent_status": state.status.value,
            "capabilities_used": list(dict.fromkeys(capabilities_used)),  # dedup, preserve order
            "steps_taken": state.steps_taken,
        }


def _parse_tool_call(response_text: str) -> dict[str, Any] | None:
    """Parse a tool call JSON from an LLM response."""
    clean = response_text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    clean = clean.removesuffix("```").strip()

    if not (clean.startswith("{") and "tool_call" in clean):
        return None

    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict) and "tool_call" in parsed:
            return parsed["tool_call"]
    except json.JSONDecodeError:
        pass
    return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_agent_brain_instance: AgentBrain | None = None


def get_agent_brain() -> AgentBrain:
    """Singleton accessor for AgentBrain."""
    global _agent_brain_instance
    if _agent_brain_instance is None:
        _agent_brain_instance = AgentBrain()
    return _agent_brain_instance
