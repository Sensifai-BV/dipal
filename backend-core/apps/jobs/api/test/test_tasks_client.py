"""Unit tests for Celery tasks, AI Gateway client, repositories, and use cases."""
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.jobs.infra.services.ai_client import AIGatewayClient
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.domains.use_cases import StartProcessingUseCase
from apps.jobs.domains.entities import JobEntity
from apps.jobs.domains.exceptions import BusinessRuleValidationException, ResourceNotFoundException
from apps.jobs.processing_stages import JobStatus, AnalysisMode
from apps.uploads.infrastructure.models import Dataset
from accounts.models import Organization, UserModel


class TestAIGatewayClient(TestCase):
    """Tests for AIGatewayClient HTTP interactions."""

    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_init_sets_attributes(self, mock_settings):
        """Client reads URL, secret, and timeout from settings."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret123"
        client = AIGatewayClient()
        self.assertEqual(client.base_url, "http://ai:8080")
        self.assertEqual(client.secret_key, "secret123")
        self.assertEqual(client.timeout, 120)

    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_get_headers(self, mock_settings):
        """Headers include content type and secret key."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret123"
        client = AIGatewayClient()
        headers = client._get_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-API-Secret-Key"], "secret123")

    @patch("apps.jobs.infra.services.ai_client.requests.post")
    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_start_processing_job_success(self, mock_settings, mock_post):
        """Successful job submission returns AI response."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret"
        mock_response = MagicMock()
        mock_response.json.return_value = {"job_id": "ai-123", "status": "running"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AIGatewayClient()
        result = client.start_processing_job(
            job_id="job-1", dataset_id="ds-1", download_url="http://url",
            parameters={"resolution_gsd": 5.0}
        )
        self.assertEqual(result["job_id"], "ai-123")
        mock_post.assert_called_once()

    @patch("apps.jobs.infra.services.ai_client.requests.post")
    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_start_processing_job_with_starting_stage(self, mock_settings, mock_post):
        """Starting stage is included in payload when provided."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret"
        mock_response = MagicMock()
        mock_response.json.return_value = {"job_id": "ai-123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AIGatewayClient()
        client.start_processing_job(
            job_id="job-1", dataset_id="ds-1", download_url="http://url",
            starting_stage="sfm"
        )
        call_kwargs = mock_post.call_args
        self.assertIn("starting_stage", call_kwargs.kwargs.get("json", call_kwargs[1].get("json", {})))

    @patch("apps.jobs.infra.services.ai_client.requests.post")
    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_start_processing_job_failure(self, mock_settings, mock_post):
        """Network failure raises exception."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret"
        import requests
        mock_post.side_effect = requests.RequestException("Connection refused")

        client = AIGatewayClient()
        with self.assertRaises(Exception) as ctx:
            client.start_processing_job(
                job_id="job-1", dataset_id="ds-1", download_url="http://url"
            )
        self.assertIn("AI Gateway", str(ctx.exception))

    @patch("apps.jobs.infra.services.ai_client.requests.get")
    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_get_job_status_success(self, mock_settings, mock_get):
        """Get job status returns response."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret"
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "running", "progress": 50}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = AIGatewayClient()
        result = client.get_job_status("ai-123")
        self.assertEqual(result["status"], "running")

    @patch("apps.jobs.infra.services.ai_client.requests.get")
    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_get_job_status_failure(self, mock_settings, mock_get):
        """Get job status failure raises exception."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret"
        import requests
        mock_get.side_effect = requests.RequestException("Timeout")

        client = AIGatewayClient()
        with self.assertRaises(Exception):
            client.get_job_status("ai-123")

    @patch("apps.jobs.infra.services.ai_client.requests.post")
    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_cancel_job_success(self, mock_settings, mock_post):
        """Cancel job returns response."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret"
        mock_response = MagicMock()
        mock_response.json.return_value = {"cancelled": True}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client = AIGatewayClient()
        result = client.cancel_job("ai-123")
        self.assertTrue(result["cancelled"])

    @patch("apps.jobs.infra.services.ai_client.requests.post")
    @patch("apps.jobs.infra.services.ai_client.settings")
    def test_cancel_job_failure(self, mock_settings, mock_post):
        """Cancel failure raises exception."""
        mock_settings.AI_GATEWAY_URL = "http://ai:8080"
        mock_settings.AI_GATEWAY_SECRET_KEY = "secret"
        import requests
        mock_post.side_effect = requests.RequestException("Error")

        client = AIGatewayClient()
        with self.assertRaises(Exception):
            client.cancel_job("ai-123")


class TestStartProcessingUseCase(TestCase):
    """Tests for StartProcessingUseCase business logic."""

    def setUp(self):
        self.mock_repo = MagicMock()
        self.mock_queue = MagicMock()
        self.use_case = StartProcessingUseCase(
            job_repo=self.mock_repo, queue_service=self.mock_queue
        )

    def test_execute_success(self):
        """Successful execution creates and queues job."""
        self.mock_repo.dataset_exists.return_value = True
        saved = JobEntity(
            dataset_id=1,
            resolution_gsd=5.0,
            radiometric_calibration=True,
            analysis_mode="fast",
            status=JobStatus.PENDING,
        )
        saved.id = str(uuid.uuid4())
        self.mock_repo.create_job.return_value = saved

        result = self.use_case.execute(
            dataset_id=1, resolution=5.0, calibration=True, analysis_mode="fast"
        )
        self.assertEqual(result.id, saved.id)
        self.mock_repo.create_job.assert_called_once()
        self.mock_queue.push_job_to_queue.assert_called_once()

    def test_execute_zero_resolution(self):
        """Resolution zero raises BusinessRuleValidationException."""
        with self.assertRaises(BusinessRuleValidationException):
            self.use_case.execute(dataset_id=1, resolution=0, calibration=False)

    def test_execute_negative_resolution(self):
        """Negative resolution raises BusinessRuleValidationException."""
        with self.assertRaises(BusinessRuleValidationException):
            self.use_case.execute(dataset_id=1, resolution=-1, calibration=False)

    def test_execute_invalid_analysis_mode(self):
        """Invalid analysis mode raises BusinessRuleValidationException."""
        with self.assertRaises(BusinessRuleValidationException):
            self.use_case.execute(
                dataset_id=1, resolution=5.0, calibration=False, analysis_mode="invalid"
            )

    def test_execute_dataset_not_found(self):
        """Non-existent dataset raises ResourceNotFoundException."""
        self.mock_repo.dataset_exists.return_value = False
        with self.assertRaises(ResourceNotFoundException):
            self.use_case.execute(dataset_id=999, resolution=5.0, calibration=False)

    def test_execute_full_mode(self):
        """Full analysis mode creates job correctly."""
        self.mock_repo.dataset_exists.return_value = True
        saved = JobEntity(
            dataset_id=1, resolution_gsd=5.0, radiometric_calibration=True,
            analysis_mode=AnalysisMode.FULL, status=JobStatus.PENDING,
        )
        saved.id = str(uuid.uuid4())
        self.mock_repo.create_job.return_value = saved

        result = self.use_case.execute(
            dataset_id=1, resolution=5.0, calibration=True, analysis_mode="full"
        )
        self.assertEqual(result.analysis_mode, "full")


class TestProcessDroneImageryTask(TestCase):
    """Tests for process_drone_imagery Celery task."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="task@test.com", password="pass")
        self.org = Organization.objects.create(name="TaskOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="TaskDs", org=self.org)

    @patch("apps.jobs.infra.services.tasks.tasks.AIGatewayClient")
    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_metadata_urls")
    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_image_urls")
    def test_task_submits_to_ai(self, mock_img_urls, mock_meta_urls, mock_client_class):
        """Task generates URLs and submits to AI Gateway."""
        from apps.jobs.infra.services.tasks.tasks import process_drone_imagery

        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PENDING
        )
        mock_img_urls.return_value = [{"url": "http://s3/img1.jpg", "filename": "img1.jpg"}]
        mock_meta_urls.return_value = []
        mock_client = MagicMock()
        mock_client.start_processing_job.return_value = {"job_id": "ai-123"}
        mock_client_class.return_value = mock_client

        process_drone_imagery(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.PROCESSING)
        mock_client.start_processing_job.assert_called_once()

    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_image_urls")
    def test_task_fails_no_images(self, mock_img_urls):
        """Task fails if no images found."""
        from apps.jobs.infra.services.tasks.tasks import process_drone_imagery

        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.PENDING
        )
        mock_img_urls.return_value = []

        process_drone_imagery(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)

    def test_task_nonexistent_job(self):
        """Task handles non-existent job gracefully."""
        from apps.jobs.infra.services.tasks.tasks import process_drone_imagery
        process_drone_imagery(str(uuid.uuid4()))

    @patch("apps.jobs.infra.services.tasks.tasks.boto3")
    @patch("apps.jobs.infra.services.tasks.tasks.settings")
    def test_generate_image_urls(self, mock_settings, mock_boto3):
        """generate_dataset_image_urls creates presigned URLs."""
        from apps.jobs.infra.services.tasks.tasks import generate_dataset_image_urls
        from apps.uploads.infrastructure.models import Image, UploadStatus

        mock_settings.AWS_S3_RAW_IMAGES_BUCKET = "raw-bucket"
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_S3_ENDPOINT_URL = None
        mock_settings.AWS_ACCESS_KEY_ID = "key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "secret"

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3/signed"
        mock_boto3.client.return_value = mock_client
        mock_boto3.session.Config.return_value = MagicMock()

        pending_status, _ = UploadStatus.objects.get_or_create(
            name="PENDING", defaults={"label": "Pending"}
        )
        completed_status, _ = UploadStatus.objects.get_or_create(
            name="COMPLETED", defaults={"label": "Completed"}
        )
        Image.objects.create(
            dataset=self.dataset,
            user_id=self.user.id,
            file_name="img1.jpg",
            s3_key="orgs/1/img1.jpg",
            file_type="IMAGE",
            status=completed_status,
        )

        urls = generate_dataset_image_urls(self.dataset)
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0]["url"], "https://s3/signed")
        self.assertEqual(urls[0]["filename"], "img1.jpg")

    @patch("apps.jobs.infra.services.tasks.tasks.boto3")
    @patch("apps.jobs.infra.services.tasks.tasks.settings")
    def test_generate_metadata_urls(self, mock_settings, mock_boto3):
        """generate_dataset_metadata_urls creates presigned URLs."""
        from apps.jobs.infra.services.tasks.tasks import generate_dataset_metadata_urls
        from apps.uploads.infrastructure.models import Image, UploadStatus

        mock_settings.AWS_S3_RAW_IMAGES_BUCKET = "raw-bucket"
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_S3_ENDPOINT_URL = None
        mock_settings.AWS_ACCESS_KEY_ID = "key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "secret"

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3/signed"
        mock_boto3.client.return_value = mock_client
        mock_boto3.session.Config.return_value = MagicMock()

        status_obj, _ = UploadStatus.objects.get_or_create(
            name="COMPLETED", defaults={"label": "Completed"}
        )
        Image.objects.create(
            dataset=self.dataset,
            user_id=self.user.id,
            file_name="data.nav",
            s3_key="orgs/1/data.nav",
            file_type="METADATA",
            status=status_obj,
        )

        urls = generate_dataset_metadata_urls(self.dataset)
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0]["filename"], "data.nav")

    @patch("apps.jobs.infra.services.tasks.tasks.boto3")
    @patch("apps.jobs.infra.services.tasks.tasks.settings")
    def test_generate_image_urls_no_bucket(self, mock_settings, mock_boto3):
        """No bucket configured returns empty list."""
        from apps.jobs.infra.services.tasks.tasks import generate_dataset_image_urls

        mock_settings.AWS_S3_RAW_IMAGES_BUCKET = None
        mock_settings.AWS_STORAGE_BUCKET_NAME = None
        mock_settings.AWS_S3_REGION_NAME = "us-east-1"
        mock_settings.AWS_S3_ENDPOINT_URL = None
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.AWS_SECRET_ACCESS_KEY = None

        urls = generate_dataset_image_urls(self.dataset)
        self.assertEqual(urls, [])

    @patch("apps.jobs.infra.services.tasks.tasks.AIGatewayClient")
    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_metadata_urls")
    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_image_urls")
    def test_task_skips_cancelled_job(self, mock_img_urls, mock_meta_urls, mock_client_class):
        """Task skips dispatch when job is already cancelled."""
        from apps.jobs.infra.services.tasks.tasks import process_drone_imagery

        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.CANCELLED
        )

        process_drone_imagery(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)
        mock_client_class.return_value.start_processing_job.assert_not_called()

    @patch("apps.jobs.infra.services.tasks.tasks.AIGatewayClient")
    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_metadata_urls")
    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_image_urls")
    def test_task_skips_completed_job(self, mock_img_urls, mock_meta_urls, mock_client_class):
        """Task skips dispatch when job is already completed."""
        from apps.jobs.infra.services.tasks.tasks import process_drone_imagery

        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )

        process_drone_imagery(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)
        mock_client_class.return_value.start_processing_job.assert_not_called()

    @patch("apps.jobs.infra.services.tasks.tasks.AIGatewayClient")
    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_metadata_urls")
    @patch("apps.jobs.infra.services.tasks.tasks.generate_dataset_image_urls")
    def test_task_skips_failed_job(self, mock_img_urls, mock_meta_urls, mock_client_class):
        """Task skips dispatch when job has already failed."""
        from apps.jobs.infra.services.tasks.tasks import process_drone_imagery

        job = ProcessingJob.objects.create(
            dataset=self.dataset, resolution_gsd=5.0, status=JobStatus.FAILED
        )

        process_drone_imagery(str(job.id))

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        mock_client_class.return_value.start_processing_job.assert_not_called()
