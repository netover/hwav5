"""
Multi-tenant Cache - Isolamento de Cache por Tenant v5.4.0

Wrapper de cache que adiciona isolamento por tenant,
garantindo que dados de diferentes clientes/ambientes
não se misturem.

Versão: 5.4.0
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar

from resync.core.multi_tenant.tenant_manager import (
    TenantManager,
    get_tenant_manager,
    NoTenantContextError,
    TenantLimitExceededError,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class MultiTenantCache:
    """
    Cache com isolamento por tenant.
    
    Funcionalidades:
    - Prefixo automático por tenant
    - TTL específico por tenant
    - Limites de uso por tenant
    - Métricas segregadas
    """
    
    def __init__(
        self,
        base_cache,
        tenant_manager: TenantManager = None,
        enforce_tenant: bool = True,
    ):
        """
        Inicializa o cache multi-tenant.
        
        Args:
            base_cache: Cache subjacente (Redis, memory, etc)
            tenant_manager: Gerenciador de tenants
            enforce_tenant: Se True, exige contexto de tenant
        """
        self.cache = base_cache
        self.tenant_manager = tenant_manager or get_tenant_manager()
        self.enforce_tenant = enforce_tenant
        
        # Métricas por tenant
        self._metrics: Dict[str, Dict[str, int]] = {}
    
    # =========================================================================
    # KEY GENERATION
    # =========================================================================
    
    def _get_tenant_key(self, key: str) -> str:
        """
        Gera chave com prefixo do tenant.
        
        Args:
            key: Chave original
            
        Returns:
            Chave prefixada
        """
        tenant_id = self.tenant_manager.get_current_tenant()
        
        if not tenant_id:
            if self.enforce_tenant:
                raise NoTenantContextError()
            return key
        
        return self.tenant_manager.get_cache_key_sync(key)
    
    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Obtém valor do cache.
        
        Args:
            key: Chave
            
        Returns:
            Valor ou None
        """
        tenant_key = self._get_tenant_key(key)
        
        try:
            value = await self._cache_get(tenant_key)
            
            if value is not None:
                self._record_hit()
            else:
                self._record_miss()
            
            return value
            
        except Exception as e:
            logger.error(f"Erro ao obter do cache: {e}")
            self._record_miss()
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Armazena valor no cache.
        
        Args:
            key: Chave
            value: Valor
            ttl: TTL em segundos (usa default do tenant se não fornecido)
            metadata: Metadados adicionais
            
        Returns:
            True se sucesso
        """
        tenant_key = self._get_tenant_key(key)
        
        try:
            # Verificar limite
            await self._check_limits()
            
            # Obter TTL do tenant se não fornecido
            if ttl is None:
                ttl = await self._get_tenant_ttl()
            
            # Armazenar
            success = await self._cache_set(tenant_key, value, ttl)
            
            if success:
                self._record_set()
                await self.tenant_manager.increment_usage("cache_entries")
            
            return success
            
        except TenantLimitExceededError:
            logger.warning(f"Limite de cache excedido para tenant")
            return False
        except Exception as e:
            logger.error(f"Erro ao armazenar no cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Remove valor do cache.
        
        Args:
            key: Chave
            
        Returns:
            True se removido
        """
        tenant_key = self._get_tenant_key(key)
        
        try:
            success = await self._cache_delete(tenant_key)
            
            if success:
                self._record_delete()
            
            return success
            
        except Exception as e:
            logger.error(f"Erro ao remover do cache: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Verifica se chave existe.
        
        Args:
            key: Chave
            
        Returns:
            True se existe
        """
        tenant_key = self._get_tenant_key(key)
        return await self._cache_exists(tenant_key)
    
    async def extend_ttl(self, key: str, additional_seconds: int = 3600) -> bool:
        """
        Estende TTL de uma chave.
        
        Args:
            key: Chave
            additional_seconds: Segundos adicionais
            
        Returns:
            True se sucesso
        """
        tenant_key = self._get_tenant_key(key)
        return await self._cache_extend_ttl(tenant_key, additional_seconds)
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalida todas as chaves que correspondem ao padrão.
        
        Args:
            pattern: Padrão (ex: "job:*")
            
        Returns:
            Número de chaves removidas
        """
        # Prefixar pattern com tenant
        tenant_id = self.tenant_manager.get_current_tenant()
        if tenant_id:
            pattern = f"tenant:{tenant_id}:cache:{pattern}"
        
        return await self._cache_invalidate_pattern(pattern)
    
    async def clear_tenant_cache(self) -> int:
        """
        Limpa todo o cache do tenant atual.
        
        Returns:
            Número de chaves removidas
        """
        tenant_id = self.tenant_manager.require_tenant()
        pattern = f"tenant:{tenant_id}:cache:*"
        
        count = await self._cache_invalidate_pattern(pattern)
        
        # Reset métricas
        self._metrics[tenant_id] = {}
        
        logger.info(f"Cache do tenant {tenant_id} limpo: {count} entradas")
        
        return count
    
    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================
    
    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        """
        Obtém múltiplos valores.
        
        Args:
            keys: Lista de chaves
            
        Returns:
            Dicionário chave -> valor
        """
        tenant_keys = [self._get_tenant_key(k) for k in keys]
        
        result = {}
        for original_key, tenant_key in zip(keys, tenant_keys):
            value = await self._cache_get(tenant_key)
            if value is not None:
                result[original_key] = value
                self._record_hit()
            else:
                self._record_miss()
        
        return result
    
    async def mset(
        self,
        items: Dict[str, Any],
        ttl: int = None,
    ) -> int:
        """
        Armazena múltiplos valores.
        
        Args:
            items: Dicionário chave -> valor
            ttl: TTL em segundos
            
        Returns:
            Número de itens armazenados
        """
        if ttl is None:
            ttl = await self._get_tenant_ttl()
        
        count = 0
        for key, value in items.items():
            if await self.set(key, value, ttl):
                count += 1
        
        return count
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    def _record_hit(self):
        """Registra cache hit."""
        tenant_id = self.tenant_manager.get_current_tenant()
        if tenant_id:
            if tenant_id not in self._metrics:
                self._metrics[tenant_id] = {}
            self._metrics[tenant_id]["hits"] = (
                self._metrics[tenant_id].get("hits", 0) + 1
            )
    
    def _record_miss(self):
        """Registra cache miss."""
        tenant_id = self.tenant_manager.get_current_tenant()
        if tenant_id:
            if tenant_id not in self._metrics:
                self._metrics[tenant_id] = {}
            self._metrics[tenant_id]["misses"] = (
                self._metrics[tenant_id].get("misses", 0) + 1
            )
    
    def _record_set(self):
        """Registra cache set."""
        tenant_id = self.tenant_manager.get_current_tenant()
        if tenant_id:
            if tenant_id not in self._metrics:
                self._metrics[tenant_id] = {}
            self._metrics[tenant_id]["sets"] = (
                self._metrics[tenant_id].get("sets", 0) + 1
            )
    
    def _record_delete(self):
        """Registra cache delete."""
        tenant_id = self.tenant_manager.get_current_tenant()
        if tenant_id:
            if tenant_id not in self._metrics:
                self._metrics[tenant_id] = {}
            self._metrics[tenant_id]["deletes"] = (
                self._metrics[tenant_id].get("deletes", 0) + 1
            )
    
    def get_metrics(self, tenant_id: str = None) -> Dict[str, Any]:
        """
        Obtém métricas do cache.
        
        Args:
            tenant_id: ID do tenant (usa contexto se não fornecido)
            
        Returns:
            Métricas do cache
        """
        if tenant_id is None:
            tenant_id = self.tenant_manager.get_current_tenant()
        
        if not tenant_id:
            return {}
        
        metrics = self._metrics.get(tenant_id, {})
        hits = metrics.get("hits", 0)
        misses = metrics.get("misses", 0)
        total = hits + misses
        
        return {
            "tenant_id": tenant_id,
            "hits": hits,
            "misses": misses,
            "sets": metrics.get("sets", 0),
            "deletes": metrics.get("deletes", 0),
            "hit_rate": hits / total if total > 0 else 0.0,
            "total_requests": total,
        }
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtém métricas de todos os tenants.
        
        Returns:
            Dicionário tenant_id -> métricas
        """
        return {
            tenant_id: self.get_metrics(tenant_id)
            for tenant_id in self._metrics
        }
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    async def _check_limits(self):
        """Verifica limites do tenant."""
        await self.tenant_manager.check_limit("cache_entries")
    
    async def _get_tenant_ttl(self) -> int:
        """Obtém TTL default do tenant."""
        try:
            config = await self.tenant_manager.get_current_config()
            return config.limits.cache_ttl_hours * 3600
        except Exception:
            return 86400  # 24 horas default
    
    # =========================================================================
    # CACHE BACKEND METHODS (override conforme implementação)
    # =========================================================================
    
    async def _cache_get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache subjacente."""
        if hasattr(self.cache, 'get'):
            if hasattr(self.cache.get, '__await__'):
                return await self.cache.get(key)
            return self.cache.get(key)
        return None
    
    async def _cache_set(self, key: str, value: Any, ttl: int) -> bool:
        """Armazena valor no cache subjacente."""
        if hasattr(self.cache, 'set'):
            if hasattr(self.cache.set, '__await__'):
                return await self.cache.set(key, value, ttl=ttl)
            return self.cache.set(key, value, ttl=ttl)
        return False
    
    async def _cache_delete(self, key: str) -> bool:
        """Remove valor do cache subjacente."""
        if hasattr(self.cache, 'delete'):
            if hasattr(self.cache.delete, '__await__'):
                return await self.cache.delete(key)
            return self.cache.delete(key)
        return False
    
    async def _cache_exists(self, key: str) -> bool:
        """Verifica existência no cache subjacente."""
        if hasattr(self.cache, 'exists'):
            if hasattr(self.cache.exists, '__await__'):
                return await self.cache.exists(key)
            return self.cache.exists(key)
        return False
    
    async def _cache_extend_ttl(self, key: str, additional_seconds: int) -> bool:
        """Estende TTL no cache subjacente."""
        if hasattr(self.cache, 'extend_ttl'):
            if hasattr(self.cache.extend_ttl, '__await__'):
                return await self.cache.extend_ttl(key, additional_seconds)
            return self.cache.extend_ttl(key, additional_seconds)
        return False
    
    async def _cache_invalidate_pattern(self, pattern: str) -> int:
        """Invalida padrão no cache subjacente."""
        if hasattr(self.cache, 'invalidate_pattern'):
            if hasattr(self.cache.invalidate_pattern, '__await__'):
                return await self.cache.invalidate_pattern(pattern)
            return self.cache.invalidate_pattern(pattern)
        return 0


# =============================================================================
# IN-MEMORY IMPLEMENTATION (para desenvolvimento/testes)
# =============================================================================


class InMemoryMultiTenantCache(MultiTenantCache):
    """
    Implementação em memória do cache multi-tenant.
    
    Útil para desenvolvimento e testes.
    """
    
    def __init__(self, tenant_manager: TenantManager = None):
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._expiry: Dict[str, datetime] = {}
        
        # Criar cache fake
        class FakeCache:
            pass
        
        super().__init__(
            base_cache=FakeCache(),
            tenant_manager=tenant_manager,
            enforce_tenant=False,
        )
    
    async def _cache_get(self, key: str) -> Optional[Any]:
        # Verificar expiração
        if key in self._expiry:
            if datetime.utcnow() > self._expiry[key]:
                del self._storage[key]
                del self._expiry[key]
                return None
        
        return self._storage.get(key)
    
    async def _cache_set(self, key: str, value: Any, ttl: int) -> bool:
        self._storage[key] = value
        if ttl:
            from datetime import timedelta
            self._expiry[key] = datetime.utcnow() + timedelta(seconds=ttl)
        return True
    
    async def _cache_delete(self, key: str) -> bool:
        if key in self._storage:
            del self._storage[key]
            self._expiry.pop(key, None)
            return True
        return False
    
    async def _cache_exists(self, key: str) -> bool:
        if key not in self._storage:
            return False
        
        # Verificar expiração
        if key in self._expiry and datetime.utcnow() > self._expiry[key]:
            del self._storage[key]
            del self._expiry[key]
            return False
        
        return True
    
    async def _cache_invalidate_pattern(self, pattern: str) -> int:
        import fnmatch
        
        keys_to_delete = [
            k for k in self._storage.keys()
            if fnmatch.fnmatch(k, pattern)
        ]
        
        for key in keys_to_delete:
            del self._storage[key]
            self._expiry.pop(key, None)
        
        return len(keys_to_delete)
    
    def get_storage_size(self) -> int:
        """Retorna número de itens armazenados."""
        return len(self._storage)
    
    def clear_all(self):
        """Limpa todo o cache (para testes)."""
        self._storage.clear()
        self._expiry.clear()
        self._metrics.clear()
