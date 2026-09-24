"""Unit tests for the HealthCheckView endpoint."""
import time
import unittest
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from rest_framework import status

from apps.jobs.api.views.health import HealthCheckView


class TestHealthCheckView(TestCase):
    """Tests for GET /health/"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = HealthCheckView.as_view()

    @patch.object(HealthCheckView, '_check_celery')
    @patch.object(HealthCheckView, '_check_redis')
    @patch.object(HealthCheckView, '_check_database')
    def test_healthy_response(self, mock_db, mock_redis, mock_celery):
        """All checks pass returns 200 with healthy status."""
        mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
        mock_redis.return_value = {"status": "healthy", "latency_ms": 2.0, "memory_usage_percent": 30.0}
        mock_celery.return_value = {"status": "healthy", "latency_ms": 5.0, "workers": 1}

        request = self.factory.get('/health/')
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["service"], "photogear-backend")
        self.assertIn("version", response.data)
        self.assertIn("timestamp", response.data)
        self.assertIn("uptime_seconds", response.data)
        self.assertIn("checks", response.data)

    @patch.object(HealthCheckView, '_check_celery')
    @patch.object(HealthCheckView, '_check_redis')
    @patch.object(HealthCheckView, '_check_database')
    def test_unhealthy_database_returns_503(self, mock_db, mock_redis, mock_celery):
        """Database failure returns 503 with unhealthy status."""
        mock_db.return_value = {"status": "unhealthy", "error": "Connection refused"}
        mock_redis.return_value = {"status": "healthy", "latency_ms": 2.0, "memory_usage_percent": 30.0}
        mock_celery.return_value = {"status": "healthy", "latency_ms": 5.0, "workers": 1}

        request = self.factory.get('/health/')
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")

    @patch.object(HealthCheckView, '_check_celery')
    @patch.object(HealthCheckView, '_check_redis')
    @patch.object(HealthCheckView, '_check_database')
    def test_unhealthy_redis_returns_503(self, mock_db, mock_redis, mock_celery):
        """Redis failure returns 503 with unhealthy status."""
        mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
        mock_redis.return_value = {"status": "unhealthy", "error": "Could not connect"}
        mock_celery.return_value = {"status": "healthy", "latency_ms": 5.0, "workers": 1}

        request = self.factory.get('/health/')
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")

    @patch.object(HealthCheckView, '_check_celery')
    @patch.object(HealthCheckView, '_check_redis')
    @patch.object(HealthCheckView, '_check_database')
    def test_degraded_celery_returns_200(self, mock_db, mock_redis, mock_celery):
        """Celery failure with other checks healthy returns degraded (200)."""
        mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
        mock_redis.return_value = {"status": "healthy", "latency_ms": 2.0, "memory_usage_percent": 30.0}
        mock_celery.return_value = {"status": "unhealthy", "error": "No workers responding"}

        request = self.factory.get('/health/')
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "degraded")

    @patch.object(HealthCheckView, '_check_celery')
    @patch.object(HealthCheckView, '_check_redis')
    @patch.object(HealthCheckView, '_check_database')
    def test_no_auth_required(self, mock_db, mock_redis, mock_celery):
        """Health check does not require authentication."""
        mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
        mock_redis.return_value = {"status": "healthy", "latency_ms": 2.0, "memory_usage_percent": None}
        mock_celery.return_value = {"status": "healthy", "latency_ms": 5.0, "workers": 1}

        request = self.factory.get('/health/')
        response = self.view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch.object(HealthCheckView, '_check_celery')
    @patch.object(HealthCheckView, '_check_redis')
    @patch.object(HealthCheckView, '_check_database')
    def test_response_contains_all_fields(self, mock_db, mock_redis, mock_celery):
        """Response JSON has all required fields."""
        mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
        mock_redis.return_value = {"status": "healthy", "latency_ms": 2.0, "memory_usage_percent": 50.0}
        mock_celery.return_value = {"status": "healthy", "latency_ms": 5.0, "workers": 2}

        request = self.factory.get('/health/')
        response = self.view(request)

        self.assertIn("status", response.data)
        self.assertIn("service", response.data)
        self.assertIn("version", response.data)
        self.assertIn("timestamp", response.data)
        self.assertIn("uptime_seconds", response.data)
        self.assertIn("checks", response.data)
        self.assertIn("database", response.data["checks"])
        self.assertIn("redis", response.data["checks"])
        self.assertIn("celery", response.data["checks"])


if __name__ == "__main__":
    unittest.main()
