from apps.jobs.domains.interfaces import ITaskQueueService
from apps.jobs.infra.services.tasks.tasks import run_ai_processing
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus


class CeleryQueueService(ITaskQueueService):
    def dispatch_processing_task(self, job_id: int):
        ProcessingJob.objects.filter(id=job_id).update(status=JobStatus.QUEUED)

        run_ai_processing.delay(job_id)
