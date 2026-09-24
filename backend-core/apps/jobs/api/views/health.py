"""Health check endpoint for the backend service."""
import time
from datetime import datetime, timezone

from django.conf import settings
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from config.logging_config import get_logger

logger = get_logger(__name__)

_startup_time = time.monotonic()
_SERVICE_VERSION = "0.9.0"


class HealthCheckView(APIView):
    """
    Health check endpoint returning service status and dependency checks.

    No authentication required — used by load balancers, Docker health
    checks, and Prometheus blackbox monitoring.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Health Check",
        description="Returns service health status with dependency checks for database, Redis, and Celery.",
        tags=["Health"],
    )
    def get(self, request):
        """Return health status with dependency latencies."""
        checks = {}
        overall = "healthy"

        checks["database"] = self._check_database()
        if checks["database"]["status"] == "unhealthy":
            overall = "unhealthy"

        checks["redis"] = self._check_redis()
        if checks["redis"]["status"] == "unhealthy":
            overall = "unhealthy"

        checks["celery"] = self._check_celery()
        if checks["celery"]["status"] == "unhealthy":
            overall = "degraded" if overall == "healthy" else overall

        checks["s3"] = self._check_s3()
        if checks["s3"]["status"] == "unhealthy":
            overall = "degraded" if overall == "healthy" else overall

        status_code = 200 if overall != "unhealthy" else 503
        uptime = time.monotonic() - _startup_time

        return Response(
            {
                "status": overall,
                "service": "photogear-backend",
                "version": _SERVICE_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": round(uptime),
                "checks": checks,
            },
            status=status_code,
        )

    def _check_database(self) -> dict:
        """Check PostgreSQL connectivity."""
        try:
            start = time.monotonic()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            latency = (time.monotonic() - start) * 1000
            return {"status": "healthy", "latency_ms": round(latency, 1)}
        except Exception as e:
            logger.error(f"[HEALTH] Database check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    def _check_redis(self) -> dict:
        """Check Redis connectivity and memory usage."""
        try:
            import redis as redis_lib

            redis_url = settings.CELERY_BROKER_URL
            start = time.monotonic()
            client = redis_lib.from_url(redis_url, socket_connect_timeout=2)
            client.ping()
            latency = (time.monotonic() - start) * 1000

            info = client.info("memory")
            used = info.get("used_memory", 0)
            max_mem = info.get("maxmemory", 0)
            mem_pct = round(used / max_mem * 100, 1) if max_mem else None

            return {
                "status": "healthy",
                "latency_ms": round(latency, 1),
                "memory_usage_percent": mem_pct,
            }
        except Exception as e:
            logger.error(f"[HEALTH] Redis check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    def _check_celery(self) -> dict:
        """Check Celery worker availability via ping."""
        try:
            from config.celery import app as celery_app

            start = time.monotonic()
            result = celery_app.control.ping(timeout=2)
            latency = (time.monotonic() - start) * 1000

            worker_count = len(result) if result else 0
            if worker_count == 0:
                return {"status": "unhealthy", "error": "No workers responding"}

            return {
                "status": "healthy",
                "latency_ms": round(latency, 1),
                "workers": worker_count,
            }
        except Exception as e:
            logger.error(f"[HEALTH] Celery check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    def _check_s3(self) -> dict:
        """Check S3 connectivity by verifying all configured buckets are reachable."""
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        buckets = {
            "raw_images": getattr(settings, "AWS_S3_RAW_IMAGES_BUCKET", None),
            "ai": getattr(settings, "AWS_S3_AI_BUCKET", None),
            "results": getattr(settings, "AWS_S3_RESULTS_BUCKET", None),
        }
        buckets = {k: v for k, v in buckets.items() if v}

        if not buckets:
            return {"status": "healthy", "note": "No S3 buckets configured"}

        try:
            session_kwargs = {}
            if getattr(settings, "AWS_S3_REGION_NAME", None):
                session_kwargs["region_name"] = settings.AWS_S3_REGION_NAME
            if not getattr(settings, "USE_AWS_ROLE", False):
                key = getattr(settings, "AWS_S3_ACCESS_KEY_ID", None)
                secret = getattr(settings, "AWS_S3_SECRET_ACCESS_KEY", None)
                if key and secret:
                    session_kwargs["aws_access_key_id"] = key
                    session_kwargs["aws_secret_access_key"] = secret

            from botocore.config import Config as BotoConfig

            start = time.monotonic()
            client = boto3.Session(**session_kwargs).client(
                "s3",
                endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
                config=BotoConfig(
                    connect_timeout=3,
                    read_timeout=3,
                    retries={"max_attempts": 0},
                ),
            )
            latency = (time.monotonic() - start) * 1000

            bucket_status = {}
            for label, bucket_name in buckets.items():
                try:
                    client.head_bucket(Bucket=bucket_name)
                    bucket_status[label] = {"bucket": bucket_name, "status": "reachable"}
                except ClientError as e:
                    code = e.response["Error"]["Code"]
                    bucket_status[label] = {
                        "bucket": bucket_name,
                        "status": "unreachable",
                        "error": f"HTTP {code}",
                    }

            all_ok = all(b["status"] == "reachable" for b in bucket_status.values())
            return {
                "status": "healthy" if all_ok else "unhealthy",
                "session_latency_ms": round(latency, 1),
                "buckets": bucket_status,
            }
        except NoCredentialsError:
            logger.error("[HEALTH] S3 check failed: no credentials")
            return {"status": "unhealthy", "error": "AWS credentials not found"}
        except Exception as e:
            logger.error(f"[HEALTH] S3 check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
