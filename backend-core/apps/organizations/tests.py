"""Tests for organization service, repository, and permissions."""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Organization, UserModel
from accounts.models.role import RoleName
from apps.organizations.application.services import OrganizationService
from apps.organizations.infrastructure.repositories import OrganizationRepository
from apps.organizations.infrastructure.permissions import IsSystemAdminOrOwner
from apps.organizations.domain.dto import OrganizationDTO
from unittest.mock import MagicMock, patch


class OrganizationRepositoryTest(TestCase):
    """Tests for OrganizationRepository."""

    def setUp(self):
        self.repo = OrganizationRepository()
        self.user = UserModel.objects.create_user(email="orgrepo@test.com", password="pass1234")
        self.org = Organization.objects.create(name="RepoOrg", user=self.user)

    def test_get_all(self):
        """Test getting all organizations."""
        orgs = self.repo.get_all()
        self.assertTrue(orgs.filter(id=self.org.id).exists())

    def test_get_by_id(self):
        """Test getting organization by ID."""
        org = self.repo.get_by_id(self.org.id)
        self.assertEqual(org.name, "RepoOrg")

    def test_create(self):
        """Test creating new organization."""
        user2 = UserModel.objects.create_user(email="orgrepo2@test.com", password="pass1234")
        new_org = self.repo.create({"name": "NewOrg", "user": user2})
        self.assertEqual(new_org.name, "NewOrg")
        self.assertTrue(Organization.objects.filter(name="NewOrg").exists())

    def test_update(self):
        """Test updating organization."""
        updated = self.repo.update(self.org, {"name": "UpdatedOrg"})
        self.assertEqual(updated.name, "UpdatedOrg")
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "UpdatedOrg")

    def test_delete(self):
        """Test deleting organization."""
        org_id = self.org.id
        self.repo.delete(self.org)
        self.assertFalse(Organization.objects.filter(id=org_id).exists())


class OrganizationServiceTest(TestCase):
    """Tests for OrganizationService."""

    def setUp(self):
        self.service = OrganizationService()
        self.user = UserModel.objects.create_user(email="orgsvc@test.com", password="pass1234")
        self.org = Organization.objects.create(name="SvcOrg", user=self.user)
        self.user.organization = self.org
        self.user.save()

    def test_list_admin_sees_all(self):
        """Test that admin sees all organizations."""
        admin = UserModel.objects.create_superuser(email="admin@test.com", password="pass1234")
        result = self.service.list_organizations(admin)
        self.assertGreaterEqual(len(result), 1)

    def test_list_regular_user(self):
        """Test that regular user sees only their org."""
        result = self.service.list_organizations(self.user)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, self.org.id)

    def test_list_user_no_org(self):
        """Test that user without org sees empty list."""
        user2 = UserModel.objects.create_user(email="noorg@test.com", password="pass1234")
        result = self.service.list_organizations(user2)
        self.assertEqual(len(result), 0)

    def test_get_organization(self):
        """Test getting single organization."""
        result = self.service.get(self.org.id)
        self.assertEqual(result.name, "SvcOrg")

    def test_create_organization(self):
        """Test creating organization assigns it to user."""
        user2 = UserModel.objects.create_user(email="neworguser@test.com", password="pass1234")
        mock_role = type('MockRole', (), {})()
        with patch.object(UserModel, 'Role', create=True, new=mock_role):
            new_org = self.service.create_organization(user2, {"name": "CreatedOrg", "user": user2})
        self.assertEqual(new_org.name, "CreatedOrg")
        user2.refresh_from_db()
        self.assertEqual(user2.organization, new_org)

    def test_update_organization(self):
        """Test updating organization."""
        updated = self.service.update(self.org.id, {"name": "Updated"})
        self.assertEqual(updated.name, "Updated")

    def test_delete_organization(self):
        """Test deleting organization."""
        org_id = self.org.id
        self.service.delete(org_id)
        self.assertFalse(Organization.objects.filter(id=org_id).exists())


class OrganizationDTOTest(TestCase):
    """Tests for OrganizationDTO."""

    def test_from_model(self):
        """Test DTO creation from model with mock."""
        mock_model = MagicMock()
        mock_model.id = 1
        mock_model.name = "DTOOrg"
        mock_model.is_active = True
        mock_model.owner_id = 42
        mock_model.created_at = "2026-01-01T00:00:00Z"
        mock_model.updated_at = "2026-01-01T00:00:00Z"

        dto = OrganizationDTO.from_model(mock_model)
        self.assertEqual(dto.name, "DTOOrg")
        self.assertEqual(dto.id, "1")


class IsSystemAdminOrOwnerTest(TestCase):
    """Tests for IsSystemAdminOrOwner permission."""

    def setUp(self):
        self.permission = IsSystemAdminOrOwner()

    def test_admin_has_permission(self):
        """Test that admin has permission."""
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_staff = True
        request.user.is_superuser = True
        self.assertTrue(self.permission.has_permission(request, None))

    def test_regular_user_has_permission(self):
        """Test that regular authenticated user has list permission."""
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_staff = False
        request.user.is_superuser = False
        request.user.is_authenticated = True
        self.assertTrue(self.permission.has_permission(request, None))

    def test_admin_has_object_permission(self):
        """Test that admin has object permission for any org."""
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_staff = True
        request.user.is_superuser = True
        obj = MagicMock()
        self.assertTrue(self.permission.has_object_permission(request, None, obj))

    def test_owner_has_object_permission(self):
        """Test that owner has permission for their org."""
        org = MagicMock()

        request = MagicMock()
        request.user = MagicMock()
        request.user.is_superuser = False
        request.user.organization = org
        request.user.role = MagicMock(name=RoleName.ADMIN)
        request.user.role.name = RoleName.ADMIN
        self.assertTrue(self.permission.has_object_permission(request, None, org))

    def test_non_owner_no_object_permission(self):
        """Test that non-owner doesn't have object permission."""
        org = MagicMock()

        request = MagicMock()
        request.user = MagicMock()
        request.user.is_superuser = False
        request.user.organization = org
        request.user.role = MagicMock()
        request.user.role.name = 'viewer'
        self.assertFalse(self.permission.has_object_permission(request, None, org))
