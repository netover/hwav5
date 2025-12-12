"""
Tenant Middleware - Identificação de Tenant em Requests v5.4.0

Middleware FastAPI para identificar e validar tenant em cada request,
permitindo isolamento automático de dados.

Fontes de identificação:
1. Header X-Tenant-ID
2. JWT Token (claim tenant_id)
3. Subdomínio
4. Query parameter (para debug)

Versão: 5.4.0
"""

import logging
from typing import Callable, Optional
from datetime import datetime
import jwt

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from resync.core.multi_tenant.tenant_manager import (
    TenantManager,
    get_tenant_manager,
    TenantNotFoundError,
    TenantInactiveError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MIDDLEWARE
# =============================================================================


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware para identificar tenant em requests HTTP.
    
    Ordem de precedência:
    1. Header X-Tenant-ID
    2. JWT token (claim tenant_id)
    3. Subdomínio (tenant.example.com)
    4. Query parameter ?tenant_id= (apenas em debug mode)
    """
    
    def __init__(
        self,
        app,
        tenant_manager: TenantManager = None,
        jwt_secret: str = None,
        jwt_algorithm: str = "HS256",
        allow_query_param: bool = False,
        exempt_paths: list = None,
    ):
        """
        Inicializa o middleware.
        
        Args:
            app: FastAPI application
            tenant_manager: Gerenciador de tenants
            jwt_secret: Secret para validar JWT
            jwt_algorithm: Algoritmo JWT
            allow_query_param: Permitir tenant via query param (debug)
            exempt_paths: Paths que não requerem tenant
        """
        super().__init__(app)
        self.tenant_manager = tenant_manager or get_tenant_manager()
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.allow_query_param = allow_query_param
        self.exempt_paths = exempt_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/v1/auth/login",
            "/api/v1/auth/token",
        ]
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """
        Processa request identificando tenant.
        
        Args:
            request: Request HTTP
            call_next: Próximo handler
            
        Returns:
            Response
        """
        # Verificar se path está isento
        if self._is_exempt_path(request.url.path):
            return await call_next(request)
        
        try:
            # Identificar tenant
            tenant_id = await self._identify_tenant(request)
            environment = self._get_environment(request)
            
            if tenant_id:
                # Validar tenant
                config = await self.tenant_manager.validate_tenant(tenant_id)
                
                # Definir contexto
                self.tenant_manager.set_current_tenant(tenant_id, environment)
                
                # Adicionar info ao request state
                request.state.tenant_id = tenant_id
                request.state.tenant_config = config
                
                logger.debug(f"Request para tenant: {tenant_id} ({environment})")
            
            # Processar request
            response = await call_next(request)
            
            # Adicionar header de tenant na resposta
            if tenant_id:
                response.headers["X-Tenant-ID"] = tenant_id
            
            return response
            
        except TenantNotFoundError as e:
            logger.warning(f"Tenant não encontrado: {e.tenant_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "error": "tenant_not_found",
                    "message": f"Tenant '{e.tenant_id}' não encontrado",
                }
            )
            
        except TenantInactiveError as e:
            logger.warning(f"Tenant inativo: {e.tenant_id} ({e.status})")
            return JSONResponse(
                status_code=403,
                content={
                    "error": "tenant_inactive",
                    "message": f"Tenant '{e.tenant_id}' está {e.status}",
                }
            )
            
        except Exception as e:
            logger.error(f"Erro no middleware de tenant: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "message": "Erro ao processar tenant",
                }
            )
        
        finally:
            # Limpar contexto
            self.tenant_manager.clear_context()
    
    async def _identify_tenant(self, request: Request) -> Optional[str]:
        """
        Identifica tenant a partir do request.
        
        Args:
            request: Request HTTP
            
        Returns:
            ID do tenant ou None
        """
        tenant_id = None
        
        # 1. Header X-Tenant-ID
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            logger.debug(f"Tenant from header: {tenant_id}")
            return tenant_id
        
        # 2. JWT Token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            tenant_id = self._extract_tenant_from_jwt(token)
            if tenant_id:
                logger.debug(f"Tenant from JWT: {tenant_id}")
                return tenant_id
        
        # 3. Subdomínio
        host = request.headers.get("Host", "")
        tenant_id = self._extract_tenant_from_subdomain(host)
        if tenant_id:
            logger.debug(f"Tenant from subdomain: {tenant_id}")
            return tenant_id
        
        # 4. Query parameter (debug mode)
        if self.allow_query_param:
            tenant_id = request.query_params.get("tenant_id")
            if tenant_id:
                logger.debug(f"Tenant from query param: {tenant_id}")
                return tenant_id
        
        return None
    
    def _extract_tenant_from_jwt(self, token: str) -> Optional[str]:
        """
        Extrai tenant_id do JWT token.
        
        Args:
            token: JWT token
            
        Returns:
            tenant_id ou None
        """
        if not self.jwt_secret:
            return None
        
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
            )
            return payload.get("tenant_id")
            
        except jwt.InvalidTokenError as e:
            logger.debug(f"JWT inválido: {e}")
            return None
    
    def _extract_tenant_from_subdomain(self, host: str) -> Optional[str]:
        """
        Extrai tenant do subdomínio.
        
        Formato esperado: {tenant}.example.com
        
        Args:
            host: Host header
            
        Returns:
            tenant_id ou None
        """
        if not host:
            return None
        
        # Remover porta
        host = host.split(":")[0]
        
        # Verificar se tem subdomínio
        parts = host.split(".")
        if len(parts) >= 3:
            subdomain = parts[0]
            # Ignorar subdomínios comuns
            if subdomain not in ("www", "api", "app", "admin"):
                return subdomain
        
        return None
    
    def _get_environment(self, request: Request) -> Optional[str]:
        """
        Obtém ambiente do request.
        
        Args:
            request: Request HTTP
            
        Returns:
            Nome do ambiente ou None
        """
        # Header X-Environment
        env = request.headers.get("X-Environment")
        if env:
            return env
        
        # Inferir do host
        host = request.headers.get("Host", "")
        if "staging" in host:
            return "staging"
        if "dev" in host or "localhost" in host:
            return "development"
        if "homolog" in host or "hom" in host:
            return "homologation"
        
        return "production"
    
    def _is_exempt_path(self, path: str) -> bool:
        """
        Verifica se path está isento de validação de tenant.
        
        Args:
            path: Path do request
            
        Returns:
            True se isento
        """
        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return True
        return False


# =============================================================================
# DEPENDENCIES (FastAPI)
# =============================================================================


async def get_current_tenant(request: Request) -> str:
    """
    Dependency para obter tenant atual.
    
    Uso:
        @router.get("/items")
        async def list_items(tenant_id: str = Depends(get_current_tenant)):
            ...
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Tenant não identificado no request",
        )
    
    return tenant_id


async def get_tenant_config(request: Request):
    """
    Dependency para obter configuração do tenant atual.
    
    Uso:
        @router.get("/config")
        async def get_config(config = Depends(get_tenant_config)):
            ...
    """
    config = getattr(request.state, "tenant_config", None)
    
    if not config:
        raise HTTPException(
            status_code=400,
            detail="Configuração de tenant não disponível",
        )
    
    return config


def require_feature(feature: str):
    """
    Dependency factory para exigir feature habilitada.
    
    Uso:
        @router.get("/reports")
        async def get_reports(
            config = Depends(require_feature("reports"))
        ):
            ...
    """
    async def _check_feature(request: Request):
        config = getattr(request.state, "tenant_config", None)
        
        if not config:
            raise HTTPException(
                status_code=400,
                detail="Tenant não identificado",
            )
        
        if not config.has_feature(feature):
            raise HTTPException(
                status_code=403,
                detail=f"Feature '{feature}' não habilitada para este tenant",
            )
        
        return config
    
    return _check_feature


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def setup_tenant_middleware(
    app,
    jwt_secret: str = None,
    allow_debug: bool = False,
    exempt_paths: list = None,
):
    """
    Configura middleware de tenant na aplicação.
    
    Args:
        app: FastAPI application
        jwt_secret: Secret JWT para validação de tokens
        allow_debug: Permitir tenant via query param
        exempt_paths: Paths isentos de validação
    """
    middleware = TenantMiddleware(
        app,
        jwt_secret=jwt_secret,
        allow_query_param=allow_debug,
        exempt_paths=exempt_paths,
    )
    
    # O middleware já é adicionado pelo construtor BaseHTTPMiddleware
    logger.info("Tenant middleware configurado")


def get_tenant_from_request(request: Request) -> Optional[str]:
    """
    Obtém tenant_id do request (sem validação).
    
    Útil para logging e métricas.
    
    Args:
        request: Request HTTP
        
    Returns:
        tenant_id ou None
    """
    return getattr(request.state, "tenant_id", None)
