"""Metrics endpoint and helpers for tracking job processing statistics.

Exposes a comprehensive ``GET /metrics/`` response designed to be scraped by
CloudWatch (via a periodic Lambda / cron) or any external monitoring system.
Counters survive process restarts because they are persisted in Redis through
the ``JobStateManager`` helper methods.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from lagom.integrations.fast_api import FastApiIntegration

from infrastructure.logging import get_logger
from infrastructure.state import JobStateManager

from ...base_endpoint import BaseEndpoint

logger = get_logger(__name__)

# In-memory counters are kept for backwards compatibility and fast access.
# They are *also* written to Redis so that metrics survive restarts.
_jobs_processed: int = 0
_jobs_failed: int = 0
_total_processing_seconds: float = 0.0

_startup_time = time.monotonic()
_started_at = datetime.now(timezone.utc).isoformat()

# Reference to the JobStateManager set once during endpoint registration.
_state_manager: JobStateManager | None = None


def _set_state_manager(manager: JobStateManager) -> None:
    """Called once at startup to inject the state manager."""
    global _state_manager
    _state_manager = manager


def record_job_completion(duration_seconds: float) -> None:
    """Record a successful job completion (in-memory + Redis)."""
    global _jobs_processed, _total_processing_seconds
    _jobs_processed += 1
    _total_processing_seconds += duration_seconds
    logger.info(f"Job completed in {duration_seconds:.1f}s (total processed: {_jobs_processed})")
    if _state_manager:
        _state_manager.record_job_metrics(duration_seconds, succeeded=True)


def record_job_failure() -> None:
    """Record a job failure (in-memory + Redis)."""
    global _jobs_failed
    _jobs_failed += 1
    logger.info(f"Job failed (total failed: {_jobs_failed})")
    if _state_manager:
        _state_manager.record_job_metrics(0.0, succeeded=False)


def record_queue_wait(wait_seconds: float) -> None:
    """Record how long a job waited in queue before processing started."""
    if _state_manager:
        _state_manager.record_queue_wait(wait_seconds)


_PROCESSING_STAGES = [
    "radiometric_calibration",
    "sfm",
    "orthomosaic",
    "uploading",
]


class MetricsAPIEndpoint(BaseEndpoint):
    """Metrics endpoint exposing comprehensive KPI data."""

    def __init__(self, deps: FastApiIntegration):
        self.deps = deps
        self._router = APIRouter(tags=["metrics"])

    @property
    def router(self) -> APIRouter:
        return self._router

    def register_api(self):
        @self._router.get("/metrics/")
        async def get_metrics(
            job_state_manager: JobStateManager = self.deps.depends(JobStateManager),
        ):
            """Return comprehensive processing metrics for CloudWatch ingestion."""
            # Inject the state manager on first call
            _set_state_manager(job_state_manager)

            # ----------------------------------------------------------
            # 1. Read Redis-persisted counters (survive restarts)
            # ----------------------------------------------------------
            redis_metrics = job_state_manager.get_metrics_summary()

            # Prefer Redis counters; fall back to in-memory
            jobs_processed = int(redis_metrics.get("jobs_processed", _jobs_processed))
            jobs_failed = int(redis_metrics.get("jobs_failed", _jobs_failed))
            total_seconds = float(redis_metrics.get("total_processing_seconds", _total_processing_seconds))

            avg_time = round(total_seconds / jobs_processed, 2) if jobs_processed > 0 else 0.0
            uptime = time.monotonic() - _startup_time

            # ----------------------------------------------------------
            # 2. Throughput (simple: total completed / uptime hours)
            # ----------------------------------------------------------
            uptime_hours = uptime / 3600
            throughput_per_hour = round(jobs_processed / uptime_hours, 2) if uptime_hours > 0 else 0.0

            # ----------------------------------------------------------
            # 3. Per-stage duration aggregates
            # ----------------------------------------------------------
            stage_durations = {}
            for stage_name in _PROCESSING_STAGES:
                total_key = f"stage:{stage_name}:total_seconds"
                count_key = f"stage:{stage_name}:count"
                total = float(redis_metrics.get(total_key, 0))
                count = int(redis_metrics.get(count_key, 0))
                avg = round(total / count, 2) if count > 0 else 0.0
                stage_durations[stage_name] = {
                    "avg_seconds": avg,
                    "total_seconds": round(total, 2),
                    "count": count,
                }

            # ----------------------------------------------------------
            # 4. Queue wait time aggregates
            # ----------------------------------------------------------
            qw_total = float(redis_metrics.get("queue_wait_total_seconds", 0))
            qw_count = int(redis_metrics.get("queue_wait_count", 0))
            queue_wait = {
                "avg_seconds": round(qw_total / qw_count, 2) if qw_count > 0 else 0.0,
                "total_seconds": round(qw_total, 2),
                "count": qw_count,
            }

            # ----------------------------------------------------------
            # 5. Active jobs
            # ----------------------------------------------------------
            active_jobs = job_state_manager.count_active_jobs()

            return {
                "uptime": {
                    "uptime_seconds": round(uptime),
                    "started_at": _started_at,
                },
                "processing": {
                    "jobs_processed": jobs_processed,
                    "jobs_failed": jobs_failed,
                    "jobs_in_progress": active_jobs,
                    "total_processing_seconds": round(total_seconds, 2),
                    "average_processing_seconds": avg_time,
                    "throughput_per_hour": throughput_per_hour,
                    "stage_durations": stage_durations,
                    "queue_wait": queue_wait,
                },
            }
