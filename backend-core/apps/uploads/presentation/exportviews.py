import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from ..Tasks.tasks import create_dataset_archive_task
from ..domain.constants import UploadStatusName


class ExportDatasetView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Request Dataset Download (Zip)",
        description="Starts a background job to zip all completed files in a dataset and stream them to S3. Returns a job_id to poll.",
        tags=['Download'],
        responses={
            202: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'job_id': {'type': 'string', 'format': 'uuid'}
                },
                'example': {
                    "message": "Export job started.",
                    "job_id": "550e8400-e29b-41d4-a716-446655440000"
                }
            }
        }
    )
    def post(self, request, dataset_id):
        user_id = request.user.id


        job_id = str(uuid.uuid4())
        job_key = f"export_job_{job_id}"

        cache.set(job_key, {'status': UploadStatusName.PENDING}, timeout=3600)

        create_dataset_archive_task.delay(dataset_id, user_id, job_key)

        return Response({
            "message": "Export job started.",
            "job_id": job_id
        }, status=status.HTTP_202_ACCEPTED)


class ExportStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Check Export Job Status",
        description="Poll this endpoint with the job_id to check if the zip file is ready.",
        tags=['Download'],
        parameters=[
            OpenApiParameter(
                name="job_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description="The UUID returned from the export request",
                required=True
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'enum': ['COMPLETED', 'FAILED']},
                    'download_url': {'type': 'string', 'format': 'uri'},
                    'file_name': {'type': 'string'}
                },
                'example': {
                    "status": "COMPLETED",
                    "download_url": "https://s3-bucket-url...",
                    "file_name": "my_dataset.zip"
                }
            },
            202: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'enum': ['PENDING', 'PROCESSING']}
                },
                'example': {"status": "PROCESSING"}
            },
            404: {'description': 'Job not found or expired'}
        }
    )
    def get(self, request, job_id):
        job_key = f"export_job_{job_id}"
        job_data = cache.get(job_key)

        if not job_data:
            return Response({"detail": "Job not found or expired."}, status=status.HTTP_404_NOT_FOUND)

        response_status = status.HTTP_200_OK
        if job_data.get('status') in [UploadStatusName.PENDING, UploadStatusName.PROCESSING]:
            response_status = status.HTTP_202_ACCEPTED

        return Response(job_data, status=response_status)
