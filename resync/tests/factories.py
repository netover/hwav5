"""
Test Data Factories - Generate test data using Polyfactory.

v5.6.0: Factory-based test data generation.

Features:
- Automatic Pydantic model factories
- SQLAlchemy model factories
- Customizable data generation
- Consistent test data

Usage:
    from resync.tests.factories import UserFactory, IncidentFactory

    # Generate a single instance
    user = UserFactory.build()

    # Generate multiple instances
    users = UserFactory.batch(10)

    # Customize fields
    user = UserFactory.build(email="custom@example.com")
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

try:
    from polyfactory.factories.pydantic_factory import ModelFactory
except ImportError:
    # Fallback for when polyfactory is not installed
    class ModelFactory:
        @classmethod
        def build(cls, **kwargs):
            raise NotImplementedError("Install polyfactory: pip install polyfactory")

        @classmethod
        def batch(cls, size: int, **kwargs):
            raise NotImplementedError("Install polyfactory: pip install polyfactory")


# =============================================================================
# Base Factory Configuration
# =============================================================================


class BaseFactory(ModelFactory):
    """Base factory with common configuration."""

    __is_base_factory__ = True

    @classmethod
    def _get_faker(cls):
        """Get faker instance with consistent seed for reproducibility."""
        from faker import Faker

        fake = Faker()
        Faker.seed(12345)  # Consistent seed for reproducibility
        return fake


# =============================================================================
# User Factories
# =============================================================================


class UserDataFactory(BaseFactory):
    """Factory for user data dictionaries."""

    __model__ = dict

    @classmethod
    def build(cls, **kwargs) -> dict[str, Any]:
        """Build user data dictionary."""
        fake = cls._get_faker()

        defaults = {
            "id": str(uuid4()),
            "username": fake.user_name(),
            "email": fake.email(),
            "full_name": fake.name(),
            "roles": ["user"],
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def build_admin(cls, **kwargs) -> dict[str, Any]:
        """Build admin user data."""
        return cls.build(roles=["admin", "user"], **kwargs)

    @classmethod
    def batch(cls, size: int, **kwargs) -> list[dict[str, Any]]:
        """Build multiple user data dictionaries."""
        return [cls.build(**kwargs) for _ in range(size)]


# =============================================================================
# Incident Factories
# =============================================================================


class IncidentDataFactory(BaseFactory):
    """Factory for incident data."""

    __model__ = dict

    @classmethod
    def build(cls, **kwargs) -> dict[str, Any]:
        """Build incident data dictionary."""
        fake = cls._get_faker()

        severities = ["low", "medium", "high", "critical"]
        statuses = ["open", "investigating", "resolved", "closed"]
        categories = ["infrastructure", "application", "security", "performance"]

        defaults = {
            "id": str(uuid4()),
            "title": f"Incident: {fake.sentence(nb_words=4)}",
            "description": fake.paragraph(),
            "severity": fake.random_element(severities),
            "status": fake.random_element(statuses),
            "category": fake.random_element(categories),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "resolved_at": None,
            "assigned_to": None,
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def build_critical(cls, **kwargs) -> dict[str, Any]:
        """Build critical incident."""
        return cls.build(severity="critical", status="open", **kwargs)

    @classmethod
    def build_resolved(cls, **kwargs) -> dict[str, Any]:
        """Build resolved incident."""
        return cls.build(status="resolved", resolved_at=datetime.utcnow().isoformat(), **kwargs)

    @classmethod
    def batch(cls, size: int, **kwargs) -> list[dict[str, Any]]:
        """Build multiple incidents."""
        return [cls.build(**kwargs) for _ in range(size)]


# =============================================================================
# Audit Event Factories
# =============================================================================


class AuditEventFactory(BaseFactory):
    """Factory for audit event data."""

    __model__ = dict

    @classmethod
    def build(cls, **kwargs) -> dict[str, Any]:
        """Build audit event data."""
        fake = cls._get_faker()

        actions = [
            "user_login",
            "user_logout",
            "data_access",
            "data_modify",
            "config_change",
            "permission_change",
            "api_call",
        ]

        defaults = {
            "id": str(uuid4()),
            "action": fake.random_element(actions),
            "user_id": str(uuid4()),
            "resource": fake.word(),
            "details": {"ip": fake.ipv4(), "user_agent": fake.user_agent()},
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": str(uuid4()),
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def batch(cls, size: int, **kwargs) -> list[dict[str, Any]]:
        """Build multiple audit events."""
        return [cls.build(**kwargs) for _ in range(size)]


# =============================================================================
# TWS Job Factories
# =============================================================================


class TWSJobFactory(BaseFactory):
    """Factory for TWS job data."""

    __model__ = dict

    @classmethod
    def build(cls, **kwargs) -> dict[str, Any]:
        """Build TWS job data."""
        fake = cls._get_faker()

        statuses = ["SUCC", "ABEND", "EXEC", "HOLD", "PEND", "READY"]

        defaults = {
            "job_name": f"JOB_{fake.word().upper()}_{fake.random_int(1000, 9999)}",
            "job_stream": f"STREAM_{fake.word().upper()}",
            "workstation": f"WS_{fake.random_int(1, 10):02d}",
            "status": fake.random_element(statuses),
            "start_time": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            "end_time": datetime.utcnow().isoformat() if fake.boolean() else None,
            "return_code": fake.random_int(0, 255),
            "description": fake.sentence(),
            "dependencies": [],
        }
        defaults.update(kwargs)
        return defaults

    @classmethod
    def build_failed(cls, **kwargs) -> dict[str, Any]:
        """Build failed job."""
        return cls.build(status="ABEND", return_code=99, **kwargs)

    @classmethod
    def build_running(cls, **kwargs) -> dict[str, Any]:
        """Build running job."""
        return cls.build(status="EXEC", end_time=None, **kwargs)

    @classmethod
    def batch(cls, size: int, **kwargs) -> list[dict[str, Any]]:
        """Build multiple jobs."""
        return [cls.build(**kwargs) for _ in range(size)]


# =============================================================================
# API Response Factories
# =============================================================================


class APIResponseFactory(BaseFactory):
    """Factory for API response data."""

    __model__ = dict

    @classmethod
    def build_success(cls, data: Any = None, **kwargs) -> dict[str, Any]:
        """Build successful API response."""
        return {
            "status": "success",
            "data": data or {},
            "meta": {
                "timestamp": datetime.utcnow().isoformat(),
                "version": "5.6.0",
            },
            **kwargs,
        }

    @classmethod
    def build_error(
        cls,
        message: str = "An error occurred",
        code: str = "ERROR",
        status_code: int = 400,
        **kwargs,
    ) -> dict[str, Any]:
        """Build error API response."""
        return {
            "status": "error",
            "error": {
                "code": code,
                "message": message,
                "status_code": status_code,
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat(),
            },
            **kwargs,
        }

    @classmethod
    def build_paginated(
        cls,
        items: list[Any],
        page: int = 1,
        page_size: int = 20,
        total: int | None = None,
    ) -> dict[str, Any]:
        """Build paginated API response."""
        total = total or len(items)
        total_pages = (total + page_size - 1) // page_size

        return {
            "status": "success",
            "data": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat(),
            },
        }


# =============================================================================
# Health Check Factories
# =============================================================================


class HealthCheckFactory(BaseFactory):
    """Factory for health check data."""

    __model__ = dict

    @classmethod
    def build_healthy(cls, **kwargs) -> dict[str, Any]:
        """Build healthy status."""
        return {
            "status": "healthy",
            "checks": {
                "database": {"status": "healthy", "latency_ms": 5},
                "redis": {"status": "healthy", "latency_ms": 2},
                "tws": {"status": "healthy", "connections": 3},
            },
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs,
        }

    @classmethod
    def build_degraded(cls, **kwargs) -> dict[str, Any]:
        """Build degraded status."""
        return {
            "status": "degraded",
            "checks": {
                "database": {"status": "healthy", "latency_ms": 150},
                "redis": {"status": "degraded", "latency_ms": 500},
                "tws": {"status": "healthy", "connections": 1},
            },
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs,
        }

    @classmethod
    def build_unhealthy(cls, **kwargs) -> dict[str, Any]:
        """Build unhealthy status."""
        return {
            "status": "unhealthy",
            "checks": {
                "database": {"status": "unhealthy", "error": "Connection refused"},
                "redis": {"status": "healthy", "latency_ms": 2},
                "tws": {"status": "unhealthy", "error": "Timeout"},
            },
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs,
        }


# =============================================================================
# Convenience Aliases
# =============================================================================

# For easier imports
UserFactory = UserDataFactory
IncidentFactory = IncidentDataFactory
JobFactory = TWSJobFactory
