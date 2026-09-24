# processings/test/test.py

from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.conf import settings
from accounts.models import Organization, UserModel
from apps.processings.models.models import ProcessingResult, ProcessingStatus
from apps.uploads.infrastructure.models import Dataset


class StartProcessingViewTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(email="proc@test.com", password="pass1234")
        self.org = Organization.objects.create(name="Test Org", user=self.user)
        self.dataset = Dataset.objects.create(name="Test Dataset", org=self.org)
        self.client.force_authenticate(user=self.user)
        self.url = reverse('processings:start_processing', kwargs={'dataset_id': self.dataset.id})

    @patch('apps.processings.tasks.tasks.dispatch_processing_task.delay')
    def test_start_processing_success(self, mock_dispatch):
        """Test that a valid request initiates processing and queues the task."""
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['status'], ProcessingStatus.QUEUED)
        self.assertTrue(ProcessingResult.objects.filter(dataset=self.dataset).exists())
        result = ProcessingResult.objects.get(dataset=self.dataset)
        self.assertEqual(result.status, ProcessingStatus.QUEUED)

        mock_dispatch.assert_called_once_with(result.id)

    @patch('apps.processings.tasks.tasks.dispatch_processing_task.delay')
    def test_prevent_duplicate_processing(self, mock_dispatch):
        """Test that an already-processing dataset returns 200."""
        ProcessingResult.objects.create(
            dataset=self.dataset,
            status=ProcessingStatus.PROCESSING
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "This dataset is currently being processed.")

        mock_dispatch.assert_not_called()

    @patch('apps.processings.tasks.tasks.dispatch_processing_task.delay')
    def test_retry_failed_job(self, mock_dispatch):
        """Test retrying a failed job resets status and re-queues."""
        result = ProcessingResult.objects.create(
            dataset=self.dataset,
            status=ProcessingStatus.FAILED,
            error_message="Old error"
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        result.refresh_from_db()
        self.assertEqual(result.status, ProcessingStatus.QUEUED)
        self.assertIsNone(result.error_message)

        mock_dispatch.assert_called_once_with(result.id)

    def test_queue_full_capacity(self):
        """Test that when queue is at capacity, return 503."""
        max_queue = getattr(settings, 'MAX_PROCESSING_QUEUE', 5)

        for i in range(max_queue):
            ds = Dataset.objects.create(name=f"Dummy {i}", org=self.org)
            ProcessingResult.objects.create(dataset=ds, status=ProcessingStatus.PROCESSING)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['error'], "System is busy, please try again later.")

    def test_nonexistent_dataset(self):
        """Test starting processing for a nonexistent dataset returns 500 (caught by generic handler)."""
        import uuid
        url = reverse('processings:start_processing', kwargs={'dataset_id': uuid.uuid4()})
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR])


class AICallbackViewTests(APITestCase):
    def setUp(self):
        self.user = UserModel.objects.create_user(email="cb@test.com", password="pass1234")
        self.org = Organization.objects.create(name="Callback Org", user=self.user)
        self.dataset = Dataset.objects.create(name="Callback Test Dataset", org=self.org)
        self.client.force_authenticate(user=self.user)
        self.processing_job = ProcessingResult.objects.create(
            dataset=self.dataset,
            status=ProcessingStatus.PROCESSING
        )
        self.url = reverse('processings:ai_callback')

    @patch('apps.processings.services.services.SocketNotificationService.send_status_update')
    def test_callback_progress_update(self, mock_socket):
        """Test progress callback updates job progress."""
        payload = {
            "job_id": str(self.processing_job.id),
            "type": "progress",
            "progress": 45
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.processing_job.refresh_from_db()
        self.assertEqual(self.processing_job.progress, 45)

    @patch('apps.processings.services.services.SocketNotificationService.send_status_update')
    def test_callback_completion(self, mock_socket):
        """Test completion callback saves outputs and marks job as completed."""
        payload = {
            "job_id": str(self.processing_job.id),
            "type": "complete",
            "outputs": {
                "orthomosaic": "http://s3.bucket/ortho.tif",
                "mesh": "http://s3.bucket/model.obj",
                "dsm": "http://s3.bucket/dsm.tif",
                "ndvi": "http://s3.bucket/ndvi.png"
            }
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.processing_job.refresh_from_db()
        self.assertEqual(self.processing_job.status, ProcessingStatus.COMPLETED)
        self.assertEqual(self.processing_job.progress, 100)
        self.assertEqual(self.processing_job.orthomosaic_url, "http://s3.bucket/ortho.tif")

    @patch('apps.processings.services.services.SocketNotificationService.send_status_update')
    def test_callback_error(self, mock_socket):
        """Test error callback marks job as failed with error message."""
        payload = {
            "job_id": str(self.processing_job.id),
            "type": "error",
            "message": "AI Processing Failed: Out of Memory"
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.processing_job.refresh_from_db()
        self.assertEqual(self.processing_job.status, ProcessingStatus.FAILED)
        self.assertEqual(self.processing_job.error_message, "AI Processing Failed: Out of Memory")

    def test_callback_invalid_job_id(self):
        """Test callback with nonexistent job_id returns 404."""
        import uuid
        payload = {
            "job_id": str(uuid.uuid4()),
            "type": "progress"
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_callback_missing_job_id(self):
        """Test callback without job_id returns 400."""
        payload = {"type": "progress"}

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
