"""
Apache AGE Graph Models.

Defines the node and edge types used in the TWS knowledge graph.
These models are used for validation and type hints, but the
actual storage is in PostgreSQL via Apache AGE.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Types of nodes in the graph."""
    JOB = "job"
    WORKSTATION = "workstation"
    EVENT = "event"
    RESOURCE = "resource"
    SCHEDULE = "schedule"
    USER = "user"


class RelationType(str, Enum):
    """Types of relationships in the graph."""
    DEPENDS_ON = "DEPENDS_ON"
    RUNS_ON = "RUNS_ON"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    NEXT = "NEXT"
    RELATES_TO = "RELATES_TO"
    TRIGGERED_BY = "TRIGGERED_BY"
    SCHEDULED_BY = "SCHEDULED_BY"


class GraphNode(BaseModel):
    """
    Base model for graph nodes.
    
    All nodes have a unique ID, type, name, and optional properties.
    """
    
    id: str = Field(..., description="Unique node identifier (e.g., 'job:BATCH_PROC')")
    node_type: NodeType = Field(..., description="Type of node")
    name: str = Field(..., description="Human-readable name")
    
    # Common properties
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    is_active: bool = True
    
    # Flexible properties
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class JobNode(GraphNode):
    """Job node model."""
    
    node_type: NodeType = NodeType.JOB
    
    # Job-specific properties
    workstation: Optional[str] = None
    job_stream: Optional[str] = None
    schedule: Optional[str] = None
    status: Optional[str] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    duration_avg_ms: Optional[int] = None
    
    def to_cypher_props(self) -> str:
        """Convert to Cypher property string."""
        props = {
            "name": self.name,
            "node_type": self.node_type,
            "workstation": self.workstation,
            "job_stream": self.job_stream,
            "schedule": self.schedule,
            "status": self.status,
            "is_active": self.is_active,
        }
        
        # Remove None values
        props = {k: v for k, v in props.items() if v is not None}
        
        # Format as JSON-like string
        import json
        return json.dumps(props)


class WorkstationNode(GraphNode):
    """Workstation node model."""
    
    node_type: NodeType = NodeType.WORKSTATION
    
    # Workstation-specific properties
    host: Optional[str] = None
    port: Optional[int] = None
    status: str = "UNKNOWN"
    agent_type: Optional[str] = None
    os_type: Optional[str] = None
    last_heartbeat: Optional[datetime] = None


class EventNode(GraphNode):
    """Event node model."""
    
    node_type: NodeType = NodeType.EVENT
    
    # Event-specific properties
    event_type: str = Field(..., description="Type of event (error, warning, info, etc.)")
    message: str = ""
    severity: str = "INFO"
    source_job: Optional[str] = None
    source_workstation: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Error details
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None


class ResourceNode(GraphNode):
    """Resource node model (files, datasets, etc.)."""
    
    node_type: NodeType = NodeType.RESOURCE
    
    # Resource-specific properties
    resource_type: str = Field(..., description="Type of resource (file, dataset, queue, etc.)")
    path: Optional[str] = None
    size_bytes: Optional[int] = None


class GraphEdge(BaseModel):
    """
    Model for graph edges (relationships).
    
    Edges connect two nodes with a typed relationship.
    """
    
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relation_type: RelationType = Field(..., description="Type of relationship")
    
    # Edge properties
    created_at: datetime = Field(default_factory=datetime.utcnow)
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # For weighted relationships
    weight: float = 1.0
    
    class Config:
        use_enum_values = True
    
    def to_cypher(self) -> str:
        """Generate Cypher for creating this edge."""
        props = {
            "created_at": self.created_at.isoformat(),
            "weight": self.weight,
            **self.properties,
        }
        
        import json
        props_str = json.dumps(props)
        
        return f"-[:{self.relation_type} {props_str}]->"


class DependencyChain(BaseModel):
    """Model for a dependency chain result."""
    
    root_job: str
    dependencies: List[Dict[str, Any]]
    total_depth: int
    
    def get_critical_path(self) -> List[str]:
        """Get the longest dependency path."""
        return [d.get("name") for d in self.dependencies]


class ImpactAnalysis(BaseModel):
    """Model for impact analysis result."""
    
    job: str
    affected_count: int
    affected_jobs: List[str]
    severity: str  # critical, high, medium, low, none
    
    def is_critical(self) -> bool:
        """Check if impact is critical."""
        return self.severity == "critical"


class GraphStatistics(BaseModel):
    """Model for graph statistics."""
    
    node_count: int
    edge_count: int
    node_types: Dict[str, int]
    edge_types: Dict[str, int]
    
    # Computed metrics
    avg_degree: Optional[float] = None
    max_degree: Optional[int] = None
    connected_components: Optional[int] = None
    is_dag: Optional[bool] = None
    
    # Backend info
    backend: str = "apache_age"
    graph_name: str = "tws_graph"
