"""
Load balancing logic for multiple service endpoints.
"""

from __future__ import annotations

import random
import time
from enum import Enum
from typing import Any

logger = None  # Will be set when logging is available


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    HEALTH_BASED = "health_based"
    LEAST_CONNECTIONS = "least_connections"


class LoadBalancer:
    """
    Load balancer for selecting service endpoints.
    """

    def __init__(
        self,
        endpoints: list[str],
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        health_check_func: Any | None = None,
    ) -> None:
        """
        Args:
            endpoints: List of service URLs
            strategy: Load balancing strategy
            health_check_func: Optional function to check endpoint health
        """
        self._endpoints = endpoints.copy()
        self._strategy = strategy
        self._health_check_func = health_check_func
        self._current_index = 0
        self._connection_counts: dict[str, int] = {ep: 0 for ep in endpoints}
        self._last_selection_time: dict[str, float] = {ep: 0.0 for ep in endpoints}
        self._health_status: dict[str, bool] = {ep: True for ep in endpoints}

    def add_endpoint(self, endpoint: str) -> None:
        """Add an endpoint."""
        if endpoint not in self._endpoints:
            self._endpoints.append(endpoint)
            self._connection_counts[endpoint] = 0
            self._last_selection_time[endpoint] = 0.0
            self._health_status[endpoint] = True

    def remove_endpoint(self, endpoint: str) -> None:
        """Remove an endpoint."""
        if endpoint in self._endpoints:
            self._endpoints.remove(endpoint)
            self._connection_counts.pop(endpoint, None)
            self._last_selection_time.pop(endpoint, None)
            self._health_status.pop(endpoint, None)

    def update_endpoints(self, endpoints: list[str]) -> None:
        """Update the list of endpoints."""
        old_endpoints = set(self._endpoints)
        new_endpoints = set(endpoints)

        # Remove endpoints that are no longer available
        for ep in old_endpoints - new_endpoints:
            self.remove_endpoint(ep)

        # Add new endpoints
        for ep in new_endpoints - old_endpoints:
            self.add_endpoint(ep)

    def mark_healthy(self, endpoint: str) -> None:
        """Mark an endpoint as healthy."""
        self._health_status[endpoint] = True

    def mark_unhealthy(self, endpoint: str) -> None:
        """Mark an endpoint as unhealthy."""
        self._health_status[endpoint] = False

    def select_endpoint(self) -> str | None:
        """
        Select an endpoint based on the load balancing strategy.

        Returns:
            Selected endpoint URL or None if no healthy endpoints
        """
        if not self._endpoints:
            return None

        # Filter to healthy endpoints if health-based strategy
        available_endpoints = self._endpoints
        if self._strategy == LoadBalancingStrategy.HEALTH_BASED:
            available_endpoints = [
                ep for ep in self._endpoints if self._health_status.get(ep, True)
            ]
            if not available_endpoints:
                # Fallback to all endpoints if none are healthy
                available_endpoints = self._endpoints

        if not available_endpoints:
            return None

        if self._strategy == LoadBalancingStrategy.ROUND_ROBIN:
            # Round-robin selection
            selected = available_endpoints[
                self._current_index % len(available_endpoints)
            ]
            self._current_index = (self._current_index + 1) % len(available_endpoints)
            return selected

        elif self._strategy == LoadBalancingStrategy.RANDOM:
            # Random selection
            return random.choice(available_endpoints)

        elif self._strategy == LoadBalancingStrategy.HEALTH_BASED:
            # Select from healthy endpoints (round-robin among healthy)
            healthy = [
                ep for ep in available_endpoints if self._health_status.get(ep, True)
            ]
            if healthy:
                selected = healthy[self._current_index % len(healthy)]
                self._current_index = (self._current_index + 1) % len(healthy)
                return selected
            # Fallback to any endpoint
            return available_endpoints[0]

        elif self._strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            # Select endpoint with least connections
            min_connections = min(
                self._connection_counts[ep] for ep in available_endpoints
            )
            candidates = [
                ep
                for ep in available_endpoints
                if self._connection_counts[ep] == min_connections
            ]
            return random.choice(candidates) if candidates else available_endpoints[0]

        # Default: round-robin
        selected = available_endpoints[self._current_index % len(available_endpoints)]
        self._current_index = (self._current_index + 1) % len(available_endpoints)
        return selected

    def increment_connections(self, endpoint: str) -> None:
        """Increment connection count for an endpoint."""
        self._connection_counts[endpoint] = self._connection_counts.get(endpoint, 0) + 1
        self._last_selection_time[endpoint] = time.time()

    def decrement_connections(self, endpoint: str) -> None:
        """Decrement connection count for an endpoint."""
        self._connection_counts[endpoint] = max(
            0, self._connection_counts.get(endpoint, 0) - 1
        )
