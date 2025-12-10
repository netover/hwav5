"""
TWS Specialist Agents Implementation.

Provides 4 specialized AI agents coordinated by an orchestrator team:
1. Job Analyst - Return codes, ABENDs, execution analysis
2. Dependency Specialist - Predecessors, successors, impact analysis
3. Resource Specialist - Workstations, CPU/memory, conflicts
4. Knowledge Specialist - Documentation RAG, troubleshooting

Author: Resync Team
Version: 5.2.3.29
"""

import asyncio
import time
from typing import Any, Optional

import structlog

from resync.core.specialists.models import (
    DEFAULT_SPECIALIST_CONFIGS,
    DEFAULT_TEAM_CONFIG,
    QueryClassification,
    SpecialistConfig,
    SpecialistResponse,
    SpecialistType,
    TeamConfig,
    TeamExecutionMode,
    TeamResponse,
)
from resync.core.specialists.tools import (
    CalendarTool,
    DependencyGraphTool,
    ErrorCodeTool,
    JobLogTool,
    WorkstationTool,
)

logger = structlog.get_logger(__name__)

# ============================================================================
# AGNO AVAILABILITY CHECK
# ============================================================================

try:
    from agno.agent import Agent
    from agno.models.litellm import LiteLLM
    from agno.team.team import Team

    AGNO_AVAILABLE = True
    logger.info("agno_framework_available", version="1.x+")
except ImportError:
    AGNO_AVAILABLE = False
    logger.warning("agno_framework_not_available", fallback="mock_agents")

    # Mock classes for development/testing
    class Agent:
        """Mock Agent when Agno is not available."""

        def __init__(self, **kwargs):
            self.name = kwargs.get("name", "MockAgent")
            self.instructions = kwargs.get("instructions", [])
            self.tools = kwargs.get("tools", [])

        async def arun(self, message: str) -> str:
            return f"[Mock {self.name}] Processing: {message[:50]}..."

    class Team:
        """Mock Team when Agno is not available."""

        def __init__(self, **kwargs):
            self.name = kwargs.get("name", "MockTeam")
            self.members = kwargs.get("members", [])

        async def arun(self, message: str) -> str:
            responses = []
            for member in self.members:
                resp = await member.arun(message)
                responses.append(resp)
            return "\n".join(responses)

    class LiteLLM:
        """Mock LiteLLM model."""

        def __init__(self, id: str = "gpt-4o", **kwargs):
            self.id = id


# ============================================================================
# QUERY CLASSIFIER
# ============================================================================


class QueryClassifier:
    """
    Classifies queries to determine which specialists should handle them.
    """

    # Intent patterns (Portuguese + English)
    PATTERNS = {
        "job_analysis": [
            r"\b(abend|erro|error|falha|failed|falhou)\b",
            r"\b(rc|return\s*code)\s*=?\s*\d+",
            r"\b(log|output|saída)\s*(do\s*)?job\b",
            r"\bpor\s*que\b.*\b(falhou|erro|abend)\b",
            r"\bwhy\s+did\b.*\b(fail|error)\b",
        ],
        "dependency": [
            r"\b(dependência|dependency|predecessor|sucessor|successor)\b",
            r"\b(cadeia|chain|upstream|downstream)\b",
            r"\b(impacto|impact)\b.*\b(se|if)\b",
            r"\b(o\s*que\s*acontece|what\s*happens)\s*(se|if)\b",
            r"\b(critical\s*path|caminho\s*crítico)\b",
        ],
        "resource": [
            r"\b(workstation|estação|servidor|server)\b",
            r"\b(cpu|memória|memory|disco|disk)\b",
            r"\b(conflito|conflict|recurso|resource)\b",
            r"\b(online|offline|status)\b.*\b(workstation|agent)\b",
            r"\b(capacidade|capacity|disponível|available)\b",
        ],
        "knowledge": [
            r"\b(como|how)\s+(fazer|to|do|resolver|fix)\b",
            r"\b(documentação|documentation|manual|guide)\b",
            r"\b(procedimento|procedure|processo|process)\b",
            r"\b(o\s*que\s*é|what\s*is)\b",
            r"\b(troubleshooting|solução|solution)\b",
        ],
    }

    SPECIALIST_MAPPING = {
        "job_analysis": SpecialistType.JOB_ANALYST,
        "dependency": SpecialistType.DEPENDENCY,
        "resource": SpecialistType.RESOURCE,
        "knowledge": SpecialistType.KNOWLEDGE,
    }

    def classify(self, query: str) -> QueryClassification:
        """
        Classify a query and determine which specialists to use.

        Args:
            query: User query text

        Returns:
            QueryClassification with recommended specialists
        """
        import re

        query_lower = query.lower()
        matches: dict[str, int] = {}

        for intent, patterns in self.PATTERNS.items():
            match_count = 0
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    match_count += 1
            if match_count > 0:
                matches[intent] = match_count

        # Sort by match count
        sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)

        # Determine recommended specialists
        recommended = []
        for intent, _count in sorted_matches:
            specialist = self.SPECIALIST_MAPPING.get(intent)
            if specialist:
                recommended.append(specialist)

        # If no clear match, use all specialists
        if not recommended:
            recommended = list(SpecialistType)

        # Calculate confidence
        total_matches = sum(matches.values()) if matches else 0
        confidence = min(0.95, 0.5 + (total_matches * 0.15))

        # Determine query type
        query_type = sorted_matches[0][0] if sorted_matches else "general"

        # Extract entities
        entities = self._extract_entities(query)

        return QueryClassification(
            query_type=query_type,
            recommended_specialists=recommended,
            confidence=confidence,
            requires_graph="dependency" in matches,
            requires_rag="knowledge" in matches,
            requires_realtime_data="job_analysis" in matches or "resource" in matches,
            entities=entities,
        )

    def _extract_entities(self, query: str) -> dict[str, list[str]]:
        """Extract entities from query."""
        import re

        entities: dict[str, list[str]] = {
            "jobs": [],
            "workstations": [],
            "error_codes": [],
        }

        # Job names (uppercase with underscores/numbers)
        job_pattern = r"\b([A-Z][A-Z0-9_]{2,})\b"
        entities["jobs"] = re.findall(job_pattern, query)

        # Workstation names
        ws_pattern = r"\b(TWS_[A-Z0-9_]+)\b"
        entities["workstations"] = re.findall(ws_pattern, query, re.IGNORECASE)

        # Error/ABEND codes
        abend_pattern = r"\b([SU]\d{3}[A-Z]?)\b"
        rc_pattern = r"(?:rc|return\s*code)\s*=?\s*(\d+)"
        entities["error_codes"] = re.findall(abend_pattern, query, re.IGNORECASE) + [
            f"RC={rc}" for rc in re.findall(rc_pattern, query, re.IGNORECASE)
        ]

        return entities


# ============================================================================
# SPECIALIST AGENT CLASSES
# ============================================================================


class BaseSpecialist:
    """Base class for specialist agents."""

    specialist_type: SpecialistType

    def __init__(
        self,
        config: SpecialistConfig | None = None,
        model: Any | None = None,
    ):
        self.config = config or DEFAULT_SPECIALIST_CONFIGS.get(
            self.specialist_type, SpecialistConfig(specialist_type=self.specialist_type)
        )
        self.model = model or LiteLLM(id=self.config.model_name)
        self._agent: Agent | None = None
        self._initialized = False

    @property
    def name(self) -> str:
        """Agent display name."""
        return f"TWS {self.specialist_type.value.replace('_', ' ').title()}"

    @property
    def agent(self) -> Agent:
        """Lazy initialization of agent."""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    def _create_agent(self) -> Agent:
        """Create the Agno agent. Override in subclasses."""
        raise NotImplementedError

    async def process(self, query: str, context: dict | None = None) -> SpecialistResponse:
        """
        Process a query and return a response.

        Args:
            query: User query
            context: Additional context (entities, history, etc.)

        Returns:
            SpecialistResponse with results
        """
        start_time = time.time()
        tools_used = []

        try:
            # Format query with context
            formatted_query = self._format_query(query, context)

            # Run the agent
            if AGNO_AVAILABLE:
                response = await self.agent.arun(formatted_query)
                # Extract tools used if available
                if hasattr(response, "tool_calls"):
                    tools_used = [tc.name for tc in response.tool_calls]
                response_text = str(response)
            else:
                response_text = await self.agent.arun(formatted_query)

            processing_time = int((time.time() - start_time) * 1000)

            return SpecialistResponse(
                specialist_type=self.specialist_type,
                response=response_text,
                confidence=0.85,
                tools_used=tools_used,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(
                "specialist_processing_error",
                specialist=self.specialist_type.value,
                error=str(e),
            )
            return SpecialistResponse(
                specialist_type=self.specialist_type,
                response="",
                confidence=0.0,
                processing_time_ms=processing_time,
                error=str(e),
            )

    def _format_query(self, query: str, context: dict | None) -> str:
        """Format query with context for the agent."""
        if not context:
            return query

        parts = [query]

        if entities := context.get("entities"):
            if jobs := entities.get("jobs"):
                parts.append(f"\nJobs mentioned: {', '.join(jobs)}")
            if ws := entities.get("workstations"):
                parts.append(f"\nWorkstations: {', '.join(ws)}")
            if errors := entities.get("error_codes"):
                parts.append(f"\nError codes: {', '.join(errors)}")

        return "\n".join(parts)


class JobAnalystAgent(BaseSpecialist):
    """
    Specialist for job execution analysis.

    Capabilities:
    - Analyze return codes and ABEND codes
    - Review job logs and execution history
    - Identify error patterns and trends
    - Provide diagnostic recommendations
    """

    specialist_type = SpecialistType.JOB_ANALYST

    def __init__(self, config: SpecialistConfig | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.job_log_tool = JobLogTool()
        self.error_code_tool = ErrorCodeTool()

    def _create_agent(self) -> Agent:
        """Create Job Analyst agent."""
        instructions = [
            "You are a TWS Job Analyst specialist.",
            "Your expertise is analyzing job failures, return codes, and ABEND codes.",
            "When analyzing a job failure:",
            "1. First check the return code and explain its meaning",
            "2. If there's an ABEND code, provide detailed explanation",
            "3. Review job history for patterns",
            "4. Provide specific, actionable recommendations",
            "Always be precise and include relevant error codes in your response.",
        ]

        if self.config.custom_instructions:
            instructions.append(self.config.custom_instructions)

        return Agent(
            name=self.name,
            model=self.model,
            tools=[
                self.job_log_tool.get_job_log,
                self.job_log_tool.analyze_return_code,
                self.job_log_tool.analyze_abend_code,
                self.job_log_tool.get_job_history,
                self.error_code_tool.lookup_error,
            ],
            instructions=instructions,
        )


class DependencySpecialist(BaseSpecialist):
    """
    Specialist for dependency and workflow analysis.

    Capabilities:
    - Trace predecessor/successor chains
    - Analyze job dependencies
    - Assess impact of failures
    - Identify critical paths
    """

    specialist_type = SpecialistType.DEPENDENCY

    def __init__(self, config: SpecialistConfig | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.dependency_tool = DependencyGraphTool()

    def _create_agent(self) -> Agent:
        """Create Dependency Specialist agent."""
        instructions = [
            "You are a TWS Dependency Specialist.",
            "Your expertise is analyzing job dependencies and workflow graphs.",
            "When analyzing dependencies:",
            "1. Identify all predecessor and successor jobs",
            "2. Trace the critical path through the workflow",
            "3. Assess impact of failures on downstream jobs",
            "4. Identify potential bottlenecks",
            "Present dependency information in a clear, hierarchical format.",
        ]

        if self.config.custom_instructions:
            instructions.append(self.config.custom_instructions)

        return Agent(
            name=self.name,
            model=self.model,
            tools=[
                self.dependency_tool.get_predecessors,
                self.dependency_tool.get_successors,
                self.dependency_tool.analyze_impact,
                self.dependency_tool.detect_cycles,
            ],
            instructions=instructions,
        )


class ResourceSpecialist(BaseSpecialist):
    """
    Specialist for resource and capacity analysis.

    Capabilities:
    - Monitor workstation status
    - Analyze resource usage
    - Detect conflicts
    - Check scheduling windows
    """

    specialist_type = SpecialistType.RESOURCE

    def __init__(self, config: SpecialistConfig | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.workstation_tool = WorkstationTool()
        self.calendar_tool = CalendarTool()

    def _create_agent(self) -> Agent:
        """Create Resource Specialist agent."""
        instructions = [
            "You are a TWS Resource Specialist.",
            "Your expertise is monitoring resources, workstations, and capacity.",
            "When analyzing resources:",
            "1. Check workstation status and availability",
            "2. Identify resource conflicts or contention",
            "3. Verify scheduling windows and calendars",
            "4. Recommend optimal scheduling",
            "Provide clear status information and actionable recommendations.",
        ]

        if self.config.custom_instructions:
            instructions.append(self.config.custom_instructions)

        return Agent(
            name=self.name,
            model=self.model,
            tools=[
                self.workstation_tool.get_workstation_status,
                self.workstation_tool.check_resource_availability,
                self.workstation_tool.get_resource_conflicts,
                self.calendar_tool.get_calendar_schedule,
                self.calendar_tool.check_scheduling_window,
            ],
            instructions=instructions,
        )


class KnowledgeSpecialist(BaseSpecialist):
    """
    Specialist for documentation and troubleshooting knowledge.

    Capabilities:
    - Search TWS documentation
    - Find troubleshooting guides
    - Provide best practices
    - Answer how-to questions
    """

    specialist_type = SpecialistType.KNOWLEDGE

    def __init__(
        self,
        config: SpecialistConfig | None = None,
        knowledge_base: Any | None = None,
        **kwargs,
    ):
        super().__init__(config, **kwargs)
        self.knowledge_base = knowledge_base

    def _create_agent(self) -> Agent:
        """Create Knowledge Specialist agent."""
        instructions = [
            "You are a TWS Knowledge Specialist.",
            "Your expertise is TWS documentation, procedures, and best practices.",
            "When providing information:",
            "1. Search the knowledge base for relevant documentation",
            "2. Provide step-by-step procedures when applicable",
            "3. Reference official IBM/HCL documentation",
            "4. Include best practices and common pitfalls",
            "Always cite sources and provide actionable guidance.",
        ]

        if self.config.custom_instructions:
            instructions.append(self.config.custom_instructions)

        agent_kwargs = {
            "name": self.name,
            "model": self.model,
            "instructions": instructions,
        }

        # Add knowledge base if available and Agno supports it
        if AGNO_AVAILABLE and self.knowledge_base:
            agent_kwargs["knowledge"] = self.knowledge_base
            agent_kwargs["search_knowledge"] = True

        return Agent(**agent_kwargs)


# ============================================================================
# TEAM ORCHESTRATOR
# ============================================================================


class TWSSpecialistTeam:
    """
    Orchestrates the 4 specialist agents as a coordinated team.

    Handles:
    - Query classification and routing
    - Parallel specialist execution
    - Response synthesis
    - Error handling and fallbacks
    """

    def __init__(
        self,
        config: TeamConfig | None = None,
        knowledge_base: Any | None = None,
    ):
        self.config = config or DEFAULT_TEAM_CONFIG
        self.knowledge_base = knowledge_base

        self.classifier = QueryClassifier()

        # Initialize specialists
        self.specialists: dict[SpecialistType, BaseSpecialist] = {}
        self._init_specialists()

        # Initialize team (if Agno available)
        self._team: Team | None = None

        logger.info(
            "specialist_team_initialized",
            specialists=list(self.specialists.keys()),
            execution_mode=self.config.execution_mode,
        )

    def _init_specialists(self):
        """Initialize all specialist agents."""
        specialist_classes = {
            SpecialistType.JOB_ANALYST: JobAnalystAgent,
            SpecialistType.DEPENDENCY: DependencySpecialist,
            SpecialistType.RESOURCE: ResourceSpecialist,
            SpecialistType.KNOWLEDGE: KnowledgeSpecialist,
        }

        for spec_type, spec_class in specialist_classes.items():
            spec_config = self.config.specialists.get(
                spec_type, DEFAULT_SPECIALIST_CONFIGS.get(spec_type)
            )

            if spec_config and spec_config.enabled:
                kwargs = {}
                if spec_type == SpecialistType.KNOWLEDGE:
                    kwargs["knowledge_base"] = self.knowledge_base

                self.specialists[spec_type] = spec_class(config=spec_config, **kwargs)

    @property
    def team(self) -> Team | None:
        """Lazy initialization of Agno Team."""
        if not AGNO_AVAILABLE:
            return None

        if self._team is None and self.specialists:
            members = [spec.agent for spec in self.specialists.values()]

            self._team = Team(
                name="TWS AI Assistant Team",
                mode=self.config.execution_mode.value,
                model=LiteLLM(id=self.config.orchestrator_model),
                members=members,
                enable_agentic_context=True,
                send_team_context_to_members=True,
                instructions=[
                    "Analyze the query and delegate to appropriate specialists.",
                    "Run independent specialists in parallel when possible.",
                    "Synthesize findings into a coherent, actionable response.",
                    "If specialists provide conflicting information, note the discrepancy.",
                ],
            )

        return self._team

    async def process(
        self,
        query: str,
        context: dict | None = None,
        use_all_specialists: bool = False,
    ) -> TeamResponse:
        """
        Process a query using the specialist team.

        Args:
            query: User query
            context: Additional context
            use_all_specialists: Force all specialists to respond

        Returns:
            TeamResponse with synthesized results
        """
        start_time = time.time()

        # Classify query
        classification = self.classifier.classify(query)

        # Determine which specialists to use
        if use_all_specialists:
            specialists_to_use = list(self.specialists.values())
        else:
            specialists_to_use = [
                self.specialists[spec_type]
                for spec_type in classification.recommended_specialists
                if spec_type in self.specialists
            ]

        # If no specialists matched, use all
        if not specialists_to_use:
            specialists_to_use = list(self.specialists.values())

        logger.info(
            "processing_query",
            query_type=classification.query_type,
            specialists=[s.specialist_type.value for s in specialists_to_use],
            parallel=self.config.parallel_execution,
        )

        # Add entities to context
        context = context or {}
        context["entities"] = classification.entities

        # Execute specialists
        if self.config.parallel_execution:
            specialist_responses = await self._execute_parallel(specialists_to_use, query, context)
        else:
            specialist_responses = await self._execute_sequential(
                specialists_to_use, query, context
            )

        # Synthesize responses
        synthesized = await self._synthesize_responses(query, specialist_responses, classification)

        total_time = int((time.time() - start_time) * 1000)

        return TeamResponse(
            query=query,
            synthesized_response=synthesized,
            specialist_responses=specialist_responses,
            execution_mode=self.config.execution_mode,
            total_processing_time_ms=total_time,
            specialists_used=[r.specialist_type for r in specialist_responses if r.is_successful],
            query_classification=classification.query_type,
            confidence=self._calculate_confidence(specialist_responses),
        )

    async def _execute_parallel(
        self,
        specialists: list[BaseSpecialist],
        query: str,
        context: dict,
    ) -> list[SpecialistResponse]:
        """Execute specialists in parallel."""
        tasks = [
            spec.process(query, context)
            for spec in specialists[: self.config.max_parallel_specialists]
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        result = []
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                result.append(
                    SpecialistResponse(
                        specialist_type=specialists[i].specialist_type,
                        response="",
                        confidence=0.0,
                        error=str(resp),
                    )
                )
            else:
                result.append(resp)

        return result

    async def _execute_sequential(
        self,
        specialists: list[BaseSpecialist],
        query: str,
        context: dict,
    ) -> list[SpecialistResponse]:
        """Execute specialists sequentially."""
        responses = []
        for spec in specialists:
            try:
                resp = await spec.process(query, context)
                responses.append(resp)
            except Exception as e:
                responses.append(
                    SpecialistResponse(
                        specialist_type=spec.specialist_type,
                        response="",
                        confidence=0.0,
                        error=str(e),
                    )
                )
        return responses

    async def _synthesize_responses(
        self,
        query: str,
        responses: list[SpecialistResponse],
        classification: QueryClassification,
    ) -> str:
        """Synthesize specialist responses into a coherent answer."""
        successful_responses = [r for r in responses if r.is_successful]

        if not successful_responses:
            return "Desculpe, não foi possível processar sua consulta no momento. Por favor, tente novamente."

        # If using Agno Team with synthesizer
        if self.team and AGNO_AVAILABLE:
            try:
                synthesis_prompt = self._build_synthesis_prompt(
                    query, successful_responses, classification
                )
                result = await self.team.arun(synthesis_prompt)
                return str(result)
            except Exception as e:
                logger.warning("team_synthesis_failed", error=str(e))

        # Fallback: simple concatenation with structure
        return self._simple_synthesis(query, successful_responses, classification)

    def _build_synthesis_prompt(
        self,
        query: str,
        responses: list[SpecialistResponse],
        classification: QueryClassification,
    ) -> str:
        """Build prompt for synthesis."""
        parts = [
            f"Original query: {query}",
            f"Query type: {classification.query_type}",
            "",
            "Specialist findings:",
        ]

        for resp in responses:
            parts.append(f"\n## {resp.specialist_type.value.replace('_', ' ').title()}")
            parts.append(resp.response)

        parts.append("\n\nSynthesize these findings into a coherent response.")

        return "\n".join(parts)

    def _simple_synthesis(
        self,
        query: str,
        responses: list[SpecialistResponse],
        classification: QueryClassification,
    ) -> str:
        """Simple synthesis without LLM."""
        parts = [f"**Análise: {classification.query_type.replace('_', ' ').title()}**\n"]

        for resp in responses:
            title = resp.specialist_type.value.replace("_", " ").title()
            parts.append(f"### {title}")
            parts.append(resp.response)
            parts.append("")

        return "\n".join(parts)

    def _calculate_confidence(self, responses: list[SpecialistResponse]) -> float:
        """Calculate overall confidence from specialist responses."""
        successful = [r.confidence for r in responses if r.is_successful]
        if not successful:
            return 0.0
        return sum(successful) / len(successful)


# ============================================================================
# SINGLETON AND FACTORY
# ============================================================================

_specialist_team_instance: TWSSpecialistTeam | None = None


def get_specialist_team() -> TWSSpecialistTeam | None:
    """Get the singleton specialist team instance."""
    return _specialist_team_instance


async def create_specialist_team(
    config: TeamConfig | None = None,
    knowledge_base: Any | None = None,
) -> TWSSpecialistTeam:
    """
    Create and initialize the specialist team.

    Args:
        config: Team configuration
        knowledge_base: Knowledge base for RAG

    Returns:
        Initialized TWSSpecialistTeam
    """
    global _specialist_team_instance

    _specialist_team_instance = TWSSpecialistTeam(
        config=config,
        knowledge_base=knowledge_base,
    )

    logger.info("specialist_team_created")
    return _specialist_team_instance


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AGNO_AVAILABLE",
    "QueryClassifier",
    "BaseSpecialist",
    "JobAnalystAgent",
    "DependencySpecialist",
    "ResourceSpecialist",
    "KnowledgeSpecialist",
    "TWSSpecialistTeam",
    "get_specialist_team",
    "create_specialist_team",
]
