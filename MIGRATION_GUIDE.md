# Migração Rápida v5.9.6 → v5.9.8

## ⚡ TL;DR - Apenas copie os arquivos!

**100% backwards compatible** - Código antigo continua funcionando.

---

## 📦 Arquivos Novos (Apenas adicionar)

Copie estes arquivos para seu projeto:

```bash
# 1. Tools LLM
resync/tools/llm_tools.py

# 2. Query Processor
resync/core/query_processor.py

# 3. Service Orchestrator
resync/core/orchestrator.py

# 4. Cache Utils
resync/core/cache_utils.py

# 5. Enhanced Endpoints
resync/api/enhanced_endpoints.py

# 6. Documentação
CHANGELOG_v5.9.8.md
README_v5.9.8.md
docs/CACHE_L1_DECISION.md
```

---

## 📝 Arquivos Modificados (Substituir)

Substitua estes arquivos:

```bash
# 1. LLM Service (adicionado generate_response_with_tools)
resync/services/llm_service.py

# 2. Chat endpoint (integrado Query Processor)
resync/api/chat.py

# 3. App factory (registrado enhanced_router + cache warming)
resync/app_factory.py
```

---

## 🚀 Comando Único de Migração

```bash
# De dentro do diretório resync-v5.9.8/

# Copiar arquivos novos
cp -r resync/tools/llm_tools.py ../resync-v5.9.6/resync/tools/
cp -r resync/core/query_processor.py ../resync-v5.9.6/resync/core/
cp -r resync/core/orchestrator.py ../resync-v5.9.6/resync/core/
cp -r resync/core/cache_utils.py ../resync-v5.9.6/resync/core/
cp -r resync/api/enhanced_endpoints.py ../resync-v5.9.6/resync/api/

# Substituir arquivos modificados
cp -f resync/services/llm_service.py ../resync-v5.9.6/resync/services/
cp -f resync/api/chat.py ../resync-v5.9.6/resync/api/
cp -f resync/app_factory.py ../resync-v5.9.6/

# Copiar documentação
cp CHANGELOG_v5.9.8.md ../resync-v5.9.6/
cp README_v5.9.8.md ../resync-v5.9.6/
mkdir -p ../resync-v5.9.6/docs
cp docs/CACHE_L1_DECISION.md ../resync-v5.9.6/docs/

# Reiniciar aplicação
cd ../resync-v5.9.6
uvicorn resync.main:app --reload
```

---

## ✅ Verificação

Depois de migrar, teste:

```bash
# 1. Aplicação inicia sem erros
# Verifique logs: tail -f logs/resync.log

# 2. Novos endpoints funcionam
curl http://localhost:8000/api/v2/system/health

# 3. Chat continua funcionando
# Abra interface web e teste mensagem

# 4. Tools estão registradas
python -c "
from resync.tools.registry import get_tool_catalog
catalog = get_tool_catalog()
print(f'Tools: {len(catalog.list_tools())}')
"
```

**Esperado:**
```
Cache warming completed
Enhanced endpoints registered
Tools: 5
```

---

## 🔄 Rollback (se algo der errado)

```bash
# Restaurar backup
rm -rf resync-v5.9.6
mv resync-v5.9.6-backup resync-v5.9.6
cd resync-v5.9.6
uvicorn resync.main:app --reload
```

---

## 🆘 Problemas Comuns

### 1. Import Error: "No module named 'resync.tools.llm_tools'"

**Solução:** Arquivo não foi copiado corretamente
```bash
cp resync/tools/llm_tools.py ../resync-v5.9.6/resync/tools/
```

---

### 2. "enhanced_endpoints_not_available"

**Solução:** Arquivo não foi copiado
```bash
cp resync/api/enhanced_endpoints.py ../resync-v5.9.6/resync/api/
```

---

### 3. Cache warming falha

**Não é crítico!** Sistema continua funcionando. Ignore o warning.

---

### 4. WebSocket erro no chat

**Possível causa:** chat.py não foi substituído corretamente

**Solução:**
```bash
cp -f resync/api/chat.py ../resync-v5.9.6/resync/api/
```

---

## 🎯 Tudo Funcionando?

**Endpoints que devem funcionar:**

```bash
# Antigos (devem continuar funcionando)
curl http://localhost:8000/api/health
curl http://localhost:8000/api/status

# Novos (devem funcionar agora)
curl http://localhost:8000/api/v2/system/health
curl http://localhost:8000/api/v2/jobs/failed?hours=24
```

---

**Dúvidas?** Consulte README_v5.9.8.md
