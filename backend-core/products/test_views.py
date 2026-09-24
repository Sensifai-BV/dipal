"""Tests for product upload and visualization views."""

import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status as http_status

from accounts.models import Organization, UserModel
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus
from products.models import Product
from products.views import UPLOAD_SESSIONS


AI_SECRET = "test-secret-key-123"


@override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET)
class ProductUploadInitViewTest(TestCase):
    """Tests for ProductUploadInitView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="prod_init@test.com", password="pass1234")
        self.org = Organization.objects.create(name="ProdOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="ProdDS", org=self.org)
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=5.0,
            status=JobStatus.PROCESSING,
        )

    @patch("products.views.S3Service")
    def test_init_success(self, MockS3):
        """Test successful product upload initialization."""
        mock_s3 = MockS3.return_value
        mock_s3.create_multipart_upload.return_value = "s3-upload-id-1"

        response = self.client.post(
            "/v1/api/products/upload/init/",
            {
                "job_id": str(self.job.id),
                "dataset_id": str(self.dataset.id),
                "product_type": "orthomosaic",
                "file_name": "ortho.tif",
                "file_size": 10240000,
                "content_type": "image/tiff",
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn("product_id", response.data)
        self.assertIn("upload_id", response.data)
        self.assertIn("s3_key", response.data)
        self.assertTrue(Product.objects.filter(type="orthomosaic", dataset=self.dataset).exists())

    @patch("products.views.S3Service")
    def test_init_rerun_reuses_product(self, MockS3):
        """Test that re-init for same job+type reuses existing product."""
        mock_s3 = MockS3.return_value
        mock_s3.create_multipart_upload.return_value = "s3-upload-id-2"

        Product.objects.create(
            dataset=self.dataset, job=self.job, type="dsm", uri="old/path.tif"
        )

        response = self.client.post(
            "/v1/api/products/upload/init/",
            {
                "job_id": str(self.job.id),
                "dataset_id": str(self.dataset.id),
                "product_type": "dsm",
                "file_name": "dsm.tif",
                "file_size": 5000000,
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(Product.objects.filter(type="dsm", job=self.job).count(), 1)

    def test_init_unauthorized(self):
        """Test that missing secret key returns 403."""
        response = self.client.post("/v1/api/products/upload/init/", {}, format="json")
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_init_wrong_key(self):
        """Test that wrong secret key returns 403."""
        response = self.client.post(
            "/v1/api/products/upload/init/",
            {},
            format="json",
            HTTP_X_API_SECRET_KEY="wrong-key",
        )
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    @patch("products.views.S3Service")
    def test_init_job_not_found(self, MockS3):
        """Test init with nonexistent job returns 404."""
        response = self.client.post(
            "/v1/api/products/upload/init/",
            {
                "job_id": str(uuid.uuid4()),
                "dataset_id": str(self.dataset.id),
                "product_type": "orthomosaic",
                "file_name": "ortho.tif",
                "file_size": 1024,
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    @patch("products.views.S3Service")
    def test_init_dataset_not_found(self, MockS3):
        """Test init with nonexistent dataset returns 404."""
        response = self.client.post(
            "/v1/api/products/upload/init/",
            {
                "job_id": str(self.job.id),
                "dataset_id": str(uuid.uuid4()),
                "product_type": "orthomosaic",
                "file_name": "ortho.tif",
                "file_size": 1024,
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)


@override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET)
class ProductChunkUploadViewTest(TestCase):
    """Tests for ProductChunkUploadView."""

    def setUp(self):
        self.client = APIClient()
        self.session_uuid = str(uuid.uuid4())
        UPLOAD_SESSIONS[self.session_uuid] = {
            "product_id": str(uuid.uuid4()),
            "s3_upload_id": "s3-up-1",
            "s3_key": "products/test/ortho.tif",
        }

    def tearDown(self):
        UPLOAD_SESSIONS.pop(self.session_uuid, None)

    @patch("products.views.S3Service")
    def test_chunk_presigned_url(self, MockS3):
        """Test getting presigned URL for chunk."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_presigned_url_part.return_value = "https://s3.example.com/signed"

        response = self.client.post(
            "/v1/api/products/upload/chunk/",
            {
                "upload_id": self.session_uuid,
                "s3_upload_id": "s3-up-1",
                "s3_key": "products/test/ortho.tif",
                "part_number": 1,
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn("url", response.data)

    def test_chunk_session_not_found(self):
        """Test chunk upload with unknown session returns 404."""
        response = self.client.post(
            "/v1/api/products/upload/chunk/",
            {
                "upload_id": str(uuid.uuid4()),
                "s3_upload_id": "x",
                "s3_key": "x",
                "part_number": 1,
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_chunk_unauthorized(self):
        """Test unauthorized chunk request."""
        response = self.client.post("/v1/api/products/upload/chunk/", {}, format="json")
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)


@override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET, AWS_STORAGE_BUCKET_NAME="test-bucket")
class ProductUploadCompleteViewTest(TestCase):
    """Tests for ProductUploadCompleteView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="prod_comp@test.com", password="pass1234")
        self.org = Organization.objects.create(name="CompOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="CompDS", org=self.org)
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )
        self.product = Product.objects.create(
            dataset=self.dataset, job=self.job, type="orthomosaic", uri=""
        )
        self.session_id = str(uuid.uuid4())
        UPLOAD_SESSIONS[self.session_id] = {
            "product_id": str(self.product.id),
            "s3_upload_id": "s3-up-comp",
            "s3_key": "products/test/ortho.tif",
            "dataset_id": str(self.dataset.id),
            "job_id": str(self.job.id),
        }

    def tearDown(self):
        UPLOAD_SESSIONS.pop(self.session_id, None)

    @patch("products.views.S3Service")
    def test_complete_success(self, MockS3):
        """Test successful product upload completion."""
        mock_s3 = MockS3.return_value
        mock_s3.complete_multipart_upload.return_value = None

        response = self.client.post(
            "/v1/api/products/upload/complete/",
            {
                "upload_id": self.session_id,
                "s3_upload_id": "s3-up-comp",
                "s3_key": "products/test/ortho.tif",
                "parts": [{"PartNumber": 1, "ETag": "\"abc\""}],
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "completed")
        self.product.refresh_from_db()
        self.assertEqual(self.product.uri, "products/test/ortho.tif")

    def test_complete_session_not_found(self):
        """Test completion with unknown session returns 404."""
        response = self.client.post(
            "/v1/api/products/upload/complete/",
            {
                "upload_id": str(uuid.uuid4()),
                "s3_upload_id": "x",
                "s3_key": "x",
                "parts": [],
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_complete_unauthorized(self):
        """Test unauthorized complete request."""
        response = self.client.post("/v1/api/products/upload/complete/", {}, format="json")
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)


@override_settings(AI_GATEWAY_SECRET_KEY=AI_SECRET)
class ProductUploadAbortViewTest(TestCase):
    """Tests for ProductUploadAbortView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="prod_abort@test.com", password="pass1234")
        self.org = Organization.objects.create(name="AbortOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="AbortDS", org=self.org)
        self.product = Product.objects.create(
            dataset=self.dataset, type="dsm", uri="temp/dsm.tif"
        )
        self.session_id = str(uuid.uuid4())
        UPLOAD_SESSIONS[self.session_id] = {
            "product_id": str(self.product.id),
            "s3_upload_id": "s3-up-abort",
            "s3_key": "products/test/dsm.tif",
        }

    def tearDown(self):
        UPLOAD_SESSIONS.pop(self.session_id, None)

    @patch("products.views.S3Service")
    def test_abort_success(self, MockS3):
        """Test successful upload abort."""
        mock_s3 = MockS3.return_value
        mock_s3.abort_multipart_upload.return_value = None

        response = self.client.post(
            "/v1/api/products/upload/abort/",
            {
                "upload_id": self.session_id,
                "s3_upload_id": "s3-up-abort",
                "s3_key": "products/test/dsm.tif",
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "aborted")
        self.assertNotIn(self.session_id, UPLOAD_SESSIONS)
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_abort_missing_fields(self):
        """Test abort with missing required fields returns 400."""
        response = self.client.post(
            "/v1/api/products/upload/abort/",
            {"upload_id": "x"},
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_abort_unauthorized(self):
        """Test unauthorized abort request."""
        response = self.client.post("/v1/api/products/upload/abort/", {}, format="json")
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    @patch("products.views.S3Service")
    def test_abort_no_session(self, MockS3):
        """Test abort when session is already gone."""
        mock_s3 = MockS3.return_value
        mock_s3.abort_multipart_upload.return_value = None

        response = self.client.post(
            "/v1/api/products/upload/abort/",
            {
                "upload_id": "nonexistent-session",
                "s3_upload_id": "x",
                "s3_key": "x",
            },
            format="json",
            HTTP_X_API_SECRET_KEY=AI_SECRET,
        )
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)


class ProductListViewTest(TestCase):
    """Tests for ProductListView (visualization)."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="prodlist@test.com", password="pass1234")
        self.org = Organization.objects.create(name="ProdListOrg", user=self.user)
        self.user.organization = self.org
        self.user.organization_id = self.org.id
        self.user.save()
        self.client.force_authenticate(user=self.user)
        self.dataset = Dataset.objects.create(name="ListDS", org=self.org)
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )

    @patch("products.visualization_views.S3Service")
    def test_list_empty(self, MockS3):
        """Test listing products when none exist."""
        response = self.client.get("/v1/api/products/")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    @patch("products.visualization_views.S3Service")
    def test_list_with_products(self, MockS3):
        """Test listing products returns results."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_presigned_download_url.return_value = "https://download.example.com"

        Product.objects.create(
            dataset=self.dataset, job=self.job, type="orthomosaic",
            uri="products/ortho.tif"
        )
        Product.objects.create(
            dataset=self.dataset, job=self.job, type="dsm",
            uri="products/dsm.tif"
        )

        response = self.client.get("/v1/api/products/")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    @patch("products.visualization_views.S3Service")
    def test_list_filter_by_type(self, MockS3):
        """Test filtering products by type."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_presigned_download_url.return_value = "https://dl.example.com"

        Product.objects.create(
            dataset=self.dataset, job=self.job, type="orthomosaic", uri="p/ortho.tif"
        )
        Product.objects.create(
            dataset=self.dataset, job=self.job, type="dsm", uri="p/dsm.tif"
        )

        response = self.client.get("/v1/api/products/?type=orthomosaic")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    @patch("products.visualization_views.S3Service")
    def test_list_filter_by_job(self, MockS3):
        """Test filtering products by job_id."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_presigned_download_url.return_value = "https://dl.example.com"

        Product.objects.create(
            dataset=self.dataset, job=self.job, type="orthomosaic", uri="p/o.tif"
        )

        response = self.client.get(f"/v1/api/products/?job_id={self.job.id}")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_unauthenticated(self):
        """Test unauthenticated request returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/v1/api/products/")
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class ProductDetailViewTest(TestCase):
    """Tests for ProductDetailView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="proddetail@test.com", password="pass1234")
        self.org = Organization.objects.create(name="ProdDetailOrg", user=self.user)
        self.user.organization = self.org
        self.user.organization_id = self.org.id
        self.user.save()
        self.client.force_authenticate(user=self.user)
        self.dataset = Dataset.objects.create(name="DetailDS", org=self.org)
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )

    @patch("products.visualization_views.S3Service")
    def test_detail_success(self, MockS3):
        """Test getting product detail."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_presigned_download_url.return_value = "https://dl.example.com"

        product = Product.objects.create(
            dataset=self.dataset, job=self.job, type="orthomosaic",
            uri="products/ortho.tif", resolution_cm=2.5
        )

        response = self.client.get(f"/v1/api/products/{product.id}/")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["type"], "orthomosaic")
        self.assertIn("download_url", response.data)

    @patch("products.visualization_views.S3Service")
    def test_detail_not_found(self, MockS3):
        """Test getting nonexistent product returns 404."""
        response = self.client.get(f"/v1/api/products/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    @patch("products.visualization_views.S3Service")
    def test_detail_empty_uri(self, MockS3):
        """Test product with empty URI has null download_url."""
        product = Product.objects.create(
            dataset=self.dataset, job=self.job, type="dsm", uri=""
        )

        response = self.client.get(f"/v1/api/products/{product.id}/")
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIsNone(response.data["download_url"])


class ProductModelTest(TestCase):
    """Tests for Product model methods."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="pmodel@test.com", password="pass1234")
        self.org = Organization.objects.create(name="ModelOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="ModelDS", org=self.org)

    def test_get_category_2d(self):
        """Test 2D product category."""
        product = Product(dataset=self.dataset, type="orthomosaic", uri="x")
        self.assertEqual(product.get_category(), "2D Raster")

    def test_get_category_3d(self):
        """Test 3D product category."""
        product = Product(dataset=self.dataset, type="pointcloud", uri="x")
        self.assertEqual(product.get_category(), "3D Model")

    def test_get_category_calibration(self):
        """Test calibration product category."""
        product = Product(dataset=self.dataset, type="ndvi", uri="x")
        self.assertEqual(product.get_category(), "Calibration")

    def test_get_category_reconstruction(self):
        """Test reconstruction product category."""
        product = Product(dataset=self.dataset, type="sparse_reconstruction", uri="x")
        self.assertEqual(product.get_category(), "Reconstruction")

    def test_get_category_other(self):
        """Test other product category."""
        product = Product(dataset=self.dataset, type="preview", uri="x")
        self.assertEqual(product.get_category(), "Other")

    def test_str(self):
        """Test string representation."""
        product = Product(dataset=self.dataset, type="orthomosaic", uri="x")
        self.assertIn("Orthomosaic", str(product))
