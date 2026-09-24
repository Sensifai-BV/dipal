"""Tests for S3Service, UploadRepository, and related infrastructure."""

import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase

from accounts.models import Organization, UserModel
from apps.uploads.infrastructure.models import Dataset, Image, UploadStatus
from apps.uploads.infrastructure.repositories import UploadRepository
from apps.uploads.domain.constants import UploadStatusName
from apps.uploads.domain.entities import UploadEntity


class S3ServiceTest(TestCase):
    """Tests for S3Service domain service (all S3 calls mocked)."""

    @patch("apps.uploads.domain.services.boto3")
    def test_generate_s3_key(self, mock_boto):
        """Test S3 key generation format."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        key = svc.generate_s3_key(
            organization_id=1,
            user_id=42,
            dataset_id="ds-abc",
            batch_id="batch-xyz",
            file_name="photo.jpg",
        )

        self.assertIn("orgs/1/", key)
        self.assertIn("users/42/", key)
        self.assertIn("datasets/ds-abc/", key)
        self.assertIn("photo.jpg", key)

    @patch("apps.uploads.domain.services.boto3")
    def test_create_multipart_upload(self, mock_boto):
        """Test creating a multipart upload returns upload ID."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_client.create_multipart_upload.return_value = {"UploadId": "mp-123"}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        upload_id = svc.create_multipart_upload("key/file.jpg", "image/jpeg")

        self.assertEqual(upload_id, "mp-123")

    @patch("apps.uploads.domain.services.boto3")
    def test_generate_presigned_url_part(self, mock_boto):
        """Test generating presigned URL for a part."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_client.generate_presigned_url.return_value = "https://signed-url"
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        url = svc.generate_presigned_url_part("key/f.jpg", "up-123", 1)

        self.assertEqual(url, "https://signed-url")
        mock_client.generate_presigned_url.assert_called_once()

    @patch("apps.uploads.domain.services.boto3")
    def test_complete_multipart_upload(self, mock_boto):
        """Test completing a multipart upload."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_client.complete_multipart_upload.return_value = {"ETag": "\"abc\""}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        svc.complete_multipart_upload("key/f.jpg", "up-123", [{"PartNumber": 1, "ETag": "\"a\""}])

        mock_client.complete_multipart_upload.assert_called_once()

    @patch("apps.uploads.domain.services.boto3")
    def test_abort_multipart_upload(self, mock_boto):
        """Test aborting a multipart upload."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        svc.abort_multipart_upload("key/f.jpg", "up-123")

        mock_client.abort_multipart_upload.assert_called_once()

    @patch("apps.uploads.domain.services.boto3")
    def test_upload_bytes(self, mock_boto):
        """Test uploading raw bytes."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        svc.upload_bytes("key/out.tif", b"data", "image/tiff")

        mock_client.put_object.assert_called_once()

    @patch("apps.uploads.domain.services.boto3")
    def test_download_file(self, mock_boto):
        """Test downloading a file from S3."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_body = MagicMock()
        mock_body.read.return_value = b"filedata"
        mock_client.get_object.return_value = {"Body": mock_body}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        data = svc.download_file("key/f.jpg")

        self.assertEqual(data, b"filedata")

    @patch("apps.uploads.domain.services.boto3")
    def test_read_object_head(self, mock_boto):
        """Test reading the first N bytes of an object."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_body = MagicMock()
        mock_body.read.return_value = b"PK\x03\x04"
        mock_client.get_object.return_value = {"Body": mock_body}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        head = svc.read_object_head("key/f.zip", n_bytes=4)

        self.assertEqual(head, b"PK\x03\x04")

    @patch("apps.uploads.domain.services.boto3")
    def test_delete_object(self, mock_boto):
        """Test deleting an S3 object."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        svc.delete_object("key/f.jpg")

        mock_client.delete_object.assert_called_once()

    @patch("apps.uploads.domain.services.boto3")
    def test_list_files(self, mock_boto):
        """Test listing files with a prefix."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_client.list_objects_v2.return_value = {"Contents": [{"Key": "a.jpg"}, {"Key": "b.jpg"}]}
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        files = svc.list_files("prefix/")

        self.assertEqual(len(files), 2)

    @patch("apps.uploads.domain.services.requests")
    @patch("apps.uploads.domain.services.boto3")
    def test_copy_from_presigned_url(self, mock_boto, mock_requests):
        """Test copying from a presigned URL to S3."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_boto.client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.raw = MagicMock()
        mock_requests.get.return_value = mock_response

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        result = svc.copy_from_presigned_url("https://source.url/file.jpg", "dest/key.jpg")

        self.assertEqual(result, "dest/key.jpg")
        mock_client.upload_fileobj.assert_called_once()

    @patch("apps.uploads.domain.services.boto3")
    def test_generate_presigned_download_url(self, mock_boto):
        """Test generating a presigned download URL."""
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_client.generate_presigned_url.return_value = "https://download-url"
        mock_boto.client.return_value = mock_client

        from apps.uploads.domain.services import S3Service
        svc = S3Service()

        url = svc.generate_presigned_download_url("key/f.jpg")

        self.assertEqual(url, "https://download-url")


class UploadRepositoryTest(TestCase):
    """Tests for UploadRepository."""

    def setUp(self):
        self.user = UserModel.objects.create_user(email="repo@test.com", password="pass1234")
        self.org = Organization.objects.create(name="RepoOrg", user=self.user)
        self.dataset = Dataset.objects.create(name="RepoDS", org=self.org)
        self.pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.COMPLETED, defaults={"label": "Completed"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.PROCESSING, defaults={"label": "Processing"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.FAILED, defaults={"label": "Failed"})

    def test_create_entity(self):
        """Test creating an upload record from entity."""
        entity = UploadEntity(
            id=None,
            user_id=self.user.id,
            organization_id=self.org.id,
            dataset_id=self.dataset.id,
            dataset_name="RepoDS",
            batch_id=uuid.uuid4(),
            file_name="test.jpg",
            file_path="key/test.jpg",
            file_size=2048,
            content_type="image/jpeg",
            upload_status=UploadStatusName.PENDING,
            s3_key="key/test.jpg",
            file_type="IMAGE",
            status=UploadStatusName.PENDING,
            parent_archive_id=None,
        )

        result = UploadRepository.create(entity)

        self.assertIsNotNone(result.id)
        self.assertEqual(result.file_name, "test.jpg")

    def test_get_by_id(self):
        """Test getting upload by ID."""
        img = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="exists.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=self.pending,
            s3_key="key/exists.jpg",
        )

        result = UploadRepository.get_by_id(img.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.file_name, "exists.jpg")

    def test_get_by_id_not_found(self):
        """Test getting nonexistent upload returns None."""
        result = UploadRepository.get_by_id(uuid.uuid4())

        self.assertIsNone(result)

    def test_update_status(self):
        """Test updating upload status."""
        img = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="status.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=self.pending,
            s3_key="key/status.jpg",
        )

        result = UploadRepository.update_status(img.id, UploadStatusName.COMPLETED)

        self.assertEqual(result.status, UploadStatusName.COMPLETED)

    def test_update_status_invalid(self):
        """Test that updating to a nonexistent status raises ValueError."""
        img = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="invalid.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=self.pending,
            s3_key="key/invalid.jpg",
        )

        with self.assertRaises(ValueError):
            UploadRepository.update_status(img.id, "NONEXISTENT_STATUS")

    def test_get_or_create_dataset(self):
        """Test get_or_create_dataset returns existing or creates new."""
        ds = UploadRepository.get_or_create_dataset("RepoDS", self.org.id)
        self.assertEqual(ds.id, self.dataset.id)

        ds2 = UploadRepository.get_or_create_dataset("BrandNew", self.org.id)
        self.assertNotEqual(ds2.id, self.dataset.id)
        self.assertEqual(ds2.name, "BrandNew")

    def test_get_user_uploads(self):
        """Test listing user uploads with filters."""
        batch = uuid.uuid4()
        for i in range(3):
            Image.objects.create(
                user_id=self.user.id,
                dataset=self.dataset,
                batch_id=batch,
                file_name=f"upload_{i}.jpg",
                file_size=1024,
                content_type="image/jpeg",
                status=self.pending,
                s3_key=f"key/upload_{i}.jpg",
                file_type="IMAGE",
            )

        uploads = UploadRepository.get_user_uploads(user_id=self.user.id)
        self.assertEqual(len(uploads), 3)

        uploads_by_type = UploadRepository.get_user_uploads(user_id=self.user.id, file_type="IMAGE")
        self.assertEqual(len(uploads_by_type), 3)

    def test_set_multipart_id(self):
        """Test setting s3_upload_id on an image."""
        img = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="mp.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=self.pending,
            s3_key="key/mp.jpg",
        )

        repo = UploadRepository()
        repo.set_multipart_id(img.id, "new-s3-upload-id")

        img.refresh_from_db()
        self.assertEqual(img.s3_upload_id, "new-s3-upload-id")

    def test_get_dataset_archive_status(self):
        """Test getting archive status for a dataset."""
        Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="archive.zip",
            file_size=5000,
            content_type="application/zip",
            status=self.pending,
            s3_key="key/archive.zip",
            file_type="ARCHIVE",
        )

        result = UploadRepository.get_dataset_archive_status(self.dataset.id)

        self.assertIsNotNone(result)
        self.assertEqual(result["file_name"], "archive.zip")

    def test_get_dataset_archive_status_not_found(self):
        """Test getting archive status when no archive exists."""
        result = UploadRepository.get_dataset_archive_status(self.dataset.id)

        self.assertIsNone(result)
