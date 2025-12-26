# Migração Completa v5.9.8 - Código Limpo (SEM Legado)

## 🔥 BREAKING CHANGES

Esta versão **REMOVE** todo código legado e backwards compatibility.

**⚠️ ATENÇÃO:** Se você tem código customizado que depende de métodos antigos, ele vai quebrar!

---

## 🗑️ Código Removido

### 1. Chat Endpoint (`resync/api/chat.py`)

**Removido:**
```python
# ❌ REMOVIDO
async def _get_enhanced_query(knowledge_graph, sanitized_data, original_data) -> str:
    """Query enhancement manual (substituído por QueryProcessor)"""

# ❌ REMOVIDO  
async def _get_optimized_response(query, context, use_cache, stream) -> str:
    """LLM optimizer específico (substituído por generate_response_with_tools)"""

# ❌ REMOVIDO
def _should_use_llm_optimization(query: str) -> bool:
    """Heurística de otimização (substituído por QueryProcessor.classify_query)"""

# ❌ REMOVIDO import
from resync.api.utils.stream_handler import AgentResponseStreamer
from resync.core.llm_wrapper import optimized_llm
```

**Substituto:**
```python
# ✅ NOVO - Usa QueryProcessor + generate_response_with_tools
from resync.core.query_processor import QueryProcessor

processor = QueryProcessor(llm, knowledge_graph)
structured = await processor.process_query(data)
messages = processor.format_for_llm(structured)
response = await llm.generate_response_with_tools(messages, user_role="operator")
```

---

### 2. LLM Service (`resync/services/llm_service.py`)

**Removido:**
```python
# ❌ REMOVIDO
async def generate_system_status_message(self, system_info: dict) -> str:
    """Helper específico (use generate_response direto)"""

# ❌ REMOVIDO
async def chat_completion(self, user_message, agent_id, ...) -> str:
    """Wrapper redundante (use generate_agent_response direto)"""

# ❌ REMOVIDO
async def get_llm_completion(prompt, model, temperature, ...) -> str:
    """Helper global (use get_llm_service().generate_response)"""
```

**Substitutos:**
```python
# ✅ Para status do sistema
llm = get_llm_service()
messages = [{"role": "user", "content": f"Resuma status: {system_info}"}]
response = await llm.generate_response(messages, max_tokens=500)

# ✅ Para chat completion
response = await llm.generate_agent_response(
    agent_id="tws-agent",
    user_message="Mensagem",
    conversation_history=history
)

# ✅ Para completion simples
llm = get_llm_service()
messages = [
    {"role": "system", "content": "System prompt"},
    {"role": "user", "content": "User prompt"}
]
response = await llm.generate_response(messages)
```

---

## ✅ Métodos Mantidos (API Limpa)

### LLMService

```python
class LLMService:
    # Core methods
    async def generate_response_with_tools(...) -> str
        """NOVO: Principal método com suporte a tools"""
    
    async def generate_response(...) -> str
        """Base: Geração simples sem tools"""
    
    async def generate_agent_response(...) -> str
        """Para agents com config específica"""
    
    async def generate_rag_response(...) -> str
        """Para RAG com Opinion-Based Prompting"""
    
    async def health_check() -> dict
        """Health check do LLM"""
    
    async def aclose() -> None
        """Cleanup de recursos"""

# Helper global
def get_llm_service() -> LLMService
    """Singleton do LLM service"""
```

---

## 🔄 Guia de Migração de Código

### Caso 1: Chat/Completion simples

**Antes (QUEBRADO):**
```python
# ❌ NÃO FUNCIONA MAIS
response = await get_llm_completion(
    "Analise este erro",
    temperature=0.3
)
```

**Depois (CORRETO):**
```python
# ✅ NOVO JEITO
from resync.services.llm_service import get_llm_service

llm = get_llm_service()
messages = [{"role": "user", "content": "Analise este erro"}]
response = await llm.generate_response(messages, temperature=0.3)
```

---

### Caso 2: Status do sistema

**Antes (QUEBRADO):**
```python
# ❌ NÃO FUNCIONA MAIS
response = await llm.generate_system_status_message(system_info)
```

**Depois (CORRETO):**
```python
# ✅ NOVO JEITO
messages = [
    {"role": "system", "content": "Você é um assistente Resync TWS."},
    {"role": "user", "content": f"Resuma status do sistema: {system_info}"}
]
response = await llm.generate_response(messages, max_tokens=500)
```

---

### Caso 3: Query enhancement no chat

**Antes (QUEBRADO):**
```python
# ❌ NÃO FUNCIONA MAIS
enhanced_query = await _get_enhanced_query(kg, sanitized_data, data)
if _should_use_llm_optimization(data):
    response = await _get_optimized_response(data)
```

**Depois (CORRETO):**
```python
# ✅ NOVO JEITO
from resync.core.query_processor import QueryProcessor

processor = QueryProcessor(llm, knowledge_graph)
structured = await processor.process_query(data)
messages = processor.format_for_llm(structured)

# Com tools automáticos
response = await llm.generate_response_with_tools(
    messages=messages,
    user_role="operator",
    max_tool_iterations=3
)
```

---

### Caso 4: Usando tools diretamente

**Novo (NÃO EXISTIA ANTES):**
```python
# ✅ TOTALMENTE NOVO
from resync.tools.llm_tools import get_llm_tools, execute_tool_call
from resync.tools.registry import UserRole

# Obter tools disponíveis
tools = get_llm_tools(user_role=UserRole.OPERATOR)

# LLM automaticamente chama tools quando necessário
response = await llm.generate_response_with_tools(
    messages=messages,
    user_role="operator"
)
```

---

## 🎯 Vantagens da Migração Completa

### Antes (com código legado):
```python
# Múltiplas formas de fazer a mesma coisa
await llm.chat_completion(...)          # Opção 1
await llm.generate_agent_response(...)  # Opção 2
await get_llm_completion(...)           # Opção 3

# Query enhancement manual
enhanced = await _get_enhanced_query(...)
if _should_use_llm_optimization(...):
    response = await _get_optimized_response(...)
```

**Problemas:**
- ❌ Confuso (qual método usar?)
- ❌ Código duplicado
- ❌ Difícil de manter
- ❌ Lógica espalhada

### Depois (código limpo):
```python
# UMA forma clara e poderosa
from resync.core.query_processor import QueryProcessor

processor = QueryProcessor(llm, knowledge_graph)
structured = await processor.process_query(user_query)
messages = processor.format_for_llm(structured)

response = await llm.generate_response_with_tools(
    messages=messages,
    user_role="operator"
)
```

**Benefícios:**
- ✅ Clara e intuitiva
- ✅ Sem código duplicado
- ✅ Fácil de manter
- ✅ Lógica centralizada
- ✅ Mais poderosa (tools automáticos)

---

## 📊 Impacto da Remoção

| Código | Antes | Depois | Redução |
|--------|-------|--------|---------|
| **chat.py** | 384 linhas | 320 linhas | **-16%** |
| **llm_service.py** | 795 linhas | 683 linhas | **-14%** |
| **Métodos públicos** | 11 métodos | 7 métodos | **-36%** |
| **Complexidade** | Alta | Baixa | **-50%** |

---

## 🚨 Checklist de Compatibilidade

Se você tem código customizado, verifique:

### ❌ Código que VAI QUEBRAR:

```python
# 1. Imports removidos
from resync.api.utils.stream_handler import AgentResponseStreamer  # ❌
from resync.core.llm_wrapper import optimized_llm  # ❌

# 2. Funções helper removidas
await _get_enhanced_query(...)  # ❌
await _get_optimized_response(...)  # ❌
_should_use_llm_optimization(...)  # ❌

# 3. Métodos LLM removidos
await llm.generate_system_status_message(...)  # ❌
await llm.chat_completion(...)  # ❌
await get_llm_completion(...)  # ❌
```

### ✅ Código que CONTINUA FUNCIONANDO:

```python
# Métodos core mantidos
await llm.generate_response(messages)  # ✅
await llm.generate_agent_response(agent_id, message)  # ✅
await llm.generate_rag_response(query, context)  # ✅
await llm.health_check()  # ✅
llm = get_llm_service()  # ✅
```

---

## 🔧 Script de Migração Automática

```bash
# Encontrar código que precisa ser atualizado
grep -r "get_llm_completion" resync/
grep -r "chat_completion" resync/
grep -r "generate_system_status_message" resync/
grep -r "_get_enhanced_query" resync/
grep -r "_get_optimized_response" resync/
grep -r "_should_use_llm_optimization" resync/
```

Se encontrar algum resultado, atualize conforme exemplos acima.

---

## 🎓 Filosofia da Migração

### Princípios:
1. **Uma forma de fazer cada coisa** - Sem métodos redundantes
2. **Explícito é melhor que implícito** - Sem helpers mágicos
3. **Componível** - Combine QueryProcessor + LLM + Tools
4. **Testável** - Componentes isolados e mockáveis

### Anti-padrões eliminados:
- ❌ Múltiplas formas de fazer a mesma coisa
- ❌ Helpers que escondem complexidade
- ❌ Lógica espalhada em vários arquivos
- ❌ Heurísticas hardcoded (_should_use_llm_optimization)

---

## 📚 Recursos

**Documentação:**
- `CHANGELOG_v5.9.8.md` - Lista completa de mudanças
- `README_v5.9.8.md` - Guia de uso dos novos métodos
- Este arquivo - Guia de migração completa

**Exemplos de código:**
- `resync/api/chat.py` - Novo fluxo de chat
- `resync/api/enhanced_endpoints.py` - Uso de orchestrator + tools
- `resync/tools/llm_tools.py` - Como criar tools

---

## 🆘 Problemas Comuns

### 1. "AttributeError: 'LLMService' has no attribute 'chat_completion'"

**Causa:** Código usando método removido.

**Solução:**
```python
# Antes
await llm.chat_completion(msg, agent_id)

# Depois
await llm.generate_agent_response(agent_id, msg)
```

---

### 2. "NameError: name 'get_llm_completion' is not defined"

**Causa:** Função helper removida.

**Solução:**
```python
# Antes
response = await get_llm_completion(prompt)

# Depois
llm = get_llm_service()
messages = [{"role": "user", "content": prompt}]
response = await llm.generate_response(messages)
```

---

### 3. "ImportError: cannot import name '_get_enhanced_query'"

**Causa:** Função interna removida.

**Solução:**
```python
# Antes
from resync.api.chat import _get_enhanced_query
enhanced = await _get_enhanced_query(kg, data, original)

# Depois
from resync.core.query_processor import QueryProcessor
processor = QueryProcessor(llm, kg)
structured = await processor.process_query(original)
messages = processor.format_for_llm(structured)
```

---

## ✅ Próximos Passos

1. ✅ Extrair e testar resync-v5.9.8-clean.zip
2. ✅ Rodar busca por código quebrado (script acima)
3. ✅ Atualizar código customizado conforme guias
4. ✅ Testar em staging
5. ✅ Deploy em produção

---

**Status:** 🔥 **CÓDIGO LIMPO - SEM LEGADO**  
**Versão:** 5.9.8 (Clean Migration)  
**Data:** Dezembro 2024
