"""
Base module server class using FastAPI.
Provides standard endpoints (health, config, metrics) and common functionality.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import sys
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

API_VERSION = "1.0"


class BaseModuleServer:
    """
    Base class for module HTTP servers.
    Provides standard endpoints and common functionality.
    """

    def __init__(
        self,
        module_name: str,
        module_version: str = "1.0.0",
        host: str = "localhost",
        port: int = 8000,
        api_key: str | None = None,
        cors_origins: list[str] | None = None,
        consul_enabled: bool = True,
        consul_host: str | None = None,
        consul_port: int = 8500,
    ) -> None:
        """
        Args:
            module_name: Name of the module (e.g., "speech", "rag")
            module_version: Module version string
            host: Host to bind to
            port: Port to bind to
            api_key: Optional API key for authentication
            cors_origins: CORS allowed origins (None = allow all)
            consul_enabled: Enable Consul registration
            consul_host: Consul server host (default: from CONSUL_HTTP_ADDR env or localhost)
            consul_port: Consul server port
        """
        self._module_name = module_name
        self._module_version = module_version
        self._host = host
        self._port = port
        self._api_key = api_key
        self._ready = False
        self._shutdown_requested = False
        self._start_time = time.time()
        self._consul_enabled = consul_enabled
        self._consul_client = None
        self._service_id = f"{module_name}-{uuid.uuid4().hex[:8]}"

        # Initialize Consul client if enabled
        if consul_enabled:
            try:
                from modules.api.consul_client import ConsulClient

                consul_addr = consul_host or os.environ.get(
                    "CONSUL_HTTP_ADDR", "http://localhost:8500"
                )
                if isinstance(consul_addr, str) and consul_addr.startswith("http://"):
                    consul_addr = consul_addr[7:]
                if ":" in str(consul_addr):
                    _consul_host, _consul_port = str(consul_addr).split(":", 1)
                    _consul_port = int(_consul_port)
                else:
                    _consul_host = str(consul_addr)
                    _consul_port = 8500

                self._consul_client = ConsulClient(host=_consul_host, port=_consul_port)
                logger.info(
                    "%s: Consul client initialized -> %s:%d",
                    module_name,
                    _consul_host,
                    _consul_port,
                )
            except Exception as e:
                logger.warning("Failed to initialize Consul client: %s", e)
                self._consul_enabled = False

        # Create FastAPI app
        self._app = FastAPI(
            title=f"Talkie {module_name.title()} Module",
            version=module_version,
        )

        # Metrics (initialized before middleware that uses them)
        self._request_count = 0
        self._request_count_by_endpoint: dict[str, int] = {}
        self._error_count = 0
        self._request_latency_sum: float = 0.0
        self._request_latency_count: int = 0

        # CORS middleware
        if cors_origins is None:
            cors_origins = ["*"]
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Request ID and metrics middleware
        @self._app.middleware("http")
        async def add_request_id_and_metrics(request: Request, call_next):
            request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
            start_time = time.time()

            # Track request
            self._request_count += 1
            endpoint = request.url.path
            self._request_count_by_endpoint[endpoint] = (
                self._request_count_by_endpoint.get(endpoint, 0) + 1
            )

            try:
                response = await call_next(request)
                # Track latency
                latency = time.time() - start_time
                self._request_latency_sum += latency
                self._request_latency_count += 1

                # Track errors
                if response.status_code >= 400:
                    self._error_count += 1

                response.headers["X-Request-ID"] = request_id
                return response
            except Exception:
                self._error_count += 1
                raise

        # Authentication middleware (if API key set)
        if api_key:

            @self._app.middleware("http")
            async def authenticate(request: Request, call_next):
                # Skip auth for health and metrics endpoints
                if request.url.path in [
                    "/health",
                    "/health/live",
                    "/health/ready",
                    "/metrics",
                    "/metrics/prometheus",
                ]:
                    return await call_next(request)

                auth_header = request.headers.get("Authorization", "")
                api_key_header = request.headers.get("X-API-Key", "")

                if (
                    auth_header.startswith("Bearer ") and auth_header[7:] == api_key
                ) or api_key_header == api_key:
                    return await call_next(request)

                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "authentication_failed",
                        "message": "Invalid API key",
                    },
                )

        # Standard endpoints
        self._setup_standard_endpoints()

    def _service_unavailable_response(self) -> JSONResponse:
        """Return 503 JSONResponse for module not initialized."""
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "service_unavailable",
                "message": "Module not initialized",
            },
        )

    def _error_response(
        self,
        status_code: int,
        error_code: str,
        message: str,
    ) -> JSONResponse:
        """Return JSONResponse with error code and message."""
        return JSONResponse(
            status_code=status_code,
            content={"error": error_code, "message": message},
        )

    def _require_service(self, service: Any) -> JSONResponse | None:
        """Return service_unavailable response if service is None, else None."""
        if service is None:
            return self._service_unavailable_response()
        return None

    def _setup_standard_endpoints(self) -> None:
        """Set up standard endpoints (health, config, metrics, version)."""

        @self._app.get("/health")
        async def health() -> dict[str, Any]:
            """Health check endpoint (compatibility)."""
            return {
                "status": "ok",
                "ready": self._ready,
                "version": API_VERSION,
                "module": self._module_name,
            }

        @self._app.get("/health/live")
        async def health_live() -> dict[str, Any]:
            """Liveness probe - indicates if the service is running."""
            return {
                "status": "ok",
                "alive": True,
            }

        @self._app.get("/health/ready")
        async def health_ready() -> dict[str, Any]:
            """Readiness probe - indicates if the service is ready to accept requests."""
            return {
                "status": "ok" if self._ready else "not_ready",
                "ready": self._ready,
                "module": self._module_name,
            }

        @self._app.get("/config")
        async def get_config() -> dict[str, Any]:
            """Get current configuration."""
            return {"config": self.get_config_dict()}

        @self._app.post("/config")
        async def update_config(request: Request) -> dict[str, Any]:
            """Update configuration."""
            try:
                data = await request.json()
                config = data.get("config", {})
                self.update_config_dict(config)
                return {"success": True}
            except Exception as e:
                logger.exception("Failed to update config: %s", e)
                return self._error_response(
                    status.HTTP_400_BAD_REQUEST, "invalid_request", str(e)
                )

        @self._app.post("/config/reload")
        async def reload_config() -> dict[str, Any]:
            """Reload configuration from file."""
            try:
                self.reload_config_from_file()
                return {"success": True}
            except Exception as e:
                logger.exception("Failed to reload config: %s", e)
                return self._error_response(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", str(e)
                )

        @self._app.get("/metrics")
        async def metrics() -> dict[str, Any]:
            """Metrics endpoint (JSON format)."""
            avg_latency = (
                self._request_latency_sum / self._request_latency_count
                if self._request_latency_count > 0
                else 0.0
            )
            uptime_sec = time.time() - self._start_time
            return {
                "requests_total": self._request_count,
                "requests_by_endpoint": dict(self._request_count_by_endpoint),
                "errors_total": self._error_count,
                "average_latency_sec": avg_latency,
                "uptime_sec": uptime_sec,
            }

        @self._app.get("/metrics/prometheus")
        async def metrics_prometheus() -> Response:
            """Prometheus-compatible metrics endpoint."""
            avg_latency = (
                self._request_latency_sum / self._request_latency_count
                if self._request_latency_count > 0
                else 0.0
            )
            uptime_sec = time.time() - self._start_time

            # Prometheus format
            lines = [
                f"# HELP {self._module_name}_requests_total Total number of requests",
                f"# TYPE {self._module_name}_requests_total counter",
                f"{self._module_name}_requests_total {self._request_count}",
                f"# HELP {self._module_name}_errors_total Total number of errors",
                f"# TYPE {self._module_name}_errors_total counter",
                f"{self._module_name}_errors_total {self._error_count}",
                f"# HELP {self._module_name}_request_latency_seconds Average request latency",
                f"# TYPE {self._module_name}_request_latency_seconds gauge",
                f"{self._module_name}_request_latency_seconds {avg_latency:.6f}",
                f"# HELP {self._module_name}_uptime_seconds Service uptime",
                f"# TYPE {self._module_name}_uptime_seconds gauge",
                f"{self._module_name}_uptime_seconds {uptime_sec:.2f}",
                f"# HELP {self._module_name}_ready Service readiness (1=ready, 0=not ready)",
                f"# TYPE {self._module_name}_ready gauge",
                f"{self._module_name}_ready {1 if self._ready else 0}",
            ]

            # Add per-endpoint metrics
            for endpoint, count in self._request_count_by_endpoint.items():
                lines.append(
                    f"# HELP {self._module_name}_requests_by_endpoint_total Requests by endpoint"
                )
                lines.append(
                    f"# TYPE {self._module_name}_requests_by_endpoint_total counter"
                )
                lines.append(
                    f'{self._module_name}_requests_by_endpoint_total{{endpoint="{endpoint}"}} {count}'
                )

            return Response(content="\n".join(lines) + "\n", media_type="text/plain")

        @self._app.get("/version")
        async def version() -> dict[str, Any]:
            """API version information."""
            return {
                "api_version": API_VERSION,
                "module_version": self._module_version,
            }

    def get_config_dict(self) -> dict[str, Any]:
        """
        Get current configuration as dict.
        Override in subclasses to return actual config.
        """
        return {}

    def update_config_dict(self, config: dict[str, Any]) -> None:
        """
        Update configuration from dict.
        Override in subclasses to handle config updates.
        """
        pass

    def reload_config_from_file(self) -> None:
        """
        Reload configuration from file and call update_config_dict.
        Subclasses override update_config_dict to apply module-specific config.
        """
        from config import load_config

        self._config = load_config()
        self.update_config_dict(self._config)

    def set_ready(self, ready: bool = True) -> None:
        """Mark module as ready (or not ready)."""
        self._ready = ready
        logger.info("%s: Module ready=%s", self._module_name, ready)

    def get_app(self) -> FastAPI:
        """Get the FastAPI app instance."""
        return self._app

    def _setup_graceful_shutdown(self) -> None:
        """Set up graceful shutdown handlers."""

        def signal_handler(signum, frame):
            logger.info(
                "%s: Received signal %d, initiating graceful shutdown",
                self._module_name,
                signum,
            )
            self._shutdown_requested = True

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    async def startup(self) -> None:
        """Called on server startup. Override to initialize module."""
        self._setup_graceful_shutdown()
        logger.info(
            "%s: Module server starting on %s:%d",
            self._module_name,
            self._host,
            self._port,
        )

        # Register with Consul if enabled (retry a few times in case Consul is still starting)
        if self._consul_enabled and self._consul_client:
            register_address = os.environ.get("CONSUL_REGISTER_ADDRESS") or self._host
            if register_address == "0.0.0.0":
                register_address = socket.gethostname()
            health_url = f"http://{register_address}:{self._port}/health"
            last_error = None
            for attempt in range(1, 6):
                try:
                    logger.info(
                        "%s: Registering with Consul (attempt %d/5) at %s:%d",
                        self._module_name,
                        attempt,
                        register_address,
                        self._port,
                    )
                    self._consul_client.register_service(
                        service_name=self._module_name,
                        service_id=self._service_id,
                        address=register_address,
                        port=self._port,
                        health_check_url=health_url,
                        tags=["talkie", "module"],
                        meta={
                            "version": self._module_version,
                            "api_version": API_VERSION,
                            "metrics_path": "/metrics/prometheus",
                        },
                    )
                    logger.info(
                        "%s: Registered with Consul as %s at %s:%d",
                        self._module_name,
                        self._service_id,
                        register_address,
                        self._port,
                    )
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "%s: Consul registration attempt %d failed: %s",
                        self._module_name,
                        attempt,
                        e,
                    )
                    if attempt < 5:
                        import asyncio

                        await asyncio.sleep(2)
            else:
                logger.warning(
                    "%s: Failed to register with Consul after 5 attempts: %s",
                    self._module_name,
                    last_error,
                )

    async def shutdown(self) -> None:
        """Called on server shutdown. Override to cleanup resources."""
        logger.info("%s: Module server shutting down", self._module_name)

        # Deregister from Consul if enabled
        if self._consul_enabled and self._consul_client:
            try:
                self._consul_client.deregister_service(self._service_id)
                logger.info("%s: Deregistered from Consul", self._module_name)
            except Exception as e:
                logger.warning(
                    "%s: Failed to deregister from Consul: %s", self._module_name, e
                )

    def run(self) -> None:
        """Run the server (blocking)."""
        import uvicorn

        # Register startup/shutdown handlers
        @self._app.on_event("startup")
        async def startup_event():
            await self.startup()

        @self._app.on_event("shutdown")
        async def shutdown_event():
            await self.shutdown()

        try:
            uvicorn.run(
                self._app,
                host=self._host,
                port=self._port,
                log_level="info",
            )
        except KeyboardInterrupt:
            logger.info("%s: Server stopped by user", self._module_name)
        except Exception as e:
            logger.exception("%s: Server error: %s", self._module_name, e)
            sys.exit(1)
