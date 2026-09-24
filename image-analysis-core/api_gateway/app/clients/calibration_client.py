from __future__ import annotations

import time
import asyncio
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from chromatrace.tracer import trace_id_ctx
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class CalibrationClientSettings(BaseSettings):
    address: str = ""
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: float = 2.0

    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
        env_prefix="CALIBRATION_CLIENT_",
        env_file=".env",
    )


class CalibrationClient:
    def __init__(self, settings: CalibrationClientSettings):
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.address,
            timeout=httpx.Timeout(settings.timeout_seconds, connect=10.0),
        )

    async def run_calibration(
        self,
        job_id: str,
        dataset_id: str,
        download_url: str,
        parameters: dict | None = None,
    ) -> dict:
        """
        Start radiometric calibration job.

        This is a fire-and-forget call - the calibration service will
        send a callback to /jobs/subservice-callback when complete.
        This method should return quickly (within timeout_seconds).
        """
        payload = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "download_url": download_url,
            "parameters": parameters or {},
        }

        last_error = None
        for attempt in range(1, self.settings.max_retries + 1):
            logger.info(f"[CLIENT] Sending calibration request for job {job_id} (attempt {attempt}/{self.settings.max_retries})")
            start_time = time.time()

            try:
                headers = {}
                trace_id = trace_id_ctx.get()
                if trace_id:
                    headers["X-Request-ID"] = trace_id
                response = await self._client.post("/calibration/run", json=payload, headers=headers)
                elapsed = time.time() - start_time
                logger.info(f"[CLIENT] Calibration response received for job {job_id} in {elapsed:.2f}s, status={response.status_code}")
                response.raise_for_status()
                result = response.json()
                logger.info(f"[CLIENT] Calibration response body for job {job_id}: {result}")
                return result

            except httpx.ConnectError as e:
                elapsed = time.time() - start_time
                logger.error(f"[CLIENT] Calibration connection error for job {job_id} after {elapsed:.2f}s (attempt {attempt}): {e}")
                last_error = e

            except httpx.TimeoutException as e:
                elapsed = time.time() - start_time
                logger.error(f"[CLIENT] Calibration timeout for job {job_id} after {elapsed:.2f}s (attempt {attempt})")
                last_error = e

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[CLIENT] Calibration request failed for job {job_id} after {elapsed:.2f}s (attempt {attempt}): {e}")
                last_error = e

            if attempt < self.settings.max_retries:
                logger.info(f"[CLIENT] Retrying calibration request in {self.settings.retry_delay_seconds}s...")
                await asyncio.sleep(self.settings.retry_delay_seconds)

        raise Exception(f"Calibration service unavailable after {self.settings.max_retries} attempts: {last_error}")

    async def get_job_status(self, job_id: str) -> dict:
        """Get calibration job status."""
        response = await self._client.get(f"/calibration/jobs/{job_id}/status")
        response.raise_for_status()
        return response.json()

    async def cancel_job(self, job_id: str) -> dict:
        """Cancel calibration job."""
        response = await self._client.post(f"/calibration/jobs/{job_id}/cancel")
        response.raise_for_status()
        return response.json()

    async def get_result(self, job_id: str) -> dict:
        """Get calibration job result."""
        response = await self._client.get(f"/calibration/jobs/{job_id}/result")
        response.raise_for_status()
        return response.json()

    async def calibrate_images(self): ...

    async def generate_ndvi(self): ...

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
