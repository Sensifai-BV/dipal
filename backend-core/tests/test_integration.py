"""
Integration tests for the PhotoGear backend.

Tests end-to-end API workflows that span multiple models/views:
- Job lifecycle: create → progress updates → completion with products
- Dataset management: create, list, detail, delete
- Job management: list/filter, detail, delete, retry, rerun, cancel
- Product listing and filtering
- Registration → authentication → API access flow
"""

import uuid
from unittest.mock import patch, MagicMock, AsyncMock

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Organization, UserModel, Role, RoleName
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus, ProcessingStage
from products.models import Product


class BaseIntegrationTest(TestCase):
    """Base class that sets up auth user + organization."""

    def setUp(self):
        Role.objects.get_or_create(id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"})
        Role.objects.get_or_create(id=2, defaults={"name": RoleName.USER, "label": "Owner"})

        self.client = APIClient()
        self.user = UserModel.objects.create_user(
            email="integ@test.com", password="pass123"
        )
        self.org = Organization.objects.create(name="IntegOrg", user=self.user)
        self.user.organization = self.org
        self.user.save()
        self.client.force_authenticate(user=self.user)


class TestRegistrationToAPIFlow(TestCase):
    """Tests complete flow: register → login → access protected endpoint."""

    def setUp(self):
        Role.objects.get_or_create(id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"})
        self.client = APIClient()

    def test_register_then_login_then_access_profile(self):
        """User registers, logs in with JWT, accesses profile."""
        reg_response = self.client.post("/v1/accounts/register/", {
            "full_name": "Integration User",
            "email": "flow_user@test.com",
            "organization": "FlowOrg",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
        }, format="json")
        self.assertEqual(reg_response.status_code, status.HTTP_201_CREATED)

        login_response = self.client.post("/v1/accounts/login/", {
            "email": "flow_user@test.com",
            "password": "StrongPass123!",
        }, format="json")
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data["data"])

        token = login_response.data["data"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        profile_response = self.client.get("/v1/accounts/profile/")
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data["data"]["email"], "flow_user@test.com")


class TestDatasetManagementFlow(BaseIntegrationTest):
    """Tests dataset CRUD lifecycle."""

    def test_create_and_list_datasets(self):
        """Datasets created via ORM appear in list endpoint."""
        Dataset.objects.create(name="Dataset Alpha", org=self.org)
        Dataset.objects.create(name="Dataset Beta", org=self.org)

        response = self.client.get("/v1/api/uploads/datasets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [d["name"] for d in response.data["results"]]
        self.assertIn("Dataset Alpha", names)
        self.assertIn("Dataset Beta", names)
        self.assertEqual(len(response.data["results"]), 2)

    def test_dataset_detail(self):
        """Dataset detail returns correct dataset."""
        ds = Dataset.objects.create(name="DetailTest", org=self.org)
        response = self.client.get(f"/v1/api/uploads/datasets/{ds.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "DetailTest")

    def test_dataset_delete(self):
        """Deleted dataset no longer appears in list."""
        ds = Dataset.objects.create(name="ToDelete", org=self.org)
        del_response = self.client.delete(f"/v1/api/uploads/datasets/{ds.id}/delete/")
        self.assertEqual(del_response.status_code, status.HTTP_200_OK)

        response = self.client.get("/v1/api/uploads/datasets/")
        names = [d["name"] for d in response.data["results"]]
        self.assertNotIn("ToDelete", names)

    def test_dataset_not_found(self):
        """Non-existent dataset returns 404."""
        fake_id = uuid.uuid4()
        response = self.client.get(f"/v1/api/uploads/datasets/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
class TestJobLifecycle(BaseIntegrationTest):
    """Tests the full job processing lifecycle via API callbacks."""

    def setUp(self):
        super().setUp()
        self.dataset = Dataset.objects.create(name="LifecycleDS", org=self.org)
        self.ai_client = APIClient()

    def _ai_callback(self, payload):
        """Send AI callback with proper secret key."""
        return self.ai_client.post(
            "/v1/api/jobs/ai-callback/",
            payload,
            format="json",
            HTTP_X_API_SECRET_KEY="test-secret",
        )

    def _start_job(self):
        """Create a job via the start-job endpoint."""
        return self.ai_client.post(
            "/v1/api/jobs/start-job/",
            {
                "dataset_id": str(self.dataset.id),
                "resolution_gsd": 5.0,
                "radiometric_calibration": False,
                "analysis_mode": "fast",
            },
            format="json",
            HTTP_X_API_SECRET_KEY="test-secret",
        )

    def test_start_job_creates_job(self):
        """Start-job endpoint creates a processing job."""
        response = self._start_job()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        job = ProcessingJob.objects.get(id=response.data["id"])
        self.assertIn(job.status, [JobStatus.PENDING, JobStatus.QUEUED])

    def test_progress_callback_updates_job(self):
        """Progress callback updates job stage and progress."""
        start_resp = self._start_job()
        job_id = start_resp.data["id"]

        resp = self._ai_callback({
            "job_id": job_id,
            "type": "progress",
            "progress": 30,
            "current_stage": "sfm",
            "message": "Running SFM",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        job = ProcessingJob.objects.get(id=job_id)
        self.assertEqual(job.progress, 30)

    def test_completion_callback_marks_completed(self):
        """Completion callback marks job as completed."""
        start_resp = self._start_job()
        job_id = start_resp.data["id"]

        resp = self._ai_callback({
            "job_id": job_id,
            "type": "complete",
            "progress": 100,
            "message": "Done",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        job = ProcessingJob.objects.get(id=job_id)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.progress, 100)

    def test_error_callback_marks_failed(self):
        """Error callback marks job as failed with error message."""
        start_resp = self._start_job()
        job_id = start_resp.data["id"]

        resp = self._ai_callback({
            "job_id": job_id,
            "type": "error",
            "error_message": "SFM crashed",
            "last_successful_stage": "radiometric_calibration",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        job = ProcessingJob.objects.get(id=job_id)
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.error_message, "SFM crashed")

    def test_callback_nonexistent_job_returns_404(self):
        """Callback for non-existent job returns 404."""
        resp = self._ai_callback({
            "job_id": str(uuid.uuid4()),
            "type": "progress",
            "progress": 50,
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class TestJobManagementFlow(BaseIntegrationTest):
    """Tests job listing, filtering, detail, and deletion."""

    def setUp(self):
        super().setUp()
        self.dataset = Dataset.objects.create(name="MgmtDS", org=self.org)
        self.pending_job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PENDING
        )
        self.completed_job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=8.0, status=JobStatus.COMPLETED
        )
        self.failed_job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=3.0, status=JobStatus.FAILED,
            error_message="Test failure"
        )

    def test_job_list_returns_all_org_jobs(self):
        """Job list endpoint returns all jobs for user's organization."""
        response = self.client.get("/v1/api/jobs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_job_list_filter_by_status(self):
        """Job list can be filtered by status."""
        response = self.client.get("/v1/api/jobs/?status=completed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], "completed")

    def test_job_list_filter_by_dataset(self):
        """Job list can be filtered by dataset_id."""
        other_ds = Dataset.objects.create(name="OtherDS", org=self.org)
        ProcessingJob.objects.create(
            dataset=other_ds, resolution_gsd=5.0, status=JobStatus.PENDING
        )
        response = self.client.get(f"/v1/api/jobs/?dataset_id={self.dataset.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_job_list_summary(self):
        """Job list includes summary statistics."""
        response = self.client.get("/v1/api/jobs/")
        self.assertIn("summary", response.data)
        self.assertEqual(response.data["summary"]["total_jobs"], 3)

    def test_job_detail(self):
        """Job detail returns correct job with full info."""
        response = self.client.get(f"/v1/api/jobs/{self.completed_job.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.completed_job.id))
        self.assertEqual(response.data["status"], "completed")
        self.assertIn("retry_info", response.data)
        self.assertIn("products", response.data)

    def test_job_detail_not_found(self):
        """Detail of non-existent job returns 404."""
        response = self.client.get(f"/v1/api/jobs/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_failed_job(self):
        """Deleting a failed job succeeds."""
        response = self.client.delete(f"/v1/api/jobs/{self.failed_job.id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ProcessingJob.objects.filter(id=self.failed_job.id).exists())

    def test_delete_completed_job(self):
        """Deleting a completed job succeeds."""
        response = self.client.delete(f"/v1/api/jobs/{self.completed_job.id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_processing_job_denied(self):
        """Cannot delete a job that is currently processing."""
        processing_job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )
        response = self.client.delete(f"/v1/api/jobs/{processing_job.id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestJobRetryFlow(BaseIntegrationTest):
    """Tests job retry and rerun flows."""

    def setUp(self):
        super().setUp()
        self.dataset = Dataset.objects.create(name="RetryDS", org=self.org)
        self.failed_job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status=JobStatus.FAILED,
            error_message="SFM error",
            last_successful_stage=ProcessingStage.RADIOMETRIC_CALIBRATION,
            can_retry=True,
        )

    @patch("apps.jobs.api.views.job_retry_view.httpx.AsyncClient")
    def test_retry_creates_new_job(self, MockAsyncClient):
        """Retrying a failed job creates a new job linked to the original."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        MockAsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockAsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

        response = self.client.post(f"/v1/api/jobs/{self.failed_job.id}/retry/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("new_job_id", response.data)
        new_job = ProcessingJob.objects.get(id=response.data["new_job_id"])
        self.assertEqual(new_job.original_job_id, self.failed_job.id)

    def test_retry_non_failed_job_denied(self):
        """Cannot retry a job that is not in failed status."""
        pending_job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PENDING
        )
        response = self.client.post(f"/v1/api/jobs/{pending_job.id}/retry/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.jobs.api.views.job_rerun_view.process_drone_imagery.delay")
    def test_rerun_resets_job(self, mock_delay):
        """Rerunning a job resets its status to queued."""
        response = self.client.post(f"/v1/api/jobs/{self.failed_job.id}/rerun/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.failed_job.refresh_from_db()
        self.assertEqual(self.failed_job.status, JobStatus.QUEUED)
        mock_delay.assert_called_once()

    @patch("apps.jobs.api.views.job_cancel_view.requests.post")
    def test_cancel_processing_job(self, mock_post):
        """Cancelling a processing job changes its status."""
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"status": "cancelled"})
        processing_job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )
        response = self.client.post(f"/v1/api/jobs/{processing_job.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        processing_job.refresh_from_db()
        self.assertEqual(processing_job.status, JobStatus.CANCELLED)


class TestProductFlow(BaseIntegrationTest):
    """Tests product listing and filtering through the visualization API."""

    def setUp(self):
        super().setUp()
        self.dataset = Dataset.objects.create(name="ProductDS", org=self.org)
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )
        self.ortho = Product.objects.create(
            dataset=self.dataset, job=self.job,
            type="orthomosaic", uri="s3://bucket/ortho.tif"
        )
        self.dsm = Product.objects.create(
            dataset=self.dataset, job=self.job,
            type="dsm", uri="s3://bucket/dsm.tif"
        )
        self.ndvi = Product.objects.create(
            dataset=self.dataset, job=self.job,
            type="ndvi", uri="s3://bucket/ndvi.tif"
        )

    @patch("products.visualization_views.S3Service")
    def test_list_all_products(self, MockS3):
        """Product list returns all products for org."""
        response = self.client.get("/v1/api/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)

    @patch("products.visualization_views.S3Service")
    def test_filter_products_by_dataset(self, MockS3):
        """Products can be filtered by dataset_id."""
        other_ds = Dataset.objects.create(name="OtherProdDS", org=self.org)
        other_job = ProcessingJob.objects.create(
            dataset=other_ds, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )
        Product.objects.create(
            dataset=other_ds, job=other_job,
            type="orthomosaic", uri="s3://bucket/other.tif"
        )
        response = self.client.get(f"/v1/api/products/?dataset_id={self.dataset.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)

    @patch("products.visualization_views.S3Service")
    def test_filter_products_by_job(self, MockS3):
        """Products can be filtered by job_id."""
        response = self.client.get(f"/v1/api/products/?job_id={self.job.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)

    @patch("products.visualization_views.S3Service")
    def test_filter_products_by_type(self, MockS3):
        """Products can be filtered by type."""
        response = self.client.get("/v1/api/products/?type=ndvi")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["type"], "ndvi")

    @patch("products.visualization_views.S3Service")
    def test_product_detail(self, MockS3):
        """Product detail returns correct product."""
        response = self.client.get(f"/v1/api/products/{self.ortho.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["type"], "orthomosaic")

    @patch("products.visualization_views.S3Service")
    def test_product_detail_not_found(self, MockS3):
        """Non-existent product returns 404."""
        response = self.client.get(f"/v1/api/products/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestJobWithProductsDetail(BaseIntegrationTest):
    """Tests that job detail includes associated products."""

    def setUp(self):
        super().setUp()
        self.dataset = Dataset.objects.create(name="DetailDS", org=self.org)
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )
        Product.objects.create(
            dataset=self.dataset, job=self.job,
            type="orthomosaic", uri="s3://bucket/ortho.tif"
        )
        Product.objects.create(
            dataset=self.dataset, job=self.job,
            type="dsm", uri="s3://bucket/dsm.tif"
        )

    def test_job_detail_includes_products(self):
        """Job detail endpoint includes the list of products."""
        response = self.client.get(f"/v1/api/jobs/{self.job.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["products"]), 2)
        product_types = [p["type"] for p in response.data["products"]]
        self.assertIn("orthomosaic", product_types)
        self.assertIn("dsm", product_types)


class TestPaginationAndOrdering(BaseIntegrationTest):
    """Tests that list endpoints support pagination and ordering."""

    def setUp(self):
        super().setUp()
        self.dataset = Dataset.objects.create(name="PaginationDS", org=self.org)
        for i in range(25):
            ProcessingJob.objects.create(
                dataset=self.dataset,
                resolution_gsd=float(i),
                status=JobStatus.COMPLETED if i % 2 == 0 else JobStatus.FAILED,
            )

    def test_default_page_size(self):
        """Job list default page is 20 items."""
        response = self.client.get("/v1/api/jobs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertEqual(response.data["count"], 25)

    def test_custom_page_size(self):
        """Job list respects custom page_size."""
        response = self.client.get("/v1/api/jobs/?page_size=5")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)

    def test_second_page(self):
        """Job list page 2 returns remaining items."""
        response = self.client.get("/v1/api/jobs/?page=2&page_size=20")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)

    def test_ordering_by_progress(self):
        """Jobs can be ordered by progress."""
        response = self.client.get("/v1/api/jobs/?ordering=progress&page_size=5")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        progresses = [r["progress"] for r in response.data["results"]]
        self.assertEqual(progresses, sorted(progresses))

    def test_multi_status_filter(self):
        """Job list supports comma-separated status filter."""
        response = self.client.get("/v1/api/jobs/?status=completed,failed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 25)


@override_settings(AI_GATEWAY_SECRET_KEY="test-secret")
class TestFullPipelineIntegration(BaseIntegrationTest):
    """
    End-to-end test: create dataset → start job → progress → complete → verify products via detail.
    """

    def setUp(self):
        super().setUp()
        self.ai_client = APIClient()

    def test_full_pipeline(self):
        """Tests the complete pipeline from dataset to job completion and product listing."""
        ds = Dataset.objects.create(name="E2E_Dataset", org=self.org)

        start_resp = self.ai_client.post(
            "/v1/api/jobs/start-job/",
            {
                "dataset_id": str(ds.id),
                "resolution_gsd": 5.0,
                "radiometric_calibration": False,
                "analysis_mode": "fast",
            },
            format="json",
            HTTP_X_API_SECRET_KEY="test-secret",
        )
        self.assertEqual(start_resp.status_code, status.HTTP_201_CREATED)
        job_id = start_resp.data["id"]

        self.ai_client.post(
            "/v1/api/jobs/ai-callback/",
            {"job_id": job_id, "type": "progress", "progress": 30, "current_stage": "sfm"},
            format="json",
            HTTP_X_API_SECRET_KEY="test-secret",
        )

        self.ai_client.post(
            "/v1/api/jobs/ai-callback/",
            {"job_id": job_id, "type": "complete", "progress": 100},
            format="json",
            HTTP_X_API_SECRET_KEY="test-secret",
        )

        job = ProcessingJob.objects.get(id=job_id)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.progress, 100)

        Product.objects.create(
            dataset=ds, job=job, type="orthomosaic", uri="s3://ortho.tif"
        )
        Product.objects.create(
            dataset=ds, job=job, type="dsm", uri="s3://dsm.tif"
        )

        detail_resp = self.client.get(f"/v1/api/jobs/{job_id}/")
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.data["status"], "completed")
        self.assertEqual(len(detail_resp.data["products"]), 2)

        list_resp = self.client.get(f"/v1/api/jobs/?dataset_id={ds.id}")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(list_resp.data["count"], 1)


class TestDashboardStats(BaseIntegrationTest):
    """Tests dashboard stats reflect actual data."""

    def setUp(self):
        super().setUp()
        ds = Dataset.objects.create(name="DashDS", org=self.org)
        ProcessingJob.objects.create(
            dataset=ds, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )
        ProcessingJob.objects.create(
            dataset=ds, resolution_gsd=5.0, status=JobStatus.FAILED
        )
        ProcessingJob.objects.create(
            dataset=ds, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )

    def test_dashboard_stats_reflect_data(self):
        """Dashboard stats endpoint returns non-empty stats."""
        response = self.client.get("/v1/api/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_datasets", response.data)
        self.assertGreaterEqual(response.data["total_datasets"], 1)
