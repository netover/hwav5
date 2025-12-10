# CHANGELOG v5.2.3.28 - Multi-Provider Embeddings & Document Processing

**Release Date:** December 10, 2024  
**Version:** 5.2.3.28

## Overview

This release adds two major enhancements:
1. **Multi-Provider Embedding Service** - LiteLLM-based embeddings supporting OpenAI, Cohere, Ollama, and more
2. **Document Processing** - BeautifulSoup4 + PyPDF for ingesting IBM/HCL TWS documentation

## 🔌 Multi-Provider Embedding Service

### Supported Providers

| Provider | Model Examples | Dimension |
|----------|---------------|-----------|
| **OpenAI** | text-embedding-3-small, text-embedding-ada-002 | 1536, 3072 |
| **Azure OpenAI** | azure/text-embedding-3-small | 1536 |
| **Cohere** | embed-english-v3.0, embed-multilingual-v3.0 | 1024 |
| **Ollama** | ollama/nomic-embed-text, ollama/bge-base-en | 768, 1024 |
| **Voyage AI** | voyage/voyage-2, voyage/voyage-code-2 | 1024, 1536 |
| **HuggingFace** | huggingface/BAAI/bge-large-en | 1024 |
| **AWS Bedrock** | bedrock/amazon.titan-embed-text-v1 | 1024 |
| **Google Vertex** | vertex_ai/textembedding-gecko | 768 |
| **Mistral** | mistral/mistral-embed | 1024 |
| **Jina** | jina/jina-embeddings-v2-base-en | 768 |

### Features

- **Auto-Detection**: Provider automatically detected from model name
- **Dimension Inference**: Embedding dimension inferred from model
- **Batch Processing**: Configurable batch size for large document sets
- **Retry Logic**: Exponential backoff on API failures
- **Hash Fallback**: Deterministic SHA-256 based fallback for dev/CI
- **Statistics**: Request counts, error rates, provider usage

### Usage Examples

```python
from resync.RAG.microservice.core import (
    create_embedding_service,
    EmbeddingProvider,
)

# OpenAI (auto-detected)
service = create_embedding_service(model="text-embedding-3-small")

# Cohere with explicit provider
service = create_embedding_service(
    provider="cohere",
    model="embed-multilingual-v3.0"
)

# Ollama local
service = create_embedding_service(
    provider="ollama",
    model="nomic-embed-text",
    api_base="http://localhost:11434"
)

# Embed texts
vectors = await service.embed_batch(["doc1", "doc2", "doc3"])
```

### Environment Variables

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Cohere
COHERE_API_KEY=...

# Voyage AI
VOYAGE_API_KEY=...

# HuggingFace
HUGGINGFACE_API_KEY=...

# AWS Bedrock (uses AWS credentials)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Google Vertex (uses service account)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Ollama (no API key needed)
OLLAMA_API_BASE=http://localhost:11434
```

## 📄 Document Processing

### PDF Parser

Optimized for IBM/HCL TWS documentation manuals:

- **Text Extraction**: Full text extraction with layout preservation
- **Table Detection**: Automatic table structure recognition
- **Section Detection**: Heading hierarchy extraction
- **Header/Footer Removal**: Automatic removal of page numbers and footers
- **Metadata Extraction**: Title, author, dates, TWS version detection
- **OCR Cleanup**: Common OCR error correction (ligatures, quotes)

### HTML Parser (BeautifulSoup4)

Optimized for IBM Knowledge Center and HCL Documentation:

- **Navigation Removal**: Automatic removal of nav, sidebar, breadcrumbs
- **Code Block Preservation**: Code examples kept with formatting
- **Link Extraction**: Resolved internal/external links
- **Table Extraction**: Structured table data
- **Section Hierarchy**: H1-H6 heading structure
- **Encoding Handling**: Multi-encoding support (UTF-8, Latin-1, etc.)

### Supported Sources

| Source | Tool | Features |
|--------|------|----------|
| TWS PDF Manuals | PyPDF | Tables, sections, metadata |
| IBM Knowledge Center | BeautifulSoup4 | Navigation removal, code blocks |
| HCL Documentation | BeautifulSoup4 | Navigation removal, code blocks |
| Markdown files | Native | Heading extraction |

### Usage Examples

```python
from resync.RAG.microservice.core import (
    create_document_parser,
    create_pdf_parser,
    create_html_parser,
)

# Unified parser (auto-detects type)
parser = create_document_parser()
doc = parser.parse("/path/to/TWS_manual.pdf")
print(doc.title, doc.metadata)

# PDF specifically
pdf_parser = create_pdf_parser(extract_tables=True)
doc = pdf_parser.parse("/path/to/TWS_manual.pdf")
for table in doc.tables:
    print(table)

# HTML from IBM Knowledge Center
html_parser = create_html_parser()
doc = html_parser.parse(html_content, url="https://ibm.com/docs/...")

# Chunk for RAG ingestion
for chunk in parser.chunk(doc, chunk_size=1000, chunk_overlap=200):
    print(f"Chunk {chunk.chunk_index}: {len(chunk.content)} chars")
```

### Documentation Fetcher

For fetching online documentation:

```python
from resync.RAG.microservice.core.document_parser import DocumentationFetcher

fetcher = DocumentationFetcher(cache_dir=Path("./doc_cache"))
content, metadata = await fetcher.fetch(
    "https://www.ibm.com/docs/en/workload-automation/..."
)
```

## 📁 Files Changed

### New Files
- `resync/RAG/microservice/core/embedding_service.py` (505 lines) - Rewritten
- `resync/RAG/microservice/core/document_parser.py` (712 lines) - New
- `tests/RAG/test_embedding_document_parser.py` (380 lines) - New

### Modified Files
- `resync/RAG/microservice/core/__init__.py` - New exports
- `resync/core/file_ingestor.py` - Added HTML support
- `requirements.txt` - Added beautifulsoup4, lxml, pypdf

## 📦 New Dependencies

```txt
beautifulsoup4>=4.12.0   # HTML parsing
lxml>=5.0.0              # Fast HTML/XML parser
pypdf>=3.17.0            # PDF text extraction
```

## 🔄 Backwards Compatibility

- `EmbeddingService` class is now an alias to `MultiProviderEmbeddingService`
- Existing code using `EmbeddingService()` continues to work unchanged
- Default model and dimension from environment variables preserved

## 📊 API Summary

### Embedding Service
```python
# Classes
MultiProviderEmbeddingService  # Main implementation
EmbeddingService              # Backwards-compatible alias
EmbeddingProvider             # Enum: openai, cohere, ollama, etc.
EmbeddingConfig               # Configuration dataclass

# Functions
create_embedding_service(provider, model, **kwargs)

# Methods
await service.embed(text) -> List[float]
await service.embed_batch(texts) -> List[List[float]]
service.get_stats() -> Dict[str, Any]
```

### Document Parser
```python
# Classes
DocumentParser      # Unified parser
PDFParser          # PDF-specific
HTMLParser         # HTML-specific
ParsedDocument     # Parse result
DocumentChunk      # Chunk result
DocumentType       # Enum: pdf, html, markdown, text

# Functions
create_document_parser()
create_pdf_parser(**kwargs)
create_html_parser(**kwargs)

# Methods
parser.parse(source, document_type=None) -> ParsedDocument
parser.chunk(document, chunk_size, chunk_overlap) -> Generator[DocumentChunk]
```

## ✅ Validation

- All Python files compile successfully
- Syntax validation passed
- Test suite created (380 lines)
- Backwards compatibility maintained
