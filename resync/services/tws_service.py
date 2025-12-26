"""
Read‑only client for interacting with the IBM TWS/HWA REST API.

This client implements a subset of the API surface focused on read‑only
operations such as listing objects, retrieving the current plan and its
relationships, and fetching configuration details. Each request is measured
and counted using Prometheus metrics for observability. HTTPX is instrumented
with OpenTelemetry if the instrumentation library is available.

v5.9.3: Added TTL-differentiated caching:
- Job status: 10s (near real-time)
- Logs: 30s (semi-live)
- Static structure: 1h (rarely changes)
- Graph dependencies: 5min

Cache injects _fetched_at for UI transparency.
"""

import time
from datetime import datetime, timezone
from typing import Any

import httpx

try:
    # Optional import for automatic OpenTelemetry instrumentation of httpx
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument()
except Exception as _e:
    # Instrumentation is optional; if it fails, continue without it
    pass

from resync.core.metrics_compat import Counter, Histogram
from resync.services.tws_cache import (
    CacheCategory,
    enrich_response_with_cache_meta,
    get_tws_cache,
)


class OptimizedTWSClient:
    """
    A lightweight asynchronous client for the TWS/HWA REST API.

    It wraps an httpx.AsyncClient and exposes convenient methods for common
    read‑only operations. All requests funnel through a single `_get` method
    which records request latency and counts by endpoint and status code.
    """

    # Prometheus metrics shared across all client instances
    _request_latency: Histogram = Histogram(
        "tws_request_latency_seconds",
        "Latency of TWS API requests",
        ["endpoint"],
    )
    _request_count: Counter = Counter(
        "tws_request_total",
        "Total number of TWS API requests",
        ["endpoint", "status"],
    )

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        engine_name: str,
        engine_owner: str,
        trust_env: bool = False,
    ) -> None:
        """
        Construct the TWS client.

        Args:
            base_url: Base URL of the TWS API (e.g., "http://localhost:8080")
            username: Basic auth username
            password: Basic auth password
            engine_name: Default engine name for queries that require it
            engine_owner: Engine owner associated with the engine
            trust_env: If True, use system proxy settings from environment variables.
                       Set to True in corporate environments that require proxy access.
                       Default is False to avoid requiring optional dependencies like socksio.
        """
        self.base_url = base_url.rstrip("/")
        self.auth = (username, password)
        self.engine_name = engine_name
        self.engine_owner = engine_owner
        # httpx client with a base URL and basic authentication. Connection pooling
        # is automatically handled by httpx.AsyncClient.
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=self.auth,
            trust_env=trust_env,
        )
        # v5.9.3: TTL-differentiated cache
        self._cache = get_tws_cache()

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self.client.aclose()

    # -------------------------------------------------------------------------
    # Cache Management (v5.9.3)
    # -------------------------------------------------------------------------
    def configure_cache(
        self,
        job_status_ttl: int | None = None,
        job_logs_ttl: int | None = None,
        static_ttl: int | None = None,
        graph_ttl: int | None = None,
    ):
        """Configure cache TTLs."""
        self._cache.configure_ttls(
            job_status=job_status_ttl,
            job_logs=job_logs_ttl,
            static_structure=static_ttl,
            graph=graph_ttl,
        )

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Internal helper for GET requests with metrics.

        Args:
            path: The path portion of the URL (should begin with '/')
            params: Optional query parameters

        Returns:
            The parsed JSON response on success.

        Raises:
            httpx.HTTPStatusError: For non‑2xx responses.
            httpx.RequestError: For network errors.
        """
        endpoint_label = path.lstrip("/").replace("/", "_") or "root"
        start = time.perf_counter()
        try:
            response = await self.client.get(path, params=params)
            elapsed = time.perf_counter() - start
            # Record metrics
            self._request_latency.labels(endpoint=endpoint_label).observe(elapsed)
            self._request_count.labels(
                endpoint=endpoint_label, status=str(response.status_code)
            ).inc()
            response.raise_for_status()
            # Parse JSON (httpx will raise if the body isn't valid JSON)
            return response.json()
        except Exception as _e:
            elapsed = time.perf_counter() - start
            # Record error in metrics
            self._request_latency.labels(endpoint=endpoint_label).observe(elapsed)
            self._request_count.labels(endpoint=endpoint_label, status="error").inc()
            raise

    # ---------------------------------------------------------------------
    # Engine & Configuration
    # ---------------------------------------------------------------------
    async def get_engine_info(self) -> Any:
        """Retrieve high level information about the engine."""
        return await self._get("/twsd/api/v2/engine/info")

    async def get_engine_configuration(self, key: str | None = None) -> Any:
        """Retrieve engine configuration values."""
        params = {"key": key} if key else None
        return await self._get("/twsd/api/v2/engine/configuration", params=params)

    async def list_users(self) -> Any:
        """List users defined in the model."""
        return await self._get("/twsd/api/v2/model/user")

    async def list_groups(self) -> Any:
        """List groups defined in the model."""
        return await self._get("/twsd/api/v2/model/group")

    # ---------------------------------------------------------------------
    # Model queries
    # ---------------------------------------------------------------------
    async def query_jobdefinitions(
        self,
        q: str | None = None,
        folder: str | None = None,
        limit: int | None = 50,
    ) -> Any:
        """Search job definitions in the model with optional filters."""
        params: dict[str, Any] = {}
        if q:
            params["query"] = q
        if folder:
            params["folder"] = folder
        if limit is not None:
            params["limit"] = limit
        return await self._get("/twsd/api/v2/model/jobdefinition", params=params)

    async def get_jobdefinition(self, jobdef_id: str) -> Any:
        """Retrieve a specific job definition by its ID."""
        return await self._get(f"/twsd/api/v2/model/jobdefinition/{jobdef_id}")

    async def query_jobstreams(
        self,
        q: str | None = None,
        folder: str | None = None,
        limit: int | None = 50,
    ) -> Any:
        """Search job streams in the model with optional filters."""
        params: dict[str, Any] = {}
        if q:
            params["query"] = q
        if folder:
            params["folder"] = folder
        if limit is not None:
            params["limit"] = limit
        return await self._get("/twsd/api/v2/model/jobstream", params=params)

    async def get_jobstream(self, jobstream_id: str) -> Any:
        """Retrieve a specific job stream by its ID."""
        return await self._get(f"/twsd/api/v2/model/jobstream/{jobstream_id}")

    async def query_workstations(
        self,
        q: str | None = None,
        limit: int | None = 50,
    ) -> Any:
        """Search workstations in the model with optional filters."""
        params: dict[str, Any] = {}
        if q:
            params["query"] = q
        if limit is not None:
            params["limit"] = limit
        return await self._get("/twsd/api/v2/model/workstation", params=params)

    async def get_workstation(self, workstation_id: str) -> Any:
        """Retrieve a workstation definition by its ID."""
        return await self._get(f"/twsd/api/v2/model/workstation/{workstation_id}")

    # ---------------------------------------------------------------------
    # Current plan queries – Jobs
    # ---------------------------------------------------------------------
    async def query_current_plan_jobs(
        self,
        q: str | None = None,
        folder: str | None = None,
        status: str | None = None,
        limit: int | None = 50,
    ) -> Any:
        """
        List or search jobs currently present in the plan.
        Filters include a free form search string, folder path and status.
        """
        params: dict[str, Any] = {}
        if q:
            params["query"] = q
        if folder:
            params["folder"] = folder
        if status:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        return await self._get("/twsd/api/v2/plan/job", params=params)

    async def get_current_plan_job(self, job_id: str) -> Any:
        """Retrieve a specific job from the current plan."""
        return await self._get(f"/twsd/api/v2/plan/job/{job_id}")

    async def get_current_plan_job_predecessors(
        self,
        job_id: str,
        depth: int | None = None,
    ) -> Any:
        """Retrieve the predecessors of a job in the current plan."""
        params: dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        return await self._get(f"/twsd/api/v2/plan/job/{job_id}/predecessors", params=params)

    async def get_current_plan_job_successors(
        self,
        job_id: str,
        depth: int | None = None,
    ) -> Any:
        """Retrieve the successors of a job in the current plan."""
        params: dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        return await self._get(f"/twsd/api/v2/plan/job/{job_id}/successors", params=params)

    async def get_current_plan_job_model(self, job_id: str) -> Any:
        """Retrieve the underlying model of a job in the current plan."""
        return await self._get(f"/twsd/api/v2/plan/job/{job_id}/model")

    async def get_current_plan_job_model_description(self, job_id: str) -> Any:
        """Retrieve the model description of a job in the current plan."""
        return await self._get(f"/twsd/api/v2/plan/job/{job_id}/model/description")

    async def get_current_plan_job_count(self) -> Any:
        """Return the total number of jobs in the current plan."""
        return await self._get("/twsd/api/v2/plan/job/count")

    async def get_current_plan_job_issues(self) -> Any:
        """Return issues detected in the current plan jobs."""
        return await self._get("/twsd/api/v2/plan/job/issues")

    async def get_current_plan_job_joblog(self) -> Any:
        """Retrieve the combined job logs for the current plan."""
        return await self._get("/twsd/api/v2/plan/job/joblog")

    # ---------------------------------------------------------------------
    # Current plan queries – Job Streams
    # ---------------------------------------------------------------------
    async def query_current_plan_jobstreams(
        self,
        q: str | None = None,
        folder: str | None = None,
        limit: int | None = 50,
    ) -> Any:
        """List or search job streams in the current plan."""
        params: dict[str, Any] = {}
        if q:
            params["query"] = q
        if folder:
            params["folder"] = folder
        if limit is not None:
            params["limit"] = limit
        return await self._get("/twsd/api/v2/plan/jobstream", params=params)

    async def get_current_plan_jobstream(self, jobstream_id: str) -> Any:
        """Retrieve a specific job stream from the current plan."""
        return await self._get(f"/twsd/api/v2/plan/jobstream/{jobstream_id}")

    async def get_current_plan_jobstream_predecessors(
        self,
        jobstream_id: str,
        depth: int | None = None,
    ) -> Any:
        """Retrieve the predecessors of a job stream in the current plan."""
        params: dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        return await self._get(
            f"/twsd/api/v2/plan/jobstream/{jobstream_id}/predecessors",
            params=params,
        )

    async def get_current_plan_jobstream_successors(
        self,
        jobstream_id: str,
        depth: int | None = None,
    ) -> Any:
        """Retrieve the successors of a job stream in the current plan."""
        params: dict[str, Any] = {}
        if depth is not None:
            params["depth"] = depth
        return await self._get(
            f"/twsd/api/v2/plan/jobstream/{jobstream_id}/successors",
            params=params,
        )

    async def get_current_plan_jobstream_model_description(self, jobstream_id: str) -> Any:
        """Retrieve the model description of a job stream in the current plan."""
        return await self._get(f"/twsd/api/v2/plan/jobstream/{jobstream_id}/model/description")

    async def get_current_plan_jobstream_count(self) -> Any:
        """Return the total number of job streams in the current plan."""
        return await self._get("/twsd/api/v2/plan/jobstream/count")

    # ---------------------------------------------------------------------
    # Current plan queries – Resources and Folders
    # ---------------------------------------------------------------------
    async def query_current_plan_resources(
        self, q: str | None = None, limit: int | None = 50
    ) -> Any:
        """List or search resources in the current plan."""
        params: dict[str, Any] = {}
        if q:
            params["query"] = q
        if limit is not None:
            params["limit"] = limit
        return await self._get("/twsd/api/v2/plan/resource", params=params)

    async def get_current_plan_resource(self, resource_id: str) -> Any:
        """Retrieve a specific resource from the current plan."""
        return await self._get(f"/twsd/api/v2/plan/resource/{resource_id}")

    async def get_current_plan_folder_objects_count(self, folder: str | None = None) -> Any:
        """Return the number of plan objects within a folder."""
        params: dict[str, Any] = {}
        if folder:
            params["folder"] = folder
        return await self._get("/twsd/api/v2/plan/folder/objects-count", params=params)

    # ---------------------------------------------------------------------
    # Current plan queries – Consumed Jobs
    # ---------------------------------------------------------------------
    async def get_consumed_jobs_runs(
        self,
        job_name: str | None = None,
        limit: int | None = 50,
    ) -> Any:
        """
        Retrieve runs of consumed jobs in the current plan.

        Args:
            job_name: Optional name filter for the job whose runs are returned.
            limit: Maximum number of runs to return.
        """
        params: dict[str, Any] = {}
        if job_name:
            params["jobName"] = job_name
        if limit is not None:
            params["limit"] = limit
        return await self._get("/twsd/api/v2/plan/consumed-jobs/runs", params=params)

    # =========================================================================
    # CACHED METHODS (v5.9.3 - Near Real-Time Strategy)
    # =========================================================================
    # These methods use TTL-differentiated caching for optimal balance between
    # API protection and data freshness. All responses include _fetched_at
    # timestamp for UI transparency.

    async def get_job_status_cached(
        self,
        job_id: str,
        with_meta: bool = False,
    ) -> Any:
        """
        Get job status with 10-second cache (near real-time).

        Args:
            job_id: Job identifier
            with_meta: If True, returns {data, meta} with cache info

        Returns:
            Job status dict with _fetched_at timestamp
            If with_meta=True: {data: {...}, meta: {cached, age_seconds, freshness}}
        """
        cache_key = f"job_status:{job_id}"

        async def fetch():
            data = await self.get_current_plan_job(job_id)
            data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
            return data

        value, is_cached, age = await self._cache.get_or_fetch(
            cache_key, fetch, CacheCategory.JOB_STATUS
        )

        if with_meta:
            return enrich_response_with_cache_meta(value, is_cached, age)
        return value

    async def get_job_logs_cached(
        self,
        job_id: str,
        with_meta: bool = False,
    ) -> Any:
        """
        Get job logs with 30-second cache.

        Returns:
            Job logs with _fetched_at timestamp
        """
        cache_key = f"job_logs:{job_id}"

        async def fetch():
            data = await self.get_current_plan_job_joblog()
            if isinstance(data, dict):
                data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
            return data

        value, is_cached, age = await self._cache.get_or_fetch(
            cache_key, fetch, CacheCategory.JOB_LOGS
        )

        if with_meta:
            return enrich_response_with_cache_meta(value, is_cached, age)
        return value

    async def get_job_dependencies_cached(
        self,
        job_id: str,
        depth: int = 1,
        with_meta: bool = False,
    ) -> dict[str, Any]:
        """
        Get job dependencies with 5-minute cache.

        Returns:
            Dict with predecessors and successors
        """
        cache_key = f"job_deps:{job_id}:d{depth}"

        async def fetch():
            preds = await self.get_current_plan_job_predecessors(job_id, depth)
            succs = await self.get_current_plan_job_successors(job_id, depth)
            return {
                "job_id": job_id,
                "predecessors": preds or [],
                "successors": succs or [],
                "_fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        value, is_cached, age = await self._cache.get_or_fetch(
            cache_key, fetch, CacheCategory.GRAPH
        )

        if with_meta:
            return enrich_response_with_cache_meta(value, is_cached, age)
        return value

    async def get_jobdefinition_cached(
        self,
        jobdef_id: str,
        with_meta: bool = False,
    ) -> Any:
        """
        Get job definition with 1-hour cache (static structure).

        Returns:
            Job definition with _fetched_at timestamp
        """
        cache_key = f"jobdef:{jobdef_id}"

        async def fetch():
            data = await self.get_jobdefinition(jobdef_id)
            if isinstance(data, dict):
                data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
            return data

        value, is_cached, age = await self._cache.get_or_fetch(
            cache_key, fetch, CacheCategory.STATIC_STRUCTURE
        )

        if with_meta:
            return enrich_response_with_cache_meta(value, is_cached, age)
        return value

    async def get_workstation_cached(
        self,
        workstation_id: str,
        with_meta: bool = False,
    ) -> Any:
        """
        Get workstation with 1-hour cache (static structure).

        Returns:
            Workstation data with _fetched_at timestamp
        """
        cache_key = f"ws:{workstation_id}"

        async def fetch():
            data = await self.get_workstation(workstation_id)
            if isinstance(data, dict):
                data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
            return data

        value, is_cached, age = await self._cache.get_or_fetch(
            cache_key, fetch, CacheCategory.STATIC_STRUCTURE
        )

        if with_meta:
            return enrich_response_with_cache_meta(value, is_cached, age)
        return value

    async def query_jobs_cached(
        self,
        q: str | None = None,
        status: str | None = None,
        limit: int = 50,
        with_meta: bool = False,
    ) -> Any:
        """
        Query jobs with 10-second cache.

        Returns:
            List of jobs with _fetched_at timestamp
        """
        cache_key = f"jobs_query:q={q}:s={status}:l={limit}"

        async def fetch():
            data = await self.query_current_plan_jobs(q, None, status, limit)
            return {
                "jobs": data if isinstance(data, list) else data.get("items", []),
                "query": q,
                "status_filter": status,
                "_fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        value, is_cached, age = await self._cache.get_or_fetch(
            cache_key, fetch, CacheCategory.JOB_STATUS
        )

        if with_meta:
            return enrich_response_with_cache_meta(value, is_cached, age)
        return value


# =============================================================================
# HELPER FUNCTION
# =============================================================================


async def get_tws_client() -> OptimizedTWSClient:
    """
    Get or create TWS client instance.

    Returns:
        OptimizedTWSClient instance
    """
    from resync.settings import settings

    hostname = settings.TWS_HOST or "localhost"
    port = settings.TWS_PORT or 31111
    base_url = f"http://{hostname}:{port}"

    return OptimizedTWSClient(
        base_url=base_url,
        username=settings.TWS_USER or "tws_user",
        password=settings.TWS_PASSWORD or "tws_password",
        engine_name=settings.TWS_ENGINE_NAME,
        engine_owner=settings.TWS_ENGINE_OWNER,
    )
