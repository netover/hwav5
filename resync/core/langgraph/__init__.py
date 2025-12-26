"""
LangGraph Integration for Resync.

This module provides agent orchestration through state graphs:
- Conditional routing based on intent
- Automatic retry loops with error injection
- Human-in-the-loop approval flows
- Checkpointing for conversation persistence
- Tool calling with validation
- Autonomous diagnostic resolution (v5.4.0)
- Hallucination detection and grading (v5.2.3.27)

Architecture:
    User Message -> Router Node -> [Handler Nodes] -> Response
                            ↓
                    Tool Node -> Validate Node
                            ↓ (if error)
                    Retry Node (back to Tool)

v5.4.0 Diagnostic Graph:
    Problem -> Diagnose -> Research -> Verify -> Propose -> [Execute] -> End
                 ↑__________________________|
                      (if confidence < threshold)

v5.2.3.27 Hallucination Grader:
    Response -> Hallucination Check -> [Grounded] -> Output
                        ↓
                  [Not Grounded] -> Regenerate

Usage:
    from resync.core.langgraph import create_tws_agent_graph, diagnose_problem

    # Standard agent
    graph = await create_tws_agent_graph()
    result = await graph.invoke({"message": "status do TWS"})

    # Autonomous diagnosis (v5.4.0)
    result = await diagnose_problem("Job AWSBH001 falhou com erro ABND")

    # Hallucination check (v5.2.3.27)
    from resync.core.langgraph import grade_hallucination
    result = await grade_hallucination(documents, generation, question)
"""

from resync.core.langgraph.agent_graph import (
    AgentGraphConfig,
    AgentState,
    create_router_graph,
    create_tws_agent_graph,
)
from resync.core.langgraph.checkpointer import (
    PostgresCheckpointer,
    get_checkpointer,
)

# v5.4.0: Autonomous diagnostic resolution
from resync.core.langgraph.diagnostic_graph import (
    DiagnosticConfig,
    DiagnosticPhase,
    DiagnosticState,
    create_diagnostic_graph,
    diagnose_problem,
)

# v5.2.3.27: Hallucination Grader
from resync.core.langgraph.hallucination_grader import (
    GradeAnswer,
    GradeDecision,
    GradeHallucinations,
    HallucinationGradeResult,
    HallucinationGrader,
    get_hallucination_grader,
    get_hallucination_route,
    grade_hallucination,
    hallucination_check_node,
    is_response_grounded,
)
from resync.core.langgraph.nodes import (
    HumanApprovalNode,
    LLMNode,
    RouterNode,
    ToolNode,
    ValidationNode,
)

__all__ = [
    # Agent Graph
    "AgentGraphConfig",
    "AgentState",
    "create_tws_agent_graph",
    "create_router_graph",
    # Nodes
    "RouterNode",
    "LLMNode",
    "ToolNode",
    "ValidationNode",
    "HumanApprovalNode",
    # Checkpointer
    "PostgresCheckpointer",
    "get_checkpointer",
    # v5.4.0: Diagnostic Graph
    "DiagnosticConfig",
    "DiagnosticPhase",
    "DiagnosticState",
    "create_diagnostic_graph",
    "diagnose_problem",
    # v5.2.3.27: Hallucination Grader
    "HallucinationGrader",
    "GradeHallucinations",
    "GradeAnswer",
    "GradeDecision",
    "HallucinationGradeResult",
    "grade_hallucination",
    "is_response_grounded",
    "get_hallucination_grader",
    "hallucination_check_node",
    "get_hallucination_route",
]
