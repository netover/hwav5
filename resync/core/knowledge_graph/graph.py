"""
TWS Knowledge Graph - NetworkX-based graph with PostgreSQL persistence.

This module provides a hybrid knowledge graph that:
1. Uses NetworkX for fast in-memory graph operations (BFS, centrality, etc.)
2. Persists data to PostgreSQL for durability
3. Integrates with Qdrant for semantic search (via HybridRAG)

Key Features:
- Multi-hop traversal for dependency chains
- Betweenness centrality to find bottlenecks
- Common neighbor detection for resource conflicts
- Temporal chains for root cause analysis
- ReadWriteLock for high-concurrency reads

Usage:
    kg = TWSKnowledgeGraph()
    await kg.initialize()
    
    # Add nodes and edges
    await kg.add_job("BATCH_PROC", workstation="WS001", dependencies=["INIT_JOB"])
    
    # Query
    chain = await kg.get_dependency_chain("BATCH_PROC")
    critical = await kg.get_critical_jobs()
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from resync.core.structured_logger import get_logger
from resync.core.database.engine import get_db_session as get_async_session
from resync.core.knowledge_graph.models import (
    GraphNode, GraphEdge, GraphSnapshot,
    NodeType, RelationType
)

logger = get_logger(__name__)


# =============================================================================
# READ-WRITE LOCK FOR HIGH CONCURRENCY
# =============================================================================

class ReadWriteLock:
    """
    Async Read-Write Lock for high-concurrency graph access.
    
    Allows multiple simultaneous readers OR one exclusive writer.
    Writers have priority to prevent starvation.
    
    Benefits:
    - Multiple read operations can execute in parallel
    - Write operations are exclusive (safe mutations)
    - ~80% throughput improvement for read-heavy workloads
    
    Usage:
        rw_lock = ReadWriteLock()
        
        # Reading (multiple allowed)
        async with rw_lock.read_lock():
            data = graph.get_data()
        
        # Writing (exclusive)
        async with rw_lock.write_lock():
            graph.add_node(...)
    """
    
    def __init__(self):
        self._read_count = 0
        self._write_waiting = 0
        self._state_lock = asyncio.Lock()      # Protects counters
        self._read_allowed = asyncio.Event()   # Readers can proceed
        self._write_lock = asyncio.Lock()      # Mutual exclusion for writers
        self._read_allowed.set()               # Initially allowed
    
    @asynccontextmanager
    async def read_lock(self):
        """
        Acquire read lock (multiple readers allowed).
        
        Blocks if a writer is waiting (writer priority).
        """
        # Wait if writer is waiting (priority for writers)
        async with self._state_lock:
            while self._write_waiting > 0:
                self._state_lock.release()
                await self._read_allowed.wait()
                await self._state_lock.acquire()
            
            self._read_count += 1
        
        try:
            yield
        finally:
            async with self._state_lock:
                self._read_count -= 1
                if self._read_count == 0:
                    self._read_allowed.set()
    
    @asynccontextmanager
    async def write_lock(self):
        """
        Acquire write lock (exclusive).
        
        Blocks all readers and other writers.
        """
        async with self._state_lock:
            self._write_waiting += 1
            self._read_allowed.clear()  # Block new readers
        
        # Wait for exclusive write access
        await self._write_lock.acquire()
        
        try:
            # Wait for existing readers to finish
            while True:
                async with self._state_lock:
                    if self._read_count == 0:
                        break
                await asyncio.sleep(0.001)  # Yield to other tasks
            
            yield
        finally:
            async with self._state_lock:
                self._write_waiting -= 1
                if self._write_waiting == 0:
                    self._read_allowed.set()  # Allow readers again
            
            self._write_lock.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get lock statistics (for monitoring)."""
        return {
            "active_readers": self._read_count,
            "waiting_writers": self._write_waiting,
            "reads_allowed": self._read_allowed.is_set(),
        }


# =============================================================================
# KNOWLEDGE GRAPH
# =============================================================================

class TWSKnowledgeGraph:
    """
    TWS Knowledge Graph with NetworkX for algorithms and PostgreSQL for persistence.
    
    Architecture:
    - self._graph: NetworkX DiGraph for fast traversal
    - PostgreSQL: Durable storage via SQLAlchemy models
    - ReadWriteLock: High-concurrency access (multiple readers, exclusive writer)
    - Sync on startup and after modifications
    """
    
    _instance: Optional["TWSKnowledgeGraph"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "TWSKnowledgeGraph":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._graph = nx.DiGraph()
        return cls._instance
    
    def __init__(self):
        """Initialize the graph (singleton, so only runs once)."""
        if not hasattr(self, '_graph'):
            self._graph = nx.DiGraph()
        # Use ReadWriteLock instead of simple Lock
        if not hasattr(self, '_rw_lock'):
            self._rw_lock = ReadWriteLock()
        # Keep simple lock for initialization only
        if not hasattr(self, '_init_lock'):
            self._init_lock = asyncio.Lock()
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    async def initialize(self) -> None:
        """Load graph from PostgreSQL into NetworkX."""
        if self._initialized:
            return
        
        async with self._init_lock:
            if self._initialized:
                return
            
            try:
                await self._load_from_database()
                self._initialized = True
                logger.info(
                    "knowledge_graph_initialized",
                    nodes=self._graph.number_of_nodes(),
                    edges=self._graph.number_of_edges()
                )
            except Exception as e:
                logger.error("knowledge_graph_init_failed", error=str(e))
                # Continue with empty graph
                self._initialized = True
    
    async def _load_from_database(self) -> None:
        """Load all nodes and edges from PostgreSQL."""
        async with get_async_session() as session:
            # Load nodes
            result = await session.execute(
                select(GraphNode).where(GraphNode.is_active == True)
            )
            nodes = result.scalars().all()
            
            for node in nodes:
                self._graph.add_node(
                    node.id,
                    type=node.node_type,
                    name=node.name,
                    properties=node.properties,
                    source=node.source
                )
            
            # Load edges
            result = await session.execute(
                select(GraphEdge).where(GraphEdge.is_active == True)
            )
            edges = result.scalars().all()
            
            for edge in edges:
                self._graph.add_edge(
                    edge.source_id,
                    edge.target_id,
                    relation=edge.relation_type,
                    weight=edge.weight,
                    properties=edge.properties,
                    confidence=edge.confidence
                )
    
    async def reload(self) -> None:
        """Force reload from database (WRITE operation - exclusive)."""
        async with self._rw_lock.write_lock():
            self._graph.clear()
            self._initialized = False
            await self._load_from_database()
            self._initialized = True
            logger.info(
                "knowledge_graph_reloaded",
                nodes=self._graph.number_of_nodes(),
                edges=self._graph.number_of_edges()
            )
    
    # =========================================================================
    # NODE OPERATIONS (WRITE - exclusive)
    # =========================================================================
    
    async def add_node(
        self,
        node_id: str,
        node_type: NodeType | str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
        source: str = "api"
    ) -> str:
        """
        Add a node to the graph (WRITE operation - exclusive).
        
        Args:
            node_id: Unique identifier (e.g., "job:BATCH_PROC")
            node_type: Type of node (job, workstation, etc.)
            name: Human-readable name
            properties: Additional properties
            source: Where this node came from
            
        Returns:
            Node ID
        """
        await self.initialize()
        
        if isinstance(node_type, NodeType):
            node_type = node_type.value
        
        async with self._rw_lock.write_lock():
            # Add to NetworkX
            self._graph.add_node(
                node_id,
                type=node_type,
                name=name,
                properties=properties or {},
                source=source
            )
            
            # Persist to PostgreSQL
            async with get_async_session() as session:
                node = GraphNode(
                    id=node_id,
                    node_type=node_type,
                    name=name,
                    source=source
                )
                node.properties = properties or {}
                
                await session.merge(node)  # Upsert
                await session.commit()
        
        logger.debug("node_added", node_id=node_id, type=node_type)
        return node_id
    
    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType | str,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        source: str = "api"
    ) -> None:
        """
        Add an edge (relationship) to the graph (WRITE operation - exclusive).
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            relation_type: Type of relationship
            weight: Edge weight for algorithms
            properties: Additional properties
            confidence: Confidence score (for LLM extractions)
            source: Where this edge came from
        """
        await self.initialize()
        
        if isinstance(relation_type, RelationType):
            relation_type = relation_type.value
        
        async with self._rw_lock.write_lock():
            # Add to NetworkX
            self._graph.add_edge(
                source_id,
                target_id,
                relation=relation_type,
                weight=weight,
                properties=properties or {},
                confidence=confidence
            )
            
            # Persist to PostgreSQL
            async with get_async_session() as session:
                # Check if edge exists
                result = await session.execute(
                    select(GraphEdge).where(
                        GraphEdge.source_id == source_id,
                        GraphEdge.target_id == target_id,
                        GraphEdge.relation_type == relation_type
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    existing.weight = weight
                    existing.confidence = confidence
                    existing.updated_at = datetime.utcnow()
                    if properties:
                        existing.properties = properties
                else:
                    edge = GraphEdge(
                        source_id=source_id,
                        target_id=target_id,
                        relation_type=relation_type,
                        weight=weight,
                        confidence=confidence,
                        source=source
                    )
                    edge.properties = properties or {}
                    session.add(edge)
                
                await session.commit()
        
        logger.debug(
            "edge_added",
            source=source_id,
            relation=relation_type,
            target=target_id
        )
    
    # =========================================================================
    # CONVENIENCE METHODS FOR TWS ENTITIES
    # =========================================================================
    
    async def add_job(
        self,
        job_name: str,
        workstation: Optional[str] = None,
        job_stream: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        resources: Optional[List[str]] = None,
        schedule: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        source: str = "tws_api"
    ) -> str:
        """
        Add a job with all its relationships.
        
        Args:
            job_name: Job name
            workstation: Workstation where job runs
            job_stream: Job stream it belongs to
            dependencies: Jobs this job depends on
            resources: Resources this job uses
            schedule: Schedule this job follows
            properties: Additional properties
            source: Data source
            
        Returns:
            Job node ID
        """
        job_id = f"job:{job_name}"
        
        # Add job node
        await self.add_node(
            job_id,
            NodeType.JOB,
            job_name,
            properties=properties,
            source=source
        )
        
        # Add workstation relationship
        if workstation:
            ws_id = f"ws:{workstation}"
            await self.add_node(ws_id, NodeType.WORKSTATION, workstation, source=source)
            await self.add_edge(job_id, ws_id, RelationType.RUNS_ON, source=source)
        
        # Add job stream relationship
        if job_stream:
            stream_id = f"stream:{job_stream}"
            await self.add_node(stream_id, NodeType.JOB_STREAM, job_stream, source=source)
            await self.add_edge(job_id, stream_id, RelationType.BELONGS_TO, source=source)
        
        # Add dependencies
        if dependencies:
            for dep in dependencies:
                dep_id = f"job:{dep}"
                # Ensure dependency node exists
                if dep_id not in self._graph:
                    await self.add_node(dep_id, NodeType.JOB, dep, source=source)
                await self.add_edge(job_id, dep_id, RelationType.DEPENDS_ON, source=source)
        
        # Add resources
        if resources:
            for res in resources:
                res_id = f"resource:{res}"
                await self.add_node(res_id, NodeType.RESOURCE, res, source=source)
                await self.add_edge(job_id, res_id, RelationType.USES, source=source)
        
        # Add schedule
        if schedule:
            sched_id = f"schedule:{schedule}"
            await self.add_node(sched_id, NodeType.SCHEDULE, schedule, source=source)
            await self.add_edge(job_id, sched_id, RelationType.FOLLOWS, source=source)
        
        return job_id
    
    async def add_event(
        self,
        event_id: str,
        event_type: str,
        message: str,
        timestamp: datetime,
        affected_job: Optional[str] = None,
        workstation: Optional[str] = None,
        previous_event: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add an event with its relationships."""
        node_id = f"event:{event_id}"
        
        props = {
            "event_type": event_type,
            "message": message,
            "timestamp": timestamp.isoformat(),
            **(properties or {})
        }
        
        await self.add_node(node_id, NodeType.EVENT, event_type, properties=props)
        
        if affected_job:
            job_id = f"job:{affected_job}"
            if job_id not in self._graph:
                await self.add_node(job_id, NodeType.JOB, affected_job)
            await self.add_edge(node_id, job_id, RelationType.AFFECTED)
        
        if workstation:
            ws_id = f"ws:{workstation}"
            if ws_id not in self._graph:
                await self.add_node(ws_id, NodeType.WORKSTATION, workstation)
            await self.add_edge(node_id, ws_id, RelationType.OCCURRED_ON)
        
        if previous_event:
            prev_id = f"event:{previous_event}"
            if prev_id in self._graph:
                await self.add_edge(prev_id, node_id, RelationType.NEXT)
        
        return node_id
    
    # =========================================================================
    # QUERY OPERATIONS - MULTI-HOP TRAVERSAL (READ - parallel allowed)
    # =========================================================================
    
    async def get_dependency_chain(
        self,
        job_name: str,
        max_hops: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get the full dependency chain for a job (READ operation - parallel).
        
        Solves: Multi-Hop Disconnection failure
        
        Args:
            job_name: Job to trace dependencies for
            max_hops: Maximum depth to traverse
            
        Returns:
            List of dependency paths with relationships
        """
        await self.initialize()
        
        job_id = f"job:{job_name}" if not job_name.startswith("job:") else job_name
        
        async with self._rw_lock.read_lock():
            if job_id not in self._graph:
                return []
            
            chain = []
            visited = set()
            
            def _traverse(node: str, depth: int, path: List[str]):
                if depth > max_hops or node in visited:
                    return
                
                visited.add(node)
                
                # Get all outgoing edges with DEPENDS_ON relation
                for _, target, data in self._graph.out_edges(node, data=True):
                    if data.get("relation") == RelationType.DEPENDS_ON.value:
                        edge_info = {
                            "from": node,
                            "to": target,
                            "relation": "depends_on",
                            "depth": depth,
                            "path": path + [target]
                        }
                        chain.append(edge_info)
                        _traverse(target, depth + 1, path + [target])
            
            _traverse(job_id, 0, [job_id])
        
        logger.debug(
            "dependency_chain_traced",
            job=job_name,
            chain_length=len(chain)
        )
        
        return chain
    
    async def get_full_lineage(
        self,
        job_name: str
    ) -> Dict[str, Any]:
        """
        Get the complete ancestry of a job (READ operation - parallel).
        
        Uses BFS to find all ancestors.
        
        Returns:
            Dict with ancestors and the path
        """
        await self.initialize()
        
        job_id = f"job:{job_name}" if not job_name.startswith("job:") else job_name
        
        async with self._rw_lock.read_lock():
            if job_id not in self._graph:
                return {"job": job_name, "ancestors": [], "ancestor_count": 0}
            
            # Find all nodes that this job depends on (following out-edges)
            ancestors = []
            
            # BFS forward - follow edges from this job to its dependencies
            for edge in nx.bfs_edges(self._graph, job_id):
                source, target = edge
                rel = self._graph[source][target].get("relation", "related")
                # Only include dependencies (not other edge types like USES)
                if rel in ("depends_on", RelationType.DEPENDS_ON.value):
                    ancestors.append({
                        "node": target,
                        "relation": rel,
                        "name": self._graph.nodes[target].get("name", target)
                    })
        
        return {
            "job": job_name,
            "ancestors": ancestors,
            "ancestor_count": len(ancestors)
        }
    
    async def get_downstream_jobs(
        self,
        job_name: str,
        max_hops: int = 5
    ) -> List[str]:
        """
        Get all jobs that depend on this job (READ operation - parallel).
        
        Args:
            job_name: Source job
            max_hops: Maximum depth
            
        Returns:
            List of downstream job names
        """
        await self.initialize()
        
        job_id = f"job:{job_name}" if not job_name.startswith("job:") else job_name
        
        async with self._rw_lock.read_lock():
            if job_id not in self._graph:
                return []
            
            # Find all nodes that have a path FROM them TO this job
            # These are jobs that depend on our job
            downstream = []
            
            for node in self._graph.nodes():
                if node == job_id:
                    continue
                if self._graph.nodes[node].get("type") != "job":
                    continue
                
                # Check if this node has a DEPENDS_ON edge to our job
                for _, target, data in self._graph.out_edges(node, data=True):
                    if target == job_id and data.get("relation") == RelationType.DEPENDS_ON.value:
                        downstream.append(node.replace("job:", ""))
                        break
        
        return downstream
    
    # =========================================================================
    # QUERY OPERATIONS - COMMON NEIGHBOR (Resource Conflicts) - READ
    # =========================================================================
    
    async def find_resource_conflicts(
        self,
        job_a: str,
        job_b: str
    ) -> List[Dict[str, Any]]:
        """
        Find shared resources between two jobs (READ operation - parallel).
        
        Solves: Common Neighbor Gap failure
        
        Args:
            job_a: First job name
            job_b: Second job name
            
        Returns:
            List of shared resources with conflict analysis
        """
        await self.initialize()
        
        job_a_id = f"job:{job_a}" if not job_a.startswith("job:") else job_a
        job_b_id = f"job:{job_b}" if not job_b.startswith("job:") else job_b
        
        async with self._rw_lock.read_lock():
            if job_a_id not in self._graph or job_b_id not in self._graph:
                return []
            
            # Get resources used by each job
            resources_a = set()
            resources_b = set()
            
            for _, target, data in self._graph.out_edges(job_a_id, data=True):
                if data.get("relation") == RelationType.USES.value:
                    resources_a.add(target)
            
            for _, target, data in self._graph.out_edges(job_b_id, data=True):
                if data.get("relation") == RelationType.USES.value:
                    resources_b.add(target)
            
            # Find intersection
            shared = resources_a.intersection(resources_b)
            
            conflicts = []
            for res_id in shared:
                res_props = self._graph.nodes[res_id].get("properties", {})
                conflicts.append({
                    "resource": res_id,
                    "name": self._graph.nodes[res_id].get("name", res_id),
                    "is_exclusive": res_props.get("exclusive", False),
                    "conflict_type": "exclusive" if res_props.get("exclusive") else "concurrent"
                })
        
        logger.debug(
            "resource_conflicts_checked",
            job_a=job_a,
            job_b=job_b,
            conflicts=len(conflicts)
        )
        
        return conflicts
    
    async def get_jobs_using_resource(self, resource_name: str) -> List[str]:
        """Get all jobs that use a specific resource (READ operation - parallel)."""
        await self.initialize()
        
        res_id = f"resource:{resource_name}" if not resource_name.startswith("resource:") else resource_name
        
        async with self._rw_lock.read_lock():
            if res_id not in self._graph:
                return []
            
            jobs = []
            for node in self._graph.predecessors(res_id):
                if self._graph.nodes[node].get("type") == "job":
                    jobs.append(node.replace("job:", ""))
        
        return jobs
    
    # =========================================================================
    # QUERY OPERATIONS - NETWORK CENTRALITY - READ
    # =========================================================================
    
    async def get_critical_jobs(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Find the most critical jobs using betweenness centrality (READ - parallel).
        
        Solves: Failing to Identify Key Influences failure
        
        Jobs with high centrality are bottlenecks - if they fail,
        many other jobs are affected.
        
        Args:
            top_n: Number of top critical jobs to return
            
        Returns:
            List of jobs with their centrality scores
        """
        await self.initialize()
        
        async with self._rw_lock.read_lock():
            # Filter to job nodes only
            job_subgraph = self._graph.subgraph([
                n for n in self._graph.nodes()
                if self._graph.nodes[n].get("type") == "job"
            ])
            
            if job_subgraph.number_of_nodes() == 0:
                return []
            
            # Calculate betweenness centrality
            centrality = nx.betweenness_centrality(job_subgraph, weight="weight")
            
            # Sort and get top N
            sorted_jobs = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]
            
            result = []
            for job_id, score in sorted_jobs:
                dependents = len(list(self._graph.predecessors(job_id)))
                dependencies = len([
                    t for _, t, d in self._graph.out_edges(job_id, data=True)
                    if d.get("relation") == RelationType.DEPENDS_ON.value
                ])
                
                result.append({
                    "job": job_id.replace("job:", ""),
                    "centrality_score": round(score, 4),
                    "dependents_count": dependents,
                    "dependencies_count": dependencies,
                    "risk_level": "high" if score > 0.5 else "medium" if score > 0.1 else "low"
                })
        
        logger.info("critical_jobs_analyzed", top_job=result[0] if result else None)
        
        return result
    
    async def get_impact_analysis(self, job_name: str) -> Dict[str, Any]:
        """
        Analyze the impact if a job fails (READ operation - parallel).
        
        Returns count and list of affected downstream jobs.
        """
        await self.initialize()
        
        job_id = f"job:{job_name}" if not job_name.startswith("job:") else job_name
        
        async with self._rw_lock.read_lock():
            if job_id not in self._graph:
                return {"job": job_name, "affected_count": 0, "affected_jobs": []}
            
            # Find all jobs that depend on this job (directly or indirectly)
            affected = set()
            
            def _find_dependents(node: str, visited: Set[str]):
                for pred in self._graph.predecessors(node):
                    if pred in visited:
                        continue
                    if self._graph.nodes[pred].get("type") == "job":
                        # Check if it's a DEPENDS_ON relationship
                        edge_data = self._graph[pred][node]
                        if edge_data.get("relation") == RelationType.DEPENDS_ON.value:
                            affected.add(pred)
                            visited.add(pred)
                            _find_dependents(pred, visited)
            
            _find_dependents(job_id, {job_id})
        
        return {
            "job": job_name,
            "affected_count": len(affected),
            "affected_jobs": [j.replace("job:", "") for j in affected],
            "severity": "critical" if len(affected) > 10 else "high" if len(affected) > 5 else "medium" if len(affected) > 0 else "low"
        }
    
    # =========================================================================
    # QUERY OPERATIONS - TEMPORAL CHAINS
    # =========================================================================
    
    async def get_event_chain(
        self,
        event_id: str,
        direction: str = "backward",
        max_events: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get the temporal chain of events.
        
        Solves: Relevance Ranking failure (events in chronological order)
        
        Args:
            event_id: Starting event
            direction: "backward" (predecessors) or "forward" (successors)
            max_events: Maximum events to return
            
        Returns:
            Ordered list of events
        """
        await self.initialize()
        
        node_id = f"event:{event_id}" if not event_id.startswith("event:") else event_id
        
        if node_id not in self._graph:
            return []
        
        chain = []
        current = node_id
        visited = set()
        
        while len(chain) < max_events and current not in visited:
            visited.add(current)
            
            node_data = self._graph.nodes.get(current, {})
            props = node_data.get("properties", {})
            
            chain.append({
                "event_id": current.replace("event:", ""),
                "type": props.get("event_type", "unknown"),
                "message": props.get("message", ""),
                "timestamp": props.get("timestamp"),
            })
            
            # Find next/previous event
            if direction == "backward":
                predecessors = [
                    (s, d) for s, _, d in self._graph.in_edges(current, data=True)
                    if d.get("relation") == RelationType.NEXT.value
                ]
                if predecessors:
                    current = predecessors[0][0]
                else:
                    break
            else:
                successors = [
                    (t, d) for _, t, d in self._graph.out_edges(current, data=True)
                    if d.get("relation") == RelationType.NEXT.value
                ]
                if successors:
                    current = successors[0][0]
                else:
                    break
        
        # Sort by timestamp if available
        chain.sort(key=lambda x: x.get("timestamp", ""), reverse=(direction == "backward"))
        
        return chain
    
    # =========================================================================
    # STATISTICS AND MONITORING - READ
    # =========================================================================
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics (READ operation - parallel)."""
        await self.initialize()
        
        async with self._rw_lock.read_lock():
            node_types = defaultdict(int)
            for _, data in self._graph.nodes(data=True):
                node_types[data.get("type", "unknown")] += 1
            
            edge_types = defaultdict(int)
            for _, _, data in self._graph.edges(data=True):
                edge_types[data.get("relation", "unknown")] += 1
            
            # Calculate degree statistics
            degrees = [d for _, d in self._graph.degree()]
            avg_degree = sum(degrees) / len(degrees) if degrees else 0
            max_degree = max(degrees) if degrees else 0
            
            # Connected components (for undirected view)
            undirected = self._graph.to_undirected()
            components = nx.number_connected_components(undirected)
            
            stats = {
                "node_count": self._graph.number_of_nodes(),
                "edge_count": self._graph.number_of_edges(),
                "node_types": dict(node_types),
                "edge_types": dict(edge_types),
                "avg_degree": round(avg_degree, 2),
                "max_degree": max_degree,
                "connected_components": components,
                "is_dag": nx.is_directed_acyclic_graph(self._graph),
            }
        
        return stats
    
    def get_lock_stats(self) -> Dict[str, Any]:
        """Get ReadWriteLock statistics for monitoring."""
        return self._rw_lock.get_stats()
    
    async def save_snapshot(self) -> None:
        """Save current graph statistics to database."""
        stats = await self.get_statistics()
        
        async with get_async_session() as session:
            import json
            snapshot = GraphSnapshot(
                node_count=stats["node_count"],
                edge_count=stats["edge_count"],
                node_types_json=json.dumps(stats["node_types"]),
                edge_types_json=json.dumps(stats["edge_types"]),
                avg_degree=stats["avg_degree"],
                max_degree=stats["max_degree"],
                connected_components=stats["connected_components"]
            )
            session.add(snapshot)
            await session.commit()
        
        logger.info("graph_snapshot_saved", **stats)
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node data."""
        if node_id in self._graph:
            return dict(self._graph.nodes[node_id])
        return None
    
    def has_node(self, node_id: str) -> bool:
        """Check if node exists."""
        return node_id in self._graph
    
    def has_edge(self, source_id: str, target_id: str) -> bool:
        """Check if edge exists."""
        return self._graph.has_edge(source_id, target_id)
    
    @property
    def node_count(self) -> int:
        """Get number of nodes."""
        return self._graph.number_of_nodes()
    
    @property
    def edge_count(self) -> int:
        """Get number of edges."""
        return self._graph.number_of_edges()


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_knowledge_graph: Optional[TWSKnowledgeGraph] = None


def get_knowledge_graph() -> TWSKnowledgeGraph:
    """Get or create the singleton knowledge graph."""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = TWSKnowledgeGraph()
    return _knowledge_graph


async def initialize_knowledge_graph() -> TWSKnowledgeGraph:
    """Initialize and return the knowledge graph."""
    kg = get_knowledge_graph()
    await kg.initialize()
    return kg
