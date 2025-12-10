"""
Context Store - Armazenamento de contexto usando SQLite

Funcionalidades:
- Armazena conversas e histórico de interações
- Gerencia auditoria de memórias
- Integra com RAG microservice (Qdrant) para busca semântica

Benefícios:
- Sem dependências externas de banco de dados
- Deployment simplificado
- Baixo consumo de recursos
"""


import json
import os
from typing import Any, Dict, List, Optional

import aiosqlite

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)

# Database path for context store
CONTEXT_DB_PATH = os.getenv("CONTEXT_DB_PATH", "context_store.db")


class ContextStore:
    """
    Armazena e recupera contexto de conversas usando SQLite.
    
    Para busca semântica avançada, use o RAG microservice com Qdrant.
    """
    
    _instance: Optional["ContextStore"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "ContextStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self) -> None:
        """Inicializa o banco de dados SQLite."""
        if self._initialized:
            return
            
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            # Tabela de conversas
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_query TEXT NOT NULL,
                    agent_response TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    model_used TEXT DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_flagged BOOLEAN DEFAULT FALSE,
                    is_approved BOOLEAN DEFAULT FALSE,
                    feedback TEXT,
                    rating INTEGER,
                    observations TEXT
                )
            """)
            
            # Tabela de conteúdo
            await db.execute("""
                CREATE TABLE IF NOT EXISTS content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Índices para busca rápida
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_agent 
                ON conversations(agent_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_created 
                ON conversations(created_at DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_flagged 
                ON conversations(is_flagged)
            """)
            
            # Full-text search para busca de contexto
            await db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts 
                USING fts5(user_query, agent_response, content='conversations', content_rowid='id')
            """)
            
            await db.commit()
            
        self._initialized = True
        logger.info("context_store_initialized", db_path=CONTEXT_DB_PATH)
    
    async def add_conversation(
        self,
        user_query: str,
        agent_response: str,
        agent_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Armazena uma conversa."""
        await self.initialize()
        
        model_used = context.get("model_used", "unknown") if context else "unknown"
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            cursor = await db.execute(
                """
                INSERT INTO conversations (user_query, agent_response, agent_id, model_used)
                VALUES (?, ?, ?, ?)
                """,
                (user_query, agent_response, agent_id, model_used)
            )
            conversation_id = cursor.lastrowid
            
            # Atualizar FTS
            await db.execute(
                """
                INSERT INTO conversations_fts (rowid, user_query, agent_response)
                VALUES (?, ?, ?)
                """,
                (conversation_id, user_query, agent_response)
            )
            
            await db.commit()
            
        logger.debug("conversation_stored", id=conversation_id, agent_id=agent_id)
        return str(conversation_id)
    
    async def get_relevant_context(self, query: str, top_k: int = 10) -> str:
        """
        Busca contexto relevante usando FTS (Full-Text Search).
        Para busca semântica mais avançada, use o RAG microservice com Qdrant.
        """
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            # Busca FTS com ranking
            cursor = await db.execute(
                """
                SELECT c.user_query, c.agent_response, c.agent_id,
                       bm25(conversations_fts) as score
                FROM conversations_fts fts
                JOIN conversations c ON fts.rowid = c.id
                WHERE conversations_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (query, top_k)
            )
            
            rows = await cursor.fetchall()
            
            if not rows:
                return "Nenhum contexto anterior encontrado."
            
            context_parts = []
            for row in rows:
                context_parts.append(
                    f"- Pergunta: {row['user_query'][:100]}...\n"
                    f"  Resposta: {row['agent_response'][:200]}..."
                )
            
            return "\n".join(context_parts)
    
    async def search_similar_issues(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Busca issues similares no histórico."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute(
                """
                SELECT c.user_query, c.agent_response, c.agent_id, c.created_at
                FROM conversations_fts fts
                JOIN conversations c ON fts.rowid = c.id
                WHERE conversations_fts MATCH ?
                ORDER BY c.created_at DESC
                LIMIT ?
                """,
                (query, limit)
            )
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def search_conversations(
        self,
        query: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lista conversas recentes."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute(
                """
                SELECT id, user_query, agent_response, agent_id, model_used, 
                       created_at, is_flagged, is_approved
                FROM conversations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def add_content(self, content: str, metadata: Dict[str, Any]) -> str:
        """Armazena conteúdo (documentos, chunks)."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            cursor = await db.execute(
                """
                INSERT INTO content (content, metadata)
                VALUES (?, ?)
                """,
                (content, json.dumps(metadata))
            )
            content_id = cursor.lastrowid
            await db.commit()
            
        return str(content_id)
    
    async def is_memory_flagged(self, memory_id: str) -> bool:
        """Verifica se uma memória está flagged."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT is_flagged FROM conversations WHERE id = ?",
                (int(memory_id),)
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else False
    
    async def is_memory_approved(self, memory_id: str) -> bool:
        """Verifica se uma memória está aprovada."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT is_approved FROM conversations WHERE id = ?",
                (int(memory_id),)
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else False
    
    async def delete_memory(self, memory_id: str) -> None:
        """Deleta uma memória."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            await db.execute(
                "DELETE FROM conversations WHERE id = ?",
                (int(memory_id),)
            )
            await db.execute(
                "DELETE FROM conversations_fts WHERE rowid = ?",
                (int(memory_id),)
            )
            await db.commit()
            
        logger.info("memory_deleted", memory_id=memory_id)
    
    async def add_observations(self, memory_id: str, observations: List[str]) -> None:
        """Adiciona observações a uma memória."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            await db.execute(
                "UPDATE conversations SET observations = ? WHERE id = ?",
                (json.dumps(observations), int(memory_id))
            )
            await db.commit()
    
    async def add_solution_feedback(
        self, memory_id: str, feedback: str, rating: int
    ) -> None:
        """Adiciona feedback do usuário."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            await db.execute(
                "UPDATE conversations SET feedback = ?, rating = ? WHERE id = ?",
                (feedback, rating, int(memory_id))
            )
            await db.commit()
    
    async def flag_memory(self, memory_id: str, flagged: bool = True) -> None:
        """Marca uma memória como flagged."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            await db.execute(
                "UPDATE conversations SET is_flagged = ? WHERE id = ?",
                (flagged, int(memory_id))
            )
            await db.commit()
    
    async def approve_memory(self, memory_id: str, approved: bool = True) -> None:
        """Marca uma memória como aprovada."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            await db.execute(
                "UPDATE conversations SET is_approved = ? WHERE id = ?",
                (approved, int(memory_id))
            )
            await db.commit()
    
    async def get_all_recent_conversations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Recupera conversas recentes para auditoria."""
        return await self.search_conversations(limit=limit)
    
    async def close(self) -> None:
        """Fecha conexões (no-op para SQLite, mantido para compatibilidade)."""
        logger.info("context_store_closed")
    
    async def is_memory_already_processed(self, memory_id: str) -> bool:
        """Verifica se uma memória já foi processada (flagged ou approved)."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT is_flagged, is_approved FROM conversations WHERE id = ?",
                (int(memory_id),)
            )
            row = await cursor.fetchone()
            if row:
                return bool(row[0]) or bool(row[1])
            return False
    
    async def atomic_check_and_flag(
        self, memory_id: str, reason: str, confidence: float
    ) -> bool:
        """Atomicamente verifica se já processou e flagga se não."""
        await self.initialize()
        
        async with aiosqlite.connect(CONTEXT_DB_PATH) as db:
            # Verificar se já processado
            cursor = await db.execute(
                "SELECT is_flagged, is_approved FROM conversations WHERE id = ?",
                (int(memory_id),)
            )
            row = await cursor.fetchone()
            
            if row and (row[0] or row[1]):
                return False  # Já processado
            
            # Flaggar
            await db.execute(
                """
                UPDATE conversations 
                SET is_flagged = TRUE, 
                    observations = json_array(?)
                WHERE id = ?
                """,
                (f"Auto-flagged: {reason} (confidence: {confidence:.2f})", int(memory_id))
            )
            await db.commit()
            return True
    
    # Métodos síncronos para compatibilidade
    def add_content_sync(self, content: str, metadata: Dict[str, Any]) -> str:
        """Versão síncrona de add_content."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.add_content(content, metadata)
        )
    
    def add_conversation_sync(
        self,
        user_query: str,
        agent_response: str,
        agent_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Versão síncrona de add_conversation."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.add_conversation(user_query, agent_response, agent_id, context)
        )
    
    def search_similar_issues_sync(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Versão síncrona de search_similar_issues."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.search_similar_issues(query, limit)
        )
    
    def search_conversations_sync(self, query: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """Versão síncrona de search_conversations."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.search_conversations(query, limit)
        )
    
    def add_solution_feedback_sync(self, memory_id: str, feedback: str, rating: int) -> None:
        """Versão síncrona de add_solution_feedback."""
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            self.add_solution_feedback(memory_id, feedback, rating)
        )
    
    def get_all_recent_conversations_sync(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Versão síncrona de get_all_recent_conversations."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.get_all_recent_conversations(limit)
        )
    
    def get_relevant_context_sync(self, query: str, top_k: int = 10) -> str:
        """Versão síncrona de get_relevant_context."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.get_relevant_context(query, top_k)
        )
    
    def is_memory_flagged_sync(self, memory_id: str) -> bool:
        """Versão síncrona de is_memory_flagged."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.is_memory_flagged(memory_id)
        )
    
    def is_memory_approved_sync(self, memory_id: str) -> bool:
        """Versão síncrona de is_memory_approved."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.is_memory_approved(memory_id)
        )
    
    def delete_memory_sync(self, memory_id: str) -> None:
        """Versão síncrona de delete_memory."""
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            self.delete_memory(memory_id)
        )
    
    def add_observations_sync(self, memory_id: str, observations: List[str]) -> None:
        """Versão síncrona de add_observations."""
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            self.add_observations(memory_id, observations)
        )
    
    def is_memory_already_processed_sync(self, memory_id: str) -> bool:
        """Versão síncrona de is_memory_already_processed."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.is_memory_already_processed(memory_id)
        )
    
    def atomic_check_and_flag_sync(
        self, memory_id: str, reason: str, confidence: float
    ) -> bool:
        """Versão síncrona de atomic_check_and_flag."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.atomic_check_and_flag(memory_id, reason, confidence)
        )


# Singleton instance
_context_store: Optional[ContextStore] = None


def get_context_store() -> ContextStore:
    """Obtém a instância singleton do ContextStore."""
    global _context_store
    if _context_store is None:
        _context_store = ContextStore()
    return _context_store


# Alias para compatibilidade com código existente
AsyncKnowledgeGraph = ContextStore
IKnowledgeGraph = ContextStore
