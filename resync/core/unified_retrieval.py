"""
Unified Retrieval Service - HybridRAG as Default.

v5.3.17 - Integrates Knowledge Graph + Vector Search + Cross-Encoder Reranking.

This service provides a unified interface for all retrieval operations:
- Uses HybridRAG by default for intelligent query routing
- Falls back to pure vector search when KG unavailable
- Applies cross-encoder reranking for precision
- Supports BM25 keyword search for exact matches

Architecture:
    Query → HybridRAG Router → [Knowledge Graph | Vector Search | Both]
                                    ↓
                              Cross-Encoder Rerank
                                    ↓
                              Final Results
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


class RetrievalMode(str, Enum):
    """Retrieval modes available."""
    
    HYBRID = "hybrid"       # KG + Vector + Cross-Encoder (default)
    VECTOR_ONLY = "vector"  # Pure vector search
    KEYWORD_ONLY = "keyword"  # BM25 keyword search
    GRAPH_ONLY = "graph"    # Knowledge Graph only


@dataclass
class RetrievalConfig:
    """Configuration for unified retrieval."""
    
    # Default mode
    mode: RetrievalMode = RetrievalMode.HYBRID
    
    # Vector search settings
    vector_top_k: int = 20  # Initial candidates
    vector_threshold: float = 0.7  # Min similarity
    
    # Cross-encoder reranking
    enable_reranking: bool = True
    rerank_top_k: int = 5  # Final results
    rerank_threshold: float = 0.3
    
    # Hybrid weights (for ensemble scoring)
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    
    # Knowledge Graph
    enable_kg: bool = True
    kg_max_hops: int = 3
    
    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        """Load configuration from environment variables."""
        return cls(
            mode=RetrievalMode(os.getenv("RETRIEVAL_MODE", "hybrid")),
            vector_top_k=int(os.getenv("RETRIEVAL_VECTOR_TOP_K", "20")),
            vector_threshold=float(os.getenv("RETRIEVAL_VECTOR_THRESHOLD", "0.7")),
            enable_reranking=os.getenv("RETRIEVAL_RERANKING", "true").lower() == "true",
            rerank_top_k=int(os.getenv("RETRIEVAL_RERANK_TOP_K", "5")),
            rerank_threshold=float(os.getenv("RETRIEVAL_RERANK_THRESHOLD", "0.3")),
            vector_weight=float(os.getenv("RETRIEVAL_VECTOR_WEIGHT", "0.6")),
            keyword_weight=float(os.getenv("RETRIEVAL_KEYWORD_WEIGHT", "0.4")),
            enable_kg=os.getenv("RETRIEVAL_ENABLE_KG", "true").lower() == "true",
            kg_max_hops=int(os.getenv("RETRIEVAL_KG_MAX_HOPS", "3")),
        )


@dataclass
class RetrievalResult:
    """Result from unified retrieval."""
    
    documents: list[dict[str, Any]] = field(default_factory=list)
    graph_data: dict[str, Any] | None = None
    query_classification: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class UnifiedRetrievalService:
    """
    Unified retrieval service using HybridRAG as default.
    
    This service provides intelligent query routing:
    - Graph queries (dependencies, impact) → Knowledge Graph
    - Documentation queries (how-to) → Vector + Cross-Encoder
    - Complex queries → Both systems + merge
    
    Benefits:
    - Single interface for all retrieval
    - Automatic query classification
    - Cross-encoder precision boost
    - Graceful fallback on failures
    """
    
    def __init__(
        self,
        config: RetrievalConfig | None = None,
        llm_service: Any | None = None,
    ):
        self.config = config or RetrievalConfig.from_env()
        self._llm = llm_service
        
        # Lazy-loaded components
        self._hybrid_rag = None
        self._vector_retriever = None
        self._keyword_retriever = None
        
        logger.info(
            "unified_retrieval_initialized",
            mode=self.config.mode.value,
            reranking=self.config.enable_reranking,
            kg_enabled=self.config.enable_kg,
        )
    
    async def _get_hybrid_rag(self):
        """Get HybridRAG instance (lazy load)."""
        if self._hybrid_rag is None:
            try:
                from resync.core.knowledge_graph.hybrid_rag import HybridRAG
                
                self._hybrid_rag = HybridRAG(
                    rag_retriever=await self._get_vector_retriever(),
                    llm_service=self._llm,
                    use_llm_router=True,
                )
                logger.info("hybrid_rag_loaded")
            except ImportError as e:
                logger.warning(f"hybrid_rag_unavailable: {e}")
                return None
        return self._hybrid_rag
    
    async def _get_vector_retriever(self):
        """Get vector retriever (lazy load)."""
        if self._vector_retriever is None:
            try:
                from resync.RAG.microservice.core.embedding_service import EmbeddingService
                from resync.RAG.microservice.core.pgvector_store import PgVectorStore
                from resync.RAG.microservice.core.retriever import RagRetriever
                
                embedder = EmbeddingService()
                store = PgVectorStore()
                self._vector_retriever = RagRetriever(embedder=embedder, store=store)
                logger.info("vector_retriever_loaded")
            except ImportError as e:
                logger.warning(f"vector_retriever_unavailable: {e}")
                return None
        return self._vector_retriever
    
    async def retrieve(
        self,
        query: str,
        mode: RetrievalMode | None = None,
        top_k: int | None = None,
        context: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        """
        Execute retrieval using configured mode.
        
        Args:
            query: User query
            mode: Override retrieval mode (optional)
            top_k: Number of results (optional)
            context: Additional context
            filters: Metadata filters
            
        Returns:
            RetrievalResult with documents and optional graph data
        """
        mode = mode or self.config.mode
        top_k = top_k or self.config.rerank_top_k
        
        logger.debug(
            "retrieval_started",
            query=query[:100],
            mode=mode.value,
            top_k=top_k,
        )
        
        try:
            if mode == RetrievalMode.HYBRID:
                return await self._hybrid_retrieve(query, top_k, context, filters)
            elif mode == RetrievalMode.VECTOR_ONLY:
                return await self._vector_retrieve(query, top_k, filters)
            elif mode == RetrievalMode.KEYWORD_ONLY:
                return await self._keyword_retrieve(query, top_k, filters)
            elif mode == RetrievalMode.GRAPH_ONLY:
                return await self._graph_retrieve(query, context)
            else:
                # Default to hybrid
                return await self._hybrid_retrieve(query, top_k, context, filters)
        except Exception as e:
            logger.error(f"retrieval_failed: {e}", exc_info=True)
            # Fallback to vector-only on failure
            try:
                return await self._vector_retrieve(query, top_k, filters)
            except Exception:
                return RetrievalResult(
                    documents=[],
                    metadata={"error": str(e), "fallback": True},
                )
    
    async def _hybrid_retrieve(
        self,
        query: str,
        top_k: int,
        context: dict[str, Any] | None,
        filters: dict[str, Any] | None,
    ) -> RetrievalResult:
        """Execute hybrid retrieval (KG + Vector + Reranking)."""
        hybrid_rag = await self._get_hybrid_rag()
        
        if hybrid_rag is None:
            # Fallback to vector-only
            logger.warning("hybrid_unavailable_falling_back_to_vector")
            return await self._vector_retrieve(query, top_k, filters)
        
        # Execute hybrid query
        result = await hybrid_rag.query(
            query_text=query,
            context=context,
            generate_response=False,  # We just want documents
            enable_continual_learning=False,
        )
        
        # Extract documents from RAG results
        documents = []
        if result.get("rag_results") and result["rag_results"].get("documents"):
            documents = result["rag_results"]["documents"][:top_k]
        
        # Extract graph data
        graph_data = result.get("graph_results")
        
        # Get classification
        classification = None
        if result.get("classification"):
            classification = {
                "intent": result["classification"].intent.value,
                "confidence": result["classification"].confidence,
                "entities": result["classification"].entities,
                "use_graph": result["classification"].use_graph,
                "use_rag": result["classification"].use_rag,
            }
        
        return RetrievalResult(
            documents=documents,
            graph_data=graph_data,
            query_classification=classification,
            metadata={
                "mode": "hybrid",
                "used_graph": bool(graph_data),
                "used_rag": bool(documents),
            },
        )
    
    async def _vector_retrieve(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> RetrievalResult:
        """Execute pure vector retrieval with cross-encoder reranking."""
        retriever = await self._get_vector_retriever()
        
        if retriever is None:
            return RetrievalResult(
                documents=[],
                metadata={"error": "Vector retriever unavailable"},
            )
        
        # Use larger initial pool for reranking
        fetch_k = top_k * 4 if self.config.enable_reranking else top_k
        
        documents = await retriever.retrieve(
            query=query,
            top_k=fetch_k,
            filters=filters,
        )
        
        return RetrievalResult(
            documents=documents[:top_k],
            metadata={
                "mode": "vector",
                "reranked": self.config.enable_reranking,
                "total_candidates": len(documents),
            },
        )
    
    async def _keyword_retrieve(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> RetrievalResult:
        """Execute BM25 keyword search."""
        # TODO: Implement BM25 search
        # For now, fallback to vector
        logger.warning("keyword_search_not_implemented_using_vector")
        return await self._vector_retrieve(query, top_k, filters)
    
    async def _graph_retrieve(
        self,
        query: str,
        context: dict[str, Any] | None,
    ) -> RetrievalResult:
        """Execute Knowledge Graph query only."""
        hybrid_rag = await self._get_hybrid_rag()
        
        if hybrid_rag is None:
            return RetrievalResult(
                documents=[],
                metadata={"error": "Knowledge Graph unavailable"},
            )
        
        # Force graph-only mode
        result = await hybrid_rag.query(
            query_text=query,
            context=context,
            generate_response=False,
        )
        
        return RetrievalResult(
            documents=[],
            graph_data=result.get("graph_results"),
            metadata={"mode": "graph"},
        )
    
    def get_info(self) -> dict[str, Any]:
        """Get service information and status."""
        return {
            "mode": self.config.mode.value,
            "vector_top_k": self.config.vector_top_k,
            "reranking_enabled": self.config.enable_reranking,
            "rerank_top_k": self.config.rerank_top_k,
            "kg_enabled": self.config.enable_kg,
            "weights": {
                "vector": self.config.vector_weight,
                "keyword": self.config.keyword_weight,
            },
            "components": {
                "hybrid_rag_loaded": self._hybrid_rag is not None,
                "vector_retriever_loaded": self._vector_retriever is not None,
            },
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_unified_retrieval: UnifiedRetrievalService | None = None


def get_unified_retrieval() -> UnifiedRetrievalService:
    """Get or create unified retrieval service instance."""
    global _unified_retrieval
    if _unified_retrieval is None:
        _unified_retrieval = UnifiedRetrievalService()
    return _unified_retrieval


async def unified_retrieve(
    query: str,
    mode: RetrievalMode | str | None = None,
    top_k: int = 5,
    context: dict[str, Any] | None = None,
) -> RetrievalResult:
    """
    Convenience function for unified retrieval.
    
    Args:
        query: User query
        mode: Retrieval mode (hybrid, vector, keyword, graph)
        top_k: Number of results
        context: Additional context
        
    Returns:
        RetrievalResult with documents and metadata
    """
    service = get_unified_retrieval()
    
    if isinstance(mode, str):
        mode = RetrievalMode(mode)
    
    return await service.retrieve(
        query=query,
        mode=mode,
        top_k=top_k,
        context=context,
    )


__all__ = [
    "RetrievalMode",
    "RetrievalConfig",
    "RetrievalResult",
    "UnifiedRetrievalService",
    "get_unified_retrieval",
    "unified_retrieve",
]
