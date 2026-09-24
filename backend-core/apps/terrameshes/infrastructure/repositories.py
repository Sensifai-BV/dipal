from ...domain.interfaces import TaskRepository
from ...domain.entities import ProcessingTask
from .django.models import TaskModel

class DjangoTaskRepository(TaskRepository):
    def to_entity(self, model: TaskModel) -> ProcessingTask:
        return ProcessingTask(
            id=str(model.id),
            user_id=model.user.id,
            image_s3_key=model.image_s3_key,
            task_type=model.task_type,
            status=model.status,
            result_data=model.result_data,
            error_log=model.error_log,
            created_at=model.created_at
        )

    def save(self, task: ProcessingTask):
        TaskModel.objects.create(
            id=task.id,
            user_id=task.user_id,
            image_s3_key=task.image_s3_key,
            task_type=task.task_type,
            status=task.status
        )

    def get_by_id(self, task_id: str) -> ProcessingTask:
        model = TaskModel.objects.get(id=task_id)
        return self.to_entity(model)

    def update(self, task: ProcessingTask):
        TaskModel.objects.filter(id=task.id).update(
            status=task.status,
            result_data=task.result_data,
            error_log=task.error_log
        )
