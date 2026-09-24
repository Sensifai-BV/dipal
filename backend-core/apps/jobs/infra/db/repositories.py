from uuid import UUID
from apps.jobs.domains.interfaces import IJobRepository, IQueueService
from apps.jobs.domains.entities import JobEntity
from apps.jobs.processing_stages import JobStatus
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.infra.services.tasks.tasks import process_drone_imagery


class DjangoJobRepository(IJobRepository):

    def get_dataset_by_id(self, dataset_id: str):
        try:
            return Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            return None

    def dataset_exists(self, dataset_id: UUID) -> bool:
        return Dataset.objects.filter(id=dataset_id).exists()

    def create_job(self, job_entity: JobEntity) -> JobEntity:
        """Persist a new job entity to the database."""
        db_job = ProcessingJob.objects.create(
            dataset_id=job_entity.dataset_id,
            resolution_gsd=job_entity.resolution_gsd,
            radiometric_calibration=job_entity.radiometric_calibration,
            analysis_mode=job_entity.analysis_mode,
            status=job_entity.status
        )

        job_entity.id = str(db_job.id)
        job_entity.job_uid = str(db_job.id)
        return job_entity


class CeleryQueueService(IQueueService):
    def push_job_to_queue(self, job_id: str):
        job_id_str = str(job_id)

        ProcessingJob.objects.filter(id=job_id_str).update(status=JobStatus.QUEUED)

        process_drone_imagery.delay(job_id_str)
