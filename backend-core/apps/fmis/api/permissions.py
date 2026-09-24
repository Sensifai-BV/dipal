from rest_framework import permissions


class IsOrganizationMember(permissions.BasePermission):


    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        user_org_id = getattr(request.user, 'organization_id', None)

        return obj.org_id == user_org_id
