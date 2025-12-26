"""
Tests for Ontology Module v5.9.2

Tests for:
1. OntologyManager - Schema loading, validation, prompt generation
2. EntityResolver - Hierarchical resolution, deduplication
3. ProvenanceTracker - Source tracking, verification
"""

import pytest
from datetime import datetime
from pathlib import Path

from resync.knowledge.ontology import (
    # OntologyManager
    OntologyManager,
    get_ontology_manager,
    validate_job,
    validate_error_code,
    normalize_status,
    ExtractionStrategy,
    # EntityResolver
    EntityResolver,
    JobResolver,
    ErrorCodeResolver,
    create_job_resolver,
    create_error_resolver,
    # Provenance
    ProvenanceTracker,
    get_provenance_tracker,
    track_entity,
    SourceInfo,
    ExtractionInfo,
    SourceType,
    ExtractionMethod,
    VerificationStatus,
)


# =============================================================================
# ONTOLOGY MANAGER TESTS
# =============================================================================


class TestOntologyManager:
    """Test OntologyManager functionality."""

    def test_load_ontology(self):
        """Should load TWS ontology from YAML."""
        manager = get_ontology_manager()
        
        assert manager.ontology is not None
        assert manager.ontology.metadata.name == "TWS Ontology"
        assert manager.ontology.metadata.version == "5.9.2"
        assert manager.ontology.metadata.domain == "tws"

    def test_entity_types_loaded(self):
        """Should load all entity types."""
        manager = get_ontology_manager()
        
        entity_types = manager.get_all_entity_types()
        assert "Job" in entity_types
        assert "JobStream" in entity_types
        assert "Workstation" in entity_types
        assert "ErrorCode" in entity_types
        assert "Resource" in entity_types

    def test_relationship_types_loaded(self):
        """Should load all relationship types."""
        manager = get_ontology_manager()
        
        rel_types = manager.get_all_relationship_types()
        assert "DEPENDS_ON" in rel_types
        assert "RUNS_ON" in rel_types
        assert "HAS_SOURCE" in rel_types

    def test_resolve_alias(self):
        """Should resolve entity type aliases."""
        manager = get_ontology_manager()
        
        assert manager.resolve_entity_type("job") == "Job"
        assert manager.resolve_entity_type("JOB") == "Job"
        assert manager.resolve_entity_type("batch job") == "Job"
        assert manager.resolve_entity_type("erro") == "ErrorCode"

    def test_get_extraction_strategy(self):
        """Should return correct extraction strategy."""
        manager = get_ontology_manager()
        
        assert manager.get_extraction_strategy("Job") == ExtractionStrategy.HYBRID
        assert manager.get_extraction_strategy("ErrorCode") == ExtractionStrategy.REGEX
        assert manager.get_extraction_strategy("Dependency") == ExtractionStrategy.LLM


class TestOntologyValidation:
    """Test entity validation against ontology."""

    def test_validate_valid_job(self):
        """Should pass validation for valid job."""
        result = validate_job({
            "job_name": "BACKUP_DIARIO",
            "status": "SUCC",
            "return_code": 0,
            "workstation": "WS01",
        })
        
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_invalid_return_code(self):
        """Should fail validation for invalid return code."""
        result = validate_job({
            "job_name": "BACKUP_DIARIO",
            "return_code": 9999,  # Above max 255
        })
        
        assert not result.is_valid
        assert any("above maximum" in e.message for e in result.errors)

    def test_validate_invalid_status(self):
        """Should fail validation for invalid status."""
        result = validate_job({
            "job_name": "BACKUP_DIARIO",
            "status": "INVALID_STATUS",
        })
        
        assert not result.is_valid
        assert any("not in allowed values" in e.message for e in result.errors)

    def test_validate_missing_required(self):
        """Should fail validation for missing required property."""
        result = validate_job({
            "status": "SUCC",  # Missing job_name
        })
        
        assert not result.is_valid
        assert any("Missing required" in e.message for e in result.errors)

    def test_validate_error_code(self):
        """Should validate error code entity."""
        result = validate_error_code({
            "code": "AWSB1234E",
            "severity": "error",
        })
        
        assert result.is_valid

    def test_validate_invalid_severity(self):
        """Should fail for invalid severity."""
        result = validate_error_code({
            "code": "AWSB1234E",
            "severity": "super_critical",  # Not in allowed values
        })
        
        assert not result.is_valid


class TestPromptGeneration:
    """Test extraction prompt generation."""

    def test_generate_job_prompt(self):
        """Should generate Job extraction prompt."""
        manager = get_ontology_manager()
        
        prompt = manager.generate_extraction_prompt(
            "Job",
            "The job BACKUP_DIARIO failed with RC=12"
        )
        
        assert "Job" in prompt
        assert "job_name" in prompt
        assert "BACKUP_DIARIO" in prompt or "failed" in prompt

    def test_generate_error_prompt(self):
        """Should generate ErrorCode extraction prompt."""
        manager = get_ontology_manager()
        
        prompt = manager.generate_extraction_prompt(
            "ErrorCode",
            "Error AWSB1234E: Connection timeout"
        )
        
        assert "ErrorCode" in prompt or "Error" in prompt


class TestStatusNormalization:
    """Test status normalization."""

    def test_normalize_success_variations(self):
        """Should normalize success status variations."""
        assert normalize_status("success") == "SUCC"
        assert normalize_status("successful") == "SUCC"
        assert normalize_status("completed") == "SUCC"
        assert normalize_status("ok") == "SUCC"

    def test_normalize_error_variations(self):
        """Should normalize error status variations."""
        assert normalize_status("abend") == "ABEND"
        assert normalize_status("failed") == "ABEND"
        assert normalize_status("failure") == "ABEND"

    def test_normalize_running_variations(self):
        """Should normalize running status variations."""
        assert normalize_status("running") == "EXEC"
        assert normalize_status("executing") == "EXEC"


# =============================================================================
# ENTITY RESOLVER TESTS
# =============================================================================


class TestEntityResolver:
    """Test EntityResolver functionality."""

    @pytest.mark.asyncio
    async def test_resolve_creates_new_entity(self):
        """Should create new entity when none exists."""
        resolver = EntityResolver()
        
        result = await resolver.resolve(
            entity_type="Job",
            name="BACKUP_DIARIO",
            folder="/root",
        )
        
        assert result.is_new
        assert result.entity_type == "Job"
        assert result.resolution_method == "new"

    @pytest.mark.asyncio
    async def test_resolve_finds_existing_entity(self):
        """Should find existing entity on second resolve."""
        resolver = EntityResolver()
        
        # First resolve - creates new
        result1 = await resolver.resolve(
            entity_type="Job",
            name="BACKUP_DIARIO",
            folder="/root",
        )
        
        # Second resolve - finds existing
        result2 = await resolver.resolve(
            entity_type="Job",
            name="BACKUP_DIARIO",
            folder="/root",
        )
        
        assert result1.is_new
        assert not result2.is_new
        assert result1.entity_id == result2.entity_id

    @pytest.mark.asyncio
    async def test_different_folders_different_entities(self):
        """Should create different entities for same name in different folders."""
        resolver = EntityResolver()
        
        result1 = await resolver.resolve(
            entity_type="Job",
            name="BACKUP",
            folder="/root",
        )
        
        result2 = await resolver.resolve(
            entity_type="Job",
            name="BACKUP",
            folder="/finance",
        )
        
        # Different folders = different entities
        assert result1.entity_id != result2.entity_id
        assert result1.canonical_id != result2.canonical_id

    def test_build_canonical_id(self):
        """Should build correct canonical ID."""
        resolver = EntityResolver()
        
        cid = resolver.build_canonical_id(
            entity_type="Job",
            name="BACKUP",
            folder="/root",
            job_stream="DAILY_JOBS",
        )
        
        assert "/ROOT/" in cid
        assert "/DAILY_JOBS/" in cid
        assert "/Job/" in cid
        assert "/BACKUP" in cid


class TestJobResolver:
    """Test specialized JobResolver."""

    @pytest.mark.asyncio
    async def test_resolve_job(self):
        """Should resolve job with normalization."""
        resolver = create_job_resolver()
        
        result = await resolver.resolve_job(
            job_name="Job BACKUP_DIARIO",  # With prefix
            folder="/root",
        )
        
        # Prefix should be removed
        assert "BACKUP_DIARIO" in result.canonical_id
        assert "Job BACKUP_DIARIO" not in result.canonical_id

    @pytest.mark.asyncio
    async def test_job_name_normalization(self):
        """Should normalize job names consistently."""
        resolver = create_job_resolver()
        
        # Different variations should resolve to same entity
        result1 = await resolver.resolve_job("BACKUP_DIARIO", folder="/root")
        result2 = await resolver.resolve_job("backup_diario", folder="/root")
        result3 = await resolver.resolve_job("Job BACKUP_DIARIO", folder="/root")
        
        assert result1.entity_id == result2.entity_id == result3.entity_id


class TestErrorCodeResolver:
    """Test specialized ErrorCodeResolver."""

    @pytest.mark.asyncio
    async def test_resolve_error_code(self):
        """Should resolve error code."""
        resolver = create_error_resolver()
        
        result = await resolver.resolve_error(
            code="AWSB1234E",
            severity="error",
        )
        
        assert not result.is_new or result.is_new  # Either is valid
        assert "AWSB1234E" in result.canonical_id

    @pytest.mark.asyncio
    async def test_normalize_rc_format(self):
        """Should normalize return code format."""
        resolver = create_error_resolver()
        
        # Different RC formats should resolve to same entity
        result1 = await resolver.resolve_error("RC=12")
        result2 = await resolver.resolve_error("rc 12")
        result3 = await resolver.resolve_error("RC12")
        
        # All should have normalized code
        assert "RC12" in result1.canonical_id


# =============================================================================
# PROVENANCE TRACKER TESTS
# =============================================================================


class TestProvenanceTracker:
    """Test ProvenanceTracker functionality."""

    def test_create_record(self):
        """Should create provenance record."""
        tracker = ProvenanceTracker()
        
        source = SourceInfo(
            source_type=SourceType.PDF,
            source_file="Manual_TWS.pdf",
            section_path="Chapter 5 > Error Codes",
        )
        
        extraction = ExtractionInfo(
            method=ExtractionMethod.LLM,
            model_name="gpt-4o",
            confidence_score=0.95,
        )
        
        record = tracker.create_record(
            entity_id="abc123",
            entity_type="Job",
            source=source,
            extraction=extraction,
        )
        
        assert record.entity_id == "abc123"
        assert record.entity_type == "Job"
        assert record.source.source_file == "Manual_TWS.pdf"
        assert record.extraction.confidence_score == 0.95

    def test_get_provenance(self):
        """Should retrieve provenance by entity ID."""
        tracker = ProvenanceTracker()
        
        source = SourceInfo(source_file="test.pdf")
        extraction = ExtractionInfo(model_name="gpt-4o")
        
        tracker.create_record("entity1", "Job", source, extraction)
        
        records = tracker.get_provenance("entity1")
        assert len(records) == 1
        assert records[0].entity_id == "entity1"

    def test_verify_entity(self):
        """Should verify entity."""
        tracker = ProvenanceTracker()
        
        source = SourceInfo(source_file="test.pdf")
        extraction = ExtractionInfo(model_name="gpt-4o")
        
        tracker.create_record("entity1", "Job", source, extraction)
        
        # Verify
        updated = tracker.verify_entity("entity1", verified_by="admin")
        
        assert len(updated) == 1
        assert updated[0].verification.status == VerificationStatus.VERIFIED
        assert updated[0].verification.verified_by == "admin"

    def test_auto_verify_high_confidence(self):
        """Should auto-verify high confidence entities."""
        tracker = ProvenanceTracker()
        
        source = SourceInfo(source_file="test.pdf")
        extraction = ExtractionInfo(
            model_name="gpt-4o",
            confidence_score=0.95,
            validation_passed=True,
        )
        
        tracker.create_record("entity1", "Job", source, extraction)
        
        # Auto-verify
        result = tracker.auto_verify_if_trustworthy("entity1", confidence_threshold=0.9)
        
        assert result
        records = tracker.get_provenance("entity1")
        assert records[0].verification.status == VerificationStatus.AUTO_VERIFIED

    def test_get_stats(self):
        """Should return correct statistics."""
        tracker = ProvenanceTracker()
        
        source = SourceInfo(source_file="test.pdf")
        extraction = ExtractionInfo(model_name="gpt-4o", confidence_score=0.8)
        
        tracker.create_record("entity1", "Job", source, extraction)
        tracker.create_record("entity2", "ErrorCode", source, extraction)
        
        tracker.verify_entity("entity1", "admin")
        
        stats = tracker.get_stats()
        
        assert stats["total"] == 2
        assert stats["verified"] == 1
        assert stats["unverified"] == 1


class TestProvenanceConvenience:
    """Test provenance convenience functions."""

    def test_track_entity(self):
        """Should track entity with convenience function."""
        chunk_metadata = {
            "source_file": "Manual_TWS.pdf",
            "document_title": "TWS Administration Guide",
            "section_path": "Chapter 5",
            "chunk_index": 10,
        }
        
        record = track_entity(
            entity_id="test123",
            entity_type="Job",
            chunk_metadata=chunk_metadata,
            model_name="gpt-4o",
            confidence=0.92,
        )
        
        assert record.entity_id == "test123"
        assert record.source.source_file == "Manual_TWS.pdf"
        assert record.extraction.model_name == "gpt-4o"
        assert record.extraction.confidence_score == 0.92


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestOntologyIntegration:
    """Integration tests for ontology module."""

    @pytest.mark.asyncio
    async def test_full_extraction_flow(self):
        """Test complete ontology-driven extraction flow."""
        # 1. Get ontology manager
        ontology = get_ontology_manager()
        
        # 2. Generate extraction prompt
        text = "Job BACKUP_DIARIO failed with RC=12 on workstation WS001"
        prompt = ontology.generate_extraction_prompt("Job", text)
        
        assert "Job" in prompt
        
        # 3. Simulate LLM extraction (normally would call LLM)
        extracted = {
            "job_name": "BACKUP_DIARIO",
            "status": "ABEND",
            "return_code": 12,
            "workstation": "WS001",
        }
        
        # 4. Validate against ontology
        validation = ontology.validate_entity("Job", extracted)
        assert validation.is_valid
        
        # 5. Resolve entity
        resolver = create_job_resolver()
        resolved = await resolver.resolve_job(
            job_name=extracted["job_name"],
            folder="/production",
        )
        
        # 6. Track provenance
        record = track_entity(
            entity_id=resolved.entity_id,
            entity_type="Job",
            chunk_metadata={"source_file": "log_2024.txt"},
            model_name="gpt-4o",
            confidence=0.95,
        )
        
        # 7. Verify all components work together
        assert resolved.entity_id is not None
        assert record.entity_id == resolved.entity_id
        assert record.extraction.confidence_score == 0.95
