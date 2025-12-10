# Arquitetura de API - Resync v5.3.x

## Visão Geral

O Resync possui duas estruturas de API que coexistem por razões históricas e funcionais:

```
resync/
├── api/                    # Rotas de administração e monitoramento
│   ├── admin.py            # Admin panel routes
│   ├── auth.py             # Autenticação centralizada
│   ├── monitoring_dashboard.py
│   ├── monitoring_routes.py
│   ├── system_config.py
│   └── litellm_config.py
│
└── fastapi_app/
    └── api/v1/routes/      # Rotas da aplicação principal
        ├── auth.py
        ├── chat.py
        ├── agents.py
        ├── audit.py
        ├── rag.py
        └── admin_*.py
```

## Justificativa

### Por que duas estruturas?

1. **Evolução incremental**: O projeto migrou de uma estrutura monolítica para uma arquitetura mais modular sem quebrar funcionalidade existente.

2. **Dois entry points**:
   - `resync/main.py` → Usa `resync/fastapi_app/main.py` (aplicação principal)
   - `resync/app_factory.py` → Entry point alternativo para testes e desenvolvimento

3. **Separação de responsabilidades**:
   - `resync/api/`: Rotas de infraestrutura (monitoramento, config, admin)
   - `resync/fastapi_app/api/`: Rotas de negócio (chat, agents, RAG)

### Arquivos Críticos em `resync/api/`

| Arquivo | Importado por | Função |
|---------|---------------|--------|
| `auth.py` | `admin.py`, `system_config.py`, `litellm_config.py` | `verify_admin_credentials()` |
| `monitoring_dashboard.py` | `fastapi_app/main.py` | Dashboard de monitoramento |
| `monitoring_routes.py` | `fastapi_app/main.py` | Rotas proativas |
| `system_config.py` | `fastapi_app/main.py` | Configuração do sistema |
| `litellm_config.py` | `fastapi_app/main.py` | Configuração LiteLLM |

## O que NÃO fazer

❌ Remover arquivos de `resync/api/` sem verificar dependências
❌ Duplicar rotas entre as duas estruturas
❌ Misturar Flask com FastAPI (já corrigido em v5.3.2)

## Roadmap de Consolidação (Futuro)

Para uma consolidação completa (v6.0+):

1. [ ] Mover `auth.py` para módulo compartilhado
2. [ ] Migrar rotas de `resync/api/` para `fastapi_app/api/v1/`
3. [ ] Unificar entry points
4. [ ] Remover `app_factory.py` após migrar testes

## Histórico de Correções

### v5.3.2
- ✅ Removido `routes.py` (Flask morto)
- ✅ Corrigido DI container com contextvars
- ✅ Implementado carregamento de agentes via YAML
- ✅ Documentada arquitetura híbrida (este documento)
