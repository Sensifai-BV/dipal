"""Tests for multipart upload use cases."""

import uuid
from unittest.mock import patch, MagicMock, PropertyMock

from django.test import TestCase

from accounts.models import Organization, UserModel
from apps.uploads.infrastructure.models import Dataset, Image, UploadStatus
from apps.uploads.domain.constants import UploadStatusName


class InitiateMultipartUploadUseCaseTest(TestCase):
    """Tests for InitiateMultipartUploadUseCase."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="mp@test.com", password="pass1234")
        self.org = Organization.objects.create(name="MPOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="MPDataset", org=self.org)
        UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.COMPLETED, defaults={"label": "Completed"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.PROCESSING, defaults={"label": "Processing"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.FAILED, defaults={"label": "Failed"})

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_initiate_image_upload(self, MockS3):
        """Test initiating a multipart upload for an image file."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_s3_key.return_value = "orgs/1/users/1/datasets/abc/batch/img.jpg"
        mock_s3.create_multipart_upload.return_value = "upload-id-123"

        from apps.uploads.application.multipart_use_cases import InitiateMultipartUploadUseCase

        uc = InitiateMultipartUploadUseCase()
        uc.s3_service = mock_s3

        result = uc.execute(
            user_id=self.user.id,
            organization_id=self.org.id,
            dataset_name="MPDataset",
            file_name="photo.jpg",
            file_type="IMAGE",
            content_type="image/jpeg",
            file_size=1024000,
            batch_id=uuid.uuid4(),
            dataset_id=self.dataset.id,
        )

        self.assertIsNotNone(result.id)
        self.assertEqual(result.s3_upload_id, "upload-id-123")
        mock_s3.create_multipart_upload.assert_called_once()

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_initiate_archive_upload_detects_type(self, MockS3):
        """Test that .zip extension is correctly classified as ARCHIVE."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_s3_key.return_value = "orgs/1/file.zip"
        mock_s3.create_multipart_upload.return_value = "upload-id-456"

        from apps.uploads.application.multipart_use_cases import InitiateMultipartUploadUseCase

        uc = InitiateMultipartUploadUseCase()
        uc.s3_service = mock_s3

        result = uc.execute(
            user_id=self.user.id,
            organization_id=self.org.id,
            dataset_name="MPDataset",
            file_name="data.zip",
            file_type="IMAGE",
            content_type="application/octet-stream",
            file_size=5000000,
            batch_id=uuid.uuid4(),
            dataset_id=self.dataset.id,
        )

        img = Image.objects.get(id=result.id)
        self.assertEqual(img.file_type, "ARCHIVE")

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_initiate_creates_dataset_when_none_provided(self, MockS3):
        """Test that a dataset is created when dataset_id is None."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_s3_key.return_value = "orgs/1/file.jpg"
        mock_s3.create_multipart_upload.return_value = "upload-id-789"

        from apps.uploads.application.multipart_use_cases import InitiateMultipartUploadUseCase

        uc = InitiateMultipartUploadUseCase()
        uc.s3_service = mock_s3

        result = uc.execute(
            user_id=self.user.id,
            organization_id=self.org.id,
            dataset_name="NewDataset",
            file_name="photo.jpg",
            file_type="IMAGE",
            content_type="image/jpeg",
            file_size=1024,
            batch_id=uuid.uuid4(),
            dataset_id=None,
        )

        self.assertTrue(Dataset.objects.filter(name="NewDataset").exists())

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_initiate_s3_failure_raises(self, MockS3):
        """Test that S3 failure propagates."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_s3_key.return_value = "orgs/1/file.jpg"
        mock_s3.create_multipart_upload.side_effect = Exception("S3 down")

        from apps.uploads.application.multipart_use_cases import InitiateMultipartUploadUseCase

        uc = InitiateMultipartUploadUseCase()
        uc.s3_service = mock_s3

        with self.assertRaises(Exception):
            uc.execute(
                user_id=self.user.id,
                organization_id=self.org.id,
                dataset_name="MPDataset",
                file_name="photo.jpg",
                file_type="IMAGE",
                content_type="image/jpeg",
                file_size=1024,
                batch_id=uuid.uuid4(),
                dataset_id=self.dataset.id,
            )


class SignMultipartPartUseCaseTest(TestCase):
    """Tests for SignMultipartPartUseCase."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="sign@test.com", password="pass1234")
        self.org = Organization.objects.create(name="SignOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="SignDS", org=self.org)
        pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        self.image = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="test.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=pending,
            s3_key="orgs/1/test.jpg",
            s3_upload_id="s3-upload-abc",
        )

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_sign_part_success(self, MockS3):
        """Test generating a presigned URL for a part."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_presigned_url_part.return_value = "https://s3.example.com/part?signed"

        from apps.uploads.application.multipart_use_cases import SignMultipartPartUseCase

        uc = SignMultipartPartUseCase()
        uc.s3_service = mock_s3

        url = uc.execute(upload_db_id=self.image.id, part_number=1)

        self.assertEqual(url, "https://s3.example.com/part?signed")
        mock_s3.generate_presigned_url_part.assert_called_once_with(
            key="orgs/1/test.jpg",
            upload_id="s3-upload-abc",
            part_number=1,
        )

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_sign_part_upload_not_found(self, MockS3):
        """Test signing part for nonexistent upload raises exception."""
        from apps.uploads.application.multipart_use_cases import SignMultipartPartUseCase

        uc = SignMultipartPartUseCase()
        uc.s3_service = MockS3.return_value

        with self.assertRaises(Exception):
            uc.execute(upload_db_id=uuid.uuid4(), part_number=1)

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_sign_part_no_s3_upload_id(self, MockS3):
        """Test that signing fails when image has no s3_upload_id."""
        self.image.s3_upload_id = None
        self.image.save()

        from apps.uploads.application.multipart_use_cases import SignMultipartPartUseCase

        uc = SignMultipartPartUseCase()
        uc.s3_service = MockS3.return_value

        with self.assertRaises(ValueError):
            uc.execute(upload_db_id=self.image.id, part_number=1)


class CompleteMultipartUploadUseCaseTest(TestCase):
    """Tests for CompleteMultipartUploadUseCase."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="complete@test.com", password="pass1234")
        self.org = Organization.objects.create(name="CompleteOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="CompleteDS", org=self.org)
        self.pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.COMPLETED, defaults={"label": "Completed"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.PROCESSING, defaults={"label": "Processing"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.FAILED, defaults={"label": "Failed"})

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_complete_image_upload(self, MockS3):
        """Test completing a non-archive upload sets status to COMPLETED."""
        mock_s3 = MockS3.return_value
        mock_s3.complete_multipart_upload.return_value = None

        image = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="photo.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=self.pending,
            s3_key="orgs/1/photo.jpg",
            s3_upload_id="s3-upload-xyz",
            file_type="IMAGE",
        )

        from apps.uploads.application.multipart_use_cases import CompleteMultipartUploadUseCase

        uc = CompleteMultipartUploadUseCase()
        uc.s3_service = mock_s3

        parts = [{"PartNumber": 1, "ETag": "\"abc\""}]
        result = uc.execute(upload_db_id=image.id, parts=parts)

        self.assertEqual(result.status, UploadStatusName.COMPLETED)

    @patch("apps.uploads.application.multipart_use_cases.process_archive_task")
    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_complete_archive_upload_triggers_task(self, MockS3, mock_archive_task):
        """Test completing an archive upload triggers process_archive_task."""
        mock_s3 = MockS3.return_value
        mock_s3.complete_multipart_upload.return_value = None
        mock_s3.read_object_head.return_value = b"PK\x03\x04" + b"\x00" * 2044

        image = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="data.zip",
            file_size=5000,
            content_type="application/zip",
            status=self.pending,
            s3_key="orgs/1/data.zip",
            s3_upload_id="s3-upload-arch",
            file_type="ARCHIVE",
        )

        from apps.uploads.application.multipart_use_cases import CompleteMultipartUploadUseCase

        uc = CompleteMultipartUploadUseCase()
        uc.s3_service = mock_s3

        parts = [{"PartNumber": 1, "ETag": "\"abc\""}]
        result = uc.execute(upload_db_id=image.id, parts=parts)

        mock_archive_task.delay.assert_called_once()

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_complete_not_found(self, MockS3):
        """Test completing a nonexistent upload raises exception."""
        from apps.uploads.application.multipart_use_cases import CompleteMultipartUploadUseCase

        uc = CompleteMultipartUploadUseCase()
        uc.s3_service = MockS3.return_value

        with self.assertRaises(Exception):
            uc.execute(upload_db_id=uuid.uuid4(), parts=[])


class AbortAndRetryMultipartUploadUseCaseTest(TestCase):
    """Tests for AbortAndRetryMultipartUploadUseCase."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="retry@test.com", password="pass1234")
        self.org = Organization.objects.create(name="RetryOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="RetryDS", org=self.org)
        self.pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        self.image = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="retry.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=self.pending,
            s3_key="orgs/1/retry.jpg",
            s3_upload_id="old-upload-id",
        )

    @patch("apps.uploads.application.multipart_use_cases.UploadRepository")
    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_abort_and_retry_success(self, MockS3, MockRepo):
        """Test aborting and retrying creates a new multipart upload."""
        mock_s3 = MockS3.return_value
        mock_s3.abort_multipart_upload.return_value = None
        mock_s3.create_multipart_upload.return_value = "new-upload-id"

        mock_repo = MockRepo.return_value
        mock_existing = MagicMock()
        mock_existing.id = self.image.id
        mock_existing.user_id = self.user.id
        mock_existing.s3_upload_id = "old-upload-id"
        mock_existing.s3_key = "orgs/1/retry.jpg"
        mock_existing.content_type = "image/jpeg"
        mock_repo.get_by_id.return_value = mock_existing

        from apps.uploads.application.multipart_use_cases import AbortAndRetryMultipartUploadUseCase

        uc = AbortAndRetryMultipartUploadUseCase()
        uc.s3_service = mock_s3
        uc.repo = mock_repo

        result = uc.execute(upload_db_id=self.image.id, user_id=self.user.id)

        self.assertEqual(result["s3_upload_id"], "new-upload-id")
        mock_s3.abort_multipart_upload.assert_called_once()

    @patch("apps.uploads.application.multipart_use_cases.UploadRepository")
    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_abort_retry_wrong_user(self, MockS3, MockRepo):
        """Test that another user cannot retry someone else's upload."""
        other_user = UserModel.objects.create_user(email="other@test.com", password="pass1234")

        mock_repo = MockRepo.return_value
        mock_existing = MagicMock()
        mock_existing.id = self.image.id
        mock_existing.user_id = self.user.id
        mock_repo.get_by_id.return_value = mock_existing

        from apps.uploads.application.multipart_use_cases import AbortAndRetryMultipartUploadUseCase

        uc = AbortAndRetryMultipartUploadUseCase()
        uc.s3_service = MockS3.return_value
        uc.repo = mock_repo

        with self.assertRaises(PermissionError):
            uc.execute(upload_db_id=self.image.id, user_id=other_user.id)

    @patch("apps.uploads.application.multipart_use_cases.UploadRepository")
    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_abort_retry_not_found(self, MockS3, MockRepo):
        """Test retrying a nonexistent upload raises ValueError."""
        mock_repo = MockRepo.return_value
        mock_repo.get_by_id.return_value = None

        from apps.uploads.application.multipart_use_cases import AbortAndRetryMultipartUploadUseCase

        uc = AbortAndRetryMultipartUploadUseCase()
        uc.s3_service = MockS3.return_value
        uc.repo = mock_repo

        with self.assertRaises(ValueError):
            uc.execute(upload_db_id=uuid.uuid4(), user_id=self.user.id)


class ProcessAICallbackUseCaseTest(TestCase):
    """Tests for ProcessAICallbackUseCase."""

    def test_callback_success(self):
        """Test successful AI callback updates job status to COMPLETED."""
        from apps.uploads.application.multipart_use_cases import ProcessAICallbackUseCase

        mock_repo = MagicMock()
        mock_notifier = MagicMock()
        mock_job = MagicMock()
        mock_job.dataset_id = "ds-123"
        mock_job.id = "job-1"
        mock_repo.get_by_id.return_value = mock_job

        uc = ProcessAICallbackUseCase(ai_job_repo=mock_repo, notification_service=mock_notifier)

        result_dto = MagicMock()
        result_dto.job_id = "job-1"
        result_dto.status = "success"
        result_dto.outputs = [MagicMock(s3_key="output/file.tif")]

        uc.execute(result_dto)

        self.assertEqual(mock_job.status, UploadStatusName.COMPLETED)
        mock_repo.save_outputs.assert_called_once()
        mock_notifier.notify_frontend.assert_called_once()

    def test_callback_failure(self):
        """Test failed AI callback sets job status to FAILED."""
        from apps.uploads.application.multipart_use_cases import ProcessAICallbackUseCase

        mock_repo = MagicMock()
        mock_notifier = MagicMock()
        mock_job = MagicMock()
        mock_job.dataset_id = "ds-123"
        mock_job.id = "job-2"
        mock_repo.get_by_id.return_value = mock_job

        uc = ProcessAICallbackUseCase(ai_job_repo=mock_repo, notification_service=mock_notifier)

        result_dto = MagicMock()
        result_dto.job_id = "job-2"
        result_dto.status = "error"

        uc.execute(result_dto)

        self.assertEqual(mock_job.status, UploadStatusName.FAILED)

    def test_callback_job_not_found(self):
        """Test AI callback raises when job not found."""
        from apps.uploads.application.multipart_use_cases import ProcessAICallbackUseCase

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_notifier = MagicMock()

        uc = ProcessAICallbackUseCase(ai_job_repo=mock_repo, notification_service=mock_notifier)

        result_dto = MagicMock()
        result_dto.job_id = "nonexistent"

        with self.assertRaises(ValueError):
            uc.execute(result_dto)
