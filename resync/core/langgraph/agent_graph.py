"""
LangGraph Agent Graph Implementation.

This module implements state-graph based agent orchestration with:
- Conditional routing with entity extraction
- Clarification loop for missing information
- Intelligent response synthesis (JSON → friendly text)
- Retry loops with error correction
- Tool calling with validation
- Human-in-the-loop approval
- Persistent checkpointing

The graph architecture (v5.9.1 - Enhanced UX):

    START
      │
      ▼
    [Router] ──────────────────────────────────────────────┐
      │                                                     │
      ├─► (missing info) ─► [Clarification] ◄──────────────┤
      │                           │                         │
      │                     (user responds)                 │
      │                           │                         │
      ├─► [Status Handler] ───────┼─────────────────────────┤
      │                           │                         │
      ├─► [Troubleshoot Handler] ─┼─► [Planner] ──► [...] ──┤
      │                           │                         │
      ├─► [Query Handler (RAG)] ──┼─────────────────────────┤
      │                           │                         │
      └─► [Action Handler] ───────┼──► [Approval] ──────────┤
                                  │                         │
                                  ▼                         │
                             [Validate]                     │
                                  │                         │
                         ┌───────┴───────┐                  │
                         │               │                  │
                    (success)       (failure)               │
                         │               │                  │
                         ▼               ▼                  │
                   [Synthesizer]   [Retry Node] ────────────┘
                         │
                         ▼
                      [END]

Key improvements (v5.9.1):
- ClarificationNode: Asks for missing info instead of guessing
- SynthesizerNode: Transforms JSON into friendly Markdown
- PlannedSteps: Shows progress for complex operations
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, TypedDict

from resync.core.langfuse import PromptType, get_prompt_manager, get_tracer
from resync.core.langgraph.hallucination_grader import (
    GradeDecision,
    hallucination_check_node,
)
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

    # Clarification Loop (NEW v5.9.1)
    missing_entities: list[str]  # Entities that are required but missing
    needs_clarification: bool     # Flag to route to clarification node
    clarification_question: str   # Question to ask the user
    clarification_context: dict[str, Any]  # Context to preserve during clarification

    # Planning (NEW v5.9.1 - for complex operations)
    planned_steps: list[dict[str, Any]]  # [{"step": 1, "action": "...", "status": "pending"}]
    current_step: int
    show_progress: bool  # Whether to show progress to user

    # Processing
    current_node: str
    retry_count: int
    max_retries: int

    # Tool execution
    tool_name: str | None
    tool_input: dict[str, Any]
    tool_output: str | None
    tool_error: str | None

    # Raw data for synthesis (NEW v5.9.1)
    raw_data: dict[str, Any]  # Raw JSON data from tools/API
    output_format: str  # "markdown", "plain", "json"

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

    # Hallucination Grading (v5.2.3.27)
    hallucination_check: dict[str, Any] | None  # Result from grader
    is_grounded: bool  # Whether response is grounded in facts
    hallucination_decision: str | None  # GradeDecision value
    hallucination_retry_count: int  # Retry count for regeneration
    max_hallucination_retries: int  # Max retries before accepting


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


# Required entities per intent
REQUIRED_ENTITIES = {
    Intent.STATUS: ["job_name"],  # Optional: workstation
    Intent.TROUBLESHOOT: ["job_name"],  # Need job name to troubleshoot
    Intent.ACTION: ["job_name", "action_type"],  # Need job and what to do
    Intent.QUERY: [],  # RAG queries don't need specific entities
    Intent.GENERAL: [],
    Intent.UNKNOWN: [],
}

# Entity extraction patterns (simple regex-based)
ENTITY_PATTERNS = {
    "job_name": [
        r"job\s+([A-Z0-9_-]+)",
        r"([A-Z][A-Z0-9_-]{3,})",  # UPPERCASE names likely jobs
        r"processo\s+([A-Z0-9_-]+)",
    ],
    "workstation": [
        r"workstation\s+([A-Z0-9_-]+)",
        r"ws[_-]?([A-Z0-9]+)",
        r"estação\s+([A-Z0-9_-]+)",
    ],
    "action_type": [
        r"(cancelar|reiniciar|executar|parar|submit|rerun|hold|release)",
    ],
    "error_code": [
        r"(AWSB[0-9]{4}[A-Z])",
        r"rc[=:\s]+(\d+)",
        r"código[=:\s]+(\d+)",
    ],
}


async def router_node(state: AgentState) -> AgentState:
    """
    Classify user intent, extract entities, and detect missing information.

    Enhanced to support clarification loop - if required entities are missing,
    sets needs_clarification=True instead of proceeding with incomplete info.
    """
    logger.debug("router_node_start", message=state.get("message", "")[:50])

    message = state.get("message", "")

    # Initialize clarification fields
    state["needs_clarification"] = False
    state["missing_entities"] = []

    # Step 1: Extract entities from message
    entities = _extract_entities(message)
    state["entities"] = entities

    # Check if this is a response to a clarification question
    clarification_context = state.get("clarification_context", {})
    if clarification_context:
        # Merge previous entities with new ones from response
        prev_entities = clarification_context.get("entities", {})
        entities = {**prev_entities, **entities}
        state["entities"] = entities
        state["clarification_context"] = {}  # Clear context

    # Step 2: Classify intent
    prompt_manager = get_prompt_manager()
    router_prompt = await prompt_manager.get_prompt("intent-router-v2")

    if not router_prompt:
        state = await _fallback_router(state)
    else:
        try:
            from resync.core.utils.llm import call_llm

            tracer = get_tracer()
            async with tracer.trace(
                "intent_classification", model=router_prompt.model_hint or "default"
            ) as trace:
                compiled = router_prompt.compile(user_message=message)

                response = await call_llm(
                    prompt=compiled,
                    model=router_prompt.model_hint or settings.llm_model or "gpt-4o",
                    max_tokens=router_prompt.config.max_tokens_hint or 50,
                    temperature=router_prompt.temperature_hint or 0.1,
                )

                trace.output = response
                trace.input_tokens = len(compiled.split()) * 2
                trace.output_tokens = len(response.split()) * 2

            # Parse response (may include intent and entities)
            intent, extra_entities, confidence = _parse_router_response(response)
            entities.update(extra_entities)
            state["entities"] = entities
            state["intent"] = intent
            state["confidence"] = confidence

        except Exception as e:
            logger.warning("router_classification_failed", error=str(e))
            state = await _fallback_router(state)

    # Step 3: Check for missing required entities
    intent = state.get("intent", Intent.GENERAL)
    required = REQUIRED_ENTITIES.get(intent, [])
    missing = [e for e in required if not entities.get(e)]

    if missing and intent in [Intent.STATUS, Intent.TROUBLESHOOT, Intent.ACTION]:
        state["needs_clarification"] = True
        state["missing_entities"] = missing
        state["clarification_context"] = {
            "intent": intent.value,
            "entities": entities,
            "original_message": message,
        }
        logger.info(
            "clarification_needed",
            intent=intent.value,
            missing=missing,
        )

    state["current_node"] = "router"

    logger.info(
        "router_complete",
        intent=intent.value,
        confidence=state.get("confidence", 0),
        entities=list(entities.keys()),
        needs_clarification=state["needs_clarification"],
    )

    return state


def _extract_entities(message: str) -> dict[str, Any]:
    """Extract entities from message using patterns."""
    import re

    entities = {}

    for entity_type, patterns in ENTITY_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                entities[entity_type] = match.group(1)
                break

    return entities


def _parse_router_response(response: str) -> tuple[Intent, dict[str, Any], float]:
    """Parse LLM router response to extract intent, entities, and confidence."""
    import re

    response_lower = response.strip().lower()
    entities = {}
    confidence = 0.85

    # Try to parse JSON if present
    if "{" in response:
        try:
            import json
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                data = json.loads(json_match.group())
                intent_str = data.get("intent", "general")
                entities = data.get("entities", {})
                confidence = data.get("confidence", 0.85)
                try:
                    return Intent(intent_str.lower()), entities, confidence
                except ValueError:
                    pass
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: parse as simple intent string
    for intent in Intent:
        if intent.value in response_lower:
            return intent, entities, confidence

    return Intent.GENERAL, entities, 0.5


async def _fallback_router(state: AgentState) -> AgentState:
    """Fallback router using keyword matching and entity extraction."""
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


# =============================================================================
# CLARIFICATION NODE (NEW v5.9.1)
# =============================================================================


# Questions templates for missing entities
CLARIFICATION_TEMPLATES = {
    "job_name": {
        "pt": "Qual é o nome do job que você gostaria de {action}?",
        "en": "What is the name of the job you would like to {action}?",
    },
    "workstation": {
        "pt": "Em qual workstation você gostaria de verificar?",
        "en": "Which workstation would you like to check?",
    },
    "action_type": {
        "pt": "O que você gostaria de fazer com o job {job_name}? (cancelar, reiniciar, executar, etc.)",
        "en": "What would you like to do with job {job_name}? (cancel, restart, execute, etc.)",
    },
    "error_code": {
        "pt": "Qual é o código de erro que você está vendo?",
        "en": "What is the error code you are seeing?",
    },
}

ACTION_VERBS = {
    Intent.STATUS: {"pt": "verificar o status", "en": "check the status of"},
    Intent.TROUBLESHOOT: {"pt": "analisar", "en": "troubleshoot"},
    Intent.ACTION: {"pt": "executar a ação em", "en": "perform the action on"},
}


async def clarification_node(state: AgentState) -> AgentState:
    """
    Generate clarification questions for missing information.

    Instead of guessing or failing, asks the user for required info.
    """
    logger.debug("clarification_node_start")

    state["current_node"] = "clarification"

    missing = state.get("missing_entities", [])
    intent = state.get("intent", Intent.GENERAL)
    entities = state.get("entities", {})
    lang = "pt"  # Could be detected from user preferences

    if not missing:
        # No clarification needed - shouldn't happen but handle gracefully
        state["needs_clarification"] = False
        return state

    # Generate clarification question
    questions = []
    action_verb = ACTION_VERBS.get(intent, {}).get(lang, "processar")

    for entity in missing:
        template = CLARIFICATION_TEMPLATES.get(entity, {}).get(lang)
        if template:
            question = template.format(
                action=action_verb,
                job_name=entities.get("job_name", "o job"),
            )
            questions.append(question)

    if questions:
        clarification_question = questions[0]  # Ask for one thing at a time
    else:
        # Generic fallback
        clarification_question = "Poderia fornecer mais detalhes sobre o que você precisa?"

    state["clarification_question"] = clarification_question
    state["response"] = clarification_question

    # Store context for when user responds
    state["clarification_context"] = {
        "intent": intent.value if isinstance(intent, Intent) else intent,
        "entities": entities,
        "missing": missing,
        "original_message": state.get("message", ""),
    }

    logger.info(
        "clarification_generated",
        missing_entities=missing,
        question=clarification_question[:50],
    )

    return state


# =============================================================================
# SYNTHESIZER NODE (NEW v5.9.1 - Enhanced response formatting)
# =============================================================================


# Response templates for different data types
SYNTHESIS_TEMPLATES = {
    "status_success": """
✅ **Status do Job: {job_name}**

| Campo | Valor |
|-------|-------|
| Status | {status} |
| Última execução | {last_run} |
| Workstation | {workstation} |
| Código de retorno | {return_code} |

{additional_info}
""",
    "status_error": """
❌ **Job com problema: {job_name}**

| Campo | Valor |
|-------|-------|
| Status | {status} |
| Código de erro | {error_code} |
| Mensagem | {error_message} |

**Recomendação:** {recommendation}
""",
    "troubleshoot_analysis": """
🔍 **Análise do Job: {job_name}**

**Problema identificado:** {problem_summary}

**Detalhes técnicos:**
```
{technical_details}
```

**Causa provável:** {root_cause}

**Ações recomendadas:**
{recommendations}
""",
    "action_result": """
{icon} **Ação executada: {action_type}**

| Job | Resultado |
|-----|-----------|
| {job_name} | {result} |

{details}
""",
}


async def synthesizer_node(state: AgentState) -> AgentState:
    """
    Transform raw data/JSON into user-friendly Markdown response.

    This is the "Final Answer Agent" - ensures the user never sees raw JSON
    and always gets a well-formatted, contextual response.
    """
    logger.debug("synthesizer_node_start")

    state["current_node"] = "synthesizer"

    # Get raw data
    tool_output = state.get("tool_output", "{}")
    raw_data = state.get("raw_data", {})
    intent = state.get("intent", Intent.GENERAL)
    entities = state.get("entities", {})

    # Parse tool output if it's JSON string
    if isinstance(tool_output, str):
        try:
            raw_data = json.loads(tool_output)
        except json.JSONDecodeError:
            raw_data = {"raw_response": tool_output}

    state["raw_data"] = raw_data

    # Check if we already have a good response
    existing_response = state.get("response", "")
    if existing_response and not _is_json_response(existing_response):
        # Already formatted - add metadata and return
        state["metadata"] = _build_metadata(state)
        return state

    # Generate synthesized response
    try:
        response = await _synthesize_response(raw_data, intent, entities, state)
        state["response"] = response
    except Exception as e:
        logger.warning("synthesis_failed", error=str(e))
        # Fallback to LLM-based synthesis
        state["response"] = await _llm_synthesize(raw_data, intent, state)

    # Add metadata
    state["metadata"] = _build_metadata(state)

    logger.info(
        "synthesis_complete",
        intent=intent.value if isinstance(intent, Intent) else intent,
        response_length=len(state.get("response", "")),
    )

    return state


def _is_json_response(response: str) -> bool:
    """Check if response looks like raw JSON."""
    response = response.strip()
    return response.startswith("{") or response.startswith("[")


def _build_metadata(state: AgentState) -> dict[str, Any]:
    """Build response metadata."""
    intent = state.get("intent", Intent.UNKNOWN)
    return {
        "intent": intent.value if isinstance(intent, Intent) else intent,
        "confidence": state.get("confidence", 0),
        "tool_used": state.get("tool_name"),
        "entities": state.get("entities", {}),
        "retry_count": state.get("retry_count", 0),
        "had_clarification": bool(state.get("clarification_context")),
    }


async def _synthesize_response(
    raw_data: dict[str, Any],
    intent: Intent,
    entities: dict[str, Any],
    state: AgentState,
) -> str:
    """Synthesize user-friendly response from raw data."""

    job_name = entities.get("job_name", raw_data.get("job_name", "N/A"))
    status = raw_data.get("status", "UNKNOWN")

    # Determine template based on intent and status
    if intent == Intent.STATUS:
        if status in ["SUCC", "SUCCESS", "COMPLETED"]:
            return SYNTHESIS_TEMPLATES["status_success"].format(
                job_name=job_name,
                status=_translate_status(status),
                last_run=raw_data.get("last_run", "N/A"),
                workstation=raw_data.get("workstation", "N/A"),
                return_code=raw_data.get("return_code", "0"),
                additional_info=_format_additional_info(raw_data),
            ).strip()
        return SYNTHESIS_TEMPLATES["status_error"].format(
            job_name=job_name,
            status=_translate_status(status),
            error_code=raw_data.get("error_code", raw_data.get("return_code", "N/A")),
            error_message=raw_data.get("error_message", raw_data.get("message", "N/A")),
            recommendation=_get_recommendation(raw_data),
        ).strip()

    if intent == Intent.TROUBLESHOOT:
        return SYNTHESIS_TEMPLATES["troubleshoot_analysis"].format(
            job_name=job_name,
            problem_summary=raw_data.get("problem", raw_data.get("summary", "Problema identificado")),
            technical_details=_format_technical_details(raw_data),
            root_cause=raw_data.get("root_cause", "Em análise"),
            recommendations=_format_recommendations(raw_data),
        ).strip()

    if intent == Intent.ACTION:
        success = raw_data.get("success", raw_data.get("status") == "SUCCESS")
        return SYNTHESIS_TEMPLATES["action_result"].format(
            icon="✅" if success else "❌",
            action_type=entities.get("action_type", "Ação"),
            job_name=job_name,
            result="Sucesso" if success else "Falha",
            details=raw_data.get("message", ""),
        ).strip()

    # Default: format as readable text
    return _format_generic_response(raw_data)


def _translate_status(status: str) -> str:
    """Translate status codes to friendly text."""
    translations = {
        "SUCC": "✅ Sucesso",
        "SUCCESS": "✅ Sucesso",
        "COMPLETED": "✅ Completado",
        "ABEND": "❌ Falha (ABEND)",
        "FAIL": "❌ Falha",
        "FAILED": "❌ Falha",
        "EXEC": "🔄 Em execução",
        "RUNNING": "🔄 Em execução",
        "READY": "⏳ Pronto para executar",
        "HOLD": "⏸️ Em espera (HOLD)",
        "CANCEL": "🚫 Cancelado",
    }
    return translations.get(status.upper(), status)


def _format_additional_info(data: dict[str, Any]) -> str:
    """Format additional information from raw data."""
    excluded = {"job_name", "status", "last_run", "workstation", "return_code"}
    extra = {k: v for k, v in data.items() if k not in excluded and v}

    if not extra:
        return ""

    lines = ["**Informações adicionais:**"]
    for key, value in extra.items():
        lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def _get_recommendation(data: dict[str, Any]) -> str:
    """Get recommendation based on error data."""
    error_code = str(data.get("error_code", data.get("return_code", "")))

    recommendations = {
        "12": "Verifique os logs do job para detalhes do erro de I/O.",
        "8": "Possível problema de condição. Verifique as dependências.",
        "4": "Aviso - o job completou com warnings. Verifique os logs.",
        "ABEND": "O job terminou anormalmente. Analise o SYSLOG e os dumps.",
    }

    for key, rec in recommendations.items():
        if key in error_code or key in str(data.get("status", "")):
            return rec

    return "Verifique os logs do job para mais detalhes."


def _format_technical_details(data: dict[str, Any]) -> str:
    """Format technical details as code block content."""
    details = []

    if "logs" in data:
        details.append(f"Logs: {data['logs'][:500]}...")
    if "return_code" in data:
        details.append(f"Return Code: {data['return_code']}")
    if "error_message" in data:
        details.append(f"Error: {data['error_message']}")

    return "\n".join(details) if details else "Detalhes não disponíveis"


def _format_recommendations(data: dict[str, Any]) -> str:
    """Format recommendations as bullet list."""
    recs = data.get("recommendations", [])

    if isinstance(recs, list):
        return "\n".join(f"- {r}" for r in recs)
    if isinstance(recs, str):
        return f"- {recs}"

    return "- Verifique os logs do sistema\n- Entre em contato com o suporte se o problema persistir"


def _format_generic_response(data: dict[str, Any]) -> str:
    """Format generic data as readable response."""
    lines = ["**Resultado:**", ""]

    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"**{key}:**")
            for k, v in value.items():
                lines.append(f"  - {k}: {v}")
        elif isinstance(value, list):
            lines.append(f"**{key}:** {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"- **{key}:** {value}")

    return "\n".join(lines)


async def _llm_synthesize(raw_data: dict[str, Any], intent: Intent, state: AgentState) -> str:
    """Use LLM to synthesize response when template fails."""
    from resync.core.utils.llm import call_llm

    prompt = f"""Transforme os dados JSON abaixo em uma resposta amigável em português.
Use formatação Markdown (tabelas para status, code blocks para logs).
Nunca mostre JSON bruto ao usuário.

Intenção do usuário: {intent.value if isinstance(intent, Intent) else intent}
Pergunta original: {state.get('message', '')}

Dados:
{json.dumps(raw_data, indent=2, ensure_ascii=False)}

Resposta formatada:"""

    try:
        response = await call_llm(
            prompt=prompt,
            model=settings.llm_model or "gpt-4o",
            max_tokens=1000,
            temperature=0.5,
        )
        return response
    except Exception as e:
        logger.error("llm_synthesis_failed", error=str(e))
        return f"Dados recebidos: {json.dumps(raw_data, indent=2, ensure_ascii=False)}"


async def status_handler_node(state: AgentState) -> AgentState:
    """Handle status queries using TWS tools."""
    logger.debug("status_handler_start")

    state["current_node"] = "status_handler"

    try:
        # Get TWS status using tool
        from resync.tools.definitions.tws import tws_status_tool

        tws_instance = state.get("tws_instance_id")
        tool_result = await tws_status_tool(instance_id=tws_instance)

        state["tool_name"] = "tws_status"
        state["tool_output"] = json.dumps(tool_result, ensure_ascii=False)

        # Generate natural language response
        await _generate_response_from_tool(state, "status_response")

    except Exception as e:
        logger.error("status_handler_error", error=str(e))
        state["error"] = str(e)
        state["response"] = f"Não foi possível obter o status do TWS: {str(e)}"

    return state


async def troubleshoot_handler_node(state: AgentState) -> AgentState:
    """Handle troubleshooting queries."""
    logger.debug("troubleshoot_handler_start")

    state["current_node"] = "troubleshoot_handler"

    try:
        from resync.tools.definitions.tws import tws_troubleshooting_tool

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
        logger.error("troubleshoot_handler_error", error=str(e))
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
        logger.error("query_handler_error", error=str(e))
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
        logger.error("general_handler_error", error=str(e))
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
    """
    Determine the next node based on intent and clarification needs.

    Enhanced to support clarification loop - if required entities are missing,
    routes to clarification node instead of the handler.
    """
    # Check if clarification is needed first
    if state.get("needs_clarification", False):
        return "clarification"

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
    return "synthesizer"  # Changed from "output" to "synthesizer"


async def create_tws_agent_graph(
    config: AgentGraphConfig | None = None,
    checkpointer: Any | None = None,
    enable_hallucination_check: bool = True,
) -> Any:
    """
    Create the TWS agent state graph (v5.9.1 - Enhanced UX).

    Args:
        config: Graph configuration
        checkpointer: Optional checkpointer for persistence
        enable_hallucination_check: Whether to enable hallucination grading (v5.2.3.27)

    Returns:
        Compiled StateGraph (or FallbackGraph if LangGraph unavailable)

    New in v5.9.1:
    - ClarificationNode: Asks for missing info instead of guessing
    - SynthesizerNode: Transforms JSON into friendly Markdown
    
    New in v5.2.3.27:
    - HallucinationCheckNode: Validates responses are grounded in facts
    """
    config = config or AgentGraphConfig()

    if not LANGGRAPH_AVAILABLE:
        logger.warning("langgraph_not_available_using_fallback")
        return FallbackGraph(config, enable_hallucination_check=enable_hallucination_check)

    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes (including new ones)
    graph.add_node("router", router_node)
    graph.add_node("clarification", clarification_node)  # NEW
    graph.add_node("status_handler", status_handler_node)
    graph.add_node("troubleshoot_handler", troubleshoot_handler_node)
    graph.add_node("query_handler", query_handler_node)
    graph.add_node("action_handler", action_handler_node)
    graph.add_node("general_handler", general_handler_node)
    graph.add_node("validation", validation_node)
    graph.add_node("synthesizer", synthesizer_node)  # NEW (replaces response_formatter)

    # v5.2.3.27: Hallucination check node
    if enable_hallucination_check:
        graph.add_node("hallucination_check", hallucination_check_node)

    # Set entry point
    graph.set_entry_point("router")

    # Add conditional edges from router
    # Now includes "clarification" as a possible destination
    graph.add_conditional_edges(
        "router",
        _get_next_node,
        {
            "clarification": "clarification",  # NEW
            "status_handler": "status_handler",
            "troubleshoot_handler": "troubleshoot_handler",
            "query_handler": "query_handler",
            "action_handler": "action_handler",
            "general_handler": "general_handler",
        },
    )

    # Clarification goes directly to END (user needs to respond)
    graph.add_edge("clarification", END)

    # Add edges from handlers to validation
    for handler in ["status_handler", "troubleshoot_handler", "query_handler", "general_handler"]:
        graph.add_edge(handler, "validation")

    # Action handler goes directly to synthesizer (after approval)
    graph.add_edge("action_handler", "synthesizer")

    # Validation: retry or proceed to synthesizer
    graph.add_conditional_edges(
        "validation",
        _should_retry,
        {
            "retry": "router",  # Back to start for retry
            "synthesizer": "synthesizer",  # NEW: goes to synthesizer
        },
    )

    # v5.2.3.27: Synthesizer -> Hallucination Check -> End (or regenerate)
    if enable_hallucination_check:
        graph.add_edge("synthesizer", "hallucination_check")
        graph.add_conditional_edges(
            "hallucination_check",
            _should_regenerate_for_hallucination,
            {
                "regenerate": "router",  # Back to router to regenerate
                "output": END,  # Grounded, proceed to output
            },
        )
    else:
        # Without hallucination check, synthesizer goes directly to end
        graph.add_edge("synthesizer", END)

    # Compile
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info(
        "tws_agent_graph_created",
        nodes=10 if enable_hallucination_check else 9,
        checkpointing=checkpointer is not None,
        version="5.2.3.27",
        features=["clarification_loop", "synthesizer", "hallucination_check"] if enable_hallucination_check else ["clarification_loop", "synthesizer"]
    )

    return compiled


def _should_regenerate_for_hallucination(state: AgentState) -> str:
    """
    Determine if we should regenerate due to hallucination.
    
    Returns:
        - "regenerate" if hallucination detected and retries remaining
        - "output" if grounded or max retries reached
    """
    decision = state.get("hallucination_decision", GradeDecision.USEFUL.value)

    if decision == GradeDecision.NOT_GROUNDED.value:
        retry_count = state.get("hallucination_retry_count", 0)
        max_retries = state.get("max_hallucination_retries", 2)

        if retry_count < max_retries:
            logger.warning(
                "hallucination_regenerate",
                retry_count=retry_count,
                max_retries=max_retries,
            )
            return "regenerate"
        logger.error(
            "hallucination_max_retries_reached",
            retry_count=retry_count,
        )

    return "output"


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
    Updated v5.9.1: Supports clarification loop and synthesizer.
    Updated v5.2.3.27: Supports hallucination checking.
    """

    def __init__(self, config: AgentGraphConfig, enable_hallucination_check: bool = True):
        self.config = config
        self.enable_hallucination_check = enable_hallucination_check

    async def invoke(self, state: dict[str, Any]) -> AgentState:
        """Process message through the graph."""
        # Initialize state with new fields
        full_state: AgentState = {
            "message": state.get("message", ""),
            "user_id": state.get("user_id"),
            "session_id": state.get("session_id"),
            "tws_instance_id": state.get("tws_instance_id"),
            "conversation_history": state.get("conversation_history", []),
            "intent": Intent.UNKNOWN,
            "confidence": 0.0,
            "entities": {},
            # Clarification fields (NEW v5.9.1)
            "needs_clarification": False,
            "missing_entities": [],
            "clarification_question": "",
            "clarification_context": state.get("clarification_context", {}),
            # Planning fields (NEW v5.9.1)
            "planned_steps": [],
            "current_step": 0,
            "show_progress": False,
            # Processing
            "current_node": "start",
            "retry_count": 0,
            "max_retries": self.config.max_retries,
            "requires_approval": False,
            "response": "",
            "metadata": {},
            "error": None,
            "error_count": 0,
            # Raw data for synthesis
            "raw_data": {},
            "output_format": "markdown",
            # Hallucination fields (NEW v5.2.3.27)
            "hallucination_check": None,
            "is_grounded": True,
            "hallucination_decision": None,
            "hallucination_retry_count": 0,
            "max_hallucination_retries": 2,
        }

        try:
            # Router (with entity extraction)
            full_state = await router_node(full_state)

            # Check if clarification is needed (NEW v5.9.1)
            if full_state.get("needs_clarification", False):
                full_state = await clarification_node(full_state)
                return full_state  # Return early, wait for user response

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

            # Synthesize response (NEW v5.9.1 - replaces response_formatter)
            full_state = await synthesizer_node(full_state)

            # Hallucination check (NEW v5.2.3.27)
            if self.enable_hallucination_check:
                full_state = await hallucination_check_node(full_state)

                # Check if regeneration is needed (with proper loop)
                max_retries = full_state.get("max_hallucination_retries", 2)
                while (full_state.get("hallucination_decision") == GradeDecision.NOT_GROUNDED.value
                       and full_state.get("hallucination_retry_count", 0) < max_retries):
                    retry_count = full_state.get("hallucination_retry_count", 0)
                    logger.warning(
                        "fallback_hallucination_detected_regenerate",
                        retry_count=retry_count,
                        max_retries=max_retries,
                    )
                    # Increment retry and re-process
                    full_state["hallucination_retry_count"] = retry_count + 1
                    # Re-run handler and synthesizer
                    full_state = await handler(full_state)
                    full_state = await synthesizer_node(full_state)
                    full_state = await hallucination_check_node(full_state)

        except Exception as e:
            logger.error("fallback_graph_error", error=str(e))
            full_state["error"] = str(e)
            full_state["response"] = f"Erro no processamento: {str(e)}"

        return full_state

    async def astream(self, state: dict[str, Any]):
        """Stream results (just yields final result for fallback)."""
        result = await self.invoke(state)
        yield result
