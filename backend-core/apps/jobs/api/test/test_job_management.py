"""Unit tests for Job Management Views (List, Detail, Delete)"""
import uuid
from datetime import timedelta

from django.test import TestCase, RequestFactory
from django.utils import timezone
from rest_framework import status
from rest_framework.test import force_authenticate

from apps.jobs.api.views.job_management_views import (
    JobListView,
    JobDetailView,
    JobDeleteView,
)
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.uploads.infrastructure.models import Dataset
from accounts.models import Organization, UserModel
from products.models import Product


class JobManagementTestMixin:
    """Shared setUp for job management view tests."""

    def _create_org_and_user(self, email, org_name):
        user = UserModel.objects.create_user(email=email, password="testpass123")
        org = Organization.objects.create(name=org_name, user=user)
        user.organization = org
        user.save()
        return user, org


class TestJobListView(JobManagementTestMixin, TestCase):
    """Tests for GET /api/jobs/"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.org = self._create_org_and_user(
            "list@example.com", "List Org"
        )

        self.dataset = Dataset.objects.create(
            name="Test Dataset", org=self.org, crs="EPSG:4326"
        )

        self.completed_job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            radiometric_calibration=True,
            analysis_mode="fast",
            status="completed",
            stage="completed",
            progress=100,
        )
        self.failed_job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=3.0,
            radiometric_calibration=False,
            analysis_mode="full",
            status="failed",
            stage="sfm",
            progress=30,
            error_message="SFM failed: not enough images",
        )
        self.processing_job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=2.5,
            status="processing",
            stage="orthomosaic",
            progress=60,
        )

    def _get(self, query_params="", user=None):
        url = f"/api/jobs/?{query_params}" if query_params else "/api/jobs/"
        request = self.factory.get(url)
        force_authenticate(request, user=user or self.user)
        view = JobListView.as_view()
        return view(request)

    def test_list_returns_all_org_jobs(self):
        response = self._get()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 3)

    def test_list_filters_by_status(self):
        response = self._get("status=failed")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["status"], "failed")

    def test_list_filters_by_multiple_statuses(self):
        response = self._get("status=completed,failed")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        statuses = {r["status"] for r in response.data["results"]}
        self.assertEqual(statuses, {"completed", "failed"})

    def test_list_filters_by_stage(self):
        response = self._get("stage=sfm")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["stage"], "sfm")

    def test_list_filters_by_dataset_id(self):
        other_dataset = Dataset.objects.create(
            name="Other Dataset", org=self.org, crs="EPSG:4326"
        )
        ProcessingJob.objects.create(
            dataset=other_dataset, resolution_gsd=5.0, status="pending"
        )

        response = self._get(f"dataset_id={self.dataset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_list_filters_by_progress_range(self):
        response = self._get("progress_min=50&progress_max=100")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for r in response.data["results"]:
            self.assertGreaterEqual(r["progress"], 50)
            self.assertLessEqual(r["progress"], 100)

    def test_list_pagination(self):
        response = self._get("page=1&page_size=2")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["count"], 3)
        self.assertIsNotNone(response.data["next"])

    def test_list_includes_summary(self):
        response = self._get()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("summary", response.data)
        self.assertEqual(response.data["summary"]["total_jobs"], 3)
        self.assertIn("by_status", response.data["summary"])

    def test_list_ordering(self):
        response = self._get("ordering=progress")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        progresses = [r["progress"] for r in response.data["results"]]
        self.assertEqual(progresses, sorted(progresses))

    def test_list_excludes_other_org_jobs(self):
        other_user, other_org = self._create_org_and_user(
            "other_list@example.com", "Other Org"
        )
        other_dataset = Dataset.objects.create(
            name="Other Dataset", org=other_org, crs="EPSG:4326"
        )
        ProcessingJob.objects.create(
            dataset=other_dataset, resolution_gsd=5.0, status="completed"
        )

        response = self._get(user=other_user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_rejects_user_without_org(self):
        no_org_user = UserModel.objects.create_user(
            email="noorg@example.com", password="testpass123"
        )

        response = self._get(user=no_org_user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("organization", response.data["error"].lower())

    def test_list_search_by_dataset_name(self):
        response = self._get("search=Test")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_list_includes_started_at_and_completed_at(self):
        now = timezone.now()
        self.completed_job.started_at = now - timedelta(minutes=10)
        self.completed_job.completed_at = now
        self.completed_job.save()

        response = self._get("status=completed")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data["results"][0]
        self.assertIn("started_at", result)
        self.assertIn("completed_at", result)
        self.assertIsNotNone(result["started_at"])
        self.assertIsNotNone(result["completed_at"])

    def test_list_duration_uses_started_at_and_completed_at(self):
        now = timezone.now()
        self.completed_job.started_at = now - timedelta(seconds=120)
        self.completed_job.completed_at = now
        self.completed_job.save()

        response = self._get("status=completed")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.data["results"][0]
        self.assertGreaterEqual(result["duration_seconds"], 119)
        self.assertLessEqual(result["duration_seconds"], 121)

class TestJobDetailView(JobManagementTestMixin, TestCase):
    """Tests for GET /api/jobs/{job_id}/"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.org = self._create_org_and_user(
            "detail@example.com", "Detail Org"
        )

        self.dataset = Dataset.objects.create(
            name="Detail Dataset", org=self.org, crs="EPSG:4326"
        )

        self.job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            radiometric_calibration=True,
            analysis_mode="full",
            status="completed",
            stage="completed",
            progress=100,
            last_successful_stage="orthomosaic",
            can_retry=True,
        )

    def _get_detail(self, job_id, user=None):
        request = self.factory.get(f"/api/jobs/{job_id}/")
        force_authenticate(request, user=user or self.user)
        view = JobDetailView.as_view()
        return view(request, job_id=job_id)

    def test_detail_returns_full_job_data(self):
        response = self._get_detail(self.job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.job.id))
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["analysis_mode"], "full")
        self.assertEqual(response.data["resolution_gsd"], 5.0)
        self.assertTrue(response.data["radiometric_calibration"])

    def test_detail_includes_dataset_info(self):
        response = self._get_detail(self.job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["dataset"]["name"], "Detail Dataset")
        self.assertEqual(response.data["dataset"]["id"], str(self.dataset.id))

    def test_detail_includes_retry_info(self):
        response = self._get_detail(self.job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        retry_info = response.data["retry_info"]
        self.assertEqual(retry_info["retry_count"], 0)
        self.assertTrue(retry_info["can_retry"])
        self.assertIsNone(retry_info["original_job_id"])
        self.assertEqual(retry_info["last_successful_stage"], "orthomosaic")

    def test_detail_includes_products(self):
        Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type="orthomosaic",
            uri="s3://bucket/products/ortho.tif",
            resolution_cm=5.0,
        )
        Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type="dsm",
            uri="s3://bucket/products/dsm.tif",
        )
        Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type="orthomosaic_2x",
            uri="s3://bucket/products/ortho_2x.tif",
            resolution_cm=10.0,
        )

        response = self._get_detail(self.job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["products"]), 3)
        product_types = {p["type"] for p in response.data["products"]}
        self.assertIn("orthomosaic", product_types)
        self.assertIn("dsm", product_types)
        self.assertIn("orthomosaic_2x", product_types)

    def test_detail_products_include_metadata(self):
        Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type="ndvi",
            uri="s3://bucket/products/ndvi.tif",
            bands=["red", "nir"],
            resolution_cm=5.0,
        )

        response = self._get_detail(self.job.id)

        product = response.data["products"][0]
        self.assertEqual(product["type"], "ndvi")
        self.assertEqual(product["type_display"], "NDVI Map")
        self.assertEqual(product["category"], "Calibration")
        self.assertEqual(product["bands"], ["red", "nir"])
        self.assertEqual(product["resolution_cm"], 5.0)

    def test_detail_includes_duration(self):
        response = self._get_detail(self.job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("duration", response.data)
        self.assertIn("seconds", response.data["duration"])
        self.assertIn("formatted", response.data["duration"])

    def test_detail_includes_started_at_and_completed_at(self):
        now = timezone.now()
        self.job.started_at = now - timedelta(minutes=5)
        self.job.completed_at = now
        self.job.save()

        response = self._get_detail(self.job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("started_at", response.data)
        self.assertIn("completed_at", response.data)
        self.assertIsNotNone(response.data["started_at"])
        self.assertIsNotNone(response.data["completed_at"])

    def test_detail_duration_uses_started_at_and_completed_at(self):
        now = timezone.now()
        self.job.started_at = now - timedelta(seconds=300)
        self.job.completed_at = now
        self.job.save()

        response = self._get_detail(self.job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["duration"]["seconds"], 299)
        self.assertLessEqual(response.data["duration"]["seconds"], 301)

    def test_detail_returns_404_for_nonexistent_job(self):
        response = self._get_detail(uuid.uuid4())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_returns_404_for_other_org_job(self):
        other_user, other_org = self._create_org_and_user(
            "other_detail@example.com", "Other Detail Org"
        )

        response = self._get_detail(self.job.id, user=other_user)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_for_failed_job_includes_error_message(self):
        self.job.status = "failed"
        self.job.error_message = "Orthomosaic generation failed: memory exceeded"
        self.job.save()

        response = self._get_detail(self.job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "failed")
        self.assertIn("memory exceeded", response.data["error_message"])

    def test_detail_empty_products_for_new_job(self):
        new_job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="pending",
            stage="queued",
        )

        response = self._get_detail(new_job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["products"], [])


class TestJobDeleteView(JobManagementTestMixin, TestCase):
    """Tests for DELETE /api/jobs/{job_id}/"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user, self.org = self._create_org_and_user(
            "delete@example.com", "Delete Org"
        )

        self.dataset = Dataset.objects.create(
            name="Delete Dataset", org=self.org, crs="EPSG:4326"
        )

        self.failed_job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status="failed",
            stage="sfm",
            progress=30,
        )

    def _delete(self, job_id, user=None):
        request = self.factory.delete(f"/api/jobs/{job_id}/")
        force_authenticate(request, user=user or self.user)
        view = JobDeleteView.as_view()
        return view(request, job_id=job_id)

    def test_delete_failed_job(self):
        job_id = self.failed_job.id

        response = self._delete(job_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ProcessingJob.objects.filter(id=job_id).exists())

    def test_delete_completed_job(self):
        self.failed_job.status = "completed"
        self.failed_job.save()

        response = self._delete(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_rejects_processing_job(self):
        self.failed_job.status = "processing"
        self.failed_job.save()

        response = self._delete(self.failed_job.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cannot delete", response.data["error"])
        self.assertTrue(ProcessingJob.objects.filter(id=self.failed_job.id).exists())

    def test_delete_returns_404_for_nonexistent_job(self):
        response = self._delete(uuid.uuid4())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_returns_404_for_other_org_job(self):
        other_user, other_org = self._create_org_and_user(
            "other_delete@example.com", "Other Delete Org"
        )

        response = self._delete(self.failed_job.id, user=other_user)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ProcessingJob.objects.filter(id=self.failed_job.id).exists())

    def test_delete_rejects_user_without_org(self):
        no_org_user = UserModel.objects.create_user(
            email="noorg_del@example.com", password="testpass123"
        )

        response = self._delete(self.failed_job.id, user=no_org_user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
