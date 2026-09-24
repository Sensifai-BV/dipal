from celery import shared_task
from django.utils import timezone
from apps.processings.models.models import ProcessingResult, ProcessingStatus
from apps.processings.services.services import AIServiceAdapter, SocketNotificationService
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def dispatch_processing_task(self, result_id):
    try:
        process_entry = ProcessingResult.objects.get(id=result_id)

        process_entry.status = ProcessingStatus.PROCESSING
        process_entry.started_at = timezone.now()
        process_entry.save()

        SocketNotificationService.send_status_update(result_id, ProcessingStatus.PROCESSING, 0)

        ai_service = AIServiceAdapter()
        response = ai_service.start_job(
            job_id=str(result_id),
            input_path=process_entry.dataset.s3_path_raw_images
        )

        if not response.get('success'):
            raise Exception(f"AI Service rejected job: {response.get('message')}")

    except Exception as exc:
        logger.error(f"Error starting processing for {result_id}: {exc}")
        try:
            process_entry = ProcessingResult.objects.get(id=result_id)
            process_entry.status = ProcessingStatus.FAILED
            process_entry.error_message = str(exc)
            process_entry.save()
            SocketNotificationService.send_status_update(result_id, ProcessingStatus.FAILED, 0)
        except:
            pass
