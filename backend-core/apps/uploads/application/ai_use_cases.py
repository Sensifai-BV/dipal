from ..infrastructure.models import Dataset, AIProcessingJob, UploadStatus, Image
from ..domain.services import S3Service
from ..domain.aiservices import AIService
from ..domain.constants import UploadStatusName


class StartAIJobUseCase:
    def __init__(self):
        self.s3_service = S3Service()

    def execute(self, dataset_id, job_type):

        try:
            dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            raise ValueError("Dataset not found")


        source_image = dataset.images.filter(file_type=Image.FileType.ARCHIVE).order_by('-created_at').first()

        if not source_image:

            raise ValueError("No source archive file found for this dataset to process.")


        pending_status, _ = UploadStatus.objects.get_or_create(
            name=UploadStatusName.PENDING, defaults={'label': 'Pending'}
        )


        job = AIProcessingJob.objects.create(
            dataset=dataset,
            type=job_type,
            status=pending_status
        )


        download_url = self.s3_service.generate_presigned_download_url(
            key=source_image.s3_key,
            expires_in=24 * 3600,
        )


        try:
            AIService.trigger_ai_processing(
                job_id=job.id,
                dataset_id=dataset.id,
                download_url=download_url
            )
        except Exception as e:
            failed_status, _ = UploadStatus.objects.get_or_create(
                name=UploadStatusName.FAILED, defaults={'label': 'Failed'}
            )
            job.status = failed_status
            job.save()
            raise e

        return job
