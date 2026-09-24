"""Metrics endpoint for the backend service.

Exposes comprehensive KPI data designed to be scraped by CloudWatch
(via a periodic Lambda / cron) or any external monitoring dashboard.
"""
import time
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import connection
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import ExtractHour
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus
from config.logging_config import get_logger

logger = get_logger(__name__)

_startup_time = time.monotonic()
_started_at = datetime.now(timezone.utc).isoformat()
_SERVICE_VERSION = "0.9.0"

# Redis key for auth failure tracking
_AUTH_FAILURES_KEY = "photogear:backend:auth_failures"


def record_auth_failure() -> None:
    """Increment auth failure counter in Redis with hourly buckets."""
    try:
        import redis as redis_lib

        client = redis_lib.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)
        now = datetime.now(timezone.utc)
        hour_key = f"{_AUTH_FAILURES_KEY}:{now.strftime('%Y%m%d%H')}"
        pipe = client.pipeline()
        pipe.incr(hour_key)
        pipe.expire(hour_key, 90 * 24 * 3600)  # keep 90 days
        pipe.incr(f"{_AUTH_FAILURES_KEY}:total")
        pipe.execute()
    except Exception as e:
        logger.warning(f"Failed to record auth failure metric: {e}")


def _get_auth_failure_counts() -> dict:
    """Read auth failure counts from Redis."""
    try:
        import redis as redis_lib

        client = redis_lib.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)
        now = datetime.now(timezone.utc)

        # Last 1 hour
        current_hour_key = f"{_AUTH_FAILURES_KEY}:{now.strftime('%Y%m%d%H')}"
        failures_1h = int(client.get(current_hour_key) or 0)

        # Last 24 hours
        failures_24h = 0
        for i in range(24):
            dt = now - timedelta(hours=i)
            key = f"{_AUTH_FAILURES_KEY}:{dt.strftime('%Y%m%d%H')}"
            failures_24h += int(client.get(key) or 0)

        total = int(client.get(f"{_AUTH_FAILURES_KEY}:total") or 0)

        return {
            "auth_failures_1h": failures_1h,
            "auth_failures_24h": failures_24h,
            "auth_failures_total": total,
        }
    except Exception as e:
        logger.warning(f"Failed to read auth failure metrics: {e}")
        return {
            "auth_failures_1h": 0,
            "auth_failures_24h": 0,
            "auth_failures_total": 0,
        }


class MetricsView(APIView):
    """
    Metrics endpoint returning comprehensive KPI data.

    No authentication required — designed to be scraped by monitoring tools.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Metrics",
        description=(
            "Returns comprehensive KPI metrics including uptime, processing "
            "time statistics, job throughput, and security event counters."
        ),
        tags=["Metrics"],
    )
    def get(self, request):
        """Return KPI metrics."""
        now = datetime.now(timezone.utc)
        uptime = time.monotonic() - _startup_time

        # ----------------------------------------------------------
        # 1. Uptime
        # ----------------------------------------------------------
        uptime_info = {
            "uptime_seconds": round(uptime),
            "started_at": _started_at,
            "version": _SERVICE_VERSION,
        }
        try:
            from config.celery import app as celery_app

            result = celery_app.control.ping(timeout=2)
            uptime_info["celery_workers"] = len(result) if result else 0
        except Exception:
            uptime_info["celery_workers"] = 0

        # ----------------------------------------------------------
        # 2. Job counts by status
        # ----------------------------------------------------------
        status_counts = dict(
            ProcessingJob.objects.values_list("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )
        total_jobs = sum(status_counts.values())

        # ----------------------------------------------------------
        # 3. Processing time stats (from completed jobs)
        # ----------------------------------------------------------
        completed_qs = ProcessingJob.objects.filter(
            status=JobStatus.COMPLETED,
            started_at__isnull=False,
            completed_at__isnull=False,
        )

        processing_agg = completed_qs.aggregate(
            avg_duration=Avg(F("completed_at") - F("started_at")),
            count=Count("id"),
        )
        avg_processing_secs = 0.0
        if processing_agg["avg_duration"]:
            avg_processing_secs = round(processing_agg["avg_duration"].total_seconds(), 2)

        # ----------------------------------------------------------
        # 4. Queue wait time stats (created_at → started_at)
        # ----------------------------------------------------------
        with_started = ProcessingJob.objects.filter(
            started_at__isnull=False,
        )
        queue_agg = with_started.aggregate(
            avg_wait=Avg(F("started_at") - F("created_at")),
            count=Count("id"),
        )
        avg_queue_wait_secs = 0.0
        if queue_agg["avg_wait"]:
            avg_queue_wait_secs = round(queue_agg["avg_wait"].total_seconds(), 2)

        # ----------------------------------------------------------
        # 5. Throughput
        # ----------------------------------------------------------
        completed_1h = ProcessingJob.objects.filter(
            status=JobStatus.COMPLETED,
            completed_at__gte=now - timedelta(hours=1),
        ).count()

        completed_24h = ProcessingJob.objects.filter(
            status=JobStatus.COMPLETED,
            completed_at__gte=now - timedelta(hours=24),
        ).count()

        throughput_per_hour_24h = round(completed_24h / 24, 2) if completed_24h else 0.0

        # ----------------------------------------------------------
        # 6. Failed jobs stats
        # ----------------------------------------------------------
        failed_24h = ProcessingJob.objects.filter(
            status=JobStatus.FAILED,
            completed_at__gte=now - timedelta(hours=24),
        ).count()

        # ----------------------------------------------------------
        # 7. Security events
        # ----------------------------------------------------------
        security = _get_auth_failure_counts()

        return Response({
            "uptime": uptime_info,
            "processing": {
                "total_jobs": total_jobs,
                "by_status": status_counts,
                "avg_processing_seconds": avg_processing_secs,
                "completed_jobs": processing_agg["count"],
                "avg_queue_wait_seconds": avg_queue_wait_secs,
                "throughput": {
                    "completed_last_1h": completed_1h,
                    "completed_last_24h": completed_24h,
                    "per_hour_24h": throughput_per_hour_24h,
                },
                "failed_last_24h": failed_24h,
            },
            "security": security,
        })


class DetailedMetricsView(APIView):
    """
    Prometheus metrics endpoint.

    Returns metrics collected by django-prometheus middleware in Prometheus
    text exposition format, suitable for scraping by Prometheus server.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Detailed Prometheus Metrics",
        description=(
            "Returns Prometheus-format metrics collected by django-prometheus "
            "middleware, including HTTP request/response counts, latencies, "
            "and database query metrics."
        ),
        tags=["Metrics"],
        responses={
            (200, "text/plain"): {
                "type": "string",
                "description": "Prometheus text exposition format metrics",
            }
        },
    )
    def get(self, request):
        """Return Prometheus metrics in text exposition format."""
        from django.http import HttpResponse
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

        return HttpResponse(
            generate_latest(),
            content_type=CONTENT_TYPE_LATEST,
        )
