"""
Retry logic with exponential backoff for module API clients.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryPolicy:
    """
    Retry policy with exponential backoff.
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay_sec: float = 1.0,
        max_delay_sec: float = 60.0,
        backoff_multiplier: float = 2.0,
    ) -> None:
        """
        Args:
            max_retries: Maximum number of retry attempts (0 = no retries)
            initial_delay_sec: Initial delay before first retry
            max_delay_sec: Maximum delay between retries
            backoff_multiplier: Multiplier for exponential backoff
        """
        self._max_retries = max(0, max_retries)
        self._initial_delay = max(0.0, initial_delay_sec)
        self._max_delay = max(self._initial_delay, max_delay_sec)
        self._backoff_multiplier = max(1.0, backoff_multiplier)

    def execute(
        self,
        func: Callable[[], T],
        should_retry: Callable[[Exception], bool] | None = None,
    ) -> T:
        """
        Execute a function with retry logic.

        Args:
            func: Function to execute (no arguments)
            should_retry: Optional callable that takes exception and returns True if should retry.
                         If None, retries on all exceptions.

        Returns:
            Function result

        Raises:
            Last exception if all retries exhausted
        """
        last_exception: Exception | None = None
        delay = self._initial_delay

        for attempt in range(self._max_retries + 1):
            try:
                return func()
            except Exception as e:
                last_exception = e

                # Check if we should retry this exception
                if should_retry is not None and not should_retry(e):
                    raise

                # Check if we have retries left
                if attempt >= self._max_retries:
                    logger.debug(
                        "Retry exhausted after %d attempts: %s",
                        attempt + 1,
                        e,
                    )
                    raise

                # Wait before retry (exponential backoff)
                delay = min(delay * self._backoff_multiplier, self._max_delay)
                logger.debug(
                    "Retry attempt %d/%d after %.2fs: %s",
                    attempt + 1,
                    self._max_retries,
                    delay,
                    e,
                )
                time.sleep(delay)

        # Should not reach here, but satisfy type checker
        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Retry logic error")
