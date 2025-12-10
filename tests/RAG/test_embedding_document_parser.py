"""
Tests for Multi-Provider Embedding Service and Document Parser.

Tests cover:
- LiteLLM-based embedding service
- Provider auto-detection
- Hash fallback mechanism
- PDF parsing
- HTML parsing
- Document chunking
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Embedding Service Tests
# =============================================================================

class TestMultiProviderEmbeddingService:
    """Tests for MultiProviderEmbeddingService."""
    
    def test_import(self):
        """Test that embedding service can be imported."""
        from resync.RAG.microservice.core.embedding_service import (
            EmbeddingService,
            MultiProviderEmbeddingService,
            EmbeddingProvider,
            create_embedding_service,
        )
        
        assert EmbeddingService is not None
        assert MultiProviderEmbeddingService is not None
        assert EmbeddingProvider is not None
        assert create_embedding_service is not None
    
    def test_provider_enum(self):
        """Test EmbeddingProvider enum values."""
        from resync.RAG.microservice.core.embedding_service import EmbeddingProvider
        
        assert EmbeddingProvider.OPENAI.value == "openai"
        assert EmbeddingProvider.COHERE.value == "cohere"
        assert EmbeddingProvider.OLLAMA.value == "ollama"
        assert EmbeddingProvider.AUTO.value == "auto"
    
    def test_auto_detect_openai_provider(self):
        """Test auto-detection of OpenAI provider from model name."""
        from resync.RAG.microservice.core.embedding_service import (
            MultiProviderEmbeddingService,
            EmbeddingProvider,
        )
        
        service = MultiProviderEmbeddingService(model="text-embedding-3-small")
        assert service.provider == EmbeddingProvider.OPENAI
    
    def test_auto_detect_cohere_provider(self):
        """Test auto-detection of Cohere provider from model name."""
        from resync.RAG.microservice.core.embedding_service import (
            MultiProviderEmbeddingService,
            EmbeddingProvider,
        )
        
        service = MultiProviderEmbeddingService(model="cohere/embed-english-v3.0")
        assert service.provider == EmbeddingProvider.COHERE
    
    def test_auto_detect_ollama_provider(self):
        """Test auto-detection of Ollama provider from model name."""
        from resync.RAG.microservice.core.embedding_service import (
            MultiProviderEmbeddingService,
            EmbeddingProvider,
        )
        
        service = MultiProviderEmbeddingService(model="ollama/nomic-embed-text")
        assert service.provider == EmbeddingProvider.OLLAMA
    
    def test_dimension_inference_openai(self):
        """Test dimension inference for OpenAI models."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="text-embedding-3-small")
        assert service.dimension == 1536
        
        service_large = MultiProviderEmbeddingService(model="text-embedding-3-large")
        assert service_large.dimension == 3072
    
    def test_dimension_inference_cohere(self):
        """Test dimension inference for Cohere models."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="embed-english-v3.0")
        assert service.dimension == 1024
    
    def test_hash_fallback(self):
        """Test hash-based fallback embedding."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="test-model")
        
        # Without API key, should use hash fallback
        vec = service._hash_vec("test text")
        
        assert len(vec) == service.dimension
        assert all(isinstance(v, float) for v in vec)
        assert all(0 <= v <= 1 for v in vec)
    
    def test_hash_deterministic(self):
        """Test that hash-based embeddings are deterministic."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="test-model")
        
        vec1 = service._hash_vec("hello world")
        vec2 = service._hash_vec("hello world")
        
        assert vec1 == vec2
    
    def test_hash_different_for_different_text(self):
        """Test that hash differs for different texts."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="test-model")
        
        vec1 = service._hash_vec("hello world")
        vec2 = service._hash_vec("goodbye world")
        
        assert vec1 != vec2
    
    @pytest.mark.asyncio
    async def test_embed_single(self):
        """Test single text embedding."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="test-model")
        
        vec = await service.embed("test text")
        
        assert len(vec) == service.dimension
        assert all(isinstance(v, float) for v in vec)
    
    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """Test batch embedding."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="test-model")
        
        texts = ["text 1", "text 2", "text 3"]
        vecs = await service.embed_batch(texts)
        
        assert len(vecs) == 3
        for vec in vecs:
            assert len(vec) == service.dimension
    
    @pytest.mark.asyncio
    async def test_embed_empty_batch(self):
        """Test empty batch returns empty list."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="test-model")
        
        vecs = await service.embed_batch([])
        
        assert vecs == []
    
    def test_get_stats(self):
        """Test statistics retrieval."""
        from resync.RAG.microservice.core.embedding_service import MultiProviderEmbeddingService
        
        service = MultiProviderEmbeddingService(model="test-model")
        
        stats = service.get_stats()
        
        assert "total_requests" in stats
        assert "total_texts" in stats
        assert "model" in stats
        assert "provider" in stats
    
    def test_factory_function(self):
        """Test create_embedding_service factory function."""
        from resync.RAG.microservice.core.embedding_service import (
            create_embedding_service,
            EmbeddingProvider,
        )
        
        service = create_embedding_service("openai")
        assert service.provider == EmbeddingProvider.OPENAI
        
        service_ollama = create_embedding_service("ollama")
        assert service_ollama.provider == EmbeddingProvider.OLLAMA
    
    def test_backwards_compatibility(self):
        """Test that EmbeddingService alias works."""
        from resync.RAG.microservice.core.embedding_service import EmbeddingService
        
        service = EmbeddingService()
        assert service is not None
        assert hasattr(service, "embed")
        assert hasattr(service, "embed_batch")


# =============================================================================
# Document Parser Tests
# =============================================================================

class TestDocumentParser:
    """Tests for DocumentParser."""
    
    def test_import(self):
        """Test that document parser can be imported."""
        from resync.RAG.microservice.core.document_parser import (
            DocumentParser,
            PDFParser,
            HTMLParser,
            DocumentType,
            ParsedDocument,
            DocumentChunk,
            create_document_parser,
        )
        
        assert DocumentParser is not None
        assert PDFParser is not None
        assert HTMLParser is not None
        assert DocumentType is not None
        assert ParsedDocument is not None
        assert DocumentChunk is not None
    
    def test_document_type_enum(self):
        """Test DocumentType enum values."""
        from resync.RAG.microservice.core.document_parser import DocumentType
        
        assert DocumentType.PDF.value == "pdf"
        assert DocumentType.HTML.value == "html"
        assert DocumentType.MARKDOWN.value == "markdown"
        assert DocumentType.TEXT.value == "text"
    
    def test_parsed_document_dataclass(self):
        """Test ParsedDocument dataclass."""
        from resync.RAG.microservice.core.document_parser import (
            ParsedDocument,
            DocumentType,
        )
        
        doc = ParsedDocument(
            title="Test Document",
            content="This is test content.",
            source="test.txt",
            document_type=DocumentType.TEXT,
        )
        
        assert doc.title == "Test Document"
        assert doc.content == "This is test content."
        assert doc.sha256 is not None
        assert len(doc.sha256) == 64
    
    def test_document_chunk_dataclass(self):
        """Test DocumentChunk dataclass."""
        from resync.RAG.microservice.core.document_parser import (
            DocumentChunk,
            DocumentType,
        )
        
        chunk = DocumentChunk(
            content="Chunk content",
            chunk_index=0,
            total_chunks=1,
            source="test.txt",
            document_type=DocumentType.TEXT,
        )
        
        assert chunk.content == "Chunk content"
        assert chunk.sha256 is not None
    
    def test_type_detection_from_path(self):
        """Test document type auto-detection from file path."""
        from resync.RAG.microservice.core.document_parser import (
            DocumentParser,
            DocumentType,
        )
        
        parser = DocumentParser()
        
        # PDF
        pdf_type = parser._detect_type(Path("document.pdf"))
        assert pdf_type == DocumentType.PDF
        
        # HTML
        html_type = parser._detect_type(Path("page.html"))
        assert html_type == DocumentType.HTML
        
        # Markdown
        md_type = parser._detect_type(Path("readme.md"))
        assert md_type == DocumentType.MARKDOWN
    
    def test_type_detection_from_content(self):
        """Test document type auto-detection from content."""
        from resync.RAG.microservice.core.document_parser import (
            DocumentParser,
            DocumentType,
        )
        
        parser = DocumentParser()
        
        # HTML content
        html_content = "<!DOCTYPE html><html><body>Test</body></html>"
        html_type = parser._detect_type(html_content)
        assert html_type == DocumentType.HTML
        
        # PDF bytes
        pdf_bytes = b"%PDF-1.4 test content"
        pdf_type = parser._detect_type(pdf_bytes)
        assert pdf_type == DocumentType.PDF


class TestHTMLParser:
    """Tests for HTMLParser."""
    
    def test_html_parser_init(self):
        """Test HTMLParser initialization."""
        from resync.RAG.microservice.core.document_parser import HTMLParser
        
        parser = HTMLParser()
        assert parser.remove_navigation is True
        assert parser.preserve_code_blocks is True
    
    def test_html_parser_custom_options(self):
        """Test HTMLParser with custom options."""
        from resync.RAG.microservice.core.document_parser import HTMLParser
        
        parser = HTMLParser(
            remove_navigation=False,
            preserve_code_blocks=False,
            extract_links=False,
        )
        
        assert parser.remove_navigation is False
        assert parser.preserve_code_blocks is False
        assert parser.extract_links is False
    
    @pytest.mark.skipif(
        not _has_bs4(),
        reason="BeautifulSoup4 not installed"
    )
    def test_html_parser_parse_string(self):
        """Test parsing HTML from string."""
        from resync.RAG.microservice.core.document_parser import (
            HTMLParser,
            DocumentType,
        )
        
        parser = HTMLParser()
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body>
            <nav>Navigation content</nav>
            <main>
                <h1>Main Title</h1>
                <p>Test paragraph content.</p>
            </main>
        </body>
        </html>
        """
        
        doc = parser.parse(html)
        
        assert doc.title == "Test Page"
        assert doc.document_type == DocumentType.HTML
        assert "Main Title" in doc.content
        assert "Test paragraph content" in doc.content
        # Navigation should be removed
        assert "Navigation content" not in doc.content


class TestPDFParser:
    """Tests for PDFParser."""
    
    def test_pdf_parser_init(self):
        """Test PDFParser initialization."""
        from resync.RAG.microservice.core.document_parser import PDFParser
        
        parser = PDFParser()
        assert parser.extract_tables is True
        assert parser.remove_headers_footers is True
    
    def test_pdf_parser_text_cleaning(self):
        """Test PDF text cleaning."""
        from resync.RAG.microservice.core.document_parser import PDFParser
        
        parser = PDFParser()
        
        # Test excessive whitespace removal
        text = "Line 1\n\n\n\n\nLine 2"
        cleaned = parser._clean_text(text)
        assert "\n\n\n\n" not in cleaned
        
        # Test ligature replacement
        text2 = "ﬁnal ﬂow"
        cleaned2 = parser._clean_text(text2)
        assert "final" in cleaned2
        assert "flow" in cleaned2


class TestDocumentChunking:
    """Tests for document chunking."""
    
    def test_single_chunk_for_short_content(self):
        """Test that short content produces single chunk."""
        from resync.RAG.microservice.core.document_parser import (
            DocumentParser,
            ParsedDocument,
            DocumentType,
        )
        
        parser = DocumentParser()
        doc = ParsedDocument(
            title="Short Doc",
            content="Short content.",
            source="short.txt",
            document_type=DocumentType.TEXT,
        )
        
        chunks = list(parser.chunk(doc, chunk_size=1000))
        
        assert len(chunks) == 1
        assert chunks[0].content == "Short content."
        assert chunks[0].total_chunks == 1
    
    def test_multiple_chunks_for_long_content(self):
        """Test that long content produces multiple chunks."""
        from resync.RAG.microservice.core.document_parser import (
            DocumentParser,
            ParsedDocument,
            DocumentType,
        )
        
        parser = DocumentParser()
        
        # Create long content
        long_content = "This is a test sentence. " * 100
        
        doc = ParsedDocument(
            title="Long Doc",
            content=long_content,
            source="long.txt",
            document_type=DocumentType.TEXT,
        )
        
        chunks = list(parser.chunk(doc, chunk_size=100, chunk_overlap=20))
        
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == len(chunks)


# =============================================================================
# Integration Tests
# =============================================================================

class TestFileIngestorHTML:
    """Tests for HTML support in FileIngestor."""
    
    def test_html_reader_in_file_readers(self):
        """Test that HTML reader is in file_readers dict."""
        from resync.core.file_ingestor import FileIngestor
        from unittest.mock import MagicMock
        
        mock_kg = MagicMock()
        ingestor = FileIngestor(mock_kg)
        
        assert ".html" in ingestor.file_readers
        assert ".htm" in ingestor.file_readers


# =============================================================================
# Helpers
# =============================================================================

def _has_bs4() -> bool:
    """Check if BeautifulSoup4 is installed."""
    try:
        from bs4 import BeautifulSoup
        return True
    except ImportError:
        return False


def _has_pypdf() -> bool:
    """Check if pypdf is installed."""
    try:
        import pypdf
        return True
    except ImportError:
        return False
