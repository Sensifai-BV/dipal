"""
Centralized RBAC permission classes for the PhotoGear backend.

Roles (seeded via migration):
    - admin  (id=1): Full access to all org resources, user management
    - user   (id=2): Standard access to own org resources

Usage::

    from utils.permissions import IsAdmin, IsOrganizationOwner, IsAIService

    class MyView(APIView):
        permission_classes = [IsAuthenticated, IsAdmin]
"""

from rest_framework.permissions import BasePermission
from django.conf import settings

from accounts.models.role import RoleName


class IsAdmin(BasePermission):
    """Grants access only to users with the ADMIN role or superusers."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        role_name = getattr(request.user.role, 'name', None)
        return role_name == RoleName.ADMIN


class IsOrganizationOwner(BasePermission):
    """
    Object-level permission: grants access if the user belongs to the
    same organization that owns the object.

    The object must expose ``org_id`` **or** ``organization_id``
    as an attribute, or the view must set ``org_field`` on the class
    to indicate the attribute name.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        user_org_id = getattr(request.user, 'organization_id', None)
        if not user_org_id:
            return False

        org_field = getattr(view, 'org_field', None)
        if org_field:
            return getattr(obj, org_field, None) == user_org_id

        obj_org_id = getattr(obj, 'org_id', None) or getattr(obj, 'organization_id', None)
        return obj_org_id == user_org_id


class IsAIServiceOrAuthenticated(BasePermission):
    """Grants access to AI service (via secret key) OR authenticated users."""

    def has_permission(self, request, view):
        secret_key = request.headers.get('X-API-Secret-Key') or request.META.get('HTTP_X_AI_TOKEN')
        expected_key = getattr(settings, 'AI_GATEWAY_SECRET_KEY', None)
        if expected_key and secret_key and secret_key == expected_key:
            return True
        return request.user and request.user.is_authenticated


class IsAIService(BasePermission):
    """
    Validates the ``X-API-Secret-Key`` header against
    ``settings.AI_GATEWAY_SECRET_KEY``.

    Used for AI-to-backend service communication endpoints.
    """

    def has_permission(self, request, view):
        secret_key = request.headers.get('X-API-Secret-Key') or request.META.get('HTTP_X_AI_TOKEN')

        expected_key = getattr(settings, 'AI_GATEWAY_SECRET_KEY', None)
        if not expected_key or not secret_key:
            return False

        return secret_key == expected_key
