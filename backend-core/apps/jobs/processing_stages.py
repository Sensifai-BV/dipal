"""
Processing stages and status definitions for job processing.

This module defines the canonical stage and status choices for processing jobs
using Django's TextChoices for proper integration with Django models.
"""
from django.db import models


class AnalysisMode(models.TextChoices):
    """
    Analysis mode options.

    Controls level of spectral analysis:
    - fast: RGB-only orthomosaic (default)
    - full: MS orthorectification + vegetation indices
    """
    FAST = "fast", "Fast (RGB only)"
    FULL = "full", "Full (Multispectral + Indices)"


class ProcessingStage(models.TextChoices):
    """
    Processing pipeline stages in order.
    
    These stage names are consistent with AI Gateway.
    See: image-analysis-core/infrastructure/state/models.py for AI-side definitions.
    """
    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    RADIOMETRIC_CALIBRATION = "radiometric_calibration", "Radiometric Calibration"
    SFM = "sfm", "Structure from Motion"
    ORTHOMOSAIC = "orthomosaic", "Orthomosaic Generation"
    UPLOADING = "uploading", "Uploading Results"
    PUBLISHING = "publishing", "Publishing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    
    @classmethod
    def get_processing_stages(cls):
        """Get stages that represent active processing (not terminal/initial)."""
        return [
            cls.RADIOMETRIC_CALIBRATION,
            cls.SFM,
            cls.ORTHOMOSAIC,
            cls.UPLOADING,
            cls.PUBLISHING,
        ]
    
    @classmethod
    def get_terminal_stages(cls):
        """Get terminal stages (job is done)."""
        return [cls.COMPLETED, cls.FAILED, cls.CANCELLED]
    
    @classmethod
    def is_valid_stage(cls, stage: str) -> bool:
        """Check if a stage value is valid."""
        return stage in cls.values


class JobStatus(models.TextChoices):
    """Job status choices."""
    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
