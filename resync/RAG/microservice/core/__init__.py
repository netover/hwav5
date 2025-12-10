"""
Core components of the pgvector-based RAG microservice.

Exports all public interfaces and implementations for easy import.

Components:
- EmbeddingService: Multi-provider embedding using LiteLLM
- DocumentParser: PDF/HTML/Markdown parsing for IBM/HCL docs
- IngestService: Document ingestion with deduplication
- RagRetriever: Vector search with reranking
- PgVectorStore: PostgreSQL pgvector-based storage (replaces Qdrant)
"""

from .document_parser import (
    DocumentationFetcher,
    DocumentChunk,
    DocumentParser,
    DocumentType,
    HTMLParser,
    ParsedDocument,
    PDFParser,
    create_document_parser,
    create_html_parser,
    create_pdf_parser,
)
from .embedding_service import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingService,
    MultiProviderEmbeddingService,
    create_embedding_service,
)
from .ingest import IngestService
from .interfaces import Embedder, Retriever, VectorStore

# Use pgvector store (PostgreSQL) instead of Qdrant
from .pgvector_store import PgVectorStore, get_default_store
from .retriever import RagRetriever

__all__ = [
    # Interfaces
    "Embedder",
    "VectorStore",
    "Retriever",

    # Embedding Service (LiteLLM multi-provider)
    "EmbeddingService",
    "MultiProviderEmbeddingService",
    "EmbeddingProvider",
    "EmbeddingConfig",
    "create_embedding_service",

    # Document Parsing (PDF/HTML/Markdown)
    "DocumentParser",
    "PDFParser",
    "HTMLParser",
    "DocumentType",
    "ParsedDocument",
    "DocumentChunk",
    "DocumentationFetcher",
    "create_document_parser",
    "create_pdf_parser",
    "create_html_parser",

    # Vector Store (pgvector)
    "PgVectorStore",
    "get_default_store",

    # Retrieval
    "RagRetriever",

    # Ingestion
    "IngestService",
]
