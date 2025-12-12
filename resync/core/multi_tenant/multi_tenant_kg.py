"""
Multi-tenant Knowledge Graph Service v5.4.0

Serviço de Knowledge Graph com isolamento por tenant/ambiente.
Cada tenant tem seu próprio schema/namespace no KG.

Funcionalidades:
- Schema separado por tenant
- Queries isoladas
- Expansão automática por tenant
- Métricas segregadas

Versão: 5.4.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from resync.core.multi_tenant.tenant_manager import (
    TenantManager,
    TenantConfig,
    get_tenant_manager,
    NoTenantContextError,
)
from resync.core.knowledge_graph.tws_relations import (
    TWSRelationType,
    TWSNodeType,
    TWSNode,
    TWSRelation,
    TWSQueryPatterns,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class MultiTenantKGConfig:
    """Configuração do KG multi-tenant."""
    
    # Prefixo de schema padrão
    schema_prefix: str = "kg_"
    
    # Tabelas base
    nodes_table: str = "nodes"
    relations_table: str = "relations"
    
    # Limites
    max_nodes_per_tenant: int = 50000
    max_relations_per_tenant: int = 100000
    
    # Cache
    enable_query_cache: bool = True
    cache_ttl_seconds: int = 300


# =============================================================================
# MULTI-TENANT KG SERVICE
# =============================================================================


class MultiTenantKGService:
    """
    Serviço de Knowledge Graph com isolamento por tenant.
    
    Cada tenant tem:
    - Schema próprio no PostgreSQL
    - Tabelas isoladas de nós e relações
    - Queries automaticamente filtradas
    - Métricas segregadas
    """
    
    def __init__(
        self,
        db_session = None,
        tenant_manager: TenantManager = None,
        config: MultiTenantKGConfig = None,
    ):
        """
        Inicializa o serviço.
        
        Args:
            db_session: Sessão do banco de dados
            tenant_manager: Gerenciador de tenants
            config: Configuração do KG
        """
        self.db = db_session
        self.tenant_manager = tenant_manager or get_tenant_manager()
        self.config = config or MultiTenantKGConfig()
        
        # Cache de queries
        self._query_cache: Dict[str, Dict[str, Any]] = {}
        
        # Métricas por tenant
        self._metrics: Dict[str, Dict[str, int]] = {}
    
    # =========================================================================
    # SCHEMA MANAGEMENT
    # =========================================================================
    
    def get_tenant_schema(self, tenant_id: str = None) -> str:
        """
        Obtém nome do schema para o tenant.
        
        Args:
            tenant_id: ID do tenant (usa contexto se não fornecido)
            
        Returns:
            Nome do schema
        """
        if tenant_id is None:
            tenant_id = self.tenant_manager.require_tenant()
        
        return f"{self.config.schema_prefix}{tenant_id}"
    
    def get_nodes_table(self, tenant_id: str = None) -> str:
        """Obtém nome completo da tabela de nós."""
        schema = self.get_tenant_schema(tenant_id)
        return f"{schema}.{self.config.nodes_table}"
    
    def get_relations_table(self, tenant_id: str = None) -> str:
        """Obtém nome completo da tabela de relações."""
        schema = self.get_tenant_schema(tenant_id)
        return f"{schema}.{self.config.relations_table}"
    
    async def ensure_tenant_schema(self, tenant_id: str = None):
        """
        Garante que schema do tenant existe.
        
        Args:
            tenant_id: ID do tenant
        """
        schema = self.get_tenant_schema(tenant_id)
        
        if not self.db:
            logger.debug(f"Schema {schema}: DB não disponível")
            return
        
        # Criar schema
        await self._execute_sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        
        # Criar tabela de nós
        nodes_table = f"{schema}.{self.config.nodes_table}"
        await self._execute_sql(f"""
            CREATE TABLE IF NOT EXISTS {nodes_table} (
                node_id VARCHAR(255) PRIMARY KEY,
                node_type VARCHAR(50) NOT NULL,
                name VARCHAR(255) NOT NULL,
                properties JSONB DEFAULT '{{}}',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Criar tabela de relações
        relations_table = f"{schema}.{self.config.relations_table}"
        await self._execute_sql(f"""
            CREATE TABLE IF NOT EXISTS {relations_table} (
                id SERIAL PRIMARY KEY,
                from_node VARCHAR(255) NOT NULL,
                to_node VARCHAR(255) NOT NULL,
                relation_type VARCHAR(50) NOT NULL,
                properties JSONB DEFAULT '{{}}',
                weight FLOAT DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(from_node, to_node, relation_type)
            )
        """)
        
        # Criar índices
        await self._execute_sql(f"""
            CREATE INDEX IF NOT EXISTS idx_{schema}_nodes_type 
            ON {nodes_table}(node_type)
        """)
        await self._execute_sql(f"""
            CREATE INDEX IF NOT EXISTS idx_{schema}_relations_from 
            ON {relations_table}(from_node)
        """)
        await self._execute_sql(f"""
            CREATE INDEX IF NOT EXISTS idx_{schema}_relations_to 
            ON {relations_table}(to_node)
        """)
        await self._execute_sql(f"""
            CREATE INDEX IF NOT EXISTS idx_{schema}_relations_type 
            ON {relations_table}(relation_type)
        """)
        
        logger.info(f"Schema {schema} criado/verificado")
    
    async def drop_tenant_schema(self, tenant_id: str):
        """
        Remove schema do tenant (DANGER!).
        
        Args:
            tenant_id: ID do tenant
        """
        schema = self.get_tenant_schema(tenant_id)
        
        if self.db:
            await self._execute_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        
        # Limpar caches
        self._query_cache.pop(tenant_id, None)
        self._metrics.pop(tenant_id, None)
        
        logger.warning(f"Schema {schema} removido")
    
    # =========================================================================
    # NODE OPERATIONS
    # =========================================================================
    
    async def create_node(self, node: TWSNode) -> bool:
        """
        Cria nó no KG.
        
        Args:
            node: Nó a criar
            
        Returns:
            True se criado
        """
        tenant_id = self.tenant_manager.require_tenant()
        table = self.get_nodes_table()
        
        # Verificar limite
        count = await self.get_node_count()
        if count >= self.config.max_nodes_per_tenant:
            logger.warning(f"Limite de nós excedido para tenant {tenant_id}")
            return False
        
        try:
            import json
            props_json = json.dumps(node.properties)
            
            await self._execute_sql(f"""
                INSERT INTO {table} (node_id, node_type, name, properties)
                VALUES ('{node.node_id}', '{node.node_type.value}', 
                        '{node.name}', '{props_json}'::jsonb)
                ON CONFLICT (node_id) DO UPDATE 
                SET properties = EXCLUDED.properties,
                    updated_at = NOW()
            """)
            
            self._record_metric("nodes_created")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar nó: {e}")
            return False
    
    async def get_node(self, node_id: str) -> Optional[TWSNode]:
        """
        Obtém nó por ID.
        
        Args:
            node_id: ID do nó
            
        Returns:
            Nó ou None
        """
        table = self.get_nodes_table()
        
        result = await self._query_sql(f"""
            SELECT node_id, node_type, name, properties, created_at, updated_at
            FROM {table}
            WHERE node_id = '{node_id}'
        """)
        
        if result:
            row = result[0]
            return TWSNode(
                node_id=row["node_id"],
                node_type=TWSNodeType(row["node_type"]),
                name=row["name"],
                properties=row.get("properties", {}),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
                tenant_id=self.tenant_manager.get_current_tenant(),
            )
        
        return None
    
    async def delete_node(self, node_id: str) -> bool:
        """
        Remove nó e suas relações.
        
        Args:
            node_id: ID do nó
            
        Returns:
            True se removido
        """
        nodes_table = self.get_nodes_table()
        relations_table = self.get_relations_table()
        
        try:
            # Remover relações
            await self._execute_sql(f"""
                DELETE FROM {relations_table}
                WHERE from_node = '{node_id}' OR to_node = '{node_id}'
            """)
            
            # Remover nó
            await self._execute_sql(f"""
                DELETE FROM {nodes_table}
                WHERE node_id = '{node_id}'
            """)
            
            self._record_metric("nodes_deleted")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover nó: {e}")
            return False
    
    async def get_node_count(self) -> int:
        """Obtém contagem de nós do tenant."""
        table = self.get_nodes_table()
        
        result = await self._query_sql(f"SELECT COUNT(*) as count FROM {table}")
        return result[0]["count"] if result else 0
    
    # =========================================================================
    # RELATION OPERATIONS
    # =========================================================================
    
    async def create_relation(self, relation: TWSRelation) -> bool:
        """
        Cria relação no KG.
        
        Args:
            relation: Relação a criar
            
        Returns:
            True se criada
        """
        tenant_id = self.tenant_manager.require_tenant()
        table = self.get_relations_table()
        
        # Verificar limite
        count = await self.get_relation_count()
        if count >= self.config.max_relations_per_tenant:
            logger.warning(f"Limite de relações excedido para tenant {tenant_id}")
            return False
        
        try:
            import json
            props_json = json.dumps(relation.properties)
            
            await self._execute_sql(f"""
                INSERT INTO {table} (from_node, to_node, relation_type, properties, weight)
                VALUES ('{relation.from_node}', '{relation.to_node}', 
                        '{relation.relation_type.value}', '{props_json}'::jsonb, 
                        {relation.weight})
                ON CONFLICT (from_node, to_node, relation_type) DO UPDATE 
                SET properties = EXCLUDED.properties,
                    weight = EXCLUDED.weight
            """)
            
            self._record_metric("relations_created")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar relação: {e}")
            return False
    
    async def get_relations(
        self,
        from_node: str = None,
        to_node: str = None,
        relation_type: TWSRelationType = None,
    ) -> List[TWSRelation]:
        """
        Obtém relações com filtros.
        
        Args:
            from_node: Filtrar por nó de origem
            to_node: Filtrar por nó de destino
            relation_type: Filtrar por tipo
            
        Returns:
            Lista de relações
        """
        table = self.get_relations_table()
        
        conditions = []
        if from_node:
            conditions.append(f"from_node = '{from_node}'")
        if to_node:
            conditions.append(f"to_node = '{to_node}'")
        if relation_type:
            conditions.append(f"relation_type = '{relation_type.value}'")
        
        where = " AND ".join(conditions) if conditions else "1=1"
        
        result = await self._query_sql(f"""
            SELECT from_node, to_node, relation_type, properties, weight, created_at
            FROM {table}
            WHERE {where}
            ORDER BY created_at DESC
        """)
        
        tenant_id = self.tenant_manager.get_current_tenant()
        
        return [
            TWSRelation(
                from_node=row["from_node"],
                to_node=row["to_node"],
                relation_type=TWSRelationType(row["relation_type"]),
                properties=row.get("properties", {}),
                weight=row.get("weight", 1.0),
                created_at=row.get("created_at"),
                tenant_id=tenant_id,
            )
            for row in (result or [])
        ]
    
    async def get_relation_count(self) -> int:
        """Obtém contagem de relações do tenant."""
        table = self.get_relations_table()
        
        result = await self._query_sql(f"SELECT COUNT(*) as count FROM {table}")
        return result[0]["count"] if result else 0
    
    # =========================================================================
    # GRAPH QUERIES
    # =========================================================================
    
    async def get_dependencies(
        self,
        job_name: str,
        max_depth: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Obtém cadeia de dependências de um job.
        
        Args:
            job_name: Nome do job
            max_depth: Profundidade máxima
            
        Returns:
            Lista de dependências com profundidade
        """
        tenant_id = self.tenant_manager.get_current_tenant()
        cache_key = f"deps:{job_name}:{max_depth}"
        
        # Verificar cache
        if self.config.enable_query_cache:
            cached = self._get_cached_query(tenant_id, cache_key)
            if cached:
                return cached
        
        # Executar query
        table = self.get_relations_table()
        
        result = await self._query_sql(f"""
            WITH RECURSIVE deps AS (
                SELECT from_node, to_node, relation_type, 1 as depth
                FROM {table}
                WHERE to_node = '{job_name}'
                AND relation_type IN ('depends_on', 'follows', 'needs')
                
                UNION ALL
                
                SELECT r.from_node, r.to_node, r.relation_type, d.depth + 1
                FROM {table} r
                JOIN deps d ON r.to_node = d.from_node
                WHERE d.depth < {max_depth}
                AND r.relation_type IN ('depends_on', 'follows', 'needs')
            )
            SELECT DISTINCT from_node, to_node, relation_type, depth
            FROM deps
            ORDER BY depth
        """)
        
        # Cachear
        if self.config.enable_query_cache:
            self._cache_query(tenant_id, cache_key, result)
        
        self._record_metric("queries_executed")
        return result or []
    
    async def get_impact(
        self,
        job_name: str,
        max_depth: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Obtém jobs impactados se job falhar.
        
        Args:
            job_name: Nome do job
            max_depth: Profundidade máxima
            
        Returns:
            Lista de jobs afetados
        """
        tenant_id = self.tenant_manager.get_current_tenant()
        cache_key = f"impact:{job_name}:{max_depth}"
        
        # Verificar cache
        if self.config.enable_query_cache:
            cached = self._get_cached_query(tenant_id, cache_key)
            if cached:
                return cached
        
        table = self.get_relations_table()
        
        result = await self._query_sql(f"""
            WITH RECURSIVE impact AS (
                SELECT to_node as affected_job, 1 as distance
                FROM {table}
                WHERE from_node = '{job_name}'
                AND relation_type IN ('triggers', 'predecessor_of')
                
                UNION ALL
                
                SELECT r.to_node, i.distance + 1
                FROM {table} r
                JOIN impact i ON r.from_node = i.affected_job
                WHERE i.distance < {max_depth}
            )
            SELECT DISTINCT affected_job, distance
            FROM impact
            ORDER BY distance
        """)
        
        # Cachear
        if self.config.enable_query_cache:
            self._cache_query(tenant_id, cache_key, result)
        
        self._record_metric("queries_executed")
        return result or []
    
    async def get_resource_conflicts(
        self,
        job_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Obtém jobs que compartilham recursos exclusivos.
        
        Args:
            job_name: Nome do job
            
        Returns:
            Lista de conflitos potenciais
        """
        table = self.get_relations_table()
        
        result = await self._query_sql(f"""
            SELECT r2.from_node as conflicting_job,
                   r1.to_node as shared_resource,
                   r1.properties->>'exclusive' as is_exclusive
            FROM {table} r1
            JOIN {table} r2 ON r1.to_node = r2.to_node
            WHERE r1.from_node = '{job_name}'
            AND r2.from_node != '{job_name}'
            AND r1.relation_type = 'allocates'
            AND r2.relation_type = 'allocates'
        """)
        
        self._record_metric("queries_executed")
        return result or []
    
    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================
    
    async def bulk_create_nodes(self, nodes: List[TWSNode]) -> int:
        """
        Cria múltiplos nós.
        
        Args:
            nodes: Lista de nós
            
        Returns:
            Número de nós criados
        """
        count = 0
        for node in nodes:
            if await self.create_node(node):
                count += 1
        return count
    
    async def bulk_create_relations(self, relations: List[TWSRelation]) -> int:
        """
        Cria múltiplas relações.
        
        Args:
            relations: Lista de relações
            
        Returns:
            Número de relações criadas
        """
        count = 0
        for relation in relations:
            if await self.create_relation(relation):
                count += 1
        return count
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    def _record_metric(self, metric: str):
        """Registra métrica."""
        tenant_id = self.tenant_manager.get_current_tenant()
        if tenant_id:
            if tenant_id not in self._metrics:
                self._metrics[tenant_id] = {}
            self._metrics[tenant_id][metric] = (
                self._metrics[tenant_id].get(metric, 0) + 1
            )
    
    def get_metrics(self, tenant_id: str = None) -> Dict[str, Any]:
        """Obtém métricas do tenant."""
        if tenant_id is None:
            tenant_id = self.tenant_manager.get_current_tenant()
        
        return self._metrics.get(tenant_id, {})
    
    # =========================================================================
    # CACHE
    # =========================================================================
    
    def _get_cached_query(
        self,
        tenant_id: str,
        cache_key: str,
    ) -> Optional[Any]:
        """Obtém resultado cacheado."""
        if tenant_id not in self._query_cache:
            return None
        
        cached = self._query_cache[tenant_id].get(cache_key)
        if cached:
            # Verificar TTL
            if cached.get("expires_at", datetime.min) > datetime.utcnow():
                return cached.get("result")
            else:
                del self._query_cache[tenant_id][cache_key]
        
        return None
    
    def _cache_query(
        self,
        tenant_id: str,
        cache_key: str,
        result: Any,
    ):
        """Cacheia resultado de query."""
        if tenant_id not in self._query_cache:
            self._query_cache[tenant_id] = {}
        
        from datetime import timedelta
        self._query_cache[tenant_id][cache_key] = {
            "result": result,
            "expires_at": datetime.utcnow() + timedelta(
                seconds=self.config.cache_ttl_seconds
            ),
        }
    
    def clear_cache(self, tenant_id: str = None):
        """Limpa cache de queries."""
        if tenant_id:
            self._query_cache.pop(tenant_id, None)
        else:
            self._query_cache.clear()
    
    # =========================================================================
    # SQL HELPERS
    # =========================================================================
    
    async def _execute_sql(self, sql: str):
        """Executa SQL."""
        if not self.db:
            logger.debug(f"SQL não executado (sem DB): {sql[:100]}...")
            return
        
        # Implementar conforme ORM utilizado
        pass
    
    async def _query_sql(self, sql: str) -> Optional[List[Dict]]:
        """Executa query SQL."""
        if not self.db:
            logger.debug(f"Query não executada (sem DB): {sql[:100]}...")
            return []
        
        # Implementar conforme ORM utilizado
        return []
    
    # =========================================================================
    # STATS
    # =========================================================================
    
    async def get_stats(self, tenant_id: str = None) -> Dict[str, Any]:
        """
        Obtém estatísticas do KG para o tenant.
        
        Args:
            tenant_id: ID do tenant
            
        Returns:
            Estatísticas
        """
        if tenant_id is None:
            tenant_id = self.tenant_manager.get_current_tenant()
        
        # Temporariamente setar contexto se necessário
        original_tenant = self.tenant_manager.get_current_tenant()
        if tenant_id and tenant_id != original_tenant:
            self.tenant_manager.set_current_tenant(tenant_id)
        
        try:
            node_count = await self.get_node_count()
            relation_count = await self.get_relation_count()
            
            return {
                "tenant_id": tenant_id,
                "schema": self.get_tenant_schema(tenant_id),
                "node_count": node_count,
                "relation_count": relation_count,
                "limits": {
                    "max_nodes": self.config.max_nodes_per_tenant,
                    "max_relations": self.config.max_relations_per_tenant,
                },
                "usage_percent": {
                    "nodes": (node_count / self.config.max_nodes_per_tenant) * 100,
                    "relations": (relation_count / self.config.max_relations_per_tenant) * 100,
                },
                "metrics": self.get_metrics(tenant_id),
            }
        finally:
            if original_tenant:
                self.tenant_manager.set_current_tenant(original_tenant)


# =============================================================================
# SINGLETON
# =============================================================================

_kg_service: Optional[MultiTenantKGService] = None


def get_multi_tenant_kg_service(
    db_session = None,
    tenant_manager: TenantManager = None,
) -> MultiTenantKGService:
    """Obtém instância singleton do serviço KG."""
    global _kg_service
    
    if _kg_service is None:
        _kg_service = MultiTenantKGService(
            db_session=db_session,
            tenant_manager=tenant_manager,
        )
    
    return _kg_service
