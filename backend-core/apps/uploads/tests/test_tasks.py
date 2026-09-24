"""Tests for upload tasks (process_archive, cleanup, export, url download)."""

import uuid
from unittest.mock import patch, MagicMock, mock_open

from django.test import TestCase

from accounts.models import Organization, UserModel
from apps.uploads.infrastructure.models import Dataset, Image, UploadStatus
from apps.uploads.domain.constants import UploadStatusName


class ProcessArchiveTaskTest(TestCase):
    """Tests for process_archive_task."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="archive@test.com", password="pass1234")
        self.org = Organization.objects.create(name="ArchiveOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="ArchiveDS", org=self.org)
        self.pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.COMPLETED, defaults={"label": "Completed"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.PROCESSING, defaults={"label": "Processing"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.FAILED, defaults={"label": "Failed"})

    @patch("apps.uploads.Tasks.tasks.DjangoChannelsNotificationService")
    @patch("apps.uploads.Tasks.tasks.S3Service")
    def test_archive_not_found(self, MockS3, MockNotifier):
        """Test that processing a nonexistent archive returns error message."""
        from apps.uploads.Tasks.tasks import process_archive_task

        result = process_archive_task(str(uuid.uuid4()), "key/missing.zip")

        self.assertEqual(result, "Archive record not found")

    @patch("apps.uploads.Tasks.tasks.DjangoChannelsNotificationService")
    @patch("apps.uploads.Tasks.tasks.S3Service")
    def test_archive_zip_with_images(self, MockS3, MockNotifier):
        """Test extracting images from a valid zip archive."""
        import zipfile
        import tempfile
        import os

        archive_img = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="test.zip",
            file_size=5000,
            content_type="application/zip",
            status=self.pending,
            s3_key="orgs/1/test.zip",
            file_type="ARCHIVE",
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(tmp, "w") as zf:
            zf.writestr("photo1.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100)
            zf.writestr("photo2.tiff", b"\x49\x49\x2a\x00" + b"\x00" * 100)
        tmp.close()

        mock_s3 = MockS3.return_value
        mock_s3.bucket_name = "test-bucket"
        mock_s3.s3_client = MagicMock()

        def fake_download(bucket, key, fileobj):
            with open(tmp.name, "rb") as f:
                fileobj.write(f.read())

        mock_s3.s3_client.download_fileobj.side_effect = fake_download
        mock_s3.upload_bytes.return_value = None

        from apps.uploads.Tasks.tasks import process_archive_task

        result = process_archive_task(str(archive_img.id), "orgs/1/test.zip")

        self.assertIn("Successfully extracted", result)
        os.unlink(tmp.name)

    @patch("apps.uploads.Tasks.tasks.DjangoChannelsNotificationService")
    @patch("apps.uploads.Tasks.tasks.S3Service")
    def test_archive_empty_zip(self, MockS3, MockNotifier):
        """Test that an empty zip raises error and sets status to FAILED."""
        import zipfile
        import tempfile
        import os

        archive_img = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="empty.zip",
            file_size=500,
            content_type="application/zip",
            status=self.pending,
            s3_key="orgs/1/empty.zip",
            file_type="ARCHIVE",
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(tmp, "w") as zf:
            pass
        tmp.close()

        mock_s3 = MockS3.return_value
        mock_s3.bucket_name = "test-bucket"
        mock_s3.s3_client = MagicMock()

        def fake_download(bucket, key, fileobj):
            with open(tmp.name, "rb") as f:
                fileobj.write(f.read())

        mock_s3.s3_client.download_fileobj.side_effect = fake_download

        from apps.uploads.Tasks.tasks import process_archive_task

        result = process_archive_task(str(archive_img.id), "orgs/1/empty.zip")

        self.assertIn("Failed", result)
        archive_img.refresh_from_db()
        self.assertEqual(archive_img.status.name, UploadStatusName.FAILED)
        os.unlink(tmp.name)


class DownloadAndProcessUrlTaskTest(TestCase):
    """Tests for download_and_process_url_task."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="urltask@test.com", password="pass1234")
        self.org = Organization.objects.create(name="UrlOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="UrlDS", org=self.org)
        self.pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.COMPLETED, defaults={"label": "Completed"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.PROCESSING, defaults={"label": "Processing"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.FAILED, defaults={"label": "Failed"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.DOWNLOADING, defaults={"label": "Downloading"})

    @patch("apps.uploads.Tasks.urluploadtasks.process_archive_task")
    @patch("apps.uploads.Tasks.urluploadtasks.DjangoChannelsNotificationService")
    @patch("apps.uploads.Tasks.urluploadtasks.S3Service")
    def test_download_success(self, MockS3, MockNotifier, mock_archive_task):
        """Test successful URL download triggers archive processing."""
        image = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="import.zip",
            file_size=0,
            content_type="application/zip",
            status=self.pending,
            s3_key="orgs/1/import.zip",
            file_type="ARCHIVE",
        )

        mock_s3 = MockS3.return_value
        mock_s3.copy_from_presigned_url.return_value = "orgs/1/import.zip"
        mock_s3.bucket_name = "test-bucket"
        mock_s3.s3_client = MagicMock()
        mock_s3.s3_client.head_object.return_value = {"ContentLength": 9999}

        from apps.uploads.Tasks.urluploadtasks import download_and_process_url_task

        download_and_process_url_task(str(image.id), "https://source.url/file.zip", "orgs/1/import.zip")

        mock_s3.copy_from_presigned_url.assert_called_once()
        mock_archive_task.delay.assert_called_once()

    @patch("apps.uploads.Tasks.urluploadtasks.process_archive_task")
    @patch("apps.uploads.Tasks.urluploadtasks.DjangoChannelsNotificationService")
    @patch("apps.uploads.Tasks.urluploadtasks.S3Service")
    def test_download_failure(self, MockS3, MockNotifier, mock_archive_task):
        """Test failed URL download sets status to FAILED."""
        image = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="fail.zip",
            file_size=0,
            content_type="application/zip",
            status=self.pending,
            s3_key="orgs/1/fail.zip",
            file_type="ARCHIVE",
        )

        mock_s3 = MockS3.return_value
        mock_s3.copy_from_presigned_url.side_effect = Exception("Network error")

        from apps.uploads.Tasks.urluploadtasks import download_and_process_url_task

        download_and_process_url_task(str(image.id), "https://bad.url/file.zip", "orgs/1/fail.zip")

        image.refresh_from_db()
        self.assertEqual(image.status.name, UploadStatusName.FAILED)
        mock_archive_task.delay.assert_not_called()


class CleanupStaleUploadsTaskTest(TestCase):
    """Tests for cleanup_stale_uploads_task."""

    @patch("apps.uploads.Tasks.tasks.S3Service")
    def test_cleanup_no_stale(self, MockS3):
        """Test cleanup when no stale uploads exist."""
        with patch("apps.uploads.Tasks.tasks.UploadRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.delete_old_pending_uploads.return_value = None

            from apps.uploads.Tasks.tasks import cleanup_stale_uploads_task

            result = cleanup_stale_uploads_task()

            self.assertEqual(result, "No stale uploads found.")

    @patch("apps.uploads.Tasks.tasks.S3Service")
    def test_cleanup_with_stale(self, MockS3):
        """Test cleanup deletes stale uploads."""
        mock_s3 = MockS3.return_value

        with patch("apps.uploads.Tasks.tasks.UploadRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.delete_old_pending_uploads.return_value = ["key1", "key2"]

            from apps.uploads.Tasks.tasks import cleanup_stale_uploads_task

            result = cleanup_stale_uploads_task()

            self.assertIn("2", result)
            self.assertEqual(mock_s3.delete_object.call_count, 2)
