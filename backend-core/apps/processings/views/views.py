from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from drf_spectacular.utils import extend_schema
from apps.processings.models.models import ProcessingResult, ProcessingStatus
from apps.processings.tasks.tasks import dispatch_processing_task
from apps.processings.services.services import SocketNotificationService
from apps.uploads.infrastructure.models import Dataset

import warnings

# Mark this module as deprecated
warnings.warn(
    "apps.processings is deprecated. Use apps.jobs instead. "
    "This app will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2
)


@extend_schema(tags=['3D (Deprecated)'])
class StartProcessingView(APIView):
    """
    DEPRECATED: Use /v1/api/jobs/start-job/ instead.
    
    This endpoint is maintained for backward compatibility only.
    """

    @extend_schema(
        summary="[DEPRECATED] Start Processing Job",
        description="**DEPRECATED**: Use POST /v1/api/jobs/start-job/ instead. "
                    "This endpoint uses the legacy ProcessingResult model.",
        deprecated=True,
    )
    def post(self, request, dataset_id):
        try:
            target_dataset = get_object_or_404(Dataset, id=dataset_id)

            active_tasks = ProcessingResult.objects.filter(
                status__in=[ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]
            ).count()

            MAX_QUEUE_SIZE = getattr(settings, 'MAX_PROCESSING_QUEUE', 5)

            if active_tasks >= MAX_QUEUE_SIZE:
                return Response(
                    {"error": "System is busy, please try again later."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            result = ProcessingResult.objects.filter(dataset_id=target_dataset.id).order_by('-created_at').first()

            if result:
                if result.status in [ProcessingStatus.PROCESSING, ProcessingStatus.QUEUED]:
                    return Response(
                        {"message": "This dataset is currently being processed.", "job_id": result.id},
                        status=status.HTTP_200_OK
                    )

                result.status = ProcessingStatus.QUEUED
                result.error_message = None
                result.progress = 0
                result.save()
            else:
                result = ProcessingResult.objects.create(
                    dataset_id=target_dataset.id,
                    status=ProcessingStatus.QUEUED
                )

            dispatch_processing_task.delay(result.id)

            return Response({
                "message": "Request queued successfully.",
                "job_id": result.id,
                "status": ProcessingStatus.QUEUED,
                "warning": "DEPRECATED: Please migrate to POST /v1/api/jobs/start-job/"
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response(
                {"error": "Internal Server Error", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=['3D (Deprecated)'])
class AICallbackView(APIView):
    """
    DEPRECATED: Use /v1/api/jobs/ai-callback/ instead.
    """

    @extend_schema(
        summary="[DEPRECATED] AI Service Callback",
        deprecated=True,
    )
    def post(self, request):
        try:
            data = request.data
            job_id = data.get('job_id')
            event_type = data.get('type')

            if not job_id:
                return Response({"error": "job_id is required"}, status=400)

            try:
                process = ProcessingResult.objects.get(id=job_id)
            except ProcessingResult.DoesNotExist:
                return Response({"error": "Job not found"}, status=404)

            if event_type == 'progress':
                progress = data.get('progress', 0)
                process.progress = progress
                process.save(update_fields=['progress'])
                SocketNotificationService.send_status_update(job_id, process.status, progress)

            elif event_type == 'complete':
                outputs = data.get('outputs', {})
                process.orthomosaic_url = outputs.get('orthomosaic')
                process.mesh_model_url = outputs.get('mesh')
                process.dsm_url = outputs.get('dsm')
                process.ndvi_url = outputs.get('ndvi')

                process.status = ProcessingStatus.COMPLETED
                process.progress = 100
                process.completed_at = timezone.now()
                process.save()
                SocketNotificationService.send_status_update(job_id, ProcessingStatus.COMPLETED, 100, outputs=outputs)

            elif event_type == 'error':
                error_msg = data.get('message', 'Unknown error')
                process.status = ProcessingStatus.FAILED
                process.error_message = error_msg
                process.save()
                SocketNotificationService.send_status_update(job_id, ProcessingStatus.FAILED, process.progress)

            return Response({"status": "received"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "error": "Callback Error",
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
