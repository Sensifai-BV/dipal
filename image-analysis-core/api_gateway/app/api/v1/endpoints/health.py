from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config as BotoConfig
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.logging import get_logger
from infrastructure.redis import RedisClient
from infrastructure.state import JobStateManager
from infrastructure.storage.s3_settings import S3StorageSettings

from ...base_endpoint import BaseEndpoint

logger = get_logger(__name__)

_startup_time = time.monotonic()


def _read_version() -> str:
    """
    Read the project version from pyproject.toml.

    Returns:
        Version string from [project] section
    """
    pyproject_path = Path(__file__).resolve().parents[5] / "pyproject.toml"
    for line in pyproject_path.read_text().splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


_SERVICE_VERSION = _read_version()


class HealthAPIEndpoint(BaseEndpoint):
    """Health check endpoint returning service status and dependency checks."""

    def __init__(self, deps: FastApiIntegration):
        self.deps = deps
        self._router = APIRouter(tags=["health"])

    @property
    def router(self) -> APIRouter:
        return self._router

    def register_api(self):
        @self._router.get("/health/")
        async def health_check(
            redis_client: RedisClient = self.deps.depends(RedisClient),
            s3_settings: S3StorageSettings = self.deps.depends(S3StorageSettings),
        ):
            """Return health status with dependency checks."""
            checks = {}
            overall = "healthy"

            checks["redis"] = _check_redis(redis_client)
            if checks["redis"]["status"] == "unhealthy":
                overall = "unhealthy"

            checks["s3"] = _check_s3(s3_settings)
            if checks["s3"]["status"] == "unhealthy":
                overall = "degraded"

            status_code = 200 if overall != "unhealthy" else 503
            uptime = time.monotonic() - _startup_time

            return JSONResponse(
                content={
                    "status": overall,
                    "service": "photogear-ai-gateway",
                    "version": _SERVICE_VERSION,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "uptime_seconds": round(uptime),
                    "checks": checks,
                },
                status_code=status_code,
            )


def _check_redis(redis_client: RedisClient) -> dict:
    """Check Redis connectivity and memory usage."""
    try:
        start = time.monotonic()
        alive = redis_client.ping()
        latency = (time.monotonic() - start) * 1000

        if not alive:
            return {"status": "unhealthy", "error": "ping returned False"}

        info = redis_client.client.info("memory")
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


def _check_s3(settings: S3StorageSettings) -> dict:
    """Check S3 connectivity by verifying all configured buckets are reachable."""
    import os

    buckets = {
        "raw_images": settings.raw_images_bucket,
        "ai": settings.ai_bucket,
        "results": settings.results_bucket,
    }

    env_key = os.environ.get("AWS_S3_ACCESS_KEY_ID")
    env_secret = os.environ.get("AWS_S3_SECRET_ACCESS_KEY")
    cred_source = _detect_credential_source(settings)

    try:
        session_kwargs: dict = {"region_name": settings.region_name}
        if settings.has_explicit_credentials:
            session_kwargs["aws_access_key_id"] = settings.access_key_id
            session_kwargs["aws_secret_access_key"] = settings.secret_access_key

        start = time.monotonic()
        session = boto3.Session(**session_kwargs)
        credentials = session.get_credentials()
        latency = (time.monotonic() - start) * 1000

        if credentials is None:
            logger.error(
                f"[HEALTH] boto3 session resolved NO credentials. "
                f"use_aws_role={settings.use_aws_role}, "
                f"has_explicit_creds={settings.has_explicit_credentials}, "
                f"env AWS_S3_ACCESS_KEY_ID={'set' if env_key else 'NOT SET'}, "
                f"AWS_CONTAINER_CREDENTIALS_RELATIVE_URI set="
                f"{bool(os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI'))}, "
                f"AWS_PROFILE={os.environ.get('AWS_PROFILE', 'unset')}"
            )
            return {
                "status": "unhealthy",
                "error": "AWS credentials not found",
                "credential_source": cred_source,
                "hint": _credential_hint(settings),
            }

        resolved = credentials.get_frozen_credentials()
        logger.info(
            f"[HEALTH] boto3 credentials resolved: method={resolved.method if hasattr(resolved, 'method') else 'unknown'}, "
            f"access_key_prefix={resolved.access_key[:4] + '...' if resolved.access_key else 'None'}"
        )

        client = session.client(
            "s3",
            config=BotoConfig(
                connect_timeout=3,
                read_timeout=3,
                retries={"max_attempts": 0},
            ),
        )

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
            "credential_source": cred_source,
            "buckets": bucket_status,
        }
    except NoCredentialsError:
        logger.error(
            f"[HEALTH] S3 check failed: no credentials. "
            f"use_aws_role={settings.use_aws_role}, "
            f"has_explicit_creds={settings.has_explicit_credentials}, "
            f"credential_source={cred_source}"
        )
        return {
            "status": "unhealthy",
            "error": "AWS credentials not found",
            "credential_source": cred_source,
            "hint": _credential_hint(settings),
        }
    except Exception as e:
        logger.error(f"[HEALTH] S3 check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


def _detect_credential_source(settings: S3StorageSettings) -> str:
    """Detect which credential source boto3 would use."""
    import os

    if settings.has_explicit_credentials:
        return "explicit_env_vars (AWS_S3_ACCESS_KEY_ID)"
    if os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"):
        return "ecs_task_role"
    if os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE"):
        return "web_identity_token (EKS)"
    if Path.home().joinpath(".aws", "credentials").exists():
        return "shared_credentials_file (~/.aws/credentials)"
    if settings.use_aws_role:
        return "aws_role (USE_AWS_ROLE=true but no metadata endpoint detected)"
    return "none_detected"


def _credential_hint(settings: S3StorageSettings) -> str:
    """Provide actionable hint for credential issues."""
    if settings.use_aws_role:
        return (
            "USE_AWS_ROLE=true but boto3 cannot find credentials. "
            "Ensure the ECS task has an IAM role attached, or that "
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI is set in the container."
        )
    return (
        "Set AWS_S3_ACCESS_KEY_ID and AWS_S3_SECRET_ACCESS_KEY in .env, "
        "or set USE_AWS_ROLE=true if running on AWS with an IAM role."
    )
