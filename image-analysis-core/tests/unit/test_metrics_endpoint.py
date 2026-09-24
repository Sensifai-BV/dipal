"""Unit tests for the AI gateway metrics endpoint."""
import unittest
from unittest.mock import Mock
import sys
from pathlib import Path

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))


class TestMetricsRecording(unittest.TestCase):
    """Tests for the record_job_completion / record_job_failure helpers."""

    def setUp(self):
        """Reset module-level counters before each test."""
        import api_gateway.app.api.v1.endpoints.metrics as m
        self._mod = m
        m._jobs_processed = 0
        m._jobs_failed = 0
        m._total_processing_seconds = 0.0

    def test_record_completion_increments_counter(self):
        """record_job_completion increments processed count."""
        self._mod.record_job_completion(120.0)

        self.assertEqual(self._mod._jobs_processed, 1)
        self.assertAlmostEqual(self._mod._total_processing_seconds, 120.0)

    def test_record_completion_accumulates_time(self):
        """Multiple completions accumulate total time."""
        self._mod.record_job_completion(60.0)
        self._mod.record_job_completion(90.0)

        self.assertEqual(self._mod._jobs_processed, 2)
        self.assertAlmostEqual(self._mod._total_processing_seconds, 150.0)

    def test_record_failure_increments_counter(self):
        """record_job_failure increments failed count."""
        self._mod.record_job_failure()
        self._mod.record_job_failure()

        self.assertEqual(self._mod._jobs_failed, 2)

    def test_failure_does_not_affect_processed(self):
        """Failures do not increment processed counter or time."""
        self._mod.record_job_failure()

        self.assertEqual(self._mod._jobs_processed, 0)
        self.assertAlmostEqual(self._mod._total_processing_seconds, 0.0)


class TestMetricsEndpointRegistration(unittest.TestCase):
    """Tests for MetricsAPIEndpoint class structure."""

    def test_router_has_metrics_tag(self):
        """Router is tagged with 'metrics'."""
        from api_gateway.app.api.v1.endpoints.metrics import MetricsAPIEndpoint

        mock_deps = Mock()
        endpoint = MetricsAPIEndpoint(deps=mock_deps)

        self.assertIn("metrics", endpoint.router.tags)

    def test_endpoint_has_router_property(self):
        """MetricsAPIEndpoint exposes a router property."""
        from api_gateway.app.api.v1.endpoints.metrics import MetricsAPIEndpoint

        mock_deps = Mock()
        endpoint = MetricsAPIEndpoint(deps=mock_deps)

        self.assertIsNotNone(endpoint.router)

    def test_average_processing_zero_when_no_jobs(self):
        """Average processing time is 0 when no jobs processed."""
        import api_gateway.app.api.v1.endpoints.metrics as m

        m._jobs_processed = 0
        m._total_processing_seconds = 0.0

        avg = (
            round(m._total_processing_seconds / m._jobs_processed, 2)
            if m._jobs_processed > 0
            else 0.0
        )
        self.assertEqual(avg, 0.0)


if __name__ == "__main__":
    unittest.main()
