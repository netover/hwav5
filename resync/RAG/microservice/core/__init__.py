"""
Core components of the Qdrant-only RAG microservice.

Exports all public interfaces and implementations for easy import.

Components:
- EmbeddingService: Multi-provider embedding using LiteLLM
- DocumentParser: PDF/HTML/Markdown parsing for IBM/HCL docs
- IngestService: Document ingestion with deduplication
- RagRetriever: Vector search with reranking
"""

from .embedding_service import (
    EmbeddingService,
    MultiProviderEmbeddingService,
    EmbeddingProvider,
    EmbeddingConfig,
    create_embedding_service,
)
from .document_parser import (
    DocumentParser,
    PDFParser,
    HTMLParser,
    DocumentType,
    ParsedDocument,
    DocumentChunk,
    DocumentationFetcher,
    create_document_parser,
    create_pdf_parser,
    create_html_parser,
)
from .ingest import IngestService
from .interfaces import Embedder
from .interfaces import Retriever
from .interfaces import VectorStore
from .retriever import RagRetriever
from .vector_store import QdrantVectorStore
from .vector_store import get_default_store

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
    
    # Vector Store
    "QdrantVectorStore",
    "get_default_store",
    
    # Retrieval
    "RagRetriever",
    
    # Ingestion
    "IngestService",
]