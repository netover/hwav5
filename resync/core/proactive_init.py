"""
Inicialização do Sistema de Monitoramento Proativo

Este módulo coordena a inicialização de todos os componentes
do sistema de monitoramento em tempo real do TWS.

Componentes:
- TWSBackgroundPoller: Coleta status do TWS
- EventBus: Broadcast de eventos
- TWSStatusStore: Persistência e padrões
- MonitoringConfig: Configurações

Autor: Resync Team
Versão: 5.2
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class ProactiveMonitoringSystem:
    """
    Sistema central de monitoramento proativo.
    
    Coordena todos os componentes e garante inicialização
    e shutdown ordenados.
    """
    
    def __init__(self):
        self._initialized = False
        self._running = False
        
        # Componentes
        self._poller = None
        self._event_bus = None
        self._status_store = None
        self._config = None
        
        # Tasks
        self._pattern_detection_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def initialize(
        self,
        tws_client: Any,
        polling_interval: int = 30,
        db_path: str = "data/tws_status.db",
    ) -> None:
        """
        Inicializa todos os componentes do sistema.
        
        Args:
            tws_client: Cliente TWS para API calls
            polling_interval: Intervalo de polling em segundos
            db_path: Caminho do banco de dados
        """
        if self._initialized:
            logger.warning("Proactive monitoring already initialized")
            return
        
        logger.info("Initializing proactive monitoring system...")
        
        # 1. Carrega configurações
        from resync.core.monitoring_config import get_monitoring_config
        self._config = get_monitoring_config()
        
        # Usa intervalo da config se não especificado
        if polling_interval == 30:
            polling_interval = self._config.polling_interval_seconds
        
        # 2. Inicializa Status Store
        from resync.core.tws_status_store import init_status_store
        self._status_store = await init_status_store(
            db_path=db_path,
            retention_days_full=self._config.retention_days_full,
            retention_days_summary=self._config.retention_days_summary,
            retention_days_patterns=self._config.retention_days_patterns,
        )
        logger.info("Status store initialized")
        
        # 3. Inicializa Event Bus
        from resync.core.event_bus import init_event_bus
        self._event_bus = init_event_bus(
            history_size=1000,
            enable_persistence=False,
        )
        await self._event_bus.start()
        logger.info("Event bus initialized")
        
        # 4. Inicializa Background Poller
        from resync.core.tws_background_poller import init_tws_poller
        self._poller = init_tws_poller(
            tws_client=tws_client,
            polling_interval=polling_interval,
            status_store=self._status_store,
            event_bus=self._event_bus,
        )
        
        # Configura thresholds do poller
        self._poller.job_stuck_threshold_minutes = self._config.job_stuck_threshold_minutes
        self._poller.job_late_threshold_minutes = self._config.job_late_threshold_minutes
        
        logger.info("Background poller initialized")
        
        # 5. Registra handlers
        self._register_event_handlers()
        
        self._initialized = True
        logger.info(
            "proactive_monitoring_system_initialized",
            polling_interval=polling_interval,
            db_path=db_path,
        )
    
    async def start(self) -> None:
        """Inicia todos os componentes."""
        if not self._initialized:
            raise RuntimeError("System not initialized. Call initialize() first.")
        
        if self._running:
            logger.warning("Proactive monitoring already running")
            return
        
        logger.info("Starting proactive monitoring system...")
        
        # Inicia poller
        await self._poller.start()
        
        # Inicia tasks de background
        if self._config.pattern_detection_enabled:
            self._pattern_detection_task = asyncio.create_task(
                self._pattern_detection_loop()
            )
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self._running = True
        logger.info("proactive_monitoring_system_started")
    
    async def stop(self) -> None:
        """Para todos os componentes."""
        if not self._running:
            return
        
        logger.info("Stopping proactive monitoring system...")
        
        # Cancela tasks
        if self._pattern_detection_task:
            self._pattern_detection_task.cancel()
            try:
                await self._pattern_detection_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Para componentes
        if self._poller:
            await self._poller.stop()
        
        if self._event_bus:
            await self._event_bus.stop()
        
        if self._status_store:
            await self._status_store.close()
        
        self._running = False
        logger.info("proactive_monitoring_system_stopped")
    
    def _register_event_handlers(self) -> None:
        """Registra handlers para eventos."""
        
        # Handler para persistir eventos no store
        async def persist_event(event_data):
            if self._status_store:
                await self._status_store.save_event(event_data)
        
        self._event_bus.subscribe(
            subscriber_id="status_store",
            callback=persist_event,
        )
        
        # Handler para notificações Teams (se configurado)
        if self._config.teams_notifications_enabled and self._config.teams_webhook_url:
            self._setup_teams_notifications()
        
        # Handler para logging de eventos críticos
        async def log_critical_events(event_data):
            severity = event_data.get("severity", "")
            if severity in ["critical", "error"]:
                logger.warning(
                    "critical_event_detected",
                    event_type=event_data.get("event_type"),
                    source=event_data.get("source"),
                    message=event_data.get("message"),
                )
        
        self._event_bus.subscribe(
            subscriber_id="critical_logger",
            callback=log_critical_events,
        )
    
    def _setup_teams_notifications(self) -> None:
        """Configura notificações do Teams."""
        from resync.core.teams_integration import TeamsNotifier
        
        notifier = TeamsNotifier(webhook_url=self._config.teams_webhook_url)
        
        async def send_teams_alert(event_data):
            severity = event_data.get("severity", "")
            if severity in self._config.notification_severities:
                await notifier.send_alert(
                    title=f"TWS Alert: {event_data.get('source', 'Unknown')}",
                    message=event_data.get("message", ""),
                    severity=severity,
                    details=event_data.get("details", {}),
                )
        
        self._event_bus.subscribe(
            subscriber_id="teams_notifier",
            callback=send_teams_alert,
        )
    
    async def _pattern_detection_loop(self) -> None:
        """Loop para detecção periódica de padrões."""
        interval = self._config.pattern_detection_interval_minutes * 60
        
        while True:
            try:
                await asyncio.sleep(interval)
                
                if self._status_store:
                    patterns = await self._status_store.detect_patterns()
                    
                    if patterns:
                        logger.info(
                            "patterns_detected",
                            count=len(patterns),
                        )
                        
                        # Publica evento de padrão detectado
                        for pattern in patterns:
                            if pattern.confidence >= self._config.pattern_min_confidence:
                                await self._event_bus.publish({
                                    "event_type": "pattern_detected",
                                    "severity": "info",
                                    "source": "PATTERN_DETECTOR",
                                    "message": pattern.description,
                                    "details": pattern.to_dict(),
                                    "timestamp": datetime.now().isoformat(),
                                })
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("pattern_detection_error", error=str(e))
    
    async def _cleanup_loop(self) -> None:
        """Loop para limpeza periódica de dados antigos."""
        # Executa cleanup uma vez por dia às 03:00
        while True:
            try:
                # Calcula tempo até próxima execução (03:00)
                now = datetime.now()
                next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run = next_run.replace(day=next_run.day + 1)
                
                wait_seconds = (next_run - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                if self._status_store:
                    deleted = await self._status_store.cleanup_old_data()
                    logger.info("scheduled_cleanup_completed", deleted=deleted)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("cleanup_error", error=str(e))
                await asyncio.sleep(3600)  # Retry in 1 hour
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def poller(self):
        return self._poller
    
    @property
    def event_bus(self):
        return self._event_bus
    
    @property
    def status_store(self):
        return self._status_store
    
    @property
    def config(self):
        return self._config
    
    def update_polling_interval(self, seconds: int) -> None:
        """Atualiza intervalo de polling em runtime."""
        if self._poller:
            self._poller.set_polling_interval(seconds)
        
        from resync.core.monitoring_config import update_monitoring_config
        update_monitoring_config({"polling_interval_seconds": seconds})
    
    async def get_system_status(self) -> dict:
        """Retorna status completo do sistema."""
        status = {
            "initialized": self._initialized,
            "running": self._running,
            "timestamp": datetime.now().isoformat(),
        }
        
        if self._poller:
            status["poller"] = self._poller.get_metrics()
            snapshot = self._poller.get_current_snapshot()
            if snapshot:
                status["snapshot"] = snapshot.to_dict()
        
        if self._event_bus:
            status["event_bus"] = self._event_bus.get_metrics()
        
        if self._status_store:
            status["database"] = await self._status_store.get_database_stats()
        
        if self._config:
            status["config"] = self._config.to_frontend_config()
        
        return status


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_monitoring_system: Optional[ProactiveMonitoringSystem] = None


def get_monitoring_system() -> Optional[ProactiveMonitoringSystem]:
    """Retorna instância singleton do sistema de monitoramento."""
    return _monitoring_system


async def init_monitoring_system(
    tws_client: Any,
    polling_interval: int = 30,
    db_path: str = "data/tws_status.db",
    auto_start: bool = True,
) -> ProactiveMonitoringSystem:
    """
    Inicializa o sistema de monitoramento singleton.
    
    Args:
        tws_client: Cliente TWS
        polling_interval: Intervalo de polling
        db_path: Caminho do banco
        auto_start: Se deve iniciar automaticamente
    
    Returns:
        Instância do sistema de monitoramento
    """
    global _monitoring_system
    
    _monitoring_system = ProactiveMonitoringSystem()
    await _monitoring_system.initialize(
        tws_client=tws_client,
        polling_interval=polling_interval,
        db_path=db_path,
    )
    
    if auto_start:
        await _monitoring_system.start()
    
    return _monitoring_system


async def shutdown_monitoring_system() -> None:
    """Desliga o sistema de monitoramento."""
    global _monitoring_system
    
    if _monitoring_system:
        await _monitoring_system.stop()
        _monitoring_system = None
