"""
Service registry using KeyDB and Consul for fast service discovery.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from modules.api.consul_client import ConsulClient
from modules.api.keydb_client import KeyDBClient

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Service registry that combines Consul (authoritative) and KeyDB (fast cache).
    """

    def __init__(
        self,
        consul_client: ConsulClient,
        keydb_client: KeyDBClient,
        cache_ttl_sec: int = 30,
    ) -> None:
        """
        Args:
            consul_client: Consul client for service discovery
            keydb_client: KeyDB client for caching
            cache_ttl_sec: Cache TTL in seconds
        """
        self._consul = consul_client
        self._keydb = keydb_client
        self._cache_ttl = cache_ttl_sec

    def get_healthy_service_urls(
        self,
        service_name: str,
        tag: str | None = None,
        protocol: str = "http",
    ) -> list[str]:
        """
        Get healthy service URLs (with caching).

        Args:
            service_name: Service name
            tag: Optional service tag
            protocol: URL protocol

        Returns:
            List of service URLs
        """
        # Try cache first
        cache_key = f"service:{service_name}:{tag or 'default'}:urls"
        cached = self._keydb.get(cache_key)
        if cached:
            try:
                urls = json.loads(cached)
                if urls:
                    logger.debug("Cache hit for service %s", service_name)
                    return urls
            except Exception as e:
                logger.debug("Failed to parse cached URLs: %s", e)

        # Cache miss: query Consul
        logger.debug("Cache miss for service %s, querying Consul", service_name)
        urls = self._consul.get_service_urls(service_name, tag, protocol)

        # Cache the result
        if urls:
            self._keydb.set(
                cache_key,
                json.dumps(urls),
                ex=self._cache_ttl,
            )

        return urls

    def get_healthy_services(
        self,
        service_name: str,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get healthy service instances (with caching).

        Args:
            service_name: Service name
            tag: Optional service tag

        Returns:
            List of service instances
        """
        # Try cache first
        cache_key = f"service:{service_name}:{tag or 'default'}:instances"
        cached = self._keydb.get(cache_key)
        if cached:
            try:
                services = json.loads(cached)
                if services:
                    logger.debug("Cache hit for service %s instances", service_name)
                    return services
            except Exception as e:
                logger.debug("Failed to parse cached services: %s", e)

        # Cache miss: query Consul
        logger.debug(
            "Cache miss for service %s instances, querying Consul", service_name
        )
        services = self._consul.get_healthy_services(service_name, tag)

        # Cache the result
        if services:
            self._keydb.set(
                cache_key,
                json.dumps(services),
                ex=self._cache_ttl,
            )

        return services

    def cache_health_status(
        self,
        service_id: str,
        status: str,
        ttl_sec: int | None = None,
    ) -> None:
        """
        Cache health status for a service instance.

        Args:
            service_id: Service instance ID
            status: Health status ("healthy", "unhealthy", etc.)
            ttl_sec: Optional TTL (defaults to cache_ttl_sec)
        """
        key = f"health:{service_id}"
        ttl = ttl_sec if ttl_sec is not None else self._cache_ttl
        self._keydb.set(key, status, ex=ttl)

    def get_cached_health_status(self, service_id: str) -> str | None:
        """
        Get cached health status for a service instance.

        Args:
            service_id: Service instance ID

        Returns:
            Health status or None
        """
        key = f"health:{service_id}"
        return self._keydb.get(key)

    def invalidate_cache(self, service_name: str, tag: str | None = None) -> None:
        """
        Invalidate cache for a service.

        Args:
            service_name: Service name
            tag: Optional service tag
        """
        keys = [
            f"service:{service_name}:{tag or 'default'}:urls",
            f"service:{service_name}:{tag or 'default'}:instances",
        ]
        for key in keys:
            self._keydb.delete(key)
        logger.debug("Invalidated cache for service %s", service_name)
