# 🔄 Migração SQLite → PostgreSQL

## Resumo Executivo

**Data:** Dezembro 2024  
**Versão:** Resync 5.2.3.32  
**Migração:** Consolidação de todos os stores SQLite em PostgreSQL

---

## Mudanças Realizadas

### Arquivos Principais Migrados

| Arquivo Original | Novo Backend | Linhas |
|-----------------|--------------|--------|
| `tws_status_store.py` | PostgreSQL via TWSStore | 140 |
| `context_store.py` | PostgreSQL via ContextStore | 130 |
| `audit_db.py` | PostgreSQL via AuditEntryRepository | 80 |
| `audit_queue.py` | PostgreSQL via AuditQueueRepository | 90 |
| `user_behavior.py` | PostgreSQL via UserBehaviorStore | 100 |
| `feedback_store.py` (2x) | PostgreSQL via FeedbackStore | 140 |
| `lightweight_store.py` | PostgreSQL via MetricsStore | 80 |
| `threshold_tuning.py` | PostgreSQL via LearningThresholds | 70 |
| `active_learning.py` (2x) | PostgreSQL via ActiveLearning | 130 |
| `tws_multi/learning.py` | PostgreSQL via FeedbackStore | 60 |

### Novos Componentes Criados

```
resync/core/database/
├── models/
│   ├── __init__.py
│   └── stores.py          # 17 SQLAlchemy models
├── repositories/
│   ├── __init__.py
│   ├── base.py            # BaseRepository, TimestampedRepository
│   ├── tws_repository.py  # TWSStore facade
│   └── stores.py          # Context, Audit, Analytics, Learning, Metrics
├── schema.py              # Schema creation utilities
├── config.py              # PostgreSQL-only config
└── engine.py              # Connection pooling
```

### Modelos SQLAlchemy Criados

#### Schema: tws
- `TWSSnapshot` - Snapshots de status
- `TWSJobStatus` - Status de jobs
- `TWSWorkstationStatus` - Status de workstations
- `TWSEvent` - Eventos e alertas
- `TWSPattern` - Padrões detectados
- `TWSProblemSolution` - Soluções conhecidas

#### Schema: context
- `Conversation` - Histórico de conversas
- `ContextContent` - Conteúdo para RAG

#### Schema: audit
- `AuditEntry` - Entradas de auditoria
- `AuditQueueItem` - Fila de processamento

#### Schema: analytics
- `UserProfile` - Perfis de usuário
- `SessionHistory` - Histórico de sessões

#### Schema: learning
- `Feedback` - Feedback de usuários
- `LearningThreshold` - Thresholds dinâmicos
- `ActiveLearningCandidate` - Candidatos para revisão

#### Schema: metrics
- `MetricDataPoint` - Pontos de dados
- `MetricAggregation` - Agregações pré-calculadas

---

## Configuração

### Variáveis de Ambiente

```bash
# Conexão PostgreSQL (obrigatório)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/resync

# Ou configuração individual
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=resync
DATABASE_USER=resync
DATABASE_PASSWORD=secret

# Pool de conexões
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
```

### Inicialização do Banco

```python
from resync.core.database import initialize_database

# Criar schemas e tabelas
await initialize_database()
```

Ou via linha de comando:
```bash
python -m resync.core.database.schema
```

---

## Migração de Dados

### De SQLite para PostgreSQL

Se você tem dados em SQLite que precisam ser migrados:

1. **Export dos dados SQLite:**
```bash
sqlite3 tws_status.db ".dump" > tws_data.sql
```

2. **Conversão para PostgreSQL:**
```bash
# Use uma ferramenta como pgloader
pgloader sqlite:///tws_status.db postgresql://user:pass@host/resync
```

3. **Ou via código Python:**
```python
# Ver scripts/migrate_sqlite_to_pg.py
```

---

## Compatibilidade

### Interface Mantida

Todas as classes mantêm a mesma interface pública:

```python
# Antes (SQLite)
store = TWSStatusStore(db_path="data/tws.db")
await store.initialize()
await store.update_job_status(job)

# Depois (PostgreSQL) - MESMA INTERFACE
store = TWSStatusStore()  # db_path ignorado
await store.initialize()
await store.update_job_status(job)
```

### Parâmetros Deprecados

O parâmetro `db_path` é aceito mas ignorado em todas as classes.
Um log de warning é emitido quando usado.

---

## Benefícios

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Bancos de dados | 2 (PG + SQLite) | 1 (PostgreSQL) |
| Arquivos .db locais | 10+ | 0 |
| Backups | 2 estratégias | 1 (pg_dump) |
| Transações cross-table | Impossível | Possível |
| Replicação | Manual | Nativa |
| Connection pooling | Parcial | Completo |

---

## Rollback

Se necessário reverter para SQLite:

1. Os arquivos originais estão em `backups/sqlite_stores/`
2. Restaure cada arquivo para sua localização original
3. Reinstale `aiosqlite` no requirements.txt
4. Reinicie a aplicação

---

## Checklist de Migração

- [x] Criar modelos SQLAlchemy para todas as tabelas
- [x] Criar repositórios com interface Repository pattern
- [x] Criar facades unificadas (TWSStore, ContextStore, etc.)
- [x] Atualizar todos os stores para usar PostgreSQL
- [x] Remover imports de aiosqlite/sqlite3
- [x] Atualizar database/config.py (PostgreSQL only)
- [x] Atualizar database/engine.py (remover NullPool)
- [x] Atualizar requirements.txt
- [x] Verificar compilação de todos os arquivos
- [x] Documentar migração

---

## Conclusão

A migração consolidou **18 arquivos** que usavam SQLite diretamente 
em uma arquitetura unificada baseada em PostgreSQL, resultando em:

- **Zero** arquivos `.db` locais
- **Zero** dependências de SQLite
- **1** banco de dados para gerenciar
- **455** arquivos Python compilando sem erros
