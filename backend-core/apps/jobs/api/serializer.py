from rest_framework import serializers
from django.utils import timezone
from apps.jobs.infra.db.models.models import ProcessingJob
from apps.jobs.processing_stages import JobStatus, AnalysisMode

class StartProcessingRequestSerializer(serializers.Serializer):
    """Serializer for job start requests."""

    dataset_id = serializers.UUIDField(help_text="ID of the dataset to process")
    resolution_gsd = serializers.FloatField(
        help_text="Desired output resolution (cm/px)",
        min_value=0.5,
        max_value=50,
    )
    radiometric_calibration = serializers.BooleanField(
        help_text="Enable radiometric calibration (optional, derived from analysis_mode if omitted)",
        required=False,
        default=None,
    )
    analysis_mode = serializers.ChoiceField(
        choices=[AnalysisMode.FAST, AnalysisMode.FULL],
        default="full",
        help_text="Analysis mode: 'fast' for RGB-only, 'full' for multispectral + vegetation indices"
    )

class JobResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    job_uid = serializers.CharField()
    status = serializers.CharField()
    resolution_gsd = serializers.FloatField()
    message = serializers.CharField(default="Processing started successfully", read_only=True)


class ProcessingJobListSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source='dataset.name', read_only=True)
    dataset_id = serializers.UUIDField(source='dataset.id', read_only=True)

    duration = serializers.SerializerMethodField()
    start_time = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M")

    class Meta:
        model = ProcessingJob
        fields = [
            'id',
            'dataset_id',
            'dataset_name',
            'status',
            'stage',
            'progress',
            'start_time',
            'duration',
            'resolution_gsd',
            'radiometric_calibration',
            'analysis_mode',
            'started_at',
            'completed_at',
        ]

    def get_duration(self, obj):
        """Calculate job duration using started_at/completed_at fields."""
        start = obj.started_at or obj.created_at
        if not start:
            return "-"

        if obj.status == JobStatus.PENDING:
            return "-"

        end = obj.completed_at if obj.status in [JobStatus.COMPLETED, JobStatus.FAILED] else timezone.now()
        if not end:
            end = timezone.now()

        diff = end - start
        total_seconds = int(diff.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        return f"{hours}h {minutes}m"