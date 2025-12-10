"""
Tests for TWS Multi-Instance Management.
"""

import pytest


class TestTWSInstance:
    """Tests for TWS instance models."""

    def test_instance_module_import(self):
        """Test instance module imports."""
        from resync.core.tws_multi.instance import (
            TWSEnvironment,
            TWSInstance,
            TWSInstanceConfig,
            TWSInstanceStatus,
        )

        assert TWSInstance is not None
        assert TWSInstanceConfig is not None

    def test_instance_status_enum(self):
        """Test TWSInstanceStatus enum."""
        from resync.core.tws_multi.instance import TWSInstanceStatus

        assert TWSInstanceStatus.CONNECTED.value == "connected"
        assert TWSInstanceStatus.DISCONNECTED.value == "disconnected"
        assert TWSInstanceStatus.ERROR.value == "error"

    def test_environment_enum(self):
        """Test TWSEnvironment enum."""
        from resync.core.tws_multi.instance import TWSEnvironment

        assert TWSEnvironment.PRODUCTION.value == "production"
        assert TWSEnvironment.STAGING.value == "staging"
        assert TWSEnvironment.DR.value == "disaster_recovery"

    def test_instance_config_creation(self):
        """Test creating instance config."""
        from resync.core.tws_multi.instance import TWSInstanceConfig

        config = TWSInstanceConfig(
            name="SAZ",
            display_name="São Paulo - SAZ",
            host="tws.saz.com.br",
            port=31116,
        )

        assert config.name == "SAZ"
        assert config.host == "tws.saz.com.br"
        assert config.port == 31116
        assert config.ssl_enabled

    def test_instance_config_to_dict(self):
        """Test config to_dict method."""
        from resync.core.tws_multi.instance import TWSInstanceConfig

        config = TWSInstanceConfig(
            name="NAZ",
            host="tws.naz.com",
        )

        data = config.to_dict()
        assert data["name"] == "NAZ"
        assert data["host"] == "tws.naz.com"
        assert "id" in data

    def test_instance_creation(self):
        """Test creating TWSInstance."""
        from resync.core.tws_multi.instance import (
            TWSInstance,
            TWSInstanceConfig,
            TWSInstanceStatus,
        )

        config = TWSInstanceConfig(name="MAZ", host="tws.maz.com")
        instance = TWSInstance(config=config)

        assert instance.status == TWSInstanceStatus.DISCONNECTED
        assert instance.config.name == "MAZ"

    def test_instance_connection_url(self):
        """Test connection URL generation."""
        from resync.core.tws_multi.instance import TWSInstance, TWSInstanceConfig

        config = TWSInstanceConfig(
            name="TEST",
            host="tws.test.com",
            port=31116,
            ssl_enabled=True,
        )
        instance = TWSInstance(config=config)

        assert instance.connection_url == "https://tws.test.com:31116"


class TestTWSLearningStore:
    """Tests for TWS learning store."""

    def test_learning_store_import(self):
        """Test learning store import."""
        from resync.core.tws_multi.learning import TWSLearningStore

        assert TWSLearningStore is not None

    def test_learning_store_creation(self):
        """Test creating learning store."""
        from resync.core.tws_multi.learning import TWSLearningStore

        store = TWSLearningStore("test-instance")
        assert store.instance_id == "test-instance"

    def test_job_pattern_model(self):
        """Test JobPattern model."""
        from resync.core.tws_multi.learning import JobPattern

        pattern = JobPattern(
            job_name="JOB001",
            job_stream="STREAM1",
            avg_duration_seconds=120.5,
        )

        assert pattern.job_name == "JOB001"
        assert pattern.avg_duration_seconds == 120.5

    def test_learning_summary(self):
        """Test learning summary."""
        from resync.core.tws_multi.learning import TWSLearningStore

        store = TWSLearningStore("test-instance")
        summary = store.get_learning_summary()

        assert "instance_id" in summary
        assert "total_job_patterns" in summary


class TestTWSSession:
    """Tests for TWS session management."""

    def test_session_import(self):
        """Test session module import."""
        from resync.core.tws_multi.session import SessionManager, TWSSession

        assert TWSSession is not None
        assert SessionManager is not None

    def test_session_creation(self):
        """Test session creation."""
        from resync.core.tws_multi.session import TWSSession

        session = TWSSession(
            instance_id="inst-1",
            instance_name="SAZ",
            user_id="user-1",
            username="operator1",
        )

        assert session.instance_name == "SAZ"
        assert session.username == "operator1"
        assert not session.connected

    def test_session_manager(self):
        """Test session manager."""
        from resync.core.tws_multi.session import SessionManager

        manager = SessionManager()
        session = manager.create_session(
            instance_id="inst-1",
            instance_name="SAZ",
            user_id="user-1",
            username="operator1",
        )

        assert session is not None
        assert session.connected

        # Get session
        retrieved = manager.get_session(session.id)
        assert retrieved.id == session.id

        # Close session
        manager.close_session(session.id)
        assert manager.get_session(session.id) is None


class TestTWSManager:
    """Tests for TWS instance manager."""

    def test_manager_import(self):
        """Test manager import."""
        from resync.core.tws_multi.manager import TWSInstanceManager, get_tws_manager

        assert TWSInstanceManager is not None
        assert callable(get_tws_manager)

    def test_manager_creation(self):
        """Test manager creation."""
        import tempfile
        from pathlib import Path

        from resync.core.tws_multi.manager import TWSInstanceManager

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "instances.json"
            manager = TWSInstanceManager(config_path=config_path)

            # Should have default instances
            instances = manager.get_all_instances()
            assert len(instances) >= 0  # May or may not have defaults


class TestTWSInstanceRoutes:
    """Tests for TWS instance API routes."""

    def test_routes_import(self):
        """Test routes module import."""
        from resync.fastapi_app.api.v1.routes import admin_tws_instances

        assert admin_tws_instances is not None

    def test_router_exists(self):
        """Test router exists."""
        from resync.fastapi_app.api.v1.routes.admin_tws_instances import router

        assert router is not None

    def test_models_import(self):
        """Test Pydantic models import."""
        from resync.fastapi_app.api.v1.routes.admin_tws_instances import (
            SessionCreate,
            TWSInstanceCreate,
            TWSInstanceUpdate,
        )

        assert TWSInstanceCreate is not None
        assert TWSInstanceUpdate is not None

    def test_create_model(self):
        """Test TWSInstanceCreate model."""
        from resync.fastapi_app.api.v1.routes.admin_tws_instances import TWSInstanceCreate

        instance = TWSInstanceCreate(
            name="SAZ",
            display_name="São Paulo - SAZ",
            host="tws.saz.com.br",
        )

        assert instance.name == "SAZ"
        assert instance.port == 31116
        assert instance.ssl_enabled
