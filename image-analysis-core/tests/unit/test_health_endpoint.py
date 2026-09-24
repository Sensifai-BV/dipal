"""Unit tests for the AI gateway health check endpoint."""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))


class TestCheckRedis(unittest.TestCase):
    """Tests for the _check_redis helper function."""

    def test_healthy_redis(self):
        """Healthy Redis returns status healthy with latency and memory."""
        from api_gateway.app.api.v1.endpoints.health import _check_redis

        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.client.info.return_value = {
            "used_memory": 5_000_000,
            "maxmemory": 100_000_000,
        }

        result = _check_redis(mock_client)

        self.assertEqual(result["status"], "healthy")
        self.assertIn("latency_ms", result)
        self.assertIsInstance(result["latency_ms"], float)
        self.assertAlmostEqual(result["memory_usage_percent"], 5.0, places=0)

    def test_redis_ping_false(self):
        """Redis ping returning False is reported as unhealthy."""
        from api_gateway.app.api.v1.endpoints.health import _check_redis

        mock_client = Mock()
        mock_client.ping.return_value = False

        result = _check_redis(mock_client)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("error", result)

    def test_redis_connection_error(self):
        """Redis connection error is reported as unhealthy."""
        from api_gateway.app.api.v1.endpoints.health import _check_redis

        mock_client = Mock()
        mock_client.ping.side_effect = ConnectionError("Connection refused")

        result = _check_redis(mock_client)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("Connection refused", result["error"])

    def test_redis_no_maxmemory(self):
        """Redis without maxmemory set returns None for memory_usage_percent."""
        from api_gateway.app.api.v1.endpoints.health import _check_redis

        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.client.info.return_value = {
            "used_memory": 5_000_000,
            "maxmemory": 0,
        }

        result = _check_redis(mock_client)

        self.assertEqual(result["status"], "healthy")
        self.assertIsNone(result["memory_usage_percent"])


class TestHealthEndpointRegistration(unittest.TestCase):
    """Tests for HealthAPIEndpoint class structure."""

    def test_router_has_health_tag(self):
        """Router is tagged with 'health'."""
        from api_gateway.app.api.v1.endpoints.health import HealthAPIEndpoint

        mock_deps = Mock()
        endpoint = HealthAPIEndpoint(deps=mock_deps)

        self.assertIn("health", endpoint.router.tags)

    def test_endpoint_has_router_property(self):
        """HealthAPIEndpoint exposes a router property."""
        from api_gateway.app.api.v1.endpoints.health import HealthAPIEndpoint

        mock_deps = Mock()
        endpoint = HealthAPIEndpoint(deps=mock_deps)

        self.assertIsNotNone(endpoint.router)


if __name__ == "__main__":
    unittest.main()
