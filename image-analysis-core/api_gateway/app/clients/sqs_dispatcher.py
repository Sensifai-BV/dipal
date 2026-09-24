from __future__ import annotations

import asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.logging import get_logger
from infrastructure.message_queue import SQSClient, SQSSettings

__all__ = ("SQSDispatcher", "DispatchSettings")

logger = get_logger(__name__)


class DispatchSettings(BaseSettings):
    """
    Controls whether the API gateway dispatches jobs via HTTP or SQS.

    Args:
        mode: 'http' for direct service calls (default), 'sqs' for queue-based dispatch
    """

    mode: str = "http"

    model_config = SettingsConfigDict(
        env_prefix="DISPATCH_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


class SQSDispatcher:
    """
    Publish job messages to SQS queues for async service processing.

    Replaces direct HTTP calls when DISPATCH_MODE=sqs. Each service
    has its own queue and the message format mirrors the HTTP payload
    so that consumers can call the same handler logic.

    Args:
        sqs_client: Configured SQS client
    """

    def __init__(self, sqs_client: SQSClient):
        self._client = sqs_client

    async def dispatch_calibration(
        self,
        job_id: str,
        dataset_id: str,
        download_url: str | list[dict],
        parameters: dict | None = None,
    ) -> dict:
        """
        Dispatch calibration job to SQS queue.

        Args:
            job_id: Sub-job ID (e.g. {main_id}_calibration)
            dataset_id: Dataset to process
            download_url: Image source URL(s)
            parameters: Processing parameters

        Returns:
            SQS send_message response
        """
        queue_url = self._client.get_queue_url("calibration")
        message = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "download_url": download_url,
            "parameters": parameters or {},
        }
        logger.info(f"[SQS-DISPATCH] Sending calibration job {job_id} to queue")
        return await asyncio.to_thread(self._client.send_message, queue_url, message)

    async def dispatch_sfm(
        self,
        job_id: str,
        dataset_id: str,
        download_url: str | list[dict],
        parameters: dict | None = None,
    ) -> dict:
        """
        Dispatch SFM job to SQS queue.

        Args:
            job_id: Sub-job ID (e.g. {main_id}_sfm)
            dataset_id: Dataset to process
            download_url: Image source URL(s)
            parameters: Processing parameters

        Returns:
            SQS send_message response
        """
        queue_url = self._client.get_queue_url("sfm")
        message = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "download_url": download_url,
            "parameters": parameters or {},
        }
        logger.info(f"[SQS-DISPATCH] Sending SFM job {job_id} to queue")
        return await asyncio.to_thread(self._client.send_message, queue_url, message)

    async def dispatch_orthomosaic(
        self,
        job_id: str,
        dataset_id: str,
        dataset_path: str,
        parameters: dict | None = None,
    ) -> dict:
        """
        Dispatch orthomosaic job to SQS queue.

        Args:
            job_id: Sub-job ID (e.g. {main_id}_orthomosaic)
            dataset_id: Dataset to process
            dataset_path: Path to SFM output for orthomosaic input
            parameters: Processing parameters

        Returns:
            SQS send_message response
        """
        queue_url = self._client.get_queue_url("orthomosaic")
        message = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "dataset_path": dataset_path,
            "parameters": parameters or {},
        }
        logger.info(f"[SQS-DISPATCH] Sending orthomosaic job {job_id} to queue")
        return await asyncio.to_thread(self._client.send_message, queue_url, message)
