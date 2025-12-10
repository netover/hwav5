"""
Cypher Query Builders for Apache AGE.

Provides fluent query builders for common graph operations.
These builders help construct safe, parameterized Cypher queries.

Usage:
    query = JobQueries.find_by_status("ABEND").with_workstation().limit(10)
    results = await graph.execute(query.build())
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# =============================================================================
# BASE QUERY BUILDER
# =============================================================================

@dataclass
class CypherQuery:
    """Represents a built Cypher query."""

    query: str
    params: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.query


class CypherQueryBuilder(ABC):
    """
    Abstract base class for Cypher query builders.

    Provides a fluent interface for constructing Cypher queries.
    """

    def __init__(self):
        self._match_clauses: list[str] = []
        self._where_clauses: list[str] = []
        self._return_fields: list[str] = []
        self._order_by: str | None = None
        self._limit: int | None = None
        self._skip: int | None = None
        self._params: dict[str, Any] = {}

    def where(self, condition: str, **params) -> CypherQueryBuilder:
        """Add a WHERE condition."""
        self._where_clauses.append(condition)
        self._params.update(params)
        return self

    def order_by(self, field: str, desc: bool = False) -> CypherQueryBuilder:
        """Add ORDER BY clause."""
        direction = "DESC" if desc else "ASC"
        self._order_by = f"{field} {direction}"
        return self

    def limit(self, n: int) -> CypherQueryBuilder:
        """Limit results."""
        self._limit = n
        return self

    def skip(self, n: int) -> CypherQueryBuilder:
        """Skip results (for pagination)."""
        self._skip = n
        return self

    def returns(self, *fields: str) -> CypherQueryBuilder:
        """Specify return fields."""
        self._return_fields.extend(fields)
        return self

    def build(self) -> CypherQuery:
        """Build the final query."""
        parts = []

        # MATCH clauses
        if self._match_clauses:
            parts.append(" ".join(self._match_clauses))

        # WHERE clause
        if self._where_clauses:
            parts.append("WHERE " + " AND ".join(self._where_clauses))

        # RETURN clause
        if self._return_fields:
            parts.append("RETURN " + ", ".join(self._return_fields))
        else:
            parts.append("RETURN *")

        # ORDER BY
        if self._order_by:
            parts.append(f"ORDER BY {self._order_by}")

        # SKIP and LIMIT
        if self._skip:
            parts.append(f"SKIP {self._skip}")
        if self._limit:
            parts.append(f"LIMIT {self._limit}")

        return CypherQuery(
            query="\n".join(parts),
            params=self._params,
        )


# =============================================================================
# JOB QUERIES
# =============================================================================

class JobQueries:
    """Query builders for Job nodes."""

    @staticmethod
    def find_all() -> JobQueryBuilder:
        """Find all jobs."""
        return JobQueryBuilder().match_all()

    @staticmethod
    def find_by_name(name: str) -> JobQueryBuilder:
        """Find job by name."""
        return JobQueryBuilder().match_by_name(name)

    @staticmethod
    def find_by_status(status: str) -> JobQueryBuilder:
        """Find jobs by status."""
        return JobQueryBuilder().match_all().filter_by_status(status)

    @staticmethod
    def find_by_workstation(workstation: str) -> JobQueryBuilder:
        """Find jobs on a workstation."""
        return JobQueryBuilder().match_on_workstation(workstation)

    @staticmethod
    def find_dependencies(job_name: str, max_depth: int = 10) -> JobQueryBuilder:
        """Find job dependencies."""
        return JobQueryBuilder().match_dependencies(job_name, max_depth)

    @staticmethod
    def find_dependents(job_name: str, max_depth: int = 10) -> JobQueryBuilder:
        """Find jobs that depend on this job."""
        return JobQueryBuilder().match_dependents(job_name, max_depth)

    @staticmethod
    def find_critical(limit: int = 10) -> JobQueryBuilder:
        """Find critical jobs by impact score."""
        return JobQueryBuilder().match_with_impact_score().limit(limit)


class JobQueryBuilder(CypherQueryBuilder):
    """Builder for Job queries."""

    def match_all(self) -> JobQueryBuilder:
        """Match all jobs."""
        self._match_clauses.append("MATCH (j:Job)")
        self._return_fields = ["j.name as name", "j.status as status", "j.workstation as workstation"]
        return self

    def match_by_name(self, name: str) -> JobQueryBuilder:
        """Match job by name."""
        self._match_clauses.append(f"MATCH (j:Job {{name: '{name}'}})")
        self._return_fields = ["j"]
        return self

    def match_on_workstation(self, workstation: str) -> JobQueryBuilder:
        """Match jobs on a workstation."""
        self._match_clauses.append(
            f"MATCH (j:Job)-[:RUNS_ON]->(w:Workstation {{name: '{workstation}'}})"
        )
        self._return_fields = ["j.name as name", "j.status as status"]
        return self

    def match_dependencies(self, job_name: str, max_depth: int = 10) -> JobQueryBuilder:
        """Match dependencies of a job."""
        self._match_clauses.append(
            f"MATCH (j:Job {{name: '{job_name}'}})-[:DEPENDS_ON*1..{max_depth}]->(dep:Job)"
        )
        self._return_fields = [
            "DISTINCT dep.name as name",
            "dep.workstation as workstation",
            "dep.status as status",
        ]
        return self

    def match_dependents(self, job_name: str, max_depth: int = 10) -> JobQueryBuilder:
        """Match jobs that depend on this job."""
        self._match_clauses.append(
            f"MATCH (j:Job {{name: '{job_name}'}})<-[:DEPENDS_ON*1..{max_depth}]-(dep:Job)"
        )
        self._return_fields = [
            "DISTINCT dep.name as name",
            "dep.workstation as workstation",
            "dep.status as status",
        ]
        return self

    def match_with_impact_score(self) -> JobQueryBuilder:
        """Match jobs with calculated impact score."""
        self._match_clauses.append("""
            MATCH (j:Job)
            OPTIONAL MATCH (dependent:Job)-[:DEPENDS_ON*1..5]->(j)
            WITH j, count(DISTINCT dependent) as impact_score
        """)
        self._return_fields = [
            "j.name as name",
            "j.workstation as workstation",
            "j.status as status",
            "impact_score",
        ]
        self._order_by = "impact_score DESC"
        return self

    def filter_by_status(self, status: str) -> JobQueryBuilder:
        """Filter by job status."""
        self._where_clauses.append(f"j.status = '{status}'")
        return self

    def filter_active_only(self) -> JobQueryBuilder:
        """Filter to active jobs only."""
        self._where_clauses.append("j.is_active = true")
        return self

    def with_workstation(self) -> JobQueryBuilder:
        """Include workstation relationship."""
        if "workstation" not in str(self._return_fields):
            self._return_fields.append("j.workstation as workstation")
        return self

    def with_schedule(self) -> JobQueryBuilder:
        """Include schedule information."""
        self._return_fields.append("j.schedule as schedule")
        return self


# =============================================================================
# WORKSTATION QUERIES
# =============================================================================

class WorkstationQueries:
    """Query builders for Workstation nodes."""

    @staticmethod
    def find_all() -> WorkstationQueryBuilder:
        """Find all workstations."""
        return WorkstationQueryBuilder().match_all()

    @staticmethod
    def find_by_name(name: str) -> WorkstationQueryBuilder:
        """Find workstation by name."""
        return WorkstationQueryBuilder().match_by_name(name)

    @staticmethod
    def find_by_status(status: str) -> WorkstationQueryBuilder:
        """Find workstations by status."""
        return WorkstationQueryBuilder().match_all().filter_by_status(status)

    @staticmethod
    def find_with_job_count() -> WorkstationQueryBuilder:
        """Find workstations with job counts."""
        return WorkstationQueryBuilder().match_with_job_count()


class WorkstationQueryBuilder(CypherQueryBuilder):
    """Builder for Workstation queries."""

    def match_all(self) -> WorkstationQueryBuilder:
        """Match all workstations."""
        self._match_clauses.append("MATCH (w:Workstation)")
        self._return_fields = ["w.name as name", "w.status as status", "w.host as host"]
        return self

    def match_by_name(self, name: str) -> WorkstationQueryBuilder:
        """Match workstation by name."""
        self._match_clauses.append(f"MATCH (w:Workstation {{name: '{name}'}})")
        self._return_fields = ["w"]
        return self

    def match_with_job_count(self) -> WorkstationQueryBuilder:
        """Match workstations with job counts."""
        self._match_clauses.append("""
            MATCH (w:Workstation)
            OPTIONAL MATCH (j:Job)-[:RUNS_ON]->(w)
            WITH w, count(j) as job_count
        """)
        self._return_fields = [
            "w.name as name",
            "w.status as status",
            "job_count",
        ]
        self._order_by = "job_count DESC"
        return self

    def filter_by_status(self, status: str) -> WorkstationQueryBuilder:
        """Filter by workstation status."""
        self._where_clauses.append(f"w.status = '{status}'")
        return self

    def filter_online_only(self) -> WorkstationQueryBuilder:
        """Filter to online workstations only."""
        return self.filter_by_status("ONLINE")


# =============================================================================
# EVENT QUERIES
# =============================================================================

class EventQueries:
    """Query builders for Event nodes."""

    @staticmethod
    def find_recent(limit: int = 100) -> EventQueryBuilder:
        """Find recent events."""
        return EventQueryBuilder().match_all().order_by("e.timestamp", desc=True).limit(limit)

    @staticmethod
    def find_by_job(job_name: str) -> EventQueryBuilder:
        """Find events for a job."""
        return EventQueryBuilder().match_by_job(job_name)

    @staticmethod
    def find_by_severity(severity: str) -> EventQueryBuilder:
        """Find events by severity."""
        return EventQueryBuilder().match_all().filter_by_severity(severity)

    @staticmethod
    def find_errors(hours: int = 24) -> EventQueryBuilder:
        """Find error events in the last N hours."""
        return EventQueryBuilder().match_all().filter_errors().filter_recent(hours)

    @staticmethod
    def find_chain(event_id: str, direction: str = "backward", max_events: int = 20) -> EventQueryBuilder:
        """Find event chain."""
        return EventQueryBuilder().match_chain(event_id, direction, max_events)


class EventQueryBuilder(CypherQueryBuilder):
    """Builder for Event queries."""

    def match_all(self) -> EventQueryBuilder:
        """Match all events."""
        self._match_clauses.append("MATCH (e:Event)")
        self._return_fields = [
            "e.event_id as event_id",
            "e.event_type as type",
            "e.message as message",
            "e.severity as severity",
            "e.timestamp as timestamp",
        ]
        return self

    def match_by_job(self, job_name: str) -> EventQueryBuilder:
        """Match events for a job."""
        self._match_clauses.append(
            f"MATCH (e:Event)-[:RELATES_TO]->(j:Job {{name: '{job_name}'}})"
        )
        self._return_fields = [
            "e.event_id as event_id",
            "e.event_type as type",
            "e.message as message",
            "e.timestamp as timestamp",
        ]
        self._order_by = "e.timestamp DESC"
        return self

    def match_chain(
        self,
        event_id: str,
        direction: str = "backward",
        max_events: int = 20
    ) -> EventQueryBuilder:
        """Match event chain."""
        if direction == "backward":
            self._match_clauses.append(
                f"MATCH path = (e:Event {{event_id: '{event_id}'}})<-[:NEXT*0..{max_events}]-(prev:Event)"
            )
            self._return_fields = [
                "prev.event_id as event_id",
                "prev.event_type as type",
                "prev.message as message",
                "prev.timestamp as timestamp",
            ]
            self._order_by = "prev.timestamp DESC"
        else:
            self._match_clauses.append(
                f"MATCH path = (e:Event {{event_id: '{event_id}'}})-[:NEXT*0..{max_events}]->(next:Event)"
            )
            self._return_fields = [
                "next.event_id as event_id",
                "next.event_type as type",
                "next.message as message",
                "next.timestamp as timestamp",
            ]
            self._order_by = "next.timestamp ASC"
        return self

    def filter_by_severity(self, severity: str) -> EventQueryBuilder:
        """Filter by severity."""
        self._where_clauses.append(f"e.severity = '{severity}'")
        return self

    def filter_errors(self) -> EventQueryBuilder:
        """Filter to error events."""
        self._where_clauses.append("e.severity IN ['ERROR', 'CRITICAL']")
        return self

    def filter_recent(self, hours: int = 24) -> EventQueryBuilder:
        """Filter to recent events."""
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        self._where_clauses.append(f"e.timestamp > '{cutoff}'")
        return self
