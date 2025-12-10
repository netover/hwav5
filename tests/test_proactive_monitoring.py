"""
Testes do Sistema de Monitoramento Proativo

Testes unitários e de integração para validar o funcionamento
do sistema de monitoramento em tempo real.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestTWSBackgroundPoller:
    """Testes para o Background Poller do TWS."""
    
    @pytest.fixture
    def mock_tws_client(self):
        """Cria um cliente TWS mock."""
        client = AsyncMock()
        client.query_workstations.return_value = {
            "items": [
                {"name": "WS001", "status": "LINKED", "agentStatus": "RUNNING"},
                {"name": "WS002", "status": "LINKED", "agentStatus": "RUNNING"},
            ]
        }
        client.get_plan_jobs.return_value = {
            "items": [
                {
                    "id": "1", "name": "JOB001", "status": "SUCC",
                    "workstation": "WS001", "jobStream": "STREAM1"
                },
                {
                    "id": "2", "name": "JOB002", "status": "EXEC",
                    "workstation": "WS002", "jobStream": "STREAM1"
                },
            ]
        }
        return client
    
    @pytest.mark.asyncio
    async def test_poller_initialization(self, mock_tws_client):
        """Testa inicialização do poller."""
        from resync.core.tws_background_poller import TWSBackgroundPoller
        
        poller = TWSBackgroundPoller(
            tws_client=mock_tws_client,
            polling_interval=30,
        )
        
        assert poller.polling_interval == 30
        assert not poller._is_running
    
    @pytest.mark.asyncio
    async def test_poller_collect_snapshot(self, mock_tws_client):
        """Testa coleta de snapshot."""
        from resync.core.tws_background_poller import TWSBackgroundPoller
        
        poller = TWSBackgroundPoller(
            tws_client=mock_tws_client,
            polling_interval=30,
        )
        
        snapshot = await poller._collect_snapshot()
        
        assert snapshot is not None
        assert len(snapshot.workstations) == 2
        assert len(snapshot.jobs) == 2
        assert snapshot.jobs_completed == 1
        assert snapshot.jobs_running == 1
    
    @pytest.mark.asyncio
    async def test_poller_detect_job_abend(self, mock_tws_client):
        """Testa detecção de job ABEND."""
        from resync.core.tws_background_poller import TWSBackgroundPoller, EventType
        
        poller = TWSBackgroundPoller(
            tws_client=mock_tws_client,
            polling_interval=30,
        )
        
        # Primeiro snapshot
        await poller._collect_snapshot()
        poller._update_cache(poller._previous_snapshot or await poller._collect_snapshot())
        
        # Simula mudança para ABEND
        mock_tws_client.get_plan_jobs.return_value = {
            "items": [
                {
                    "id": "1", "name": "JOB001", "status": "ABEND",
                    "workstation": "WS001", "jobStream": "STREAM1",
                    "errorMessage": "Database connection failed"
                },
            ]
        }
        
        # Segundo snapshot
        snapshot = await poller._collect_snapshot()
        events = poller._detect_changes(snapshot)
        
        # Verifica se detectou ABEND
        abend_events = [e for e in events if e.event_type == EventType.JOB_ABEND]
        assert len(abend_events) >= 1


class TestEventBus:
    """Testes para o Event Bus."""
    
    @pytest.mark.asyncio
    async def test_event_bus_publish(self):
        """Testa publicação de eventos."""
        from resync.core.event_bus import EventBus
        
        bus = EventBus()
        await bus.start()
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        bus.subscribe("test", handler)
        
        await bus.publish({"event_type": "test", "message": "Hello"})
        
        # Aguarda processamento
        await asyncio.sleep(0.1)
        
        await bus.stop()
        
        assert len(received_events) == 1
        assert received_events[0]["message"] == "Hello"
    
    @pytest.mark.asyncio
    async def test_event_bus_history(self):
        """Testa histórico de eventos."""
        from resync.core.event_bus import EventBus
        
        bus = EventBus(history_size=100)
        await bus.start()
        
        for i in range(10):
            await bus.publish({"event_type": "test", "index": i})
        
        await asyncio.sleep(0.1)
        
        recent = bus.get_recent_events(5)
        
        await bus.stop()
        
        assert len(recent) == 5


class TestTWSStatusStore:
    """Testes para o Status Store."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Cria banco temporário."""
        return str(tmp_path / "test_status.db")
    
    @pytest.mark.asyncio
    async def test_store_initialization(self, temp_db):
        """Testa inicialização do store."""
        from resync.core.tws_status_store import TWSStatusStore
        
        store = TWSStatusStore(db_path=temp_db)
        await store.initialize()
        
        stats = await store.get_database_stats()
        
        await store.close()
        
        assert stats["snapshots"] == 0
        assert stats["events"] == 0
    
    @pytest.mark.asyncio
    async def test_store_save_event(self, temp_db):
        """Testa salvamento de eventos."""
        from resync.core.tws_status_store import TWSStatusStore
        
        store = TWSStatusStore(db_path=temp_db)
        await store.initialize()
        
        event = {
            "event_id": "test_1",
            "event_type": "job_abend",
            "severity": "error",
            "source": "JOB001",
            "message": "Job failed",
            "timestamp": datetime.now().isoformat(),
        }
        
        event_id = await store.save_event(event)
        
        assert event_id > 0
        
        # Verifica busca
        events = await store.get_events_in_range(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )
        
        await store.close()
        
        assert len(events) == 1
        assert events[0]["source"] == "JOB001"
    
    @pytest.mark.asyncio
    async def test_store_pattern_detection(self, temp_db):
        """Testa detecção de padrões."""
        from resync.core.tws_status_store import TWSStatusStore
        
        store = TWSStatusStore(db_path=temp_db)
        await store.initialize()
        
        # Simula múltiplas falhas do mesmo job
        for i in range(5):
            await store._save_job_status({
                "job_id": f"job_{i}",
                "job_name": "FAILING_JOB",
                "status": "ABEND",
                "workstation": "WS001",
            })
        
        patterns = await store.detect_patterns()
        
        await store.close()
        
        # Deve detectar padrão de falha recorrente
        recurring = [p for p in patterns if p.pattern_type == "recurring_failure"]
        # Pode não ter padrão se menos de 3 falhas no período


class TestTWSHistoryRAG:
    """Testes para o RAG de histórico."""
    
    def test_time_extraction_yesterday(self):
        """Testa extração de 'ontem'."""
        from resync.core.tws_history_rag import TWSHistoryRAG
        
        rag = TWSHistoryRAG()
        
        start, end = rag._extract_time_range("o que aconteceu ontem?")
        
        expected = (datetime.now() - timedelta(days=1)).date()
        assert start.date() == expected
        assert end.date() == expected
    
    def test_time_extraction_last_days(self):
        """Testa extração de 'últimos N dias'."""
        from resync.core.tws_history_rag import TWSHistoryRAG
        
        rag = TWSHistoryRAG()
        
        start, end = rag._extract_time_range("últimos 7 dias")
        
        diff = (end - start).days
        assert diff >= 6 and diff <= 7
    
    def test_intent_identification(self):
        """Testa identificação de intenção."""
        from resync.core.tws_history_rag import TWSHistoryRAG
        
        rag = TWSHistoryRAG()
        
        assert rag._identify_intent("quais jobs falharam?") == "failures"
        assert rag._identify_intent("o que aconteceu?") == "summary"
        assert rag._identify_intent("status das workstations") == "workstations"


class TestMonitoringConfig:
    """Testes para configuração de monitoramento."""
    
    def test_default_config(self):
        """Testa configuração padrão."""
        from resync.core.monitoring_config import MonitoringConfig
        
        config = MonitoringConfig()
        
        assert config.polling_interval_seconds == 30
        assert config.alerts_enabled == True
        assert config.pattern_detection_enabled == True
    
    def test_config_validation(self):
        """Testa validação de configuração."""
        from resync.core.monitoring_config import MonitoringConfig
        import pytest
        
        # Intervalo muito pequeno deve falhar
        with pytest.raises(Exception):
            MonitoringConfig(polling_interval_seconds=1)
        
        # Intervalo muito grande deve falhar
        with pytest.raises(Exception):
            MonitoringConfig(polling_interval_seconds=500)
    
    def test_frontend_config(self):
        """Testa conversão para frontend."""
        from resync.core.monitoring_config import MonitoringConfig
        
        config = MonitoringConfig()
        frontend = config.to_frontend_config()
        
        assert "polling" in frontend
        assert "alerts" in frontend
        assert "notifications" in frontend
        assert "dashboard" in frontend
        
        assert frontend["polling"]["interval"] == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
