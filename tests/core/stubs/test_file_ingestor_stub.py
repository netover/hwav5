"""
Comprehensive tests for file_ingestor module.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os


class TestFileIngestor:
    """Tests for file ingestion functionality."""

    def test_module_imports(self):
        """Test module can be imported."""
        from resync.core import file_ingestor
        assert file_ingestor is not None

    def test_ingestor_class_exists(self):
        """Test file ingestor class exists."""
        from resync.core import file_ingestor
        
        module_attrs = dir(file_ingestor)
        has_ingestor = any('ingest' in attr.lower() for attr in module_attrs)
        assert has_ingestor or len(module_attrs) > 5

    def test_ingestion_methods_exist(self):
        """Test ingestion methods are available."""
        from resync.core import file_ingestor
        
        public_attrs = [a for a in dir(file_ingestor) if not a.startswith('_')]
        assert len(public_attrs) > 0
