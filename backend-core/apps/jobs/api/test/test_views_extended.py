"""Unit tests for AI callback view, job cancel view, and start processing view."""
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory, override_settings
from rest_framework import status
from rest_framework.test import force_authenticate

from apps.jobs.api.views.ai_callback import AICallbackView
from apps.jobs.api.views.job_cancel_view import JobCancelView
from apps.jobs.api.views.views import StartProcessingView
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus, ProcessingStage
from apps.uploads.infrastructure.models import Dataset
from accounts.models import Organization, UserModel


class TestAICallbackView(TestCase):
    """Tests for POST /api/ai-callback/"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = AICallbackView.as_view()
        self.user = UserModel.objects.create_user(email="cb@test.com", password="pass")
        self.org = Organization.objects.create(name="CbOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="CbDs", org=self.org)
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status=JobStatus.PROCESSING,
            stage=ProcessingStage.SFM,
            progress=10,
        )

    def _post(self, data, secret_key=None):
        request = self.factory.post("/api/ai-callback/", data=data, content_type="application/json")
        if secret_key:
            request.META["HTTP_X_API_SECRET_KEY"] = secret_key
        return self.view(request)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_unauthorized_without_secret(self):
        """Missing secret key returns 403."""
        response = self._post({"job_id": str(self.job.id), "type": "progress"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(AI_GATEWAY_SECRET_KEY="correct-secret")
    def test_unauthorized_wrong_secret(self):
        """Wrong secret key returns 403."""
        response = self._post(
            {"job_id": str(self.job.id), "type": "progress"},
            secret_key="wrong-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_missing_job_id(self):
        """Missing job_id returns 400."""
        response = self._post({"type": "progress"}, secret_key="test-secret")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_job_not_found(self):
        """Non-existent job returns 404."""
        response = self._post(
            {"job_id": str(uuid.uuid4()), "type": "progress"},
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_unknown_callback_type(self):
        """Unknown callback type returns 400."""
        response = self._post(
            {"job_id": str(self.job.id), "type": "unknown"},
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_progress_update(self):
        """Progress callback updates job progress and stage."""
        response = self._post(
            {
                "job_id": str(self.job.id),
                "type": "progress",
                "progress": 50,
                "current_stage": "sfm",
            },
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.progress, 50)
        self.assertEqual(self.job.stage, "sfm")

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_progress_with_stage_completion(self):
        """Stage progress 100% sets last_successful_stage."""
        response = self._post(
            {
                "job_id": str(self.job.id),
                "type": "progress",
                "progress": 60,
                "current_stage": "sfm",
                "stage_progress": 100,
            },
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.last_successful_stage, "sfm")

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_completion_callback(self):
        """Completion callback marks job as completed."""
        response = self._post(
            {"job_id": str(self.job.id), "type": "complete", "outputs": {}},
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.COMPLETED)
        self.assertEqual(self.job.progress, 100)
        self.assertIsNotNone(self.job.completed_at)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_error_callback(self):
        """Error callback marks job as failed."""
        response = self._post(
            {
                "job_id": str(self.job.id),
                "type": "error",
                "error_message": "SFM failed",
            },
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.FAILED)
        self.assertEqual(self.job.error_message, "SFM failed")
        self.assertIsNotNone(self.job.completed_at)

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_error_callback_sets_stage_to_failed(self):
        """Error callback sets stage to ProcessingStage.FAILED."""
        response = self._post(
            {
                "job_id": str(self.job.id),
                "type": "error",
                "error_message": "Orthomosaic failed: GPS composite failed",
                "error_details": {"service": "orthomosaic", "stage": "orthomosaic"},
            },
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.FAILED)
        self.assertEqual(self.job.stage, ProcessingStage.FAILED)
        self.assertEqual(self.job.error_message, "Orthomosaic failed: GPS composite failed")

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_error_callback_missing_error_message_uses_default(self):
        """Error callback with no error_message falls back to 'Unknown error'."""
        response = self._post(
            {
                "job_id": str(self.job.id),
                "type": "error",
                # no error_message key
            },
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.FAILED)
        self.assertEqual(self.job.error_message, "Unknown error")

    @override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
    def test_progress_invalid_stage_ignored(self):
        """Invalid stage in progress update is ignored."""
        old_stage = self.job.stage
        response = self._post(
            {
                "job_id": str(self.job.id),
                "type": "progress",
                "progress": 20,
                "current_stage": "nonexistent_stage",
            },
            secret_key="test-secret",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job.refresh_from_db()
        self.assertEqual(self.job.stage, old_stage)


class TestJobCancelView(TestCase):
    """Tests for POST /api/jobs/{job_id}/cancel/"""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = JobCancelView.as_view()
        self.user = UserModel.objects.create_user(email="cancel@test.com", password="pass")
        self.org = Organization.objects.create(name="CancelOrg", user=self.user)
        self.user.organization = self.org
        self.user.save()
        self.dataset = Dataset.objects.create(name="CancelDs", org=self.org)

    def _post(self, job_id, user=None):
        request = self.factory.post(f"/api/jobs/{job_id}/cancel/")
        force_authenticate(request, user=user or self.user)
        return self.view(request, job_id=job_id)

    def test_cancel_no_org(self):
        """User without org gets 400."""
        no_org_user = UserModel.objects.create_user(email="noorg_cancel@test.com", password="pass")
        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )
        response = self._post(job.id, user=no_org_user)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_not_found(self):
        """Non-existent job returns 404."""
        response = self._post(uuid.uuid4())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_already_completed(self):
        """Cannot cancel completed job."""
        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )
        response = self._post(job.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_already_failed(self):
        """Cannot cancel failed job."""
        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.FAILED
        )
        response = self._post(job.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.jobs.api.views.job_cancel_view.requests.post")
    def test_cancel_processing_job(self, mock_post):
        """Cancelling a processing job succeeds."""
        mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"cancelled": True}))
        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )
        response = self._post(job.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

    @patch("apps.jobs.api.views.job_cancel_view.requests.post")
    def test_cancel_queued_job(self, mock_post):
        """Cancelling a queued job succeeds."""
        mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"cancelled": True}))
        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.QUEUED
        )
        response = self._post(job.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

    @patch("apps.jobs.api.views.job_cancel_view.requests.post")
    def test_cancel_ai_gateway_unreachable(self, mock_post):
        """Cancel succeeds even if AI Gateway is unreachable."""
        mock_post.side_effect = Exception("Connection refused")
        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )
        response = self._post(job.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

    def test_cancel_other_org_job(self):
        """Cannot cancel job from another org."""
        other_user = UserModel.objects.create_user(email="other_cancel@test.com", password="pass")
        other_org = Organization.objects.create(name="OtherCancelOrg", user=other_user)
        other_user.organization = other_org
        other_user.save()

        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )
        response = self._post(job.id, user=other_user)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestStartProcessingView(TestCase):
    """Tests for POST /api/start-job/"""

    AI_SECRET = "test-start-secret"

    def setUp(self):
        self.factory = RequestFactory()
        self.view = StartProcessingView.as_view()
        self.user = UserModel.objects.create_user(email="start@test.com", password="pass")
        self.org = Organization.objects.create(name="StartOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="StartDs", org=self.org)

    def _make_request(self, data):
        request = self.factory.post(
            "/api/start-job/",
            data=data,
            content_type="application/json",
        )
        request.META["HTTP_X_API_SECRET_KEY"] = self.AI_SECRET
        return request

    @override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET)
    @patch("apps.jobs.infra.services.tasks.tasks.process_drone_imagery.delay")
    def test_start_job_success(self, mock_task_delay):
        request = self._make_request({
            "dataset_id": str(self.dataset.id),
            "resolution_gsd": 5.0,
            "radiometric_calibration": True,
            "analysis_mode": "fast",
        })
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET)
    def test_start_job_invalid_resolution(self):
        """Resolution <= 0 returns 400."""
        request = self._make_request({
            "dataset_id": str(self.dataset.id),
            "resolution_gsd": -1.0,
            "radiometric_calibration": False,
        })
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET)
    def test_start_job_nonexistent_dataset(self):
        """Non-existent dataset returns 404."""
        request = self._make_request({
            "dataset_id": str(uuid.uuid4()),
            "resolution_gsd": 5.0,
            "radiometric_calibration": False,
        })
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET)
    def test_start_job_missing_fields(self):
        """Missing required fields returns 400."""
        request = self._make_request({})
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET)
    @patch("apps.jobs.infra.services.tasks.tasks.process_drone_imagery.delay")
    def test_start_job_invalid_analysis_mode(self, mock_task_delay):
        """Invalid analysis mode returns 400."""
        request = self._make_request({
            "dataset_id": str(self.dataset.id),
            "resolution_gsd": 5.0,
            "radiometric_calibration": False,
            "analysis_mode": "invalid",
        })
        response = self.view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
