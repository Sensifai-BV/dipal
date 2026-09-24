from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from apps.jobs.processing_stages import JobStatus, ProcessingStage, AnalysisMode


@dataclass
class JobEntity:
    """Domain entity representing a processing job."""

    dataset_id: int
    resolution_gsd: float
    radiometric_calibration: bool
    analysis_mode: str = AnalysisMode.FAST
    status: str = JobStatus.PENDING
    stage: str = ProcessingStage.QUEUED
    progress: int = 0
    job_uid: Optional[str] = None
    id: Optional[int] = None
