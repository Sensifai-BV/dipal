"""Settings for radiometric calibration service."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.storage.s3_settings import TempStorageSettings


class CallbackSettings(BaseSettings):
    """Settings for callback to API Gateway."""

    url: str = "http://api_gateway:8080"
    callback_endpoint: str = "/jobs/subservice-callback"
    timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(
        env_prefix="API_GATEWAY_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def callback_url(self) -> str:
        """Get the full callback URL for the API Gateway."""
        return f"{self.url.rstrip('/')}{self.callback_endpoint}"


class S3Settings(BaseSettings):
    """S3 storage settings."""

    ai_bucket: str = "photogear-production-ai-bucket"

    model_config = SettingsConfigDict(
        env_prefix="AWS_S3_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


__all__ = ["CallbackSettings", "S3Settings", "TempStorageSettings"]
