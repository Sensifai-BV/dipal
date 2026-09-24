from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid
from apps.uploads.infrastructure.models import Dataset

class ProcessingStatus(models.TextChoices):
    PENDING = 'PENDING', _('pending')
    QUEUED = 'QUEUED', _('queued')
    PROCESSING = 'PROCESSING', _('processing')
    COMPLETED = 'COMPLETED', _('completed')
    FAILED = 'FAILED', _('failed')


class ProcessingResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name='processings'
    )

    status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING
    )

    progress = models.IntegerField(default=0)
    orthomosaic_url = models.URLField(null=True, blank=True)
    mesh_model_url = models.URLField(null=True, blank=True)
    dsm_url = models.URLField(null=True, blank=True)
    ndvi_url = models.URLField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Processing {self.id} for Dataset {self.dataset_id}"
