"""
TWS Specialist Agents Module.

This module provides 4 specialized AI agents for TWS analysis:
- Job Analyst: Return codes, ABENDs, job execution analysis
- Dependency Specialist: Predecessors, successors, critical path
- Resource Specialist: CPU, memory, workstation conflicts
- Knowledge Specialist: Documentation RAG, troubleshooting guides

Architecture:
    Query → Orchestrator → [Specialists in parallel] → Synthesizer → Response

Author: Resync Team
Version: 5.2.3.29
"""

from resync.core.specialists.agents import (
    JobAnalystAgent,
    DependencySpecialist,
    ResourceSpecialist,
    KnowledgeSpecialist,
    TWSSpecialistTeam,
    create_specialist_team,
    get_specialist_team,
)
from resync.core.specialists.tools import (
    JobLogTool,
    ErrorCodeTool,
    DependencyGraphTool,
    WorkstationTool,
    CalendarTool,
)
from resync.core.specialists.models import (
    SpecialistConfig,
    SpecialistType,
    TeamExecutionMode,
    SpecialistResponse,
    TeamResponse,
)

__all__ = [
    # Agents
    "JobAnalystAgent",
    "DependencySpecialist",
    "ResourceSpecialist",
    "KnowledgeSpecialist",
    "TWSSpecialistTeam",
    "create_specialist_team",
    "get_specialist_team",
    # Tools
    "JobLogTool",
    "ErrorCodeTool",
    "DependencyGraphTool",
    "WorkstationTool",
    "CalendarTool",
    # Models
    "SpecialistConfig",
    "SpecialistType",
    "TeamExecutionMode",
    "SpecialistResponse",
    "TeamResponse",
]
