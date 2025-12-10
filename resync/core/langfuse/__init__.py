"""
LangFuse Integration for Resync.

This module provides prompt management and observability through LangFuse.
Key features:
- Centralized prompt versioning
- A/B testing of prompts
- Performance tracking and analytics
- Admin UI integration

Usage:
    from resync.core.langfuse import prompt_manager

    # Get a prompt with variables
    prompt = await prompt_manager.get_prompt("tws-agent-v1")
    compiled = prompt.compile(context="system status", user_query="what's the status?")
"""

from resync.core.langfuse.observability import (
    LangFuseTracer,
    get_tracer,
    trace_llm_call,
)
from resync.core.langfuse.prompt_manager import (
    PromptConfig,
    PromptManager,
    PromptTemplate,
    get_prompt_manager,
)

__all__ = [
    "PromptManager",
    "get_prompt_manager",
    "PromptConfig",
    "PromptTemplate",
    "LangFuseTracer",
    "get_tracer",
    "trace_llm_call",
]
