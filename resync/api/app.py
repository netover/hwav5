"""
FastAPI application for the TWS read‑only microservice.

This module instantiates a FastAPI app, registers the `/tws` router, exposes
basic health and metrics endpoints, and sets up OpenTelemetry instrumentation
for the framework if available.
"""

import json
import logging

from fastapi import FastAPI
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Internal metrics system
from resync.core.metrics_internal import registry  # noqa: E402

try:
    # Optional instrumentation for FastAPI and ASGI frameworks
    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
except Exception as e:
    logger.error("exception_caught", error=str(e), exc_info=True)
    FastAPIInstrumentor = None  # type: ignore
    OpenTelemetryMiddleware = None  # type: ignore

from resync.api.endpoints import router as tws_router  # noqa: E402


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        An instance of FastAPI ready to be served.
    """
    app = FastAPI(
        title="TWS Read‑Only API",
        description="Microservice exposing read‑only routes for the IBM TWS/HWA API.",
        version="1.0.0",
    )

    # Register API routers
    app.include_router(tws_router)

    # Basic health check
    @app.get("/healthz", summary="Health check")
    async def healthz():
        return {"status": "ok"}

    # Internal metrics endpoint (JSON format)
    @app.get("/metrics", summary="Application metrics")
    async def metrics():
        metrics_data = registry.export_json()
        return Response(
            json.dumps(metrics_data, indent=2),
            media_type="application/json",
        )

    # OpenTelemetry ASGI middleware and FastAPI instrumentation
    if OpenTelemetryMiddleware is not None:
        app.add_middleware(OpenTelemetryMiddleware)
    if FastAPIInstrumentor is not None:
        try:  # noqa: SIM105
            FastAPIInstrumentor().instrument_app(app)
        except Exception as _e:
            # Instrumentation is optional; ignore failures
            pass

    return app


# App instance used by ASGI servers (e.g. uvicorn)
app = create_app()
