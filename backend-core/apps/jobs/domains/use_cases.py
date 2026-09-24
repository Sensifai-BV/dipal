from .interfaces import IJobRepository, IQueueService
from .entities import JobEntity
from .exceptions import BusinessRuleValidationException, ResourceNotFoundException
from apps.jobs.processing_stages import JobStatus, AnalysisMode

class StartProcessingUseCase:
    def __init__(self, job_repo: IJobRepository, queue_service: IQueueService):
        self.job_repo = job_repo
        self.queue_service = queue_service

    def execute(self, dataset_id: int, resolution: float, calibration: bool, analysis_mode: str = "fast") -> JobEntity:
        """Create and queue a processing job.

        Args:
            dataset_id: Target dataset identifier
            resolution: Desired GSD in cm/px
            calibration: Enable radiometric calibration
            analysis_mode: 'fast' (RGB only) or 'full' (multispectral + indices)

        Returns:
            Persisted JobEntity with assigned ID

        Raises:
            BusinessRuleValidationException: Invalid inputs
            ResourceNotFoundException: Dataset does not exist
        """
        if resolution <= 0:
            raise BusinessRuleValidationException("Resolution (GSD) must be greater than zero.")

        if analysis_mode not in (AnalysisMode.FAST, AnalysisMode.FULL):
            raise BusinessRuleValidationException("Analysis mode must be 'fast' or 'full'.")

        if not self.job_repo.dataset_exists(dataset_id):
            raise ResourceNotFoundException(f"Dataset with ID {dataset_id} not found.")

        new_job = JobEntity(
            dataset_id=dataset_id,
            resolution_gsd=resolution,
            radiometric_calibration=calibration,
            analysis_mode=analysis_mode,
            status=JobStatus.PENDING
        )

        # 4. Persist to Database (via Repository)
        saved_job = self.job_repo.create_job(new_job)

        # 5. Trigger Async Process (via Queue Service)
        if saved_job.id:
            self.queue_service.push_job_to_queue(saved_job.id)

        return saved_job
