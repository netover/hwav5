"""
Knowledge Graph Database Models.

SQLAlchemy models for persisting graph nodes and edges in PostgreSQL.
Graph queries are executed via Apache AGE extension using Cypher.

Architecture:
- PostgreSQL: Persistence layer (nodes, edges, metadata)
- Apache AGE: Graph queries via Cypher
- pgvector: Semantic search (via RAG)
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from resync.core.database.engine import Base

# =============================================================================
# ENUMS
# =============================================================================

class NodeType(str, Enum):
    """Types of nodes in the TWS knowledge graph."""
    JOB = "job"
    JOB_STREAM = "job_stream"
    WORKSTATION = "workstation"
    RESOURCE = "resource"
    SCHEDULE = "schedule"
    POLICY = "policy"
    APPLICATION = "application"
    ENVIRONMENT = "environment"
    EVENT = "event"
    ALERT = "alert"


class RelationType(str, Enum):
    """Types of relationships (edges) in the TWS knowledge graph."""
    # Job relationships
    DEPENDS_ON = "depends_on"           # Job → Job
    TRIGGERS = "triggers"               # Job → Job (downstream)
    RUNS_ON = "runs_on"                 # Job → Workstation
    BELONGS_TO = "belongs_to"           # Job → JobStream
    USES = "uses"                       # Job → Resource
    FOLLOWS = "follows"                 # Job → Schedule
    GOVERNED_BY = "governed_by"         # Job → Policy

    # Hierarchy relationships
    PART_OF = "part_of"                 # JobStream → Application
    HOSTED_ON = "hosted_on"             # Application → Environment
    CONTAINS = "contains"               # Parent → Child (generic)

    # Event relationships
    OCCURRED_ON = "occurred_on"         # Event → Workstation
    AFFECTED = "affected"               # Event → Job
    NEXT = "next"                       # Event → Event (temporal chain)
    CAUSED_BY = "caused_by"             # Event → Event (causal)

    # Resource relationships
    SHARED_BY = "shared_by"             # Resource → Job (multiple)
    EXCLUSIVE_TO = "exclusive_to"       # Resource → Job (single)


# =============================================================================
# MODELS
# =============================================================================

class GraphNode(Base):
    """
    Represents a node in the knowledge graph.

    Stores entities like Jobs, Workstations, Resources, etc.
    """

    __tablename__ = "kg_nodes"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        comment="Unique identifier (e.g., 'job:BATCH_PROCESS', 'ws:WS001')"
    )

    # Node type
    node_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of node (job, workstation, resource, etc.)"
    )

    # Display name
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Human-readable name"
    )

    # Properties as JSON
    properties_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional properties as JSON"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Source tracking
    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Where this node came from (tws_api, manual, llm_extracted)"
    )

    # Soft delete
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True
    )

    # Indexes
    __table_args__ = (
        Index('ix_kg_nodes_type_name', 'node_type', 'name'),
        Index('ix_kg_nodes_active_type', 'is_active', 'node_type'),
    )

    @property
    def properties(self) -> dict[str, Any]:
        """Get properties as dict."""
        if self.properties_json:
            return json.loads(self.properties_json)
        return {}

    @properties.setter
    def properties(self, value: dict[str, Any]):
        """Set properties from dict."""
        self.properties_json = json.dumps(value) if value else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for NetworkX."""
        return {
            "id": self.id,
            "type": self.node_type,
            "name": self.name,
            "properties": self.properties,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source": self.source,
        }

    def __repr__(self) -> str:
        return f"<GraphNode(id={self.id}, type={self.node_type}, name={self.name})>"


class GraphEdge(Base):
    """
    Represents an edge (relationship) in the knowledge graph.

    Stores relationships like Job→DEPENDS_ON→Job, Job→RUNS_ON→Workstation.
    """

    __tablename__ = "kg_edges"

    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # Source node
    source_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Source node ID"
    )

    # Target node
    target_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Target node ID"
    )

    # Relationship type
    relation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of relationship"
    )

    # Edge weight (for algorithms like PageRank)
    weight: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        comment="Edge weight for graph algorithms"
    )

    # Properties as JSON
    properties_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional properties as JSON"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Validity period (for temporal edges)
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="When this relationship became valid"
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="When this relationship expired (null = still valid)"
    )

    # Source tracking
    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Where this edge came from"
    )

    # Confidence score (for LLM-extracted edges)
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        comment="Confidence score (1.0 = certain, 0.0 = uncertain)"
    )

    # Soft delete
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True
    )

    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('source_id', 'target_id', 'relation_type', name='uq_edge_triplet'),
        Index('ix_kg_edges_source_relation', 'source_id', 'relation_type'),
        Index('ix_kg_edges_target_relation', 'target_id', 'relation_type'),
        Index('ix_kg_edges_active_relation', 'is_active', 'relation_type'),
    )

    @property
    def properties(self) -> dict[str, Any]:
        """Get properties as dict."""
        if self.properties_json:
            return json.loads(self.properties_json)
        return {}

    @properties.setter
    def properties(self, value: dict[str, Any]):
        """Set properties from dict."""
        self.properties_json = json.dumps(value) if value else None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for NetworkX."""
        return {
            "source": self.source_id,
            "target": self.target_id,
            "relation": self.relation_type,
            "weight": self.weight,
            "properties": self.properties,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<GraphEdge({self.source_id})-[{self.relation_type}]->({self.target_id})>"


class ExtractedTriplet(Base):
    """
    Stores triplets extracted by LLM for review before adding to main graph.

    Allows human-in-the-loop validation of LLM extractions.
    """

    __tablename__ = "kg_extracted_triplets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # Triplet data
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    object: Mapped[str] = mapped_column(String(255), nullable=False)

    # Source text
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_document: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Extraction metadata
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    # Review status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",  # pending, approved, rejected
        index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "status": self.status,
            "source_text": self.source_text[:200] + "..." if len(self.source_text) > 200 else self.source_text,
        }


class GraphSnapshot(Base):
    """
    Stores periodic snapshots of graph statistics for monitoring.
    """

    __tablename__ = "kg_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Statistics
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, default=0)

    # Node type counts as JSON
    node_types_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Edge type counts as JSON
    edge_types_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Graph metrics
    avg_degree: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_degree: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connected_components: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    @property
    def node_types(self) -> dict[str, int]:
        if self.node_types_json:
            return json.loads(self.node_types_json)
        return {}

    @property
    def edge_types(self) -> dict[str, int]:
        if self.edge_types_json:
            return json.loads(self.edge_types_json)
        return {}
