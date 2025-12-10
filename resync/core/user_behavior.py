"""
Advanced User Behavior Analysis for Threat Detection.

This module provides intelligent behavioral analysis including:
- User profiling and behavior pattern recognition
- Session analysis and anomaly detection
- Bot detection and automated attack identification
- Risk scoring based on behavioral patterns
- Temporal analysis of user activities
- Machine learning-based user classification
- SQLite persistence for user profiles (v5.2.3.25)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiosqlite

from resync.core.structured_logger import get_logger

logger = get_logger(__name__)


@dataclass
class UserActivity:
    """Represents a user activity event."""

    user_id: str
    timestamp: float = field(default_factory=time.time)
    action: str = ""  # login, logout, api_call, etc.
    endpoint: str = ""
    method: str = "GET"
    status_code: int = 200
    response_time: float = 0.0
    ip_address: str = ""
    user_agent: str = ""
    session_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def hour_of_day(self) -> int:
        """Get hour of day (0-23)."""
        return datetime.fromtimestamp(self.timestamp).hour

    @property
    def day_of_week(self) -> int:
        """Get day of week (0=Monday, 6=Sunday)."""
        return datetime.fromtimestamp(self.timestamp).weekday()

    @property
    def is_business_hours(self) -> bool:
        """Check if activity occurred during business hours."""
        hour = self.hour_of_day
        return 9 <= hour <= 17  # 9 AM to 5 PM

    @property
    def activity_hash(self) -> str:
        """Generate hash for activity deduplication."""
        # Using MD5 for deduplication only, not for security purposes
        key = f"{self.user_id}_{self.action}_{self.endpoint}_{int(self.timestamp // 3600)}"
        return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()


@dataclass
class UserProfile:
    """Profile of user behavior patterns."""

    user_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    # Activity patterns
    total_activities: int = 0
    unique_endpoints: Set[str] = field(default_factory=set)
    activity_frequency: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Temporal patterns
    hourly_pattern: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    daily_pattern: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    session_durations: List[float] = field(default_factory=list)

    # Behavioral metrics
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    unique_ips: Set[str] = field(default_factory=set)
    unique_user_agents: Set[str] = field(default_factory=set)

    # Risk indicators
    suspicious_patterns: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    last_risk_update: float = field(default_factory=time.time)

    def update_activity(self, activity: UserActivity) -> None:
        """Update profile with new activity."""
        self.last_activity = activity.timestamp
        self.total_activities += 1

        # Update patterns
        self.unique_endpoints.add(activity.endpoint)
        self.activity_frequency[activity.action] += 1
        self.hourly_pattern[activity.hour_of_day] += 1
        self.daily_pattern[activity.day_of_week] += 1

        # Update network info
        if activity.ip_address:
            self.unique_ips.add(activity.ip_address)
        if activity.user_agent:
            self.unique_user_agents.add(activity.user_agent)

        # Update metrics
        self._update_metrics(activity)

    def _update_metrics(self, activity: UserActivity) -> None:
        """Update behavioral metrics."""
        # Update average response time
        if self.total_activities == 1:
            self.avg_response_time = activity.response_time
        else:
            self.avg_response_time = (
                (self.avg_response_time * (self.total_activities - 1))
                + activity.response_time
            ) / self.total_activities

        # Update error rate
        is_error = activity.status_code >= 400
        total_errors = int(self.error_rate * (self.total_activities - 1))
        if is_error:
            total_errors += 1
        self.error_rate = total_errors / self.total_activities

    def calculate_risk_score(self) -> float:
        """Calculate behavioral risk score (0.0 to 1.0)."""
        score = 0.0
        factors = []

        # Factor 1: Unusual timing (weight: 0.3)
        current_hour = datetime.now().hour
        expected_activities = self.hourly_pattern.get(current_hour, 0)
        avg_activities = sum(self.hourly_pattern.values()) / max(
            1, len(self.hourly_pattern)
        )

        if avg_activities > 0:
            timing_anomaly = abs(expected_activities - avg_activities) / avg_activities
            timing_score = min(1.0, timing_anomaly * 2)  # Scale up anomalies
            score += 0.3 * timing_score
            factors.append(f"timing_anomaly:{timing_score:.2f}")

        # Factor 2: High error rate (weight: 0.25)
        error_score = min(1.0, self.error_rate * 4)  # 25% error rate = max score
        score += 0.25 * error_score
        factors.append(f"error_rate:{error_score:.2f}")

        # Factor 3: Multiple IPs/User-Agents (weight: 0.2)
        ip_score = min(1.0, len(self.unique_ips) / 5)  # 5+ IPs = suspicious
        ua_score = min(1.0, len(self.unique_user_agents) / 3)  # 3+ UAs = suspicious
        network_score = (ip_score + ua_score) / 2
        score += 0.2 * network_score
        factors.append(f"network_diversity:{network_score:.2f}")

        # Factor 4: Session anomalies (weight: 0.15)
        if self.session_durations:
            avg_session = sum(self.session_durations) / len(self.session_durations)
            # Very short sessions might indicate automated access
            if avg_session < 60:  # Less than 1 minute
                session_score = 0.8
            elif avg_session < 300:  # Less than 5 minutes
                session_score = 0.4
            else:
                session_score = 0.0
            score += 0.15 * session_score
            factors.append(f"session_anomaly:{session_score:.2f}")

        # Factor 5: Activity burst (weight: 0.1)
        # Check for sudden activity spikes
        recent_activities = sum(
            count
            for hour, count in self.hourly_pattern.items()
            if abs(hour - current_hour) <= 1
        )
        total_activities = sum(self.hourly_pattern.values())
        burst_ratio = recent_activities / max(1, total_activities)

        if burst_ratio > 0.5:  # More than 50% of activity in recent hours
            burst_score = min(1.0, (burst_ratio - 0.5) * 4)
            score += 0.1 * burst_score
            factors.append(f"activity_burst:{burst_score:.2f}")

        # Update suspicious patterns
        if score > 0.6:
            self.suspicious_patterns.append(
                f"high_risk_score_{score:.2f}_at_{time.time()}"
            )
            # Keep only last 10 patterns
            self.suspicious_patterns = self.suspicious_patterns[-10:]

        self.risk_score = min(1.0, score)
        self.last_risk_update = time.time()

        logger.debug(
            f"Risk score calculated for user {self.user_id}: {score:.3f}",
            factors=factors,
        )

        return self.risk_score

    def get_behavior_summary(self) -> Dict[str, Any]:
        """Get comprehensive behavior summary."""
        return {
            "user_id": self.user_id,
            "profile_age_days": (time.time() - self.created_at) / 86400,
            "total_activities": self.total_activities,
            "unique_endpoints": len(self.unique_endpoints),
            "unique_ips": len(self.unique_ips),
            "unique_user_agents": len(self.unique_user_agents),
            "avg_response_time": self.avg_response_time,
            "error_rate": self.error_rate,
            "risk_score": self.risk_score,
            "top_activities": sorted(
                self.activity_frequency.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "peak_hours": sorted(
                self.hourly_pattern.items(), key=lambda x: x[1], reverse=True
            )[:3],
            "suspicious_patterns": self.suspicious_patterns[-3:],  # Last 3
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to dictionary for persistence."""
        return {
            "user_id": self.user_id,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "total_activities": self.total_activities,
            "unique_endpoints": list(self.unique_endpoints),
            "activity_frequency": dict(self.activity_frequency),
            "hourly_pattern": {str(k): v for k, v in self.hourly_pattern.items()},
            "daily_pattern": {str(k): v for k, v in self.daily_pattern.items()},
            "session_durations": self.session_durations[-100:],  # Keep last 100
            "avg_response_time": self.avg_response_time,
            "error_rate": self.error_rate,
            "unique_ips": list(self.unique_ips),
            "unique_user_agents": list(self.unique_user_agents),
            "suspicious_patterns": self.suspicious_patterns[-10:],
            "risk_score": self.risk_score,
            "last_risk_update": self.last_risk_update,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Deserialize profile from dictionary."""
        profile = cls(user_id=data["user_id"])
        profile.created_at = data.get("created_at", time.time())
        profile.last_activity = data.get("last_activity", time.time())
        profile.total_activities = data.get("total_activities", 0)
        profile.unique_endpoints = set(data.get("unique_endpoints", []))
        profile.activity_frequency = defaultdict(int, data.get("activity_frequency", {}))
        profile.hourly_pattern = defaultdict(int, {int(k): v for k, v in data.get("hourly_pattern", {}).items()})
        profile.daily_pattern = defaultdict(int, {int(k): v for k, v in data.get("daily_pattern", {}).items()})
        profile.session_durations = data.get("session_durations", [])
        profile.avg_response_time = data.get("avg_response_time", 0.0)
        profile.error_rate = data.get("error_rate", 0.0)
        profile.unique_ips = set(data.get("unique_ips", []))
        profile.unique_user_agents = set(data.get("unique_user_agents", []))
        profile.suspicious_patterns = data.get("suspicious_patterns", [])
        profile.risk_score = data.get("risk_score", 0.0)
        profile.last_risk_update = data.get("last_risk_update", time.time())
        return profile


@dataclass
class SessionAnalysis:
    """Analysis of user session behavior."""

    session_id: str
    user_id: str
    start_time: float
    last_activity: float = 0.0
    activities: List[UserActivity] = field(default_factory=list)
    is_active: bool = True

    @property
    def duration(self) -> float:
        """Get session duration in seconds."""
        if self.last_activity > 0:
            return self.last_activity - self.start_time
        return time.time() - self.start_time

    @property
    def activity_count(self) -> int:
        """Get number of activities in session."""
        return len(self.activities)

    @property
    def avg_time_between_activities(self) -> float:
        """Calculate average time between activities."""
        if len(self.activities) < 2:
            return 0.0

        timestamps = sorted([a.timestamp for a in self.activities])
        intervals = [
            timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)
        ]
        return sum(intervals) / len(intervals)

    def analyze_bot_probability(self) -> float:
        """
        Analyze probability that this session is from a bot.

        Returns:
            Probability score (0.0 to 1.0)
        """
        score = 0.0

        # Factor 1: Activity frequency (bots often have regular patterns)
        if len(self.activities) > 10:
            intervals = []
            for i in range(1, len(self.activities)):
                interval = (
                    self.activities[i].timestamp - self.activities[i - 1].timestamp
                )
                intervals.append(interval)

            if intervals:
                # Calculate coefficient of variation (lower = more regular = more bot-like)
                mean_interval = sum(intervals) / len(intervals)
                variance = sum((x - mean_interval) ** 2 for x in intervals) / len(
                    intervals
                )
                std_dev = variance**0.5
                cv = std_dev / max(0.001, mean_interval)  # Coefficient of variation

                # Low CV indicates very regular intervals (bot-like)
                if cv < 0.3:  # Very regular
                    score += 0.4
                elif cv < 0.6:  # Somewhat regular
                    score += 0.2

        # Factor 2: Activity rate (bots often have high activity rates)
        duration_hours = self.duration / 3600
        if duration_hours > 0:
            activity_rate = len(self.activities) / duration_hours
            if activity_rate > 60:  # More than 1 activity per minute
                score += 0.3
            elif activity_rate > 30:  # More than 1 activity per 2 minutes
                score += 0.15

        # Factor 3: Endpoint diversity (bots often hit few endpoints repeatedly)
        unique_endpoints = len(set(a.endpoint for a in self.activities))
        endpoint_diversity = unique_endpoints / max(1, len(self.activities))

        if endpoint_diversity < 0.1:  # Less than 10% unique endpoints
            score += 0.3

        return min(1.0, score)


@dataclass
class BehavioralAnalysisConfig:
    """Configuration for behavioral analysis."""

    # Profile management
    max_profiles: int = 10000
    profile_ttl_days: int = 90
    cleanup_interval_hours: int = 24

    # Risk assessment
    high_risk_threshold: float = 0.8
    medium_risk_threshold: float = 0.6
    low_risk_threshold: float = 0.4

    # Bot detection
    bot_probability_threshold: float = 0.7
    session_timeout_minutes: int = 30

    # Alerting
    enable_real_time_alerts: bool = True
    alert_cooldown_minutes: int = 15

    # Performance
    max_session_history: int = 1000
    activity_batch_size: int = 100


class BehavioralAnalysisEngine:
    """
    Advanced behavioral analysis engine for user threat detection.

    Features:
    - Real-time user profiling and risk assessment
    - Session analysis and bot detection
    - Temporal pattern recognition
    - Automated alerting and risk scoring
    - Performance optimized for high-throughput
    - SQLite persistence for user profiles (v5.2.3.25)
    """

    def __init__(
        self,
        config: Optional[BehavioralAnalysisConfig] = None,
        db_path: str = "data/user_behavior.db",
    ):
        self.config = config or BehavioralAnalysisConfig()
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # User profiles
        self.user_profiles: Dict[str, UserProfile] = {}
        self.profile_access_times: Dict[str, float] = {}

        # Session tracking
        self.active_sessions: Dict[str, SessionAnalysis] = {}
        self.session_history: deque = deque(maxlen=self.config.max_session_history)

        # Risk monitoring
        self.high_risk_users: Set[str] = set()
        self.recent_alerts: Dict[str, float] = {}  # user_id -> last_alert_time

        # Statistics
        self.total_activities_processed = 0
        self.bots_detected = 0
        self.alerts_generated = 0

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._analysis_task: Optional[asyncio.Task] = None
        self._persistence_task: Optional[asyncio.Task] = None
        self._running = False

        # Thread safety
        self._lock = asyncio.Lock()

    async def _init_db(self) -> None:
        """Initialize SQLite database for profile persistence."""
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    profile_data TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS session_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    duration REAL NOT NULL,
                    activity_count INTEGER NOT NULL,
                    bot_probability REAL DEFAULT 0.0,
                    created_at REAL NOT NULL
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_user ON session_history(user_id)
            """)
            await db.commit()
        logger.info("User behavior database initialized", db_path=str(self._db_path))

    async def _load_profiles(self) -> None:
        """Load user profiles from SQLite database."""
        try:
            async with aiosqlite.connect(str(self._db_path)) as db:
                async with db.execute(
                    "SELECT user_id, profile_data FROM user_profiles"
                ) as cursor:
                    async for row in cursor:
                        user_id, profile_json = row
                        try:
                            data = json.loads(profile_json)
                            self.user_profiles[user_id] = UserProfile.from_dict(data)
                        except Exception as e:
                            logger.warning(f"Failed to load profile {user_id}: {e}")
            logger.info(
                "Loaded user profiles from database",
                count=len(self.user_profiles),
            )
        except Exception as e:
            logger.error(f"Failed to load profiles from database: {e}")

    async def _save_profiles(self) -> None:
        """Save user profiles to SQLite database."""
        if not self.user_profiles:
            return
        
        try:
            async with aiosqlite.connect(str(self._db_path)) as db:
                for user_id, profile in self.user_profiles.items():
                    profile_json = json.dumps(profile.to_dict())
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO user_profiles (user_id, profile_data, updated_at)
                        VALUES (?, ?, ?)
                        """,
                        (user_id, profile_json, time.time()),
                    )
                await db.commit()
            logger.debug(
                "Saved user profiles to database",
                count=len(self.user_profiles),
            )
        except Exception as e:
            logger.error(f"Failed to save profiles to database: {e}")

    async def _save_session_to_db(self, session: SessionAnalysis) -> None:
        """Save completed session to database."""
        try:
            async with aiosqlite.connect(str(self._db_path)) as db:
                await db.execute(
                    """
                    INSERT INTO session_history 
                    (session_id, user_id, start_time, duration, activity_count, bot_probability, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.session_id,
                        session.user_id,
                        session.start_time,
                        session.duration,
                        session.activity_count,
                        session.analyze_bot_probability(),
                        time.time(),
                    ),
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save session to database: {e}")

    async def _persistence_loop(self) -> None:
        """Background task to periodically save profiles."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Save every 5 minutes
                await self._save_profiles()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in persistence loop: {e}")

    async def start(self) -> None:
        """Start the behavioral analysis engine."""
        if self._running:
            return

        # Initialize database and load existing profiles
        await self._init_db()
        await self._load_profiles()

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._analysis_task = asyncio.create_task(self._analysis_loop())
        self._persistence_task = asyncio.create_task(self._persistence_loop())

        logger.info(
            "Behavioral analysis engine started",
            loaded_profiles=len(self.user_profiles),
        )

    async def stop(self) -> None:
        """Stop the behavioral analysis engine."""
        if not self._running:
            return

        self._running = False

        # Save profiles before stopping
        await self._save_profiles()

        for task in [self._cleanup_task, self._analysis_task, self._persistence_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info(
            "Behavioral analysis engine stopped",
            saved_profiles=len(self.user_profiles),
        )

    async def analyze_activity(
        self, activity: UserActivity, generate_alerts: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze user activity for behavioral anomalies.

        Args:
            activity: User activity to analyze
            generate_alerts: Whether to generate alerts for suspicious activity

        Returns:
            Analysis results including risk scores and alerts
        """
        async with self._lock:
            self.total_activities_processed += 1

            # Update user profile
            await self._update_user_profile(activity)

            # Update session analysis
            await self._update_session_analysis(activity)

            # Perform comprehensive analysis
            analysis_result = await self._perform_comprehensive_analysis(activity)

            # Generate alerts if requested
            if generate_alerts:
                await self._generate_alerts(activity, analysis_result)

            return analysis_result

    async def _update_user_profile(self, activity: UserActivity) -> None:
        """Update or create user profile with new activity."""
        user_id = activity.user_id

        # Get or create profile
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserProfile(user_id=user_id)

        profile = self.user_profiles[user_id]
        profile.update_activity(activity)
        self.profile_access_times[user_id] = time.time()

        # Recalculate risk score periodically
        if time.time() - profile.last_risk_update > 300:  # Every 5 minutes
            profile.calculate_risk_score()

        # Check if user became high risk
        if profile.risk_score >= self.config.high_risk_threshold:
            self.high_risk_users.add(user_id)
        elif profile.risk_score < self.config.medium_risk_threshold:
            self.high_risk_users.discard(user_id)

    async def _update_session_analysis(self, activity: UserActivity) -> None:
        """Update session analysis with new activity."""
        session_id = activity.session_id
        if not session_id:
            return

        # Get or create session
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = SessionAnalysis(
                session_id=session_id,
                user_id=activity.user_id,
                start_time=activity.timestamp,
            )

        session = self.active_sessions[session_id]
        session.activities.append(activity)
        session.last_activity = activity.timestamp

        # Check for session timeout
        if time.time() - session.last_activity > (
            self.config.session_timeout_minutes * 60
        ):
            # Move to history
            self.session_history.append(session)
            del self.active_sessions[session_id]

    async def _perform_comprehensive_analysis(
        self, activity: UserActivity
    ) -> Dict[str, Any]:
        """Perform comprehensive behavioral analysis."""
        user_id = activity.user_id
        profile = self.user_profiles.get(user_id)

        if not profile:
            return {"error": "User profile not found"}

        # Basic risk assessment
        risk_score = profile.calculate_risk_score()
        risk_level = self._calculate_risk_level(risk_score)

        # Session analysis
        session_risk = 0.0
        bot_probability = 0.0

        session = self.active_sessions.get(activity.session_id)
        if session:
            bot_probability = session.analyze_bot_probability()
            if bot_probability > self.config.bot_probability_threshold:
                session_risk = 0.8
                self.bots_detected += 1

        # Temporal analysis
        temporal_anomalies = self._analyze_temporal_patterns(activity, profile)

        # Network analysis
        network_anomalies = self._analyze_network_patterns(activity, profile)

        # Combined analysis
        overall_risk = max(risk_score, session_risk)
        is_suspicious = (
            overall_risk >= self.config.medium_risk_threshold
            or bot_probability > self.config.bot_probability_threshold
            or len(temporal_anomalies) > 0
            or len(network_anomalies) > 0
        )

        return {
            "user_id": user_id,
            "risk_score": overall_risk,
            "risk_level": risk_level,
            "is_suspicious": is_suspicious,
            "bot_probability": bot_probability,
            "is_bot": bot_probability > self.config.bot_probability_threshold,
            "temporal_anomalies": temporal_anomalies,
            "network_anomalies": network_anomalies,
            "profile_summary": profile.get_behavior_summary(),
            "session_info": {
                "session_id": activity.session_id,
                "active_sessions": len(self.active_sessions),
                "session_duration": session.duration if session else 0,
                "activities_in_session": session.activity_count if session else 0,
            },
        }

    def _analyze_temporal_patterns(
        self, activity: UserActivity, profile: UserProfile
    ) -> List[str]:
        """Analyze temporal patterns for anomalies."""
        anomalies = []

        # Check unusual hour
        current_hour = activity.hour_of_day
        expected_activities = profile.hourly_pattern.get(current_hour, 0)
        avg_activities = sum(profile.hourly_pattern.values()) / max(
            1, len(profile.hourly_pattern)
        )

        if avg_activities > 0 and expected_activities < avg_activities * 0.1:
            anomalies.append(f"unusual_hour_{current_hour}")

        # Check unusual day
        current_day = activity.day_of_week
        if profile.daily_pattern:
            max_day = max(
                profile.daily_pattern.keys(), key=lambda k: profile.daily_pattern[k]
            )
            if (
                current_day != max_day
                and profile.daily_pattern.get(current_day, 0)
                < profile.daily_pattern[max_day] * 0.2
            ):
                anomalies.append(f"unusual_day_{current_day}")

        # Check business hours violation
        if not activity.is_business_hours and profile.total_activities > 10:
            # Calculate percentage of activities outside business hours
            out_of_hours = sum(
                count
                for hour, count in profile.hourly_pattern.items()
                if not (9 <= hour <= 17)
            )
            total_activities = sum(profile.hourly_pattern.values())

            if total_activities > 0 and (out_of_hours / total_activities) < 0.3:
                anomalies.append("outside_business_hours")

        return anomalies

    def _analyze_network_patterns(
        self, activity: UserActivity, profile: UserProfile
    ) -> List[str]:
        """Analyze network patterns for anomalies."""
        anomalies = []

        # Check new IP
        if activity.ip_address and activity.ip_address not in profile.unique_ips:
            if len(profile.unique_ips) >= 3:  # Already has multiple IPs
                anomalies.append("new_ip_address")

        # Check new User-Agent
        if (
            activity.user_agent
            and activity.user_agent not in profile.unique_user_agents
        ):
            if len(profile.unique_user_agents) >= 2:  # Already has multiple UAs
                anomalies.append("new_user_agent")

        # Check rapid IP changes
        if len(profile.unique_ips) > 5:
            anomalies.append("multiple_ip_addresses")

        return anomalies

    def _calculate_risk_level(self, risk_score: float) -> str:
        """Calculate risk level from score."""
        if risk_score >= self.config.high_risk_threshold:
            return "high"
        elif risk_score >= self.config.medium_risk_threshold:
            return "medium"
        elif risk_score >= self.config.low_risk_threshold:
            return "low"
        else:
            return "minimal"

    async def _generate_alerts(
        self, activity: UserActivity, analysis_result: Dict[str, Any]
    ) -> None:
        """Generate alerts for suspicious activities."""
        user_id = activity.user_id

        # Check cooldown
        last_alert = self.recent_alerts.get(user_id, 0)
        if time.time() - last_alert < (self.config.alert_cooldown_minutes * 60):
            return

        alerts = []

        # High risk user alert
        if analysis_result["risk_level"] == "high":
            alerts.append(
                {
                    "type": "high_risk_user",
                    "severity": "high",
                    "message": f"User {user_id} showing high risk behavior (score: {analysis_result['risk_score']:.2f})",
                    "details": {
                        "risk_score": analysis_result["risk_score"],
                        "temporal_anomalies": analysis_result["temporal_anomalies"],
                        "network_anomalies": analysis_result["network_anomalies"],
                    },
                }
            )

        # Bot detection alert
        if analysis_result["is_bot"]:
            alerts.append(
                {
                    "type": "bot_detected",
                    "severity": "high",
                    "message": f"Bot-like behavior detected for user {user_id} (probability: {analysis_result['bot_probability']:.2f})",
                    "details": analysis_result["session_info"],
                }
            )

        # Suspicious pattern alerts
        if analysis_result["temporal_anomalies"]:
            alerts.append(
                {
                    "type": "temporal_anomaly",
                    "severity": "medium",
                    "message": f"Temporal anomalies detected for user {user_id}",
                    "details": {"anomalies": analysis_result["temporal_anomalies"]},
                }
            )

        if analysis_result["network_anomalies"]:
            alerts.append(
                {
                    "type": "network_anomaly",
                    "severity": "medium",
                    "message": f"Network anomalies detected for user {user_id}",
                    "details": {"anomalies": analysis_result["network_anomalies"]},
                }
            )

        # Send alerts
        for alert in alerts:
            await self._send_alert(alert, activity)
            self.alerts_generated += 1

        if alerts:
            self.recent_alerts[user_id] = time.time()

    async def _send_alert(self, alert: Dict[str, Any], activity: UserActivity) -> None:
        """Send alert to monitoring systems."""
        # Log alert
        logger.warning(
            "behavioral_alert",
            alert_type=alert["type"],
            severity=alert["severity"],
            user_id=activity.user_id,
            message=alert["message"],
            details=alert["details"],
        )

        # Here you could integrate with external systems:
        # - Send to SIEM
        # - Send email alerts
        # - Trigger automated responses
        # - Send to Slack/PagerDuty

    async def _cleanup_loop(self) -> None:
        """Background cleanup of old profiles and sessions."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_hours * 3600)

                async with self._lock:
                    await self._cleanup_old_profiles()
                    await self._cleanup_expired_sessions()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    async def _cleanup_old_profiles(self) -> None:
        """Clean up old user profiles."""
        current_time = time.time()
        ttl_seconds = self.config.profile_ttl_days * 24 * 3600

        to_remove = []
        for user_id, last_access in self.profile_access_times.items():
            if current_time - last_access > ttl_seconds:
                to_remove.append(user_id)

        for user_id in to_remove:
            if user_id in self.user_profiles:
                del self.user_profiles[user_id]
            if user_id in self.profile_access_times:
                del self.profile_access_times[user_id]
            self.high_risk_users.discard(user_id)

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old user profiles")

    async def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        current_time = time.time()
        timeout_seconds = self.config.session_timeout_minutes * 60

        expired_sessions = []
        for session_id, session in self.active_sessions.items():
            if current_time - session.last_activity > timeout_seconds:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            session = self.active_sessions[session_id]
            self.session_history.append(session)
            del self.active_sessions[session_id]

        if expired_sessions:
            logger.debug(f"Moved {len(expired_sessions)} sessions to history")

    async def _analysis_loop(self) -> None:
        """Background analysis loop for periodic checks."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes

                # Analyze high-risk users
                await self._analyze_high_risk_users()

                # Update risk scores for active users
                await self._update_risk_scores()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Analysis loop error: {e}")

    async def _analyze_high_risk_users(self) -> None:
        """Perform deeper analysis on high-risk users."""
        async with self._lock:
            for user_id in list(self.high_risk_users):
                if user_id in self.user_profiles:
                    profile = self.user_profiles[user_id]
                    current_risk = profile.calculate_risk_score()

                    # If risk has decreased, remove from high-risk list
                    if current_risk < self.config.medium_risk_threshold:
                        self.high_risk_users.discard(user_id)
                        logger.info(
                            f"User {user_id} risk level decreased, removed from high-risk monitoring"
                        )

    async def _update_risk_scores(self) -> None:
        """Update risk scores for active users."""
        async with self._lock:
            # Update risk scores for recently active users
            current_time = time.time()
            recently_active = [
                user_id
                for user_id, last_access in self.profile_access_times.items()
                if current_time - last_access < 3600  # Active in last hour
            ]

            for user_id in recently_active[:50]:  # Limit to avoid overload
                if user_id in self.user_profiles:
                    self.user_profiles[user_id].calculate_risk_score()

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive behavioral analysis statistics."""
        return {
            "performance": {
                "total_activities_processed": self.total_activities_processed,
                "active_user_profiles": len(self.user_profiles),
                "active_sessions": len(self.active_sessions),
                "high_risk_users": len(self.high_risk_users),
                "bots_detected": self.bots_detected,
                "alerts_generated": self.alerts_generated,
            },
            "risk_distribution": self._calculate_risk_distribution(),
            "session_stats": {
                "avg_session_duration": self._calculate_avg_session_duration(),
                "total_sessions_history": len(self.session_history),
            },
            "temporal_patterns": self._analyze_global_temporal_patterns(),
            "configuration": {
                "max_profiles": self.config.max_profiles,
                "profile_ttl_days": self.config.profile_ttl_days,
                "bot_probability_threshold": self.config.bot_probability_threshold,
            },
        }

    def _calculate_risk_distribution(self) -> Dict[str, int]:
        """Calculate distribution of user risk levels."""
        distribution = {"high": 0, "medium": 0, "low": 0, "minimal": 0}

        for profile in self.user_profiles.values():
            risk_level = self._calculate_risk_level(profile.risk_score)
            distribution[risk_level] += 1

        return distribution

    def _calculate_avg_session_duration(self) -> float:
        """Calculate average session duration."""
        if not self.session_history:
            return 0.0

        total_duration = sum(session.duration for session in self.session_history)
        return total_duration / len(self.session_history)

    def _analyze_global_temporal_patterns(self) -> Dict[str, Any]:
        """Analyze global temporal patterns across all users."""
        hourly_activity = defaultdict(int)
        daily_activity = defaultdict(int)

        for profile in self.user_profiles.values():
            for hour, count in profile.hourly_pattern.items():
                hourly_activity[hour] += count
            for day, count in profile.daily_pattern.items():
                daily_activity[day] += count

        peak_hour = max(hourly_activity.items(), key=lambda x: x[1], default=(0, 0))[0]
        peak_day = max(daily_activity.items(), key=lambda x: x[1], default=(0, 0))[0]

        return {
            "peak_hour": peak_hour,
            "peak_day": peak_day,
            "total_activities_by_hour": dict(hourly_activity),
            "total_activities_by_day": dict(daily_activity),
        }

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed user profile and analysis."""
        if user_id not in self.user_profiles:
            return None

        profile = self.user_profiles[user_id]
        return {
            "profile": profile.get_behavior_summary(),
            "risk_assessment": {
                "current_risk_score": profile.risk_score,
                "risk_level": self._calculate_risk_level(profile.risk_score),
                "is_high_risk": user_id in self.high_risk_users,
                "last_risk_update": profile.last_risk_update,
            },
            "session_analysis": self._get_user_session_analysis(user_id),
        }

    def _get_user_session_analysis(self, user_id: str) -> Dict[str, Any]:
        """Get session analysis for a specific user."""
        user_sessions = [
            session
            for session in self.active_sessions.values()
            if session.user_id == user_id
        ]

        if not user_sessions:
            return {"active_sessions": 0, "analysis": {}}

        # Analyze user's sessions
        total_activities = sum(len(session.activities) for session in user_sessions)
        avg_duration = sum(session.duration for session in user_sessions) / len(
            user_sessions
        )
        bot_probabilities = [
            session.analyze_bot_probability() for session in user_sessions
        ]
        avg_bot_probability = sum(bot_probabilities) / len(bot_probabilities)

        return {
            "active_sessions": len(user_sessions),
            "total_activities": total_activities,
            "avg_session_duration": avg_duration,
            "avg_bot_probability": avg_bot_probability,
            "max_bot_probability": max(bot_probabilities) if bot_probabilities else 0,
        }


# Global behavioral analysis engine instance
behavioral_analysis_engine = BehavioralAnalysisEngine()


async def get_behavioral_analysis_engine() -> BehavioralAnalysisEngine:
    """Get the global behavioral analysis engine instance."""
    if not behavioral_analysis_engine._running:
        await behavioral_analysis_engine.start()
    return behavioral_analysis_engine
