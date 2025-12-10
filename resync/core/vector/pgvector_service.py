"""
PgVector Service - PostgreSQL Vector Similarity Search.

Replaces Qdrant with PostgreSQL's pgvector extension for a unified database stack.
Provides CRUD operations and similarity search for document embeddings.

Features:
- Async operations via asyncpg
- HNSW indexing for fast similarity search
- Multiple collections support
- Batch upsert with conflict handling
- Cosine, L2, and inner product distance metrics

Requirements:
- PostgreSQL 15+ with pgvector extension
- asyncpg driver
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Union

import asyncpg

logger = logging.getLogger(__name__)


class DistanceMetric(str, Enum):
    """Supported distance metrics for similarity search."""
    COSINE = "cosine"
    L2 = "l2"
    INNER_PRODUCT = "inner_product"


@dataclass
class VectorDocument:
    """Document with embedding for vector storage."""
    
    document_id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document_id": self.document_id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "chunk_id": self.chunk_id,
        }


@dataclass
class SearchResult:
    """Result from similarity search."""
    
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: int = 0
    
    @property
    def similarity(self) -> float:
        """Get similarity score (higher is better for cosine)."""
        return 1.0 - self.score  # Convert distance to similarity


@dataclass
class CollectionStats:
    """Statistics for a collection."""
    
    name: str
    document_count: int
    total_chunks: int
    embedding_dimension: Optional[int] = None
    index_type: str = "hnsw"


class PgVectorService:
    """
    PostgreSQL Vector Service using pgvector extension.
    
    Provides vector similarity search as a drop-in replacement for Qdrant.
    
    Example:
        service = PgVectorService(pool)
        await service.initialize()
        
        # Upsert documents
        docs = [VectorDocument(document_id="1", content="Hello", embedding=[0.1, 0.2, ...])]
        await service.upsert(docs, collection="my_collection")
        
        # Search
        results = await service.search(query_embedding=[0.1, 0.2, ...], collection="my_collection")
    """
    
    def __init__(
        self,
        pool: asyncpg.Pool,
        default_collection: str = "default",
        embedding_dimension: int = 1536,
    ):
        """
        Initialize PgVector service.
        
        Args:
            pool: asyncpg connection pool
            default_collection: Default collection name
            embedding_dimension: Dimension of embeddings (default 1536 for OpenAI)
        """
        self._pool = pool
        self._default_collection = default_collection
        self._embedding_dimension = embedding_dimension
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize the service and ensure table exists.
        
        Creates the document_embeddings table if it doesn't exist.
        """
        if self._initialized:
            return
        
        async with self._pool.acquire() as conn:
            # Check if pgvector extension is available
            ext_check = await conn.fetchval(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            )
            
            if not ext_check:
                logger.warning(
                    "pgvector_extension_not_found",
                    message="Install pgvector extension: CREATE EXTENSION vector"
                )
                # Try to create it (requires superuser)
                try:
                    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    logger.info("pgvector_extension_created")
                except Exception as e:
                    logger.error("pgvector_extension_creation_failed", error=str(e))
                    raise RuntimeError(
                        "pgvector extension is required. Install with: CREATE EXTENSION vector"
                    ) from e
            
            # Create table if not exists
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS document_embeddings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    collection_name VARCHAR(100) NOT NULL,
                    document_id VARCHAR(255) NOT NULL,
                    chunk_id INTEGER NOT NULL DEFAULT 0,
                    content TEXT NOT NULL,
                    embedding vector({self._embedding_dimension}),
                    metadata JSONB DEFAULT '{{}}',
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
                CREATE INDEX IF NOT EXISTS idx_embeddings_document 
                ON document_embeddings(document_id)
            """)
            
            # Create HNSW index for vector search
            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_vector 
                    ON document_embeddings 
                    USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64)
                """)
            except Exception as e:
                logger.warning("hnsw_index_creation_failed", error=str(e))
        
        self._initialized = True
        logger.info("pgvector_service_initialized", dimension=self._embedding_dimension)
    
    async def upsert(
        self,
        documents: List[VectorDocument],
        collection: Optional[str] = None,
    ) -> int:
        """
        Upsert documents into a collection.
        
        Args:
            documents: List of documents with embeddings
            collection: Collection name (uses default if not provided)
            
        Returns:
            Number of documents upserted
        """
        if not documents:
            return 0
        
        collection = collection or self._default_collection
        
        async with self._pool.acquire() as conn:
            # Prepare batch insert
            count = 0
            for doc in documents:
                if doc.embedding is None:
                    logger.warning("document_missing_embedding", document_id=doc.document_id)
                    continue
                
                # Convert embedding to pgvector format
                embedding_str = f"[{','.join(str(x) for x in doc.embedding)}]"
                
                await conn.execute("""
                    INSERT INTO document_embeddings 
                    (collection_name, document_id, chunk_id, content, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb)
                    ON CONFLICT (collection_name, document_id, chunk_id)
                    DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, 
                    collection,
                    doc.document_id,
                    doc.chunk_id,
                    doc.content,
                    embedding_str,
                    doc.metadata or {},
                )
                count += 1
            
            logger.info("documents_upserted", collection=collection, count=count)
            return count
    
    async def search(
        self,
        query_embedding: List[float],
        collection: Optional[str] = None,
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> List[SearchResult]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query vector
            collection: Collection to search
            limit: Maximum results to return
            score_threshold: Minimum similarity score (0-1 for cosine)
            filter_metadata: Filter by metadata fields
            metric: Distance metric to use
            
        Returns:
            List of search results ordered by similarity
        """
        collection = collection or self._default_collection
        
        # Build operator based on metric
        if metric == DistanceMetric.COSINE:
            operator = "<=>"  # Cosine distance
        elif metric == DistanceMetric.L2:
            operator = "<->"  # L2 distance
        else:
            operator = "<#>"  # Inner product (negative)
        
        # Convert embedding to pgvector format
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        # Build query
        query = f"""
            SELECT 
                document_id,
                chunk_id,
                content,
                metadata,
                embedding {operator} $1::vector AS distance
            FROM document_embeddings
            WHERE collection_name = $2
        """
        params = [embedding_str, collection]
        param_idx = 3
        
        # Add metadata filter
        if filter_metadata:
            for key, value in filter_metadata.items():
                query += f" AND metadata->>'{key}' = ${param_idx}"
                params.append(str(value))
                param_idx += 1
        
        # Add score threshold for cosine
        if score_threshold is not None and metric == DistanceMetric.COSINE:
            # Convert similarity to distance threshold
            distance_threshold = 1.0 - score_threshold
            query += f" AND embedding {operator} $1::vector <= ${param_idx}"
            params.append(distance_threshold)
            param_idx += 1
        
        query += f" ORDER BY distance LIMIT ${param_idx}"
        params.append(limit)
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        results = []
        for row in rows:
            results.append(SearchResult(
                document_id=row["document_id"],
                content=row["content"],
                score=float(row["distance"]),
                metadata=dict(row["metadata"]) if row["metadata"] else {},
                chunk_id=row["chunk_id"],
            ))
        
        logger.debug(
            "search_completed",
            collection=collection,
            results=len(results),
            metric=metric.value,
        )
        
        return results
    
    async def delete(
        self,
        document_ids: Optional[List[str]] = None,
        collection: Optional[str] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Delete documents from collection.
        
        Args:
            document_ids: Specific document IDs to delete
            collection: Collection name
            filter_metadata: Delete by metadata filter
            
        Returns:
            Number of documents deleted
        """
        collection = collection or self._default_collection
        
        query = "DELETE FROM document_embeddings WHERE collection_name = $1"
        params = [collection]
        param_idx = 2
        
        if document_ids:
            placeholders = ",".join(f"${i}" for i in range(param_idx, param_idx + len(document_ids)))
            query += f" AND document_id IN ({placeholders})"
            params.extend(document_ids)
            param_idx += len(document_ids)
        
        if filter_metadata:
            for key, value in filter_metadata.items():
                query += f" AND metadata->>'{key}' = ${param_idx}"
                params.append(str(value))
                param_idx += 1
        
        async with self._pool.acquire() as conn:
            result = await conn.execute(query, *params)
            count = int(result.split()[-1])
        
        logger.info("documents_deleted", collection=collection, count=count)
        return count
    
    async def get_collection_stats(
        self,
        collection: Optional[str] = None,
    ) -> CollectionStats:
        """
        Get statistics for a collection.
        
        Args:
            collection: Collection name
            
        Returns:
            Collection statistics
        """
        collection = collection or self._default_collection
        
        async with self._pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT document_id) as doc_count,
                    COUNT(*) as total_chunks
                FROM document_embeddings
                WHERE collection_name = $1
            """, collection)
        
        return CollectionStats(
            name=collection,
            document_count=stats["doc_count"] or 0,
            total_chunks=stats["total_chunks"] or 0,
            embedding_dimension=self._embedding_dimension,
        )
    
    async def list_collections(self) -> List[str]:
        """
        List all collections.
        
        Returns:
            List of collection names
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT collection_name 
                FROM document_embeddings
                ORDER BY collection_name
            """)
        
        return [row["collection_name"] for row in rows]
    
    async def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
    ) -> None:
        """
        Create a new collection.
        
        Note: In pgvector, collections are just partitions of the same table.
        This method is for compatibility with Qdrant API.
        
        Args:
            name: Collection name
            dimension: Embedding dimension (ignored, uses service default)
        """
        # No-op for pgvector - collections are just values in collection_name column
        logger.info("collection_created", name=name)
    
    async def delete_collection(self, name: str) -> bool:
        """
        Delete a collection and all its documents.
        
        Args:
            name: Collection name
            
        Returns:
            True if collection existed and was deleted
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM document_embeddings
                WHERE collection_name = $1
            """, name)
            count = int(result.split()[-1])
        
        logger.info("collection_deleted", name=name, documents=count)
        return count > 0
    
    async def get_document(
        self,
        document_id: str,
        collection: Optional[str] = None,
        chunk_id: int = 0,
    ) -> Optional[VectorDocument]:
        """
        Get a specific document by ID.
        
        Args:
            document_id: Document ID
            collection: Collection name
            chunk_id: Chunk ID (default 0)
            
        Returns:
            Document if found, None otherwise
        """
        collection = collection or self._default_collection
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT document_id, chunk_id, content, metadata
                FROM document_embeddings
                WHERE collection_name = $1 AND document_id = $2 AND chunk_id = $3
            """, collection, document_id, chunk_id)
        
        if not row:
            return None
        
        return VectorDocument(
            document_id=row["document_id"],
            content=row["content"],
            metadata=dict(row["metadata"]) if row["metadata"] else {},
            chunk_id=row["chunk_id"],
            # Note: embedding not returned by default for performance
        )


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_vector_service: Optional[PgVectorService] = None
_pool: Optional[asyncpg.Pool] = None


async def get_vector_service() -> PgVectorService:
    """
    Get singleton vector service instance.
    
    Creates connection pool and initializes service on first call.
    
    Returns:
        Initialized PgVectorService instance
    """
    global _vector_service, _pool
    
    if _vector_service is not None:
        return _vector_service
    
    import os
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL", "postgresql://resync:password@localhost:5432/resync")
    
    # Convert to asyncpg format
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    elif database_url.startswith("postgres://"):
        pass  # Already compatible
    
    # Create pool
    _pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    
    # Create and initialize service
    _vector_service = PgVectorService(_pool)
    await _vector_service.initialize()
    
    return _vector_service


async def close_vector_service() -> None:
    """Close vector service and connection pool."""
    global _vector_service, _pool
    
    if _pool is not None:
        await _pool.close()
        _pool = None
    
    _vector_service = None
    logger.info("vector_service_closed")
