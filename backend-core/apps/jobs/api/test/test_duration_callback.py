"""Tests for AI callback view - started_at / completed_at and duration."""
import unittest
from datetime import timedelta

from django.test import TestCase, RequestFactory
from django.utils import timezone
from rest_framework import status

from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.api.serializer import ProcessingJobListSerializer
from apps.uploads.infrastructure.models import Dataset
from accounts.models import Organization, UserModel


class TestJobDuration(TestCase):
    """Tests for ProcessingJobListSerializer.get_duration() using started_at/completed_at."""

    def setUp(self):
        self.user = UserModel.objects.create_user(
            email="duration@test.com", password="testpass123"
        )
        self.org = Organization.objects.create(name="Duration Org", user=self.user)
        self.dataset = Dataset.objects.create(
            name="Duration Dataset", org=self.org, crs="EPSG:4326"
        )

    def test_pending_job_returns_dash(self):
        """Pending job should return '-' for duration."""
        job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="pending",
        )
        serializer = ProcessingJobListSerializer(job)
        self.assertEqual(serializer.data["duration"], "-")

    def test_completed_job_uses_started_and_completed_at(self):
        """Completed job duration uses started_at and completed_at."""
        now = timezone.now()
        job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="completed",
            stage="completed",
            progress=100,
        )
        job.started_at = now - timedelta(hours=2, minutes=30)
        job.completed_at = now
        job.save(update_fields=['started_at', 'completed_at'])

        serializer = ProcessingJobListSerializer(job)
        self.assertEqual(serializer.data["duration"], "2h 30m")

    def test_failed_job_uses_completed_at(self):
        """Failed job duration uses completed_at as end time."""
        now = timezone.now()
        job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="failed",
            stage="failed",
        )
        job.started_at = now - timedelta(minutes=10)
        job.completed_at = now
        job.save(update_fields=['started_at', 'completed_at'])

        serializer = ProcessingJobListSerializer(job)
        self.assertEqual(serializer.data["duration"], "0h 10m")

    def test_running_job_uses_now_as_end(self):
        """Running job uses current time as end."""
        job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="processing",
            stage="sfm",
        )
        job.started_at = timezone.now() - timedelta(hours=1)
        job.save(update_fields=['started_at'])

        serializer = ProcessingJobListSerializer(job)
        duration = serializer.data["duration"]
        self.assertIn("1h", duration)

    def test_job_without_started_at_falls_back_to_created_at(self):
        """If started_at is None, falls back to created_at."""
        job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="processing",
            stage="sfm",
        )
        self.assertIsNone(job.started_at)

        serializer = ProcessingJobListSerializer(job)
        duration = serializer.data["duration"]
        self.assertIn("h", duration)
        self.assertIn("m", duration)


class TestAICallbackSetsTimestamps(TestCase):
    """Tests for AI callback setting started_at and completed_at."""

    def setUp(self):
        self.user = UserModel.objects.create_user(
            email="callback@test.com", password="testpass123"
        )
        self.org = Organization.objects.create(name="Callback Org", user=self.user)
        self.dataset = Dataset.objects.create(
            name="Callback Dataset", org=self.org, crs="EPSG:4326"
        )

    def test_completion_callback_sets_completed_at(self):
        """_handle_completion sets completed_at timestamp."""
        from apps.jobs.api.views.ai_callback import AICallbackView

        job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="processing",
            stage="orthomosaic",
        )
        self.assertIsNone(job.completed_at)

        view = AICallbackView()
        view._handle_completion(job, {"outputs": {}, "metadata": {}})

        job.refresh_from_db()
        self.assertIsNotNone(job.completed_at)
        self.assertEqual(job.status, "completed")

    def test_error_callback_sets_completed_at(self):
        """_handle_error sets completed_at timestamp."""
        from apps.jobs.api.views.ai_callback import AICallbackView

        job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="processing",
            stage="sfm",
        )
        self.assertIsNone(job.completed_at)

        view = AICallbackView()
        view._handle_error(job, {
            "error_message": "SFM failed",
            "error_details": {"service": "sfm"},
        })

        job.refresh_from_db()
        self.assertIsNotNone(job.completed_at)
        self.assertEqual(job.status, "failed")


if __name__ == "__main__":
    unittest.main()
