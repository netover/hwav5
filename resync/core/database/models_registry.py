"""
Models Registry - Imports all SQLAlchemy models to ensure they are registered.

This module must be imported before calling init_db() to ensure all
models are registered with SQLAlchemy's Base.metadata.

Usage:
    from resync.core.database.models_registry import register_all_models
    register_all_models()
    await init_db()  # Now all tables will be created
"""

import logging

logger = logging.getLogger(__name__)

_registered = False


def register_all_models():
    """
    Import all SQLAlchemy models to register them with Base.metadata.
    
    This must be called before init_db() to ensure all tables are created.
    """
    global _registered
    
    if _registered:
        return
    
    # Import all model modules to register them with Base
    try:
        # FastAPI app models (Users, Sessions, etc.)
        from resync.fastapi_app.db.models import (
            User,
            Session,
            APIKey,
        )
        logger.debug("Registered fastapi_app models")
    except ImportError as e:
        logger.warning(f"Could not import fastapi_app models: {e}")
    
    try:
        # Knowledge Graph models
        from resync.core.knowledge_graph.models import (
            GraphNode,
            GraphEdge,
            ExtractedTriplet,
            GraphSnapshot,
        )
        logger.debug("Registered knowledge_graph models")
    except ImportError as e:
        logger.warning(f"Could not import knowledge_graph models: {e}")
    
    _registered = True
    logger.info("All database models registered")


# Convenience: auto-register when module is imported
register_all_models()
