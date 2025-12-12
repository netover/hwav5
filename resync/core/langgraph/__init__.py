"""
LangGraph Integration for Resync.

This module provides agent orchestration through state graphs:
- Conditional routing based on intent
- Automatic retry loops with error injection
- Human-in-the-loop approval flows
- Checkpointing for conversation persistence
- Tool calling with validation

Architecture:
    User Message -> Router Node -> [Handler Nodes] -> Response
                            ↓
                    Tool Node -> Validate Node
                            ↓ (if error)
                    Retry Node (back to Tool)

Usage:
    from resync.core.langgraph import create_tws_agent_graph

    graph = await create_tws_agent_graph()
    result = await graph.invoke({"message": "status do TWS"})
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

__all__ = [
    "AgentGraphConfig",
    "AgentState",
    "create_tws_agent_graph",
    "create_router_graph",
    "RouterNode",
    "LLMNode",
    "ToolNode",
    "ValidationNode",
    "HumanApprovalNode",
    "PostgresCheckpointer",
    "get_checkpointer",
]
