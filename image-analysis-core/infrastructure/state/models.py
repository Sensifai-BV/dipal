from __future__ import annotations

from enum import Enum

__all__ = ["JobState", "StageStatus", "ProcessingStage"]


class ProcessingStage(str, Enum):
    """
    Processing pipeline stages in order.
    
    These stage names are consistent with Backend (Django).
    Backend equivalent: backend/apps/jobs/processing_stages.py
    """

    PENDING = "pending"
    QUEUED = "queued"
    RADIOMETRIC_CALIBRATION = "radiometric_calibration"
    SFM = "sfm"
    ORTHOMOSAIC = "orthomosaic"  # Changed from orthomosaic_generation for consistency
    UPLOADING = "uploading"  # Changed from uploading_results for consistency
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def get_next_stage(cls, current: "ProcessingStage", skip_calibration: bool = False) -> "ProcessingStage | None":
        """Get the next stage in the pipeline."""
        stage_order = [
            cls.PENDING,
            cls.QUEUED,
            cls.RADIOMETRIC_CALIBRATION,
            cls.SFM,
            cls.ORTHOMOSAIC,
            cls.UPLOADING,
            cls.PUBLISHING,
            cls.COMPLETED,
        ]
        
        # If skipping calibration, remove it from order
        if skip_calibration:
            stage_order = [s for s in stage_order if s != cls.RADIOMETRIC_CALIBRATION]
        
        try:
            current_idx = stage_order.index(current)
            if current_idx < len(stage_order) - 1:
                return stage_order[current_idx + 1]
            return None
        except ValueError:
            return None

    @classmethod
    def get_stage_progress(cls, stage: "ProcessingStage") -> float:
        """Get the progress percentage for a stage start."""
        progress_map = {
            cls.PENDING: 0.0,
            cls.QUEUED: 0.0,
            cls.RADIOMETRIC_CALIBRATION: 5.0,
            cls.SFM: 15.0,
            cls.ORTHOMOSAIC: 60.0,
            cls.UPLOADING: 90.0,
            cls.PUBLISHING: 95.0,
            cls.COMPLETED: 100.0,
            cls.FAILED: 0.0,
            cls.CANCELLED: 0.0,
        }
        return progress_map.get(stage, 0.0)
    
    @classmethod
    def is_terminal(cls, stage: "ProcessingStage") -> bool:
        """Check if stage is a terminal state."""
        return stage in (cls.COMPLETED, cls.FAILED, cls.CANCELLED)


class StageStatus(str, Enum):
    """Status of individual stage."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobState:
    """Job state data class for serialization."""

    def __init__(
        self,
        job_id: str,
        backend_job_id: str | None = None,
        dataset_id: str | None = None,
        download_url: str | list | None = None,
        parameters: dict | None = None,
        current_stage: ProcessingStage = ProcessingStage.PENDING,
        status: str = "pending",
        progress: float = 0.0,
        stage_statuses: dict[str, StageStatus] | None = None,
        stage_results: dict[str, dict] | None = None,
        stage_timestamps: dict[str, dict[str, str]] | None = None,
        error: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ):
        self.job_id = job_id
        self.backend_job_id = backend_job_id or job_id
        self.dataset_id = dataset_id
        self.download_url = download_url
        self.parameters = parameters or {}
        self.current_stage = current_stage
        self.status = status
        self.progress = progress
        self.stage_statuses = stage_statuses or {
            ProcessingStage.RADIOMETRIC_CALIBRATION.value: StageStatus.PENDING.value,
            ProcessingStage.SFM.value: StageStatus.PENDING.value,
            ProcessingStage.ORTHOMOSAIC.value: StageStatus.PENDING.value,
            ProcessingStage.UPLOADING.value: StageStatus.PENDING.value,
        }
        self.stage_results = stage_results or {}
        self.stage_timestamps = stage_timestamps or {}
        self.error = error
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "job_id": self.job_id,
            "backend_job_id": self.backend_job_id,
            "dataset_id": self.dataset_id,
            "download_url": self.download_url,
            "parameters": self.parameters,
            "current_stage": self.current_stage.value if isinstance(self.current_stage, ProcessingStage) else self.current_stage,
            "status": self.status,
            "progress": self.progress,
            "stage_statuses": self.stage_statuses,
            "stage_results": self.stage_results,
            "stage_timestamps": self.stage_timestamps,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JobState":
        """Deserialize from dictionary."""
        current_stage = data.get("current_stage", "pending")
        if isinstance(current_stage, str):
            try:
                current_stage = ProcessingStage(current_stage)
            except ValueError:
                current_stage = ProcessingStage.PENDING

        return cls(
            job_id=data["job_id"],
            backend_job_id=data.get("backend_job_id"),
            dataset_id=data.get("dataset_id"),
            download_url=data.get("download_url"),
            parameters=data.get("parameters", {}),
            current_stage=current_stage,
            status=data.get("status", "pending"),
            progress=data.get("progress", 0.0),
            stage_statuses=data.get("stage_statuses"),
            stage_results=data.get("stage_results"),
            stage_timestamps=data.get("stage_timestamps"),
            error=data.get("error"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
