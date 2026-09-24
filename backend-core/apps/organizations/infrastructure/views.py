from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.organizations.infrastructure.serializers import OrganizationSerializer
from apps.organizations.infrastructure.permissions import IsSystemAdminOrOwner
from apps.organizations.application.services import OrganizationService

@extend_schema(tags=['Organizations'])
class OrganizationViewSet(viewsets.ViewSet):

    permission_classes = [IsSystemAdminOrOwner]
    serializer_class = OrganizationSerializer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = OrganizationService()

    @extend_schema(
        summary="List Organizations",
        description="Returns a list of organizations based on user permissions (Admin sees all, User sees own).",
        responses={200: OrganizationSerializer(many=True)}
    )
    def list(self, request):
        orgs = self.service.list_organizations(request.user)
        serializer = OrganizationSerializer(orgs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Retrieve Organization",
        description="Get details of a specific organization by ID.",
        responses={200: OrganizationSerializer}
    )
    def retrieve(self, request, pk=None):
        org = self.service.get(pk)
        self.check_object_permissions(request, org)
        serializer = OrganizationSerializer(org)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Create Organization",
        description="Creates a new organization. The current user is automatically set as the owner.",
        request=OrganizationSerializer,
        responses={201: OrganizationSerializer}
    )
    def create(self, request):
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org = self.service.create_organization(request.user, serializer.validated_data)

        return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Update Organization",
        description="Update an existing organization.",
        request=OrganizationSerializer,
        responses={200: OrganizationSerializer}
    )
    def update(self, request, pk=None):
        org_obj = self.service.get(pk)
        self.check_object_permissions(request, org_obj)

        serializer = OrganizationSerializer(instance=org_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated_org = self.service.update(pk, serializer.validated_data)
        return Response(OrganizationSerializer(updated_org).data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Delete Organization",
        description="Permanently remove an organization.",
        responses={204: None}
    )
    def destroy(self, request, pk=None):
        org_obj = self.service.get(pk)
        self.check_object_permissions(request, org_obj)

        self.service.delete(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
