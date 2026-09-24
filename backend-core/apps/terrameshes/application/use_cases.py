import uuid
from ..domain.entities import ProcessingTask, TaskStatus
from ..domain.interfaces import TaskRepository, AIServiceClient, StorageService


class RequestProcessingUseCase:
    def __init__(self, repo: TaskRepository, ai_service: AIServiceClient, storage: StorageService):
        self.repo = repo
        self.ai_service = ai_service
        self.storage = storage

    def execute(self, user_id: int, image_s3_key: str, task_type: str) -> ProcessingTask:
        # 1. Validation: Check if file exists in S3
        if not self.storage.check_file_exists(image_s3_key):
            raise ValueError(f"File {image_s3_key} does not exist in S3.")

        task = ProcessingTask(
            id=str(uuid.uuid4()),
            user_id=user_id,
            image_s3_key=image_s3_key,
            task_type=task_type
        )
        self.repo.save(task)

        try:
            success = self.ai_service.trigger_processing(task)
            if not success:
                task.mark_failed("Failed to trigger AI Service immediately.")
                self.repo.update(task)
            else:
                task.status = TaskStatus.PROCESSING
                self.repo.update(task)
        except Exception as e:
            # Fallback for connection errors
            task.mark_failed(f"Infrastructure Error: {str(e)}")
            self.repo.update(task)

        return task


class ProcessWebhookUseCase:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    def execute(self, task_id: str, status: str, result_data: dict = None, error: str = None):
        try:
            task = self.repo.get_by_id(task_id)

            if status == "SUCCESS":
                task.mark_completed(result_data)
            elif status == "FAILED":
                error_msg = error or "Unknown error from AI Service"
                if "No space left" in error_msg or "S3 Upload Failed" in error_msg:
                    error_msg = f"CRITICAL STORAGE ERROR: {error_msg}"

                task.mark_failed(error_msg)

            self.repo.update(task)
            return task
        except Exception as e:
            raise e
