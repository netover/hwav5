"""
Circuit Breaker Pattern Implementation.

Provides fault tolerance by temporarily blocking calls to failing services.
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Callable

from resync.core.exceptions import CircuitBreakerError

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Blocking calls
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Failures exceeded threshold, calls blocked
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before testing recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0

    async def call(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result if successful
            
        Raises:
            Exception: If circuit is open or function fails
        """
        import time
        
        # Check if circuit should recover
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerError("Circuit breaker is open")

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset if half-open
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failures = 0
            
            return result
            
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    extra={"failures": self.failures}
                )
            
            raise

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0

    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        return {
            "state": self.state.value,
            "failures": self.failures,
            "threshold": self.failure_threshold,
        }
