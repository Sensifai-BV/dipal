from rest_framework import generics
from accounts.models.role import Role
from accounts.serializers.role import RoleSerializer
from drf_spectacular.utils import extend_schema

class RoleListAPIView(generics.ListAPIView):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer

    @extend_schema(
        summary="Get Dynamic User Roles",
        description="Returns a list of roles defined in the database.",
        tags=['Config']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
