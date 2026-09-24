"""Tests for uploads presentation views and dataset management views."""

import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Organization, UserModel
from apps.uploads.infrastructure.models import Dataset, Image, UploadStatus
from apps.uploads.domain.constants import UploadStatusName
from apps.jobs.processing_stages import JobStatus


class InitiateMultipartUploadViewTest(TestCase):
    """Tests for InitiateMultipartUploadView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="init_view@test.com", password="pass1234")
        self.org = Organization.objects.create(name="InitOrg", user=self.user)
        self.client.force_authenticate(user=self.user)
        UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.COMPLETED, defaults={"label": "Completed"})

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_initiate_success(self, MockS3):
        """Test successful multipart upload initiation."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_s3_key.return_value = "orgs/1/file.jpg"
        mock_s3.create_multipart_upload.return_value = "upload-id-view"

        ds = Dataset.objects.create(name="ViewDS", org=self.org)
        response = self.client.post("/v1/api/uploads/multipart/init/", {
            "dataset_name": "ViewDS",
            "dataset_id": str(ds.id),
            "batch_id": str(uuid.uuid4()),
            "file_name": "dataset.zip",
            "file_type": "ARCHIVE",
            "content_type": "application/zip",
            "file_size": 1024000,
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("upload_id", response.data)
        self.assertIn("s3_key", response.data)

    def test_initiate_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.post("/v1/api/uploads/multipart/init/", {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SignMultipartPartViewTest(TestCase):
    """Tests for SignMultipartPartView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="sign_view@test.com", password="pass1234")
        self.org = Organization.objects.create(name="SignViewOrg", user=self.user)
        self.client.force_authenticate(user=self.user)
        pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        self.dataset = Dataset.objects.create(name="SignViewDS", org=self.org)
        self.image = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="sign_view.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=pending,
            s3_key="orgs/1/sign_view.jpg",
            s3_upload_id="s3-up-sign",
        )

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_sign_part_success(self, MockS3):
        """Test successful part signing."""
        mock_s3 = MockS3.return_value
        mock_s3.generate_presigned_url_part.return_value = "https://signed-url.example.com"

        response = self.client.post("/v1/api/uploads/multipart/sign-part/", {
            "upload_id": str(self.image.id),
            "part_number": 1,
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("url", response.data)


class CompleteMultipartUploadViewTest(TestCase):
    """Tests for CompleteMultipartUploadView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="complete_view@test.com", password="pass1234")
        self.org = Organization.objects.create(name="CompleteViewOrg", user=self.user)
        self.client.force_authenticate(user=self.user)
        pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        UploadStatus.objects.get_or_create(name=UploadStatusName.COMPLETED, defaults={"label": "Completed"})
        self.dataset = Dataset.objects.create(name="CompleteViewDS", org=self.org)
        self.image = Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="complete_view.jpg",
            file_size=1024,
            content_type="image/jpeg",
            status=pending,
            s3_key="orgs/1/complete_view.jpg",
            s3_upload_id="s3-up-complete",
            file_type="IMAGE",
        )

    @patch("apps.uploads.application.multipart_use_cases.S3Service")
    def test_complete_success(self, MockS3):
        """Test successful multipart upload completion."""
        mock_s3 = MockS3.return_value
        mock_s3.complete_multipart_upload.return_value = None

        response = self.client.post("/v1/api/uploads/multipart/complete/", {
            "upload_id": str(self.image.id),
            "parts": [{"PartNumber": 1, "ETag": "\"abc123\""}],
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UploadFromUrlViewTest(TestCase):
    """Tests for UploadFromUrlView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="urlview@test.com", password="pass1234")
        self.org = Organization.objects.create(name="UrlViewOrg", user=self.user)
        self.client.force_authenticate(user=self.user)
        UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})

    @patch("apps.uploads.presentation.views.download_and_process_url_task")
    @patch("apps.uploads.application.uri_upload_use_casees.S3Service")
    @patch("apps.uploads.presentation.serializers.requests")
    def test_upload_from_url_success(self, mock_requests, MockS3, mock_download_task):
        """Test successful URL upload initiation."""
        mock_head_resp = MagicMock()
        mock_head_resp.status_code = 200
        mock_head_resp.headers = {"Content-Length": "1024"}
        mock_head_resp.__enter__ = MagicMock(return_value=mock_head_resp)
        mock_head_resp.__exit__ = MagicMock(return_value=False)
        mock_requests.head.return_value = mock_head_resp
        mock_requests.RequestException = Exception

        mock_s3 = MockS3.return_value
        mock_s3.generate_s3_key.return_value = "orgs/1/import.zip"

        ds = Dataset.objects.create(name="UrlViewDS", org=self.org)
        response = self.client.post("/v1/api/uploads/upload/url/", {
            "file_url": "https://mybucket.s3.amazonaws.com/data.zip?X-Amz-Signature=abc123",
            "dataset_name": "UrlViewDS",
            "dataset_id": str(ds.id),
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("upload_id", response.data)
        mock_download_task.delay.assert_called_once()


class DatasetDetailViewTest(TestCase):
    """Tests for DatasetDetailView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="dsdetail@test.com", password="pass1234")
        self.org = Organization.objects.create(name="DSDetailOrg", user=self.user)
        self.client.force_authenticate(user=self.user)
        self.dataset = Dataset.objects.create(name="DetailDS", org=self.org)
        pending, _ = UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})
        Image.objects.create(
            user_id=self.user.id,
            dataset=self.dataset,
            batch_id=uuid.uuid4(),
            file_name="detail.jpg",
            file_size=2048,
            content_type="image/jpeg",
            status=pending,
            s3_key="key/detail.jpg",
            file_type="IMAGE",
        )

    def test_get_detail_success(self):
        """Test getting dataset detail with statistics."""
        response = self.client.get(f"/v1/api/uploads/datasets/{self.dataset.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "DetailDS")
        self.assertEqual(response.data["statistics"]["total_images"], 1)

    def test_get_detail_not_found(self):
        """Test getting nonexistent dataset returns 404."""
        response = self.client.get(f"/v1/api/uploads/datasets/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DatasetListViewTest(TestCase):
    """Tests for DatasetListView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="dslist@test.com", password="pass1234")
        self.org = Organization.objects.create(name="DSListOrg", user=self.user)
        self.user.organization = self.org
        self.user.save()
        self.client.force_authenticate(user=self.user)
        UploadStatus.objects.get_or_create(name=UploadStatusName.PENDING, defaults={"label": "Pending"})

    def test_list_empty(self):
        """Test listing datasets when none exist."""
        response = self.client.get("/v1/api/uploads/datasets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_with_datasets(self):
        """Test listing datasets returns results."""
        for i in range(3):
            Dataset.objects.create(name=f"ListDS{i}", org=self.org)
        response = self.client.get("/v1/api/uploads/datasets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_list_search_filter(self):
        """Test searching datasets by name."""
        Dataset.objects.create(name="AlphaDS", org=self.org)
        Dataset.objects.create(name="BetaDS", org=self.org)
        response = self.client.get("/v1/api/uploads/datasets/?search=Alpha")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_ordering(self):
        """Test ordering datasets by name."""
        Dataset.objects.create(name="Zebra", org=self.org)
        Dataset.objects.create(name="Alpha", org=self.org)
        response = self.client.get("/v1/api/uploads/datasets/?order_by=name")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["name"], "Alpha")


class DatasetDeleteViewTest(TestCase):
    """Tests for DatasetDeleteView."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="dsdelete@test.com", password="pass1234")
        self.org = Organization.objects.create(name="DSDeleteOrg", user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_delete_success(self):
        """Test deleting a dataset."""
        ds = Dataset.objects.create(name="DeleteMe", org=self.org)
        response = self.client.delete(f"/v1/api/uploads/datasets/{ds.id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Dataset.objects.filter(id=ds.id).exists())

    def test_delete_not_found(self):
        """Test deleting nonexistent dataset."""
        response = self.client.delete(f"/v1/api/uploads/datasets/{uuid.uuid4()}/delete/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_with_active_jobs(self):
        """Test deleting dataset with active processing jobs is forbidden."""
        from apps.jobs.infra.db.models.models import ProcessingJob
        ds = Dataset.objects.create(name="ActiveJobDS", org=self.org)
        ProcessingJob.objects.create(
            dataset=ds,
            resolution_gsd=5.0,
            status=JobStatus.PROCESSING,
        )
        response = self.client.delete(f"/v1/api/uploads/datasets/{ds.id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PermissionsTest(TestCase):
    """Tests for IsAIServiceAuthenticated permission."""

    def test_valid_token(self):
        """Test that valid AI token passes permission."""
        from apps.uploads.permissions import IsAIServiceAuthenticated

        perm = IsAIServiceAuthenticated()
        request = MagicMock()
        request.META = {"HTTP_X_AI_TOKEN": "test-secret"}

        with patch("apps.uploads.permissions.settings") as mock_settings:
            mock_settings.AI_GATEWAY_SECRET_KEY = "test-secret"
            self.assertTrue(perm.has_permission(request, None))

    def test_invalid_token(self):
        """Test that invalid AI token fails permission."""
        from apps.uploads.permissions import IsAIServiceAuthenticated

        perm = IsAIServiceAuthenticated()
        request = MagicMock()
        request.META = {"HTTP_X_AI_TOKEN": "wrong-secret"}

        with patch("apps.uploads.permissions.settings") as mock_settings:
            mock_settings.AI_GATEWAY_SECRET_KEY = "correct-secret"
            self.assertFalse(perm.has_permission(request, None))

    def test_no_expected_token(self):
        """Test that missing config always fails."""
        from apps.uploads.permissions import IsAIServiceAuthenticated

        perm = IsAIServiceAuthenticated()
        request = MagicMock()
        request.META = {"HTTP_X_AI_TOKEN": "anything"}

        with patch("apps.uploads.permissions.settings") as mock_settings:
            mock_settings.AI_GATEWAY_SECRET_KEY = None
            self.assertFalse(perm.has_permission(request, None))

    def test_no_token_header(self):
        """Test that missing token header fails."""
        from apps.uploads.permissions import IsAIServiceAuthenticated

        perm = IsAIServiceAuthenticated()
        request = MagicMock()
        request.META = {}

        with patch("apps.uploads.permissions.settings") as mock_settings:
            mock_settings.AI_GATEWAY_SECRET_KEY = "some-secret"
            self.assertFalse(perm.has_permission(request, None))


class MiddlewareTest(TestCase):
    """Tests for JwtAuthMiddleware."""

    def test_get_user_valid_token(self):
        """Test that a valid JWT token returns the correct user."""
        from apps.uploads.middleware import get_user
        import asyncio

        user = UserModel.objects.create_user(email="mw@test.com", password="pass1234")
        mock_user = MagicMock()
        mock_user.id = user.id

        with patch("apps.uploads.middleware.AccessToken") as MockToken, \
             patch("apps.uploads.middleware.User") as MockUser:
            mock_token = MagicMock()
            mock_token.__getitem__ = MagicMock(return_value=user.id)
            MockToken.return_value = mock_token
            MockUser.objects.get.return_value = mock_user

            loop = asyncio.new_event_loop()
            try:
                resolved = loop.run_until_complete(get_user("valid-token"))
            finally:
                loop.close()
            self.assertEqual(resolved.id, user.id)

    def test_get_user_invalid_token(self):
        """Test that an invalid token returns AnonymousUser."""
        from apps.uploads.middleware import get_user
        from rest_framework_simplejwt.exceptions import InvalidToken
        import asyncio

        with patch("apps.uploads.middleware.AccessToken") as MockToken:
            MockToken.side_effect = InvalidToken("bad")

            resolved = asyncio.get_event_loop().run_until_complete(get_user("bad-token"))
            self.assertTrue(resolved.is_anonymous)


class NotificationServiceTest(TestCase):
    """Tests for DjangoChannelsNotificationService."""

    @patch("apps.uploads.domain.ainotification.get_channel_layer")
    @patch("apps.uploads.domain.ainotification.async_to_sync")
    def test_notify_frontend(self, mock_a2s, mock_get_layer):
        """Test that notification is sent to the correct group."""
        from apps.uploads.domain.ainotification import DjangoChannelsNotificationService

        mock_send = MagicMock()
        mock_a2s.return_value = mock_send

        svc = DjangoChannelsNotificationService()
        svc.notify_frontend("ds-123", "UPLOAD_COMPLETED", {"upload_id": "u1"})

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        self.assertEqual(args[0], "dataset_ds-123")

    @patch("apps.uploads.domain.ainotification.get_channel_layer")
    @patch("apps.uploads.domain.ainotification.async_to_sync")
    def test_notify_frontend_failure_handled(self, mock_a2s, mock_get_layer):
        """Test that notification failures are handled gracefully."""
        from apps.uploads.domain.ainotification import DjangoChannelsNotificationService

        mock_a2s.return_value = MagicMock(side_effect=Exception("Redis down"))

        svc = DjangoChannelsNotificationService()
        svc.notify_frontend("ds-123", "UPLOAD_FAILED", {})
