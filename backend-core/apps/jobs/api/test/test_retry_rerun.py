"""Unit tests for Job Rerun View"""
import unittest
from unittest.mock import patch, MagicMock
import uuid

from django.test import TestCase, RequestFactory
from django.conf import settings
from rest_framework import status
from rest_framework.test import force_authenticate

from apps.jobs.api.views.job_rerun_view import JobRerunView
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.uploads.infrastructure.models import Dataset
from accounts.models import Organization, UserModel


class TestJobRerunView(TestCase):
    """Tests for POST /api/jobs/{job_id}/rerun/"""

    def setUp(self):
        self.factory = RequestFactory()

        self.user = UserModel.objects.create_user(
            email="rerun@example.com",
            password="testpass123"
        )
        self.org = Organization.objects.create(
            name="Rerun Test Org",
            user=self.user
        )
        self.user.organization = self.org
        self.user.save()

        self.dataset = Dataset.objects.create(
            name="Test Dataset",
            org=self.org,
            crs="EPSG:4326"
        )

        self.failed_job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            radiometric_calibration=False,
            analysis_mode="fast",
            status="failed",
            stage="orthomosaic",
            progress=60,
            error_message="Orthomosaic timeout",
            can_retry=True,
        )

    def _post_rerun(self, job_id, query_params=None, user=None):
        url = f"/api/jobs/{job_id}/rerun/"
        if query_params:
            url += "?" + "&".join(f"{k}={v}" for k, v in query_params.items())
        request = self.factory.post(url)
        force_authenticate(request, user=user or self.user)
        view = JobRerunView.as_view()
        return view(request, job_id=job_id)

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery")
    def test_rerun_resets_job_and_pushes_to_celery(self, mock_celery):
        response = self._post_rerun(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.failed_job.refresh_from_db()
        self.assertEqual(self.failed_job.status, "queued")
        self.assertEqual(self.failed_job.stage, "queued")
        self.assertEqual(self.failed_job.progress, 0)
        self.assertIsNone(self.failed_job.error_message)

        mock_celery.delay.assert_called_once_with(str(self.failed_job.id))

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery")
    def test_rerun_with_resume_passes_starting_stage(self, mock_celery):
        response = self._post_rerun(
            self.failed_job.id, query_params={"resume": "true"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["resume_from"], "orthomosaic")

        mock_celery.delay.assert_called_once_with(
            str(self.failed_job.id), starting_stage="orthomosaic"
        )

    def test_rerun_returns_404_for_unknown_job(self):
        response = self._post_rerun(uuid.uuid4())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_rerun_returns_404_for_job_from_other_org(self):
        other_user = UserModel.objects.create_user(
            email="other2@example.com", password="testpass123"
        )
        other_org = Organization.objects.create(name="Other Org 2", user=other_user)
        other_user.organization = other_org
        other_user.save()

        response = self._post_rerun(self.failed_job.id, user=other_user)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery")
    def test_rerun_preserves_job_id(self, mock_celery):
        original_id = self.failed_job.id

        response = self._post_rerun(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], str(original_id))

        self.failed_job.refresh_from_db()
        self.assertEqual(self.failed_job.id, original_id)

    def test_rerun_requires_authentication(self):
        """Rerun endpoint should reject unauthenticated requests."""
        request = self.factory.post(f"/api/jobs/{self.failed_job.id}/rerun/")
        view = JobRerunView.as_view()
        response = view(request, job_id=self.failed_job.id)

        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery")
    def test_rerun_with_resume_clears_error_message(self, mock_celery):
        """Rerun with resume=true should still clear error_message."""
        self.failed_job.error_message = "Old pipeline error"
        self.failed_job.save()

        response = self._post_rerun(
            self.failed_job.id, query_params={"resume": "true"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.failed_job.refresh_from_db()
        self.assertIsNone(self.failed_job.error_message)

    def test_rerun_rejects_non_failed_job(self):
        """Only failed or cancelled jobs can be rerun."""
        self.failed_job.status = "processing"
        self.failed_job.save()

        response = self._post_rerun(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot retry job", response.data["error"])

    def test_rerun_rejects_non_retryable_job(self):
        """Jobs with can_retry=False should be rejected."""
        self.failed_job.can_retry = False
        self.failed_job.save()

        response = self._post_rerun(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be retried", response.data["error"])

    def test_rerun_respects_max_retries_limit(self):
        """Job should be rejected after MAX_RETRIES (3) attempts."""
        self.failed_job.retry_count = 3
        self.failed_job.save()

        response = self._post_rerun(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Maximum retry limit", response.data["error"])

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery")
    def test_rerun_increments_retry_count(self, mock_celery):
        """Each rerun should increment retry_count."""
        self.failed_job.retry_count = 1
        self.failed_job.save()

        response = self._post_rerun(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.failed_job.refresh_from_db()
        self.assertEqual(self.failed_job.retry_count, 2)
        self.assertEqual(response.data["retry_count"], 2)

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery")
    def test_rerun_allows_cancelled_job(self, mock_celery):
        """Cancelled jobs should also be eligible for rerun."""
        self.failed_job.status = "cancelled"
        self.failed_job.save()

        response = self._post_rerun(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.failed_job.refresh_from_db()
        self.assertEqual(self.failed_job.status, "queued")

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery")
    def test_rerun_response_contains_dataset_info(self, mock_celery):
        """Response should include dataset id and name."""
        response = self._post_rerun(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["dataset"]["id"], str(self.dataset.id))
        self.assertEqual(response.data["dataset"]["name"], self.dataset.name)

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery")
    def test_rerun_resume_with_queued_stage_starts_from_beginning(self, mock_celery):
        """Resume with stage=queued should start from beginning."""
        self.failed_job.stage = "queued"
        self.failed_job.save()

        response = self._post_rerun(
            self.failed_job.id, query_params={"resume": "true"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["resume_from"])
        mock_celery.delay.assert_called_once_with(str(self.failed_job.id))

    def test_rerun_rejects_user_without_organization(self):
        """User without organization should get 400."""
        orphan_user = UserModel.objects.create_user(
            email="orphan@example.com", password="testpass123"
        )

        response = self._post_rerun(self.failed_job.id, user=orphan_user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("organization", response.data["error"].lower())


class TestAICallbackView(TestCase):
    """Tests for AI callback endpoint clearing error_message on completion."""

    def setUp(self):
        self.factory = RequestFactory()

        self.user = UserModel.objects.create_user(
            email="callback@example.com",
            password="testpass123"
        )
        self.org = Organization.objects.create(
            name="Callback Test Org",
            user=self.user
        )

        self.dataset = Dataset.objects.create(
            name="Test Dataset",
            org=self.org,
            crs="EPSG:4326"
        )

        self.job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            radiometric_calibration=False,
            analysis_mode="full",
            status="failed",
            stage="sfm",
            progress=30,
            error_message="Pipeline error after sfm stage: Orthomosaic service unavailable",
        )

    @patch.object(settings, 'AI_GATEWAY_SECRET_KEY', 'test-secret-key')
    def test_completion_callback_clears_error_message(self):
        """Successful completion callback should clear old error_message."""
        from apps.jobs.api.views.ai_callback import AICallbackView

        request = self.factory.post(
            '/v1/api/jobs/ai-callback/',
            data={
                'job_id': str(self.job.id),
                'type': 'complete',
                'outputs': {},
            },
            content_type='application/json',
            HTTP_X_API_SECRET_KEY='test-secret-key',
        )

        view = AICallbackView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')
        self.assertIsNone(self.job.error_message)
        self.assertEqual(self.job.progress, 100)

    @patch.object(settings, 'AI_GATEWAY_SECRET_KEY', 'test-secret-key')
    def test_error_callback_sets_error_message(self):
        """Error callback should set the error_message."""
        from apps.jobs.api.views.ai_callback import AICallbackView

        request = self.factory.post(
            '/v1/api/jobs/ai-callback/',
            data={
                'job_id': str(self.job.id),
                'type': 'error',
                'error_message': 'New pipeline failure',
            },
            content_type='application/json',
            HTTP_X_API_SECRET_KEY='test-secret-key',
        )

        view = AICallbackView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertEqual(self.job.error_message, 'New pipeline failure')

    @patch.object(settings, 'AI_GATEWAY_SECRET_KEY', 'test-secret-key')
    def test_upload_status_all_success(self):
        """Upload status callback with no failures keeps job completed."""
        from apps.jobs.api.views.ai_callback import AICallbackView

        self.job.status = 'completed'
        self.job.stage = 'completed'
        self.job.progress = 100
        self.job.error_message = None
        self.job.save()

        request = self.factory.post(
            '/v1/api/jobs/ai-callback/',
            data={
                'job_id': str(self.job.id),
                'type': 'upload_status',
                'uploaded': [
                    {'product_type': 'orthomosaic', 'product_id': 'p1'},
                    {'product_type': 'dsm', 'product_id': 'p2'},
                ],
                'failed': [],
            },
            content_type='application/json',
            HTTP_X_API_SECRET_KEY='test-secret-key',
        )

        view = AICallbackView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')
        self.assertIsNone(self.job.error_message)

    @patch.object(settings, 'AI_GATEWAY_SECRET_KEY', 'test-secret-key')
    def test_upload_status_with_failures_marks_failed(self):
        """Upload status callback with failures marks job FAILED."""
        from apps.jobs.api.views.ai_callback import AICallbackView

        self.job.status = 'completed'
        self.job.stage = 'completed'
        self.job.progress = 100
        self.job.error_message = None
        self.job.save()

        request = self.factory.post(
            '/v1/api/jobs/ai-callback/',
            data={
                'job_id': str(self.job.id),
                'type': 'upload_status',
                'uploaded': [
                    {'product_type': 'dsm', 'product_id': 'p2'},
                ],
                'failed': [
                    {'product_type': 'orthomosaic', 'error': 'timeout'},
                    {'product_type': 'mesh', 'error': 'file not found'},
                ],
            },
            content_type='application/json',
            HTTP_X_API_SECRET_KEY='test-secret-key',
        )

        view = AICallbackView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'failed')
        self.assertIn('orthomosaic', self.job.error_message)
        self.assertIn('mesh', self.job.error_message)


if __name__ == "__main__":
    unittest.main()
