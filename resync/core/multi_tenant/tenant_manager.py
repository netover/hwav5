"""
Multi-tenant Manager - Gerenciamento de Tenants v5.4.0

Gerencia configurações e isolamento de tenants para:
- Cache semântico isolado por tenant
- Knowledge Graph separado por ambiente
- Configurações específicas por cliente
- Métricas e audit logs segregados

Versão: 5.4.0
"""

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# CONTEXT VARIABLES
# =============================================================================

# Context variable para tenant atual (thread-safe)
current_tenant: ContextVar[Optional[str]] = ContextVar('current_tenant', default=None)

# Context variable para ambiente atual
current_environment: ContextVar[Optional[str]] = ContextVar('current_environment', default=None)


# =============================================================================
# ENUMS
# =============================================================================


class TenantEnvironment(Enum):
    """Ambientes disponíveis por tenant."""
    PRODUCTION = "production"
    HOMOLOGATION = "homologation"
    DEVELOPMENT = "development"
    STAGING = "staging"
    SANDBOX = "sandbox"


class TenantStatus(Enum):
    """Status do tenant."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    EXPIRED = "expired"
    PENDING = "pending"


# =============================================================================
# MODELS
# =============================================================================


@dataclass
class TenantLimits:
    """Limites de uso por tenant."""
    
    max_cache_size_mb: int = 100
    max_cache_entries: int = 10000
    max_kg_nodes: int = 50000
    max_kg_relations: int = 100000
    max_requests_per_minute: int = 100
    max_concurrent_queries: int = 10
    cache_ttl_hours: int = 24
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_cache_size_mb": self.max_cache_size_mb,
            "max_cache_entries": self.max_cache_entries,
            "max_kg_nodes": self.max_kg_nodes,
            "max_kg_relations": self.max_kg_relations,
            "max_requests_per_minute": self.max_requests_per_minute,
            "max_concurrent_queries": self.max_concurrent_queries,
            "cache_ttl_hours": self.cache_ttl_hours,
        }


@dataclass
class TenantConfig:
    """Configuração completa de um tenant."""
    
    tenant_id: str
    name: str
    environment: TenantEnvironment = TenantEnvironment.PRODUCTION
    status: TenantStatus = TenantStatus.ACTIVE
    
    # Prefixos para isolamento
    cache_prefix: str = ""
    kg_schema: str = ""
    
    # Conexões TWS
    tws_instance: str = ""
    tws_api_url: str = ""
    
    # Limites
    limits: TenantLimits = field(default_factory=TenantLimits)
    
    # Features habilitadas
    features: Set[str] = field(default_factory=set)
    
    # Metadados
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Configurações customizadas
    custom_config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Gerar prefixos padrão se não fornecidos
        if not self.cache_prefix:
            self.cache_prefix = f"tenant:{self.tenant_id}:cache"
        if not self.kg_schema:
            self.kg_schema = f"kg_{self.tenant_id}"
        
        # Converter features para set
        if isinstance(self.features, list):
            self.features = set(self.features)
    
    def is_active(self) -> bool:
        """Verifica se tenant está ativo."""
        if self.status != TenantStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def has_feature(self, feature: str) -> bool:
        """Verifica se feature está habilitada."""
        return feature in self.features
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "environment": self.environment.value,
            "status": self.status.value,
            "cache_prefix": self.cache_prefix,
            "kg_schema": self.kg_schema,
            "tws_instance": self.tws_instance,
            "tws_api_url": self.tws_api_url,
            "limits": self.limits.to_dict(),
            "features": list(self.features),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active(),
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================


class TenantError(Exception):
    """Erro base para operações de tenant."""
    pass


class TenantNotFoundError(TenantError):
    """Tenant não encontrado."""
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        super().__init__(f"Tenant não encontrado: {tenant_id}")


class TenantInactiveError(TenantError):
    """Tenant inativo ou expirado."""
    def __init__(self, tenant_id: str, status: str):
        self.tenant_id = tenant_id
        self.status = status
        super().__init__(f"Tenant {tenant_id} está {status}")


class NoTenantContextError(TenantError):
    """Operação requer contexto de tenant."""
    def __init__(self):
        super().__init__("Operação requer contexto de tenant")


class TenantLimitExceededError(TenantError):
    """Limite do tenant excedido."""
    def __init__(self, tenant_id: str, limit_name: str, current: int, max_value: int):
        self.tenant_id = tenant_id
        self.limit_name = limit_name
        self.current = current
        self.max_value = max_value
        super().__init__(
            f"Tenant {tenant_id}: limite {limit_name} excedido "
            f"({current}/{max_value})"
        )


# =============================================================================
# TENANT MANAGER
# =============================================================================


class TenantManager:
    """
    Gerenciador de Tenants.
    
    Responsabilidades:
    - Carregar/cachear configurações de tenants
    - Gerenciar contexto de tenant atual
    - Validar permissões e limites
    - Gerar chaves/prefixos isolados
    """
    
    def __init__(self, db_session = None):
        """
        Inicializa o gerenciador.
        
        Args:
            db_session: Sessão do banco de dados
        """
        self.db = db_session
        self._config_cache: Dict[str, TenantConfig] = {}
        self._usage_cache: Dict[str, Dict[str, int]] = {}
    
    # =========================================================================
    # CONTEXT MANAGEMENT
    # =========================================================================
    
    def set_current_tenant(self, tenant_id: str, environment: str = None):
        """
        Define o tenant atual no contexto.
        
        Args:
            tenant_id: ID do tenant
            environment: Ambiente (opcional)
        """
        current_tenant.set(tenant_id)
        if environment:
            current_environment.set(environment)
        logger.debug(f"Tenant context set: {tenant_id} ({environment})")
    
    def get_current_tenant(self) -> Optional[str]:
        """Obtém ID do tenant atual."""
        return current_tenant.get()
    
    def get_current_environment(self) -> Optional[str]:
        """Obtém ambiente atual."""
        return current_environment.get()
    
    def clear_context(self):
        """Limpa o contexto de tenant."""
        current_tenant.set(None)
        current_environment.set(None)
    
    def require_tenant(self) -> str:
        """
        Obtém tenant atual ou levanta exceção.
        
        Returns:
            ID do tenant
            
        Raises:
            NoTenantContextError: Se não houver tenant no contexto
        """
        tenant_id = self.get_current_tenant()
        if not tenant_id:
            raise NoTenantContextError()
        return tenant_id
    
    # =========================================================================
    # CONFIG MANAGEMENT
    # =========================================================================
    
    async def get_tenant_config(self, tenant_id: str) -> TenantConfig:
        """
        Obtém configuração do tenant.
        
        Args:
            tenant_id: ID do tenant
            
        Returns:
            Configuração do tenant
            
        Raises:
            TenantNotFoundError: Se tenant não existir
        """
        # Verificar cache
        if tenant_id in self._config_cache:
            return self._config_cache[tenant_id]
        
        # Carregar do banco
        config = await self._load_tenant_config(tenant_id)
        
        if not config:
            raise TenantNotFoundError(tenant_id)
        
        # Cachear
        self._config_cache[tenant_id] = config
        
        return config
    
    async def get_current_config(self) -> TenantConfig:
        """
        Obtém configuração do tenant atual.
        
        Returns:
            Configuração do tenant
        """
        tenant_id = self.require_tenant()
        return await self.get_tenant_config(tenant_id)
    
    async def create_tenant(
        self,
        tenant_id: str,
        name: str,
        environment: TenantEnvironment = TenantEnvironment.PRODUCTION,
        tws_instance: str = "",
        limits: TenantLimits = None,
        features: Set[str] = None,
    ) -> TenantConfig:
        """
        Cria novo tenant.
        
        Args:
            tenant_id: ID único do tenant
            name: Nome do tenant
            environment: Ambiente
            tws_instance: Instância TWS associada
            limits: Limites customizados
            features: Features habilitadas
            
        Returns:
            Configuração do tenant criado
        """
        config = TenantConfig(
            tenant_id=tenant_id,
            name=name,
            environment=environment,
            tws_instance=tws_instance,
            limits=limits or TenantLimits(),
            features=features or {"semantic_cache", "kg_queries", "rag"},
        )
        
        # Persistir
        await self._save_tenant_config(config)
        
        # Cachear
        self._config_cache[tenant_id] = config
        
        logger.info(f"Tenant criado: {tenant_id} ({name})")
        
        return config
    
    async def update_tenant(
        self,
        tenant_id: str,
        **updates,
    ) -> TenantConfig:
        """
        Atualiza configuração do tenant.
        
        Args:
            tenant_id: ID do tenant
            **updates: Campos a atualizar
            
        Returns:
            Configuração atualizada
        """
        config = await self.get_tenant_config(tenant_id)
        
        # Aplicar updates
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_at = datetime.utcnow()
        
        # Persistir
        await self._save_tenant_config(config)
        
        # Atualizar cache
        self._config_cache[tenant_id] = config
        
        return config
    
    async def delete_tenant(self, tenant_id: str):
        """
        Remove tenant (soft delete - marca como expirado).
        
        Args:
            tenant_id: ID do tenant
        """
        await self.update_tenant(
            tenant_id,
            status=TenantStatus.EXPIRED,
            expires_at=datetime.utcnow(),
        )
        
        # Remover do cache
        self._config_cache.pop(tenant_id, None)
        
        logger.info(f"Tenant removido: {tenant_id}")
    
    # =========================================================================
    # KEY/PREFIX GENERATION
    # =========================================================================
    
    async def get_cache_key(self, key: str) -> str:
        """
        Gera chave de cache prefixada com tenant.
        
        Args:
            key: Chave original
            
        Returns:
            Chave com prefixo do tenant
        """
        config = await self.get_current_config()
        return f"{config.cache_prefix}:{key}"
    
    async def get_kg_table_name(self, base_table: str) -> str:
        """
        Gera nome de tabela do KG com schema do tenant.
        
        Args:
            base_table: Nome base da tabela
            
        Returns:
            Nome completo com schema
        """
        config = await self.get_current_config()
        return f"{config.kg_schema}.{base_table}"
    
    def get_cache_key_sync(self, key: str) -> str:
        """
        Versão síncrona para obter chave de cache.
        Usa tenant do contexto atual.
        """
        tenant_id = self.require_tenant()
        config = self._config_cache.get(tenant_id)
        
        if config:
            return f"{config.cache_prefix}:{key}"
        
        # Fallback com prefixo genérico
        return f"tenant:{tenant_id}:cache:{key}"
    
    # =========================================================================
    # LIMITS & USAGE
    # =========================================================================
    
    async def check_limit(
        self,
        limit_name: str,
        current_usage: int = None,
    ) -> bool:
        """
        Verifica se limite foi excedido.
        
        Args:
            limit_name: Nome do limite (ex: "cache_entries")
            current_usage: Uso atual (se não fornecido, obtém do cache)
            
        Returns:
            True se dentro do limite
            
        Raises:
            TenantLimitExceededError: Se limite excedido
        """
        config = await self.get_current_config()
        tenant_id = config.tenant_id
        
        # Obter limite máximo
        limit_attr = f"max_{limit_name}"
        max_value = getattr(config.limits, limit_attr, None)
        
        if max_value is None:
            return True  # Limite não definido
        
        # Obter uso atual
        if current_usage is None:
            current_usage = self._usage_cache.get(tenant_id, {}).get(limit_name, 0)
        
        if current_usage >= max_value:
            raise TenantLimitExceededError(
                tenant_id, limit_name, current_usage, max_value
            )
        
        return True
    
    async def increment_usage(self, metric: str, amount: int = 1):
        """
        Incrementa contador de uso.
        
        Args:
            metric: Nome da métrica
            amount: Quantidade a incrementar
        """
        tenant_id = self.require_tenant()
        
        if tenant_id not in self._usage_cache:
            self._usage_cache[tenant_id] = {}
        
        self._usage_cache[tenant_id][metric] = (
            self._usage_cache[tenant_id].get(metric, 0) + amount
        )
    
    async def get_usage(self, metric: str = None) -> Dict[str, int]:
        """
        Obtém métricas de uso do tenant.
        
        Args:
            metric: Métrica específica (opcional)
            
        Returns:
            Dicionário de métricas
        """
        tenant_id = self.require_tenant()
        usage = self._usage_cache.get(tenant_id, {})
        
        if metric:
            return {metric: usage.get(metric, 0)}
        
        return usage
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    async def validate_tenant(self, tenant_id: str) -> TenantConfig:
        """
        Valida tenant e retorna config se válido.
        
        Args:
            tenant_id: ID do tenant
            
        Returns:
            Configuração do tenant
            
        Raises:
            TenantNotFoundError: Se não existir
            TenantInactiveError: Se não estiver ativo
        """
        config = await self.get_tenant_config(tenant_id)
        
        if not config.is_active():
            raise TenantInactiveError(tenant_id, config.status.value)
        
        return config
    
    async def validate_feature(self, feature: str) -> bool:
        """
        Valida se feature está habilitada para tenant.
        
        Args:
            feature: Nome da feature
            
        Returns:
            True se habilitada
        """
        config = await self.get_current_config()
        return config.has_feature(feature)
    
    # =========================================================================
    # PERSISTENCE (implementar conforme banco utilizado)
    # =========================================================================
    
    async def _load_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """Carrega config do banco."""
        if not self.db:
            # Retornar config default para desenvolvimento
            return self._get_default_config(tenant_id)
        
        # TODO: Implementar query real
        return self._get_default_config(tenant_id)
    
    async def _save_tenant_config(self, config: TenantConfig):
        """Salva config no banco."""
        if not self.db:
            logger.debug(f"Config não persistida (sem DB): {config.tenant_id}")
            return
        
        # TODO: Implementar persistência real
        pass
    
    def _get_default_config(self, tenant_id: str) -> TenantConfig:
        """Retorna config default para desenvolvimento."""
        return TenantConfig(
            tenant_id=tenant_id,
            name=f"Tenant {tenant_id}",
            environment=TenantEnvironment.DEVELOPMENT,
            features={"semantic_cache", "kg_queries", "rag", "cross_encoder"},
        )
    
    # =========================================================================
    # LIST & SEARCH
    # =========================================================================
    
    async def list_tenants(
        self,
        status: TenantStatus = None,
        environment: TenantEnvironment = None,
        limit: int = 100,
    ) -> List[TenantConfig]:
        """
        Lista tenants com filtros opcionais.
        
        Args:
            status: Filtrar por status
            environment: Filtrar por ambiente
            limit: Limite de resultados
            
        Returns:
            Lista de configurações
        """
        # Retornar do cache para desenvolvimento
        tenants = list(self._config_cache.values())
        
        if status:
            tenants = [t for t in tenants if t.status == status]
        
        if environment:
            tenants = [t for t in tenants if t.environment == environment]
        
        return tenants[:limit]
    
    async def get_tenant_stats(self, tenant_id: str = None) -> Dict[str, Any]:
        """
        Obtém estatísticas do tenant.
        
        Args:
            tenant_id: ID do tenant (ou usa contexto atual)
            
        Returns:
            Estatísticas
        """
        if tenant_id is None:
            tenant_id = self.require_tenant()
        
        config = await self.get_tenant_config(tenant_id)
        usage = self._usage_cache.get(tenant_id, {})
        
        return {
            "tenant_id": tenant_id,
            "name": config.name,
            "environment": config.environment.value,
            "status": config.status.value,
            "is_active": config.is_active(),
            "limits": config.limits.to_dict(),
            "usage": usage,
            "features": list(config.features),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_tenant_manager: Optional[TenantManager] = None


def get_tenant_manager(db_session = None) -> TenantManager:
    """
    Obtém instância singleton do TenantManager.
    
    Args:
        db_session: Sessão do banco (opcional, só necessário na primeira chamada)
        
    Returns:
        TenantManager instance
    """
    global _tenant_manager
    
    if _tenant_manager is None:
        _tenant_manager = TenantManager(db_session)
    
    return _tenant_manager


def reset_tenant_manager():
    """Reseta o singleton (para testes)."""
    global _tenant_manager
    _tenant_manager = None
