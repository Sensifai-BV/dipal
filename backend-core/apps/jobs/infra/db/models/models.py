from django.db import models
import uuid
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.processing_stages import AnalysisMode, ProcessingStage, JobStatus


class ProcessingJob(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name='processing_jobs',
        db_column='dataset_id'
    )

    resolution_gsd = models.FloatField(help_text="GSD in cm/px")
    radiometric_calibration = models.BooleanField(default=False)
    analysis_mode = models.CharField(
        max_length=10,
        choices=AnalysisMode.choices,
        default=AnalysisMode.FAST,
        help_text="Analysis mode: fast (RGB only) or full (multispectral + indices)"
    )

    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.PENDING)
    stage = models.CharField(max_length=30, choices=ProcessingStage.choices, default=ProcessingStage.QUEUED)
    progress = models.PositiveIntegerField(default=0)
    
    # Error handling and retry management
    error_message = models.TextField(null=True, blank=True, help_text="Error details if job failed")
    retry_count = models.PositiveIntegerField(default=0, help_text="Number of times this job has been retried")
    last_successful_stage = models.CharField(
        max_length=30, 
        choices=ProcessingStage.choices, 
        null=True, 
        blank=True,
        help_text="Last stage completed successfully (for resume on retry)"
    )
    original_job_id = models.UUIDField(
        null=True, 
        blank=True,
        help_text="Original job ID if this is a retry"
    )
    can_retry = models.BooleanField(
        default=True,
        help_text="Whether this job can be retried if it fails"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the job started processing"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the job completed or failed"
    )

    def __str__(self):
        return f"{self.id} - Dataset: {self.dataset.name if self.dataset else 'Unknown'}"

    class Meta:
        app_label = 'jobs'
        db_table = 'jobs_processing_job'
