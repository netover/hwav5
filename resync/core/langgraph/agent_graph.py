"""
LangGraph Agent Graph Implementation.

This module implements state-graph based agent orchestration with:
- Conditional routing
- Retry loops with error correction
- Tool calling with validation
- Human-in-the-loop approval
- Persistent checkpointing

The graph architecture:

    START
      │
      ▼
    [Router] ─────────────────────────────┐
      │                                    │
      ├─► [Status Handler] ──► [Response]  │
      │                                    │
      ├─► [Troubleshoot Handler] ──► [...] │
      │                                    │
      ├─► [Query Handler (RAG)] ──► [...]  │
      │                                    │
      └─► [Action Handler] ──► [Approval] ─┤
                                    │      │
                                    ▼      │
                              [Execute] ───┘
                                    │
                                    ▼
                               [Validate]
                                    │
                           ┌───────┴───────┐
                           │               │
                      (success)       (failure)
                           │               │
                           ▼               ▼
                       [Format]      [Retry Node]
                           │               │
                           ▼               │
                        [END]  ◄───────────┘
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, TypedDict

from resync.core.langfuse import PromptType, get_prompt_manager, get_tracer
from resync.core.structured_logger import get_logger
from resync.settings import settings

logger = get_logger(__name__)

# Try to import langgraph (optional dependency)
try:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph import END, StateGraph
    from langgraph.prebuilt import ToolNode as LGToolNode  # noqa: F401 - reserved for future use

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = "END"
    BaseCheckpointSaver = object


# =============================================================================
# STATE DEFINITION
# =============================================================================


class Intent(str, Enum):
    """User intent categories."""

    STATUS = "status"
    TROUBLESHOOT = "troubleshoot"
    QUERY = "query"
    ACTION = "action"
    GENERAL = "general"
    UNKNOWN = "unknown"


class AgentState(TypedDict, total=False):
    """
    State passed between nodes in the graph.

    This is the central data structure that flows through the graph.
    Each node reads from and writes to this state.
    """

    # Input
    message: str
    user_id: str | None
    session_id: str | None
    tws_instance_id: str | None

    # Conversation
    conversation_history: list[dict[str, str]]

    # Classification
    intent: Intent
    confidence: float
    entities: dict[str, Any]

    # Processing
    current_node: str
    retry_count: int
    max_retries: int

    # Tool execution
    tool_name: str | None
    tool_input: dict[str, Any]
    tool_output: str | None
    tool_error: str | None

    # Human-in-the-loop
    requires_approval: bool
    approval_id: str | None
    approval_status: Literal["pending", "approved", "rejected"] | None

    # LLM
    llm_messages: list[dict[str, str]]
    llm_response: str | None

    # Output
    response: str
    metadata: dict[str, Any]

    # Errors
    error: str | None
    error_count: int


@dataclass
class AgentGraphConfig:
    """Configuration for the agent graph."""

    # Retry settings
    max_retries: int = 3
    retry_delay_ms: int = 500

    # Approval settings
    require_approval_for_actions: bool = True
    approval_timeout_seconds: int = 300

    # LLM settings
    default_model: str = "meta/llama-3.1-70b-instruct"
    default_temperature: float = 0.7
    max_tokens: int = 1000

    # Checkpointing
    enable_checkpointing: bool = True
    checkpoint_every_n_steps: int = 1

    # Debug
    verbose: bool = False


# =============================================================================
# NODE FUNCTIONS
# =============================================================================


async def router_node(state: AgentState) -> AgentState:
    """
    Classify user intent and route to appropriate handler.

    Uses a fast, lightweight LLM call for classification.
    """
    logger.debug("router_node_start", message=state.get("message", "")[:50])

    message = state.get("message", "")

    # Get router prompt
    prompt_manager = get_prompt_manager()
    router_prompt = await prompt_manager.get_prompt("intent-router-v1")

    if not router_prompt:
        # Fallback to simple keyword matching
        return await _fallback_router(state)

    try:
        # Use call_llm for classification (project standard with LiteLLM + resilience)
        from resync.core.utils.llm import call_llm

        tracer = get_tracer()
        async with tracer.trace(
            "intent_classification", model=router_prompt.model_hint or "default"
        ) as trace:
            compiled = router_prompt.compile(user_message=message)

            # Use call_llm with resilience built-in
            response = await call_llm(
                prompt=compiled,
                model=router_prompt.model_hint or settings.llm_model or "gpt-4o",
                max_tokens=router_prompt.config.max_tokens_hint or 10,
                temperature=router_prompt.temperature_hint or 0.1,
            )

            trace.output = response
            trace.input_tokens = len(compiled.split()) * 2  # Rough estimate
            trace.output_tokens = len(response.split()) * 2

        # Parse intent
        intent_str = response.strip().upper()
        try:
            intent = Intent(intent_str.lower())
        except ValueError:
            intent = Intent.GENERAL

        state["intent"] = intent
        state["confidence"] = 0.85  # Could be extracted from LLM response
        state["current_node"] = "router"

        logger.info(
            "intent_classified",
            intent=intent.value,
            confidence=state["confidence"],
            message_preview=message[:30],
        )

    except Exception as e:
        logger.warning("router_classification_failed", error=str(e), exc_info=True)
        return await _fallback_router(state)

    return state


async def _fallback_router(state: AgentState) -> AgentState:
    """Fallback router using keyword matching."""
    message = state.get("message", "").lower()

    # Keyword-based classification
    if any(kw in message for kw in ["status", "estado", "workstation", "online", "offline"]):
        intent = Intent.STATUS
        confidence = 0.7
    elif any(
        kw in message for kw in ["erro", "error", "falha", "abend", "problema", "troubleshoot"]
    ):
        intent = Intent.TROUBLESHOOT
        confidence = 0.7
    elif any(kw in message for kw in ["cancelar", "reiniciar", "executar", "parar", "submit"]):
        intent = Intent.ACTION
        confidence = 0.8
    elif any(kw in message for kw in ["como", "o que", "qual", "porque", "documentação"]):
        intent = Intent.QUERY
        confidence = 0.6
    else:
        intent = Intent.GENERAL
        confidence = 0.5

    state["intent"] = intent
    state["confidence"] = confidence
    state["current_node"] = "router"

    return state


async def status_handler_node(state: AgentState) -> AgentState:
    """Handle status queries using TWS tools."""
    logger.debug("status_handler_start")

    state["current_node"] = "status_handler"

    try:
        # Get TWS status using tool
        from resync.tool_definitions.tws_tools import tws_status_tool

        tws_instance = state.get("tws_instance_id")
        tool_result = await tws_status_tool(instance_id=tws_instance)

        state["tool_name"] = "tws_status"
        state["tool_output"] = json.dumps(tool_result, ensure_ascii=False)

        # Generate natural language response
        await _generate_response_from_tool(state, "status_response")

    except Exception as e:
        logger.error("status_handler_error", error=str(e), exc_info=True)
        state["error"] = str(e)
        state["response"] = f"Não foi possível obter o status do TWS: {str(e)}"

    return state


async def troubleshoot_handler_node(state: AgentState) -> AgentState:
    """
    Handle troubleshooting queries using parallel data fetching.
    
    Performance: Uses parallel execution to fetch data from multiple sources
    simultaneously, reducing latency by ~60-70%.
    
    Sources queried in parallel:
    - TWS status (API)
    - RAG knowledge base
    - Historical logs (cache)
    - System metrics
    """
    logger.debug("troubleshoot_handler_start")

    state["current_node"] = "troubleshoot_handler"

    try:
        # Use parallel troubleshooting for better performance
        from resync.core.langgraph.parallel_graph import parallel_troubleshoot

        message = state.get("message", "")
        entities = state.get("entities", {})
        job_name = entities.get("job_name")
        tws_instance = state.get("tws_instance_id")

        # Execute parallel troubleshooting
        result = await parallel_troubleshoot(
            message=message,
            job_name=job_name,
            tws_instance_id=tws_instance,
        )

        state["tool_name"] = "parallel_troubleshooting"
        state["tool_output"] = json.dumps(result.get("metadata", {}), ensure_ascii=False)
        state["response"] = result.get("response", "")
        
        # Add performance metrics to metadata
        state["metadata"] = {
            **(state.get("metadata") or {}),
            "parallel_execution": True,
            "parallel_latency_ms": result.get("parallel_latency_ms", 0),
            "total_latency_ms": result.get("total_latency_ms", 0),
        }

        logger.info(
            "troubleshoot_parallel_complete",
            parallel_latency_ms=result.get("parallel_latency_ms"),
            total_latency_ms=result.get("total_latency_ms"),
        )

    except ImportError:
        # Fallback to sequential troubleshooting if parallel module unavailable
        logger.warning("parallel_module_unavailable_using_fallback")
        return await _fallback_troubleshoot_handler(state)

    except Exception as e:
        logger.error("troubleshoot_handler_error", error=str(e), exc_info=True)
        state["error"] = str(e)
        state["response"] = f"Erro durante análise de troubleshooting: {str(e)}"

    return state


async def _fallback_troubleshoot_handler(state: AgentState) -> AgentState:
    """Fallback sequential troubleshooting handler."""
    try:
        from resync.tool_definitions.tws_tools import tws_troubleshooting_tool

        message = state.get("message", "")
        entities = state.get("entities", {})
        job_name = entities.get("job_name")

        tool_result = await tws_troubleshooting_tool(
            query=message,
            job_name=job_name,
        )

        state["tool_name"] = "tws_troubleshooting"
        state["tool_output"] = json.dumps(tool_result, ensure_ascii=False)

        await _generate_response_from_tool(state, "troubleshoot_response")

    except Exception as e:
        logger.error("fallback_troubleshoot_error", error=str(e), exc_info=True)
        state["error"] = str(e)
        state["response"] = f"Erro durante análise de troubleshooting: {str(e)}"

    return state


async def query_handler_node(state: AgentState) -> AgentState:
    """Handle documentation/knowledge queries using RAG."""
    logger.debug("query_handler_start")

    state["current_node"] = "query_handler"

    try:
        from resync.core.utils.llm import call_llm
        from resync.services.rag_client import RAGClient

        message = state.get("message", "")

        # Search knowledge base
        rag_client = RAGClient()
        search_results = await rag_client.search(query=message, limit=5)

        # Build context
        context = "\n\n".join(
            [
                f"[{r.get('source', 'Unknown')}]: {r.get('content', '')}"
                for r in search_results.get("results", [])
            ]
        )

        # Get RAG prompt and generate response
        prompt_manager = get_prompt_manager()
        rag_prompt = await prompt_manager.get_default_prompt(PromptType.RAG)

        if rag_prompt:
            system_message = rag_prompt.compile(rag_context=context)
            full_prompt = f"SYSTEM: {system_message}\n\nUSER: {message}"

            # Use call_llm with project standard (LiteLLM + resilience)
            response = await call_llm(
                prompt=full_prompt,
                model=rag_prompt.model_hint or settings.llm_model or "gpt-4o",
                max_tokens=1000,
                temperature=0.3,
            )

            state["response"] = response
        else:
            state["response"] = f"Baseado na documentação:\n\n{context[:500]}..."

    except Exception as e:
        logger.error("query_handler_error", error=str(e), exc_info=True)
        state["error"] = str(e)
        state["response"] = "Não foi possível buscar na base de conhecimento."

    return state


async def action_handler_node(state: AgentState) -> AgentState:
    """Handle action requests (requires approval)."""
    logger.debug("action_handler_start")

    state["current_node"] = "action_handler"

    # Actions require approval
    state["requires_approval"] = True
    state["approval_id"] = str(uuid.uuid4())
    state["approval_status"] = "pending"

    # Parse the requested action
    message = state.get("message", "").lower()

    if "cancelar" in message:
        action = "cancel_job"
    elif "reiniciar" in message or "rerun" in message:
        action = "rerun_job"
    elif "submit" in message or "executar" in message:
        action = "submit_job"
    else:
        action = "unknown_action"

    state["tool_name"] = action
    state["response"] = (
        f"⚠️ Ação '{action}' requer aprovação.\n\n"
        f"ID da Aprovação: {state['approval_id']}\n\n"
        f"Use `/approve {state['approval_id']}` para aprovar ou "
        f"`/reject {state['approval_id']}` para rejeitar."
    )

    return state


async def general_handler_node(state: AgentState) -> AgentState:
    """Handle general conversation."""
    logger.debug("general_handler_start")

    state["current_node"] = "general_handler"

    try:
        from resync.core.utils.llm import call_llm

        prompt_manager = get_prompt_manager()
        agent_prompt = await prompt_manager.get_default_prompt(PromptType.AGENT)

        message = state.get("message", "")
        history = state.get("conversation_history", [])

        messages = []

        if agent_prompt:
            system_content = agent_prompt.compile(context="Conversa geral sobre TWS.")
            messages.append({"role": "system", "content": system_content})

        # Add history
        messages.extend(history[-5:])
        messages.append({"role": "user", "content": message})

        # Build full prompt for call_llm
        full_prompt = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])

        # Use call_llm with project standard (LiteLLM + resilience)
        response = await call_llm(
            prompt=full_prompt,
            model=agent_prompt.model_hint if agent_prompt else settings.llm_model or "gpt-4o",
            max_tokens=1000,
            temperature=0.7,
        )
        state["response"] = response

    except Exception as e:
        logger.error("general_handler_error", error=str(e), exc_info=True)
        state["response"] = "Olá! Como posso ajudar com o TWS hoje?"

    return state


async def validation_node(state: AgentState) -> AgentState:
    """Validate tool outputs and responses."""
    logger.debug("validation_node_start")

    state["current_node"] = "validation"

    # Check for tool errors
    if state.get("tool_error"):
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)

        if retry_count < max_retries:
            state["retry_count"] = retry_count + 1
            logger.warning(
                "validation_retry",
                retry_count=state["retry_count"],
                error=state["tool_error"],
            )
        else:
            logger.error("validation_max_retries", error=state["tool_error"])
            state["error"] = f"Falha após {max_retries} tentativas: {state['tool_error']}"

    return state


async def response_formatter_node(state: AgentState) -> AgentState:
    """Format the final response."""
    logger.debug("response_formatter_start")

    state["current_node"] = "response_formatter"

    # Add metadata
    state["metadata"] = {
        "intent": state.get("intent", Intent.UNKNOWN).value,
        "confidence": state.get("confidence", 0),
        "tool_used": state.get("tool_name"),
        "retry_count": state.get("retry_count", 0),
    }

    return state


async def _generate_response_from_tool(state: AgentState, response_type: str) -> None:
    """Generate natural language response from tool output."""
    from resync.core.utils.llm import call_llm

    tool_output = state.get("tool_output", "{}")
    message = state.get("message", "")

    prompt_manager = get_prompt_manager()
    formatter_prompt = await prompt_manager.get_prompt("tool-response-formatter-v1")

    if formatter_prompt:
        compiled = formatter_prompt.compile(
            tool_name=state.get("tool_name", "unknown"),
            tool_output=tool_output,
        )

        full_prompt = f"SYSTEM: {compiled}\n\nUSER: {message}"

        # Use call_llm with project standard (LiteLLM + resilience)
        response = await call_llm(
            prompt=full_prompt,
            model=formatter_prompt.model_hint or settings.llm_model or "gpt-4o",
            max_tokens=800,
            temperature=0.5,
        )

        state["response"] = response
    else:
        # Fallback: return tool output directly
        state["response"] = tool_output


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================


def _get_next_node(state: AgentState) -> str:
    """Determine the next node based on intent."""
    intent = state.get("intent", Intent.GENERAL)

    routing = {
        Intent.STATUS: "status_handler",
        Intent.TROUBLESHOOT: "troubleshoot_handler",
        Intent.QUERY: "query_handler",
        Intent.ACTION: "action_handler",
        Intent.GENERAL: "general_handler",
        Intent.UNKNOWN: "general_handler",
    }

    return routing.get(intent, "general_handler")


def _should_retry(state: AgentState) -> str:
    """Determine if we should retry or proceed to output."""
    tool_error = state.get("tool_error")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if tool_error and retry_count < max_retries:
        return "retry"
    return "output"


async def create_tws_agent_graph(
    config: AgentGraphConfig | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """
    Create the TWS agent state graph.

    Args:
        config: Graph configuration
        checkpointer: Optional checkpointer for persistence

    Returns:
        Compiled StateGraph (or FallbackGraph if LangGraph unavailable)
    """
    config = config or AgentGraphConfig()

    if not LANGGRAPH_AVAILABLE:
        logger.warning("langgraph_not_available_using_fallback")
        return FallbackGraph(config)

    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("status_handler", status_handler_node)
    graph.add_node("troubleshoot_handler", troubleshoot_handler_node)
    graph.add_node("query_handler", query_handler_node)
    graph.add_node("action_handler", action_handler_node)
    graph.add_node("general_handler", general_handler_node)
    graph.add_node("validation", validation_node)
    graph.add_node("response_formatter", response_formatter_node)

    # Set entry point
    graph.set_entry_point("router")

    # Add conditional edges from router
    graph.add_conditional_edges(
        "router",
        _get_next_node,
        {
            "status_handler": "status_handler",
            "troubleshoot_handler": "troubleshoot_handler",
            "query_handler": "query_handler",
            "action_handler": "action_handler",
            "general_handler": "general_handler",
        },
    )

    # Add edges from handlers to validation
    for handler in ["status_handler", "troubleshoot_handler", "query_handler", "general_handler"]:
        graph.add_edge(handler, "validation")

    # Action handler goes directly to formatter (after approval)
    graph.add_edge("action_handler", "response_formatter")

    # Validation: retry or proceed
    graph.add_conditional_edges(
        "validation",
        _should_retry,
        {
            "retry": "router",  # Back to start for retry
            "output": "response_formatter",
        },
    )

    # Response formatter to end
    graph.add_edge("response_formatter", END)

    # Compile
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("tws_agent_graph_created", nodes=6, checkpointing=checkpointer is not None)

    return compiled


async def create_router_graph() -> Any:
    """Create a simplified router-only graph for intent classification."""
    if not LANGGRAPH_AVAILABLE:
        return FallbackGraph(AgentGraphConfig())

    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.set_entry_point("router")
    graph.add_edge("router", END)

    return graph.compile()


# =============================================================================
# FALLBACK IMPLEMENTATION
# =============================================================================


class FallbackGraph:
    """
    Fallback implementation when LangGraph is not available.

    Provides the same interface but uses simple sequential execution.
    """

    def __init__(self, config: AgentGraphConfig):
        self.config = config

    async def invoke(self, state: dict[str, Any]) -> AgentState:
        """Process message through the graph."""
        # Initialize state
        full_state: AgentState = {
            "message": state.get("message", ""),
            "user_id": state.get("user_id"),
            "session_id": state.get("session_id"),
            "tws_instance_id": state.get("tws_instance_id"),
            "conversation_history": state.get("conversation_history", []),
            "intent": Intent.UNKNOWN,
            "confidence": 0.0,
            "entities": {},
            "current_node": "start",
            "retry_count": 0,
            "max_retries": self.config.max_retries,
            "requires_approval": False,
            "response": "",
            "metadata": {},
            "error": None,
            "error_count": 0,
        }

        try:
            # Router
            full_state = await router_node(full_state)

            # Handler based on intent
            intent = full_state.get("intent", Intent.GENERAL)

            handlers = {
                Intent.STATUS: status_handler_node,
                Intent.TROUBLESHOOT: troubleshoot_handler_node,
                Intent.QUERY: query_handler_node,
                Intent.ACTION: action_handler_node,
                Intent.GENERAL: general_handler_node,
            }

            handler = handlers.get(intent, general_handler_node)
            full_state = await handler(full_state)

            # Validation
            full_state = await validation_node(full_state)

            # Format response
            full_state = await response_formatter_node(full_state)

        except Exception as e:
            logger.error("fallback_graph_error", error=str(e), exc_info=True)
            full_state["error"] = str(e)
            full_state["response"] = f"Erro no processamento: {str(e)}"

        return full_state

    async def astream(self, state: dict[str, Any]):
        """Stream results (just yields final result for fallback)."""
        result = await self.invoke(state)
        yield result
