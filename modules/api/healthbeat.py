"""
Healthbeat service for continuous health monitoring of all service instances.
Integrates with Consul and KeyDB for service discovery and caching.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

from modules.api.consul_client import ConsulClient
from modules.api.keydb_client import KeyDBClient
from modules.api.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class Healthbeat:
    """
    Health monitoring service that polls all service instances and updates
    Consul health checks and KeyDB cache.
    """

    def __init__(
        self,
        consul_client: ConsulClient,
        keydb_client: KeyDBClient,
        check_interval_sec: float = 10.0,
        timeout_sec: float = 5.0,
    ) -> None:
        """
        Args:
            consul_client: Consul client
            keydb_client: KeyDB client
            check_interval_sec: Interval between health checks
            timeout_sec: HTTP request timeout
        """
        self._consul = consul_client
        self._keydb = keydb_client
        self._registry = ServiceRegistry(consul_client, keydb_client)
        self._check_interval = check_interval_sec
        self._timeout = timeout_sec
        self._running = False
        self._http_client = httpx.AsyncClient(timeout=timeout_sec)

    async def check_service_health(
        self, service_url: str, service_id: str
    ) -> dict[str, Any]:
        """
        Check health of a single service instance.

        Args:
            service_url: Service URL
            service_id: Service instance ID

        Returns:
            Health status dict
        """
        try:
            # Check liveness
            live_response = await self._http_client.get(f"{service_url}/health/live")
            live_ok = live_response.status_code == 200

            # Check readiness
            ready_response = await self._http_client.get(f"{service_url}/health/ready")
            ready_ok = ready_response.status_code == 200 and ready_response.json().get(
                "ready", False
            )

            # Get full health info
            health_response = await self._http_client.get(f"{service_url}/health")
            health_data = (
                health_response.json() if health_response.status_code == 200 else {}
            )

            status = "healthy" if (live_ok and ready_ok) else "unhealthy"

            return {
                "service_id": service_id,
                "url": service_url,
                "status": status,
                "live": live_ok,
                "ready": ready_ok,
                "health_data": health_data,
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.debug("Health check failed for %s: %s", service_url, e)
            return {
                "service_id": service_id,
                "url": service_url,
                "status": "unhealthy",
                "live": False,
                "ready": False,
                "error": str(e),
                "timestamp": time.time(),
            }

    async def check_all_services(self) -> dict[str, list[dict[str, Any]]]:
        """
        Check health of all registered services.

        Returns:
            Dict mapping service names to lists of health statuses
        """
        services_to_check = ["speech", "rag", "browser"]
        results: dict[str, list[dict[str, Any]]] = {}

        for service_name in services_to_check:
            try:
                # Get healthy services from Consul
                service_instances = self._consul.get_healthy_services(service_name)
                if not service_instances:
                    logger.debug("No instances found for service %s", service_name)
                    results[service_name] = []
                    continue

                # Check each instance
                health_checks = []
                for instance in service_instances:
                    service_id = instance.get("id", "")
                    address = instance.get("address", "")
                    port = instance.get("port", 0)
                    service_url = f"http://{address}:{port}"

                    health = await self.check_service_health(service_url, service_id)
                    health_checks.append(health)

                    # Cache health status
                    self._registry.cache_health_status(
                        service_id,
                        health["status"],
                        ttl_sec=int(self._check_interval * 2),
                    )

                results[service_name] = health_checks

                # Log status changes
                healthy_count = sum(
                    1 for h in health_checks if h["status"] == "healthy"
                )
                logger.info(
                    "Service %s: %d/%d instances healthy",
                    service_name,
                    healthy_count,
                    len(health_checks),
                )

            except Exception as e:
                logger.warning("Failed to check service %s: %s", service_name, e)
                results[service_name] = []

        return results

    async def run_loop(self) -> None:
        """Run health check loop continuously."""
        self._running = True
        logger.info(
            "Healthbeat started, checking services every %.1fs", self._check_interval
        )

        while self._running:
            try:
                await self.check_all_services()
            except Exception as e:
                logger.exception("Error in health check loop: %s", e)

            await asyncio.sleep(self._check_interval)

    def stop(self) -> None:
        """Stop the health check loop."""
        self._running = False
        logger.info("Healthbeat stopped")

    async def close(self) -> None:
        """Close resources."""
        self.stop()
        await self._http_client.aclose()


async def main() -> None:
    """CLI entry point for healthbeat service."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Healthbeat service for health monitoring"
    )
    parser.add_argument("--consul-host", default="localhost", help="Consul server host")
    parser.add_argument(
        "--consul-port", type=int, default=8500, help="Consul server port"
    )
    parser.add_argument("--keydb-host", default="localhost", help="KeyDB server host")
    parser.add_argument(
        "--keydb-port", type=int, default=6379, help="KeyDB server port"
    )
    parser.add_argument(
        "--interval", type=float, default=10.0, help="Check interval in seconds"
    )
    args = parser.parse_args()

    # Use environment variables if available
    consul_addr = os.environ.get(
        "CONSUL_HTTP_ADDR", f"http://{args.consul_host}:{args.consul_port}"
    )
    if consul_addr.startswith("http://"):
        consul_addr = consul_addr[7:]
    if ":" in consul_addr:
        consul_host, consul_port = consul_addr.split(":", 1)
        consul_port = int(consul_port)
    else:
        consul_host = consul_addr
        consul_port = args.consul_port

    keydb_host = os.environ.get("KEYDB_HOST", args.keydb_host)
    keydb_port = int(os.environ.get("KEYDB_PORT", str(args.keydb_port)))

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Create clients
    consul_client = ConsulClient(host=consul_host, port=consul_port)
    keydb_client = KeyDBClient(host=keydb_host, port=keydb_port)

    # Create and run healthbeat
    healthbeat = Healthbeat(
        consul_client=consul_client,
        keydb_client=keydb_client,
        check_interval_sec=args.interval,
    )

    try:
        await healthbeat.run_loop()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await healthbeat.close()


if __name__ == "__main__":
    asyncio.run(main())
