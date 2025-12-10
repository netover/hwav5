"""
Vector Store Module - pgvector PostgreSQL Extension.

This module provides vector similarity search using PostgreSQL's pgvector extension,
replacing the previous Qdrant integration for a unified database stack.

Components:
- PgVectorService: Main service for vector operations
- VectorDocument: Document model for embeddings
- EmbeddingProvider: Interface for embedding generation

Usage:
    from resync.core.vector import get_vector_service, VectorDocument
    
    service = await get_vector_service()
    
    # Add documents
    doc = VectorDocument(
        document_id="doc1",
        content="TWS job scheduling guide",
        metadata={"source": "manual"}
    )
    await service.upsert([doc], collection="tws_docs")
    
    # Search
    results = await service.search("how to schedule jobs", collection="tws_docs", limit=5)
"""

from .pgvector_service import (
    PgVectorService,
    get_vector_service,
    VectorDocument,
    SearchResult,
    CollectionStats,
)

from .embedding_provider import (
    EmbeddingProvider,
    LiteLLMEmbeddingProvider,
    get_embedding_provider,
)

__all__ = [
    # Service
    "PgVectorService",
    "get_vector_service",
    
    # Models
    "VectorDocument",
    "SearchResult",
    "CollectionStats",
    
    # Embedding
    "EmbeddingProvider",
    "LiteLLMEmbeddingProvider",
    "get_embedding_provider",
]
