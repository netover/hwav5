"""
TWS Learning Store.

Stores and manages learning data for each TWS instance independently.
Each instance has isolated:
- Job patterns and behaviors
- Failure patterns and resolutions
- Performance baselines
- Operator actions history

v5.2.3.25: Migrated from JSON to SQLite for better performance and reliability.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class JobPattern:
    """Learned pattern for a job."""
    job_name: str
    job_stream: str
    
    # Timing patterns
    avg_duration_seconds: float = 0.0
    min_duration_seconds: float = 0.0
    max_duration_seconds: float = 0.0
    typical_start_hour: int = 0
    
    # Dependency patterns
    common_predecessors: List[str] = field(default_factory=list)
    common_successors: List[str] = field(default_factory=list)
    
    # Failure patterns
    failure_rate: float = 0.0
    common_failure_reasons: List[str] = field(default_factory=list)
    
    # Resolution patterns
    auto_recoverable: bool = False
    typical_resolution_time_minutes: float = 0.0
    
    # Statistics
    execution_count: int = 0
    last_execution: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_name": self.job_name,
            "job_stream": self.job_stream,
            "avg_duration_seconds": self.avg_duration_seconds,
            "min_duration_seconds": self.min_duration_seconds,
            "max_duration_seconds": self.max_duration_seconds,
            "typical_start_hour": self.typical_start_hour,
            "common_predecessors": self.common_predecessors,
            "common_successors": self.common_successors,
            "failure_rate": self.failure_rate,
            "common_failure_reasons": self.common_failure_reasons,
            "auto_recoverable": self.auto_recoverable,
            "typical_resolution_time_minutes": self.typical_resolution_time_minutes,
            "execution_count": self.execution_count,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
        }


@dataclass
class FailureRecord:
    """Record of a job failure."""
    id: str
    job_name: str
    job_stream: str
    timestamp: datetime
    error_code: str
    error_message: str
    
    # Resolution
    resolved: bool = False
    resolution_action: Optional[str] = None
    resolution_time: Optional[datetime] = None
    resolved_by: Optional[str] = None
    
    # Learning
    similar_failures: int = 0
    suggested_action: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_name": self.job_name,
            "job_stream": self.job_stream,
            "timestamp": self.timestamp.isoformat(),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "resolved": self.resolved,
            "resolution_action": self.resolution_action,
            "resolution_time": self.resolution_time.isoformat() if self.resolution_time else None,
            "resolved_by": self.resolved_by,
            "similar_failures": self.similar_failures,
            "suggested_action": self.suggested_action,
        }


class TWSLearningStore:
    """
    Learning data store for a single TWS instance.
    
    Maintains isolated learning data including:
    - Job execution patterns
    - Failure patterns and resolutions
    - Performance baselines
    - Operator action history
    
    v5.2.3.25: Now uses SQLite for persistence instead of JSON files.
    """
    
    def __init__(self, instance_id: str, storage_path: Optional[Path] = None):
        self.instance_id = instance_id
        self.storage_path = storage_path or Path(f"data/learning/{instance_id}")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # SQLite database path
        self._db_path = self.storage_path / "learning.db"
        
        # In-memory data (loaded from SQLite)
        self.job_patterns: Dict[str, JobPattern] = {}
        self.failure_records: List[FailureRecord] = []
        self.failure_resolutions: Dict[str, List[str]] = defaultdict(list)  # error_code -> resolutions
        self.performance_baselines: Dict[str, Dict[str, float]] = {}
        self.operator_actions: List[Dict[str, Any]] = []
        
        # Initialize database and load data
        self._init_db()
        self._migrate_from_json()  # One-time migration from old JSON format
        self._load_data()
    
    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_patterns (
                    pattern_key TEXT PRIMARY KEY,
                    job_name TEXT NOT NULL,
                    job_stream TEXT NOT NULL,
                    pattern_data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failure_resolutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_code TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_error_code ON failure_resolutions(error_code)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failure_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operator_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
        logger.info(f"Initialized SQLite database for {self.instance_id}")

    def _migrate_from_json(self):
        """One-time migration from JSON files to SQLite."""
        # Migrate job patterns
        patterns_file = self.storage_path / "job_patterns.json"
        if patterns_file.exists():
            try:
                with open(patterns_file, 'r') as f:
                    data = json.load(f)
                with sqlite3.connect(str(self._db_path)) as conn:
                    for key, value in data.items():
                        conn.execute(
                            "INSERT OR REPLACE INTO job_patterns (pattern_key, job_name, job_stream, pattern_data, updated_at) VALUES (?, ?, ?, ?, ?)",
                            (key, value.get('job_name', ''), value.get('job_stream', ''), json.dumps(value), datetime.now().isoformat())
                        )
                    conn.commit()
                # Rename old file as backup
                patterns_file.rename(patterns_file.with_suffix('.json.migrated'))
                logger.info(f"Migrated job_patterns.json to SQLite for {self.instance_id}")
            except Exception as e:
                logger.error(f"Error migrating job patterns: {e}")
        
        # Migrate failure resolutions
        resolutions_file = self.storage_path / "failure_resolutions.json"
        if resolutions_file.exists():
            try:
                with open(resolutions_file, 'r') as f:
                    data = json.load(f)
                with sqlite3.connect(str(self._db_path)) as conn:
                    for error_code, resolutions in data.items():
                        for resolution in resolutions:
                            conn.execute(
                                "INSERT INTO failure_resolutions (error_code, resolution, created_at) VALUES (?, ?, ?)",
                                (error_code, resolution, datetime.now().isoformat())
                            )
                    conn.commit()
                resolutions_file.rename(resolutions_file.with_suffix('.json.migrated'))
                logger.info(f"Migrated failure_resolutions.json to SQLite for {self.instance_id}")
            except Exception as e:
                logger.error(f"Error migrating failure resolutions: {e}")
    
    def _load_data(self):
        """Load learning data from SQLite database."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                # Load job patterns
                cursor = conn.execute("SELECT pattern_key, pattern_data FROM job_patterns")
                for row in cursor:
                    key, pattern_json = row
                    try:
                        value = json.loads(pattern_json)
                        if "last_execution" in value and value["last_execution"]:
                            value["last_execution"] = datetime.fromisoformat(value["last_execution"])
                        self.job_patterns[key] = JobPattern(**value)
                    except Exception as e:
                        logger.warning(f"Failed to load pattern {key}: {e}")
                
                # Load failure resolutions
                cursor = conn.execute("SELECT error_code, resolution FROM failure_resolutions")
                for row in cursor:
                    error_code, resolution = row
                    self.failure_resolutions[error_code].append(resolution)
                
            logger.info(f"Loaded {len(self.job_patterns)} job patterns for {self.instance_id}")
        except Exception as e:
            logger.error(f"Error loading data from SQLite: {e}")
    
    def _save_data(self):
        """Save learning data to SQLite database."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                # Save job patterns
                for key, pattern in self.job_patterns.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO job_patterns (pattern_key, job_name, job_stream, pattern_data, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (key, pattern.job_name, pattern.job_stream, json.dumps(pattern.to_dict()), datetime.now().isoformat())
                    )
                
                # Save failure resolutions (only new ones - avoid duplicates)
                existing = set()
                cursor = conn.execute("SELECT error_code, resolution FROM failure_resolutions")
                for row in cursor:
                    existing.add((row[0], row[1]))
                
                for error_code, resolutions in self.failure_resolutions.items():
                    for resolution in resolutions:
                        if (error_code, resolution) not in existing:
                            conn.execute(
                                "INSERT INTO failure_resolutions (error_code, resolution, created_at) VALUES (?, ?, ?)",
                                (error_code, resolution, datetime.now().isoformat())
                            )
                
                conn.commit()
            logger.debug(f"Saved learning data for {self.instance_id}")
        except Exception as e:
            logger.error(f"Error saving data to SQLite: {e}")
    
    def record_job_execution(
        self,
        job_name: str,
        job_stream: str,
        duration_seconds: float,
        success: bool,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Record a job execution and update patterns."""
        key = f"{job_stream}/{job_name}"
        
        if key not in self.job_patterns:
            self.job_patterns[key] = JobPattern(
                job_name=job_name,
                job_stream=job_stream,
            )
        
        pattern = self.job_patterns[key]
        
        # Update timing statistics
        count = pattern.execution_count
        if count == 0:
            pattern.avg_duration_seconds = duration_seconds
            pattern.min_duration_seconds = duration_seconds
            pattern.max_duration_seconds = duration_seconds
        else:
            # Running average
            pattern.avg_duration_seconds = (
                (pattern.avg_duration_seconds * count + duration_seconds) / (count + 1)
            )
            pattern.min_duration_seconds = min(pattern.min_duration_seconds, duration_seconds)
            pattern.max_duration_seconds = max(pattern.max_duration_seconds, duration_seconds)
        
        pattern.execution_count += 1
        pattern.last_execution = datetime.utcnow()
        
        # Update failure rate
        if not success:
            pattern.failure_rate = (
                (pattern.failure_rate * count + 1) / (count + 1)
            )
            if error_message and error_message not in pattern.common_failure_reasons:
                pattern.common_failure_reasons.append(error_message)
                # Keep only top 10 reasons
                pattern.common_failure_reasons = pattern.common_failure_reasons[-10:]
        else:
            pattern.failure_rate = (pattern.failure_rate * count) / (count + 1)
        
        self._save_data()
    
    def record_failure_resolution(
        self,
        error_code: str,
        resolution_action: str,
        job_name: Optional[str] = None,
    ):
        """Record how a failure was resolved."""
        if resolution_action not in self.failure_resolutions[error_code]:
            self.failure_resolutions[error_code].append(resolution_action)
        
        # Update job pattern if job specified
        if job_name:
            for key, pattern in self.job_patterns.items():
                if pattern.job_name == job_name:
                    pattern.auto_recoverable = True
                    break
        
        self._save_data()
    
    def get_suggested_resolution(self, error_code: str) -> Optional[str]:
        """Get suggested resolution for an error code."""
        resolutions = self.failure_resolutions.get(error_code, [])
        if resolutions:
            # Return most common resolution
            return resolutions[-1]
        return None
    
    def get_job_pattern(self, job_name: str, job_stream: str) -> Optional[JobPattern]:
        """Get learned pattern for a job."""
        key = f"{job_stream}/{job_name}"
        return self.job_patterns.get(key)
    
    def get_all_patterns(self) -> List[JobPattern]:
        """Get all job patterns."""
        return list(self.job_patterns.values())
    
    def predict_job_duration(self, job_name: str, job_stream: str) -> Optional[float]:
        """Predict job duration based on learned patterns."""
        pattern = self.get_job_pattern(job_name, job_stream)
        if pattern and pattern.execution_count >= 5:
            return pattern.avg_duration_seconds
        return None
    
    def is_job_likely_to_fail(self, job_name: str, job_stream: str) -> tuple[bool, float]:
        """Check if job is likely to fail based on history."""
        pattern = self.get_job_pattern(job_name, job_stream)
        if pattern and pattern.execution_count >= 10:
            return pattern.failure_rate > 0.2, pattern.failure_rate
        return False, 0.0
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of learning data."""
        total_executions = sum(p.execution_count for p in self.job_patterns.values())
        high_failure_jobs = [
            p.job_name for p in self.job_patterns.values()
            if p.failure_rate > 0.1 and p.execution_count >= 10
        ]
        
        return {
            "instance_id": self.instance_id,
            "total_job_patterns": len(self.job_patterns),
            "total_executions_recorded": total_executions,
            "total_error_codes_known": len(self.failure_resolutions),
            "total_resolutions_learned": sum(len(r) for r in self.failure_resolutions.values()),
            "high_failure_rate_jobs": high_failure_jobs,
            "storage_path": str(self.storage_path),
        }
    
    def export_learning_data(self) -> Dict[str, Any]:
        """Export all learning data."""
        return {
            "instance_id": self.instance_id,
            "exported_at": datetime.utcnow().isoformat(),
            "job_patterns": {k: v.to_dict() for k, v in self.job_patterns.items()},
            "failure_resolutions": dict(self.failure_resolutions),
        }
    
    def import_learning_data(self, data: Dict[str, Any]):
        """Import learning data."""
        if "job_patterns" in data:
            for key, value in data["job_patterns"].items():
                if "last_execution" in value and value["last_execution"]:
                    value["last_execution"] = datetime.fromisoformat(value["last_execution"])
                self.job_patterns[key] = JobPattern(**value)
        
        if "failure_resolutions" in data:
            for error_code, resolutions in data["failure_resolutions"].items():
                self.failure_resolutions[error_code].extend(resolutions)
        
        self._save_data()
        logger.info(f"Imported learning data for {self.instance_id}")
    
    def clear_learning_data(self):
        """Clear all learning data (use with caution!)."""
        self.job_patterns.clear()
        self.failure_resolutions.clear()
        self.failure_records.clear()
        self.operator_actions.clear()
        
        # Remove storage files
        for file in self.storage_path.glob("*.json"):
            file.unlink()
        
        logger.warning(f"Cleared all learning data for {self.instance_id}")
