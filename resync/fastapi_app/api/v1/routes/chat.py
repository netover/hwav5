"""
Chat routes for FastAPI with RAG integration and Unified Agent routing.

This module provides the chat API endpoints using the UnifiedAgent system
which automatically routes messages to the appropriate handler based on
intent classification. Users no longer need to select a specific agent.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

# Import Unified Agent
from resync.core.agent_manager import unified_agent

# Import RAG components
from resync.RAG.microservice.core.embedding_service import EmbeddingService
from resync.RAG.microservice.core.ingest import IngestService
from resync.RAG.microservice.core.retriever import RagRetriever
from resync.RAG.microservice.core.pgvector_store import get_default_store

from ..dependencies import get_logger
from ..models.request_models import ChatHistoryQuery, ChatMessageRequest
from ..models.response_models import ChatMessageResponse

router = APIRouter()
logger = None  # Will be injected by dependency

# RAG components will be initialized lazily (when first used)
# to avoid event loop issues during module import
_rag_initialized = False
_rag_embedding_service = None
_rag_vector_store = None
_rag_retriever = None
_rag_ingest_service = None


async def _get_rag_components():
    """Lazy initialization of RAG components within async context"""
    global \
        _rag_initialized, \
        _rag_embedding_service, \
        _rag_vector_store, \
        _rag_retriever, \
        _rag_ingest_service

    if not _rag_initialized:
        try:
            _rag_embedding_service = EmbeddingService()
            _rag_vector_store = get_default_store()
            _rag_retriever = RagRetriever(_rag_embedding_service, _rag_vector_store)
            _rag_ingest_service = IngestService(_rag_embedding_service, _rag_vector_store)
            _rag_initialized = True
            if logger:
                logger.info("RAG components initialized successfully (lazy)")
        except Exception as e:
            if logger:
                logger.error(f"Failed to initialize RAG components: {e}", exc_info=True)
            _rag_embedding_service = None
            _rag_vector_store = None
            _rag_retriever = None
            _rag_ingest_service = None

    return _rag_embedding_service, _rag_vector_store, _rag_retriever, _rag_ingest_service


@router.post("/chat", response_model=ChatMessageResponse)
async def chat_message(
    request: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    # Temporarily disabled authentication for testing
    # current_user: dict = Depends(get_current_user),
    logger_instance=Depends(get_logger),
):
    """
    Send chat message to Resync AI Assistant.

    The message is automatically routed to the appropriate handler based on
    intent classification. No agent_id selection is required - the system
    automatically determines the best handler for each query.

    Supported intents:
    - Status queries (job status, workstation status)
    - Troubleshooting (error analysis, diagnostics)
    - Job management (run, stop, rerun operations)
    - Monitoring (real-time status, alerts)
    - Analysis (trends, patterns, historical data)
    - General assistance (help, explanations)
    """
    global logger
    logger = logger_instance

    try:
        # Use the Unified Agent for automatic routing
        result = await unified_agent.chat_with_metadata(
            message=request.message, include_history=True, tws_instance_id=request.tws_instance_id
        )

        response_message = result["response"]

        logger_instance.info(
            "chat_message_processed",
            user_id="test_user",
            intent=result["intent"],
            confidence=result["confidence"],
            handler=result["handler"],
            tools_used=result["tools_used"],
            tws_instance_id=request.tws_instance_id,
            message_length=len(request.message),
            response_length=len(response_message),
            processing_time_ms=result["processing_time_ms"],
        )

        return ChatMessageResponse(
            message=response_message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=result["handler"],  # Return the handler that processed the message
            is_final=True,
            metadata={
                "intent": result["intent"],
                "confidence": result["confidence"],
                "tools_used": result["tools_used"],
                "entities": result["entities"],
                "tws_instance_id": request.tws_instance_id,
            },
        )

    except Exception as e:
        logger_instance.error("chat_message_error", error=str(e), user_id="test_user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message",
        ) from e


@router.post("/chat/analyze", response_model=dict)
async def analyze_message(request: ChatMessageRequest, logger_instance=Depends(get_logger)):
    """
    Analyze a message without processing it.

    Returns the intent classification, confidence score, and which handler
    would process the message. Useful for debugging and understanding
    how the router interprets different queries.
    """
    global logger
    logger = logger_instance

    try:
        from resync.core.agent_router import IntentClassifier

        classifier = IntentClassifier()
        classification = classifier.classify(request.message)

        return {
            "message": request.message,
            "primary_intent": classification.primary_intent.value,
            "confidence": classification.confidence,
            "secondary_intents": [i.value for i in classification.secondary_intents],
            "entities": classification.entities,
            "requires_tools": classification.requires_tools,
            "is_high_confidence": classification.is_high_confidence,
            "needs_clarification": classification.needs_clarification,
        }

    except Exception as e:
        logger_instance.error("analyze_message_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to analyze message"
        ) from e


@router.get("/chat/history")
async def chat_history(
    query_params: ChatHistoryQuery = Depends(),
    # Temporarily disabled authentication for testing
    # current_user: dict = Depends(get_current_user)
):
    """Get chat history for the current session."""
    history = unified_agent.get_history()

    return {
        "history": history,
        "agent_id": "unified",  # Always unified now
        "total_messages": len(history),
    }


@router.delete("/chat/history")
async def clear_chat_history(
    query_params: ChatHistoryQuery = Depends(),
    # Temporarily disabled authentication for testing
    # current_user: dict = Depends(get_current_user),
    logger_instance=Depends(get_logger),
):
    """Clear chat history for the current session."""
    unified_agent.clear_history()

    logger_instance.info("chat_history_cleared", user_id="test_user")
    return {"message": "Chat history cleared successfully"}


@router.get("/chat/intents")
async def list_supported_intents():
    """
    List all supported intents and their descriptions.

    Useful for understanding what types of queries the system can handle.
    """
    from resync.core.agent_router import Intent

    intent_descriptions = {
        Intent.STATUS.value: "Check system, job, or workstation status",
        Intent.TROUBLESHOOTING.value: "Diagnose and resolve issues, analyze errors",
        Intent.JOB_MANAGEMENT.value: "Run, stop, rerun, or schedule jobs",
        Intent.MONITORING.value: "Real-time monitoring and alerts",
        Intent.ANALYSIS.value: "Deep analysis of patterns and trends",
        Intent.REPORTING.value: "Generate reports and summaries",
        Intent.GREETING.value: "Greetings and introductions",
        Intent.GENERAL.value: "General questions and help",
    }

    return {"intents": intent_descriptions, "total": len(intent_descriptions)}
