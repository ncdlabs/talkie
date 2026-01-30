"""
Circuit breaker pattern for module API clients.
Prevents cascading failures by stopping requests after N consecutive failures.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker that opens after N consecutive failures and auto-recovers after timeout.
    Thread-safe.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 60.0,
        name: str = "circuit",
    ) -> None:
        """
        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout_sec: Seconds to wait before attempting recovery (half-open)
            name: Name for logging
        """
        self._failure_threshold = max(1, failure_threshold)
        self._recovery_timeout_sec = max(1.0, recovery_timeout_sec)
        self._name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = Lock()

    def call(self, func, *args, **kwargs):
        """
        Execute a function with circuit breaker protection.
        Raises exception if circuit is open, otherwise calls function and tracks success/failure.

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function raises
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self._recovery_timeout_sec:
                        self._state = CircuitState.HALF_OPEN
                        self._failure_count = 0
                        logger.info(
                            "%s: Circuit entering HALF_OPEN state (testing recovery)",
                            self._name,
                        )
                    else:
                        raise RuntimeError(
                            f"Circuit breaker is OPEN (failed {self._failure_count} times, "
                            f"retry in {self._recovery_timeout_sec - elapsed:.1f}s)"
                        )
                else:
                    raise RuntimeError("Circuit breaker is OPEN")

        # Try the call
        try:
            result = func(*args, **kwargs)
            # Success: reset failure count
            with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    # Success in half-open: close the circuit
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._last_failure_time = None
                    logger.info("%s: Circuit CLOSED (recovered)", self._name)
                elif self._state == CircuitState.CLOSED:
                    # Reset failure count on success
                    self._failure_count = 0
            return result
        except Exception:
            # Failure: increment count
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()

                if self._state == CircuitState.HALF_OPEN:
                    # Failure in half-open: open again
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "%s: Circuit OPEN (failed during recovery)",
                        self._name,
                    )
                elif (
                    self._state == CircuitState.CLOSED
                    and self._failure_count >= self._failure_threshold
                ):
                    # Too many failures: open the circuit
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "%s: Circuit OPEN (failed %d times)",
                        self._name,
                        self._failure_count,
                    )
            raise

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    def reset(self) -> None:
        """Manually reset circuit to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            logger.info("%s: Circuit manually reset", self._name)
