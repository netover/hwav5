"""
pgvector-based vector store implementation for RAG.

Replaces Qdrant with PostgreSQL's pgvector extension for a unified database stack.
Provides async-safe upsert, query, and deduplication with metadata indexing.
"""

import json
import logging
import os
from typing import Any

from .config import CFG
from .interfaces import VectorStore

logger = logging.getLogger(__name__)

# Optional imports - defer error until actual usage
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False


class PgVectorStore(VectorStore):
    """
    PostgreSQL-based vector store using pgvector extension.

    Encapsulates upsert/query operations with automatic table creation,
    HNSW indexing, and metadata filters. All operations are async.
    """

    def __init__(
        self,
        database_url: str | None = None,
        collection: str | None = None,
        dim: int = CFG.embed_dim,
    ):
        """
        Initialize pgvector store.

        Args:
            database_url: PostgreSQL connection URL
            collection: Default collection name
            dim: Embedding dimension (default from config)
        """
        if not ASYNCPG_AVAILABLE:
            raise RuntimeError("asyncpg is required. pip install asyncpg")

        self._database_url = database_url or os.getenv(
            "DATABASE_URL", "postgresql://resync:password@localhost:5432/resync"
        )
        # Clean URL for asyncpg (remove driver prefix)
        if self._database_url.startswith("postgresql+asyncpg://"):
            self._database_url = self._database_url.replace(
                "postgresql+asyncpg://", "postgresql://"
            )

        self._collection_default = collection or CFG.collection_write
        self._dim = dim
        self._pool: asyncpg.Pool | None = None
        self._initialized = False

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=2,
                max_size=10,
                command_timeout=60.0,
            )
            await self._ensure_table()
        return self._pool

    async def _ensure_table(self) -> None:
        """Ensure the embeddings table and indexes exist."""
        if self._initialized:
            return

        pool = self._pool
        if pool is None:
            return

        async with pool.acquire() as conn:
            # Check/create pgvector extension
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            except Exception as e:
                logger.warning("pgvector_extension_check_failed", error=str(e), exc_info=True)

            # Create table
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS document_embeddings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    collection_name VARCHAR(100) NOT NULL,
                    document_id VARCHAR(255) NOT NULL,
                    chunk_id INTEGER NOT NULL DEFAULT 0,
                    content TEXT NOT NULL,
                    embedding vector({self._dim}),
                    metadata JSONB DEFAULT '{{}}',
                    sha256 VARCHAR(64),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_name, document_id, chunk_id)
                )
            """)

            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_collection
                ON document_embeddings(collection_name)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_embeddings_sha256
                ON document_embeddings(sha256)
            """)

            # Create HNSW index for fast vector search
            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_vector
                    ON document_embeddings
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 256)
                """)
            except Exception as e:
                logger.warning("hnsw_index_creation_failed", error=str(e), exc_info=True)

        self._initialized = True
        logger.info(
            "pgvector_store_initialized", collection=self._collection_default, dim=self._dim
        )

    async def upsert_batch(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
        collection: str | None = None,
    ) -> None:
        """
        Batch upsert documents with embeddings.

        Uses a single transaction with prepared statement for better performance.

        Args:
            ids: Document IDs (used as document_id)
            vectors: Embedding vectors
            payloads: Metadata payloads (should include 'text' or 'content')
            collection: Collection name (optional)
        """
        if not ids:
            return

        col = collection or self._collection_default
        pool = await self._get_pool()

        # Prepare all records
        records = []
        for doc_id, vector, payload in zip(ids, vectors, payloads, strict=False):
            content = payload.get("text", payload.get("content", ""))
            sha256 = payload.get("sha256", "")
            chunk_id = payload.get("chunk_id", 0)

            # Convert vector to pgvector format
            embedding_str = f"[{','.join(str(x) for x in vector)}]"

            # Clean payload (remove fields stored separately)
            metadata = {
                k: v
                for k, v in payload.items()
                if k not in ("text", "content", "sha256", "chunk_id")
            }

            records.append(
                (
                    col,
                    doc_id,
                    chunk_id,
                    content,
                    embedding_str,
                    json.dumps(metadata),
                    sha256,
                )
            )

        # Execute all in a single transaction
        async with pool.acquire() as conn, conn.transaction():
            # Use prepared statement for better performance
            stmt = await conn.prepare("""
                    INSERT INTO document_embeddings
                    (collection_name, document_id, chunk_id, content, embedding, metadata, sha256)
                    VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb, $7)
                    ON CONFLICT (collection_name, document_id, chunk_id)
                    DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        sha256 = EXCLUDED.sha256,
                        updated_at = CURRENT_TIMESTAMP
                """)

            # Execute all records with prepared statement
            await stmt.executemany(records)

        logger.debug("batch_upserted", collection=col, count=len(ids))

    async def query(
        self,
        vector: list[float],
        top_k: int,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
        ef_search: int | None = None,
        with_vectors: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Query for similar documents.

        Args:
            vector: Query embedding
            top_k: Number of results to return
            collection: Collection to search
            filters: Metadata filters
            ef_search: HNSW ef parameter (ignored in pgvector, uses index default)
            with_vectors: Include vectors in results

        Returns:
            List of results with id, score, payload, and optionally vector
        """
        col = collection or CFG.collection_read
        pool = await self._get_pool()

        # Build query
        embedding_str = f"[{','.join(str(x) for x in vector)}]"

        # Base query
        select_cols = "document_id, chunk_id, content, metadata, sha256"
        if with_vectors:
            select_cols += ", embedding"

        query = f"""
            SELECT {select_cols},
                   embedding <=> $1::vector AS distance
            FROM document_embeddings
            WHERE collection_name = $2
        """
        params = [embedding_str, col]
        param_idx = 3

        # Add metadata filters
        if filters:
            for key, value in filters.items():
                if value is None:
                    continue
                if key == "sha256":
                    query += f" AND sha256 = ${param_idx}"
                else:
                    query += f" AND metadata->>'{key}' = ${param_idx}"
                params.append(str(value))
                param_idx += 1

        query += f" ORDER BY distance LIMIT ${param_idx}"
        params.append(top_k)

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            # Build payload from stored fields
            payload = dict(row["metadata"]) if row["metadata"] else {}
            payload["text"] = row["content"]
            payload["sha256"] = row["sha256"]
            payload["chunk_id"] = row["chunk_id"]

            item = {
                "id": row["document_id"],
                "score": 1.0 - float(row["distance"]),  # Convert distance to similarity
                "payload": payload,
            }

            if with_vectors and "embedding" in row:
                # Parse vector from pgvector format
                item["vector"] = list(row["embedding"])

            results.append(item)

        return results

    async def count(self, collection: str | None = None) -> int:
        """
        Count documents in collection.

        Args:
            collection: Collection name

        Returns:
            Number of documents
        """
        col = collection or CFG.collection_read
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM document_embeddings
                WHERE collection_name = $1
            """,
                col,
            )

        return int(count or 0)

    async def exists_by_sha256(self, sha256: str, collection: str | None = None) -> bool:
        """
        Check if document with SHA256 hash exists.

        Args:
            sha256: Document hash
            collection: Collection name

        Returns:
            True if document exists
        """
        col = collection or CFG.collection_read
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT 1 FROM document_embeddings
                WHERE collection_name = $1 AND sha256 = $2
                LIMIT 1
            """,
                col,
                sha256,
            )

        return exists is not None

    async def delete_by_document_id(self, document_id: str, collection: str | None = None) -> int:
        """
        Delete all chunks for a document.

        Args:
            document_id: Document ID
            collection: Collection name

        Returns:
            Number of deleted rows
        """
        col = collection or self._collection_default
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM document_embeddings
                WHERE collection_name = $1 AND document_id = $2
            """,
                col,
                document_id,
            )
            return int(result.split()[-1])

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None


def get_default_store() -> PgVectorStore:
    """Get default vector store instance."""
    return PgVectorStore()
