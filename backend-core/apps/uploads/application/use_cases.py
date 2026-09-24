import uuid
from typing import Optional
from ..infrastructure.repositories import UploadRepository
from ..domain.constants import UploadStatusName

class GetUserUploadsUseCase:
    def __init__(self):
        self.repository = UploadRepository()

    def execute(self, user_id: int, dataset_id: Optional[uuid.UUID], batch_id: Optional[uuid.UUID], file_type: Optional[str] = None):
        return self.repository.get_user_uploads(user_id, dataset_id, batch_id, file_type)


class GetUserDatasetsStatsUseCase:
    def __init__(self):
        self.repository = UploadRepository()

    def execute(self, user_id: int):
        return self.repository.get_datasets_stats(user_id=user_id)


# --------------------------------------------
class ProcessAICallbackUseCase:
    def __init__(self, ai_job_repo, notification_service):
        self.ai_job_repo = ai_job_repo
        self.notification_service = notification_service

    def execute(self, result_dto: 'AICompletionResult'):  # type: ignore

        job = self.ai_job_repo.get_by_id(result_dto.job_id)

        if not job:
            raise ValueError("AI Job not found")

        if result_dto.status == 'success':
            job.status = UploadStatusName.COMPLETED
            self.ai_job_repo.save_outputs(job, result_dto.outputs)
        else:
            job.status = UploadStatusName.FAILED

        self.ai_job_repo.update(job)

        self.notification_service.notify_frontend(
            dataset_id=job.dataset_id,
            message_type="AI_PROCESS_COMPLETED",
            payload={
                "job_id": job.id,
                "status": job.status,
                "result_files": [out.s3_key for out in result_dto.outputs]
            }
        )
