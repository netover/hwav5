"""
FastAPI Application Main Entry Point

Resync v5.2 - AI Interface for HCL Workload Automation
- Unified Agent Routing (automatic intent detection)
- Internal Monitoring Dashboard (replaces Prometheus/Grafana)
- WebSocket real-time updates
- Proactive TWS Monitoring (background polling)
- Real-time Event Broadcasting
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from resync.api.litellm_config import router as litellm_config_router

# Import monitoring dashboard router (replaces Prometheus/Grafana)
from resync.api.monitoring_dashboard import router as monitoring_router

# Import proactive monitoring router (real-time TWS monitoring)
from resync.api.monitoring_routes import monitoring_router as proactive_router

# Import system configuration and LiteLLM management routers
from resync.api.system_config import router as system_config_router

# Import AI Monitoring router (Specialist Agents + Evidently drift detection)
from resync.fastapi_app.api.v1.routes.admin_ai_monitoring import router as ai_monitoring_router

# Import Backup management router
from resync.fastapi_app.api.v1.routes.admin_backup import router as backup_router

# Import Observability management router (LangFuse + Evidently config)
from resync.fastapi_app.api.v1.routes.admin_observability import router as observability_router

# Import Teams integration router
from resync.fastapi_app.api.v1.routes.admin_teams import router as teams_router

# Import Threshold Tuning router for Active Learning threshold calibration
from resync.fastapi_app.api.v1.routes.admin_threshold_tuning import (
    router as threshold_tuning_router,
)

# Import TWS multi-instance management router
from resync.fastapi_app.api.v1.routes.admin_tws_instances import router as tws_instances_router

from .api.v1.routes.admin_config import router as admin_config_router
from .api.v1.routes.agents import router as agents_router
from .api.v1.routes.audit import router as audit_router
from .api.v1.routes.auth import router as auth_router
from .api.v1.routes.chat import router as chat_router
from .api.v1.routes.rag import router as rag_router
from .api.v1.routes.status import router as status_router
from .api.websocket.handlers import websocket_handler

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for startup/shutdown events.

    Startup:
    - Initialize proactive monitoring system
    - Start background TWS polling
    - Start event bus

    Shutdown:
    - Stop background tasks gracefully
    - Close database connections

    RESILIENCE PATTERN:
    Each service initialization is wrapped in try/except to ensure that
    failure of one service doesn't prevent others from starting. This is
    intentional - the application can run in degraded mode with partial
    functionality rather than failing completely.

    Services that fail to initialize are logged as warnings/errors but
    the application continues. Check logs for "Could not initialize"
    messages to identify services that need attention.
    """
    logger.info("Application starting up...")

    # Initialize proactive monitoring if TWS client is available
    try:
        from resync.services.tws_service import get_tws_client

        tws_client = get_tws_client()

        if tws_client:
            from resync.core.monitoring_config import get_monitoring_config
            from resync.core.proactive_init import init_monitoring_system

            config = get_monitoring_config()

            await init_monitoring_system(
                tws_client=tws_client,
                polling_interval=config.polling_interval_seconds,
                # db_path removed - using PostgreSQL
                auto_start=True,
            )
            logger.info(
                "proactive_monitoring_started",
                polling_interval=config.polling_interval_seconds,
            )
        else:
            logger.warning("TWS client not available, proactive monitoring disabled")
    except ImportError as e:
        logger.warning(f"Could not initialize proactive monitoring: {e}")
    except Exception as e:
        logger.error(f"Error starting proactive monitoring: {e}")

    logger.info("Application startup complete")

    # Initialize AI Monitoring Service (Evidently)
    try:
        import json
        from pathlib import Path

        from resync.core.monitoring import MonitoringConfig, init_monitoring_service

        ai_config_path = Path("config/ai_config.json")
        if ai_config_path.exists():
            with open(ai_config_path) as f:
                ai_config = json.load(f)
            monitoring_config = MonitoringConfig(**ai_config.get("monitoring", {}))
        else:
            monitoring_config = MonitoringConfig()

        if monitoring_config.enabled:
            await init_monitoring_service(monitoring_config)
            logger.info("ai_monitoring_service_started", schedule=monitoring_config.schedule)
    except ImportError as e:
        logger.warning(f"Could not initialize AI monitoring: {e}")
    except Exception as e:
        logger.error(f"Error starting AI monitoring: {e}")

    # Initialize Specialist Agents Team
    try:
        from resync.core.specialists import create_specialist_team
        from resync.core.specialists.models import TeamConfig

        if ai_config_path.exists():
            with open(ai_config_path) as f:
                ai_config = json.load(f)
            specialists_config = ai_config.get("specialists", {})
            if specialists_config.get("enabled", True):
                team_config = TeamConfig(**specialists_config)
                await create_specialist_team(config=team_config)
                logger.info("specialist_agents_initialized")
        else:
            await create_specialist_team()
            logger.info("specialist_agents_initialized", config="default")
    except ImportError as e:
        logger.warning(f"Could not initialize specialist agents: {e}")
    except Exception as e:
        logger.error(f"Error initializing specialist agents: {e}")

    # Initialize Observability (LangFuse + Evidently)
    try:
        from resync.core.observability import setup_observability

        obs_results = await setup_observability()
        logger.info(
            "observability_initialized",
            langfuse=obs_results.get("langfuse"),
            evidently=obs_results.get("evidently"),
        )
    except ImportError as e:
        logger.warning(f"Could not initialize observability: {e}")
    except Exception as e:
        logger.error(f"Error initializing observability: {e}")

    # Start Backup Scheduler
    try:
        from resync.core.backup import get_backup_service

        backup_service = get_backup_service()
        await backup_service.start_scheduler()
        logger.info("backup_scheduler_started")
    except ImportError as e:
        logger.warning(f"Could not start backup scheduler: {e}")
    except Exception as e:
        logger.error(f"Error starting backup scheduler: {e}")

    yield  # Application runs here

    # Shutdown
    logger.info("Application shutting down...")

    try:
        from resync.core.proactive_init import shutdown_monitoring_system

        await shutdown_monitoring_system()
        logger.info("Proactive monitoring stopped")
    except Exception as e:
        logger.error(f"Error stopping proactive monitoring: {e}")

    # Shutdown AI Monitoring Service
    try:
        from resync.core.monitoring import get_monitoring_service

        service = get_monitoring_service()
        if service:
            await service.stop()
            logger.info("AI monitoring service stopped")
    except Exception as e:
        logger.error(f"Error stopping AI monitoring: {e}")

    # Shutdown Backup Scheduler
    try:
        from resync.core.backup import get_backup_service

        backup_service = get_backup_service()
        await backup_service.stop_scheduler()
        logger.info("Backup scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping backup scheduler: {e}")

    # Shutdown Observability
    try:
        from resync.core.observability import shutdown_observability

        await shutdown_observability()
        logger.info("Observability services stopped")
    except Exception as e:
        logger.error(f"Error stopping observability: {e}")

    logger.info("Application shutdown complete")


app = FastAPI(
    title="Resync API",
    version="5.2.1",
    description="AI Interface for HCL Workload Automation - Proactive Monitoring & Real-time Dashboard",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates - use absolute path from project root
import pathlib  # noqa: E402

project_root = pathlib.Path(__file__).parent.parent.parent
templates = Jinja2Templates(directory=str(project_root / "templates"))

# Include routers
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(audit_router, prefix="/api/v1", tags=["Audit"])
app.include_router(agents_router, prefix="/api/v1", tags=["Agents"])
app.include_router(rag_router, prefix="/api/v1", tags=["RAG"])
app.include_router(status_router, prefix="/api/v1", tags=["Status"])

# Include admin configuration routes under a dedicated namespace
app.include_router(admin_config_router, prefix="/api/v1/admin", tags=["Admin"])

# Include monitoring dashboard router (lightweight internal monitoring)
# Replaces need for Prometheus + Grafana (~1.2GB → ~50MB)
app.include_router(monitoring_router, tags=["Monitoring"])

# Include proactive monitoring router (real-time TWS events)
app.include_router(proactive_router, tags=["Proactive Monitoring"])

# Include system configuration router (admin settings management)
app.include_router(system_config_router, tags=["System Configuration"])

# Include LiteLLM management router (AI model configuration)
app.include_router(litellm_config_router, tags=["LiteLLM Configuration"])

# Include TWS multi-instance management router
app.include_router(tws_instances_router, prefix="/api/v1/admin", tags=["TWS Instances"])

# Include Threshold Tuning router for Active Learning threshold calibration
app.include_router(threshold_tuning_router, prefix="/api/v1/admin", tags=["Threshold Tuning"])

# Include AI Monitoring router (Specialist Agents + Evidently drift detection)
app.include_router(ai_monitoring_router, prefix="/api/v1/admin", tags=["AI Monitoring"])

# Include Backup management router
app.include_router(backup_router, prefix="/api/v1", tags=["Backup Management"])

# Include Observability management router (LangFuse + Evidently config)
app.include_router(observability_router, prefix="/api/v1", tags=["Observability"])

# Include Teams integration router
app.include_router(teams_router, prefix="/api/v1", tags=["Teams Integration"])


# WebSocket endpoint
@app.websocket("/api/v1/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for real-time chat with agents"""
    await websocket_handler(websocket, agent_id)


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Main dashboard page with all system functionalities"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", response_class=HTMLResponse)
async def health_page(request: Request):
    """Health check page with system status"""
    return templates.TemplateResponse("health.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Web page for chat interface"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/revisao", response_class=HTMLResponse)
async def revisao_page(request: Request):
    """Web page for review interface"""
    return templates.TemplateResponse("revisao.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Web page for admin interface"""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request):
    """
    Internal Monitoring Dashboard - Replaces Prometheus + Grafana

    Features:
    - Real-time metrics via WebSocket (5s updates)
    - 2-hour rolling history (~1.4 MB memory)
    - Chart.js visualizations (zero external dependencies)
    - Automatic alerts with browser notifications

    Resource Usage:
    - Memory: ~50 MB (vs ~1.2 GB for Prometheus+Grafana)
    - CPU: ~3% (vs ~15-20% for external stack)
    - Storage: 0 (in-memory rolling buffer)
    """
    return templates.TemplateResponse("monitoring.html", {"request": request})


@app.get("/tws-monitor", response_class=HTMLResponse)
async def tws_monitor_page(request: Request):
    """
    TWS Real-time Monitor Dashboard

    Features:
    - Live TWS status with WebSocket updates
    - Workstation health gauges
    - Job status tracking (running, completed, failed)
    - Event timeline with severity indicators
    - Pattern detection and suggestions
    - Dark mode and mobile responsive
    - Browser push notifications
    - Configurable polling interval
    """
    return templates.TemplateResponse("realtime_dashboard.html", {"request": request})


# API routes are now handled by routers included above
# Direct app routes removed to avoid conflicts
