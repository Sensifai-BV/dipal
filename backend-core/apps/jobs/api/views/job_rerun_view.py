"""Job Rerun View - Re-trigger an existing job (retry or restart)"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.infra.services.tasks.tasks import process_drone_imagery
from apps.jobs.processing_stages import JobStatus, ProcessingStage
from config.logging_config import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3


class JobRerunView(APIView):
    """
    POST /api/jobs/{job_id}/rerun/
    Re-trigger an existing job: resume from last step or restart from beginning.
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Rerun Existing Job",
        description="""
        Re-trigger an existing job without creating a new job record.
        
        **Modes:**
        - `resume=true`: Resume from the stage where the job failed/stopped.
        - `resume=false` (default): Restart from the beginning.
        
        **Validation:**
        - Only failed or cancelled jobs can be retried.
        - Job must have `can_retry=true`.
        - Maximum retry limit enforced (3 retries).
        
        **Stages:**
        - queued → radiometric_calibration → sfm → orthomosaic → uploading → publishing
        """,
        parameters=[
            OpenApiParameter(
                name='job_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
                description='UUID of the job to re-run'
            ),
            OpenApiParameter(
                name='resume',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Resume from the failed stage instead of restarting (default: false)',
                required=False
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'job_id': {'type': 'string', 'format': 'uuid'},
                    'status': {'type': 'string'},
                    'retry_count': {'type': 'integer'},
                    'resume_from': {'type': 'string', 'nullable': True},
                    'message': {'type': 'string'},
                    'dataset': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string'},
                            'name': {'type': 'string'}
                        }
                    }
                }
            },
            400: {'description': 'Job cannot be retried (not failed/cancelled, max retries, etc.)'},
            404: {'description': 'Job not found'}
        },
        tags=['Processing Jobs']
    )
    def post(self, request, job_id):
        """Re-run an existing job."""
        org_id = request.user.organization_id if hasattr(request.user, 'organization_id') else None
        if not org_id:
            logger.warning(
                f"Job rerun request failed: User {request.user.username} (ID: {request.user.id}) "
                f"has no organization assigned. Email: {getattr(request.user, 'email', 'N/A')}"
            )
            return Response(
                {'error': 'User organization not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        resume = request.query_params.get('resume', 'false').lower() == 'true'
        
        try:
            job = ProcessingJob.objects.select_related('dataset').get(
                id=job_id,
                dataset__org_id=org_id
            )
        except ProcessingJob.DoesNotExist:
            logger.warning(
                f"Job rerun failed: Job {job_id} not found for organization {org_id}"
            )
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
            return Response(
                {
                    'error': f'Cannot retry job with status "{job.status}". Only failed or cancelled jobs can be retried.',
                    'current_status': job.status
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not job.can_retry:
            return Response(
                {
                    'error': 'This job cannot be retried (retry disabled)',
                    'reason': 'Job marked as non-retryable'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if job.retry_count >= MAX_RETRIES:
            return Response(
                {
                    'error': f'Maximum retry limit reached ({MAX_RETRIES} retries)',
                    'retry_count': job.retry_count,
                    'suggestion': 'Please check the error logs and fix the issue before creating a new job'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        starting_stage = None
        if resume and job.stage and job.stage not in [ProcessingStage.QUEUED, ProcessingStage.COMPLETED]:
            starting_stage = job.stage
            logger.info(f"Job {job_id} will resume from stage: {starting_stage}")
        
        job.error_message = None
        job.retry_count += 1
        job.status = JobStatus.QUEUED
        if not resume:
            job.stage = ProcessingStage.QUEUED
            job.progress = 0
        job.save()
        logger.info(
            f"Job {job_id} reset for rerun (retry_count={job.retry_count}, "
            f"resume_from={starting_stage or 'beginning'})"
        )
        
        try:
            if starting_stage:
                process_drone_imagery.delay(str(job.id), starting_stage=starting_stage)
            else:
                process_drone_imagery.delay(str(job.id))
            
            message = f'Job re-queued successfully (retry #{job.retry_count}).'
            if starting_stage:
                message += f' Resuming from {starting_stage}.'
            
            return Response({
                'job_id': str(job.id),
                'status': job.status,
                'retry_count': job.retry_count,
                'resume_from': starting_stage,
                'message': message,
                'dataset': {
                    'id': str(job.dataset.id),
                    'name': job.dataset.name
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Failed to push job {job_id} to queue: {e}", exc_info=True)
            return Response(
                {'error': f'Failed to queue job: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
