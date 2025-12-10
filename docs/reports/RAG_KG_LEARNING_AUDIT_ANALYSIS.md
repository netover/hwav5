# Análise da Arquitetura RAG + KG + Aprendizado + Audit

## 1. Estado Atual - Visão Geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITETURA ATUAL DO RESYNC                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │    RAG      │    │  Knowledge  │    │   Audit     │    │  Learning   │   │
│  │  (Qdrant)   │    │    Graph    │    │   System    │    │   Store     │   │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘   │
│         │                  │                  │                  │          │
│         │                  │                  │                  │          │
│         └────────┬─────────┴─────────────────┴──────────────────┘          │
│                  │                                                          │
│                  ▼                                                          │
│         ┌─────────────────┐                                                 │
│         │   HybridRAG     │  ← Único ponto de integração (KG + RAG)        │
│         │   QueryRouter   │                                                 │
│         └─────────────────┘                                                 │
│                                                                              │
│  ❌ Problemas:                                                               │
│  - Componentes isolados (silos)                                             │
│  - Feedback não retroalimenta RAG                                           │
│  - Audit não alimenta Knowledge Graph                                       │
│  - Learning Store desconectado                                              │
│  - Sem Active Learning                                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Análise por Componente

### 2.1 RAG (Qdrant)

**Localização:** `resync/RAG/microservice/`

**Pontos Fortes:**
- ✅ Embeddings com chunking
- ✅ Busca vetorial eficiente
- ✅ Re-ranking básico (cosine)

**Pontos Fracos:**
| Problema | Impacto | Severidade |
|----------|---------|------------|
| Sem feedback loop | Respostas ruins não melhoram | 🔴 Alto |
| Re-ranking simplista | Relevância subótima | 🟡 Médio |
| Sem query expansion | Perde sinônimos/contexto | 🟡 Médio |
| Cache não considera feedback | Mesmos erros repetidos | 🟡 Médio |

**Código Atual:**
```python
# resync/RAG/microservice/core/retriever.py
class RagRetriever:
    async def retrieve(self, query, top_k=10):
        vec = await self.embedder.embed(query)
        hits = await self.store.query(vector=vec, ...)
        # ❌ Não considera histórico de feedback
        # ❌ Não aprende com interações passadas
        return hits
```

---

### 2.2 Knowledge Graph (NetworkX + PostgreSQL)

**Localização:** `resync/core/knowledge_graph/`

**Pontos Fortes:**
- ✅ Arquitetura híbrida (NetworkX + PostgreSQL)
- ✅ ReadWriteLock para concorrência
- ✅ Extração de triplets com LLM
- ✅ Human-in-the-loop (ExtractedTriplet)
- ✅ Cache com TTL

**Pontos Fracos:**
| Problema | Impacto | Severidade |
|----------|---------|------------|
| Triplets pending não são processados automaticamente | Backlog cresce | 🟡 Médio |
| Sem integração com audit | Perde insights de erros | 🔴 Alto |
| Sem aprendizado de novas relações | Grafo estático | 🟡 Médio |

**Código Atual:**
```python
# resync/core/knowledge_graph/extractor.py
async def extract_from_text(..., auto_approve=False):
    triplets = await self._extract_with_llm(text)
    # ❌ Se auto_approve=False, triplets ficam em "pending"
    # ❌ Não há processo automático de review
    return triplets
```

---

### 2.3 Sistema de Audit

**Localização:** `resync/core/audit_log.py`, `resync/core/ia_auditor.py`

**Pontos Fortes:**
- ✅ Auditor LLM avalia respostas
- ✅ Queue para revisão humana
- ✅ Confidence thresholds
- ✅ Locking distribuído

**Pontos Fracos:**
| Problema | Impacto | Severidade |
|----------|---------|------------|
| Audit não alimenta KG | Conhecimento perdido | 🔴 Alto |
| Feedback humano não melhora RAG | Mesmos erros | 🔴 Alto |
| Sem métricas de qualidade por tópico | Cego para gaps | 🟡 Médio |

**Código Atual:**
```python
# resync/core/ia_auditor.py
async def _perform_action_on_memory(mem, analysis):
    if analysis.get("is_incorrect"):
        # ❌ Apenas deleta/flag memória
        # ❌ Não cria conhecimento a partir do erro
        # ❌ Não melhora RAG embeddings
        await kg.atomic_check_and_delete(memory_id)
```

---

### 2.4 Sistema de Learning

**Localização:** `resync/core/tws_multi/learning.py`, `resync/core/context_store.py`

**Pontos Fortes:**
- ✅ Aprende padrões de jobs
- ✅ Predição de duração
- ✅ Histórico de resoluções
- ✅ Armazena feedback do usuário

**Pontos Fracos:**
| Problema | Impacto | Severidade |
|----------|---------|------------|
| Totalmente isolado | Não melhora respostas | 🔴 Alto |
| Não alimenta RAG | Respostas genéricas | 🔴 Alto |
| Não alimenta KG | Padrões não viram grafo | 🔴 Alto |
| Sem Active Learning | Não pede ajuda | 🟡 Médio |

---

## 3. Gaps Críticos Identificados

### 3.1 Falta de Feedback Loop Fechado

```
Atual:
User Query → RAG → Response → Feedback → (nada acontece)

Ideal:
User Query → RAG → Response → Feedback → Ajusta Embeddings → Melhora RAG
```

### 3.2 Componentes em Silos

```
Atual:                              Ideal:
┌─────┐  ┌─────┐  ┌─────┐          ┌─────────────────────────┐
│ RAG │  │ KG  │  │Audit│          │   Unified Learning      │
└─────┘  └─────┘  └─────┘          │   ┌─────────────────┐   │
   ↓        ↓        ↓              │   │ RAG ←→ KG ←→   │   │
 (nada)  (nada)   (log)            │   │ Audit ←→ Learn │   │
                                    │   └─────────────────┘   │
                                    └─────────────────────────┘
```

### 3.3 Conhecimento Perdido

| Fonte | Conhecimento | Destino Atual | Destino Ideal |
|-------|-------------|---------------|---------------|
| Audit LLM | Erros identificados | Log apenas | KG + RAG embeddings |
| User Feedback | Qualidade resposta | context_store | RAG rerank weights |
| Job Patterns | Duração/falhas | learning.py | KG + RAG context |
| Human Review | Triplets aprovados | kg_extracted | Automatic training |

---

## 4. Arquitetura Proposta - Continual Learning

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITETURA PROPOSTA - CLOSED LOOP                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│                         ┌─────────────────────┐                               │
│                         │    Query Router     │                               │
│                         │  (LLM + Regex)      │                               │
│                         └──────────┬──────────┘                               │
│                                    │                                          │
│              ┌─────────────────────┼─────────────────────┐                   │
│              │                     │                     │                    │
│              ▼                     ▼                     ▼                    │
│    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│    │      RAG        │  │  Knowledge      │  │   Learning      │            │
│    │    (Qdrant)     │  │    Graph        │  │    Context      │            │
│    │                 │  │  (NetworkX+PG)  │  │                 │            │
│    │ ┌─────────────┐ │  │                 │  │ ┌─────────────┐ │            │
│    │ │ Feedback    │ │  │                 │  │ │ Job         │ │            │
│    │ │ Embeddings  │◀┼──┼─────────────────┼──┼─│ Patterns    │ │            │
│    │ └─────────────┘ │  │                 │  │ └─────────────┘ │            │
│    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘            │
│             │                    │                    │                      │
│             └────────────┬───────┴────────────────────┘                      │
│                          │                                                   │
│                          ▼                                                   │
│             ┌─────────────────────────┐                                      │
│             │    Response Generator   │                                      │
│             └──────────┬──────────────┘                                      │
│                        │                                                     │
│                        ▼                                                     │
│             ┌─────────────────────────┐                                      │
│             │    Audit + Feedback     │                                      │
│             │    ┌───────────────┐    │                                      │
│             │    │ IA Auditor    │    │                                      │
│             │    └───────┬───────┘    │                                      │
│             │            │            │                                      │
│             │    ┌───────▼───────┐    │                                      │
│             │    │ User Feedback │    │                                      │
│             │    └───────┬───────┘    │                                      │
│             └────────────┼────────────┘                                      │
│                          │                                                   │
│  ┌───────────────────────┼────────────────────────────────────────────────┐ │
│  │                       ▼              FEEDBACK LOOP                      │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │                    Continual Learning Engine                     │   │ │
│  │  │                                                                  │   │ │
│  │  │  1. Feedback → Adjust RAG embeddings (positive/negative)        │   │ │
│  │  │  2. Errors → Extract triplets → Add to KG                       │   │ │
│  │  │  3. Patterns → Update Learning Context → Enrich RAG             │   │ │
│  │  │  4. Low confidence → Active Learning → Human review             │   │ │
│  │  │                                                                  │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Melhorias Específicas Propostas

### 5.1 RAG com Feedback Embeddings

```python
# PROPOSTO: resync/RAG/microservice/core/feedback_embeddings.py

class FeedbackAwareRetriever:
    """Retriever que aprende com feedback."""
    
    async def retrieve(self, query: str, user_id: str) -> List[Document]:
        # 1. Retrieve normal
        candidates = await self.base_retriever.retrieve(query)
        
        # 2. Apply feedback-based reranking
        candidates = await self._apply_feedback_weights(
            candidates, query, user_id
        )
        
        return candidates
    
    async def _apply_feedback_weights(self, candidates, query, user_id):
        """Ajusta scores baseado em feedback histórico."""
        for doc in candidates:
            # Buscar feedback histórico para documentos similares
            feedback_score = await self.feedback_store.get_document_score(
                doc.id, query_embedding
            )
            # Boost/penalize baseado em feedback
            doc.score = doc.score * (1 + feedback_score * 0.3)
        
        return sorted(candidates, key=lambda x: x.score, reverse=True)
    
    async def record_feedback(self, query: str, doc_id: str, rating: int):
        """Registra feedback para aprendizado."""
        query_embedding = await self.embedder.embed(query)
        await self.feedback_store.record(
            query_embedding=query_embedding,
            doc_id=doc_id,
            rating=rating  # -1 (ruim), 0 (neutro), +1 (bom)
        )
```

### 5.2 Audit → Knowledge Graph Pipeline

```python
# PROPOSTO: resync/core/audit_to_kg_pipeline.py

class AuditToKGPipeline:
    """Converte insights de audit em conhecimento no KG."""
    
    async def process_audit_result(self, audit_result: AuditResult):
        """Quando audit identifica erro, extrai conhecimento."""
        
        if audit_result.is_incorrect:
            # Extrair o que estava errado
            error_triplets = await self.extractor.extract_error_pattern(
                query=audit_result.user_query,
                incorrect_response=audit_result.agent_response,
                reason=audit_result.reason
            )
            
            # Adicionar ao KG como "NÃO_DEVE_FAZER" ou "ERRO_COMUM"
            for triplet in error_triplets:
                await self.kg.add_edge(
                    source=triplet.subject,
                    target=triplet.object,
                    relation_type="INCORRECT_ASSOCIATION",
                    properties={
                        "error_reason": audit_result.reason,
                        "confidence": audit_result.confidence,
                    }
                )
            
            # Notificar RAG para down-rank documentos relacionados
            await self.rag_feedback.penalize_documents(
                query=audit_result.user_query,
                penalty_factor=0.5
            )
```

### 5.3 Active Learning para Casos Incertos

```python
# PROPOSTO: resync/core/active_learning.py

class ActiveLearningManager:
    """Identifica casos onde o sistema precisa de ajuda humana."""
    
    CONFIDENCE_THRESHOLD = 0.6  # Abaixo disso, pedir ajuda
    
    async def should_request_human_review(
        self, 
        query: str,
        response: str,
        classification_confidence: float,
        rag_similarity_score: float,
    ) -> bool:
        """Decide se deve pedir revisão humana."""
        
        # Critérios para Active Learning
        reasons = []
        
        # 1. Classificação de baixa confiança
        if classification_confidence < self.CONFIDENCE_THRESHOLD:
            reasons.append("low_classification_confidence")
        
        # 2. Documentos RAG pouco relevantes
        if rag_similarity_score < 0.7:
            reasons.append("low_rag_relevance")
        
        # 3. Query sem entidades reconhecidas
        entities = self.entity_extractor.extract(query)
        if not entities.get("jobs") and not entities.get("workstations"):
            reasons.append("no_entities_found")
        
        # 4. Query similar a erros passados
        similar_errors = await self.audit_store.find_similar_errors(query)
        if similar_errors:
            reasons.append("similar_to_past_errors")
        
        if reasons:
            # Enfileirar para revisão
            await self.review_queue.add({
                "query": query,
                "response": response,
                "reasons": reasons,
                "timestamp": datetime.utcnow(),
            })
            return True
        
        return False
```

### 5.4 Learning Store → RAG Context Enrichment

```python
# PROPOSTO: resync/core/context_enrichment.py

class ContextEnricher:
    """Enriquece queries RAG com contexto aprendido."""
    
    async def enrich_query(
        self, 
        query: str, 
        instance_id: str
    ) -> str:
        """Adiciona contexto do Learning Store à query."""
        
        # 1. Extrair entidades da query
        entities = self.entity_extractor.extract(query)
        job_name = entities.get("jobs", [None])[0]
        
        if not job_name:
            return query
        
        # 2. Buscar padrões aprendidos
        learning_store = get_learning_store(instance_id)
        pattern = learning_store.get_job_pattern(job_name, "*")
        
        if pattern:
            # 3. Enriquecer query com contexto
            context_parts = []
            
            if pattern.failure_rate > 0.1:
                context_parts.append(
                    f"(Job com taxa de falha de {pattern.failure_rate:.1%})"
                )
            
            if pattern.common_failure_reasons:
                context_parts.append(
                    f"(Erros comuns: {', '.join(pattern.common_failure_reasons[:3])})"
                )
            
            if pattern.avg_duration_seconds > 3600:
                context_parts.append(
                    f"(Job de longa duração: ~{pattern.avg_duration_seconds/60:.0f}min)"
                )
            
            if context_parts:
                return f"{query} {' '.join(context_parts)}"
        
        return query
```

---

## 6. Roadmap de Implementação

### Fase 1: Feedback Loop Básico (3 dias)
| Tarefa | Arquivos | Esforço |
|--------|----------|---------|
| Feedback Store para RAG | `RAG/feedback_store.py` | 4h |
| Feedback-aware reranking | `RAG/retriever.py` | 4h |
| API de feedback | `api/feedback.py` | 2h |
| Testes | `tests/` | 4h |

### Fase 2: Audit → KG Pipeline (2 dias)
| Tarefa | Arquivos | Esforço |
|--------|----------|---------|
| Pipeline audit → triplets | `core/audit_to_kg.py` | 6h |
| Integração com ia_auditor | `core/ia_auditor.py` | 4h |
| Testes | `tests/` | 4h |

### Fase 3: Context Enrichment (2 dias)
| Tarefa | Arquivos | Esforço |
|--------|----------|---------|
| Context Enricher | `core/context_enrichment.py` | 4h |
| Integração Learning → RAG | `RAG/retriever.py` | 4h |
| Testes | `tests/` | 4h |

### Fase 4: Active Learning (2 dias)
| Tarefa | Arquivos | Esforço |
|--------|----------|---------|
| Active Learning Manager | `core/active_learning.py` | 6h |
| Review queue UI | `api/review.py` | 4h |
| Testes | `tests/` | 4h |

---

## 7. Métricas de Sucesso

| Métrica | Atual | Meta |
|---------|-------|------|
| Feedback positivo (%) | ~70% (estimado) | >85% |
| Respostas flagged pelo audit | ~15% (estimado) | <5% |
| Tempo de resolução de issues | Manual | Auto-sugerido |
| Triplets pendentes no KG | Crescente | Processados em <24h |
| Queries com Active Learning | 0% | <10% (apenas casos difíceis) |

---

## 8. Conclusão

### O que está bom:
- ✅ Arquitetura modular bem separada
- ✅ KG com ReadWriteLock e cache TTL
- ✅ Audit com LLM funcionando
- ✅ Learning Store por instância

### O que precisa melhorar:
- ❌ **Componentes em silos** - não se comunicam
- ❌ **Feedback não retroalimenta** - conhecimento perdido
- ❌ **Sem Active Learning** - sistema não pede ajuda
- ❌ **RAG estático** - não aprende com uso

### Prioridade:
1. 🔴 **Feedback Loop RAG** - Maior impacto imediato
2. 🔴 **Audit → KG Pipeline** - Converte erros em conhecimento
3. 🟡 **Context Enrichment** - Melhora relevância
4. 🟡 **Active Learning** - Reduz erros em casos difíceis
