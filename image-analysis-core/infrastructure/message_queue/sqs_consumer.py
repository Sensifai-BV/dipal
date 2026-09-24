from __future__ import annotations

import asyncio
import json
import signal
from collections.abc import Awaitable, Callable
from typing import Any

from infrastructure.logging import get_logger
from .sqs_client import SQSClient
from .sqs_settings import SQSSettings

__all__ = ("SQSConsumer",)

logger = get_logger(__name__)


class SQSConsumer:
    """
    Async SQS polling consumer for processing service queues.

    Polls a single SQS queue in a loop, deserializes messages, and
    invokes the handler coroutine for each job. Designed to run
    alongside the FastAPI HTTP server (for health checks / direct calls).

    Args:
        sqs_client: Configured SQS client
        queue_url: URL of the queue to poll
        handler: Async callable(message_body: dict) that processes the job
        service_name: Human-readable name for log messages
    """

    def __init__(
        self,
        sqs_client: SQSClient,
        queue_url: str,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        service_name: str = "unknown",
    ):
        self._client = sqs_client
        self._queue_url = queue_url
        self._handler = handler
        self._service_name = service_name
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start polling in a background asyncio task."""
        if self._running:
            logger.warning(f"[SQS-CONSUMER-{self._service_name}] Already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            f"[SQS-CONSUMER-{self._service_name}] Started polling {self._queue_url}"
        )

    async def stop(self) -> None:
        """Gracefully stop the polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"[SQS-CONSUMER-{self._service_name}] Stopped")

    async def _poll_loop(self) -> None:
        """
        Main polling loop.

        Long-polls the SQS queue, processes each message, and deletes
        it on success. On handler failure the message stays in the queue
        and will be retried (or sent to DLQ after maxReceiveCount).
        """
        settings = self._client.settings

        while self._running:
            try:
                messages = await asyncio.to_thread(
                    self._client.receive_messages,
                    self._queue_url,
                )

                for msg in messages:
                    receipt = msg["ReceiptHandle"]
                    try:
                        body = json.loads(msg["Body"])
                        logger.info(
                            f"[SQS-CONSUMER-{self._service_name}] "
                            f"Received job: {body.get('job_id', 'unknown')}"
                        )

                        await self._handler(body)

                        await asyncio.to_thread(
                            self._client.delete_message,
                            self._queue_url,
                            receipt,
                        )
                        logger.info(
                            f"[SQS-CONSUMER-{self._service_name}] "
                            f"Job completed, message deleted"
                        )

                    except json.JSONDecodeError:
                        logger.error(
                            f"[SQS-CONSUMER-{self._service_name}] "
                            f"Invalid JSON in message, deleting"
                        )
                        await asyncio.to_thread(
                            self._client.delete_message,
                            self._queue_url,
                            receipt,
                        )

                    except Exception as exc:
                        logger.error(
                            f"[SQS-CONSUMER-{self._service_name}] "
                            f"Handler failed: {exc}",
                            exc_info=True,
                        )

                if not messages:
                    await asyncio.sleep(settings.poll_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    f"[SQS-CONSUMER-{self._service_name}] Poll error: {exc}",
                    exc_info=True,
                )
                await asyncio.sleep(settings.poll_interval_seconds)
