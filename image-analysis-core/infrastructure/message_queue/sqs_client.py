from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.config import Config

from infrastructure.logging import get_logger
from .sqs_settings import SQSSettings

__all__ = ("SQSClient",)

logger = get_logger(__name__)


class SQSClient:
    """
    Thin wrapper around boto3 SQS operations.

    Args:
        settings: SQS configuration (credentials, region, queue URLs)
    """

    def __init__(self, settings: SQSSettings | None = None):
        self.settings = settings or SQSSettings()
        self._client = self._build_client()

    def _build_client(self):
        """
        Create boto3 SQS client from settings.

        Returns:
            boto3 SQS client
        """
        config = Config(
            region_name=self.settings.region_name,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        if self.settings.use_aws_role:
            return boto3.client("sqs", config=config)

        return boto3.client(
            "sqs",
            aws_access_key_id=self.settings.access_key_id,
            aws_secret_access_key=self.settings.secret_access_key,
            region_name=self.settings.region_name,
            config=config,
        )

    def send_message(self, queue_url: str, message_body: dict) -> dict:
        """
        Publish a JSON message to an SQS queue.

        Args:
            queue_url: Full SQS queue URL
            message_body: Dict to serialize as JSON message body

        Returns:
            SQS SendMessage response dict
        """
        logger.info(f"[SQS] Publishing message to {queue_url}")
        response = self._client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body),
        )
        logger.info(f"[SQS] Message sent: MessageId={response.get('MessageId')}")
        return response

    def receive_messages(
        self,
        queue_url: str,
        max_messages: int | None = None,
        wait_time: int | None = None,
        visibility_timeout: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Long-poll for messages from an SQS queue.

        Args:
            queue_url: Full SQS queue URL
            max_messages: Max messages to fetch (default from settings)
            wait_time: Long-poll wait seconds (default from settings)
            visibility_timeout: Seconds before message becomes visible again

        Returns:
            List of SQS message dicts
        """
        response = self._client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages or self.settings.max_messages_per_poll,
            WaitTimeSeconds=wait_time or self.settings.wait_time_seconds,
            VisibilityTimeout=visibility_timeout or self.settings.visibility_timeout,
        )
        return response.get("Messages", [])

    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        """
        Delete a message after successful processing.

        Args:
            queue_url: Full SQS queue URL
            receipt_handle: Receipt handle of the message to delete
        """
        self._client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )
        logger.debug("[SQS] Message deleted")

    def change_visibility(
        self, queue_url: str, receipt_handle: str, timeout: int
    ) -> None:
        """
        Extend visibility timeout for long-running jobs.

        Args:
            queue_url: Full SQS queue URL
            receipt_handle: Receipt handle of the message
            timeout: New visibility timeout in seconds
        """
        self._client.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=timeout,
        )

    def get_queue_url(self, service_name: str) -> str:
        """
        Get queue URL for a service name.

        Args:
            service_name: One of 'calibration', 'sfm', 'orthomosaic'

        Returns:
            Queue URL string

        Raises:
            ValueError: If service name is unknown
        """
        queue_map = {
            "calibration": self.settings.calibration_queue_url,
            "sfm": self.settings.sfm_queue_url,
            "orthomosaic": self.settings.orthomosaic_queue_url,
        }
        url = queue_map.get(service_name)
        if not url:
            raise ValueError(f"Unknown service: {service_name}")
        return url
