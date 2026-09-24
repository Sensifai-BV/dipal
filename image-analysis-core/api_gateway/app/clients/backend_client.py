"""Backend API Client for callbacks"""
from __future__ import annotations

import asyncio
import httpx
from typing import Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict

from chromatrace.tracer import trace_id_ctx
from infrastructure.logging import get_logger

logger = get_logger(__name__)

CALLBACK_MAX_RETRIES = 5
CALLBACK_BASE_DELAY_SECONDS = 1.0


class BackendClientSettings(BaseSettings):
    """Backend API configuration."""

    api_url: str
    callback_endpoint: str = "/v1/api/jobs/ai-callback/"
    api_secret_key: str
    callback_max_retries: int = CALLBACK_MAX_RETRIES
    callback_base_delay: float = CALLBACK_BASE_DELAY_SECONDS

    model_config = SettingsConfigDict(
        env_prefix="BACKEND_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


class BackendClient:
    """Client for sending callbacks to Backend."""

    def __init__(self, settings: BackendClientSettings):
        self.settings = settings
        self.callback_url = f"{settings.api_url.rstrip('/')}{settings.callback_endpoint}"
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Content-Type": "application/json",
                "X-API-Secret-Key": settings.api_secret_key,
            },
            event_hooks={"request": [self._inject_trace_id]},
        )

    @staticmethod
    async def _inject_trace_id(request: httpx.Request) -> None:
        trace_id = trace_id_ctx.get()
        if trace_id:
            request.headers["X-Request-ID"] = trace_id

    async def send_progress_update(
        self,
        job_id: str,
        progress: float,
        current_stage: str,
        message: str | None = None
    ) -> bool:
        """
        Send progress update to backend.

        Args:
            job_id: Job ID
            progress: Progress percentage (0-100)
            current_stage: Current processing stage
            message: Optional status message

        Returns:
            True if successful
        """
        payload = {
            "job_id": job_id,
            "type": "progress",
            "progress": progress,
            "current_stage": current_stage,
            "message": message
        }

        return await self._send_callback(payload)

    async def send_completion(
        self,
        job_id: str,
        dataset_id: str,
        outputs: Dict[str, str],
        metadata: Dict[str, Any] | None = None
    ) -> bool:
        """
        Send job completion notification to backend.

        Args:
            job_id: Job ID
            dataset_id: Dataset ID
            outputs: Dict of {output_type: s3_uri}
            metadata: Optional additional metadata

        Returns:
            True if successful
        """
        payload = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "type": "complete",
            "status": "completed",
            "outputs": outputs,
            "metadata": metadata or {}
        }

        return await self._send_callback(payload)

    async def send_failure(
        self,
        job_id: str,
        error_message: str,
        error_details: Dict[str, Any] | None = None
    ) -> bool:
        """
        Send job failure notification to backend.

        Args:
            job_id: Job ID
            error_message: Error message
            error_details: Optional error details

        Returns:
            True if successful
        """
        payload = {
            "job_id": job_id,
            "type": "error",
            "status": "failed",
            "error_message": error_message,
            "error_details": error_details or {}
        }

        return await self._send_callback(payload)

    async def send_upload_status(
        self,
        job_id: str,
        uploaded: list[Dict[str, Any]],
        failed: list[Dict[str, Any]],
    ) -> bool:
        """
        Send product upload status to backend after background uploads complete.

        Args:
            job_id: Job ID
            uploaded: List of successfully uploaded products
            failed: List of products that failed to upload

        Returns:
            True if successful
        """
        payload = {
            "job_id": job_id,
            "type": "upload_status",
            "uploaded": uploaded,
            "failed": failed,
        }

        return await self._send_callback(payload)

    async def _send_callback(self, payload: Dict[str, Any]) -> bool:
        """
        Send callback to backend with exponential backoff retry.

        Args:
            payload: Callback payload

        Returns:
            True if successful
        """
        for attempt in range(1, self.settings.callback_max_retries + 1):
            try:
                logger.info(f"Sending callback to {self.callback_url}: {payload.get('type')} (attempt {attempt})")

                response = await self._client.post(self.callback_url, json=payload)

                if response.status_code == 200:
                    logger.info(f"Callback successful for job {payload.get('job_id')}")
                    return True
                else:
                    logger.error(f"Callback failed: {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"Failed to send callback (attempt {attempt}): {e}", exc_info=True)

            if attempt < self.settings.callback_max_retries:
                delay = self.settings.callback_base_delay * (2 ** (attempt - 1))
                logger.info(f"Retrying callback in {delay:.1f}s...")
                await asyncio.sleep(delay)

        logger.error(f"Callback failed after {self.settings.callback_max_retries} attempts for job {payload.get('job_id')}")
        return False

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
