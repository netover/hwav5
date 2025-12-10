# Database Migration: SQLite → PostgreSQL

## Overview

As of version 5.2.3.32, Resync uses **PostgreSQL as the only database backend**.
All SQLite references have been removed to simplify operations and maintenance.

## Changes Made

### Removed Components
- All `aiosqlite` and `sqlite3` imports and usage
- SQLite-specific code paths in data stores
- Development SQLite database support
- `.db` file references

### Updated Components

| Component | Before | After |
|-----------|--------|-------|
| `tws_status_store.py` | SQLite (1102 lines) | PostgreSQL repository |
| `context_store.py` | SQLite (495 lines) | PostgreSQL repository |
| `audit_db.py` | SQLite (482 lines) | PostgreSQL repository |
| `audit_queue.py` | SQLite (844 lines) | PostgreSQL repository |
| `user_behavior.py` | SQLite (1112 lines) | PostgreSQL repository |
| `feedback_store.py` | SQLite | PostgreSQL repository |
| `threshold_tuning.py` | SQLite | PostgreSQL repository |
| `active_learning.py` | SQLite | PostgreSQL repository |
| `lightweight_store.py` | SQLite | PostgreSQL repository |

### New Components

```
resync/core/database/
├── __init__.py          # Updated exports
├── config.py            # PostgreSQL-only config
├── engine.py            # SQLAlchemy async engine
├── schema.py            # Schema creation scripts
├── models/
│   ├── __init__.py
│   └── stores.py        # All SQLAlchemy models
└── repositories/
    ├── __init__.py
    ├── base.py          # Base repository pattern
    ├── tws_repository.py # TWS-specific repositories
    └── stores.py        # Other store repositories
```

## Database Schemas

PostgreSQL schemas created:

- `tws` - TWS job status, events, patterns, solutions
- `context` - Conversations, content
- `audit` - Audit entries, queue
- `analytics` - User profiles, sessions
- `learning` - Feedback, thresholds, active learning
- `metrics` - Metric data points, aggregations

## Configuration

### Environment Variables

```bash
# Option 1: Full connection URL
DATABASE_URL=postgresql://user:password@host:5432/resync

# Option 2: Individual variables
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=resync
DATABASE_USER=resync
DATABASE_PASSWORD=your_password

# Connection pool settings
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600
```

### Required Dependencies

```
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
psycopg2-binary>=2.9.0
```

## Database Setup

### 1. Create Database

```sql
CREATE DATABASE resync;
CREATE USER resync WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE resync TO resync;
```

### 2. Initialize Schema

```python
from resync.core.database import initialize_database

# Run once to create schemas and tables
await initialize_database()
```

Or via CLI:

```bash
python -m resync.core.database.schema
```

## Migration from SQLite

If you have existing SQLite data, use the migration script:

```bash
python scripts/migrate_sqlite_to_postgresql.py
```

This will:
1. Read data from existing `.db` files
2. Transform to new schema format
3. Insert into PostgreSQL

## Backward Compatibility

The public interfaces remain unchanged:

```python
# These still work exactly as before
from resync.core.tws_status_store import TWSStatusStore, JobStatus
from resync.core.context_store import ContextStore
from resync.core.audit_db import AuditDB

# Usage unchanged
store = TWSStatusStore()
await store.initialize()
await store.update_job_status(job)
```

## Benefits

1. **Single database** - One system to manage, backup, monitor
2. **Connection pooling** - Built-in via SQLAlchemy + asyncpg
3. **Better performance** - PostgreSQL optimizations, indexes
4. **Scalability** - Native replication, sharding options
5. **Features** - JSONB, full-text search, advanced indexes
6. **Transactions** - Cross-table transactions possible

## Troubleshooting

### Connection Issues

```python
from resync.core.database import check_database_connection

if not await check_database_connection():
    print("Database connection failed")
```

### Schema Issues

```python
from resync.core.database import create_schemas, create_tables

await create_schemas()  # Create schemas
await create_tables()   # Create tables
```
