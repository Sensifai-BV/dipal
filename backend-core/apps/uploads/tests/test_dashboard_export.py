"""Tests for dashboard views and exports."""

import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Organization, UserModel
from apps.uploads.infrastructure.models import Dataset, Image, UploadStatus
from apps.uploads.domain.constants import UploadStatusName
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus
from products.models import Product


class DashboardStatsViewTest(TestCase):
    """Tests for DashboardStatsView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="dash@test.com", password="pass1234")
        self.org = Organization.objects.create(name="DashOrg", user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_stats_empty(self):
        """Test dashboard stats with no data."""
        response = self.client.get("/v1/api/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_datasets"], 0)
        self.assertEqual(response.data["total_products"], 0)
        self.assertEqual(response.data["total_completed_jobs"], 0)

    def test_stats_with_data(self):
        """Test dashboard stats with real data."""
        ds = Dataset.objects.create(name="DashDS", org=self.org)
        job = ProcessingJob.objects.create(
            dataset=ds, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )
        Product.objects.create(dataset=ds, job=job, type="orthomosaic", uri="p/o.tif")

        response = self.client.get("/v1/api/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_datasets"], 1)
        self.assertEqual(response.data["total_products"], 1)
        self.assertEqual(response.data["total_completed_jobs"], 1)

    def test_stats_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/v1/api/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RecentActivitiesViewTest(TestCase):
    """Tests for RecentActivitiesView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="activity@test.com", password="pass1234")
        self.org = Organization.objects.create(name="ActivityOrg", user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_activities_empty(self):
        """Test activities with no data."""
        response = self.client.get("/v1/api/dashboard/activities/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["activities"]), 0)

    def test_activities_with_data(self):
        """Test activities include dataset uploads and job starts."""
        ds = Dataset.objects.create(name="ActDS", org=self.org)
        ProcessingJob.objects.create(
            dataset=ds, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )

        response = self.client.get("/v1/api/dashboard/activities/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        activities = response.data["activities"]
        self.assertEqual(len(activities), 2)
        types = {a["type"] for a in activities}
        self.assertIn("dataset_upload", types)
        self.assertIn("job_started", types)

    def test_activities_limit(self):
        """Test activities respect the limit parameter."""
        for i in range(5):
            Dataset.objects.create(name=f"LimitDS{i}", org=self.org)

        response = self.client.get("/v1/api/dashboard/activities/?limit=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data["activities"]), 2)

    def test_activities_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/v1/api/dashboard/activities/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ExportViewTest(TestCase):
    """Tests for DatasetExportStatusView and CreateDatasetArchiveView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="export@test.com", password="pass1234")
        self.org = Organization.objects.create(name="ExportOrg", user=self.user)
        self.client.force_authenticate(user=self.user)
        self.dataset = Dataset.objects.create(name="ExportDS", org=self.org)

    def test_export_status_not_found(self):
        """Test export status when job not found."""
        response = self.client.get(
            f"/v1/api/uploads/export/status/{uuid.uuid4()}/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.uploads.presentation.exportviews.create_dataset_archive_task")
    def test_create_archive(self, mock_task):
        """Test creating a dataset archive triggers celery task."""
        mock_task.delay = MagicMock()

        pending, _ = UploadStatus.objects.get_or_create(
            name=UploadStatusName.PENDING, defaults={"label": "Pending"}
        )
        Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="export.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=pending,
            s3_key="key/export.jpg",
            file_type="IMAGE",
        )

        response = self.client.post(
            f"/v1/api/uploads/export/dataset/{self.dataset.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mock_task.delay.assert_called_once()
