"""
TWS Specialist Tools.

Custom tools for each specialist agent to interact with TWS data,
logs, graphs, and documentation.

Author: Resync Team
Version: 5.2.3.29
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable

import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# TOOL DECORATOR (Agno-compatible)
# ============================================================================

def tool(func: Callable) -> Callable:
    """
    Decorator to mark a function as a tool for Agno agents.
    
    Compatible with both Agno's @tool decorator and standalone usage.
    """
    func._is_tool = True
    func._tool_name = func.__name__
    func._tool_description = func.__doc__ or ""
    return func


# ============================================================================
# JOB ANALYST TOOLS
# ============================================================================

class JobLogTool:
    """
    Tool for analyzing TWS job logs and execution history.
    
    Capabilities:
    - Retrieve job execution logs
    - Parse return codes and ABEND codes
    - Identify error patterns
    - Get execution statistics
    """
    
    # Common TWS/z/OS ABEND codes with descriptions
    ABEND_CODES: Dict[str, str] = {
        "S0C1": "Operation exception - invalid instruction",
        "S0C4": "Protection exception - invalid memory access",
        "S0C7": "Data exception - invalid decimal/numeric data",
        "S013": "I/O error - file not found or access denied",
        "S106": "Module not found",
        "S222": "Job cancelled by operator",
        "S322": "Job timed out - CPU or wait time exceeded",
        "S522": "Job wait time exceeded",
        "S806": "Module load failure",
        "S878": "Virtual storage exhausted",
        "S913": "Security violation - RACF/ACF2 denied",
        "U0016": "User abend - application error",
        "U1000": "User abend - custom application code",
        "U4038": "CICS transaction abend",
    }
    
    # Common return code meanings
    RETURN_CODES: Dict[int, str] = {
        0: "Successful completion",
        4: "Warning - minor issues",
        8: "Error - processing problems",
        12: "Severe error - partial failure",
        16: "Critical error - job failed",
        20: "Fatal error - immediate termination",
    }
    
    def __init__(self, tws_client: Optional[Any] = None):
        """Initialize with optional TWS client."""
        self.tws_client = tws_client
    
    @tool
    def get_job_log(
        self,
        job_name: str,
        run_date: Optional[str] = None,
        max_lines: int = 100,
    ) -> Dict[str, Any]:
        """
        Retrieve execution log for a specific job.
        
        Args:
            job_name: Name of the job (e.g., BATCH001, DAILY_BACKUP)
            run_date: Date to retrieve (YYYY-MM-DD), defaults to today
            max_lines: Maximum log lines to return
            
        Returns:
            Job log details including status, return code, and log content
        """
        logger.info("get_job_log", job_name=job_name, run_date=run_date)
        
        # Mock implementation - replace with actual TWS API call
        return {
            "job_name": job_name,
            "run_date": run_date or datetime.now().strftime("%Y-%m-%d"),
            "status": "ABEND",
            "return_code": 16,
            "abend_code": "S0C7",
            "start_time": "08:30:00",
            "end_time": "08:35:22",
            "duration_seconds": 322,
            "workstation": "TWS_AGENT1",
            "log_excerpt": [
                "08:30:00 Job BATCH001 started on TWS_AGENT1",
                "08:32:15 Step STEP010 completed RC=0",
                "08:34:50 Step STEP020 processing file INPUT.DATA",
                "08:35:22 ABEND S0C7 in STEP030 - Data exception",
            ],
            "error_details": "Data exception at offset 0x1A2F in module PROC001",
        }
    
    @tool
    def analyze_return_code(self, return_code: int) -> Dict[str, Any]:
        """
        Analyze a return code and provide interpretation.
        
        Args:
            return_code: The job return code (0-999)
            
        Returns:
            Analysis with severity, description, and recommendations
        """
        # Determine severity
        if return_code == 0:
            severity = "SUCCESS"
        elif return_code <= 4:
            severity = "WARNING"
        elif return_code <= 8:
            severity = "ERROR"
        elif return_code <= 12:
            severity = "SEVERE"
        else:
            severity = "CRITICAL"
        
        description = self.RETURN_CODES.get(
            return_code,
            f"Custom return code {return_code}"
        )
        
        return {
            "return_code": return_code,
            "severity": severity,
            "description": description,
            "action_required": severity in ("ERROR", "SEVERE", "CRITICAL"),
            "recommendations": self._get_rc_recommendations(return_code, severity),
        }
    
    @tool
    def analyze_abend_code(self, abend_code: str) -> Dict[str, Any]:
        """
        Analyze an ABEND code and provide interpretation.
        
        Args:
            abend_code: The ABEND code (e.g., S0C7, U0016)
            
        Returns:
            Analysis with description, common causes, and solutions
        """
        abend_upper = abend_code.upper()
        description = self.ABEND_CODES.get(
            abend_upper,
            f"Unknown ABEND code {abend_upper}"
        )
        
        return {
            "abend_code": abend_upper,
            "description": description,
            "category": "System" if abend_upper.startswith("S") else "User",
            "common_causes": self._get_abend_causes(abend_upper),
            "recommended_actions": self._get_abend_solutions(abend_upper),
        }
    
    @tool
    def get_job_history(
        self,
        job_name: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get execution history for a job over specified days.
        
        Args:
            job_name: Name of the job
            days: Number of days of history
            
        Returns:
            Execution history with statistics and trends
        """
        # Mock implementation
        return {
            "job_name": job_name,
            "period_days": days,
            "total_executions": 21,
            "success_rate": 0.857,
            "avg_duration_seconds": 345,
            "max_duration_seconds": 890,
            "min_duration_seconds": 210,
            "failure_count": 3,
            "common_failure_codes": ["S0C7", "RC=16"],
            "trend": "degrading",  # improving, stable, degrading
            "last_success": "2025-12-08T14:30:00Z",
            "last_failure": "2025-12-09T08:35:22Z",
        }
    
    def _get_rc_recommendations(self, rc: int, severity: str) -> List[str]:
        """Get recommendations based on return code."""
        if severity == "SUCCESS":
            return ["No action required"]
        elif severity == "WARNING":
            return [
                "Review job output for warnings",
                "Verify data quality if applicable",
            ]
        elif severity == "ERROR":
            return [
                "Check job log for error details",
                "Verify input files exist and are accessible",
                "Check for resource constraints",
            ]
        else:
            return [
                "Immediate investigation required",
                "Check system logs for related issues",
                "Verify job dependencies completed successfully",
                "Consider rerunning after investigation",
            ]
    
    def _get_abend_causes(self, abend: str) -> List[str]:
        """Get common causes for an ABEND code."""
        causes_map = {
            "S0C7": [
                "Invalid numeric data in input file",
                "Uninitialized working storage fields",
                "Packed decimal field contains invalid data",
            ],
            "S0C4": [
                "Array subscript out of bounds",
                "Invalid pointer reference",
                "Memory corruption",
            ],
            "S322": [
                "Job exceeded CPU time limit",
                "Infinite loop in program",
                "Excessive I/O operations",
            ],
            "S913": [
                "Missing RACF/ACF2 permissions",
                "Dataset protected",
                "Invalid user credentials",
            ],
        }
        return causes_map.get(abend, ["Unknown - check system logs"])
    
    def _get_abend_solutions(self, abend: str) -> List[str]:
        """Get recommended solutions for an ABEND code."""
        solutions_map = {
            "S0C7": [
                "Validate input data before processing",
                "Add data validation in program",
                "Check file record formats match program definitions",
            ],
            "S0C4": [
                "Review array bounds and subscripts",
                "Check pointer initialization",
                "Run with storage debug options",
            ],
            "S322": [
                "Increase TIME parameter in JCL",
                "Optimize program logic",
                "Review loop conditions",
            ],
            "S913": [
                "Request appropriate RACF access",
                "Verify user ID has required permissions",
                "Check dataset profiles",
            ],
        }
        return solutions_map.get(abend, ["Consult system programmer"])


class ErrorCodeTool:
    """
    Tool for looking up and explaining TWS error codes.
    """
    
    # TWS/HWA specific error codes
    TWS_ERRORS: Dict[str, str] = {
        "AWSBCJ001E": "Job not found in current plan",
        "AWSBCJ002E": "Job already running",
        "AWSBCJ003E": "Job dependencies not satisfied",
        "AWSBCJ004E": "Workstation not available",
        "AWSBCJ005E": "Resource conflict detected",
        "AWSBCW001E": "Workstation offline",
        "AWSBCW002E": "Agent communication failure",
        "AWSBCW003E": "Invalid workstation configuration",
        "AWSBCD001E": "Dependency cycle detected",
        "AWSBCD002E": "Missing predecessor job",
        "AWSBCS001E": "Scheduler service unavailable",
        "AWSBCS002E": "Database connection failed",
    }
    
    @tool
    def lookup_error(self, error_code: str) -> Dict[str, Any]:
        """
        Look up a TWS error code and provide explanation.
        
        Args:
            error_code: TWS error code (e.g., AWSBCJ001E)
            
        Returns:
            Error details with description and resolution steps
        """
        code_upper = error_code.upper()
        description = self.TWS_ERRORS.get(
            code_upper,
            "Unknown TWS error code"
        )
        
        return {
            "error_code": code_upper,
            "description": description,
            "category": self._categorize_error(code_upper),
            "severity": self._get_severity(code_upper),
            "resolution_steps": self._get_resolution(code_upper),
        }
    
    def _categorize_error(self, code: str) -> str:
        """Categorize error by type."""
        if "BCJ" in code:
            return "Job Error"
        elif "BCW" in code:
            return "Workstation Error"
        elif "BCD" in code:
            return "Dependency Error"
        elif "BCS" in code:
            return "System Error"
        return "Unknown"
    
    def _get_severity(self, code: str) -> str:
        """Determine error severity."""
        if code.endswith("E"):
            return "ERROR"
        elif code.endswith("W"):
            return "WARNING"
        elif code.endswith("I"):
            return "INFO"
        return "UNKNOWN"
    
    def _get_resolution(self, code: str) -> List[str]:
        """Get resolution steps for error."""
        resolutions = {
            "AWSBCJ001E": [
                "Verify job name is correct",
                "Check if job is in current plan",
                "Run jnextday if needed",
            ],
            "AWSBCW001E": [
                "Check agent status on workstation",
                "Verify network connectivity",
                "Restart TWS agent if needed",
            ],
        }
        return resolutions.get(code, ["Check TWS documentation"])


# ============================================================================
# DEPENDENCY SPECIALIST TOOLS
# ============================================================================

class DependencyGraphTool:
    """
    Tool for analyzing job dependencies and workflow graphs.
    """
    
    def __init__(self, knowledge_graph: Optional[Any] = None):
        """Initialize with optional knowledge graph."""
        self.knowledge_graph = knowledge_graph
    
    @tool
    def get_predecessors(
        self,
        job_name: str,
        depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Get predecessor jobs (upstream dependencies).
        
        Args:
            job_name: Name of the job
            depth: How many levels of predecessors to retrieve
            
        Returns:
            Predecessor tree with dependency details
        """
        logger.info("get_predecessors", job_name=job_name, depth=depth)
        
        # Mock implementation
        return {
            "job_name": job_name,
            "depth": depth,
            "predecessors": [
                {
                    "job_name": "DAILY_EXTRACT",
                    "level": 1,
                    "dependency_type": "SUCCESS",
                    "status": "SUCC",
                },
                {
                    "job_name": "FILE_TRANSFER",
                    "level": 1,
                    "dependency_type": "SUCCESS",
                    "status": "SUCC",
                },
                {
                    "job_name": "INIT_PROCESS",
                    "level": 2,
                    "dependency_type": "SUCCESS",
                    "status": "SUCC",
                },
            ],
            "total_predecessors": 3,
            "blocking_predecessors": [],
            "critical_path": ["INIT_PROCESS", "DAILY_EXTRACT", job_name],
        }
    
    @tool
    def get_successors(
        self,
        job_name: str,
        depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Get successor jobs (downstream dependents).
        
        Args:
            job_name: Name of the job
            depth: How many levels of successors to retrieve
            
        Returns:
            Successor tree with impact assessment
        """
        logger.info("get_successors", job_name=job_name, depth=depth)
        
        # Mock implementation
        return {
            "job_name": job_name,
            "depth": depth,
            "successors": [
                {
                    "job_name": "REPORT_GEN",
                    "level": 1,
                    "dependency_type": "SUCCESS",
                    "status": "WAITING",
                },
                {
                    "job_name": "DATA_LOAD",
                    "level": 1,
                    "dependency_type": "SUCCESS",
                    "status": "WAITING",
                },
                {
                    "job_name": "FINAL_REPORT",
                    "level": 2,
                    "dependency_type": "SUCCESS",
                    "status": "HOLD",
                },
            ],
            "total_successors": 3,
            "impacted_jobs": ["REPORT_GEN", "DATA_LOAD", "FINAL_REPORT"],
            "critical_successors": ["REPORT_GEN"],  # Business-critical
        }
    
    @tool
    def analyze_impact(
        self,
        job_name: str,
        failure_scenario: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze the impact if a job fails or is delayed.
        
        Args:
            job_name: Name of the job
            failure_scenario: True for failure, False for delay
            
        Returns:
            Impact analysis with affected jobs and recommendations
        """
        successors = self.get_successors(job_name)
        
        return {
            "job_name": job_name,
            "scenario": "failure" if failure_scenario else "delay",
            "direct_impact": len(successors.get("successors", [])),
            "total_impact": successors.get("total_successors", 0),
            "impacted_jobs": successors.get("impacted_jobs", []),
            "critical_jobs_affected": successors.get("critical_successors", []),
            "estimated_delay_minutes": 45,  # Based on historical data
            "risk_level": "HIGH" if successors.get("critical_successors") else "MEDIUM",
            "recommendations": [
                "Prioritize resolution of this job",
                "Notify downstream job owners",
                "Consider running backup procedures",
            ],
        }
    
    @tool
    def detect_cycles(self, job_stream: str) -> Dict[str, Any]:
        """
        Detect dependency cycles in a job stream.
        
        Args:
            job_stream: Name of the job stream to analyze
            
        Returns:
            Cycle detection results
        """
        # Mock implementation
        return {
            "job_stream": job_stream,
            "has_cycles": False,
            "cycles_found": [],
            "jobs_analyzed": 15,
            "analysis_time_ms": 120,
        }


# ============================================================================
# RESOURCE SPECIALIST TOOLS
# ============================================================================

class WorkstationTool:
    """
    Tool for analyzing workstation status and capacity.
    """
    
    @tool
    def get_workstation_status(
        self,
        workstation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get current workstation status.
        
        Args:
            workstation_name: Specific workstation or None for all
            
        Returns:
            Workstation status details
        """
        # Mock implementation
        if workstation_name:
            return {
                "workstation": workstation_name,
                "status": "ONLINE",
                "agent_status": "ACTIVE",
                "jobs_running": 3,
                "jobs_queued": 5,
                "cpu_usage_percent": 45.2,
                "memory_usage_percent": 62.8,
                "disk_usage_percent": 78.5,
                "last_heartbeat": "2025-12-09T10:45:00Z",
            }
        else:
            return {
                "workstations": [
                    {"name": "TWS_MASTER", "status": "ONLINE", "jobs_running": 2},
                    {"name": "TWS_AGENT1", "status": "ONLINE", "jobs_running": 5},
                    {"name": "TWS_AGENT2", "status": "OFFLINE", "jobs_running": 0},
                ],
                "total_online": 2,
                "total_offline": 1,
            }
    
    @tool
    def check_resource_availability(
        self,
        resource_name: str,
    ) -> Dict[str, Any]:
        """
        Check if a specific resource is available.
        
        Args:
            resource_name: Name of the resource
            
        Returns:
            Resource availability and usage details
        """
        return {
            "resource_name": resource_name,
            "available": True,
            "current_owner": None,
            "max_concurrent": 1,
            "current_usage": 0,
            "queue_depth": 0,
            "waiting_jobs": [],
        }
    
    @tool
    def get_resource_conflicts(
        self,
        job_names: List[str],
    ) -> Dict[str, Any]:
        """
        Check for resource conflicts between jobs.
        
        Args:
            job_names: List of job names to check
            
        Returns:
            Conflict analysis
        """
        return {
            "jobs_analyzed": job_names,
            "conflicts_found": False,
            "conflict_details": [],
            "can_run_parallel": True,
            "recommendations": [],
        }


class CalendarTool:
    """
    Tool for TWS calendar and scheduling analysis.
    """
    
    @tool
    def get_calendar_schedule(
        self,
        calendar_name: str,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get calendar schedule information.
        
        Args:
            calendar_name: Name of the TWS calendar
            date: Specific date or None for today
            
        Returns:
            Calendar schedule details
        """
        check_date = date or datetime.now().strftime("%Y-%m-%d")
        
        return {
            "calendar": calendar_name,
            "date": check_date,
            "is_workday": True,
            "is_holiday": False,
            "special_processing": None,
            "next_run_date": check_date,
            "business_days_remaining": 15,
        }
    
    @tool
    def check_scheduling_window(
        self,
        job_name: str,
    ) -> Dict[str, Any]:
        """
        Check the scheduling window for a job.
        
        Args:
            job_name: Name of the job
            
        Returns:
            Scheduling window details
        """
        return {
            "job_name": job_name,
            "earliest_start": "06:00:00",
            "latest_start": "22:00:00",
            "deadline": "23:59:59",
            "within_window": True,
            "time_to_deadline_minutes": 480,
            "priority": 5,
        }


# ============================================================================
# EXPORT ALL TOOLS
# ============================================================================

__all__ = [
    "tool",
    "JobLogTool",
    "ErrorCodeTool",
    "DependencyGraphTool",
    "WorkstationTool",
    "CalendarTool",
]
