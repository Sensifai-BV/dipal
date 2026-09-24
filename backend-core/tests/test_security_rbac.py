"""
Security and RBAC tests for the PhotoGear backend.

Covers:
- Permission class unit tests (IsAdmin, IsOrganizationOwner, IsAIService)
- Endpoint access control enforcement
- Cross-organization data isolation (IDOR protection)
- AI service authentication enforcement
- Default role assignment on registration
"""

import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory, override_settings
from rest_framework import status
from rest_framework.test import APIClient, force_authenticate

from accounts.models import Organization, UserModel, Role, RoleName
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus
from products.models import Product
from utils.permissions import IsAdmin, IsOrganizationOwner, IsAIService


class TestIsAdminPermission(TestCase):
    """Unit tests for the IsAdmin permission class."""

    def setUp(self):
        self.permission = IsAdmin()

    def test_superuser_granted(self):
        """Superusers always pass IsAdmin."""
        request = MagicMock()
        request.user.is_authenticated = True
        request.user.is_superuser = True
        self.assertTrue(self.permission.has_permission(request, None))

    def test_admin_role_granted(self):
        """Users with admin role pass IsAdmin."""
        request = MagicMock()
        request.user.is_authenticated = True
        request.user.is_superuser = False
        request.user.role = MagicMock()
        request.user.role.name = RoleName.ADMIN
        self.assertTrue(self.permission.has_permission(request, None))

    def test_user_role_denied(self):
        """Users with non-admin role are denied."""
        request = MagicMock()
        request.user.is_authenticated = True
        request.user.is_superuser = False
        request.user.role = MagicMock()
        request.user.role.name = RoleName.USER
        self.assertFalse(self.permission.has_permission(request, None))

    def test_no_role_denied(self):
        """Users without a role are denied."""
        request = MagicMock()
        request.user.is_authenticated = True
        request.user.is_superuser = False
        request.user.role = None
        self.assertFalse(self.permission.has_permission(request, None))

    def test_unauthenticated_denied(self):
        """Unauthenticated requests are denied."""
        request = MagicMock()
        request.user = None
        self.assertFalse(self.permission.has_permission(request, None))


class TestIsOrganizationOwnerPermission(TestCase):
    """Unit tests for the IsOrganizationOwner permission class."""

    def setUp(self):
        self.permission = IsOrganizationOwner()

    def test_superuser_always_passes(self):
        """Superusers pass object-level check."""
        request = MagicMock()
        request.user.is_superuser = True
        obj = MagicMock(org_id=uuid.uuid4())
        self.assertTrue(self.permission.has_object_permission(request, None, obj))

    def test_same_org_passes(self):
        """User in matching organization passes."""
        org_id = uuid.uuid4()
        request = MagicMock()
        request.user.is_superuser = False
        request.user.organization_id = org_id
        obj = MagicMock(org_id=org_id)
        self.assertTrue(self.permission.has_object_permission(request, None, obj))

    def test_different_org_denied(self):
        """User in different organization is denied."""
        request = MagicMock()
        request.user.is_superuser = False
        request.user.organization_id = uuid.uuid4()
        obj = MagicMock(org_id=uuid.uuid4())
        self.assertFalse(self.permission.has_object_permission(request, None, obj))

    def test_no_org_denied(self):
        """User with no organization is denied."""
        request = MagicMock()
        request.user.is_superuser = False
        request.user.organization_id = None
        obj = MagicMock(org_id=uuid.uuid4())
        self.assertFalse(self.permission.has_object_permission(request, None, obj))

    def test_custom_org_field(self):
        """Respects view.org_field attribute."""
        org_id = uuid.uuid4()
        request = MagicMock()
        request.user.is_superuser = False
        request.user.organization_id = org_id
        view = MagicMock(org_field="owner_org_id")
        obj = MagicMock(owner_org_id=org_id)
        self.assertTrue(self.permission.has_object_permission(request, view, obj))


class TestIsAIServicePermission(TestCase):
    """Unit tests for the IsAIService permission class."""

    def setUp(self):
        self.permission = IsAIService()

    @override_settings(AI_GATEWAY_SECRET_KEY="correct-key")
    def test_valid_key_passes(self):
        """Correct API secret key passes."""
        request = MagicMock()
        request.headers = {"X-API-Secret-Key": "correct-key"}
        request.META = {}
        self.assertTrue(self.permission.has_permission(request, None))

    @override_settings(AI_GATEWAY_SECRET_KEY="correct-key")
    def test_wrong_key_denied(self):
        """Wrong API secret key is denied."""
        request = MagicMock()
        request.headers = {"X-API-Secret-Key": "wrong-key"}
        request.META = {}
        self.assertFalse(self.permission.has_permission(request, None))

    @override_settings(AI_GATEWAY_SECRET_KEY="correct-key")
    def test_missing_key_denied(self):
        """Missing API secret key is denied."""
        request = MagicMock()
        request.headers = {}
        request.META = {}
        self.assertFalse(self.permission.has_permission(request, None))

    @override_settings(AI_GATEWAY_SECRET_KEY=None)
    def test_no_config_denied(self):
        """Missing server config always denies."""
        request = MagicMock()
        request.headers = {"X-API-Secret-Key": "any-key"}
        request.META = {}
        self.assertFalse(self.permission.has_permission(request, None))


class TestCrossOrgDataIsolation(TestCase):
    """
    Tests that users in Org A cannot access resources belonging to Org B.

    Covers: Jobs, Datasets, Products (IDOR protection).
    """

    def setUp(self):
        self.client = APIClient()
        self.user_a = UserModel.objects.create_user(email="user_a@test.com", password="pass123")
        self.org_a = Organization.objects.create(name="OrgA", user=self.user_a)
        self.user_a.organization = self.org_a
        self.user_a.save()

        self.user_b = UserModel.objects.create_user(email="user_b@test.com", password="pass123")
        self.org_b = Organization.objects.create(name="OrgB", user=self.user_b)
        self.user_b.organization = self.org_b
        self.user_b.save()

        self.dataset_a = Dataset.objects.create(name="DatasetA", org=self.org_a)
        self.dataset_b = Dataset.objects.create(name="DatasetB", org=self.org_b)

        self.job_a = ProcessingJob.objects.create(
            dataset=self.dataset_a, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )
        self.job_b = ProcessingJob.objects.create(
            dataset=self.dataset_b, resolution_gsd=5.0, status=JobStatus.COMPLETED
        )

        self.product_a = Product.objects.create(
            dataset=self.dataset_a, job=self.job_a, type="orthomosaic", uri="a/ortho.tif"
        )
        self.product_b = Product.objects.create(
            dataset=self.dataset_b, job=self.job_b, type="orthomosaic", uri="b/ortho.tif"
        )

    def test_job_list_only_own_org(self):
        """User A sees only Org A jobs."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/v1/api/jobs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [r["id"] for r in response.data["results"]]
        self.assertIn(str(self.job_a.id), job_ids)
        self.assertNotIn(str(self.job_b.id), job_ids)

    def test_job_detail_cross_org_denied(self):
        """User A cannot access Org B job detail."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/v1/api/jobs/{self.job_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_job_delete_cross_org_denied(self):
        """User A cannot delete Org B job."""
        self.client.force_authenticate(user=self.user_a)
        job_b_failed = ProcessingJob.objects.create(
            dataset=self.dataset_b, resolution_gsd=5.0, status=JobStatus.FAILED
        )
        response = self.client.delete(f"/v1/api/jobs/{job_b_failed.id}/delete/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.jobs.api.views.job_cancel_view.requests.post")
    def test_job_cancel_cross_org_denied(self, mock_post):
        """User A cannot cancel Org B job."""
        self.client.force_authenticate(user=self.user_a)
        job_b_running = ProcessingJob.objects.create(
            dataset=self.dataset_b, resolution_gsd=5.0, status=JobStatus.PROCESSING
        )
        response = self.client.post(f"/v1/api/jobs/{job_b_running.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_dataset_list_only_own_org(self):
        """User A sees only Org A datasets."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/v1/api/uploads/datasets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ds_names = [r["name"] for r in response.data["results"]]
        self.assertIn("DatasetA", ds_names)
        self.assertNotIn("DatasetB", ds_names)

    def test_dataset_detail_cross_org_denied(self):
        """User A cannot access Org B dataset detail."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/v1/api/uploads/datasets/{self.dataset_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("products.visualization_views.S3Service")
    def test_product_list_only_own_org(self, MockS3):
        """User A sees only Org A products."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/v1/api/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prod_ids = [r["id"] for r in response.data["results"]]
        self.assertIn(str(self.product_a.id), prod_ids)
        self.assertNotIn(str(self.product_b.id), prod_ids)

    @patch("products.visualization_views.S3Service")
    def test_product_detail_cross_org_denied(self, MockS3):
        """User A cannot access Org B product detail."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/v1/api/products/{self.product_b.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(AI_GATEWAY_SECRET_KEY="test-ai-secret")
class TestAIServiceEndpointProtection(TestCase):
    """
    Tests that AI-service endpoints reject requests without valid secret key.
    """

    def setUp(self):
        self.client = APIClient()

    def test_start_job_no_key(self):
        """Start job endpoint rejects requests without AI key."""
        response = self.client.post("/v1/api/jobs/start-job/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_start_job_wrong_key(self):
        """Start job endpoint rejects wrong AI key."""
        response = self.client.post(
            "/v1/api/jobs/start-job/", {}, format="json",
            HTTP_X_API_SECRET_KEY="wrong-key"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ai_callback_no_key(self):
        """AI callback endpoint rejects requests without key."""
        response = self.client.post("/v1/api/jobs/ai-callback/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_upload_init_no_key(self):
        """Product upload init rejects requests without key."""
        response = self.client.post("/v1/api/products/upload/init/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_chunk_no_key(self):
        """Product chunk endpoint rejects requests without key."""
        response = self.client.post("/v1/api/products/upload/chunk/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_complete_no_key(self):
        """Product complete endpoint rejects requests without key."""
        response = self.client.post("/v1/api/products/upload/complete/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_abort_no_key(self):
        """Product abort endpoint rejects requests without key."""
        response = self.client.post("/v1/api/products/upload/abort/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestUnauthenticatedEndpointProtection(TestCase):
    """Tests that authenticated endpoints reject unauthenticated requests."""

    def setUp(self):
        self.client = APIClient()

    def test_jobs_list_unauthenticated(self):
        """Job list requires authentication."""
        response = self.client.get("/v1/api/jobs/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_datasets_list_unauthenticated(self):
        """Dataset list requires authentication."""
        response = self.client.get("/v1/api/uploads/datasets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_products_list_unauthenticated(self):
        """Product list requires authentication."""
        response = self.client.get("/v1/api/products/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_unauthenticated(self):
        """Profile endpoint requires authentication."""
        response = self.client.get("/v1/accounts/profile/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dashboard_stats_unauthenticated(self):
        """Dashboard stats requires authentication."""
        response = self.client.get("/v1/api/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_init_unauthenticated(self):
        """Upload initiation requires authentication."""
        response = self.client.post("/v1/api/uploads/multipart/init/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestPublicEndpointsAccessible(TestCase):
    """Tests that public endpoints are accessible without authentication."""

    def setUp(self):
        self.client = APIClient()

    def test_health_check(self):
        """Health check is public (does not require authentication)."""
        response = self.client.get("/health/")
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_endpoint(self):
        """Login endpoint is public (POST returns 400 with empty body, not 401)."""
        response = self.client.post("/v1/accounts/login/", {}, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_endpoint(self):
        """Register endpoint is public (POST returns 400 with empty body, not 401)."""
        response = self.client.post("/v1/accounts/register/", {}, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestDefaultAdminRole(TestCase):
    """Tests that new users are assigned the admin role by default."""

    def setUp(self):
        Role.objects.get_or_create(id=1, defaults={"name": RoleName.ADMIN, "label": "Admin"})
        Role.objects.get_or_create(id=2, defaults={"name": RoleName.USER, "label": "Owner"})

    def test_create_user_gets_admin_role(self):
        """UserModel.objects.create_user assigns admin role by default."""
        user = UserModel.objects.create_user(email="newuser@test.com", password="pass123")
        self.assertIsNotNone(user.role)
        self.assertEqual(user.role.name, RoleName.ADMIN)

    def test_create_user_explicit_role_preserved(self):
        """Explicitly provided role is not overridden."""
        user_role = Role.objects.get(name=RoleName.USER)
        user = UserModel.objects.create_user(
            email="explicit_role@test.com", password="pass123", role=user_role
        )
        self.assertEqual(user.role.name, RoleName.USER)

    def test_register_without_role_defaults_to_admin(self):
        """Registration API defaults to admin role."""
        client = APIClient()
        response = client.post("/v1/accounts/register/", {
            "full_name": "Test User",
            "email": "register_default@test.com",
            "organization": "TestOrg",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = UserModel.objects.get(email="register_default@test.com")
        self.assertEqual(user.role.name, RoleName.ADMIN)


class TestNoOrgUserRestrictions(TestCase):
    """Tests that users without an organization get appropriate errors."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserModel.objects.create_user(email="noorg@test.com", password="pass123")
        self.client.force_authenticate(user=self.user)

    def test_job_list_no_org(self):
        """User without org gets 400 on job list."""
        response = self.client.get("/v1/api/jobs/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dataset_list_no_org(self):
        """User without org gets 400 on dataset list."""
        response = self.client.get("/v1/api/uploads/datasets/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("products.visualization_views.S3Service")
    def test_product_list_no_org(self, MockS3):
        """User without org gets 400 on product list."""
        response = self.client.get("/v1/api/products/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
