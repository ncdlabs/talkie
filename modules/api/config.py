"""
Module server configuration helpers.
"""

from __future__ import annotations

import os
from typing import Any


def get_module_server_config(
    raw_config: dict[str, Any], module_name: str
) -> dict[str, Any] | None:
    """
    Get module server configuration from config.

    Args:
        raw_config: Full config dict
        module_name: Module name (e.g., "speech", "rag", "browser")

    Returns:
        Server config dict if enabled, None otherwise
    """
    modules = raw_config.get("modules", {})
    module = modules.get(module_name, {})
    server = module.get("server", {})
    if not server.get("enabled", False):
        return None

    # Get infrastructure config for service discovery
    infrastructure = raw_config.get("infrastructure", {})
    consul_config = infrastructure.get("consul", {})
    keydb_config = infrastructure.get("keydb", {})
    service_discovery_config = infrastructure.get("service_discovery", {})
    load_balancing_config = infrastructure.get("load_balancing", {})

    # Service discovery settings
    use_service_discovery = server.get("use_service_discovery", False)
    endpoints = server.get("endpoints", [])

    # Consul settings
    consul_host = consul_config.get("host", "localhost")
    consul_port = int(consul_config.get("port", 8500))
    consul_addr = os.environ.get(
        "CONSUL_HTTP_ADDR", f"http://{consul_host}:{consul_port}"
    )
    if consul_addr.startswith("http://"):
        consul_addr = consul_addr[7:]
    if ":" in consul_addr:
        consul_host, consul_port = consul_addr.split(":", 1)
        consul_port = int(consul_port)

    # KeyDB settings
    keydb_host = keydb_config.get("host", "localhost")
    keydb_port = int(keydb_config.get("port", 6379))
    keydb_host = os.environ.get("KEYDB_HOST", keydb_host)
    keydb_port = int(os.environ.get("KEYDB_PORT", str(keydb_port)))

    # Load balancing strategy
    load_balancing_strategy = load_balancing_config.get("strategy", "health_based")
    if use_service_discovery and not endpoints:
        # Use service discovery
        load_balancing_strategy = server.get(
            "load_balancing_strategy", load_balancing_strategy
        )
    else:
        # Use static endpoints
        load_balancing_strategy = server.get("load_balancing_strategy", "round_robin")

    # Health check interval
    health_check_interval = service_discovery_config.get(
        "health_check_interval_sec", 30.0
    )
    if server.get("health_check_interval_sec"):
        health_check_interval = float(server.get("health_check_interval_sec"))

    return {
        "host": str(server.get("host", "localhost")),
        "port": int(server.get("port", 8000)),
        "timeout_sec": float(server.get("timeout_sec", 30.0)),
        "retry_max": int(server.get("retry_max", 3)),
        "retry_delay_sec": float(server.get("retry_delay_sec", 1.0)),
        "health_check_interval_sec": health_check_interval,
        "circuit_breaker_failure_threshold": int(
            server.get("circuit_breaker_failure_threshold", 5)
        ),
        "circuit_breaker_recovery_timeout_sec": float(
            server.get("circuit_breaker_recovery_timeout_sec", 60.0)
        ),
        "api_key": server.get("api_key"),
        # Service discovery options
        "use_service_discovery": use_service_discovery,
        "endpoints": endpoints if endpoints else None,
        "consul_host": consul_host,
        "consul_port": consul_port,
        "keydb_host": keydb_host,
        "keydb_port": keydb_port,
        "load_balancing_strategy": load_balancing_strategy,
    }


def get_module_base_url(server_config: dict[str, Any]) -> str | list[str] | None:
    """
    Get base URL(s) for module server.

    Args:
        server_config: Server config dict from get_module_server_config

    Returns:
        Base URL string, list of URLs, or None (for service discovery)
    """
    # If using service discovery and no static endpoints, return None
    if server_config.get("use_service_discovery") and not server_config.get(
        "endpoints"
    ):
        return None

    # If endpoints are provided, return them
    endpoints = server_config.get("endpoints")
    if endpoints:
        return endpoints

    # Otherwise, construct from host/port
    host = server_config["host"]
    port = server_config["port"]
    # Determine protocol (http vs https)
    protocol = "https" if server_config.get("tls_enabled", False) else "http"
    return f"{protocol}://{host}:{port}"
