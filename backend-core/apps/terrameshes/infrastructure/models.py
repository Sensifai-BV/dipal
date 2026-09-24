from django.db import models
from django.contrib.auth.models import User
from apps.terrameshes.domain.entities import TaskStatus


class TaskModel(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image_s3_key = models.CharField(max_length=255)
    task_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default=TaskStatus.PENDING)
    result_data = models.JSONField(null=True, blank=True)
    error_log = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'processing_tasks'
