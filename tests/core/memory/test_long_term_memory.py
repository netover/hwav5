"""
Tests for Long-Term Memory System v5.2.3.26

Tests the Google Context Engineering implementation:
1. Declarative Memory (facts, preferences)
2. Procedural Memory (behavior patterns)
3. Memory Extraction via LLM
4. Provenance tracking
5. Push vs Pull retrieval
6. Memory consolidation

Author: Resync Team
Version: 5.2.3.26
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from resync.core.memory.long_term_memory import (
    DeclarativeMemory,
    ProceduralMemory,
    DeclarativeCategory,
    ProceduralCategory,
    MemoryType,
    RetrievalMode,
    MemoryProvenance,
    InMemoryLongTermStore,
    MemoryExtractor,
    LongTermMemoryManager,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_provenance() -> MemoryProvenance:
    """Create a sample provenance."""
    return MemoryProvenance(
        source_session_id="session_123",
        source_message="O job BATCH_001 falhou com RC=8",
        times_referenced=5,
        times_confirmed=2,
    )


@pytest.fixture
def sample_declarative(sample_provenance) -> DeclarativeMemory:
    """Create a sample declarative memory."""
    return DeclarativeMemory(
        id="",
        user_id="user_001",
        category=DeclarativeCategory.RESPONSIBILITY,
        content="Usuário gerencia o job stream BATCH_NOTURNO",
        confidence=0.8,
        related_jobs=["BATCH_001", "BATCH_002"],
        environment="PROD",
        provenance=sample_provenance,
    )


@pytest.fixture
def sample_procedural(sample_provenance) -> ProceduralMemory:
    """Create a sample procedural memory."""
    return ProceduralMemory(
        id="",
        user_id="user_001",
        category=ProceduralCategory.TROUBLESHOOTING,
        pattern="Usuário verifica logs antes de reiniciar jobs",
        examples=["Pediu logs do BATCH_001 antes de rerun"],
        trigger_conditions=["Quando um job falha"],
        confidence=0.7,
        times_observed=3,
        provenance=sample_provenance,
    )


@pytest.fixture
def memory_store() -> InMemoryLongTermStore:
    """Create an in-memory store for testing."""
    return InMemoryLongTermStore()


@pytest.fixture
def sample_conversation() -> list[dict[str, str]]:
    """Sample conversation for extraction testing."""
    return [
        {"role": "user", "content": "Preciso verificar o job BATCH_001 que falhou"},
        {"role": "assistant", "content": "Vou verificar o status do job BATCH_001..."},
        {"role": "user", "content": "Mostra os logs primeiro, sempre faço isso antes de reiniciar"},
        {"role": "assistant", "content": "Aqui estão os logs do BATCH_001..."},
        {"role": "user", "content": "Ok, pode reiniciar. Sou responsável pelo BATCH_NOTURNO"},
        {"role": "assistant", "content": "Job reiniciado com sucesso."},
    ]


# =============================================================================
# PROVENANCE TESTS
# =============================================================================


class TestMemoryProvenance:
    """Tests for provenance tracking."""

    def test_confidence_adjustment_positive(self, sample_provenance):
        """Test confidence increases with confirmations."""
        adjustment = sample_provenance.confidence_adjustment
        assert adjustment > 0  # 2 confirmations should add positive value

    def test_confidence_adjustment_with_contradictions(self):
        """Test confidence decreases with contradictions."""
        provenance = MemoryProvenance(
            source_session_id="test",
            source_message="test",
            times_confirmed=1,
            times_contradicted=3,
        )
        adjustment = provenance.confidence_adjustment
        assert adjustment < 0  # More contradictions should be negative

    def test_serialization(self, sample_provenance):
        """Test provenance serialization and deserialization."""
        data = sample_provenance.to_dict()
        restored = MemoryProvenance.from_dict(data)
        
        assert restored.source_session_id == sample_provenance.source_session_id
        assert restored.times_confirmed == sample_provenance.times_confirmed


# =============================================================================
# DECLARATIVE MEMORY TESTS
# =============================================================================


class TestDeclarativeMemory:
    """Tests for declarative (factual) memory."""

    def test_id_generation(self):
        """Test deterministic ID generation."""
        mem1 = DeclarativeMemory(
            id="",
            user_id="user1",
            category=DeclarativeCategory.PREFERENCE,
            content="Prefere português",
        )
        mem2 = DeclarativeMemory(
            id="",
            user_id="user1",
            category=DeclarativeCategory.PREFERENCE,
            content="Prefere português",
        )
        # Same content should generate same ID
        assert mem1.id == mem2.id
        assert mem1.id.startswith("decl_")

    def test_effective_confidence(self, sample_declarative):
        """Test effective confidence with provenance adjustment."""
        base_confidence = sample_declarative.confidence
        effective = sample_declarative.effective_confidence
        
        # Should be higher due to confirmations
        assert effective >= base_confidence

    def test_expiration(self):
        """Test memory expiration."""
        # Non-expired
        mem1 = DeclarativeMemory(
            id="",
            user_id="user1",
            category=DeclarativeCategory.PREFERENCE,
            content="Test",
            expires_at=datetime.now() + timedelta(days=1),
        )
        assert not mem1.is_expired
        
        # Expired
        mem2 = DeclarativeMemory(
            id="",
            user_id="user1",
            category=DeclarativeCategory.PREFERENCE,
            content="Test",
            expires_at=datetime.now() - timedelta(days=1),
        )
        assert mem2.is_expired

    def test_high_confidence_detection(self, sample_declarative):
        """Test high confidence detection for proactive retrieval."""
        sample_declarative.confidence = 0.9
        assert sample_declarative.is_high_confidence

    def test_serialization(self, sample_declarative):
        """Test serialization and deserialization."""
        data = sample_declarative.to_dict()
        restored = DeclarativeMemory.from_dict(data)
        
        assert restored.user_id == sample_declarative.user_id
        assert restored.content == sample_declarative.content
        assert restored.category == sample_declarative.category
        assert restored.related_jobs == sample_declarative.related_jobs

    def test_prompt_formatting(self, sample_declarative):
        """Test formatting for LLM prompt."""
        text = sample_declarative.to_prompt_text()
        
        assert "responsibility" in text
        assert "BATCH_NOTURNO" in text


# =============================================================================
# PROCEDURAL MEMORY TESTS
# =============================================================================


class TestProceduralMemory:
    """Tests for procedural (behavioral) memory."""

    def test_observation_tracking(self, sample_procedural):
        """Test observation counting increases confidence."""
        initial_confidence = sample_procedural.confidence
        initial_count = sample_procedural.times_observed
        
        sample_procedural.observe()
        
        assert sample_procedural.times_observed == initial_count + 1
        assert sample_procedural.confidence > initial_confidence

    def test_effective_confidence_with_observations(self, sample_procedural):
        """Test effective confidence increases with observations."""
        # Many observations should increase effective confidence
        sample_procedural.times_observed = 10
        effective = sample_procedural.effective_confidence
        
        assert effective > sample_procedural.confidence

    def test_serialization(self, sample_procedural):
        """Test serialization and deserialization."""
        data = sample_procedural.to_dict()
        restored = ProceduralMemory.from_dict(data)
        
        assert restored.pattern == sample_procedural.pattern
        assert restored.examples == sample_procedural.examples
        assert restored.times_observed == sample_procedural.times_observed


# =============================================================================
# MEMORY STORE TESTS
# =============================================================================


class TestInMemoryLongTermStore:
    """Tests for in-memory storage backend."""

    @pytest.mark.asyncio
    async def test_save_and_get(self, memory_store, sample_declarative):
        """Test saving and retrieving a memory."""
        await memory_store.save_memory(sample_declarative)
        
        retrieved = await memory_store.get_memory(sample_declarative.id)
        
        assert retrieved is not None
        assert retrieved.content == sample_declarative.content

    @pytest.mark.asyncio
    async def test_delete(self, memory_store, sample_declarative):
        """Test deleting a memory."""
        await memory_store.save_memory(sample_declarative)
        
        result = await memory_store.delete_memory(sample_declarative.id)
        assert result is True
        
        retrieved = await memory_store.get_memory(sample_declarative.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_user_memories(self, memory_store, sample_declarative, sample_procedural):
        """Test getting all memories for a user."""
        await memory_store.save_memory(sample_declarative)
        await memory_store.save_memory(sample_procedural)
        
        memories = await memory_store.get_user_memories("user_001")
        
        assert len(memories) == 2

    @pytest.mark.asyncio
    async def test_filter_by_type(self, memory_store, sample_declarative, sample_procedural):
        """Test filtering by memory type."""
        await memory_store.save_memory(sample_declarative)
        await memory_store.save_memory(sample_procedural)
        
        declarative_only = await memory_store.get_user_memories(
            "user_001",
            memory_type=MemoryType.DECLARATIVE,
        )
        
        assert len(declarative_only) == 1
        assert isinstance(declarative_only[0], DeclarativeMemory)

    @pytest.mark.asyncio
    async def test_filter_by_confidence(self, memory_store):
        """Test filtering by minimum confidence."""
        low_conf = DeclarativeMemory(
            id="",
            user_id="user_001",
            category=DeclarativeCategory.PREFERENCE,
            content="Low confidence memory",
            confidence=0.3,
        )
        high_conf = DeclarativeMemory(
            id="",
            user_id="user_001",
            category=DeclarativeCategory.PREFERENCE,
            content="High confidence memory",
            confidence=0.9,
        )
        
        await memory_store.save_memory(low_conf)
        await memory_store.save_memory(high_conf)
        
        high_only = await memory_store.get_user_memories(
            "user_001",
            min_confidence=0.8,
        )
        
        assert len(high_only) == 1
        assert high_only[0].content == "High confidence memory"

    @pytest.mark.asyncio
    async def test_search_memories(self, memory_store, sample_declarative):
        """Test semantic search (keyword-based in this implementation)."""
        await memory_store.save_memory(sample_declarative)
        
        results = await memory_store.search_memories(
            "user_001",
            query="BATCH_NOTURNO job stream",
        )
        
        assert len(results) > 0
        assert "BATCH_NOTURNO" in results[0].content

    @pytest.mark.asyncio
    async def test_get_proactive_memories(self, memory_store):
        """Test getting proactive (push) memories."""
        proactive = DeclarativeMemory(
            id="",
            user_id="user_001",
            category=DeclarativeCategory.PREFERENCE,
            content="Proactive memory",
            retrieval_mode=RetrievalMode.PROACTIVE,
        )
        reactive = DeclarativeMemory(
            id="",
            user_id="user_001",
            category=DeclarativeCategory.PREFERENCE,
            content="Reactive memory",
            retrieval_mode=RetrievalMode.REACTIVE,
            confidence=0.4,  # Low confidence, stays reactive
        )
        
        await memory_store.save_memory(proactive)
        await memory_store.save_memory(reactive)
        
        proactive_only = await memory_store.get_proactive_memories("user_001")
        
        assert len(proactive_only) == 1
        assert proactive_only[0].content == "Proactive memory"


# =============================================================================
# MEMORY EXTRACTOR TESTS
# =============================================================================


class TestMemoryExtractor:
    """Tests for LLM-based memory extraction."""

    @pytest.mark.asyncio
    async def test_extraction_with_mock_llm(self, sample_conversation):
        """Test memory extraction with mocked LLM response."""
        mock_response = '''
        {
            "declarative": [
                {
                    "category": "responsibility",
                    "content": "Usuário é responsável pelo BATCH_NOTURNO",
                    "confidence": 0.8,
                    "related_jobs": ["BATCH_001"],
                    "environment": null
                }
            ],
            "procedural": [
                {
                    "category": "troubleshooting",
                    "pattern": "Verifica logs antes de reiniciar jobs",
                    "trigger_conditions": ["Quando um job falha"],
                    "confidence": 0.9
                }
            ]
        }
        '''
        
        async def mock_llm(prompt):
            return mock_response
        
        extractor = MemoryExtractor(llm_caller=mock_llm)
        memories = await extractor.extract_memories(
            user_id="user_001",
            conversation=sample_conversation,
            session_id="session_123",
        )
        
        assert len(memories) == 2
        
        # Check declarative
        declarative = [m for m in memories if isinstance(m, DeclarativeMemory)]
        assert len(declarative) == 1
        assert "BATCH_NOTURNO" in declarative[0].content
        
        # Check procedural
        procedural = [m for m in memories if isinstance(m, ProceduralMemory)]
        assert len(procedural) == 1
        assert "logs" in procedural[0].pattern.lower()

    @pytest.mark.asyncio
    async def test_extraction_handles_empty_response(self):
        """Test extraction handles empty LLM response gracefully."""
        async def mock_llm(prompt):
            return '{"declarative": [], "procedural": []}'
        
        extractor = MemoryExtractor(llm_caller=mock_llm)
        memories = await extractor.extract_memories(
            user_id="user_001",
            conversation=[{"role": "user", "content": "Hello"}],
            session_id="session_123",
        )
        
        assert len(memories) == 0

    @pytest.mark.asyncio
    async def test_extraction_handles_invalid_json(self):
        """Test extraction handles invalid JSON gracefully."""
        async def mock_llm(prompt):
            return "This is not JSON"
        
        extractor = MemoryExtractor(llm_caller=mock_llm)
        memories = await extractor.extract_memories(
            user_id="user_001",
            conversation=[{"role": "user", "content": "Hello"}],
            session_id="session_123",
        )
        
        # Should return empty list, not crash
        assert memories == []


# =============================================================================
# MEMORY MANAGER TESTS
# =============================================================================


class TestLongTermMemoryManager:
    """Tests for the high-level memory manager."""

    @pytest.fixture
    def manager(self, memory_store) -> LongTermMemoryManager:
        """Create a manager with test store."""
        async def mock_llm(prompt):
            return '''
            {
                "declarative": [
                    {"category": "preference", "content": "Teste", "confidence": 0.7}
                ],
                "procedural": []
            }
            '''
        
        extractor = MemoryExtractor(llm_caller=mock_llm)
        return LongTermMemoryManager(store=memory_store, extractor=extractor)

    @pytest.mark.asyncio
    async def test_extract_from_session(self, manager, sample_conversation):
        """Test extracting and storing memories from a session."""
        memories = await manager.extract_from_session(
            user_id="user_001",
            conversation=sample_conversation,
            session_id="session_123",
        )
        
        assert len(memories) > 0

    @pytest.mark.asyncio
    async def test_get_memory_context(self, manager, sample_declarative):
        """Test getting formatted memory context for prompts."""
        # Pre-populate store
        manager._store = InMemoryLongTermStore()
        await manager._store.save_memory(sample_declarative)
        
        context = await manager.get_memory_context(
            user_id="user_001",
            query="BATCH_NOTURNO",
        )
        
        assert "<user_memory>" in context
        assert "BATCH_NOTURNO" in context

    @pytest.mark.asyncio
    async def test_add_memory_manually(self, manager):
        """Test manually adding a memory."""
        manager._store = InMemoryLongTermStore()
        
        memory = await manager.add_memory(
            user_id="user_001",
            content="Prefere respostas em português",
            memory_type=MemoryType.DECLARATIVE,
            category="preference",
        )
        
        assert memory.id.startswith("decl_")
        assert memory.content == "Prefere respostas em português"

    @pytest.mark.asyncio
    async def test_confirm_memory(self, manager, sample_declarative):
        """Test confirming a memory increases confidence."""
        manager._store = InMemoryLongTermStore()
        await manager._store.save_memory(sample_declarative)
        
        initial_confidence = sample_declarative.confidence
        
        result = await manager.confirm_memory(sample_declarative.id)
        assert result is True
        
        # Reload and check
        updated = await manager._store.get_memory(sample_declarative.id)
        assert updated.confidence > initial_confidence

    @pytest.mark.asyncio
    async def test_contradict_memory(self, manager, sample_declarative):
        """Test contradicting a memory decreases confidence."""
        manager._store = InMemoryLongTermStore()
        await manager._store.save_memory(sample_declarative)
        
        initial_confidence = sample_declarative.confidence
        
        result = await manager.contradict_memory(sample_declarative.id)
        assert result is True
        
        updated = await manager._store.get_memory(sample_declarative.id)
        assert updated.confidence < initial_confidence

    @pytest.mark.asyncio
    async def test_delete_user_memories(self, manager, sample_declarative, sample_procedural):
        """Test GDPR-compliant deletion of all user memories."""
        manager._store = InMemoryLongTermStore()
        await manager._store.save_memory(sample_declarative)
        await manager._store.save_memory(sample_procedural)
        
        count = await manager.delete_user_memories("user_001")
        assert count == 2
        
        # Verify deletion
        memories = await manager._store.get_user_memories("user_001")
        assert len(memories) == 0

    @pytest.mark.asyncio
    async def test_get_statistics(self, manager, sample_declarative, sample_procedural):
        """Test getting memory statistics."""
        manager._store = InMemoryLongTermStore()
        await manager._store.save_memory(sample_declarative)
        await manager._store.save_memory(sample_procedural)
        
        stats = await manager.get_statistics("user_001")
        
        assert stats["total_memories"] == 2
        assert stats["declarative_count"] == 1
        assert stats["procedural_count"] == 1

    @pytest.mark.asyncio
    async def test_memory_consolidation(self, manager):
        """Test that similar memories are consolidated."""
        manager._store = InMemoryLongTermStore()
        
        # Create mock extractor that returns same content twice
        async def mock_llm(prompt):
            return '''
            {
                "declarative": [
                    {"category": "preference", "content": "Prefere português", "confidence": 0.6}
                ],
                "procedural": []
            }
            '''
        manager._extractor = MemoryExtractor(llm_caller=mock_llm)
        
        # Extract from first session
        await manager.extract_from_session(
            user_id="user_001",
            conversation=[{"role": "user", "content": "Test 1"}],
            session_id="session_1",
        )
        
        # Extract from second session (same content)
        await manager.extract_from_session(
            user_id="user_001",
            conversation=[{"role": "user", "content": "Test 2"}],
            session_id="session_2",
        )
        
        # Should have consolidated into 1 memory, not 2
        memories = await manager._store.get_user_memories("user_001")
        assert len(memories) == 1
        
        # Confidence should have increased due to consolidation
        assert memories[0].confidence >= 0.6


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for the complete memory system."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow: extract → store → retrieve → use."""
        # Setup
        store = InMemoryLongTermStore()
        
        async def mock_llm(prompt):
            return '''
            {
                "declarative": [
                    {
                        "category": "responsibility",
                        "content": "Gerencia o ambiente PROD",
                        "confidence": 0.85,
                        "related_jobs": ["BATCH_PROD_001"],
                        "environment": "PROD"
                    }
                ],
                "procedural": [
                    {
                        "category": "troubleshooting",
                        "pattern": "Sempre verifica dependências antes de reiniciar",
                        "trigger_conditions": ["Job em ABEND"],
                        "confidence": 0.75
                    }
                ]
            }
            '''
        
        extractor = MemoryExtractor(llm_caller=mock_llm)
        manager = LongTermMemoryManager(store=store, extractor=extractor)
        
        # 1. Extract from session
        conversation = [
            {"role": "user", "content": "O job BATCH_PROD_001 falhou"},
            {"role": "assistant", "content": "Verificando..."},
            {"role": "user", "content": "Mostra as dependências primeiro"},
        ]
        
        memories = await manager.extract_from_session(
            user_id="operator_001",
            conversation=conversation,
            session_id="incident_session",
        )
        
        assert len(memories) == 2
        
        # 2. Later, retrieve for new query
        context = await manager.get_memory_context(
            user_id="operator_001",
            query="Job BATCH_PROD_001 falhou novamente",
        )
        
        # Should include relevant memories
        assert "PROD" in context
        assert "dependências" in context.lower()
        
        # 3. Verify statistics
        stats = await manager.get_statistics("operator_001")
        assert stats["total_memories"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
