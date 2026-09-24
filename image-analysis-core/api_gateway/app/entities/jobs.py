from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"


class ProcessingStage(str, Enum):
    """
    Processing pipeline stages.
    
    These stage names are consistent with Backend (Django).
    Backend equivalent: backend/apps/jobs/processing_stages.py
    """

    PENDING = "pending"
    QUEUED = "queued"
    RADIOMETRIC_CALIBRATION = "radiometric_calibration"
    SFM = "sfm"
    ORTHOMOSAIC = "orthomosaic"  # Consistent naming (was orthomosaic_generation)
    UPLOADING = "uploading"  # Consistent naming (was uploading_results)
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobInitializationInput(BaseModel):
    job_id: str = Field(..., description="Unique identifier for the job")
    dataset_id: str = Field(
        ...,
        description="Identifier for the dataset to be processed",
    )
    download_url: str = Field(..., description="URL to download the data for the job")
    parameters: dict | None = Field(
        None,
        description="Optional parameters for job initialization",
    )


class JobRunRequest(BaseModel):
    """Request to run a job"""

    job_id: str | None = Field(None, description="Job ID from backend (if provided, will be used instead of generating new one)")
    dataset_id: str = Field(..., description="Identifier for the dataset")
    download_url: str | list[dict] = Field(..., description="Download URL or list of image URLs with filenames")
    parameters: dict | None = Field(None, description="Processing parameters")
    starting_stage: str | None = Field(None, description="Stage to resume from (for retry/resume functionality)")


class JobInitializationOutput(BaseModel):
    job_id: str = Field(..., description="Unique identifier for the job")
    dataset_id: str = Field(
        ...,
        description="Identifier for the dataset to be processed",
    )
    status: str = Field(..., description="Current status of the job")
    message: str | None = Field(
        None,
        description="Additional information about the job initialization",
    )


class JobStatusResponse(BaseModel):
    """Response for job status queries"""

    job_id: str = Field(..., description="Unique identifier for the job")
    status: JobStatus = Field(..., description="Current status of the job")
    progress: float | None = Field(None, description="Progress percentage (0-100)")
    current_stage: ProcessingStage | None = Field(
        None,
        description="Current processing stage",
    )
    result: dict | None = Field(None, description="Job result if completed")
    error: str | None = Field(None, description="Error message if failed")
    created_at: str | None = Field(None, description="Job creation timestamp")
    updated_at: str | None = Field(None, description="Last update timestamp")


class JobCancelResponse(BaseModel):
    """Response for job cancellation"""

    job_id: str = Field(..., description="Job identifier")
    cancelled: bool = Field(..., description="Whether cancellation was successful")
    message: str = Field(..., description="Cancellation message")


class JobSyncInput(BaseModel):
    job_id: str = Field(..., description="Unique identifier for the job")
    # ToDo: Add more fields as necessary for synchronization


class JobSyncOutput(BaseModel):
    job_id: str = Field(..., description="Unique identifier for the job")
    status: str = Field(..., description="Current status of the job")
    progress: float | None = Field(None, description="Progress percentage of the job")


class S3StorageConfig(BaseModel):
    bucket_name: str = Field(..., description="Name of the S3 bucket")
    access_key: str = Field(..., description="Access key for S3")
    secret_key: str = Field(..., description="Secret key for S3")
    region: str | None = Field(None, description="AWS region of the S3 bucket")
    prefix: str | None = Field(None, description="Prefix path within the S3 bucket")
