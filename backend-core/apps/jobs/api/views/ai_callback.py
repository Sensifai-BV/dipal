"""AI Gateway Callback View"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import ProcessingStage, JobStatus
from django.conf import settings
from utils.permissions import IsAIService
from config.logging_config import get_logger

logger = get_logger(__name__)


class AICallbackView(APIView):
    """
    Receives callbacks from AI Gateway with processing updates
    """
    authentication_classes = []
    permission_classes = [IsAIService]
    
    @extend_schema(
        summary="AI Gateway Callback",
        description="Receives processing updates from AI Gateway",
        request={
            "application/json": {
                "example": {
                    "job_id": "uuid",
                    "type": "progress|complete|error",
                    "progress": 50.0,
                    "current_stage": "sfm",
                    "message": "Processing...",
                    "outputs": {
                        "orthomosaic": "s3://bucket/path",
                        "dsm": "s3://bucket/path"
                    }
                }
            }
        },
        tags=['AI Callbacks']
    )
    def post(self, request):
        """Handle AI Gateway callback"""
        data = request.data
        job_id = data.get('job_id')
        callback_type = data.get('type')
        
        logger.info(f"Received AI callback: type={callback_type}, job_id={job_id}")
        
        if not job_id:
            return Response(
                {"error": "job_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            job = ProcessingJob.objects.get(id=job_id)
            logger.debug(f"Found job {job_id} with current status: {job.status}, stage: {job.stage}")
        except ProcessingJob.DoesNotExist:
            logger.error(f"Job {job_id} not found for AI callback")
            return Response(
                {"error": "Job not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Handle different callback types
        try:
            if callback_type == 'progress':
                self._handle_progress_update(job, data)
            elif callback_type == 'complete':
                self._handle_completion(job, data)
            elif callback_type == 'error':
                self._handle_error(job, data)
            elif callback_type == 'upload_status':
                self._handle_upload_status(job, data)
            else:
                logger.warning(f"Unknown callback type: {callback_type}")
                return Response(
                    {"error": f"Unknown callback type: {callback_type}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({"acknowledged": True}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing AI callback for job {job_id}: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _handle_progress_update(self, job: ProcessingJob, data: dict):
        """Handle progress update from AI"""
        progress = data.get('progress', job.progress)
        current_stage = data.get('current_stage')
        message = data.get('message')
        
        job.progress = int(progress)
        update_fields = ['progress']
        
        if current_stage:
            # Validate stage using ProcessingStage enum
            if ProcessingStage.is_valid_stage(current_stage):
                job.stage = current_stage
                update_fields.append('stage')
            else:
                logger.warning(f"Unknown stage '{current_stage}' for job {job.id}")
            
            # If stage progress is 100%, mark it as last successful stage
            # This allows retry to resume from the next stage
            stage_progress = data.get('stage_progress')
            if stage_progress == 100:
                job.last_successful_stage = current_stage
                update_fields.append('last_successful_stage')
                logger.info(
                    f"Stage '{current_stage}' completed for job {job.id}. "
                    f"Marked as last_successful_stage"
                )
        
        job.save(update_fields=update_fields)
        
        logger.info(
            f"Job {job.id} progress update: {progress}% - {current_stage}"
        )
    
    def _handle_completion(self, job: ProcessingJob, data: dict):
        """Handle job completion from AI"""
        outputs = data.get('outputs', {})
        metadata = data.get('metadata', {})
        
        logger.info(f"Received completion callback for job {job.id}. Current status: {job.status}")
        
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.stage = ProcessingStage.COMPLETED
        job.last_successful_stage = ProcessingStage.COMPLETED
        job.error_message = None
        job.completed_at = timezone.now()
        
        job.save(update_fields=['status', 'progress', 'stage', 'last_successful_stage', 'error_message', 'completed_at'])
        
        logger.info(
            f"Job {job.id} completed successfully. "
            f"Products saved via Product model (separate API calls from AI)"
        )
    
    def _handle_error(self, job: ProcessingJob, data: dict):
        """Handle job failure from AI"""
        error_message = data.get('error_message', 'Unknown error')
        error_details = data.get('error_details', {})
        
        logger.info(f"Received error callback for job {job.id}. Current status: {job.status}, New status: FAILED")
        
        job.status = JobStatus.FAILED
        job.error_message = error_message
        job.stage = ProcessingStage.FAILED
        job.completed_at = timezone.now()
        
        job.save(update_fields=['status', 'error_message', 'stage', 'completed_at'])
        
        logger.error(
            f"Job {job.id} failed: {error_message}. Details: {error_details}"
        )
        logger.info(f"Job {job.id} status saved as FAILED in database")
    
    def _handle_upload_status(self, job: ProcessingJob, data: dict):
        """
        Handle upload status report from AI after product uploads complete.

        Args:
            job: The processing job
            data: Callback data with uploaded/failed product lists
        """
        uploaded = data.get('uploaded', [])
        failed = data.get('failed', [])
        
        logger.info(
            f"Upload status for job {job.id}: "
            f"{len(uploaded)} succeeded, {len(failed)} failed"
        )
        
        if failed:
            failed_types = [f.get('product_type', 'unknown') for f in failed]
            error_msg = f"Failed to upload products: {', '.join(failed_types)}"
            
            job.error_message = error_msg
            job.status = JobStatus.FAILED
            job.stage = ProcessingStage.FAILED
            job.save(update_fields=['error_message', 'status', 'stage'])
            
            logger.error(
                f"Job {job.id} marked FAILED due to upload failures: {failed_types}"
            )
        else:
            logger.info(f"All uploads succeeded for job {job.id}")
