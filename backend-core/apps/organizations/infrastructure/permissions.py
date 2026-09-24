from rest_framework import permissions

from accounts.models.role import RoleName


class IsSystemAdminOrOwner(permissions.BasePermission):
    """
    1. Create: Authenticated users can create.
    2. List/Retrieve: Admins see all, Owners see their own.
    3. Update/Delete: Admins or Owners only.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        role_name = getattr(request.user.role, 'name', None)

        if request.user.organization == obj:
            return role_name in (RoleName.ADMIN, RoleName.USER)

        return False
