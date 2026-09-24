from __future__ import annotations

from pydantic import BaseModel, Field


class OrthomosaicJobRequest(BaseModel):
    """Request to run orthomosaic generation job"""

    job_id: str = Field(..., description="Unique identifier for the job")
    dataset_id: str = Field(..., description="Dataset identifier")
    dataset_path: str = Field(..., description="Path to dataset with SFM results")
    parameters: dict | None = Field(None, description="Orthomosaic parameters")


class OrthomosaicJobResponse(BaseModel):
    """Response for orthomosaic job operations"""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    message: str | None = Field(None, description="Additional message")


class OrthomosaicJobStatusResponse(BaseModel):
    """Response for job status"""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    progress: float | None = Field(None, description="Progress percentage")
    result: dict | None = Field(None, description="Job result if completed")
    error: str | None = Field(None, description="Error message if failed")
