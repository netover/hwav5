# CHANGELOG v5.2.3.20

**Data:** 2024-12-16

## 🎯 Resumo

Esta versão implementa o fluxo "Golden Record" para incorporação de conhecimento humano no sistema de RAG. Quando um administrador aprova um feedback com uma correção, essa correção é transformada em um documento de conhecimento que é indexado no vector store com máxima prioridade de retrieval.

## ✨ Novas Funcionalidades

### Knowledge Incorporator
- **Novo serviço:** `KnowledgeIncorporator` em `resync/core/continual_learning/knowledge_incorporator.py`
- Transforma feedback aprovado em documentos "Golden Record"
- Documentos criados têm máxima prioridade no retrieval:
  - `source_tier: "verified"`
  - `authority_tier: 1`
  - `doc_type: "golden_record"`
- Extração automática de keywords TWS (job names, error codes)
- Suporte a incorporação em batch

### API de Curadoria de Feedback
- **Novos endpoints** em `/api/v1/admin/feedback`:
  - `GET /pending` - Lista feedbacks pendentes de aprovação
  - `GET /{id}` - Detalhes completos de um feedback
  - `GET /stats` - Estatísticas de curadoria
  - `POST /{id}/approve` - Aprova e incorpora feedback como conhecimento
  - `POST /{id}/reject` - Rejeita feedback
  - `DELETE /{id}/rollback` - Remove documento incorporado
  - `POST /bulk-approve` - Aprovação em lote

### Modelo de Dados
- **Novos campos** na tabela `feedback`:
  - `user_correction` (TEXT) - Resposta correta do especialista
  - `curation_status` (VARCHAR) - Status: pending/approved/rejected/incorporated
  - `approved_by` (VARCHAR) - ID do revisor
  - `approved_at` (TIMESTAMP) - Data de aprovação
  - `incorporated_doc_id` (VARCHAR) - ID do documento no vector store
- **Novo índice:** `idx_feedback_curation_status`

## 📁 Arquivos Modificados

### Novos Arquivos
- `resync/core/continual_learning/knowledge_incorporator.py`
- `resync/api/routes/admin/feedback_curation.py`
- `alembic/versions/20241216_0003_golden_record_fields.py`

### Arquivos Atualizados
- `resync/core/database/models/stores.py` - Campos Golden Record
- `resync/core/continual_learning/__init__.py` - Exports
- `resync/api/routes/admin/__init__.py` - Router registration
- `resync/app_factory.py` - Router inclusion

## 🔧 Migration

Para aplicar as mudanças no banco de dados:

```bash
alembic upgrade head
```

Ou especificamente:

```bash
alembic upgrade 20241216_0003
```

## 🚀 Como Usar

### 1. Aprovar Feedback e Incorporar Conhecimento

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/admin/feedback/123/approve",
    json={
        "reviewer_id": "admin",
        "user_correction": "Para reiniciar o job XPTO, use: rerun XPTO",
        "incorporate_to_kb": True
    }
)

# Resposta:
# {
#     "message": "O Resync aprendeu com sucesso!",
#     "feedback_id": 123,
#     "incorporated": true,
#     "doc_id": "golden_record_123"
# }
```

### 2. Listar Feedbacks Pendentes

```python
response = httpx.get(
    "http://localhost:8000/api/v1/admin/feedback/pending",
    params={"limit": 50, "has_negative_rating": True}
)
```

### 3. Ver Estatísticas

```python
response = httpx.get("http://localhost:8000/api/v1/admin/feedback/stats")

# Resposta:
# {
#     "total": 150,
#     "pending": 45,
#     "approved": 80,
#     "rejected": 15,
#     "incorporated": 65,
#     "avg_rating": 3.2,
#     "pending_with_correction": 12
# }
```

## 🔍 Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLUXO GOLDEN RECORD                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Usuário dá feedback    2. Admin revisa       3. Incorpora   │
│  ┌──────────────┐          ┌──────────────┐      ┌───────────┐  │
│  │   Feedback   │──────────│   Curadoria  │──────│  pgvector │  │
│  │   (rating,   │          │  (approve/   │      │  (Golden  │  │
│  │   comment)   │          │   reject)    │      │  Record)  │  │
│  └──────────────┘          └──────────────┘      └───────────┘  │
│                                   │                     │       │
│                                   ▼                     ▼       │
│                            ┌──────────────┐      ┌───────────┐  │
│                            │  Knowledge   │──────│   RAG     │  │
│                            │ Incorporator │      │ Retrieval │  │
│                            └──────────────┘      └───────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## ⚠️ Breaking Changes

Nenhum. Todos os novos campos são opcionais e têm valores default.

## 🧪 Testes

Execute os testes de integração:

```bash
pytest tests/continual_learning/ -v
```

## 📚 Documentação

Ver `docs/CONTINUAL_LEARNING.md` para documentação completa do sistema de aprendizado contínuo.
