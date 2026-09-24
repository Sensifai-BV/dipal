from __future__ import annotations

from pydantic import BaseModel, Field


class ColmapPipelineInput(BaseModel):
    job_id: str = Field(..., description="Unique identifier for the job")
    storage_base_path: str = Field(
        ...,
        description="Base path for storage (e.g., local directory or cloud bucket)",
    )
    project_id: str = Field(
        ...,
        description="Identifier for the dataset to be processed",
    )
    parameters: dict | None = Field(
        None,
        description="Optional parameters for the COLMAP pipeline",
    )


class SFMJobRequest(BaseModel):
    """Request to run SFM job"""

    job_id: str = Field(..., description="Unique identifier for the job")
    dataset_id: str = Field(..., description="Dataset identifier")
    download_url: str | list[dict] = Field(..., description="Presigned URL(s) or S3 URI to download images")
    parameters: dict | None = Field(None, description="SFM parameters")


class SFMJobResponse(BaseModel):
    """Response for SFM job operations"""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    message: str | None = Field(None, description="Additional message")


class SFMJobStatusResponse(BaseModel):
    """Response for job status"""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    progress: float | None = Field(None, description="Progress percentage")
    result: dict | None = Field(None, description="Job result if completed")
    error: str | None = Field(None, description="Error message if failed")
