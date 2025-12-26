# Análise do Hybrid Retriever - Resync v5.2.3.21

**Data:** 2024-12-16  
**Objetivo:** Otimizar pesos e configurações do Hybrid Retriever para domínio TWS

---

## 📊 Estado Atual

### Configuração de Pesos

```python
# hybrid_retriever.py - HybridRetrieverConfig
vector_weight: float = 0.5   # Busca semântica
bm25_weight: float = 0.5     # Busca por keywords

# Sem variável de ambiente para configurar!
# Sem ajuste dinâmico baseado no tipo de query!
```

### Problemas Identificados

| Problema | Impacto | Severidade |
|----------|---------|------------|
| Pesos fixos 50/50 | Query "job AWSBH001" tem mesmo peso semântico que exato | 🔴 Alto |
| Sem config via .env | Não é possível ajustar sem código | 🟡 Médio |
| Sem ajuste dinâmico | Todas as queries tratadas igual | 🔴 Alto |
| Tokenização incompleta | Códigos de erro (RC=8) não tokenizados bem | 🟡 Médio |

---

## 🎯 Sugestões de Ajuste

### 1. Pesos Dinâmicos por Tipo de Query

**Lógica:** Queries com códigos exatos (jobs, erros) devem priorizar BM25

```python
# SUGESTÃO: Adicionar ao HybridRetrieverConfig
class QueryWeightStrategy(Enum):
    EXACT_MATCH = "exact"      # BM25: 0.8, Vector: 0.2
    SEMANTIC = "semantic"      # BM25: 0.2, Vector: 0.8
    BALANCED = "balanced"      # BM25: 0.5, Vector: 0.5

# Padrões TWS que indicam EXACT_MATCH:
EXACT_MATCH_PATTERNS = [
    r'\b[A-Z]{2,}[0-9_]+\b',        # AWSBH001, BATCH_001
    r'\bRC[=:]\s*\d+\b',            # RC=8, RC: 12
    r'\bABEND\s*[A-Z0-9]+\b',       # ABEND S0C7
    r'\b[A-Z]{2,}\d{3,}\b',         # WS001, SRV123
    r'\bEQQQ\w+\b',                 # EQQQ... (mensagens TWS)
    r'\bAWSB\w+\b',                 # AWSB... (jobs TWS)
]
```

**Pesos Recomendados por Cenário:**

| Tipo de Query | Exemplo | BM25 | Vector |
|---------------|---------|------|--------|
| Job/código exato | "status job AWSBH001" | **0.8** | 0.2 |
| Erro específico | "RC=8 no job BACKUP" | **0.7** | 0.3 |
| Conceitual | "jobs lentos ontem" | 0.3 | **0.7** |
| Troubleshooting | "como resolver ABEND" | 0.4 | **0.6** |
| Documentação | "como configurar agente" | 0.2 | **0.8** |
| Misto | "por que BATCH001 está lento" | **0.5** | **0.5** |

---

### 2. Configuração via Environment Variables

**Adicionar ao `settings.py`:**

```python
# Hybrid Retriever Weights
hybrid_vector_weight: float = Field(
    default=0.5,
    ge=0.0,
    le=1.0,
    description="Peso da busca vetorial no hybrid retriever (0-1)",
)

hybrid_bm25_weight: float = Field(
    default=0.5,
    ge=0.0,
    le=1.0,
    description="Peso da busca BM25 no hybrid retriever (0-1)",
)

hybrid_auto_weight: bool = Field(
    default=True,
    description="Ajustar pesos automaticamente baseado no tipo de query",
)
```

**Adicionar ao `.env.example`:**

```bash
# Hybrid Retriever (v5.2.3.22)
# Pesos da busca híbrida (devem somar 1.0)
HYBRID_VECTOR_WEIGHT=0.5
HYBRID_BM25_WEIGHT=0.5
HYBRID_AUTO_WEIGHT=true  # Ajuste automático por tipo de query
```

---

### 3. Melhorar Tokenização para TWS

**Problema atual:** Códigos como "RC=8" ou "EQQQ0001" não são bem tokenizados

**Sugestão - Adicionar ao `_tokenize()`:**

```python
def _tokenize(self, text: str) -> list[str]:
    """
    Tokenize text for BM25 indexing.
    v5.2.3.22: Enhanced for TWS patterns.
    """
    if not text:
        return []

    # Lowercase
    text = text.lower()

    # === v5.2.3.22: PRE-PROCESS TWS PATTERNS ===
    
    # Normalize RC codes: "RC=8" -> "rc_8" and "rc8"
    text = re.sub(r'rc[=:]\s*(\d+)', r'rc_\1 rc\1', text)
    
    # Normalize ABEND codes: "ABEND S0C7" -> "abend_s0c7"
    text = re.sub(r'abend\s+([a-z0-9]+)', r'abend_\1', text)
    
    # Normalize message IDs: "EQQQ001I" -> keep as-is (already good)
    
    # === END TWS PATTERNS ===

    # Standard tokenization
    tokens = re.findall(r"[a-z0-9_\-]+", text)

    # Expand compound names
    expanded = []
    for token in tokens:
        expanded.append(token)
        if "_" in token:
            expanded.extend(token.split("_"))
        if "-" in token:
            expanded.extend(token.split("-"))

    return [t for t in expanded if len(t) >= 2]
```

---

### 4. Boost para Campos Específicos TWS

**Problema:** Metadata como `job_name` tem mesmo peso que `content`

**Sugestão - Field Boosting:**

```python
# No build_index(), adicionar boost para campos TWS:

FIELD_BOOSTS = {
    "job_name": 3.0,      # Job name é muito importante
    "workstation": 2.0,   # Workstation também
    "error_code": 2.5,    # Códigos de erro
    "job_stream": 1.5,    # Job stream
    "content": 1.0,       # Conteúdo padrão
}

def build_index(self, documents, text_field="content"):
    for doc_idx, doc in enumerate(documents):
        metadata = doc.get("metadata", {}) or {}
        
        # Indexar com boost
        for field, boost in FIELD_BOOSTS.items():
            value = metadata.get(field, "") or ""
            if value:
                tokens = self._tokenize(value)
                for token in tokens:
                    # Aplicar boost na frequência
                    term_freqs[token] += int(boost)
```

---

### 5. Integrar Classificação de Query com Pesos

**Problema:** `QueryClassifier` existe mas não afeta pesos do BM25/Vector

**Sugestão - Conectar os sistemas:**

```python
# No método retrieve(), antes da fusão:

async def retrieve(self, query: str, top_k: int = 10, ...):
    # === v5.2.3.22: AJUSTE DINÂMICO DE PESOS ===
    if self.config.auto_weight:
        weights = self._get_dynamic_weights(query)
    else:
        weights = (self.config.vector_weight, self.config.bm25_weight)
    
    # ... resto do código ...
    
    results = self._reciprocal_rank_fusion(
        [vector_results, bm25_results],
        list(weights),  # Usar pesos dinâmicos
    )

def _get_dynamic_weights(self, query: str) -> tuple[float, float]:
    """Determina pesos baseado no tipo de query."""
    
    # Detectar padrões de match exato
    exact_patterns = [
        r'\b[A-Z]{2,}[0-9_]+\b',    # AWSBH001
        r'\bRC[=:]\s*\d+\b',         # RC=8
        r'\bABEND\s*[A-Z0-9]+\b',    # ABEND S0C7
    ]
    
    has_exact = any(re.search(p, query, re.IGNORECASE) for p in exact_patterns)
    
    # Detectar padrões semânticos
    semantic_patterns = [
        r'\b(como|how|why|por que)\b',
        r'\b(resolver|fix|solve)\b',
        r'\b(configurar|configure|setup)\b',
    ]
    
    has_semantic = any(re.search(p, query, re.IGNORECASE) for p in semantic_patterns)
    
    if has_exact and not has_semantic:
        return (0.2, 0.8)  # Priorizar BM25
    elif has_semantic and not has_exact:
        return (0.8, 0.2)  # Priorizar Vector
    else:
        return (0.5, 0.5)  # Balanceado
```

---

## 📋 Plano de Implementação

### Fase 1: Quick Wins (v5.2.3.22) ✅ CONCLUÍDA
1. ✅ Adicionar variáveis de ambiente para pesos
2. ✅ Implementar `_get_dynamic_weights()` básico
3. ✅ Melhorar tokenização para RC codes

**Esforço:** ~2h | **Impacto:** Alto

### Fase 2: Field Boosting (v5.2.3.23) ✅ CONCLUÍDA
1. ✅ Implementar boost por campo
2. ✅ Adicionar mais padrões TWS
3. ✅ Testes com queries reais

**Esforço:** ~4h | **Impacto:** Médio

### Fase 3: Integração Completa (v5.2.3.24) ✅ CONCLUÍDA
1. ✅ Cache de classificações com TTL
2. ✅ Métricas de performance por tipo
3. ✅ Remoção do Agno (bônus)

**Esforço:** ~8h | **Impacto:** Alto

---

## 🧪 Como Validar

```python
# Script de teste
test_queries = [
    # Deve priorizar BM25 (exact match)
    ("status job AWSBH001", "high_bm25"),
    ("erro RC=8 no batch", "high_bm25"),
    ("ABEND S0C7 no job PAYROLL", "high_bm25"),
    
    # Deve priorizar Vector (semântico)
    ("como configurar agente TWS", "high_vector"),
    ("jobs lentos no ambiente de produção", "high_vector"),
    ("melhores práticas para scheduling", "high_vector"),
    
    # Deve ser balanceado
    ("por que BATCH001 está falhando", "balanced"),
    ("troubleshooting job PAYMENT_DAILY", "balanced"),
]

for query, expected in test_queries:
    weights = retriever._get_dynamic_weights(query)
    print(f"Query: {query}")
    print(f"  Weights: BM25={weights[1]:.1f}, Vector={weights[0]:.1f}")
    print(f"  Expected: {expected}")
```

---

## 📊 Métricas de Sucesso

| Métrica | Antes | Depois (esperado) |
|---------|-------|-------------------|
| Precision@5 (exact match) | ~60% | 85%+ |
| Precision@5 (semantic) | ~70% | 75%+ |
| Latência média | 150ms | 160ms (+10ms) |
| Queries sem resultado | 15% | 5% |

---

## ⚠️ Riscos

1. **Regressão em queries ambíguas** - Mitigar com fallback para 50/50
2. **Overhead de classificação** - Cache de padrões regex já compilados
3. **Complexidade de debug** - Adicionar logging dos pesos usados

---

## 📚 Referências

- [BM25 vs Dense Retrieval](https://arxiv.org/abs/2104.08663)
- [Hybrid Search Best Practices](https://www.pinecone.io/learn/hybrid-search-intro/)
- [RRF Paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
