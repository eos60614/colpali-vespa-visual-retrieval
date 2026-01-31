"""
Unified health check system for all services.

Checks:
- Vespa search engine
- LLM provider connectivity
- ColPali model loaded
- Job queue status
- Connector health
- Database connectivity (if configured)
"""

import asyncio
import time
from datetime import datetime
from typing import Callable, Dict, Optional

import httpx

from backend.core.config import get, get_env
from backend.core.logging_config import get_logger
from backend.gateway.schemas import HealthStatus, ServiceHealth

logger = get_logger(__name__)


class HealthChecker:
    """
    Unified health checker for all backend services.

    Runs health checks against:
    - Vespa
    - LLM provider
    - ColPali model
    - Job queue
    - Connectors
    - S3 (if configured)
    - PostgreSQL (if configured)
    """

    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, ServiceHealth] = {}
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default health checks."""
        self.register("vespa", self._check_vespa)
        self.register("llm", self._check_llm)
        self.register("colpali_model", self._check_colpali)
        self.register("job_queue", self._check_job_queue)
        self.register("connectors", self._check_connectors)

        # Optional services
        if get_env("AWS_ACCESS_KEY_ID"):
            self.register("s3", self._check_s3)
        if get_env("PROCORE_DATABASE_URL"):
            self.register("database", self._check_database)

    def register(self, name: str, check_func: Callable):
        """Register a health check function."""
        self._checks[name] = check_func

    def unregister(self, name: str):
        """Unregister a health check."""
        self._checks.pop(name, None)

    async def check_all(self) -> HealthStatus:
        """
        Run all health checks.

        Returns:
            HealthStatus with results for all services
        """
        services = []
        tasks = []

        for name, check_func in self._checks.items():
            tasks.append(self._run_check(name, check_func))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, ServiceHealth):
                services.append(result)
                self._last_results[result.name] = result
            elif isinstance(result, Exception):
                logger.error(f"Health check error: {result}")

        # Overall health is True only if all services are healthy
        overall_healthy = all(s.healthy for s in services)

        return HealthStatus(
            healthy=overall_healthy,
            timestamp=datetime.utcnow(),
            services=services,
            version=get("app", "version", fallback="1.0.0"),
        )

    async def check_service(self, name: str) -> Optional[ServiceHealth]:
        """Run health check for a specific service."""
        check_func = self._checks.get(name)
        if not check_func:
            return None
        return await self._run_check(name, check_func)

    async def _run_check(
        self,
        name: str,
        check_func: Callable,
    ) -> ServiceHealth:
        """Run a single health check with timing."""
        start = time.perf_counter()
        try:
            result = await check_func()
            latency = (time.perf_counter() - start) * 1000

            if isinstance(result, ServiceHealth):
                result.latency_ms = latency
                return result
            elif isinstance(result, bool):
                return ServiceHealth(
                    name=name,
                    healthy=result,
                    latency_ms=latency,
                    message="OK" if result else "Failed",
                )
            else:
                return ServiceHealth(
                    name=name,
                    healthy=True,
                    latency_ms=latency,
                    details=result if isinstance(result, dict) else {},
                )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            logger.error(f"Health check failed for {name}: {e}")
            return ServiceHealth(
                name=name,
                healthy=False,
                latency_ms=latency,
                message=str(e),
            )

    # =========================================================================
    # Default health check implementations
    # =========================================================================

    async def _check_vespa(self) -> ServiceHealth:
        """Check Vespa connectivity."""
        try:

            # Try to get an existing instance or create a minimal one
            vespa_url = get_env("VESPA_LOCAL_URL") or get_env("VESPA_APP_TOKEN_URL")
            if not vespa_url:
                return ServiceHealth(
                    name="vespa",
                    healthy=False,
                    message="Vespa URL not configured",
                )

            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check Vespa health endpoint
                response = await client.get(f"{vespa_url}/state/v1/health")
                if response.status_code == 200:
                    return ServiceHealth(
                        name="vespa",
                        healthy=True,
                        message="Connected",
                        details={"url": vespa_url},
                    )
                else:
                    return ServiceHealth(
                        name="vespa",
                        healthy=False,
                        message=f"HTTP {response.status_code}",
                    )
        except Exception as e:
            return ServiceHealth(
                name="vespa",
                healthy=False,
                message=str(e),
            )

    async def _check_llm(self) -> ServiceHealth:
        """Check LLM provider connectivity."""
        try:
            from backend.connectors.llm.config import resolve_llm_config, get_chat_model

            base_url, api_key = resolve_llm_config()
            model = get_chat_model()

            if not base_url:
                return ServiceHealth(
                    name="llm",
                    healthy=False,
                    message="LLM_BASE_URL not configured",
                )

            # Try a simple API call (list models or similar)
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                # Try the models endpoint
                response = await client.get(
                    f"{base_url}/models",
                    headers=headers,
                )

                if response.status_code in (200, 401, 403):
                    # 401/403 means API is reachable but auth may be wrong
                    return ServiceHealth(
                        name="llm",
                        healthy=response.status_code == 200,
                        message="Connected" if response.status_code == 200 else "Auth error",
                        details={
                            "base_url": base_url,
                            "model": model,
                        },
                    )
                else:
                    return ServiceHealth(
                        name="llm",
                        healthy=False,
                        message=f"HTTP {response.status_code}",
                    )
        except Exception as e:
            return ServiceHealth(
                name="llm",
                healthy=False,
                message=str(e),
            )

    async def _check_colpali(self) -> ServiceHealth:
        """Check if ColPali model is loaded."""
        try:
            # Check if the model is loaded in the global state
            # This assumes sim_map_generator is available globally
            import sys
            main_module = sys.modules.get("__main__")

            if main_module and hasattr(main_module, "sim_map_generator"):
                generator = getattr(main_module, "sim_map_generator")
                if generator and hasattr(generator, "model"):
                    return ServiceHealth(
                        name="colpali_model",
                        healthy=True,
                        message="Model loaded",
                        details={
                            "model_name": getattr(generator, "model_name", "unknown"),
                            "device": str(getattr(generator, "device", "unknown")),
                        },
                    )

            return ServiceHealth(
                name="colpali_model",
                healthy=False,
                message="Model not loaded",
            )
        except Exception as e:
            return ServiceHealth(
                name="colpali_model",
                healthy=False,
                message=str(e),
            )

    async def _check_job_queue(self) -> ServiceHealth:
        """Check job queue status."""
        try:
            from backend.gateway.jobs import job_queue, JobState

            # Get queue statistics
            queued = len(job_queue.store.get_by_state(JobState.QUEUED))
            processing = len(job_queue._active_jobs)

            return ServiceHealth(
                name="job_queue",
                healthy=True,
                message=f"Running ({processing} active, {queued} queued)",
                details={
                    "running": job_queue._running,
                    "active_jobs": processing,
                    "queued_jobs": queued,
                    "max_workers": job_queue.max_workers,
                },
            )
        except Exception as e:
            return ServiceHealth(
                name="job_queue",
                healthy=False,
                message=str(e),
            )

    async def _check_connectors(self) -> ServiceHealth:
        """Check connector health."""
        try:
            from backend.connectors.base import connector_registry

            connectors = connector_registry.get_all()
            if not connectors:
                return ServiceHealth(
                    name="connectors",
                    healthy=True,
                    message="No connectors registered",
                )

            # Check each connector
            results = await connector_registry.health_check_all()
            healthy_count = sum(1 for v in results.values() if v)
            total = len(results)

            return ServiceHealth(
                name="connectors",
                healthy=healthy_count == total,
                message=f"{healthy_count}/{total} healthy",
                details={
                    "connectors": {k: "healthy" if v else "unhealthy" for k, v in results.items()},
                },
            )
        except Exception as e:
            return ServiceHealth(
                name="connectors",
                healthy=False,
                message=str(e),
            )

    async def _check_s3(self) -> ServiceHealth:
        """Check S3 connectivity."""
        try:
            import boto3

            s3 = boto3.client("s3")
            bucket = get_env("S3_BUCKET")

            if not bucket:
                return ServiceHealth(
                    name="s3",
                    healthy=False,
                    message="S3_BUCKET not configured",
                )

            # Try to head the bucket
            s3.head_bucket(Bucket=bucket)
            return ServiceHealth(
                name="s3",
                healthy=True,
                message="Connected",
                details={"bucket": bucket},
            )
        except Exception as e:
            return ServiceHealth(
                name="s3",
                healthy=False,
                message=str(e),
            )

    async def _check_database(self) -> ServiceHealth:
        """Check PostgreSQL connectivity."""
        try:
            import asyncpg

            db_url = get_env("PROCORE_DATABASE_URL")
            if not db_url:
                return ServiceHealth(
                    name="database",
                    healthy=False,
                    message="PROCORE_DATABASE_URL not configured",
                )

            conn = await asyncpg.connect(db_url, timeout=5.0)
            await conn.execute("SELECT 1")
            await conn.close()

            return ServiceHealth(
                name="database",
                healthy=True,
                message="Connected",
            )
        except Exception as e:
            return ServiceHealth(
                name="database",
                healthy=False,
                message=str(e),
            )

    def get_last_results(self) -> Dict[str, ServiceHealth]:
        """Get the last health check results."""
        return self._last_results.copy()


# Global health checker instance
health_checker = HealthChecker()
