"""
Configuration for the pgvector-based RAG system.

Defines environment variables and defaults for PostgreSQL connection, embedding model, and search parameters.
"""


import os
from dataclasses import dataclass


def _bool(env: str, default: bool = False) -> bool:
    v = os.getenv(env)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RagConfig:
    """Configuration model for RAG with pgvector."""

    # PostgreSQL connection (uses main DATABASE_URL)
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://resync:password@localhost:5432/resync"
    )

    # Collection names (stored in collection_name column)
    collection_write: str = os.getenv("RAG_COLLECTION_WRITE", "knowledge_v1")
    collection_read: str = os.getenv("RAG_COLLECTION_READ", "knowledge_v1")

    # Embedding settings
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    embed_dim: int = int(os.getenv("EMBED_DIM", "1536"))

    # Search parameters
    max_top_k: int = int(os.getenv("RAG_MAX_TOPK", "50"))

    # HNSW index parameters (used during table creation)
    hnsw_m: int = int(os.getenv("RAG_HNSW_M", "16"))
    hnsw_ef_construction: int = int(os.getenv("RAG_HNSW_EF_CONSTRUCTION", "256"))

    # Search tuning
    ef_search_base: int = int(os.getenv("RAG_EF_SEARCH_BASE", "64"))
    ef_search_max: int = int(os.getenv("RAG_EF_SEARCH_MAX", "128"))
    max_neighbors: int = int(os.getenv("RAG_MAX_NEIGHBORS", "32"))

    # Reranking
    enable_rerank: bool = _bool("RAG_RERANKER_ON", False)


CFG = RagConfig()
