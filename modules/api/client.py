"""
Module API client base class and implementations.
Provides HTTP client wrappers that implement module interfaces.
"""

from __future__ import annotations

import base64
import logging
import os
import threading
import time
import uuid
from typing import Any, Callable

import requests

from modules.api.circuit_breaker import CircuitBreaker
from modules.api.load_balancer import LoadBalancer, LoadBalancingStrategy
from modules.api.retry import RetryPolicy

logger = logging.getLogger(__name__)

API_VERSION = "1.0"


class ModuleAPIClient:
    """
    Base class for module API clients.
    Provides connection management, retry logic, and circuit breaker.
    """

    def __init__(
        self,
        base_url: str | list[str] | None = None,
        timeout_sec: float = 30.0,
        retry_max: int = 3,
        retry_delay_sec: float = 1.0,
        circuit_breaker_failure_threshold: int = 5,
        circuit_breaker_recovery_timeout_sec: float = 60.0,
        api_key: str | None = None,
        module_name: str = "module",
        # Service discovery options
        use_service_discovery: bool = False,
        consul_host: str | None = None,
        consul_port: int = 8500,
        keydb_host: str | None = None,
        keydb_port: int = 6379,
        load_balancing_strategy: str = "round_robin",
        health_check_interval_sec: float = 30.0,
    ) -> None:
        """
        Args:
            base_url: Base URL(s) - single URL, list of URLs, or None (use service discovery)
            timeout_sec: Request timeout in seconds
            retry_max: Maximum retry attempts
            retry_delay_sec: Initial retry delay (exponential backoff)
            circuit_breaker_failure_threshold: Failures before opening circuit
            circuit_breaker_recovery_timeout_sec: Seconds before retry after circuit open
            api_key: Optional API key for authentication
            module_name: Module name for logging
            use_service_discovery: Enable Consul/KeyDB service discovery
            consul_host: Consul server host
            consul_port: Consul server port
            keydb_host: KeyDB server host
            keydb_port: KeyDB server port
            load_balancing_strategy: Strategy (round_robin, random, health_based, least_connections)
            health_check_interval_sec: Interval for refreshing service discovery
        """
        self._module_name = module_name
        self._timeout = timeout_sec
        self._api_key = api_key
        self._use_service_discovery = use_service_discovery
        self._health_check_interval = health_check_interval_sec
        self._last_discovery_refresh = 0.0
        self._discovery_lock = threading.Lock()

        # Determine endpoints
        if base_url is None:
            # Use service discovery
            if not use_service_discovery:
                raise ValueError(
                    "base_url required when use_service_discovery is False"
                )
            self._endpoints: list[str] = []
        elif isinstance(base_url, str):
            # Single URL
            self._endpoints = [base_url.rstrip("/")]
        else:
            # List of URLs
            self._endpoints = [url.rstrip("/") for url in base_url]

        # Service discovery clients
        self._consul_client = None
        self._keydb_client = None
        self._service_registry = None

        if use_service_discovery:
            try:
                from modules.api.consul_client import ConsulClient
                from modules.api.keydb_client import KeyDBClient
                from modules.api.service_registry import ServiceRegistry

                consul_host = consul_host or os.environ.get(
                    "CONSUL_HTTP_ADDR", "http://localhost:8500"
                )
                if consul_host.startswith("http://"):
                    consul_host = consul_host[7:]
                if ":" in consul_host:
                    consul_host, consul_port = consul_host.split(":", 1)
                    consul_port = int(consul_port)

                keydb_host = keydb_host or os.environ.get("KEYDB_HOST", "localhost")
                keydb_port = int(os.environ.get("KEYDB_PORT", str(keydb_port)))

                self._consul_client = ConsulClient(host=consul_host, port=consul_port)
                self._keydb_client = KeyDBClient(host=keydb_host, port=keydb_port)
                self._service_registry = ServiceRegistry(
                    self._consul_client, self._keydb_client
                )
                logger.info("%s: Service discovery enabled", module_name)
            except Exception as e:
                logger.warning(
                    "%s: Failed to initialize service discovery: %s", module_name, e
                )
                self._use_service_discovery = False

        # Load balancer
        strategy_map = {
            "round_robin": LoadBalancingStrategy.ROUND_ROBIN,
            "random": LoadBalancingStrategy.RANDOM,
            "health_based": LoadBalancingStrategy.HEALTH_BASED,
            "least_connections": LoadBalancingStrategy.LEAST_CONNECTIONS,
        }
        strategy = strategy_map.get(
            load_balancing_strategy, LoadBalancingStrategy.ROUND_ROBIN
        )
        self._load_balancer = LoadBalancer(self._endpoints, strategy=strategy)

        # Initialize endpoints from service discovery if needed
        if self._use_service_discovery and self._service_registry:
            self._refresh_endpoints_from_discovery()

        if not self._endpoints:
            raise ValueError(f"{module_name}: No endpoints available")

        # Current base URL (selected by load balancer)
        self._base_url = self._endpoints[0]  # Default to first endpoint

        # Create session for connection pooling
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-API-Version": API_VERSION,
                "Content-Type": "application/json",
            }
        )
        if api_key:
            self._session.headers.update({"X-API-Key": api_key})

        # Retry policy
        self._retry_policy = RetryPolicy(
            max_retries=retry_max,
            initial_delay_sec=retry_delay_sec,
        )

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_failure_threshold,
            recovery_timeout_sec=circuit_breaker_recovery_timeout_sec,
            name=f"{module_name}_circuit",
        )

        # Health check on init (async, don't block)
        try:
            self._check_health()
        except Exception:
            pass  # Don't fail init if health check fails

    def _refresh_endpoints_from_discovery(self) -> None:
        """Refresh endpoints from service discovery."""
        if not self._use_service_discovery or not self._service_registry:
            return

        try:
            urls = self._service_registry.get_healthy_service_urls(
                service_name=self._module_name,
                protocol="http",
            )
            if urls:
                self._load_balancer.update_endpoints(urls)
                self._endpoints = urls
                logger.debug(
                    "%s: Refreshed %d endpoints from service discovery",
                    self._module_name,
                    len(urls),
                )
        except Exception as e:
            logger.debug("%s: Failed to refresh endpoints: %s", self._module_name, e)

    def _check_health(self) -> bool:
        """Check if module is healthy and ready."""
        # Refresh endpoints if using service discovery
        if self._use_service_discovery:
            now = time.time()
            if now - self._last_discovery_refresh > self._health_check_interval:
                with self._discovery_lock:
                    if now - self._last_discovery_refresh > self._health_check_interval:
                        self._refresh_endpoints_from_discovery()
                        self._last_discovery_refresh = now

        # Try current endpoint
        endpoint = self._load_balancer.select_endpoint()
        if not endpoint:
            logger.warning("%s: No healthy endpoints available", self._module_name)
            return False

        try:
            response = self._session.get(
                f"{endpoint}/health",
                timeout=1.0,
            )
            response.raise_for_status()
            data = response.json()
            ready = data.get("ready", False)
            if ready:
                self._load_balancer.mark_healthy(endpoint)
            else:
                self._load_balancer.mark_unhealthy(endpoint)
                logger.warning(
                    "%s: Module not ready at %s", self._module_name, endpoint
                )
            return ready
        except Exception as e:
            self._load_balancer.mark_unhealthy(endpoint)
            logger.debug(
                "%s: Health check failed for %s: %s", self._module_name, endpoint, e
            )
            return False

    def _request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        timeout: float | None = None,
        should_retry: Callable[[Exception], bool] | None = None,
        max_failover_attempts: int = 3,
    ) -> dict[str, Any]:
        """
        Make an HTTP request with retry, circuit breaker, and failover.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: URL path (relative to base_url)
            json_data: Optional JSON body
            timeout: Optional timeout (defaults to self._timeout)
            should_retry: Optional function to determine if exception should be retried
            max_failover_attempts: Maximum number of endpoints to try on failure

        Returns:
            JSON response as dict

        Raises:
            requests.RequestException: On HTTP errors
            RuntimeError: If circuit breaker is open
        """
        timeout = timeout if timeout is not None else self._timeout
        request_id = str(uuid.uuid4())
        last_exception: Exception | None = None

        # Try multiple endpoints with failover
        for attempt in range(max_failover_attempts):
            # Select endpoint
            endpoint = self._load_balancer.select_endpoint()
            if not endpoint:
                # Refresh from discovery if available
                if self._use_service_discovery:
                    self._refresh_endpoints_from_discovery()
                    endpoint = self._load_balancer.select_endpoint()

                if not endpoint:
                    if last_exception:
                        raise last_exception
                    raise RuntimeError(
                        f"{self._module_name}: No healthy endpoints available"
                    )

            url = f"{endpoint}{path}"
            self._load_balancer.increment_connections(endpoint)

            def _do_request():
                try:
                    response = self._session.request(
                        method=method,
                        url=url,
                        json=json_data,
                        timeout=timeout,
                        headers={"X-Request-ID": request_id},
                    )
                    response.raise_for_status()
                    result = response.json()
                    # Mark as healthy on success
                    self._load_balancer.mark_healthy(endpoint)
                    return result
                except requests.RequestException as e:
                    # Mark as unhealthy on failure
                    self._load_balancer.mark_unhealthy(endpoint)
                    # Convert to standard error format
                    if hasattr(e, "response") and e.response is not None:
                        try:
                            error_data = e.response.json()
                            raise RuntimeError(error_data.get("message", str(e))) from e
                        except Exception:
                            raise
                    raise

            try:
                result = self._circuit_breaker.call(
                    lambda: self._retry_policy.execute(
                        _do_request, should_retry=should_retry
                    )
                )
                self._load_balancer.decrement_connections(endpoint)
                return result
            except RuntimeError as e:
                # Circuit breaker open or other runtime error
                if "Circuit breaker" in str(e):
                    logger.warning(
                        "%s: %s (endpoint: %s)", self._module_name, e, endpoint
                    )
                last_exception = e
                self._load_balancer.decrement_connections(endpoint)
                # Try next endpoint if available
                if attempt < max_failover_attempts - 1:
                    logger.debug(
                        "%s: Trying next endpoint after failure", self._module_name
                    )
                    continue
                raise
            except requests.RequestException as e:
                last_exception = e
                self._load_balancer.decrement_connections(endpoint)
                # Try next endpoint if available
                if attempt < max_failover_attempts - 1:
                    logger.debug(
                        "%s: Trying next endpoint after failure", self._module_name
                    )
                    continue
                logger.error("%s: Request failed: %s", self._module_name, e)
                raise

        # Should not reach here, but satisfy type checker
        if last_exception:
            raise last_exception
        raise RuntimeError(
            f"{self._module_name}: Request failed after {max_failover_attempts} attempts"
        )

    def _encode_audio(self, audio_bytes: bytes) -> str:
        """Encode audio bytes to base64."""
        return base64.b64encode(audio_bytes).decode("utf-8")

    def _decode_audio(self, audio_base64: str) -> bytes:
        """Decode base64 audio to bytes."""
        return base64.b64decode(audio_base64)

    def close(self) -> None:
        """Close the client and cleanup resources."""
        self._session.close()
        if self._keydb_client:
            self._keydb_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
