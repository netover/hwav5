"""
RAG Service Configuration.

Configures the RAG system including:
- PostgreSQL/pgvector connection settings
- Embedding model settings
- Chunking parameters
"""

import os
from dataclasses import dataclass, field


@dataclass
class RAGConfig:
    """Configuration for RAG service with pgvector."""

    # PostgreSQL settings (uses main DATABASE_URL)
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://resync:password@localhost:5432/resync"
        )
    )
    collection_name: str = field(
        default_factory=lambda: os.getenv("RAG_COLLECTION", "resync_documents")
    )

    # Embedding settings
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    embedding_dim: int = 1536

    # Chunking settings
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Service settings
    use_mock: bool = field(
        default_factory=lambda: os.getenv("RAG_USE_MOCK", "true").lower() == "true"
    )
    upload_dir: str = field(
        default_factory=lambda: os.getenv("RAG_UPLOAD_DIR", "uploads")
    )

    # Search settings
    default_top_k: int = 10
    max_top_k: int = 100

    @classmethod
    def from_env(cls) -> "RAGConfig":
        """Create configuration from environment variables."""
        return cls()

    def is_pgvector_configured(self) -> bool:
        """Check if pgvector is properly configured."""
        return bool(self.database_url) and not self.use_mock


# Global configuration instance
_config: RAGConfig | None = None


def get_rag_config() -> RAGConfig:
    """Get or create RAG configuration."""
    global _config
    if _config is None:
        _config = RAGConfig.from_env()
    return _config


def reset_rag_config():
    """Reset configuration (for testing)."""
    global _config
    _config = None
