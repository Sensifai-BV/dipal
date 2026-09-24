"""Unit tests for upload URL view and tasks."""
import unittest
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from rest_framework import status
from rest_framework.test import force_authenticate

from accounts.models import Organization, UserModel

VALID_PRESIGNED_URL = (
    "https://bucket.s3.amazonaws.com/data.zip"
    "?X-Amz-Signature=abc123&X-Amz-Expires=3600"
)


def _bypass_url_validation(self, value):
    """Skip domain/signature/HEAD checks in unit tests."""
    return value


class TestUploadFromUrlView(TestCase):
    """Tests for POST upload-from-url endpoint."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserModel.objects.create_user(
            email="upload@test.com", password="testpass123"
        )
        self.org = Organization.objects.create(name="Upload Org", user=self.user)
        self.user.organization = self.org
        self.user.save()

    @patch('apps.uploads.presentation.serializers.UploadFromUrlRequestSerializer.validate_file_url', _bypass_url_validation)
    @patch('apps.uploads.presentation.views.download_and_process_url_task')
    @patch('apps.uploads.presentation.views.StartUploadFromUrlUseCase')
    def test_successful_url_upload(self, mock_use_case_cls, mock_task):
        """Successful URL upload returns 202 with upload details."""
        from apps.uploads.presentation.views import UploadFromUrlView

        mock_entity = MagicMock()
        mock_entity.id = uuid.uuid4()
        mock_entity.dataset_id = uuid.uuid4()
        mock_entity.s3_key = "uploads/test.zip"
        mock_use_case_cls.return_value.execute.return_value = mock_entity

        request = self.factory.post(
            '/api/uploads/url/',
            data={
                'file_url': VALID_PRESIGNED_URL,
                'dataset_name': 'Test Dataset',
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)

        view = UploadFromUrlView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("upload_id", response.data)
        self.assertIn("status", response.data)
        self.assertEqual(response.data["status"], "DOWNLOADING")
        mock_task.delay.assert_called_once()

    @patch('apps.uploads.presentation.serializers.UploadFromUrlRequestSerializer.validate_file_url', _bypass_url_validation)
    @patch('apps.uploads.presentation.views.download_and_process_url_task')
    @patch('apps.uploads.presentation.views.StartUploadFromUrlUseCase')
    def test_url_upload_uses_org_id_from_user(self, mock_use_case_cls, mock_task):
        """Upload uses organization_id from user object."""
        from apps.uploads.presentation.views import UploadFromUrlView

        mock_entity = MagicMock()
        mock_entity.id = uuid.uuid4()
        mock_entity.dataset_id = uuid.uuid4()
        mock_entity.s3_key = "uploads/test.zip"
        mock_use_case_cls.return_value.execute.return_value = mock_entity

        request = self.factory.post(
            '/api/uploads/url/',
            data={
                'file_url': VALID_PRESIGNED_URL,
                'dataset_name': 'Test Dataset',
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)

        view = UploadFromUrlView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        call_kwargs = mock_use_case_cls.return_value.execute.call_args
        org_val = call_kwargs.kwargs.get('organization_id')
        self.assertEqual(org_val, self.org.id)

    @patch('apps.uploads.presentation.serializers.UploadFromUrlRequestSerializer.validate_file_url', _bypass_url_validation)
    @patch('apps.uploads.presentation.views.download_and_process_url_task')
    @patch('apps.uploads.presentation.views.StartUploadFromUrlUseCase')
    def test_url_upload_derives_file_name(self, mock_use_case_cls, mock_task):
        """File name is derived from URL when not provided."""
        from apps.uploads.presentation.views import UploadFromUrlView

        mock_entity = MagicMock()
        mock_entity.id = uuid.uuid4()
        mock_entity.dataset_id = uuid.uuid4()
        mock_entity.s3_key = "uploads/data.zip"
        mock_use_case_cls.return_value.execute.return_value = mock_entity

        request = self.factory.post(
            '/api/uploads/url/',
            data={
                'file_url': VALID_PRESIGNED_URL,
                'dataset_name': 'Test Dataset',
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)

        view = UploadFromUrlView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        call_kwargs = mock_use_case_cls.return_value.execute.call_args
        self.assertEqual(call_kwargs.kwargs.get('file_name'), 'data.zip')

    @patch('apps.uploads.presentation.serializers.UploadFromUrlRequestSerializer.validate_file_url', _bypass_url_validation)
    @patch('apps.uploads.presentation.views.download_and_process_url_task')
    @patch('apps.uploads.presentation.views.StartUploadFromUrlUseCase')
    def test_url_upload_generates_batch_id(self, mock_use_case_cls, mock_task):
        """A UUID batch_id is generated when not provided."""
        from apps.uploads.presentation.views import UploadFromUrlView

        mock_entity = MagicMock()
        mock_entity.id = uuid.uuid4()
        mock_entity.dataset_id = uuid.uuid4()
        mock_entity.s3_key = "uploads/data.zip"
        mock_use_case_cls.return_value.execute.return_value = mock_entity

        request = self.factory.post(
            '/api/uploads/url/',
            data={
                'file_url': VALID_PRESIGNED_URL,
                'dataset_name': 'Test Dataset',
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)

        view = UploadFromUrlView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        call_kwargs = mock_use_case_cls.return_value.execute.call_args
        batch_id = call_kwargs.kwargs.get('batch_id')
        self.assertIsNotNone(batch_id)

    @patch('apps.uploads.presentation.serializers.UploadFromUrlRequestSerializer.validate_file_url', _bypass_url_validation)
    @patch('apps.uploads.presentation.views.download_and_process_url_task')
    @patch('apps.uploads.presentation.views.StartUploadFromUrlUseCase')
    def test_url_upload_use_case_error_returns_400(self, mock_use_case_cls, mock_task):
        """Use case error returns 400 with error message."""
        from apps.uploads.presentation.views import UploadFromUrlView

        mock_use_case_cls.return_value.execute.side_effect = ValueError("Dataset not found")

        request = self.factory.post(
            '/api/uploads/url/',
            data={
                'file_url': VALID_PRESIGNED_URL,
                'dataset_name': 'Test Dataset',
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)

        view = UploadFromUrlView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_url_upload_missing_file_url_returns_400(self):
        """Missing file_url returns 400 validation error."""
        from apps.uploads.presentation.views import UploadFromUrlView

        request = self.factory.post(
            '/api/uploads/url/',
            data={'dataset_name': 'Test Dataset'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)

        view = UploadFromUrlView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestDownloadAndProcessUrlTask(TestCase):
    """Tests for the download_and_process_url_task Celery task."""

    @patch('apps.uploads.Tasks.urluploadtasks.process_archive_task')
    @patch('apps.uploads.Tasks.urluploadtasks.DjangoChannelsNotificationService')
    @patch('apps.uploads.Tasks.urluploadtasks.S3Service')
    @patch('apps.uploads.Tasks.urluploadtasks.UploadRepository')
    def test_successful_download(self, mock_repo_cls, mock_s3_cls, mock_notifier_cls, mock_archive_task):
        """Successful download queues archive processing."""
        from apps.uploads.Tasks.urluploadtasks import download_and_process_url_task

        mock_repo = mock_repo_cls.return_value
        mock_entity = MagicMock()
        mock_entity.dataset_id = uuid.uuid4()
        mock_repo.get_by_id.return_value = mock_entity

        mock_s3 = mock_s3_cls.return_value
        mock_s3.s3_client.head_object.return_value = {'ContentLength': 1024}
        mock_s3.bucket_name = 'test-bucket'

        download_and_process_url_task(
            upload_id="upload-123",
            file_url="https://example.com/test.zip",
            s3_key="uploads/test.zip",
        )

        mock_s3.copy_from_presigned_url.assert_called_once_with(
            source_url="https://example.com/test.zip",
            destination_key="uploads/test.zip",
        )
        mock_archive_task.delay.assert_called_once_with(
            upload_id="upload-123",
            s3_key="uploads/test.zip",
        )

    @patch('apps.uploads.Tasks.urluploadtasks.DjangoChannelsNotificationService')
    @patch('apps.uploads.Tasks.urluploadtasks.S3Service')
    @patch('apps.uploads.Tasks.urluploadtasks.UploadRepository')
    def test_download_failure_marks_failed(self, mock_repo_cls, mock_s3_cls, mock_notifier_cls):
        """Download failure marks upload as FAILED and notifies frontend."""
        from apps.uploads.Tasks.urluploadtasks import download_and_process_url_task

        mock_repo = mock_repo_cls.return_value
        mock_entity = MagicMock()
        mock_entity.dataset_id = uuid.uuid4()
        mock_repo.get_by_id.return_value = mock_entity

        mock_s3 = mock_s3_cls.return_value
        mock_s3.copy_from_presigned_url.side_effect = Exception("Connection timeout")

        download_and_process_url_task(
            upload_id="upload-456",
            file_url="https://example.com/bad.zip",
            s3_key="uploads/bad.zip",
        )

        mock_repo.update_status.assert_any_call("upload-456", 'FAILED')
        mock_notifier_cls.return_value.notify_frontend.assert_any_call(
            str(mock_entity.dataset_id),
            'DOWNLOAD_FAILED',
            unittest.mock.ANY,
        )


if __name__ == "__main__":
    unittest.main()
