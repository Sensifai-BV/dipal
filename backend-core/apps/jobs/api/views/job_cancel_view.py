"""
Job Cancel View - Cancel a running processing job
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema

from apps.jobs.processing_stages import JobStatus
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.infra.services.ai_client import AIGatewayClient
from config.logging_config import get_logger

logger = get_logger(__name__)


class JobCancelView(APIView):
    """
    POST /api/jobs/{job_id}/cancel/
    Cancel a running processing job
    
    This endpoint:
    1. Validates the job belongs to user's organization
    2. Checks if job is in a cancellable state (queued or processing)
    3. Sends cancel request to AI Gateway
    4. Updates job status to 'cancelled'
    """
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Cancel Processing Job",
        description="""
        Cancel a running or queued processing job.
        
        Cancellation Flow:
        1. Backend validates job ownership and state
        2. Backend sends cancel request to AI Gateway
        3. AI Gateway cancels the background task
        4. Job status is updated to 'cancelled'
        
        Note: Jobs that are already completed or failed cannot be cancelled.
        """,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'job_id': {'type': 'string', 'format': 'uuid'},
                    'previous_status': {'type': 'string'},
                    'new_status': {'type': 'string'},
                    'ai_gateway_response': {'type': 'object'},
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'job_status': {'type': 'string'},
                }
            },
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
            502: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'detail': {'type': 'string'},
                }
            },
        },
        tags=['Processing Jobs']
    )
    def post(self, request, job_id):
        # Validate organization
        org_id = request.user.organization_id if hasattr(request.user, 'organization_id') else None
        if not org_id:
            logger.warning(
                f"Job cancel request failed: User {request.user.username} (ID: {request.user.id}) "
                f"has no organization assigned."
            )
            return Response(
                {'error': 'User organization not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get job
        try:
            job = ProcessingJob.objects.get(
                id=job_id,
                dataset__org_id=org_id
            )
        except ProcessingJob.DoesNotExist:
            return Response(
                {'error': 'Job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if job can be cancelled
        previous_status = job.status
        if previous_status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return Response(
                {
                    'error': f'Cannot cancel job with status: {previous_status}',
                    'job_status': previous_status,
                    'job_id': str(job.id),
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Send cancel request to AI Gateway
        ai_response = None
        try:
            ai_client = AIGatewayClient()
            ai_response = ai_client.cancel_job(str(job.id))
            logger.info(f"AI Gateway cancel response for job {job.id}: {ai_response}")
        except Exception as e:
            logger.error(f"Failed to send cancel request to AI Gateway: {e}")
            ai_response = {'error': str(e), 'gateway_unreachable': True}
        
        # Update job status
        job.status = JobStatus.CANCELLED
        job.error_message = f"Cancelled by user: {request.user.username}"
        job.save()
        
        logger.info(
            f"Job {job.id} cancelled by user {request.user.username}. "
            f"Previous status: {previous_status}"
        )
        
        return Response(
            {
                'message': 'Job cancelled successfully',
                'job_id': str(job.id),
                'previous_status': previous_status,
                'new_status': JobStatus.CANCELLED,
                'ai_gateway_response': ai_response,
            },
            status=status.HTTP_200_OK
        )
    

