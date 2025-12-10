"""
Observability Module for Resync.

Provides centralized configuration and setup for monitoring tools:
- LangFuse: LLM tracing, prompt management, cost tracking
- Evidently: ML monitoring, data drift detection

Usage:
    from resync.core.observability import (
        setup_observability,
        get_observability_status,
        get_langfuse_client,
        get_evidently_monitor,
    )

    # On startup
    await setup_observability()

    # Check status
    status = get_observability_status()
"""

from resync.core.observability.config import (
    EvidentlyConfig,
    EvidentlyMonitor,
    LangFuseConfig,
    # Configuration
    ObservabilityConfig,
    get_evidently_monitor,
    get_langfuse_client,
    get_observability_config,
    get_observability_status,
    # Evidently
    setup_evidently,
    # LangFuse
    setup_langfuse,
    # Combined
    setup_observability,
    shutdown_langfuse,
    shutdown_observability,
)

__all__ = [
    # Configuration
    "ObservabilityConfig",
    "LangFuseConfig",
    "EvidentlyConfig",
    "get_observability_config",

    # LangFuse
    "setup_langfuse",
    "shutdown_langfuse",
    "get_langfuse_client",

    # Evidently
    "setup_evidently",
    "get_evidently_monitor",
    "EvidentlyMonitor",

    # Combined
    "setup_observability",
    "shutdown_observability",
    "get_observability_status",
]
