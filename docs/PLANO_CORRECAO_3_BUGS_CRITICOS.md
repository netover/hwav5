# Plano de Correção Profunda - 3 Bugs Críticos do HybridRouter

**Versão**: 5.7.1  
**Data**: Dezembro 2024  
**Prioridade**: CRÍTICA - Bloqueiam funcionalidade core  

---

## Resumo Executivo

| Bug | Descrição | Impacto | Complexidade |
|-----|-----------|---------|--------------|
| **#1** | RAGTool.search_knowledge_base retorna `[]` (stub) | RAG_ONLY 100% inoperante | Média |
| **#2** | Parâmetros incorretos em `_handle_status` | TypeError em runtime | Baixa |
| **#3** | HybridRouter sem AgentManager | Agents Agno retornam "" | Alta |

---

## Bug #1: RAGTool com Retrieval Comentado

### Diagnóstico

```python
# resync/core/specialists/tools.py:983
results = []  # retriever.retrieve(query, top_k=top_k)  # ← STUB!
```

O código de retrieval está **comentado**, fazendo o RAG_ONLY sempre cair no fallback genérico.

### Causa Raiz
- O `HybridRetriever` é **assíncrono** (`async def retrieve()`)
- O método `search_knowledge_base` é **síncrono** (decorado com `@tool`)
- O desenvolvedor comentou a chamada porque não podia fazer `await` dentro de método sync

### Solução Arquitetural

**Opção A: Wrapper Síncrono com Event Loop** (Recomendada)
```python
def search_knowledge_base(self, query: str, top_k: int = 5, use_hybrid: bool = True) -> dict:
    retriever = self._get_hybrid_retriever() if use_hybrid else self._get_retriever()
    if not retriever:
        return {"results": [], "error": "Retriever not available"}
    
    # Executar coroutine de forma síncrona
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Dentro de contexto async - usar nest_asyncio ou thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, retriever.retrieve(query, top_k=top_k))
                results = future.result(timeout=30)
        else:
            results = loop.run_until_complete(retriever.retrieve(query, top_k=top_k))
        
        return {
            "results": results,
            "query": query,
            "total_found": len(results),
        }
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return {"results": [], "error": str(e)}
```

**Opção B: Método Assíncrono Separado**
```python
@tool(permission=ToolPermission.READ_ONLY, tags=["rag", "search"])
def search_knowledge_base(self, query: str, top_k: int = 5) -> dict:
    """Sync wrapper - delegates to async implementation."""
    return asyncio.run(self._async_search(query, top_k))

async def _async_search(self, query: str, top_k: int) -> dict:
    retriever = self._get_hybrid_retriever()
    results = await retriever.retrieve(query, top_k=top_k)
    return {"results": results, "total_found": len(results)}
```

### Arquivos a Modificar

| Arquivo | Modificação |
|---------|-------------|
| `resync/core/specialists/tools.py` | Implementar chamada real ao retriever |
| `resync/core/specialists/tools.py` | Adicionar tratamento de async/sync |

### Código de Correção Completo

```python
# resync/core/specialists/tools.py - Método corrigido

import asyncio
import concurrent.futures
from functools import partial

class RAGTool:
    # ... (existing code)
    
    def _run_async_retrieval(self, retriever, query: str, top_k: int) -> list:
        """Execute async retrieval in sync context."""
        async def _retrieve():
            return await retriever.retrieve(query, top_k=top_k)
        
        return asyncio.run(_retrieve())
    
    @tool(
        permission=ToolPermission.READ_ONLY,
        tags=["rag", "search", "knowledge"],
    )
    def search_knowledge_base(
        self,
        query: str,
        top_k: int = 5,
        use_hybrid: bool = True,
    ) -> dict[str, Any]:
        """
        Search the TWS knowledge base using RAG.
        
        Args:
            query: Search query
            top_k: Number of results to return
            use_hybrid: Use hybrid retrieval (BM25 + vector)
            
        Returns:
            Search results with relevance scores
        """
        start_time = time.time()
        
        try:
            retriever = self._get_hybrid_retriever() if use_hybrid else self._get_retriever()
            
            if not retriever:
                return {
                    "results": [],
                    "query": query,
                    "total_found": 0,
                    "search_time_ms": 0,
                    "error": "Retriever not available",
                }
            
            # FIX BUG #1: Execute async retrieval properly
            try:
                # Check if we're already in an event loop
                loop = asyncio.get_running_loop()
                # We're in async context - use thread pool
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        self._run_async_retrieval, retriever, query, top_k
                    )
                    results = future.result(timeout=30)
            except RuntimeError:
                # No running loop - safe to use asyncio.run
                results = self._run_async_retrieval(retriever, query, top_k)
            
            search_time = int((time.time() - start_time) * 1000)
            
            # Normalize results format
            normalized_results = []
            for r in results:
                if isinstance(r, dict):
                    normalized_results.append(r)
                else:
                    # Handle tuple/list format from some retrievers
                    normalized_results.append({
                        "content": str(r[0]) if isinstance(r, (tuple, list)) else str(r),
                        "score": float(r[1]) if isinstance(r, (tuple, list)) and len(r) > 1 else 0.0,
                    })
            
            return {
                "results": normalized_results,
                "query": query,
                "total_found": len(normalized_results),
                "search_time_ms": search_time,
            }
            
        except Exception as e:
            logger.error(f"RAG search failed: {e}", exc_info=True)
            return {
                "results": [],
                "query": query,
                "total_found": 0,
                "search_time_ms": int((time.time() - start_time) * 1000),
                "error": str(e),
            }
```

### Testes de Validação

```python
# tests/core/test_rag_tool_fix.py

import pytest
from resync.core.specialists.tools import RAGTool

class TestRAGToolFix:
    """Tests for Bug #1 fix."""
    
    def test_search_knowledge_base_returns_results(self):
        """Verify search doesn't return empty stub."""
        rag = RAGTool()
        result = rag.search_knowledge_base("TWS error AWSBCW001E")
        
        # Should not be empty stub
        assert "error" not in result or result.get("results")
        # If retriever available, should have results
        
    def test_search_handles_async_context(self):
        """Test search works from async context."""
        import asyncio
        
        async def async_search():
            rag = RAGTool()
            return rag.search_knowledge_base("backup job")
        
        result = asyncio.run(async_search())
        assert isinstance(result, dict)
        assert "results" in result
        
    def test_search_timeout_handling(self):
        """Test timeout doesn't crash."""
        rag = RAGTool()
        # Should handle timeout gracefully
        result = rag.search_knowledge_base("test query", top_k=100)
        assert isinstance(result, dict)
```

---

## Bug #2: Parâmetros Incorretos em _handle_status

### Diagnóstico

```python
# resync/core/agent_router.py:598
parameters={"ws_name": ws}  # ← ERRADO!
# Assinatura real: get_workstation_status(workstation_name: str | None)

# resync/core/agent_router.py:615
parameters={"job_name": job, "lines": 10}  # ← ERRADO!
# Assinatura real: get_job_log(job_name, run_date=None, max_lines=100)
```

### Causa Raiz
- Desconexão entre quem escreveu o handler e quem definiu as tools
- Falta de type checking ou validação em tempo de desenvolvimento
- Nomes de parâmetros não seguiram convenção consistente

### Solução

**Correção direta dos nomes de parâmetros:**

```python
# resync/core/agent_router.py - AgenticHandler._handle_status

async def _handle_status(
    self,
    message: str,
    context: dict[str, Any],
    classification: IntentClassification,
) -> str:
    """Handle status queries with parallel execution."""
    from resync.core.specialists.parallel_executor import (
        ExecutionStrategy,
        ToolRequest,
    )

    workstations = classification.entities.get("workstation", [])
    job_names = classification.entities.get("job_name", [])

    requests = []

    # FIX BUG #2: Correct parameter name (ws_name → workstation_name)
    if workstations:
        for ws in workstations[:5]:
            requests.append(
                ToolRequest(
                    tool_name="get_workstation_status",
                    parameters={"workstation_name": ws},  # FIXED
                )
            )
    else:
        requests.append(
            ToolRequest(
                tool_name="get_workstation_status",
                parameters={},
            )
        )

    # FIX BUG #2: Correct parameter name (lines → max_lines)
    if job_names:
        for job in job_names[:5]:
            requests.append(
                ToolRequest(
                    tool_name="get_job_log",
                    parameters={"job_name": job, "max_lines": 10},  # FIXED
                )
            )

    # ... rest of method unchanged
```

### Prevenção Futura: Validação de Parâmetros

Adicionar validação em `ParallelExecutor`:

```python
# resync/core/specialists/parallel_executor.py

def _validate_tool_request(self, request: ToolRequest, tool_def: ToolDefinition) -> list[str]:
    """Validate request parameters match tool signature."""
    errors = []
    
    # Get expected parameters from tool definition
    expected_params = set(tool_def.parameters.keys()) if tool_def.parameters else set()
    provided_params = set(request.parameters.keys())
    
    # Check for unknown parameters
    unknown = provided_params - expected_params
    if unknown:
        errors.append(f"Unknown parameters for {request.tool_name}: {unknown}")
    
    # Check for required parameters
    required_params = {
        name for name, spec in (tool_def.parameters or {}).items()
        if spec.get("required", False)
    }
    missing = required_params - provided_params
    if missing:
        errors.append(f"Missing required parameters for {request.tool_name}: {missing}")
    
    return errors
```

### Arquivos a Modificar

| Arquivo | Modificação |
|---------|-------------|
| `resync/core/agent_router.py:598` | `ws_name` → `workstation_name` |
| `resync/core/agent_router.py:615` | `lines` → `max_lines` |
| `resync/core/specialists/parallel_executor.py` | Adicionar validação |

### Testes de Validação

```python
# tests/core/test_handle_status_params.py

import pytest
from resync.core.agent_router import AgenticHandler, IntentClassification, Intent

class TestHandleStatusParams:
    """Tests for Bug #2 fix."""
    
    @pytest.mark.asyncio
    async def test_workstation_param_name_correct(self):
        """Verify correct parameter name for workstation."""
        handler = AgenticHandler(agent_manager=None)
        
        classification = IntentClassification(
            primary_intent=Intent.STATUS,
            confidence=0.9,
            entities={"workstation": ["TWS_MASTER"]},
        )
        
        # Should not raise TypeError
        result = await handler._handle_status("status TWS_MASTER", {}, classification)
        assert isinstance(result, str)
    
    @pytest.mark.asyncio
    async def test_job_log_param_name_correct(self):
        """Verify correct parameter name for job log."""
        handler = AgenticHandler(agent_manager=None)
        
        classification = IntentClassification(
            primary_intent=Intent.STATUS,
            confidence=0.9,
            entities={"job_name": ["BATCH001"]},
        )
        
        # Should not raise TypeError about 'lines'
        result = await handler._handle_status("log BATCH001", {}, classification)
        assert isinstance(result, str)
```

---

## Bug #3: HybridRouter sem AgentManager

### Diagnóstico

```python
# resync/fastapi_app/api/v1/routes/chat.py:171
_hybrid_router = HybridRouter()  # ← SEM AgentManager!

# Consequência em agent_router.py:431-437
async def _get_agent_response(self, agent_id: str, message: str) -> str:
    if self.agent_manager:  # None → False
        agent = await self.agent_manager.get_agent(agent_id)
        if agent and hasattr(agent, "arun"):
            return await agent.arun(message)
    return ""  # ← SEMPRE RETORNA VAZIO
```

### Causa Raiz
- `HybridRouter` foi projetado para receber `AgentManager` como dependência
- O endpoint `/chat` cria o router como singleton sem injetar dependências
- Não existe integração com o sistema de Dependency Injection (DI) do FastAPI

### Solução Arquitetural

**Abordagem: Integração com DI Container + Lazy Initialization**

```
┌─────────────────────────────────────────────────────────────────┐
│                      ARQUITETURA CORRIGIDA                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FastAPI Startup                                                │
│       │                                                         │
│       ▼                                                         │
│  DIContainer.initialize()                                       │
│       │                                                         │
│       ├──► AgentManager (singleton)                             │
│       │         │                                               │
│       │         ▼                                               │
│       └──► HybridRouter(agent_manager) ◄─── Injeção             │
│                 │                                               │
│                 ├── RAGOnlyHandler(agent_manager)               │
│                 ├── AgenticHandler(agent_manager)               │
│                 └── DiagnosticHandler(agent_manager)            │
│                                                                 │
│  /chat endpoint                                                 │
│       │                                                         │
│       ▼                                                         │
│  Depends(get_hybrid_router) ──► Router singleton com DI         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementação

#### Passo 1: Criar Provider para HybridRouter

```python
# resync/core/di_container.py - Adicionar

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from resync.core.agent_router import HybridRouter
    from resync.core.agent_manager import AgentManager

class DIContainer:
    _hybrid_router: "HybridRouter | None" = None
    _agent_manager: "AgentManager | None" = None
    
    @classmethod
    def get_agent_manager(cls) -> "AgentManager":
        """Get or create AgentManager singleton."""
        if cls._agent_manager is None:
            from resync.core.agent_manager import AgentManager
            cls._agent_manager = AgentManager()
        return cls._agent_manager
    
    @classmethod
    def get_hybrid_router(cls) -> "HybridRouter":
        """Get or create HybridRouter with proper dependencies."""
        if cls._hybrid_router is None:
            from resync.core.agent_router import HybridRouter
            
            agent_manager = cls.get_agent_manager()
            cls._hybrid_router = HybridRouter(agent_manager=agent_manager)
        return cls._hybrid_router
    
    @classmethod
    def reset(cls) -> None:
        """Reset all singletons (for testing)."""
        cls._hybrid_router = None
        cls._agent_manager = None
```

#### Passo 2: Criar Dependency Injection para FastAPI

```python
# resync/api/dependencies.py - Adicionar

from fastapi import Depends
from resync.core.di_container import DIContainer

def get_hybrid_router():
    """FastAPI dependency for HybridRouter."""
    return DIContainer.get_hybrid_router()

def get_agent_manager():
    """FastAPI dependency for AgentManager."""
    return DIContainer.get_agent_manager()
```

#### Passo 3: Corrigir Endpoint /chat

```python
# resync/fastapi_app/api/v1/routes/chat.py - CORRIGIDO

from fastapi import APIRouter, Depends, HTTPException
from resync.api.dependencies import get_hybrid_router

# REMOVE: Global singleton sem DI
# _hybrid_router: HybridRouter | None = None

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/message")
async def chat_message(
    request: ChatRequest,
    hybrid_router = Depends(get_hybrid_router),  # FIX: Inject via DI
    x_routing_mode: str | None = Header(None),
):
    """
    Process chat message with intelligent routing.
    
    v5.7.1: Fixed HybridRouter dependency injection
    """
    # ... validation code ...
    
    # Parse forced routing mode
    force_mode = None
    if x_routing_mode:
        try:
            force_mode = RoutingMode(x_routing_mode)
        except ValueError:
            pass
    
    # Route using injected router (with AgentManager!)
    result = await hybrid_router.route(
        message=resolved_message,
        context={
            "tws_instance_id": request.tws_instance_id,
            "session_id": context.session_id,
            "conversation_history": conversation_context,
        },
        force_mode=force_mode,
    )
    
    response_message = result.response
    # ... rest of handler
```

#### Passo 4: Inicialização no Startup

```python
# resync/lifespan.py - Adicionar

from resync.core.di_container import DIContainer

async def startup_event():
    """Initialize application services."""
    # ... existing startup code ...
    
    # Pre-warm HybridRouter with AgentManager
    try:
        router = DIContainer.get_hybrid_router()
        logger.info("hybrid_router_initialized", has_agent_manager=router.agent_manager is not None)
    except Exception as e:
        logger.error(f"Failed to initialize HybridRouter: {e}")
```

### Arquivos a Modificar

| Arquivo | Modificação |
|---------|-------------|
| `resync/core/di_container.py` | Adicionar providers para Router/Manager |
| `resync/api/dependencies.py` | Adicionar FastAPI dependencies |
| `resync/fastapi_app/api/v1/routes/chat.py` | Usar `Depends(get_hybrid_router)` |
| `resync/lifespan.py` | Pre-warm router no startup |

### Testes de Validação

```python
# tests/api/test_chat_router_di.py

import pytest
from fastapi.testclient import TestClient
from resync.core.di_container import DIContainer

class TestChatRouterDI:
    """Tests for Bug #3 fix."""
    
    def setup_method(self):
        DIContainer.reset()
    
    def test_hybrid_router_has_agent_manager(self):
        """Verify router is created with AgentManager."""
        router = DIContainer.get_hybrid_router()
        
        assert router.agent_manager is not None
        assert hasattr(router.agent_manager, "get_agent")
    
    def test_agent_response_not_empty(self):
        """Verify agents can return responses."""
        router = DIContainer.get_hybrid_router()
        handler = router._handlers[RoutingMode.AGENTIC]
        
        # _get_agent_response should not return ""
        import asyncio
        result = asyncio.run(handler._get_agent_response("tws-general", "test"))
        
        # With AgentManager, should get actual response or graceful fallback
        # NOT empty string
        assert result != "" or result is not None
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_uses_injected_router(self, client: TestClient):
        """Verify /chat uses properly initialized router."""
        response = client.post(
            "/api/v1/chat/message",
            json={"message": "status do TWS_MASTER", "session_id": "test123"},
            headers={"X-Routing-Mode": "agentic"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have actual response, not empty
        assert data.get("message") or data.get("response")
```

---

## Plano de Execução

### Fase 1: Correções Críticas (Dias 1-2)

```
┌────────────────────────────────────────────────────────────────┐
│ DIA 1: Bugs #2 e #3 (mais simples, desbloqueiam testes)        │
├────────────────────────────────────────────────────────────────┤
│ □ Corrigir parâmetros em _handle_status (Bug #2)               │
│ □ Criar providers no DIContainer (Bug #3)                      │
│ □ Criar dependencies.py com get_hybrid_router                  │
│ □ Atualizar chat.py para usar Depends()                        │
│ □ Executar testes unitários                                    │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ DIA 2: Bug #1 (mais complexo, requer cuidado com async)        │
├────────────────────────────────────────────────────────────────┤
│ □ Implementar _run_async_retrieval helper                      │
│ □ Corrigir search_knowledge_base para chamar retriever         │
│ □ Adicionar tratamento de contexto async/sync                  │
│ □ Normalizar formato de resultados                             │
│ □ Testes de integração RAG                                     │
└────────────────────────────────────────────────────────────────┘
```

### Fase 2: Validação (Dia 3)

```
┌────────────────────────────────────────────────────────────────┐
│ VALIDAÇÃO END-TO-END                                           │
├────────────────────────────────────────────────────────────────┤
│ □ Testar RAG_ONLY mode com query real                          │
│ □ Testar AGENTIC mode com entidades (workstation, job)         │
│ □ Testar agents Agno retornam respostas reais                  │
│ □ Testar fallbacks funcionam quando retriever indisponível     │
│ □ Verificar logs sem TypeErrors                                │
│ □ Load test básico /chat endpoint                              │
└────────────────────────────────────────────────────────────────┘
```

### Fase 3: Prevenção (Dias 4-5)

```
┌────────────────────────────────────────────────────────────────┐
│ PREVENÇÃO DE REGRESSÃO                                         │
├────────────────────────────────────────────────────────────────┤
│ □ Adicionar validação de parâmetros no ParallelExecutor        │
│ □ Criar teste que verifica Router tem AgentManager             │
│ □ Criar teste que verifica RAGTool retorna resultados          │
│ □ Adicionar CI check para stubs comentados                     │
│ □ Documentar convenção de nomes de parâmetros                  │
└────────────────────────────────────────────────────────────────┘
```

---

## Checklist de Validação Final

### Bug #1: RAG Retrieval
- [ ] `search_knowledge_base` não retorna `{"results": []}`
- [ ] Funciona dentro de contexto async (FastAPI)
- [ ] Funciona fora de contexto async (CLI)
- [ ] Timeout é tratado graciosamente
- [ ] Erros de conexão não crasham

### Bug #2: Parâmetros
- [ ] `get_workstation_status(workstation_name=...)` funciona
- [ ] `get_job_log(job_name=..., max_lines=...)` funciona
- [ ] Sem TypeErrors no log
- [ ] Validação previne futuros erros

### Bug #3: Dependency Injection
- [ ] `DIContainer.get_hybrid_router()` retorna router com AgentManager
- [ ] `/chat` endpoint usa router injetado
- [ ] Agents Agno respondem (não retornam "")
- [ ] Startup pre-aquece router

---

## Métricas de Sucesso

| Métrica | Antes | Depois | Target |
|---------|-------|--------|--------|
| RAG_ONLY queries com resultados | 0% | >80% | ≥90% |
| AGENTIC queries sem TypeError | 0% | 100% | 100% |
| Agents Agno com resposta real | 0% | >90% | ≥95% |
| Tempo médio /chat response | - | <2s | <1.5s |

---

## Rollback Plan

Se as correções causarem regressão:

1. **Bug #1**: Reverter para stub comentado (comportamento atual)
2. **Bug #2**: Reverter para parâmetros originais (erro é preferível a comportamento errado)
3. **Bug #3**: Reverter para `HybridRouter()` sem argumento

```bash
# Git tags para cada correção
git tag pre-bug1-fix
git tag pre-bug2-fix  
git tag pre-bug3-fix
```

---

## Referências

- Código fonte analisado: `resync v5.7.0`
- Arquivos afetados:
  - `resync/core/specialists/tools.py`
  - `resync/core/agent_router.py`
  - `resync/fastapi_app/api/v1/routes/chat.py`
  - `resync/core/di_container.py`
  - `resync/api/dependencies.py`
