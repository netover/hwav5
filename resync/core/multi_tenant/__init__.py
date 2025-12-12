"""
Multi-tenant Module - Resync v5.4.0

Fornece isolamento de dados e configurações por tenant/cliente,
permitindo que múltiplas organizações utilizem a mesma instância
com dados completamente segregados.

Componentes:
- TenantManager: Gerenciamento de configurações de tenant
- MultiTenantCache: Cache isolado por tenant
- MultiTenantKGService: Knowledge Graph separado por tenant
- TenantMiddleware: Identificação de tenant em requests

Uso básico:
    from resync.core.multi_tenant import (
        get_tenant_manager,
        TenantMiddleware,
        MultiTenantCache,
    )
    
    # Configurar middleware
    app.add_middleware(TenantMiddleware)
    
    # Em código
    tenant_manager = get_tenant_manager()
    tenant_manager.set_current_tenant("client_a")
    
    # Cache isolado
    cache = MultiTenantCache(base_cache)
    await cache.set("key", "value")  # Prefixado com tenant

Versão: 5.4.0
"""

from resync.core.multi_tenant.tenant_manager import (
    TenantManager,
    TenantConfig,
    TenantLimits,
    TenantEnvironment,
    TenantStatus,
    TenantError,
    TenantNotFoundError,
    TenantInactiveError,
    NoTenantContextError,
    TenantLimitExceededError,
    get_tenant_manager,
    reset_tenant_manager,
    current_tenant,
    current_environment,
)

from resync.core.multi_tenant.multi_tenant_cache import (
    MultiTenantCache,
    InMemoryMultiTenantCache,
)

from resync.core.multi_tenant.tenant_middleware import (
    TenantMiddleware,
    get_current_tenant,
    get_tenant_config,
    require_feature,
    setup_tenant_middleware,
    get_tenant_from_request,
)

from resync.core.multi_tenant.multi_tenant_kg import (
    MultiTenantKGService,
    MultiTenantKGConfig,
    get_multi_tenant_kg_service,
)


__all__ = [
    # Manager
    "TenantManager",
    "TenantConfig",
    "TenantLimits",
    "TenantEnvironment",
    "TenantStatus",
    "get_tenant_manager",
    "reset_tenant_manager",
    "current_tenant",
    "current_environment",
    
    # Exceptions
    "TenantError",
    "TenantNotFoundError",
    "TenantInactiveError",
    "NoTenantContextError",
    "TenantLimitExceededError",
    
    # Cache
    "MultiTenantCache",
    "InMemoryMultiTenantCache",
    
    # Middleware
    "TenantMiddleware",
    "get_current_tenant",
    "get_tenant_config",
    "require_feature",
    "setup_tenant_middleware",
    "get_tenant_from_request",
    
    # Knowledge Graph
    "MultiTenantKGService",
    "MultiTenantKGConfig",
    "get_multi_tenant_kg_service",
]
