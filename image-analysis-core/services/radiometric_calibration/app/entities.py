from __future__ import annotations

from pydantic import BaseModel, Field


class NDVICalculationInput(BaseModel):
    job_id: str = Field(..., description="Unique identifier for the calibration job")
    s3_url_get: str = Field(
        ...,
        description="Pre-signed S3 URL for accessing the input data",
    )
    s3_url_post: str = Field(
        ...,
        description="Pre-signed S3 URL for uploading the calibrated output data",
    )
    parameters: dict | None = Field(
        None,
        description="Optional parameters for the calibration process",
    )


class NDVICalculationOutput(BaseModel):
    job_id: str = Field(..., description="Unique identifier for the calibration job")
    status: str = Field(..., description="Status of the calibration process")
    message: str | None = Field(
        None,
        description="Additional information about the calibration process",
    )


class CalibrationJobRequest(BaseModel):
    """Request to run calibration job"""

    job_id: str = Field(..., description="Unique identifier for the job")
    dataset_id: str = Field(..., description="Dataset identifier")
    download_url: str | list[dict] = Field(..., description="Download URL for the dataset (string or list of presigned URLs)")
    parameters: dict | None = Field(None, description="Calibration parameters")


class CalibrationJobResponse(BaseModel):
    """Response for calibration job operations"""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    message: str | None = Field(None, description="Additional message")


class CalibrationJobStatusResponse(BaseModel):
    """Response for job status"""

    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status")
    progress: float | None = Field(None, description="Progress percentage")
    result: dict | None = Field(None, description="Job result if completed")
    error: str | None = Field(None, description="Error message if failed")
