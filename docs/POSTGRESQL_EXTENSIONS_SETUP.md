# PostgreSQL Extensions Setup Guide

Resync v5.3+ uses a unified PostgreSQL stack with three extensions:

| Extension | Purpose | Required |
|-----------|---------|----------|
| **pgvector** | Vector similarity search (RAG) | ✅ Yes |
| **Apache AGE** | Graph queries (Cypher) | ✅ Yes |
| **pg_trgm** | Text search optimization | Optional |

## Prerequisites

- PostgreSQL 15+ (recommended) or 14+
- Superuser access to install extensions
- ~500MB disk space for extensions

## Quick Setup (Docker)

The easiest way to get all extensions is using a pre-built image:

```bash
# Using pgvector + AGE combined image
docker run -d \
  --name resync-postgres \
  -e POSTGRES_USER=resync \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=resync \
  -p 5432:5432 \
  apache/age:PG15_latest
```

Then install pgvector:

```bash
docker exec -it resync-postgres psql -U resync -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Manual Installation

### 1. Install pgvector

**Ubuntu/Debian:**
```bash
# For PostgreSQL 15
sudo apt install postgresql-15-pgvector

# For PostgreSQL 16
sudo apt install postgresql-16-pgvector
```

**macOS (Homebrew):**
```bash
brew install pgvector
```

**From Source:**
```bash
cd /tmp
git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install  # requires sudo on Linux
```

### 2. Install Apache AGE

**From Source (recommended):**
```bash
cd /tmp
git clone https://github.com/apache/age.git
cd age
make PG_CONFIG=/usr/bin/pg_config
sudo make install
```

**Docker Build:**
```dockerfile
FROM postgres:15

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-15 \
    && rm -rf /var/lib/apt/lists/*

# Build and install AGE
RUN cd /tmp && \
    git clone https://github.com/apache/age.git && \
    cd age && \
    make PG_CONFIG=/usr/bin/pg_config && \
    make install && \
    rm -rf /tmp/age

# Build and install pgvector
RUN cd /tmp && \
    git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git && \
    cd pgvector && \
    make && \
    make install && \
    rm -rf /tmp/pgvector
```

## Database Setup

After installing extensions, run these SQL commands as superuser:

```sql
-- Connect to your database
\c resync

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Enable Apache AGE extension
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- 3. Create the graph for TWS data
SELECT create_graph('tws_graph');

-- 4. Optional: Enable trigram for better text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 5. Verify extensions
SELECT * FROM pg_extension WHERE extname IN ('vector', 'age', 'pg_trgm');
```

## Create Resync Tables

Run the Alembic migrations to create all required tables:

```bash
cd /path/to/resync
alembic upgrade head
```

Or run manually:

```sql
-- LangGraph Checkpoints (for conversation persistence)
CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    checkpoint JSONB NOT NULL,
    checkpoint_compressed BYTEA,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    PRIMARY KEY (thread_id, checkpoint_id)
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON langgraph_checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_expires ON langgraph_checkpoints(expires_at);

-- Vector Embeddings (for RAG)
CREATE TABLE IF NOT EXISTS document_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_name VARCHAR(100) NOT NULL,
    document_id VARCHAR(255) NOT NULL,
    chunk_id INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI ada-002 dimension
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_name, document_id, chunk_id)
);
CREATE INDEX IF NOT EXISTS idx_embeddings_collection ON document_embeddings(collection_name);
CREATE INDEX IF NOT EXISTS idx_embeddings_document ON document_embeddings(document_id);

-- Create HNSW index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON document_embeddings 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Prompts Storage (for LangFuse local fallback)
CREATE TABLE IF NOT EXISTS prompts (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    content TEXT NOT NULL,
    description TEXT DEFAULT '',
    variables JSONB DEFAULT '[]',
    default_values JSONB DEFAULT '{}',
    model_hint VARCHAR(100),
    temperature_hint FLOAT,
    max_tokens_hint INTEGER,
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    ab_test_group VARCHAR(100),
    ab_test_weight FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_prompts_type ON prompts(type);
CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts(is_active);
```

## Verify Installation

Run this SQL to verify everything is working:

```sql
-- Check extensions
SELECT extname, extversion FROM pg_extension 
WHERE extname IN ('vector', 'age');

-- Check vector operations
SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector AS distance;

-- Check AGE graph
SELECT * FROM ag_catalog.ag_graph WHERE name = 'tws_graph';

-- Check tables
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('langgraph_checkpoints', 'document_embeddings', 'prompts');
```

Expected output:
```
 extname | extversion
---------+------------
 vector  | 0.7.4
 age     | 1.5.0

 distance
----------
 5.196...

 graphid |   name    | namespace
---------+-----------+-----------
    ...  | tws_graph | tws_graph

 table_name
----------------------
 langgraph_checkpoints
 document_embeddings
 prompts
```

## Troubleshooting

### Extension not found

```
ERROR: could not open extension control file "/usr/share/postgresql/15/extension/vector.control"
```

**Solution:** The extension is not installed. Follow the installation steps above.

### AGE not loading

```
ERROR: could not access file "age": No such file or directory
```

**Solution:** Add AGE to shared_preload_libraries in postgresql.conf:

```bash
# Edit postgresql.conf
echo "shared_preload_libraries = 'age'" >> /etc/postgresql/15/main/postgresql.conf

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Vector dimension mismatch

```
ERROR: different vector dimensions 1536 and 768
```

**Solution:** Ensure your embedding model output matches the table dimension. The default is 1536 (OpenAI ada-002). For other models:

```sql
-- For 768-dim models (e.g., sentence-transformers)
ALTER TABLE document_embeddings 
ALTER COLUMN embedding TYPE vector(768);
```

### Permission denied

```
ERROR: permission denied to create extension "age"
```

**Solution:** Run as superuser or grant SUPERUSER:

```sql
ALTER USER resync WITH SUPERUSER;
-- Then create extension
-- Then revoke if needed:
ALTER USER resync WITH NOSUPERUSER;
```

## Performance Tuning

For production workloads, tune these PostgreSQL settings:

```conf
# postgresql.conf

# Memory (adjust based on available RAM)
shared_buffers = 4GB           # 25% of RAM
effective_cache_size = 12GB    # 75% of RAM
work_mem = 256MB               # For vector operations
maintenance_work_mem = 1GB     # For index builds

# Vector-specific
max_parallel_workers_per_gather = 4
enable_seqscan = off           # Force index usage for vectors

# AGE-specific
shared_preload_libraries = 'age'
```

## Migration from Qdrant

If migrating from Qdrant, export your data and re-import:

```python
# Export from Qdrant
from qdrant_client import QdrantClient

qdrant = QdrantClient(host="localhost", port=6333)
points = qdrant.scroll(collection_name="tws_docs", limit=10000)[0]

# Import to pgvector
import asyncpg

conn = await asyncpg.connect(dsn)
for point in points:
    await conn.execute("""
        INSERT INTO document_embeddings 
        (document_id, content, embedding, metadata)
        VALUES ($1, $2, $3, $4)
    """, point.id, point.payload['content'], point.vector, point.payload)
```

## Next Steps

After setup:

1. Run migrations: `alembic upgrade head`
2. Start the application: `uvicorn resync.main:app --reload`
3. Verify health: `curl http://localhost:8000/api/v1/health`
