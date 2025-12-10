"""
Intelligent Agent Router for Resync.

This module provides automatic agent selection based on user intent classification.
Instead of requiring users to manually select an agent, the router analyzes the
user's message and automatically routes it to the most appropriate handler.

Architecture:
    User Message → Intent Classifier → Agent Router → Appropriate Handler → Response

Features:
    - Zero-configuration for end users
    - Automatic intent detection using keyword analysis and LLM classification
    - Seamless context switching between different expertise areas
    - Fallback to general assistant for ambiguous queries
    - Extensible handler system for future agent types
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# INTENT CLASSIFICATION
# =============================================================================


class Intent(str, Enum):
    """
    Classified intents for user messages.
    Each intent maps to a specific handling strategy.
    """

    # TWS Operations
    STATUS = "status"  # Check system/job/workstation status
    TROUBLESHOOTING = "troubleshooting"  # Diagnose and fix issues
    JOB_MANAGEMENT = "job_management"  # Run, stop, rerun jobs
    MONITORING = "monitoring"  # Real-time monitoring queries

    # Analysis & Reporting
    ANALYSIS = "analysis"  # Deep analysis of patterns/trends
    REPORTING = "reporting"  # Generate reports

    # General
    GENERAL = "general"  # General questions, help
    GREETING = "greeting"  # Hello, hi, etc.

    # System
    UNKNOWN = "unknown"  # Cannot classify


@dataclass
class IntentClassification:
    """Result of intent classification."""

    primary_intent: Intent
    confidence: float  # 0.0 to 1.0
    secondary_intents: list[Intent] = field(default_factory=list)
    entities: dict[str, Any] = field(default_factory=dict)
    requires_tools: bool = False

    @property
    def is_high_confidence(self) -> bool:
        """Check if classification confidence is high enough for routing."""
        return self.confidence >= 0.7

    @property
    def needs_clarification(self) -> bool:
        """Check if we should ask for clarification."""
        return self.confidence < 0.4


class IntentClassifier:
    """
    Classifies user messages into intents using a combination of
    rule-based keyword matching and optional LLM enhancement.
    """

    # Keyword patterns for each intent (Portuguese and English)
    INTENT_PATTERNS: dict[Intent, list[str]] = {
        Intent.STATUS: [
            r"\bstatus\b",
            r"\bsituação\b",
            r"\bestado\b",
            r"\bcomo\s+est[áa]\b",
            r"\bqual\s+o\s+status\b",
            r"\bworkstation[s]?\b",
            r"\bjob[s]?\b.*\b(rodando|executando|running)\b",
            r"\bonline\b",
            r"\boffline\b",
            r"\blinked\b",
            r"\bunlinked\b",
            r"\bativo[s]?\b",
            r"\binativo[s]?\b",
        ],
        Intent.TROUBLESHOOTING: [
            r"\babend\b",
            r"\berro[s]?\b",
            r"\bfalha[s]?\b",
            r"\bfailed\b",
            r"\bproblema[s]?\b",
            r"\bissue[s]?\b",
            r"\bbug[s]?\b",
            r"\bpor\s*que\b.*\b(falhou|erro|abend)\b",
            r"\bcausa\b",
            r"\broot\s*cause\b",
            r"\bdiagn[oó]stic\b",
            r"\bresolver\b",
            r"\bfix\b",
            r"\bcorrigir\b",
            r"\bsolução\b",
            r"\binvestigar\b",
            r"\banalisar\s+(erro|falha|problema)\b",
            r"\brc\s*=\s*\d+\b",
            r"\breturn\s*code\b",
        ],
        Intent.JOB_MANAGEMENT: [
            r"\bexecutar\b",
            r"\brodar\b",
            r"\brun\b",
            r"\bstart\b",
            r"\bparar\b",
            r"\bstop\b",
            r"\bcancel\b",
            r"\bkill\b",
            r"\brerun\b",
            r"\breexecutar\b",
            r"\breiniciar\b",
            r"\bsubmit\b",
            r"\brelease\b",
            r"\bhold\b",
            r"\bagendar\b",
            r"\bschedule\b",
        ],
        Intent.MONITORING: [
            r"\bmonitor\w*\b",
            r"\bacompanhar\b",
            r"\bwatch\b",
            r"\balert[as]?\b",
            r"\bnotifica\w*\b",
            r"\btempo\s+real\b",
            r"\breal[\s-]*time\b",
            r"\bdashboard\b",
            r"\bmétricas?\b",
            r"\bmetrics?\b",
        ],
        Intent.ANALYSIS: [
            r"\banalis[ae]\w*\b",
            r"\banalyz[e]?\w*\b",
            r"\btendênci\w*\b",
            r"\btrend[s]?\b",
            r"\bpadr[ãa]o\b",
            r"\bpattern[s]?\b",
            r"\bhistóric\w*\b",
            r"\bhistor\w*\b",
            r"\bcompar\w*\b",
            r"\bcorrelação\b",
            r"\bperformance\b",
            r"\bdesempenho\b",
        ],
        Intent.REPORTING: [
            r"\brelatório\w*\b",
            r"\breport\w*\b",
            r"\bgerar\b.*\b(relatório|report)\b",
            r"\bexport\w*\b",
            r"\bextrair\b",
            r"\bressum\w*\b",
            r"\bsummar\w*\b",
            r"\bdocument\w*\b",
        ],
        Intent.GREETING: [
            r"^(ol[áa]|oi|hey|hi|hello|bom\s*dia|boa\s*(tarde|noite))[\s!?.,]*$",
            r"^(tudo\s*bem|como\s*vai)[\s!?.,]*$",
        ],
        Intent.GENERAL: [
            r"\bajud[ae]\b",
            r"\bhelp\b",
            r"\bo\s*que\s*(é|são|significa)\b",
            r"\bwhat\s*is\b",
            r"\bcomo\s+(funciona|usar|faz)\b",
            r"\bhow\s+(to|do|does)\b",
            r"\bexplica\w*\b",
            r"\bexplain\b",
        ],
    }

    # Entity extraction patterns
    ENTITY_PATTERNS: dict[str, str] = {
        "job_name": r"\bjob\s+([A-Z0-9_]+)\b|\b([A-Z][A-Z0-9_]{2,})\b",
        "workstation": r"\bworkstation\s+([A-Z0-9_]+)\b|\b(TWS_[A-Z0-9_]+)\b",
        "error_code": r"\brc\s*=\s*(\d+)\b|\breturn\s*code\s*(\d+)\b",
        "time_reference": r"\b(hoje|ontem|última\s+hora|last\s+hour|yesterday|today)\b",
    }

    def __init__(self, llm_classifier: Callable | None = None):
        """
        Initialize the classifier.

        Args:
            llm_classifier: Optional async function for LLM-based classification
                           enhancement. Signature: async (message: str) -> Intent
        """
        self.llm_classifier = llm_classifier
        self._compiled_patterns: dict[Intent, list[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        for intent, patterns in self.INTENT_PATTERNS.items():
            self._compiled_patterns[intent] = [
                re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns
            ]

    def classify(self, message: str) -> IntentClassification:
        """
        Classify a user message into an intent.

        Args:
            message: The user's input message

        Returns:
            IntentClassification with primary intent and metadata
        """
        message = message.strip()

        if not message:
            return IntentClassification(primary_intent=Intent.UNKNOWN, confidence=0.0)

        # Score each intent based on pattern matches
        scores: dict[Intent, float] = {}

        for intent, patterns in self._compiled_patterns.items():
            match_count = sum(1 for pattern in patterns if pattern.search(message))
            if match_count > 0:
                # Score based on matches relative to total patterns
                scores[intent] = min(1.0, match_count / max(2, len(patterns) * 0.3))

        # Extract entities
        entities = self._extract_entities(message)

        # Determine primary intent
        if not scores:
            return IntentClassification(
                primary_intent=Intent.GENERAL,
                confidence=0.5,
                entities=entities,
                requires_tools=False,
            )

        # Sort by score
        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_intent, confidence = sorted_intents[0]

        # Get secondary intents
        secondary = [intent for intent, score in sorted_intents[1:3] if score >= 0.3]

        # Determine if tools are needed
        requires_tools = primary_intent in {
            Intent.STATUS,
            Intent.TROUBLESHOOTING,
            Intent.JOB_MANAGEMENT,
            Intent.MONITORING,
            Intent.ANALYSIS,
        }

        logger.debug(
            "intent_classified",
            message_preview=message[:50],
            primary_intent=primary_intent.value,
            confidence=confidence,
            secondary_intents=[i.value for i in secondary],
            entities=entities,
        )

        return IntentClassification(
            primary_intent=primary_intent,
            confidence=confidence,
            secondary_intents=secondary,
            entities=entities,
            requires_tools=requires_tools,
        )

    def _extract_entities(self, message: str) -> dict[str, Any]:
        """Extract named entities from the message."""
        entities = {}

        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            matches = re.findall(pattern, message, re.IGNORECASE)
            if matches:
                # Flatten tuple matches and filter empty strings
                values = [
                    m if isinstance(m, str) else next((v for v in m if v), None) for m in matches
                ]
                values = [v for v in values if v]
                if values:
                    entities[entity_type] = values[0] if len(values) == 1 else values

        return entities

    async def classify_with_llm(self, message: str) -> IntentClassification:
        """
        Enhanced classification using LLM for ambiguous cases.
        Falls back to rule-based classification if LLM is unavailable.
        """
        # First, try rule-based classification
        classification = self.classify(message)

        # If confidence is high enough, return as-is
        if classification.is_high_confidence:
            return classification

        # If LLM classifier is available and confidence is low, use it
        if self.llm_classifier and classification.confidence < 0.6:
            try:
                llm_intent = await self.llm_classifier(message)
                if llm_intent and llm_intent != Intent.UNKNOWN:
                    return IntentClassification(
                        primary_intent=llm_intent,
                        confidence=0.85,  # LLM classifications get moderate-high confidence
                        secondary_intents=classification.secondary_intents,
                        entities=classification.entities,
                        requires_tools=llm_intent
                        in {
                            Intent.STATUS,
                            Intent.TROUBLESHOOTING,
                            Intent.JOB_MANAGEMENT,
                            Intent.MONITORING,
                            Intent.ANALYSIS,
                        },
                    )
            except Exception as e:
                logger.warning("llm_classification_failed", error=str(e))

        return classification


# =============================================================================
# AGENT ROUTER
# =============================================================================


class MessageHandler(Protocol):
    """Protocol for message handlers."""

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        """Handle a message and return response."""
        ...


@dataclass
class RoutingResult:
    """Result of message routing."""

    handler_name: str
    classification: IntentClassification
    response: str
    tools_used: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class AgentRouter:
    """
    Routes user messages to appropriate handlers based on intent classification.

    This is the main entry point for the unified agent interface. Users interact
    with a single "Resync AI Assistant" and the router handles all the complexity
    of selecting the right expertise/handler for their query.

    Usage:
        router = AgentRouter(agent_manager)
        response = await router.route("Quais jobs estão em ABEND?")
    """

    def __init__(self, agent_manager: Any, classifier: IntentClassifier | None = None):
        """
        Initialize the router.

        Args:
            agent_manager: The AgentManager instance for accessing agents and tools
            classifier: Optional custom classifier (defaults to IntentClassifier)
        """
        self.agent_manager = agent_manager
        self.classifier = classifier or IntentClassifier()
        self._handlers: dict[Intent, MessageHandler] = {}
        self._setup_default_handlers()

    def _setup_default_handlers(self) -> None:
        """Register default handlers for each intent."""
        # Create handler instances
        self._handlers = {
            Intent.STATUS: StatusHandler(self.agent_manager),
            Intent.TROUBLESHOOTING: TroubleshootingHandler(self.agent_manager),
            Intent.JOB_MANAGEMENT: JobManagementHandler(self.agent_manager),
            Intent.MONITORING: MonitoringHandler(self.agent_manager),
            Intent.ANALYSIS: AnalysisHandler(self.agent_manager),
            Intent.REPORTING: ReportingHandler(self.agent_manager),
            Intent.GREETING: GreetingHandler(self.agent_manager),
            Intent.GENERAL: GeneralHandler(self.agent_manager),
            Intent.UNKNOWN: GeneralHandler(self.agent_manager),
        }

    def register_handler(self, intent: Intent, handler: MessageHandler) -> None:
        """Register a custom handler for an intent."""
        self._handlers[intent] = handler
        logger.info("handler_registered", intent=intent.value, handler=type(handler).__name__)

    async def route(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        use_llm_classification: bool = False,
    ) -> RoutingResult:
        """
        Route a message to the appropriate handler.

        Args:
            message: The user's input message
            context: Optional context dict (conversation history, user info, etc.)
            use_llm_classification: Whether to use LLM for classification enhancement

        Returns:
            RoutingResult with handler name, classification, and response
        """
        import time

        start_time = time.perf_counter()

        context = context or {}

        # Classify the message
        if use_llm_classification:
            classification = await self.classifier.classify_with_llm(message)
        else:
            classification = self.classifier.classify(message)

        # Get the appropriate handler
        handler = self._handlers.get(classification.primary_intent, self._handlers[Intent.GENERAL])

        logger.info(
            "routing_message",
            intent=classification.primary_intent.value,
            confidence=classification.confidence,
            handler=type(handler).__name__,
            entities=classification.entities,
        )

        # Handle the message
        try:
            response = await handler.handle(message, context, classification)
            tools_used = getattr(handler, "last_tools_used", [])
        except Exception as e:
            logger.error("handler_error", error=str(e), handler=type(handler).__name__)
            response = (
                "Desculpe, ocorreu um erro ao processar sua solicitação. "
                "Por favor, tente novamente ou reformule sua pergunta."
            )
            tools_used = []

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return RoutingResult(
            handler_name=type(handler).__name__,
            classification=classification,
            response=response,
            tools_used=tools_used,
            processing_time_ms=elapsed_ms,
        )

    async def route_with_streaming(self, message: str, context: dict[str, Any] | None = None):
        """
        Route a message and stream the response.
        Yields response chunks as they become available.
        """
        # For now, just wrap the regular route
        # Can be enhanced later for true streaming
        result = await self.route(message, context)
        yield result.response


# =============================================================================
# INTENT HANDLERS
# =============================================================================


class BaseHandler(ABC):
    """Base class for all intent handlers."""

    def __init__(self, agent_manager: Any):
        self.agent_manager = agent_manager
        self.last_tools_used: list[str] = []

    @abstractmethod
    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        """Handle the message and return a response."""

    async def _get_tws_tools(self) -> dict[str, Any]:
        """Get available TWS tools from agent manager."""
        return getattr(self.agent_manager, "tools", {})

    async def _call_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """Call a tool and track usage."""
        tools = await self._get_tws_tools()
        if tool_name in tools:
            self.last_tools_used.append(tool_name)
            tool_func = tools[tool_name]
            if callable(tool_func):
                return await tool_func(*args, **kwargs)
        return None

    async def _get_agent_response(self, agent_id: str, message: str) -> str:
        """Get response from a specific agent."""
        agent = await self.agent_manager.get_agent(agent_id)
        if agent and hasattr(agent, "arun"):
            return await agent.arun(message)
        return ""


class StatusHandler(BaseHandler):
    """Handler for status-related queries."""

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        self.last_tools_used = []

        try:
            # Use the TWS status tool
            status_result = await self._call_tool("get_tws_status")

            if status_result:
                return status_result

            # Fallback to agent
            return await self._get_agent_response("tws-general", message)

        except Exception as e:
            logger.error("status_handler_error", error=str(e))
            return (
                "Não foi possível obter o status do sistema no momento. "
                "Verifique se a conexão com o TWS está ativa."
            )


class TroubleshootingHandler(BaseHandler):
    """Handler for troubleshooting and diagnostic queries."""

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        self.last_tools_used = []

        try:
            # First, analyze failures
            analysis_result = await self._call_tool("analyze_tws_failures")

            # If specific job mentioned, add context
            job_name = classification.entities.get("job_name")
            if job_name:
                # Could add more specific job analysis here
                pass

            if analysis_result:
                # Enhance with troubleshooting agent for recommendations
                agent_response = await self._get_agent_response(
                    "tws-troubleshooting",
                    f"Com base nesta análise, sugira soluções:\n{analysis_result}\n\nPergunta original: {message}",
                )

                if agent_response and agent_response != analysis_result:
                    return f"{analysis_result}\n\n**Recomendações:**\n{agent_response}"
                return analysis_result

            return await self._get_agent_response("tws-troubleshooting", message)

        except Exception as e:
            logger.error("troubleshooting_handler_error", error=str(e))
            return (
                "Não foi possível realizar a análise de problemas. "
                "Tente verificar manualmente o console do TWS."
            )


class JobManagementHandler(BaseHandler):
    """Handler for job management operations."""

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        self.last_tools_used = []

        # Job management requires careful handling due to potential impact
        job_name = classification.entities.get("job_name")

        if not job_name:
            return (
                "Para executar operações em jobs, preciso que você especifique "
                "o nome do job. Por exemplo: 'Rerun do job ETL_DAILY_BACKUP'"
            )

        # For safety, confirm destructive operations
        destructive_keywords = ["stop", "cancel", "kill", "parar", "cancelar"]
        is_destructive = any(kw in message.lower() for kw in destructive_keywords)

        if is_destructive:
            return (
                f"⚠️ **Confirmação Necessária**\n\n"
                f"Você solicitou uma operação que pode interromper o job `{job_name}`.\n\n"
                f"Por favor, confirme digitando: 'Confirmo {message.lower()}'"
            )

        # For now, delegate to agent for safe operations
        return await self._get_agent_response("tws-general", message)


class MonitoringHandler(BaseHandler):
    """Handler for monitoring-related queries."""

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        self.last_tools_used = []

        # Get current status first
        status = await self._call_tool("get_tws_status")

        response = "**📊 Monitoramento TWS**\n\n"

        if status:
            response += f"{status}\n\n"

        response += (
            "💡 **Dica:** Use o dashboard para monitoramento em tempo real "
            "ou configure alertas em Configurações > Notificações."
        )

        return response


class AnalysisHandler(BaseHandler):
    """Handler for analysis and trend queries."""

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        self.last_tools_used = []

        # For deep analysis, use the troubleshooting agent with analysis focus
        return await self._get_agent_response(
            "tws-troubleshooting", f"Realize uma análise detalhada: {message}"
        )


class ReportingHandler(BaseHandler):
    """Handler for report generation requests."""

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        self.last_tools_used = []

        return (
            "📝 **Geração de Relatórios**\n\n"
            "Para gerar relatórios, você pode:\n\n"
            "1. **Relatório de Status:** Acesse Dashboard > Exportar\n"
            "2. **Relatório de Falhas:** Vá em Análise > Histórico de Falhas\n"
            "3. **Relatório Personalizado:** Configurações > Relatórios\n\n"
            "Posso ajudar a filtrar dados específicos para seu relatório. "
            "Qual período ou tipo de informação você precisa?"
        )


class GreetingHandler(BaseHandler):
    """Handler for greetings."""

    GREETINGS = [
        "Olá! 👋 Sou o assistente do Resync. Como posso ajudar com o TWS hoje?",
        "Oi! Estou aqui para ajudar com operações do TWS. O que você precisa?",
        "Olá! Posso ajudar com status, troubleshooting, ou gerenciamento de jobs do TWS.",
    ]

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        import random

        return random.choice(self.GREETINGS)


class GeneralHandler(BaseHandler):
    """Handler for general queries and fallback."""

    async def handle(
        self, message: str, context: dict[str, Any], classification: IntentClassification
    ) -> str:
        self.last_tools_used = []

        # Try the general assistant agent
        response = await self._get_agent_response("tws-general", message)

        if response:
            return response

        # Ultimate fallback
        return (
            "Entendi sua pergunta. Posso ajudar com:\n\n"
            "• **Status:** Verificar situação de jobs e workstations\n"
            "• **Troubleshooting:** Diagnosticar e resolver problemas\n"
            "• **Monitoramento:** Acompanhar execuções em tempo real\n"
            "• **Análise:** Identificar padrões e tendências\n\n"
            "Como posso ajudar?"
        )


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_router(agent_manager: Any) -> AgentRouter:
    """
    Factory function to create a configured AgentRouter.

    Args:
        agent_manager: The AgentManager instance

    Returns:
        Configured AgentRouter ready for use
    """
    classifier = IntentClassifier()
    router = AgentRouter(agent_manager, classifier)

    logger.info(
        "agent_router_created",
        handlers=list(router._handlers.keys()),
    )

    return router


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

__all__ = [
    "Intent",
    "IntentClassification",
    "IntentClassifier",
    "AgentRouter",
    "RoutingResult",
    "BaseHandler",
    "create_router",
]
