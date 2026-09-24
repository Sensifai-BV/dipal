# fmis/api/views.py
from django.utils import timezone
from rest_framework import viewsets, permissions, exceptions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from apps.fmis.models import WebhookEndpoint, FMISIntegration, Job, FMISIntegrationStatus
from apps.fmis.selectors import webhook_list
from apps.fmis.services.integrations import IntegrationFactory
from apps.fmis.tasks import process_job_task  # Import the new task

from .serializers import (
    WebhookSerializer,
    FMISIntegrationSerializer,
    TestConnectionRequestSerializer,
    JobSerializer
)
from .permissions import IsOrganizationMember


@extend_schema(tags=['Webhooks'])
class WebhookViewSet(viewsets.ModelViewSet):
    serializer_class = WebhookSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return WebhookEndpoint.objects.none()

        if not hasattr(self.request.user, 'organization_id'):
            return WebhookEndpoint.objects.none()

        org_id = self.request.user.organization_id
        return webhook_list(org_id=org_id)

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, 'organization_id') and not user.is_staff:
            raise exceptions.ValidationError("User does not belong to an organization.")

        org_instance = user.organization
        serializer.save(org=org_instance)


@extend_schema(tags=['External Integrations'])
class FMISIntegrationViewSet(viewsets.ModelViewSet):
    serializer_class = FMISIntegrationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return FMISIntegration.objects.none()

        if not hasattr(self.request.user, 'organization_id'):
            return FMISIntegration.objects.none()

        return FMISIntegration.objects.filter(org_id=self.request.user.organization_id)

    def perform_create(self, serializer):
        self._test_and_save(serializer)

    def perform_update(self, serializer):
        self._test_and_save(serializer)

    def _test_and_save(self, serializer):
        data = serializer.validated_data

        provider_name = data.get('provider_name')
        if not provider_name and serializer.instance:
            provider_name = serializer.instance.provider_name

        token = data.get('api_token')
        url = data.get('base_url')

        if token and url:
            is_connected, msg = IntegrationFactory.run_test(
                provider_name=provider_name,
                base_url=url,
                token=token,
                extra_headers=data.get('extra_headers', {})
            )

            status_val = FMISIntegrationStatus.CONNECTED if is_connected else FMISIntegrationStatus.FAILED

            serializer.save(
                org=self.request.user.organization,
                status=status_val,
                last_error_message=msg if not is_connected else None,
                last_connected_at=timezone.now() if is_connected else None
            )
        else:
            serializer.save(org=self.request.user.organization)

    @extend_schema(request=TestConnectionRequestSerializer)
    @action(detail=False, methods=['post'], url_path='test-connection')
    def test_connection_adhoc(self, request):
        """
        Tests connection dynamically using the Factory based on selected provider.
        """
        serializer = TestConnectionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        is_connected, msg = IntegrationFactory.run_test(
            provider_name=data['provider_name'],
            base_url=data['base_url'],
            token=data['api_token'],
            extra_headers=data.get('extra_headers', {})
        )

        if is_connected:
            return Response(
                {"message": "Connection successful.", "details": msg},
                status=status.HTTP_200_OK
            )
        return Response(
            {"message": "Connection failed.", "details": msg},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(tags=['Jobs'])
class JobViewSet(mixins.CreateModelMixin,
                 mixins.RetrieveModelMixin,
                 mixins.ListModelMixin,
                 viewsets.GenericViewSet):
    """
    API for submitting processing jobs.
    1. Client POSTs data -> Returns Job ID (Pending).
    2. Server processes in background.
    3. Server sends Webhook (job.completed) when done.
    """
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationMember]

    def get_queryset(self):
        if not hasattr(self.request.user, 'organization_id'):
            return Job.objects.none()
        # Users see only their organization's jobs
        return Job.objects.filter(org=self.request.user.organization).order_by('-created_at')

    def perform_create(self, serializer):
        # 1. Save the job to DB
        job = serializer.save()

        # 2. Trigger the Celery task immediately
        process_job_task.delay(job.id)
