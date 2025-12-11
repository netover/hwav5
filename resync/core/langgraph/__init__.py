"""
LangGraph Integration for Resync.

This module provides agent orchestration through state graphs:
- Conditional routing based on intent
- Automatic retry loops with error injection
- Human-in-the-loop approval flows
- Checkpointing for conversation persistence
- Tool calling with validation
- **PARALLEL EXECUTION** for troubleshooting (v5.3.14+)

Architecture:
    User Message -> Router Node -> [Handler Nodes] -> Response
                            ↓
                    Tool Node -> Validate Node
                            ↓ (if error)
                    Retry Node (back to Tool)

Parallel Troubleshooting Architecture (v5.3.14+):
    Router → ┌─ TWS Status  ─┐
             ├─ RAG Search   ─┼→ Aggregator → Response
             ├─ Log Cache    ─┤
             └─ Metrics      ─┘

Usage:
    from resync.core.langgraph import create_tws_agent_graph
    
    # Standard graph
    graph = await create_tws_agent_graph()
    result = await graph.invoke({"message": "status do TWS"})
    
    # Parallel troubleshooting (direct use)
    from resync.core.langgraph import parallel_troubleshoot
    result = await parallel_troubleshoot("Job BATCH001 falhou")
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
from resync.core.langgraph.nodes import (
    HumanApprovalNode,
    LLMNode,
    RouterNode,
    ToolNode,
    ValidationNode,
)
from resync.core.langgraph.parallel_graph import (
    ParallelConfig,
    ParallelState,
    create_parallel_troubleshoot_graph,
    parallel_troubleshoot,
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
    # Checkpointing
    "PostgresCheckpointer",
    "get_checkpointer",
    # Parallel Execution (v5.3.14+)
    "ParallelConfig",
    "ParallelState",
    "create_parallel_troubleshoot_graph",
    "parallel_troubleshoot",
]
