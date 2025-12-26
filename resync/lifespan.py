"""Application lifespan management.

v5.6.0: Enhanced with OpenTelemetry and improved observability.

This module handles FastAPI application startup and shutdown events,
managing the lifecycle of critical application components including:

- Database connections and pools
- Redis connections and health monitoring (FAIL-FAST)
- OpenTelemetry distributed tracing
- Prometheus metrics
- Background task schedulers
- Health check services
- Enterprise modules
- Resource cleanup and graceful shutdown

Redis Strategy Tiers:
- READ_ONLY: Never needs Redis (health checks, docs)
- BEST_EFFORT: Cache optional, degrades gracefully
- CRITICAL: Redis required, app won't start without it (default in production)
"""

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import datetime

from fastapi import FastAPI
from redis.exceptions import (
    BusyLoadingError,
    ResponseError,
)

from resync.api_gateway.container import setup_dependencies
from resync.core.container import app_container
from resync.core.exceptions import (
    ConfigurationError,
    RedisAuthError,
    RedisConnectionError,
    RedisInitializationError,
    RedisTimeoutError,
)
from resync.core.interfaces import IAgentManager, IKnowledgeGraph, ITWSClient
from resync.core.redis_init import RedisInitializer
from resync.core.structured_logger import get_logger
from resync.core.tws_monitor import get_tws_monitor, shutdown_tws_monitor

# CQRS removed in v5.9.3 - was unused code
from resync.settings import settings

# Import observability (v5.6.0)
try:
    from resync.core.observability import (
        setup_prometheus_metrics,
        setup_telemetry,
        shutdown_telemetry,
    )

    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

# Import rate limiting (v5.6.0)
try:
    from resync.core.security.rate_limiter_v2 import setup_rate_limiting

    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False

logger = get_logger(__name__)

# Track application startup time
_startup_time: datetime | None = None


def get_startup_time() -> datetime | None:
    """Get the application startup time."""
    return _startup_time


def set_startup_time() -> None:
    """Set the startup time to now."""
    global _startup_time
    from datetime import datetime

    _startup_time = datetime.utcnow()


# Lazy initialization with environment flag
_EAGER = os.getenv("RESYNC_EAGER_BOOT") == "1"
_BOOTED = False

# Background task handle for Redis health monitoring
_redis_health_task = None


def boot_if_needed():
    """Boot lifespan components if needed, preventing multiple initializations."""
    global _BOOTED
    if _BOOTED:
        return
    _BOOTED = True
    logger.info("Lifespan booted lazily.")


if _EAGER:
    boot_if_needed()

# Create a global RedisInitializer instance - lazy initialization
_redis_initializer = None


def get_redis_initializer() -> RedisInitializer:
    """Get the global Redis initializer instance with lazy initialization."""
    global _redis_initializer
    if _redis_initializer is None:
        _redis_initializer = RedisInitializer()
    return _redis_initializer


def get_redis_strategy_config() -> dict:
    """
    Get Redis strategy configuration.

    Returns configuration for fail-fast behavior based on:
    1. config/redis_strategy.yaml if exists
    2. Environment variables
    3. Defaults (fail_fast=True for production)
    """
    try:
        from resync.core.redis_strategy import get_redis_strategy

        strategy = get_redis_strategy()
        return strategy.get_startup_config()
    except Exception as e:
        logger.warning(
            "redis_strategy_load_failed_using_defaults",
            error=str(e),
        )
        # Default: fail-fast enabled unless explicitly disabled
        return {
            "fail_fast": os.getenv("REDIS_FAIL_FAST_ON_STARTUP", "true").lower() == "true",
            "max_retries": int(os.getenv("REDIS_MAX_RETRIES", "3")),
            "backoff_seconds": float(os.getenv("REDIS_BACKOFF_SECONDS", "0.5")),
        }


@asynccontextmanager
async def redis_connection_manager() -> AsyncIterator:
    """
    Context manager para Redis com cleanup automático.

    Yields:
        Redis client validado

    Raises:
        RedisConnectionError: Falha de conexão
        RedisAuthError: Falha de autenticação
    """
    from resync.core.cache import get_redis_client

    client = None
    try:
        client = await get_redis_client()

        # Validar conexão antes de usar
        await client.ping()
        logger.info("redis_connection_validated")

        yield client

    except RedisConnectionError as e:
        logger.error(
            "redis_connection_failed",
            error=str(e),
            redis_url=settings.REDIS_URL.split("@")[-1],  # Sem senha no log
        )
        raise RedisConnectionError(
            "Não foi possível conectar ao Redis",
            details={
                "redis_url": settings.REDIS_URL.split("@")[-1],
                "error": str(e),
                "hint": "Verifique se Redis está rodando: redis-cli ping",
            },
        ) from e

    except RedisAuthError as e:
        logger.error("redis_auth_failed", error=str(e))
        raise RedisAuthError(
            "Falha de autenticação no Redis",
            details={"error": str(e), "hint": "Verifique REDIS_URL no .env"},
        ) from e

    except RedisTimeoutError as e:
        logger.error("redis_timeout", error=str(e))
        raise RedisTimeoutError(
            "Timeout ao conectar ao Redis",
            details={
                "error": str(e),
                "hint": "Redis pode estar sobrecarregado ou rede lenta",
            },
        ) from e

    finally:
        if client:
            try:
                await client.close()
                await client.connection_pool.disconnect()
                logger.debug("redis_connection_closed")
            except Exception as e:
                logger.warning("redis_cleanup_warning", error=type(e).__name__, message=str(e))


async def initialize_redis_with_retry(
    max_retries: int = 3, base_backoff: float = 0.5, max_backoff: float = 5.0
) -> None:
    """
    Inicializa Redis com retry exponencial.

    Args:
        max_retries: Máximo de tentativas
        base_backoff: Tempo base de espera (segundos)
        max_backoff: Tempo máximo de espera (segundos)

    Raises:
        RedisConnectionError: Redis inacessível após retries
        RedisAuthError: Credenciais inválidas
        RedisTimeoutError: Timeout persistente
    """

    # Validar configuração
    if not settings.REDIS_URL:
        logger.critical("redis_url_missing")
        raise ConfigurationError(
            "REDIS_URL não configurado",
            details={"hint": "Adicione REDIS_URL ao arquivo .env"},
        )

    logger.info(
        "redis_initialization_started",
        max_retries=max_retries,
        redis_url=settings.REDIS_URL.split("@")[-1],
    )

    last_error = None

    for attempt in range(max_retries):
        try:
            async with redis_connection_manager() as redis_client:
                # Inicializar idempotency manager
                from resync.api.dependencies import initialize_idempotency_manager

                await initialize_idempotency_manager(redis_client)

                logger.info("redis_initialized", attempt=attempt + 1, max_retries=max_retries)
                return

        except RedisAuthError:
            # Não faz retry em erro de auth
            logger.critical("redis_auth_failed_no_retry")
            raise

        except (RedisConnectionError, RedisTimeoutError) as e:
            last_error = e

            if attempt >= max_retries - 1:
                # Última tentativa falhou
                logger.critical("redis_initialization_failed", attempts=max_retries, error=str(e))
                raise

            # Calcular backoff exponencial
            backoff = min(max_backoff, base_backoff * (2**attempt))

            logger.warning(
                "redis_retry_attempt",
                attempt=attempt + 1,
                max_retries=max_retries,
                next_retry_seconds=backoff,
                error=str(e),
            )

            await asyncio.sleep(backoff)

        except ResponseError as e:
            error_msg = str(e).upper()

            # Verificar se é erro de autenticação disfarçado
            if "NOAUTH" in error_msg or "WRONGPASS" in error_msg:
                logger.critical("redis_access_denied", error=str(e))
                raise RedisAuthError(
                    "Redis requer autenticação",
                    details={
                        "error": str(e),
                        "hint": "Adicione senha ao REDIS_URL: redis://:senha@localhost:6379",
                    },
                ) from e

            # Outros erros de resposta
            if attempt >= max_retries - 1:
                logger.critical("redis_response_error", error=str(e))
                raise RedisInitializationError(
                    f"Erro Redis: {str(e)}", details={"error": str(e)}
                ) from e

            backoff = min(max_backoff, base_backoff * (2**attempt))
            await asyncio.sleep(backoff)

        except BusyLoadingError as e:
            # Redis ainda carregando
            if attempt >= max_retries - 1:
                logger.critical("redis_busy_loading", error=str(e))
                raise RedisConnectionError(
                    "Redis ocupado carregando dados",
                    details={
                        "error": str(e),
                        "hint": "Aguarde Redis finalizar carga inicial",
                    },
                ) from e

            backoff = min(max_backoff, base_backoff * (2**attempt))
            logger.warning("redis_busy_retry", attempt=attempt + 1, backoff_seconds=backoff)
            await asyncio.sleep(backoff)

        except Exception as e:
            # Erro inesperado - fail fast
            logger.critical("redis_unexpected_error", error_type=type(e).__name__, error=str(e))
            raise RedisInitializationError(
                f"Erro inesperado ao inicializar Redis: {type(e).__name__}",
                details={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "hint": "Verifique logs para detalhes",
                },
            ) from e

    # Se chegou aqui, todas as tentativas falharam
    if last_error:
        raise last_error


async def redis_health_monitor(app: FastAPI):
    """
    Background task para monitorar saúde do Redis.

    Se Redis ficar indisponível:
    - Atualiza app.state.redis_available = False
    - Endpoints CRITICAL retornarão 503
    - Endpoints BEST_EFFORT degradarão

    Se Redis voltar:
    - Atualiza app.state.redis_available = True
    - Endpoints voltam ao normal
    """
    from resync.core.cache import get_redis_client

    check_interval = int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30"))
    consecutive_failures = 0
    max_failures_before_degraded = 3

    logger.info("redis_health_monitor_started", interval_seconds=check_interval)

    while True:
        try:
            await asyncio.sleep(check_interval)

            # Health check
            client = await get_redis_client()
            await client.ping()

            # Redis is healthy
            if not getattr(app.state, "redis_available", True):
                logger.info("redis_recovered_from_failure")
                app.state.redis_available = True
                consecutive_failures = 0

        except asyncio.CancelledError:
            logger.info("redis_health_monitor_cancelled")
            break

        except Exception as e:
            consecutive_failures += 1

            if getattr(app.state, "redis_available", True):
                logger.warning(
                    "redis_health_check_failed",
                    error=str(e),
                    consecutive_failures=consecutive_failures,
                )

                if consecutive_failures >= max_failures_before_degraded:
                    logger.error(
                        "redis_marked_unavailable",
                        consecutive_failures=consecutive_failures,
                        impact="CRITICAL endpoints will return 503",
                    )
                    app.state.redis_available = False


@asynccontextmanager
async def lifespan_with_improvements(app: FastAPI) -> AsyncIterator[None]:
    """
    Unified Lifecycle Manager com Redis FAIL-FAST Strategy.

    v5.4.5 Features:
    - Auth requirements validation at startup (fail-closed)
    - Single source of truth para lifespan
    - Redis FAIL-FAST configurável no startup
    - Background health check de Redis
    - Graceful shutdown
    - Documented tier-based degradation

    Phases:
    0. Auth requirements validation (FAIL-CLOSED)
    1. Redis initialization (FAIL-FAST if configured)
    2. DI Container warmup
    3. CQRS Dispatcher initialization
    4. Background tasks startup
    5. Application ready

    Shutdown:
    1. Stop background tasks
    2. Cleanup resources
    3. Close connections
    """
    global _redis_health_task

    logger.info("starting_application_v5.4.5", version="5.4.5")

    # Initialize app state
    app.state.redis_available = False
    app.state.startup_complete = False

    # ===================================================================
    # PHASE 0: Auth Requirements Validation (FAIL-CLOSED)
    # ===================================================================
    logger.info("phase_0_auth_validation")

    try:
        from resync.api.security import validate_auth_requirements

        validate_auth_requirements()
        logger.info("auth_requirements_validated")
    except RuntimeError as e:
        # In development, warn but continue
        environment = os.getenv("ENVIRONMENT", os.getenv("ENV", "production"))
        if environment.lower() in ("development", "dev", "local", "test"):
            logger.warning(
                "auth_validation_skipped_dev_mode",
                error=str(e),
                hint="This would fail in production",
            )
        else:
            logger.critical("auth_validation_failed", error=str(e))
            sys.exit(1)
    except ImportError as e:
        logger.warning(
            "auth_module_import_failed",
            error=str(e),
            hint="Install PyJWT: pip install PyJWT>=2.10.1",
        )

    # Get Redis strategy configuration
    strategy_config = get_redis_strategy_config()
    fail_fast = strategy_config.get("fail_fast", True)

    logger.info(
        "redis_strategy_config",
        fail_fast=fail_fast,
        max_retries=strategy_config.get("max_retries", 3),
    )

    try:
        # ===================================================================
        # PHASE 1: Redis Initialization (FAIL-FAST)
        # ===================================================================
        logger.info("phase_1_redis_initialization", fail_fast=fail_fast)

        try:
            await initialize_redis_with_retry(
                max_retries=strategy_config.get("max_retries", 3),
                base_backoff=strategy_config.get("backoff_seconds", 0.5),
            )
            app.state.redis_available = True
            logger.info("redis_initialization_success")

        except (
            RedisConnectionError,
            RedisAuthError,
            RedisTimeoutError,
            RedisInitializationError,
        ) as e:
            logger.error("redis_initialization_failed", error=str(e))

            if fail_fast:
                logger.critical(
                    "fail_fast_enabled_exiting",
                    reason="Redis is required but unavailable",
                    hint="Set REDIS_FAIL_FAST_ON_STARTUP=false for development",
                )
                sys.exit(1)
            else:
                logger.warning(
                    "starting_in_degraded_mode",
                    impact="CRITICAL endpoints will return 503",
                )
                app.state.redis_available = False

        # ===================================================================
        # PHASE 2: Core Architecture (DI Container + CQRS)
        # ===================================================================
        logger.info("phase_2_core_architecture")

        # Get required services from DI container
        tws_client = await app_container.get(ITWSClient)
        agent_manager = await app_container.get(IAgentManager)
        knowledge_graph = await app_container.get(IKnowledgeGraph)

        # Initialize TWS monitor
        await get_tws_monitor(tws_client)

        # Setup dependency injection
        setup_dependencies(tws_client, agent_manager, knowledge_graph)

        # CQRS dispatcher removed in v5.9.3 (was unused)

        logger.info("core_architecture_initialized")

        # ===================================================================
        # PHASE 3: Enterprise Modules (v5.5.0)
        # ===================================================================
        logger.info("phase_3_enterprise_modules")

        try:
            from resync.core.enterprise import get_enterprise_manager

            enterprise = await get_enterprise_manager()
            app.state.enterprise = enterprise
            logger.info(
                "enterprise_modules_initialized",
                status=enterprise.get_status(),
            )
        except Exception as e:
            logger.warning(
                "enterprise_modules_init_failed",
                error=str(e),
                hint="Enterprise features will be unavailable",
            )
            app.state.enterprise = None

        # ===================================================================
        # PHASE 3.5: Observability (v5.6.0)
        # ===================================================================
        logger.info("phase_3_5_observability")

        if OBSERVABILITY_AVAILABLE:
            try:
                # Setup OpenTelemetry distributed tracing
                setup_telemetry(app)
                logger.info("opentelemetry_initialized")

                # Setup Prometheus metrics
                setup_prometheus_metrics(app)
                logger.info("prometheus_metrics_initialized")
            except Exception as e:
                logger.warning(
                    "observability_init_failed",
                    error=str(e),
                    hint="Observability features may be limited",
                )
        else:
            logger.info("observability_not_available", hint="Install opentelemetry packages")

        # Setup rate limiting
        if RATE_LIMITING_AVAILABLE:
            try:
                setup_rate_limiting(app)
                logger.info("rate_limiting_initialized")
            except Exception as e:
                logger.warning("rate_limiting_init_failed", error=str(e))

        # ===================================================================
        # PHASE 4: Background Tasks
        # ===================================================================
        logger.info("phase_4_background_tasks")

        # Start Redis health monitor if Redis is available
        if app.state.redis_available:
            _redis_health_task = asyncio.create_task(redis_health_monitor(app))
            logger.info("redis_health_monitor_started")

        # ===================================================================
        # STARTUP COMPLETE
        # ===================================================================
        app.state.startup_complete = True
        set_startup_time()  # Track startup time for admin UI
        logger.info(
            "application_startup_completed",
            redis_available=app.state.redis_available,
            mode="normal" if app.state.redis_available else "degraded",
        )

        yield  # Application runs here

    except Exception as e:
        logger.critical("failed_to_start_application", error=str(e), exc_info=True)
        raise

    finally:
        # ===================================================================
        # SHUTDOWN
        # ===================================================================
        logger.info("shutting_down_application")

        # Stop background tasks
        if _redis_health_task:
            _redis_health_task.cancel()
            with suppress(asyncio.CancelledError):
                await _redis_health_task
            logger.info("redis_health_monitor_stopped")

        try:
            await shutdown_tws_monitor()
            logger.info("tws_monitor_shutdown_completed")
        except Exception as e:
            logger.error("error_during_shutdown", error=str(e), exc_info=True)

        # Shutdown observability (v5.6.0)
        if OBSERVABILITY_AVAILABLE:
            try:
                shutdown_telemetry()
                logger.info("opentelemetry_shutdown_completed")
            except Exception as e:
                logger.error("opentelemetry_shutdown_error", error=str(e))

        # Shutdown enterprise modules
        try:
            if hasattr(app.state, "enterprise") and app.state.enterprise:
                from resync.core.enterprise import shutdown_enterprise_manager

                await shutdown_enterprise_manager()
                logger.info("enterprise_modules_shutdown_completed")
        except Exception as e:
            logger.error("enterprise_shutdown_error", error=str(e), exc_info=True)

        logger.info("application_shutdown_completed")
