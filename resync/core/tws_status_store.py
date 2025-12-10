"""
TWS Status Store - Armazenamento de Status para Aprendizado

Este módulo implementa persistência de status do TWS com suporte
a queries históricas e detecção de padrões.

Funcionalidades:
- Armazenamento de snapshots e eventos
- Retenção escalonada (7/30/90 dias)
- Detecção de padrões de falha
- Correlação problema-solução
- Queries para RAG ("o que aconteceu ontem?")

Autor: Resync Team
Versão: 5.2
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PatternMatch:
    """Representa um padrão detectado."""
    
    pattern_id: str
    pattern_type: str  # recurring_failure, time_correlation, dependency_chain
    description: str
    confidence: float  # 0.0 a 1.0
    occurrences: int
    first_seen: datetime
    last_seen: datetime
    affected_jobs: List[str]
    suggested_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "affected_jobs": self.affected_jobs,
            "suggested_action": self.suggested_action,
            "metadata": self.metadata,
        }


@dataclass
class ProblemSolution:
    """Correlação problema-solução."""
    
    problem_id: str
    problem_type: str  # job_abend, ws_offline, etc.
    problem_pattern: str  # Padrão de erro (regex ou descrição)
    solution: str
    success_rate: float
    times_applied: int
    last_applied: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "problem_type": self.problem_type,
            "problem_pattern": self.problem_pattern,
            "solution": self.solution,
            "success_rate": self.success_rate,
            "times_applied": self.times_applied,
            "last_applied": self.last_applied.isoformat(),
        }


class TWSStatusStore:
    """
    Store para status do TWS com suporte a histórico e aprendizado.
    
    Características:
    - SQLite com WAL mode para writes eficientes
    - Retenção escalonada automática
    - Índices otimizados para queries temporais
    - Detecção de padrões integrada
    """
    
    SCHEMA = """
    -- Snapshots do sistema
    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        system_health TEXT,
        jobs_running INTEGER,
        jobs_completed INTEGER,
        jobs_failed INTEGER,
        jobs_pending INTEGER,
        total_jobs INTEGER,
        snapshot_data TEXT,  -- JSON completo
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Status de jobs individuais
    CREATE TABLE IF NOT EXISTS job_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        job_name TEXT NOT NULL,
        job_stream TEXT,
        workstation TEXT,
        status TEXT NOT NULL,
        return_code INTEGER,
        start_time TEXT,
        end_time TEXT,
        duration_seconds REAL,
        error_message TEXT,
        timestamp TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Status de workstations
    CREATE TABLE IF NOT EXISTS workstation_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        agent_status TEXT,
        jobs_running INTEGER,
        jobs_pending INTEGER,
        timestamp TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Eventos gerados
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE NOT NULL,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        source TEXT,
        message TEXT,
        details TEXT,  -- JSON
        previous_state TEXT,
        current_state TEXT,
        timestamp TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Padrões detectados
    CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_id TEXT UNIQUE NOT NULL,
        pattern_type TEXT NOT NULL,
        description TEXT,
        confidence REAL,
        occurrences INTEGER DEFAULT 1,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        affected_jobs TEXT,  -- JSON array
        suggested_action TEXT,
        metadata TEXT,  -- JSON
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Correlações problema-solução
    CREATE TABLE IF NOT EXISTS problem_solutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        problem_id TEXT UNIQUE NOT NULL,
        problem_type TEXT NOT NULL,
        problem_pattern TEXT NOT NULL,
        solution TEXT NOT NULL,
        success_rate REAL DEFAULT 0.0,
        times_applied INTEGER DEFAULT 0,
        times_successful INTEGER DEFAULT 0,
        last_applied TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Índices para performance
    CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);
    CREATE INDEX IF NOT EXISTS idx_job_status_timestamp ON job_status(timestamp);
    CREATE INDEX IF NOT EXISTS idx_job_status_name ON job_status(job_name);
    CREATE INDEX IF NOT EXISTS idx_job_status_status ON job_status(status);
    CREATE INDEX IF NOT EXISTS idx_workstation_status_timestamp ON workstation_status(timestamp);
    CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
    CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
    CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
    CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
    
    -- FTS para busca textual
    CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
        event_type, source, message, details,
        content='events',
        content_rowid='id'
    );
    
    -- Triggers para manter FTS sincronizado
    CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
        INSERT INTO events_fts(rowid, event_type, source, message, details)
        VALUES (new.id, new.event_type, new.source, new.message, new.details);
    END;
    """
    
    def __init__(
        self,
        db_path: str = "data/tws_status.db",
        retention_days_full: int = 7,
        retention_days_summary: int = 30,
        retention_days_patterns: int = 90,
    ):
        """
        Inicializa o status store.
        
        Args:
            db_path: Caminho do banco de dados
            retention_days_full: Dias para reter dados completos
            retention_days_summary: Dias para reter sumários
            retention_days_patterns: Dias para reter padrões
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.retention_days_full = retention_days_full
        self.retention_days_summary = retention_days_summary
        self.retention_days_patterns = retention_days_patterns
        
        self._db: Optional[aiosqlite.Connection] = None
        self._initialized = False
        
        # Cache para detecção de padrões
        self._failure_cache: Dict[str, List[datetime]] = defaultdict(list)
        self._pattern_cache: Dict[str, PatternMatch] = {}
        
        logger.info(
            "tws_status_store_initialized",
            db_path=str(self.db_path),
            retention_full=retention_days_full,
            retention_summary=retention_days_summary,
        )
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    
    async def initialize(self) -> None:
        """Inicializa o banco de dados."""
        if self._initialized:
            return
        
        self._db = await aiosqlite.connect(str(self.db_path))
        
        # Configurações de performance
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("PRAGMA cache_size=-64000")  # 64MB cache
        await self._db.execute("PRAGMA temp_store=MEMORY")
        
        # Cria schema
        await self._db.executescript(self.SCHEMA)
        await self._db.commit()
        
        self._initialized = True
        logger.info("tws_status_store_database_initialized")
    
    async def close(self) -> None:
        """Fecha conexão com o banco."""
        if self._db:
            await self._db.close()
            self._db = None
            self._initialized = False
    
    # =========================================================================
    # SNAPSHOT OPERATIONS
    # =========================================================================
    
    async def save_snapshot(self, snapshot: Any) -> int:
        """
        Salva um snapshot do sistema.
        
        Returns:
            ID do snapshot salvo
        """
        await self.initialize()
        
        snapshot_dict = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        
        cursor = await self._db.execute(
            """
            INSERT INTO snapshots (
                timestamp, system_health, jobs_running, jobs_completed,
                jobs_failed, jobs_pending, total_jobs, snapshot_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_dict.get("timestamp", datetime.now().isoformat()),
                snapshot_dict.get("summary", {}).get("system_health", "unknown"),
                snapshot_dict.get("summary", {}).get("jobs_running", 0),
                snapshot_dict.get("summary", {}).get("jobs_completed", 0),
                snapshot_dict.get("summary", {}).get("jobs_failed", 0),
                snapshot_dict.get("summary", {}).get("jobs_pending", 0),
                snapshot_dict.get("summary", {}).get("total_jobs_today", 0),
                json.dumps(snapshot_dict),
            ),
        )
        await self._db.commit()
        
        # Salva jobs individuais (apenas os que mudaram de status)
        for job in snapshot_dict.get("jobs", []):
            await self._save_job_status(job)
        
        # Salva workstations
        for ws in snapshot_dict.get("workstations", []):
            await self._save_workstation_status(ws)
        
        return cursor.lastrowid
    
    async def _save_job_status(self, job: Dict[str, Any]) -> None:
        """Salva status de um job."""
        await self._db.execute(
            """
            INSERT INTO job_status (
                job_id, job_name, job_stream, workstation, status,
                return_code, start_time, end_time, duration_seconds,
                error_message, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.get("job_id"),
                job.get("job_name"),
                job.get("job_stream"),
                job.get("workstation"),
                job.get("status"),
                job.get("return_code"),
                job.get("start_time"),
                job.get("end_time"),
                job.get("duration_seconds"),
                job.get("error_message"),
                datetime.now().isoformat(),
            ),
        )
        
        # Atualiza cache de falhas para detecção de padrões
        if job.get("status") == "ABEND":
            job_name = job.get("job_name", "unknown")
            self._failure_cache[job_name].append(datetime.now())
            
            # Mantém apenas últimos 30 dias no cache
            cutoff = datetime.now() - timedelta(days=30)
            self._failure_cache[job_name] = [
                dt for dt in self._failure_cache[job_name]
                if dt > cutoff
            ]
    
    async def _save_workstation_status(self, ws: Dict[str, Any]) -> None:
        """Salva status de uma workstation."""
        await self._db.execute(
            """
            INSERT INTO workstation_status (
                name, status, agent_status, jobs_running, jobs_pending, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ws.get("name"),
                ws.get("status"),
                ws.get("agent_status"),
                ws.get("jobs_running", 0),
                ws.get("jobs_pending", 0),
                datetime.now().isoformat(),
            ),
        )
    
    # =========================================================================
    # EVENT OPERATIONS
    # =========================================================================
    
    async def save_event(self, event: Any) -> int:
        """Salva um evento."""
        await self.initialize()
        
        event_dict = event.to_dict() if hasattr(event, "to_dict") else event
        
        try:
            cursor = await self._db.execute(
                """
                INSERT INTO events (
                    event_id, event_type, severity, source, message,
                    details, previous_state, current_state, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_dict.get("event_id"),
                    event_dict.get("event_type"),
                    event_dict.get("severity"),
                    event_dict.get("source"),
                    event_dict.get("message"),
                    json.dumps(event_dict.get("details", {})),
                    event_dict.get("previous_state"),
                    event_dict.get("current_state"),
                    event_dict.get("timestamp", datetime.now().isoformat()),
                ),
            )
            await self._db.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Evento já existe
            return 0
    
    # =========================================================================
    # QUERY OPERATIONS
    # =========================================================================
    
    async def get_events_in_range(
        self,
        start_time: datetime,
        end_time: datetime,
        event_types: Optional[List[str]] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Busca eventos em um intervalo de tempo.
        
        Args:
            start_time: Início do período
            end_time: Fim do período
            event_types: Filtrar por tipos de evento
            severity: Filtrar por severidade
            limit: Máximo de resultados
        """
        await self.initialize()
        
        query = """
            SELECT event_id, event_type, severity, source, message,
                   details, previous_state, current_state, timestamp
            FROM events
            WHERE timestamp BETWEEN ? AND ?
        """
        params = [start_time.isoformat(), end_time.isoformat()]
        
        if event_types:
            placeholders = ",".join(["?" for _ in event_types])
            query += f" AND event_type IN ({placeholders})"
            params.extend(event_types)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        
        return [
            {
                "event_id": row[0],
                "event_type": row[1],
                "severity": row[2],
                "source": row[3],
                "message": row[4],
                "details": json.loads(row[5]) if row[5] else {},
                "previous_state": row[6],
                "current_state": row[7],
                "timestamp": row[8],
            }
            for row in rows
        ]
    
    async def search_events(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Busca eventos por texto (FTS).
        
        Args:
            query: Termo de busca
            limit: Máximo de resultados
        """
        await self.initialize()
        
        cursor = await self._db.execute(
            """
            SELECT e.event_id, e.event_type, e.severity, e.source, e.message,
                   e.details, e.timestamp
            FROM events e
            JOIN events_fts ON e.id = events_fts.rowid
            WHERE events_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        rows = await cursor.fetchall()
        
        return [
            {
                "event_id": row[0],
                "event_type": row[1],
                "severity": row[2],
                "source": row[3],
                "message": row[4],
                "details": json.loads(row[5]) if row[5] else {},
                "timestamp": row[6],
            }
            for row in rows
        ]
    
    async def get_job_history(
        self,
        job_name: str,
        days: int = 7,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Obtém histórico de um job específico.
        
        Args:
            job_name: Nome do job
            days: Quantos dias de histórico
            limit: Máximo de resultados
        """
        await self.initialize()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor = await self._db.execute(
            """
            SELECT job_id, job_name, job_stream, workstation, status,
                   return_code, start_time, end_time, duration_seconds,
                   error_message, timestamp
            FROM job_status
            WHERE job_name = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (job_name, cutoff, limit),
        )
        rows = await cursor.fetchall()
        
        return [
            {
                "job_id": row[0],
                "job_name": row[1],
                "job_stream": row[2],
                "workstation": row[3],
                "status": row[4],
                "return_code": row[5],
                "start_time": row[6],
                "end_time": row[7],
                "duration_seconds": row[8],
                "error_message": row[9],
                "timestamp": row[10],
            }
            for row in rows
        ]
    
    async def get_daily_summary(
        self,
        date: datetime,
    ) -> Dict[str, Any]:
        """
        Obtém resumo de um dia específico.
        
        Args:
            date: Data do resumo
        """
        await self.initialize()
        
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        # Contagem de jobs por status
        cursor = await self._db.execute(
            """
            SELECT status, COUNT(*) as count
            FROM job_status
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY status
            """,
            (start.isoformat(), end.isoformat()),
        )
        status_counts = dict(await cursor.fetchall())
        
        # Eventos do dia
        events = await self.get_events_in_range(start, end, limit=500)
        
        # Jobs que falharam
        cursor = await self._db.execute(
            """
            SELECT DISTINCT job_name, error_message
            FROM job_status
            WHERE status = 'ABEND' AND timestamp BETWEEN ? AND ?
            """,
            (start.isoformat(), end.isoformat()),
        )
        failed_jobs = await cursor.fetchall()
        
        return {
            "date": date.strftime("%Y-%m-%d"),
            "status_counts": status_counts,
            "total_events": len(events),
            "critical_events": sum(1 for e in events if e["severity"] == "critical"),
            "failed_jobs": [
                {"job_name": row[0], "error": row[1]}
                for row in failed_jobs
            ],
            "summary": f"Em {date.strftime('%d/%m/%Y')}: "
                       f"{status_counts.get('SUCC', 0)} jobs completados, "
                       f"{status_counts.get('ABEND', 0)} falhas, "
                       f"{len(events)} eventos gerados.",
        }
    
    # =========================================================================
    # PATTERN DETECTION
    # =========================================================================
    
    async def detect_patterns(self) -> List[PatternMatch]:
        """
        Detecta padrões nos dados históricos.
        
        Returns:
            Lista de padrões detectados
        """
        await self.initialize()
        
        patterns = []
        
        # 1. Falhas recorrentes (mesmo job falha frequentemente)
        patterns.extend(await self._detect_recurring_failures())
        
        # 2. Correlações temporais (falhas em horários específicos)
        patterns.extend(await self._detect_time_correlations())
        
        # 3. Cadeias de dependência (job A falha → job B falha)
        patterns.extend(await self._detect_dependency_chains())
        
        # Salva padrões no banco
        for pattern in patterns:
            await self._save_pattern(pattern)
        
        return patterns
    
    async def _detect_recurring_failures(self) -> List[PatternMatch]:
        """Detecta jobs que falham frequentemente."""
        patterns = []
        
        # Jobs com mais de 3 falhas nos últimos 7 dias
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        
        cursor = await self._db.execute(
            """
            SELECT job_name, COUNT(*) as failure_count,
                   MIN(timestamp) as first_failure,
                   MAX(timestamp) as last_failure
            FROM job_status
            WHERE status = 'ABEND' AND timestamp > ?
            GROUP BY job_name
            HAVING failure_count >= 3
            ORDER BY failure_count DESC
            """,
            (cutoff,),
        )
        rows = await cursor.fetchall()
        
        for row in rows:
            job_name, count, first, last = row
            
            confidence = min(1.0, count / 10)  # Normaliza para 0-1
            
            pattern = PatternMatch(
                pattern_id=f"recurring_{job_name}_{int(time.time())}",
                pattern_type="recurring_failure",
                description=f"Job {job_name} falhou {count} vezes nos últimos 7 dias",
                confidence=confidence,
                occurrences=count,
                first_seen=datetime.fromisoformat(first),
                last_seen=datetime.fromisoformat(last),
                affected_jobs=[job_name],
                suggested_action=f"Investigar causa raiz das falhas do job {job_name}",
                metadata={"failure_count": count},
            )
            patterns.append(pattern)
        
        return patterns
    
    async def _detect_time_correlations(self) -> List[PatternMatch]:
        """Detecta falhas em horários específicos."""
        patterns = []
        
        # Agrupa falhas por hora do dia
        cutoff = (datetime.now() - timedelta(days=14)).isoformat()
        
        cursor = await self._db.execute(
            """
            SELECT 
                job_name,
                CAST(strftime('%H', timestamp) AS INTEGER) as hour,
                COUNT(*) as count
            FROM job_status
            WHERE status = 'ABEND' AND timestamp > ?
            GROUP BY job_name, hour
            HAVING count >= 3
            ORDER BY count DESC
            """,
            (cutoff,),
        )
        rows = await cursor.fetchall()
        
        for row in rows:
            job_name, hour, count = row
            
            pattern = PatternMatch(
                pattern_id=f"time_corr_{job_name}_{hour}_{int(time.time())}",
                pattern_type="time_correlation",
                description=f"Job {job_name} tende a falhar por volta das {hour:02d}:00",
                confidence=min(1.0, count / 7),
                occurrences=count,
                first_seen=datetime.now() - timedelta(days=14),
                last_seen=datetime.now(),
                affected_jobs=[job_name],
                suggested_action=f"Verificar dependências e recursos às {hour:02d}:00",
                metadata={"hour": hour, "failure_count": count},
            )
            patterns.append(pattern)
        
        return patterns
    
    async def _detect_dependency_chains(self) -> List[PatternMatch]:
        """Detecta cadeias de falha (job A falha → job B falha)."""
        patterns = []
        
        # Jobs que falham dentro de 10 minutos um do outro
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        
        cursor = await self._db.execute(
            """
            SELECT 
                a.job_name as job_a,
                b.job_name as job_b,
                COUNT(*) as correlation_count
            FROM job_status a
            JOIN job_status b ON 
                a.job_name != b.job_name
                AND a.status = 'ABEND'
                AND b.status = 'ABEND'
                AND datetime(b.timestamp) BETWEEN 
                    datetime(a.timestamp) 
                    AND datetime(a.timestamp, '+10 minutes')
            WHERE a.timestamp > ?
            GROUP BY a.job_name, b.job_name
            HAVING correlation_count >= 2
            ORDER BY correlation_count DESC
            LIMIT 20
            """,
            (cutoff,),
        )
        rows = await cursor.fetchall()
        
        for row in rows:
            job_a, job_b, count = row
            
            pattern = PatternMatch(
                pattern_id=f"dep_chain_{job_a}_{job_b}_{int(time.time())}",
                pattern_type="dependency_chain",
                description=f"Quando {job_a} falha, {job_b} também falha em seguida",
                confidence=min(1.0, count / 5),
                occurrences=count,
                first_seen=datetime.now() - timedelta(days=7),
                last_seen=datetime.now(),
                affected_jobs=[job_a, job_b],
                suggested_action=f"Verificar dependência entre {job_a} e {job_b}",
                metadata={"job_a": job_a, "job_b": job_b, "correlation_count": count},
            )
            patterns.append(pattern)
        
        return patterns
    
    async def _save_pattern(self, pattern: PatternMatch) -> None:
        """Salva ou atualiza um padrão."""
        try:
            await self._db.execute(
                """
                INSERT INTO patterns (
                    pattern_id, pattern_type, description, confidence,
                    occurrences, first_seen, last_seen, affected_jobs,
                    suggested_action, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pattern_id) DO UPDATE SET
                    confidence = excluded.confidence,
                    occurrences = excluded.occurrences,
                    last_seen = excluded.last_seen,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    pattern.pattern_id,
                    pattern.pattern_type,
                    pattern.description,
                    pattern.confidence,
                    pattern.occurrences,
                    pattern.first_seen.isoformat(),
                    pattern.last_seen.isoformat(),
                    json.dumps(pattern.affected_jobs),
                    pattern.suggested_action,
                    json.dumps(pattern.metadata),
                ),
            )
            await self._db.commit()
        except Exception as e:
            logger.error("pattern_save_error", error=str(e))
    
    async def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Obtém padrões detectados."""
        await self.initialize()
        
        query = """
            SELECT pattern_id, pattern_type, description, confidence,
                   occurrences, first_seen, last_seen, affected_jobs,
                   suggested_action, metadata
            FROM patterns
            WHERE confidence >= ?
        """
        params = [min_confidence]
        
        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)
        
        query += " ORDER BY confidence DESC, occurrences DESC"
        
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        
        return [
            {
                "pattern_id": row[0],
                "pattern_type": row[1],
                "description": row[2],
                "confidence": row[3],
                "occurrences": row[4],
                "first_seen": row[5],
                "last_seen": row[6],
                "affected_jobs": json.loads(row[7]) if row[7] else [],
                "suggested_action": row[8],
                "metadata": json.loads(row[9]) if row[9] else {},
            }
            for row in rows
        ]
    
    # =========================================================================
    # PROBLEM-SOLUTION CORRELATION
    # =========================================================================
    
    async def add_solution(
        self,
        problem_type: str,
        problem_pattern: str,
        solution: str,
    ) -> str:
        """
        Adiciona uma correlação problema-solução.
        
        Args:
            problem_type: Tipo de problema (job_abend, ws_offline, etc.)
            problem_pattern: Padrão que identifica o problema
            solution: Descrição da solução
            
        Returns:
            ID do problema
        """
        await self.initialize()
        
        problem_id = f"prob_{int(time.time())}"
        
        await self._db.execute(
            """
            INSERT INTO problem_solutions (
                problem_id, problem_type, problem_pattern, solution
            ) VALUES (?, ?, ?, ?)
            """,
            (problem_id, problem_type, problem_pattern, solution),
        )
        await self._db.commit()
        
        return problem_id
    
    async def find_solution(
        self,
        problem_type: str,
        error_message: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Busca solução para um problema.
        
        Args:
            problem_type: Tipo de problema
            error_message: Mensagem de erro
            
        Returns:
            Solução encontrada ou None
        """
        await self.initialize()
        
        cursor = await self._db.execute(
            """
            SELECT problem_id, problem_pattern, solution, success_rate,
                   times_applied
            FROM problem_solutions
            WHERE problem_type = ?
            ORDER BY success_rate DESC, times_applied DESC
            """,
            (problem_type,),
        )
        rows = await cursor.fetchall()
        
        for row in rows:
            pattern = row[1]
            # Verifica se o pattern está contido na mensagem de erro
            if pattern.lower() in error_message.lower():
                return {
                    "problem_id": row[0],
                    "pattern": pattern,
                    "solution": row[2],
                    "success_rate": row[3],
                    "times_applied": row[4],
                }
        
        return None
    
    async def record_solution_result(
        self,
        problem_id: str,
        success: bool,
    ) -> None:
        """
        Registra resultado de aplicação de uma solução.
        
        Args:
            problem_id: ID do problema
            success: Se a solução funcionou
        """
        await self.initialize()
        
        if success:
            await self._db.execute(
                """
                UPDATE problem_solutions
                SET times_applied = times_applied + 1,
                    times_successful = times_successful + 1,
                    success_rate = CAST(times_successful + 1 AS REAL) / (times_applied + 1),
                    last_applied = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE problem_id = ?
                """,
                (problem_id,),
            )
        else:
            await self._db.execute(
                """
                UPDATE problem_solutions
                SET times_applied = times_applied + 1,
                    success_rate = CAST(times_successful AS REAL) / (times_applied + 1),
                    last_applied = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE problem_id = ?
                """,
                (problem_id,),
            )
        
        await self._db.commit()
    
    # =========================================================================
    # MAINTENANCE
    # =========================================================================
    
    async def cleanup_old_data(self) -> Dict[str, int]:
        """
        Remove dados antigos baseado nas políticas de retenção.
        
        Returns:
            Contagem de registros removidos por tabela
        """
        await self.initialize()
        
        deleted = {}
        
        # Dados completos: retention_days_full
        cutoff_full = (
            datetime.now() - timedelta(days=self.retention_days_full)
        ).isoformat()
        
        cursor = await self._db.execute(
            "DELETE FROM job_status WHERE timestamp < ?",
            (cutoff_full,),
        )
        deleted["job_status"] = cursor.rowcount
        
        cursor = await self._db.execute(
            "DELETE FROM workstation_status WHERE timestamp < ?",
            (cutoff_full,),
        )
        deleted["workstation_status"] = cursor.rowcount
        
        # Eventos: retention_days_summary
        cutoff_summary = (
            datetime.now() - timedelta(days=self.retention_days_summary)
        ).isoformat()
        
        cursor = await self._db.execute(
            "DELETE FROM events WHERE timestamp < ?",
            (cutoff_summary,),
        )
        deleted["events"] = cursor.rowcount
        
        cursor = await self._db.execute(
            "DELETE FROM snapshots WHERE timestamp < ?",
            (cutoff_summary,),
        )
        deleted["snapshots"] = cursor.rowcount
        
        # Padrões: retention_days_patterns
        cutoff_patterns = (
            datetime.now() - timedelta(days=self.retention_days_patterns)
        ).isoformat()
        
        cursor = await self._db.execute(
            "DELETE FROM patterns WHERE last_seen < ?",
            (cutoff_patterns,),
        )
        deleted["patterns"] = cursor.rowcount
        
        await self._db.commit()
        
        # Vacuum para recuperar espaço
        await self._db.execute("VACUUM")
        
        logger.info("cleanup_completed", deleted=deleted)
        
        return deleted
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do banco de dados."""
        await self.initialize()
        
        stats = {}
        
        for table in ["snapshots", "job_status", "workstation_status", 
                      "events", "patterns", "problem_solutions"]:
            cursor = await self._db.execute(f"SELECT COUNT(*) FROM {table}")
            row = await cursor.fetchone()
            stats[table] = row[0]
        
        # Tamanho do banco
        stats["database_size_mb"] = self.db_path.stat().st_size / (1024 * 1024)
        
        return stats


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_status_store_instance: Optional[TWSStatusStore] = None


def get_status_store() -> Optional[TWSStatusStore]:
    """Retorna instância singleton do status store."""
    return _status_store_instance


async def init_status_store(
    db_path: str = "data/tws_status.db",
    retention_days_full: int = 7,
    retention_days_summary: int = 30,
    retention_days_patterns: int = 90,
) -> TWSStatusStore:
    """Inicializa o status store singleton."""
    global _status_store_instance
    
    _status_store_instance = TWSStatusStore(
        db_path=db_path,
        retention_days_full=retention_days_full,
        retention_days_summary=retention_days_summary,
        retention_days_patterns=retention_days_patterns,
    )
    
    await _status_store_instance.initialize()
    
    return _status_store_instance
