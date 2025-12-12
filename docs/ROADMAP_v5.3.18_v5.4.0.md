# Resync Roadmap: v5.3.18 → v5.4.0

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ROADMAP RESYNC                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  v5.3.17 (Atual)     v5.3.18 (Curto Prazo)      v5.4.0 (Médio Prazo)        │
│  ──────────────      ───────────────────        ─────────────────────        │
│  ✅ Semantic Cache   🔧 Syntax Fixes            🎯 Fine-tuned Embeddings     │
│  ✅ Cross-Encoder    🔧 200+ Intent Examples    🎯 KG Expansion              │
│  ✅ TWS Validators   🔧 Cache Warming           🎯 Feedback Loop             │
│  ✅ Embedding Router 🔧 Metrics Dashboard       🎯 Multi-tenant              │
│                                                                              │
│  Timeline: ──────────┬───────────────────┬─────────────────────────────────  │
│            Hoje      │   +2 semanas      │        +6 semanas                 │
│                      │                   │                                   │
└──────────────────────┴───────────────────┴───────────────────────────────────┘
```

---

## 📅 v5.3.18 - Curto Prazo (2 semanas)

### Fase 1: Correções de Sintaxe (Dia 1-2)

#### 1.1 Correção do `common_error_handlers.py`

**Problema Identificado:**
```python
# Linha 172 - await fora de função async
await asyncio.sleep(current_delay)  # ❌ ERRO
```

**Solução:**
```python
# Opção A: Tornar a função async
async def retry_with_backoff(...):
    ...
    await asyncio.sleep(current_delay)  # ✅

# Opção B: Usar versão síncrona
import time
time.sleep(current_delay)  # ✅ Para contexto síncrono
```

**Arquivos a Verificar:**
| Arquivo | Ação |
|---------|------|
| `resync/core/utils/common_error_handlers.py` | Corrigir await |
| `resync/core/utils/json_parser.py` | Verificar imports |
| `resync/core/ia_auditor.py` | Verificar dependências |

**Comando de Validação:**
```bash
# Verificar todos os arquivos Python
find resync/ -name "*.py" -exec python -m py_compile {} \; 2>&1 | grep -v "^$"

# Verificar com AST
python -c "import ast; import pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('resync').rglob('*.py')]"
```

---

### Fase 2: Expansão de Exemplos de Intent (Dia 3-5)

#### 2.1 Análise Atual

```
Intents Atuais: 14
Exemplos Atuais: 107
Média por Intent: 7.6 exemplos
Target: 200+ exemplos (14+ por intent)
```

#### 2.2 Estrutura de Novos Exemplos

```python
# resync/core/embedding_router.py - INTENT_EXAMPLES expansion

INTENT_EXAMPLES_EXPANDED = {
    RouterIntent.DEPENDENCY_CHAIN: [
        # Português (existentes + novos)
        "quais são as dependências do job X",
        "mostre a cadeia de dependências",
        "lista predecessores do job",
        "quais jobs rodam antes de X",
        "dependências upstream do job",
        "jobs que precisam terminar antes",
        "qual a árvore de dependências",
        "predecessores diretos e indiretos",
        "cadeia completa de jobs",
        "fluxo de execução antes do job",
        # English
        "show job dependencies",
        "what runs before this job",
        "predecessor jobs list",
        "upstream dependencies",
        "job execution chain",
    ],
    
    RouterIntent.IMPACT_ANALYSIS: [
        # Português
        "qual o impacto se o job falhar",
        "quantos jobs serão afetados",
        "análise de impacto do job",
        "jobs dependentes downstream",
        "cascata de falha do job",
        "efeito dominó se parar",
        "jobs que vão atrasar",
        "impacto no schedule",
        "consequências da falha",
        "análise de risco do job",
        # English
        "impact if job fails",
        "downstream affected jobs",
        "failure cascade analysis",
        "risk assessment for job",
        "what breaks if this fails",
    ],
    
    RouterIntent.RESOURCE_CONFLICT: [
        # Português
        "conflito de recursos",
        "jobs usando mesmo recurso",
        "contenção de recursos",
        "recursos exclusivos em uso",
        "deadlock de recursos",
        "recursos compartilhados",
        "jobs competindo por recurso",
        "alocação de recursos",
        "recurso bloqueado por job",
        "liberação de recursos",
        # English
        "resource conflict detection",
        "shared resource contention",
        "exclusive resource lock",
        "resource allocation issues",
        "jobs competing for resource",
    ],
    
    RouterIntent.CRITICAL_JOBS: [
        # Português
        "jobs críticos do dia",
        "jobs prioritários",
        "jobs que não podem falhar",
        "SLA críticos",
        "jobs de alta prioridade",
        "processos essenciais",
        "jobs mandatórios",
        "batch crítico",
        "jobs com deadline",
        "processos regulatórios",
        # English
        "critical jobs today",
        "high priority jobs",
        "SLA critical processes",
        "mandatory batch jobs",
        "deadline sensitive jobs",
    ],
    
    RouterIntent.JOB_LINEAGE: [
        # Português
        "linhagem do job",
        "histórico de execuções",
        "evolução do job",
        "versões anteriores",
        "mudanças no job",
        "quem criou o job",
        "audit trail do job",
        "modificações recentes",
        "origem do job",
        "rastreabilidade",
        # English
        "job lineage",
        "execution history",
        "job audit trail",
        "who created this job",
        "job change history",
    ],
    
    RouterIntent.TROUBLESHOOTING: [
        # Português
        "como resolver erro X",
        "job falhou, o que fazer",
        "debug do job",
        "investigar falha",
        "análise de erro",
        "por que o job falhou",
        "solução para RC 12",
        "corrigir abend",
        "recuperar job",
        "restart após falha",
        "job preso, como resolver",
        "timeout do job",
        "job lento, como otimizar",
        "erro de conexão TWS",
        "problema de permissão",
        # English
        "how to fix job error",
        "job failed what to do",
        "debug job failure",
        "troubleshoot RC code",
        "fix abend job",
    ],
    
    RouterIntent.ERROR_LOOKUP: [
        # Português
        "o que significa RC 8",
        "código de erro 12",
        "traduzir erro TWS",
        "significado do abend",
        "erro AWKR0001",
        "código de retorno",
        "mensagem de erro",
        "catálogo de erros",
        "lista de RCs",
        "erro desconhecido",
        # English
        "what does RC 8 mean",
        "error code lookup",
        "TWS error message",
        "return code meaning",
        "abend code translation",
    ],
    
    RouterIntent.DOCUMENTATION: [
        # Português
        "documentação do TWS",
        "manual do job",
        "como usar ferramenta X",
        "guia de referência",
        "tutorial TWS",
        "procedimento padrão",
        "boas práticas",
        "instruções de operação",
        "onde encontro informação",
        "referência técnica",
        # English
        "TWS documentation",
        "job manual",
        "how to use TWS",
        "reference guide",
        "best practices",
    ],
    
    RouterIntent.JOB_DETAILS: [
        # Português
        "status do job X",
        "detalhes do job",
        "informações do job",
        "quando rodou o job",
        "último run do job",
        "próxima execução",
        "parâmetros do job",
        "configuração do job",
        "owner do job",
        "workstation do job",
        "horário agendado",
        "duração média",
        "estatísticas do job",
        "RC do último run",
        "log do job",
        # English
        "job status",
        "job details",
        "when did job run",
        "next scheduled run",
        "job parameters",
    ],
    
    RouterIntent.ROOT_CAUSE: [
        # Português
        "causa raiz do problema",
        "por que falhou",
        "análise de causa",
        "investigação profunda",
        "origem do erro",
        "motivo da falha",
        "diagnóstico completo",
        "análise forense",
        "o que causou o abend",
        "fonte do problema",
        # English
        "root cause analysis",
        "why did it fail",
        "failure investigation",
        "problem diagnosis",
        "error origin",
    ],
}
```

#### 2.3 Script de Validação de Exemplos

```python
# scripts/validate_intent_examples.py

def validate_examples():
    """Valida qualidade dos exemplos de intent."""
    from resync.core.embedding_router import INTENT_EXAMPLES, RouterIntent
    
    stats = {
        "total_intents": len(RouterIntent),
        "intents_with_examples": 0,
        "total_examples": 0,
        "min_examples": float('inf'),
        "max_examples": 0,
        "duplicates": [],
    }
    
    all_examples = set()
    
    for intent, examples in INTENT_EXAMPLES.items():
        stats["intents_with_examples"] += 1
        stats["total_examples"] += len(examples)
        stats["min_examples"] = min(stats["min_examples"], len(examples))
        stats["max_examples"] = max(stats["max_examples"], len(examples))
        
        for ex in examples:
            if ex.lower() in all_examples:
                stats["duplicates"].append(ex)
            all_examples.add(ex.lower())
    
    stats["avg_examples"] = stats["total_examples"] / stats["intents_with_examples"]
    
    print(f"Total Intents: {stats['total_intents']}")
    print(f"Intents com Exemplos: {stats['intents_with_examples']}")
    print(f"Total de Exemplos: {stats['total_examples']}")
    print(f"Média por Intent: {stats['avg_examples']:.1f}")
    print(f"Min/Max: {stats['min_examples']}/{stats['max_examples']}")
    
    if stats["duplicates"]:
        print(f"⚠️  Duplicados: {stats['duplicates']}")
    
    # Validações
    assert stats["total_examples"] >= 200, f"Precisa de 200+ exemplos, tem {stats['total_examples']}"
    assert stats["min_examples"] >= 10, f"Cada intent precisa de 10+ exemplos"
    assert len(stats["duplicates"]) == 0, f"Remover duplicados: {stats['duplicates']}"
    
    print("✅ Validação passou!")

if __name__ == "__main__":
    validate_examples()
```

---

### Fase 3: Cache Warming (Dia 6-8)

#### 3.1 Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                    CACHE WARMING SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Query        │───▶│ Embedding    │───▶│ Semantic     │       │
│  │ Collector    │    │ Generator    │    │ Cache        │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                                       │                │
│         ▼                                       ▼                │
│  ┌──────────────┐                      ┌──────────────┐         │
│  │ Analytics    │                      │ Pre-computed │         │
│  │ (top queries)│                      │ Responses    │         │
│  └──────────────┘                      └──────────────┘         │
│                                                                  │
│  Fontes de Queries:                                              │
│  • Histórico de chat (últimos 30 dias)                          │
│  • Jobs críticos do TWS                                          │
│  • Erros frequentes                                              │
│  • Perguntas comuns documentadas                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.2 Implementação

```python
# resync/core/cache/cache_warmer.py

"""
Cache Warming Service para Semantic Cache.

Pré-popula o cache semântico com queries frequentes para
reduzir latência e aumentar hit rate desde o startup.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from resync.core.cache.semantic_cache import SemanticCache
from resync.core.embedding_router import EmbeddingRouter
from resync.core.unified_retrieval import UnifiedRetrievalService

logger = logging.getLogger(__name__)


@dataclass
class WarmingQuery:
    """Query para warming do cache."""
    query: str
    category: str
    priority: int  # 1=alta, 2=média, 3=baixa
    expected_intent: Optional[str] = None


class CacheWarmer:
    """
    Serviço de warming do cache semântico.
    
    Estratégias:
    1. Queries estáticas predefinidas (FAQ)
    2. Queries dinâmicas do histórico
    3. Queries baseadas em jobs críticos
    """
    
    # Queries estáticas mais comuns
    STATIC_QUERIES: List[WarmingQuery] = [
        # Job Status (alta prioridade)
        WarmingQuery("qual o status do job", "job_status", 1),
        WarmingQuery("job está rodando", "job_status", 1),
        WarmingQuery("último run do job", "job_status", 1),
        WarmingQuery("próxima execução", "job_status", 1),
        
        # Troubleshooting (alta prioridade)
        WarmingQuery("job falhou o que fazer", "troubleshooting", 1),
        WarmingQuery("como resolver RC 12", "troubleshooting", 1),
        WarmingQuery("job abendou", "troubleshooting", 1),
        WarmingQuery("erro de conexão TWS", "troubleshooting", 1),
        
        # Dependências (média prioridade)
        WarmingQuery("quais as dependências do job", "dependency", 2),
        WarmingQuery("jobs predecessores", "dependency", 2),
        WarmingQuery("cadeia de dependências", "dependency", 2),
        
        # Impacto (média prioridade)
        WarmingQuery("impacto se job falhar", "impact", 2),
        WarmingQuery("quantos jobs afetados", "impact", 2),
        
        # Documentação (baixa prioridade)
        WarmingQuery("documentação TWS", "documentation", 3),
        WarmingQuery("manual de operação", "documentation", 3),
        WarmingQuery("boas práticas", "documentation", 3),
        
        # Erros comuns (alta prioridade)
        WarmingQuery("o que significa RC 8", "error", 1),
        WarmingQuery("código de erro 12", "error", 1),
        WarmingQuery("AWKR0001", "error", 1),
    ]
    
    def __init__(
        self,
        cache: SemanticCache,
        retrieval_service: UnifiedRetrievalService,
        router: EmbeddingRouter,
        db_session = None,
    ):
        self.cache = cache
        self.retrieval = retrieval_service
        self.router = router
        self.db = db_session
        self._warming_in_progress = False
        self._stats = {
            "queries_warmed": 0,
            "errors": 0,
            "last_warm": None,
            "duration_seconds": 0,
        }
    
    async def warm_static_queries(self, priority: int = 3) -> int:
        """
        Aquece cache com queries estáticas.
        
        Args:
            priority: Máximo nível de prioridade a processar (1-3)
            
        Returns:
            Número de queries processadas
        """
        queries = [q for q in self.STATIC_QUERIES if q.priority <= priority]
        return await self._process_queries(queries)
    
    async def warm_from_history(
        self,
        days: int = 30,
        limit: int = 100,
    ) -> int:
        """
        Aquece cache com queries mais frequentes do histórico.
        
        Args:
            days: Período em dias para análise
            limit: Número máximo de queries
            
        Returns:
            Número de queries processadas
        """
        if not self.db:
            logger.warning("Database session não disponível para histórico")
            return 0
        
        # Query para obter queries mais frequentes
        # (assumindo tabela chat_messages existe)
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # TODO: Implementar query real ao banco
        # Por enquanto, retorna lista vazia
        historical_queries = []
        
        warming_queries = [
            WarmingQuery(q["content"], "historical", 2)
            for q in historical_queries
        ]
        
        return await self._process_queries(warming_queries[:limit])
    
    async def warm_critical_jobs(self) -> int:
        """
        Aquece cache com queries sobre jobs críticos.
        
        Gera queries automáticas para:
        - Status dos jobs críticos
        - Dependências
        - Impacto potencial
        
        Returns:
            Número de queries processadas
        """
        # TODO: Obter lista de jobs críticos do TWS
        critical_jobs = [
            "BATCH_DIARIO",
            "FECHAMENTO_MES",
            "BACKUP_NOTURNO",
            "ETL_PRINCIPAL",
            "REPORT_REGULATORIO",
        ]
        
        warming_queries = []
        for job in critical_jobs:
            warming_queries.extend([
                WarmingQuery(f"status do job {job}", "critical_job", 1),
                WarmingQuery(f"dependências do job {job}", "critical_job", 1),
                WarmingQuery(f"impacto se {job} falhar", "critical_job", 1),
            ])
        
        return await self._process_queries(warming_queries)
    
    async def _process_queries(self, queries: List[WarmingQuery]) -> int:
        """Processa lista de queries para warming."""
        processed = 0
        
        for wq in queries:
            try:
                # Verificar se já está no cache
                cached = await self.cache.get(wq.query)
                if cached:
                    logger.debug(f"Query já em cache: {wq.query[:50]}...")
                    continue
                
                # Classificar intent
                classification = await self.router.classify(wq.query)
                
                # Buscar resposta
                result = await self.retrieval.retrieve(
                    query=wq.query,
                    intent=classification.intent,
                )
                
                # Armazenar no cache
                if result.documents or result.graph_data:
                    await self.cache.set(
                        query=wq.query,
                        response={
                            "intent": classification.intent.value,
                            "confidence": classification.confidence,
                            "documents": [d.dict() for d in result.documents],
                            "graph_data": result.graph_data,
                        },
                        metadata={
                            "source": "cache_warmer",
                            "category": wq.category,
                            "priority": wq.priority,
                        }
                    )
                    processed += 1
                    self._stats["queries_warmed"] += 1
                
            except Exception as e:
                logger.error(f"Erro no warming de '{wq.query[:50]}': {e}")
                self._stats["errors"] += 1
        
        return processed
    
    async def full_warm(self) -> dict:
        """
        Executa warming completo do cache.
        
        Ordem de execução:
        1. Queries estáticas (prioridade alta)
        2. Jobs críticos
        3. Queries estáticas (todas)
        4. Histórico
        
        Returns:
            Estatísticas do warming
        """
        if self._warming_in_progress:
            return {"error": "Warming já em progresso"}
        
        self._warming_in_progress = True
        start_time = datetime.utcnow()
        
        try:
            results = {
                "static_high": await self.warm_static_queries(priority=1),
                "critical_jobs": await self.warm_critical_jobs(),
                "static_all": await self.warm_static_queries(priority=3),
                "historical": await self.warm_from_history(),
            }
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._stats["last_warm"] = start_time.isoformat()
            self._stats["duration_seconds"] = duration
            
            results["total"] = sum(results.values())
            results["duration_seconds"] = duration
            results["stats"] = self._stats.copy()
            
            logger.info(
                f"Cache warming completo: {results['total']} queries em {duration:.2f}s"
            )
            
            return results
            
        finally:
            self._warming_in_progress = False
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do warming."""
        return self._stats.copy()


# Endpoint para API
async def warm_cache_endpoint(
    priority: int = 1,
    include_history: bool = False,
) -> dict:
    """
    Endpoint para triggerar cache warming manualmente.
    
    Args:
        priority: Nível de prioridade máximo (1-3)
        include_history: Se deve incluir queries do histórico
    """
    # TODO: Injetar dependências corretamente
    warmer = CacheWarmer(
        cache=SemanticCache(),
        retrieval_service=UnifiedRetrievalService(),
        router=EmbeddingRouter(),
    )
    
    if include_history:
        return await warmer.full_warm()
    else:
        count = await warmer.warm_static_queries(priority=priority)
        count += await warmer.warm_critical_jobs()
        return {
            "queries_warmed": count,
            "stats": warmer.get_stats(),
        }
```

#### 3.3 Integração com Lifespan

```python
# resync/lifespan.py - Adicionar warming no startup

async def warm_cache_on_startup():
    """Executa cache warming no startup da aplicação."""
    from resync.core.cache.cache_warmer import CacheWarmer
    
    try:
        warmer = CacheWarmer(...)
        # Warming apenas queries de alta prioridade no startup
        # para não atrasar muito o boot
        result = await warmer.warm_static_queries(priority=1)
        logger.info(f"Cache warming inicial: {result} queries")
    except Exception as e:
        logger.warning(f"Cache warming falhou (não crítico): {e}")
```

---

### Fase 4: Dashboard de Métricas (Dia 9-14)

#### 4.1 Arquitetura do Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        METRICS DASHBOARD                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         CACHE METRICS                                   ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               ││
│  │  │ Hit Rate │  │ Entries  │  │ Memory   │  │ Latency  │               ││
│  │  │  67.3%   │  │  1,234   │  │ 45.2 MB  │  │ 12ms avg │               ││
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘               ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         ROUTER METRICS                                  ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               ││
│  │  │ Accuracy │  │ Fallback │  │ Avg Time │  │ Top Intent│               ││
│  │  │  89.2%   │  │  8.3%    │  │ 18ms     │  │job_details│               ││
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘               ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌────────────────────────────────┐  ┌────────────────────────────────────┐│
│  │      HIT RATE OVER TIME        │  │      INTENT DISTRIBUTION          ││
│  │  100%│    ___                  │  │  job_details    ████████░░  42%   ││
│  │   80%│___/   \___              │  │  troubleshoot   █████░░░░░  28%   ││
│  │   60%│           \__           │  │  dependency     ███░░░░░░░  15%   ││
│  │   40%│                         │  │  documentation  ██░░░░░░░░  10%   ││
│  │      └──────────────────────   │  │  other          █░░░░░░░░░   5%   ││
│  │        00:00  06:00  12:00     │  │                                   ││
│  └────────────────────────────────┘  └────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 4.2 Backend - API de Métricas

```python
# resync/fastapi_app/api/v1/routes/admin_metrics_dashboard.py

"""
Dashboard de Métricas em Tempo Real.

Endpoints para visualização de métricas de:
- Semantic Cache (hit rate, entries, memory)
- Embedding Router (accuracy, fallback rate)
- RAG Cross-Encoder (rerank stats)
- TWS Validators (validation counts)
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

router = APIRouter(prefix="/metrics-dashboard", tags=["Metrics Dashboard"])


class CacheMetrics(BaseModel):
    """Métricas do Semantic Cache."""
    hit_rate: float
    total_entries: int
    memory_mb: float
    avg_latency_ms: float
    hits_last_hour: int
    misses_last_hour: int


class RouterMetrics(BaseModel):
    """Métricas do Embedding Router."""
    accuracy: float
    fallback_rate: float
    avg_classification_ms: float
    top_intents: dict[str, int]
    low_confidence_count: int


class RerankerMetrics(BaseModel):
    """Métricas do Cross-Encoder."""
    enabled: bool
    avg_rerank_ms: float
    docs_processed: int
    docs_filtered: int
    filter_rate: float


class DashboardMetrics(BaseModel):
    """Métricas consolidadas do dashboard."""
    timestamp: datetime
    cache: CacheMetrics
    router: RouterMetrics
    reranker: RerankerMetrics
    system: dict


@router.get("/", response_model=DashboardMetrics)
async def get_dashboard_metrics():
    """Retorna todas as métricas do dashboard."""
    from resync.core.cache.semantic_cache import SemanticCache
    from resync.core.embedding_router import EmbeddingRouter
    
    cache = SemanticCache()
    cache_stats = await cache.get_stats()
    
    return DashboardMetrics(
        timestamp=datetime.utcnow(),
        cache=CacheMetrics(
            hit_rate=cache_stats.get("hit_rate", 0),
            total_entries=cache_stats.get("total_entries", 0),
            memory_mb=cache_stats.get("memory_bytes", 0) / (1024 * 1024),
            avg_latency_ms=cache_stats.get("avg_latency_ms", 0),
            hits_last_hour=cache_stats.get("hits_last_hour", 0),
            misses_last_hour=cache_stats.get("misses_last_hour", 0),
        ),
        router=RouterMetrics(
            accuracy=0.89,  # TODO: Calcular de métricas reais
            fallback_rate=0.08,
            avg_classification_ms=18.0,
            top_intents={"job_details": 420, "troubleshooting": 280},
            low_confidence_count=45,
        ),
        reranker=RerankerMetrics(
            enabled=True,
            avg_rerank_ms=35.0,
            docs_processed=1500,
            docs_filtered=450,
            filter_rate=0.30,
        ),
        system={
            "uptime_hours": 72.5,
            "requests_today": 4521,
            "errors_today": 12,
        }
    )


@router.get("/cache/history")
async def get_cache_history(
    hours: int = Query(default=24, ge=1, le=168),
    interval: str = Query(default="1h", regex="^(5m|15m|1h|6h|1d)$"),
):
    """Retorna histórico de métricas do cache."""
    # TODO: Implementar armazenamento de métricas históricas
    return {
        "hours": hours,
        "interval": interval,
        "data_points": [],
    }


@router.get("/router/intent-distribution")
async def get_intent_distribution(
    hours: int = Query(default=24, ge=1, le=168),
):
    """Retorna distribuição de intents classificados."""
    return {
        "period_hours": hours,
        "distribution": {
            "job_details": 0.42,
            "troubleshooting": 0.28,
            "dependency_chain": 0.15,
            "documentation": 0.10,
            "other": 0.05,
        },
        "total_classifications": 1234,
    }


@router.post("/cache/warm")
async def trigger_cache_warming(
    priority: int = Query(default=1, ge=1, le=3),
):
    """Dispara warming manual do cache."""
    from resync.core.cache.cache_warmer import CacheWarmer
    
    # TODO: Injetar dependências corretamente
    warmer = CacheWarmer(...)
    result = await warmer.warm_static_queries(priority=priority)
    
    return {
        "queries_warmed": result,
        "message": f"Cache warming iniciado (prioridade {priority})",
    }
```

#### 4.3 Frontend - Dashboard HTML/React

```jsx
// templates/metrics_dashboard_v2.html ou React component

const MetricsDashboard = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMetrics = async () => {
      const response = await fetch('/api/v1/admin/metrics-dashboard/');
      const data = await response.json();
      setMetrics(data);
      setLoading(false);
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Refresh a cada 5s
    return () => clearInterval(interval);
  }, []);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="dashboard-container">
      <h1>Resync Metrics Dashboard</h1>
      
      {/* Cache Metrics */}
      <section className="metrics-section">
        <h2>🗄️ Semantic Cache</h2>
        <div className="metrics-grid">
          <MetricCard
            title="Hit Rate"
            value={`${(metrics.cache.hit_rate * 100).toFixed(1)}%`}
            trend={metrics.cache.hit_rate > 0.6 ? 'up' : 'down'}
            target="60%"
          />
          <MetricCard
            title="Entries"
            value={metrics.cache.total_entries.toLocaleString()}
          />
          <MetricCard
            title="Memory"
            value={`${metrics.cache.memory_mb.toFixed(1)} MB`}
          />
          <MetricCard
            title="Avg Latency"
            value={`${metrics.cache.avg_latency_ms.toFixed(0)}ms`}
            target="<50ms"
          />
        </div>
      </section>

      {/* Router Metrics */}
      <section className="metrics-section">
        <h2>🧭 Embedding Router</h2>
        <div className="metrics-grid">
          <MetricCard
            title="Accuracy"
            value={`${(metrics.router.accuracy * 100).toFixed(1)}%`}
            target="85%"
          />
          <MetricCard
            title="LLM Fallback"
            value={`${(metrics.router.fallback_rate * 100).toFixed(1)}%`}
            trend={metrics.router.fallback_rate < 0.2 ? 'up' : 'down'}
            target="<20%"
          />
          <MetricCard
            title="Classification Time"
            value={`${metrics.router.avg_classification_ms.toFixed(0)}ms`}
          />
        </div>
        <IntentDistributionChart data={metrics.router.top_intents} />
      </section>

      {/* Actions */}
      <section className="actions-section">
        <button onClick={() => warmCache(1)}>
          🔥 Warm Cache (High Priority)
        </button>
        <button onClick={() => warmCache(3)}>
          🔥 Full Cache Warm
        </button>
      </section>
    </div>
  );
};
```

---

## 🎯 v5.4.0 - Médio Prazo (6 semanas)

### Fase 1: Fine-tuning do Embedding Model (Semanas 1-2)

#### 1.1 Coleta de Dados de Treinamento

```python
# scripts/collect_training_data.py

"""
Coleta dados para fine-tuning do modelo de embeddings.

Fontes:
1. Histórico de chat com feedback positivo
2. Documentação TWS
3. Logs de queries com alta confiança
4. Pares query-intent validados manualmente
"""

from dataclasses import dataclass
from typing import List, Tuple
import json


@dataclass
class TrainingPair:
    """Par de treinamento para fine-tuning."""
    anchor: str       # Query original
    positive: str     # Exemplo similar (mesmo intent)
    negative: str     # Exemplo diferente (intent diferente)
    intent: str       # Intent correto


def collect_from_chat_history(db_session) -> List[TrainingPair]:
    """Coleta pares de queries similares do histórico."""
    # Queries que receberam thumbs up
    positive_queries = db_session.query(...).filter(
        feedback='positive'
    ).all()
    
    pairs = []
    for q in positive_queries:
        # Encontrar queries similares com mesmo intent
        similar = find_similar_queries(q, same_intent=True)
        different = find_similar_queries(q, same_intent=False)
        
        if similar and different:
            pairs.append(TrainingPair(
                anchor=q.content,
                positive=similar[0].content,
                negative=different[0].content,
                intent=q.classified_intent,
            ))
    
    return pairs


def collect_from_documentation() -> List[TrainingPair]:
    """Gera pares a partir da documentação TWS."""
    # Carregar documentação indexada
    docs = load_tws_documentation()
    
    pairs = []
    for doc in docs:
        # Gerar queries sintéticas para cada seção
        synthetic_queries = generate_queries_for_doc(doc)
        
        for q1, q2 in zip(synthetic_queries[:-1], synthetic_queries[1:]):
            pairs.append(TrainingPair(
                anchor=q1,
                positive=q2,
                negative=get_random_query_different_topic(),
                intent=doc.category,
            ))
    
    return pairs


def export_for_training(pairs: List[TrainingPair], output_path: str):
    """Exporta dados no formato para fine-tuning."""
    # Formato para sentence-transformers
    data = {
        "triplets": [
            {
                "anchor": p.anchor,
                "positive": p.positive,
                "negative": p.negative,
            }
            for p in pairs
        ],
        "metadata": {
            "total_pairs": len(pairs),
            "intents": list(set(p.intent for p in pairs)),
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Exportados {len(pairs)} pares para {output_path}")
```

#### 1.2 Script de Fine-tuning

```python
# scripts/finetune_embedding_model.py

"""
Fine-tuning do modelo de embeddings para domínio TWS.

Modelo base: sentence-transformers/all-MiniLM-L6-v2
Objetivo: Melhorar classificação de intents específicos do TWS
"""

from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
import json


def load_training_data(path: str) -> list[InputExample]:
    """Carrega dados de treinamento."""
    with open(path) as f:
        data = json.load(f)
    
    examples = []
    for triplet in data["triplets"]:
        examples.append(InputExample(
            texts=[
                triplet["anchor"],
                triplet["positive"],
                triplet["negative"],
            ]
        ))
    
    return examples


def finetune_model(
    base_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    training_data_path: str = "data/training_pairs.json",
    output_path: str = "models/resync-embeddings-v1",
    epochs: int = 3,
    batch_size: int = 16,
):
    """
    Executa fine-tuning do modelo.
    
    Args:
        base_model: Modelo base para fine-tuning
        training_data_path: Caminho para dados de treinamento
        output_path: Onde salvar modelo fine-tuned
        epochs: Número de épocas
        batch_size: Tamanho do batch
    """
    # Carregar modelo base
    model = SentenceTransformer(base_model)
    
    # Carregar dados
    train_examples = load_training_data(training_data_path)
    train_dataloader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=batch_size,
    )
    
    # Loss function para triplet learning
    train_loss = losses.TripletLoss(model=model)
    
    # Treinar
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=epochs,
        warmup_steps=100,
        output_path=output_path,
        show_progress_bar=True,
    )
    
    print(f"Modelo salvo em {output_path}")
    
    return model


def evaluate_model(
    model_path: str,
    test_data_path: str,
) -> dict:
    """Avalia modelo fine-tuned."""
    from sklearn.metrics import accuracy_score
    
    model = SentenceTransformer(model_path)
    
    with open(test_data_path) as f:
        test_data = json.load(f)
    
    correct = 0
    total = 0
    
    for item in test_data["test_cases"]:
        query_embedding = model.encode(item["query"])
        
        # Calcular similaridade com cada intent
        best_intent = None
        best_score = -1
        
        for intent, examples in item["intent_examples"].items():
            example_embeddings = model.encode(examples)
            similarity = cosine_similarity(
                [query_embedding],
                example_embeddings
            ).mean()
            
            if similarity > best_score:
                best_score = similarity
                best_intent = intent
        
        if best_intent == item["expected_intent"]:
            correct += 1
        total += 1
    
    accuracy = correct / total
    print(f"Accuracy: {accuracy:.2%}")
    
    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
    }


if __name__ == "__main__":
    # 1. Fine-tune
    model = finetune_model()
    
    # 2. Avaliar
    results = evaluate_model(
        model_path="models/resync-embeddings-v1",
        test_data_path="data/test_cases.json",
    )
```

---

### Fase 2: Knowledge Graph Expansion (Semanas 3-4)

#### 2.1 Novas Relações TWS

```python
# resync/core/knowledge_graph/tws_relations.py

"""
Expansão do Knowledge Graph com relações específicas do TWS.

Novas relações:
- TRIGGERS: Job A dispara Job B
- RECOVERS: Job A é recovery de Job B
- SHARES_RESOURCE: Jobs compartilham recurso
- RUNS_ON: Job roda em workstation
- BELONGS_TO: Job pertence a schedule
- MONITORED_BY: Job monitorado por alerta
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


class TWSRelationType(Enum):
    """Tipos de relação no grafo TWS."""
    # Existentes
    DEPENDS_ON = "depends_on"
    FOLLOWS = "follows"
    NEEDS = "needs"
    
    # Novos
    TRIGGERS = "triggers"
    RECOVERS = "recovers"
    SHARES_RESOURCE = "shares_resource"
    RUNS_ON = "runs_on"
    BELONGS_TO = "belongs_to"
    MONITORED_BY = "monitored_by"
    PREDECESSOR_OF = "predecessor_of"
    SUCCESSOR_OF = "successor_of"
    EXCLUSIVE_WITH = "exclusive_with"


@dataclass
class TWSRelation:
    """Relação entre entidades TWS."""
    from_entity: str
    to_entity: str
    relation_type: TWSRelationType
    properties: dict = None
    
    def to_cypher(self) -> str:
        """Gera query Cypher para criar relação."""
        props = ""
        if self.properties:
            props = " {" + ", ".join(
                f"{k}: '{v}'" for k, v in self.properties.items()
            ) + "}"
        
        return f"""
        MATCH (a {{name: '{self.from_entity}'}})
        MATCH (b {{name: '{self.to_entity}'}})
        MERGE (a)-[:{self.relation_type.value}{props}]->(b)
        """


class TWSGraphExpander:
    """Expande o Knowledge Graph com dados do TWS."""
    
    def __init__(self, graph_service):
        self.graph = graph_service
    
    async def expand_from_tws_api(self, tws_client) -> int:
        """
        Expande grafo com dados da API do TWS.
        
        Extrai:
        - Dependências entre jobs
        - Recursos compartilhados
        - Schedules e seus jobs
        - Workstations
        - Recovery jobs
        """
        relations_created = 0
        
        # 1. Obter todos os jobs
        jobs = await tws_client.get_all_jobs()
        
        for job in jobs:
            # Criar nó do job
            await self.graph.create_node("Job", {
                "name": job.name,
                "workstation": job.workstation,
                "schedule": job.schedule,
                "priority": job.priority,
            })
            
            # Relação RUNS_ON
            if job.workstation:
                await self.graph.create_relation(TWSRelation(
                    from_entity=job.name,
                    to_entity=job.workstation,
                    relation_type=TWSRelationType.RUNS_ON,
                ))
                relations_created += 1
            
            # Relação BELONGS_TO
            if job.schedule:
                await self.graph.create_relation(TWSRelation(
                    from_entity=job.name,
                    to_entity=job.schedule,
                    relation_type=TWSRelationType.BELONGS_TO,
                ))
                relations_created += 1
            
            # Dependências
            for dep in job.dependencies:
                await self.graph.create_relation(TWSRelation(
                    from_entity=job.name,
                    to_entity=dep.job_name,
                    relation_type=TWSRelationType.DEPENDS_ON,
                    properties={"type": dep.dependency_type},
                ))
                relations_created += 1
            
            # Recovery job
            if job.recovery_job:
                await self.graph.create_relation(TWSRelation(
                    from_entity=job.recovery_job,
                    to_entity=job.name,
                    relation_type=TWSRelationType.RECOVERS,
                ))
                relations_created += 1
        
        # 2. Detectar recursos compartilhados
        resources = await tws_client.get_all_resources()
        for resource in resources:
            jobs_using = await tws_client.get_jobs_using_resource(resource.name)
            
            for i, job1 in enumerate(jobs_using):
                for job2 in jobs_using[i+1:]:
                    await self.graph.create_relation(TWSRelation(
                        from_entity=job1,
                        to_entity=job2,
                        relation_type=TWSRelationType.SHARES_RESOURCE,
                        properties={"resource": resource.name},
                    ))
                    relations_created += 1
        
        return relations_created
    
    async def expand_from_audit_log(self, days: int = 30) -> int:
        """
        Expande grafo com padrões do audit log.
        
        Detecta:
        - Jobs que frequentemente falham juntos
        - Padrões de recuperação
        - Sequências de execução comuns
        """
        # TODO: Implementar análise de audit log
        pass
```

---

### Fase 3: Feedback Loop Automático (Semana 5)

#### 3.1 Sistema de Feedback

```python
# resync/core/feedback/feedback_collector.py

"""
Sistema de Feedback Loop Automático.

Coleta feedback implícito e explícito para:
- Melhorar classificação de intents
- Ajustar threshold do reranker
- Identificar queries problemáticas
- Atualizar cache warming priorities
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import asyncio


class FeedbackType(Enum):
    """Tipos de feedback."""
    THUMBS_UP = "positive"
    THUMBS_DOWN = "negative"
    RETRY = "retry"           # Usuário reformulou pergunta
    FOLLOWUP = "followup"     # Usuário fez pergunta de followup
    ABANDON = "abandon"       # Usuário abandonou a conversa


@dataclass
class FeedbackEvent:
    """Evento de feedback."""
    query_id: str
    query_text: str
    classified_intent: str
    confidence: float
    feedback_type: FeedbackType
    timestamp: datetime
    user_id: Optional[str] = None
    corrected_intent: Optional[str] = None
    notes: Optional[str] = None


class FeedbackCollector:
    """Coleta e processa feedback dos usuários."""
    
    def __init__(self, db_session, embedding_router, cache):
        self.db = db_session
        self.router = embedding_router
        self.cache = cache
        self._pending_updates = []
    
    async def record_feedback(self, event: FeedbackEvent):
        """Registra evento de feedback."""
        # Salvar no banco
        await self._save_to_db(event)
        
        # Atualizar métricas
        await self._update_metrics(event)
        
        # Processar feedback
        if event.feedback_type == FeedbackType.THUMBS_UP:
            await self._handle_positive_feedback(event)
        elif event.feedback_type == FeedbackType.THUMBS_DOWN:
            await self._handle_negative_feedback(event)
        elif event.feedback_type == FeedbackType.RETRY:
            await self._handle_retry_feedback(event)
    
    async def _handle_positive_feedback(self, event: FeedbackEvent):
        """Processa feedback positivo."""
        # Aumentar peso do exemplo no router
        if event.confidence < 0.9:
            # Query foi classificada corretamente mas com baixa confiança
            # Adicionar como exemplo de treinamento
            await self._add_training_example(
                query=event.query_text,
                intent=event.classified_intent,
                source="positive_feedback",
            )
        
        # Manter resposta no cache por mais tempo
        await self.cache.extend_ttl(event.query_id)
    
    async def _handle_negative_feedback(self, event: FeedbackEvent):
        """Processa feedback negativo."""
        # Invalidar cache para esta query
        await self.cache.invalidate(event.query_id)
        
        # Se intent foi corrigido, usar como exemplo negativo
        if event.corrected_intent:
            await self._add_negative_example(
                query=event.query_text,
                wrong_intent=event.classified_intent,
                correct_intent=event.corrected_intent,
            )
        
        # Registrar para revisão manual se confiança era alta
        if event.confidence > 0.8:
            await self._flag_for_review(event)
    
    async def _handle_retry_feedback(self, event: FeedbackEvent):
        """Processa retry (reformulação de pergunta)."""
        # Query original provavelmente não foi bem entendida
        # Diminuir confiança implícita para queries similares
        await self._decrease_confidence_similar(event.query_text)


class FeedbackProcessor:
    """Processa feedback em batch para atualização de modelos."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def generate_training_update(
        self,
        min_positive: int = 10,
        min_negative: int = 5,
    ) -> dict:
        """
        Gera atualização de treinamento baseada em feedback.
        
        Returns:
            Dict com novos exemplos para cada intent
        """
        # Coletar feedback positivo
        positive = await self.db.query(
            "SELECT query_text, classified_intent FROM feedback "
            "WHERE feedback_type = 'positive' "
            "GROUP BY classified_intent "
            "HAVING COUNT(*) >= :min",
            {"min": min_positive}
        )
        
        # Coletar feedback negativo
        negative = await self.db.query(
            "SELECT query_text, classified_intent, corrected_intent FROM feedback "
            "WHERE feedback_type = 'negative' AND corrected_intent IS NOT NULL "
            "HAVING COUNT(*) >= :min",
            {"min": min_negative}
        )
        
        return {
            "new_examples": positive,
            "corrections": negative,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    async def auto_adjust_thresholds(self) -> dict:
        """
        Ajusta automaticamente thresholds baseado em feedback.
        
        Analisa:
        - Taxa de falsos positivos (alta confiança + feedback negativo)
        - Taxa de falsos negativos (baixa confiança + feedback positivo)
        """
        # Calcular taxa de erro por faixa de confiança
        confidence_ranges = [
            (0.0, 0.5),
            (0.5, 0.7),
            (0.7, 0.85),
            (0.85, 1.0),
        ]
        
        analysis = {}
        for low, high in confidence_ranges:
            stats = await self._analyze_confidence_range(low, high)
            analysis[f"{low}-{high}"] = stats
        
        # Recomendar novos thresholds
        recommendations = self._calculate_optimal_thresholds(analysis)
        
        return {
            "current_analysis": analysis,
            "recommendations": recommendations,
        }
```

---

### Fase 4: Multi-tenant Support (Semana 6)

#### 4.1 Arquitetura Multi-tenant

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MULTI-TENANT ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         TENANT ROUTER                                   ││
│  │                    (Identifica tenant por header/token)                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│           ┌────────────────────────┼────────────────────────┐               │
│           ▼                        ▼                        ▼               │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │   TENANT A      │     │   TENANT B      │     │   TENANT C      │       │
│  │   (Produção)    │     │   (Homologação) │     │   (Dev)         │       │
│  ├─────────────────┤     ├─────────────────┤     ├─────────────────┤       │
│  │ • Cache isolado │     │ • Cache isolado │     │ • Cache isolado │       │
│  │ • KG separado   │     │ • KG separado   │     │ • KG separado   │       │
│  │ • Configs own   │     │ • Configs own   │     │ • Configs own   │       │
│  │ • Métricas own  │     │ • Métricas own  │     │ • Métricas own  │       │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    SHARED RESOURCES                                     ││
│  │  • Embedding Model (read-only)                                          ││
│  │  • Base Documentation                                                    ││
│  │  • System Prompts                                                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 4.2 Implementação

```python
# resync/core/multi_tenant/tenant_manager.py

"""
Gerenciador Multi-tenant.

Isola:
- Semantic Cache (prefixo por tenant)
- Knowledge Graph (schema separado)
- Configurações
- Métricas
- Audit logs
"""

from dataclasses import dataclass
from typing import Optional
from contextvars import ContextVar

# Context variable para tenant atual
current_tenant: ContextVar[Optional[str]] = ContextVar('current_tenant', default=None)


@dataclass
class TenantConfig:
    """Configuração de um tenant."""
    tenant_id: str
    name: str
    environment: str  # prod, homolog, dev
    cache_prefix: str
    kg_schema: str
    tws_instance: str
    max_cache_size_mb: int = 100
    cache_ttl_hours: int = 24
    enabled: bool = True


class TenantManager:
    """Gerencia configurações e isolamento de tenants."""
    
    def __init__(self, db_session):
        self.db = db_session
        self._cache = {}  # Cache de configs por tenant
    
    async def get_tenant_config(self, tenant_id: str) -> TenantConfig:
        """Obtém configuração do tenant."""
        if tenant_id in self._cache:
            return self._cache[tenant_id]
        
        config = await self.db.query(
            "SELECT * FROM tenants WHERE tenant_id = :id",
            {"id": tenant_id}
        )
        
        if not config:
            raise TenantNotFoundError(tenant_id)
        
        tenant_config = TenantConfig(**config)
        self._cache[tenant_id] = tenant_config
        
        return tenant_config
    
    def set_current_tenant(self, tenant_id: str):
        """Define tenant atual no contexto."""
        current_tenant.set(tenant_id)
    
    def get_current_tenant(self) -> Optional[str]:
        """Obtém tenant atual do contexto."""
        return current_tenant.get()
    
    async def get_tenant_cache_key(self, key: str) -> str:
        """Gera chave de cache prefixada com tenant."""
        tenant_id = self.get_current_tenant()
        if not tenant_id:
            raise NoTenantContextError()
        
        config = await self.get_tenant_config(tenant_id)
        return f"{config.cache_prefix}:{key}"
    
    async def get_tenant_kg_schema(self) -> str:
        """Obtém schema do KG para tenant atual."""
        tenant_id = self.get_current_tenant()
        config = await self.get_tenant_config(tenant_id)
        return config.kg_schema


class TenantMiddleware:
    """Middleware para identificar tenant em requests."""
    
    def __init__(self, app, tenant_manager: TenantManager):
        self.app = app
        self.tenant_manager = tenant_manager
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            
            # Tentar identificar tenant por header
            tenant_id = headers.get(b"x-tenant-id", b"").decode()
            
            # Ou por token JWT
            if not tenant_id:
                auth_header = headers.get(b"authorization", b"").decode()
                if auth_header.startswith("Bearer "):
                    tenant_id = self._extract_tenant_from_jwt(auth_header[7:])
            
            # Definir tenant no contexto
            if tenant_id:
                self.tenant_manager.set_current_tenant(tenant_id)
        
        await self.app(scope, receive, send)


# Exemplo de uso no cache
class MultiTenantCache:
    """Cache com isolamento por tenant."""
    
    def __init__(self, base_cache, tenant_manager: TenantManager):
        self.cache = base_cache
        self.tenant_manager = tenant_manager
    
    async def get(self, key: str):
        tenant_key = await self.tenant_manager.get_tenant_cache_key(key)
        return await self.cache.get(tenant_key)
    
    async def set(self, key: str, value, ttl: int = None):
        tenant_key = await self.tenant_manager.get_tenant_cache_key(key)
        
        # Aplicar TTL específico do tenant se não fornecido
        if ttl is None:
            config = await self.tenant_manager.get_tenant_config(
                self.tenant_manager.get_current_tenant()
            )
            ttl = config.cache_ttl_hours * 3600
        
        return await self.cache.set(tenant_key, value, ttl=ttl)
```

---

## 📋 Checklist de Validação

### Pré-Deploy v5.3.18

```bash
#!/bin/bash
# scripts/validate_v5318.sh

echo "=== Validação v5.3.18 ==="

# 1. Verificar sintaxe
echo "1. Verificando sintaxe Python..."
find resync/ -name "*.py" -exec python -m py_compile {} \; 2>&1 | tee syntax_errors.log
if [ -s syntax_errors.log ]; then
    echo "❌ Erros de sintaxe encontrados!"
    exit 1
fi
echo "✅ Sintaxe OK"

# 2. Executar testes
echo "2. Executando testes de integração..."
pytest tests/integration/test_v5317_integration.py tests/integration/test_full_pipeline.py -v
if [ $? -ne 0 ]; then
    echo "❌ Testes falharam!"
    exit 1
fi
echo "✅ Testes OK"

# 3. Validar exemplos de intent
echo "3. Validando exemplos de intent..."
python scripts/validate_intent_examples.py
if [ $? -ne 0 ]; then
    echo "❌ Exemplos insuficientes!"
    exit 1
fi
echo "✅ Exemplos OK (200+)"

# 4. Verificar Redis
echo "4. Verificando Redis Stack..."
redis-cli -p 6379 MODULE LIST | grep -q "search"
if [ $? -ne 0 ]; then
    echo "❌ RediSearch não encontrado!"
    exit 1
fi
echo "✅ Redis Stack OK"

# 5. Testar cache warming
echo "5. Testando cache warming..."
python -c "
from resync.core.cache.cache_warmer import CacheWarmer
print('✅ Cache warmer importado')
"

# 6. Verificar dashboard
echo "6. Verificando endpoints do dashboard..."
curl -s http://localhost:8000/api/v1/admin/metrics-dashboard/ | jq .
if [ $? -ne 0 ]; then
    echo "⚠️ Dashboard não acessível (app não está rodando)"
fi

echo ""
echo "=== Validação Completa ==="
echo "✅ v5.3.18 pronto para deploy!"
```

### Pré-Deploy v5.4.0

```bash
#!/bin/bash
# scripts/validate_v540.sh

echo "=== Validação v5.4.0 ==="

# 1. Verificar modelo fine-tuned
echo "1. Verificando modelo fine-tuned..."
if [ -d "models/resync-embeddings-v1" ]; then
    echo "✅ Modelo fine-tuned encontrado"
else
    echo "❌ Modelo não encontrado em models/resync-embeddings-v1"
    exit 1
fi

# 2. Validar expansão do KG
echo "2. Verificando expansão do Knowledge Graph..."
python -c "
from resync.core.knowledge_graph.tws_relations import TWSRelationType
print(f'Tipos de relação: {len(TWSRelationType)}')
assert len(TWSRelationType) >= 10, 'Menos relações que esperado'
print('✅ KG expandido')
"

# 3. Testar feedback loop
echo "3. Verificando sistema de feedback..."
python -c "
from resync.core.feedback.feedback_collector import FeedbackCollector, FeedbackType
print('✅ Feedback loop OK')
"

# 4. Validar multi-tenant
echo "4. Verificando suporte multi-tenant..."
python -c "
from resync.core.multi_tenant.tenant_manager import TenantManager, TenantConfig
print('✅ Multi-tenant OK')
"

# 5. Benchmark de performance
echo "5. Executando benchmark..."
python scripts/benchmark_v540.py

echo ""
echo "=== Validação Completa ==="
echo "✅ v5.4.0 pronto para deploy!"
```

---

## 📊 Métricas de Sucesso

| Versão | Métrica | Target | Como Medir |
|--------|---------|--------|------------|
| v5.3.18 | Syntax errors | 0 | py_compile |
| v5.3.18 | Intent examples | 200+ | validate script |
| v5.3.18 | Cache hit rate | >60% | Dashboard |
| v5.3.18 | Dashboard uptime | 99.9% | Prometheus |
| v5.4.0 | Intent accuracy | >90% | A/B test |
| v5.4.0 | KG relations | >1000 | Graph count |
| v5.4.0 | Feedback response | <24h | SLA |
| v5.4.0 | Tenant isolation | 100% | Security audit |

---

## Timeline Consolidado

```
Semana 1-2: v5.3.18
├── Dia 1-2: Correções de sintaxe
├── Dia 3-5: Expansão de exemplos (107→200+)
├── Dia 6-8: Cache warming
└── Dia 9-14: Dashboard de métricas

Semana 3-4: v5.4.0 - Fase 1
├── Coleta de dados de treinamento
├── Fine-tuning do embedding model
└── Validação e deploy do modelo

Semana 5-6: v5.4.0 - Fase 2
├── Expansão do Knowledge Graph
├── Sistema de feedback loop
├── Multi-tenant support
└── Testes E2E e deploy
```
