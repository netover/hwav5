"""
Rate Limiter usando Redis - Token Bucket Algorithm

Implementa rate limiting com Redis para proteção contra abuse/DDoS.
Usa algoritmo de token bucket com sliding window.

PERFORMANCE: Pure ASGI implementation (1.5-2x faster than BaseHTTPMiddleware)
Storage: ~100 bytes por IP no Redis

Configurações por tipo de endpoint:
- Autenticação: 5 req/min (proteção contra brute force)
- APIs normais: 100 req/min (uso geral)
- LLM endpoints: 10 req/min (custos altos)
"""

import time

from redis.asyncio import Redis
from starlette.datastructures import MutableHeaders
from starlette.types import Message, Receive, Scope, Send

import structlog

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    """Exception para rate limit excedido."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class RedisRateLimiter:
    """
    Rate limiter usando Redis com sliding window algorithm.

    Implementação eficiente que usa apenas 1 comando Redis por request.
    """

    def __init__(self, redis: Redis):
        """
        Inicializa rate limiter.

        Args:
            redis: Instância do Redis client
        """
        self.redis = redis

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int = 60,
    ) -> tuple[bool, int, int]:
        """
        Verifica rate limit usando sliding window.

        Args:
            key: Chave única para o recurso (ex: "rate_limit:192.168.1.1:/api/login")
            limit: Número máximo de requests
            window: Janela de tempo em segundos

        Returns:
            (allowed, remaining, retry_after)
            - allowed: Se request é permitido
            - remaining: Requests restantes
            - retry_after: Segundos até resetar (se não permitido)
        """
        now = time.time()
        window_start = now - window

        # Lua script para operação atômica
        # Remove entries antigas, conta requests, adiciona novo request
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_start = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local window = tonumber(ARGV[4])

        -- Remove entries antigas
        redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

        -- Conta requests na janela atual
        local current = redis.call('ZCARD', key)

        if current < limit then
            -- Adiciona novo request
            redis.call('ZADD', key, now, now)
            redis.call('EXPIRE', key, window)
            return {1, limit - current - 1, 0}
        else
            -- Rate limit excedido, calcula retry_after
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')[2]
            local retry_after = math.ceil(oldest + window - now)
            return {0, 0, retry_after}
        end
        """

        try:
            result = await self.redis.eval(
                lua_script,
                1,
                key,
                now,
                window_start,
                limit,
                window,
            )

            allowed = bool(result[0])
            remaining = int(result[1])
            retry_after = int(result[2])

            return allowed, remaining, retry_after

        except Exception as e:
            # Se Redis falhar, permite request (fail-open)
            # Logga erro mas não bloqueia aplicação
            logger.error(
                "rate_limiter_redis_error",
                error=str(e),
                key=key,
            )
            return True, limit, 0


class RateLimitMiddleware:
    """
    Pure ASGI middleware de rate limiting por IP e endpoint.

    Aplica diferentes limites baseados no path:
    - /api/auth/*: 5 req/min (proteção brute force)
    - /api/llm/*: 10 req/min (custos LLM)
    - Outros: 100 req/min (uso geral)

    PERFORMANCE: 1.5-2x faster than BaseHTTPMiddleware
    """

    def __init__(
        self,
        app,
        redis: Redis,
        enabled: bool = True,
        default_limit: int = 100,
        default_window: int = 60,
    ):
        """
        Inicializa middleware.

        Args:
            app: ASGI application
            redis: Redis client
            enabled: Se rate limiting está ativo
            default_limit: Limite padrão (requests)
            default_window: Janela padrão (segundos)
        """
        self.app = app
        self.limiter = RedisRateLimiter(redis)
        self.enabled = enabled
        self.default_limit = default_limit
        self.default_window = default_window

        # Configurações específicas por path pattern
        self.path_limits = {
            "/api/auth/": (5, 60),  # 5 req/min para auth
            "/api/llm/": (10, 60),  # 10 req/min para LLM
            "/health/": (1000, 60),  # Health checks sem limite real
        }

    def _get_limit_for_path(self, path: str) -> tuple[int, int]:
        """Determina limite baseado no path."""
        for prefix, (limit, window) in self.path_limits.items():
            if path.startswith(prefix):
                return limit, window
        return self.default_limit, self.default_window

    def _get_client_ip(self, headers: list[tuple[bytes, bytes]]) -> str:
        """Extrai IP do cliente dos headers."""
        # Try X-Forwarded-For first
        for header_name, header_value in headers:
            if header_name == b"x-forwarded-for":
                # Take first IP in the list
                ip = header_value.decode().split(",")[0].strip()
                return ip
            elif header_name == b"x-real-ip":
                return header_value.decode()

        # Fallback to client address from scope
        return "unknown"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI interface implementation."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip if disabled
        if not self.enabled:
            await self.app(scope, receive, send)
            return

        path = scope["path"]

        # Skip health checks always
        if path.startswith("/health/"):
            await self.app(scope, receive, send)
            return

        # Determine limit based on path
        limit, window = self._get_limit_for_path(path)

        # Get client IP
        client_ip = self._get_client_ip(scope["headers"])
        if scope.get("client"):
            if client_ip == "unknown":
                client_ip = scope["client"][0]  # (host, port) tuple

        # Rate limit key
        rate_limit_key = f"rate_limit:{client_ip}:{path}"

        try:
            # Check rate limit
            allowed, remaining, retry_after = await self.limiter.check_rate_limit(
                rate_limit_key, limit, window
            )

            if not allowed:
                # Rate limit exceeded - return 429
                response_body = {
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after
                }

                import json
                body = json.dumps(response_body).encode()

                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"x-ratelimit-limit", str(limit).encode()],
                        [b"x-ratelimit-remaining", b"0"],
                        [b"x-ratelimit-reset", str(retry_after).encode()],
                        [b"retry-after", str(retry_after).encode()],
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })

                logger.warning(
                    "rate_limit_exceeded",
                    client_ip=client_ip,
                    path=path,
                    limit=limit,
                    retry_after=retry_after,
                )
                return

            # Add rate limit headers to response
            async def send_with_rate_limit_headers(message: Message) -> None:
                if message["type"] == "http.response.start":
                    headers = MutableHeaders(scope=message)
                    headers.append("X-RateLimit-Limit", str(limit))
                    headers.append("X-RateLimit-Remaining", str(remaining))
                    headers.append("X-RateLimit-Window", str(window))

                await send(message)

            await self.app(scope, receive, send_with_rate_limit_headers)

        except Exception as e:
            # Fail open - allow request if Redis fails
            logger.error(
                "rate_limit_check_failed",
                error=str(e),
                client_ip=client_ip,
                path=path,
            )
            await self.app(scope, receive, send)

