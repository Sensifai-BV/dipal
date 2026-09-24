from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.logging import get_logger

__all__ = ("BackgroundTaskHandler", "JobStatus", "BackgroundTaskSettings")

logger = get_logger(__name__)


class BackgroundTaskSettings(BaseSettings):
    """Background task handler settings."""

    use_redis: bool = True
    cleanup_hours: int = 24
    max_concurrent_pipelines: int = 1

    model_config = SettingsConfigDict(
        env_prefix="BACKGROUND_TASK_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"


class BackgroundTaskHandler:
    """
    Background task handler with optional Redis persistence.
    
    Manages async task execution and job status tracking.
    When Redis is configured, job status is persisted for recovery.
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        settings: BackgroundTaskSettings | None = None,
    ):
        self.settings = settings or BackgroundTaskSettings()
        self.redis = redis_client
        self._task_storage: dict[str, dict[str, Any]] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._key_prefix = "photogear:task:"
        self.assets_file_path = Path("./data")
        self._pipeline_semaphore = asyncio.Semaphore(
            self.settings.max_concurrent_pipelines
        )
        self._pipeline_events: dict[str, asyncio.Event] = {}
        
        # Backward compatibility aliases
        self.task_storage = self._task_storage
        self.running_tasks = self._running_tasks

    def _get_redis_key(self, job_id: str) -> str:
        """Generate Redis key for task."""
        return f"{self._key_prefix}{job_id}"

    def _get_storage(self, job_id: str) -> dict[str, Any] | None:
        """Get task data from storage (Redis or in-memory)."""
        if self.redis and self.settings.use_redis:
            return self.redis.get(self._get_redis_key(job_id))
        return self._task_storage.get(job_id)

    def _set_storage(self, job_id: str, data: dict[str, Any]):
        """Save task data to storage (Redis or in-memory)."""
        if self.redis and self.settings.use_redis:
            self.redis.set(
                self._get_redis_key(job_id),
                data,
                ttl=self.settings.cleanup_hours * 3600,
            )
        self._task_storage[job_id] = data

    def _delete_storage(self, job_id: str):
        """Delete task data from storage."""
        if self.redis and self.settings.use_redis:
            self.redis.delete(self._get_redis_key(job_id))
        self._task_storage.pop(job_id, None)

    def create_job(self, job_id: str, metadata: dict[str, Any] | None = None):
        """Create a new job entry."""
        now = datetime.now(UTC).isoformat()
        data = {
            "status": JobStatus.PENDING.value,
            "result": None,
            "error": None,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
            "progress": 0.0,
        }
        self._set_storage(job_id, data)
        logger.info(f"Job {job_id} created")

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: Any = None,
        error: str | None = None,
        progress: float | None = None,
    ):
        """Update job status and metadata."""
        data = self._get_storage(job_id)
        if data:
            data["status"] = status.value if isinstance(status, JobStatus) else status
            data["updated_at"] = datetime.now(UTC).isoformat()
            if result is not None:
                data["result"] = result
            if error is not None:
                data["error"] = error
            if progress is not None:
                data["progress"] = progress
            self._set_storage(job_id, data)
            logger.info(f"Job {job_id} status updated to {status}")

    def update_job_metadata(self, job_id: str, metadata: dict[str, Any]):
        """Update job metadata fields."""
        data = self._get_storage(job_id)
        if data:
            data["metadata"].update(metadata)
            data["updated_at"] = datetime.now(UTC).isoformat()
            self._set_storage(job_id, data)

    def store_task_result(
        self,
        task_id: str,
        status: str,
        result: Any = None,
        error: str = "",
    ):
        """Legacy method for backward compatibility."""
        now = datetime.now(UTC).isoformat()
        data = {
            "status": status,
            "result": result,
            "error": error,
            "metadata": {},
            "created_at": now,
            "updated_at": now,
            "progress": 100.0 if status == "completed" else 0.0,
        }
        self._set_storage(task_id, data)

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get task/job status."""
        data = self._get_storage(task_id)
        if not data:
            return {"status": JobStatus.NOT_FOUND.value, "job_id": task_id}
        return data

    async def run_background_task(
        self,
        job_id: str,
        task_func: Callable[..., Coroutine[Any, Any, Any]],
        *args,
        **kwargs,
    ):
        """Execute a task in the background."""
        try:
            self.update_job_status(job_id, JobStatus.RUNNING)
            result = await task_func(*args, **kwargs)
            self.update_job_status(
                job_id,
                JobStatus.COMPLETED,
                result=result,
                progress=100.0,
            )
            logger.info(f"Job {job_id} completed successfully")
        except asyncio.CancelledError:
            self.update_job_status(
                job_id,
                JobStatus.CANCELLED,
                error="Job was cancelled",
            )
            logger.info(f"Job {job_id} was cancelled")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.update_job_status(job_id, JobStatus.FAILED, error=error_msg)
            logger.error(f"Job {job_id} failed: {error_msg}")
        finally:
            if job_id in self._running_tasks:
                del self._running_tasks[job_id]

    def start_background_task(
        self,
        job_id: str,
        task_func: Callable[..., Coroutine[Any, Any, Any]],
        *args,
        **kwargs,
    ):
        """Start a background task and track it."""
        task = asyncio.create_task(
            self.run_background_task(job_id, task_func, *args, **kwargs),
        )
        self._running_tasks[job_id] = task
        logger.info(f"Background task started for job {job_id}")

    async def acquire_pipeline_slot(self, job_id: str) -> None:
        """Acquire a pipeline execution slot, blocking if at capacity."""
        logger.info(
            f"Job {job_id} waiting for pipeline slot "
            f"(max={self.settings.max_concurrent_pipelines})"
        )
        await self._pipeline_semaphore.acquire()
        self._pipeline_events[job_id] = asyncio.Event()
        logger.info(f"Job {job_id} acquired pipeline slot")

    def signal_pipeline_complete(self, job_id: str) -> None:
        """Signal that a pipeline has finished, unblocking the waiting task."""
        event = self._pipeline_events.get(job_id)
        if event:
            event.set()
            logger.info(f"Pipeline completion signaled for job {job_id}")

    def release_pipeline_slot(self, job_id: str) -> None:
        """Release a pipeline execution slot."""
        self._pipeline_events.pop(job_id, None)
        try:
            self._pipeline_semaphore.release()
            logger.info(f"Pipeline slot released for job {job_id}")
        except ValueError:
            logger.warning(f"Pipeline slot already released for job {job_id}")

    async def wait_for_pipeline(self, job_id: str) -> None:
        """Wait until the pipeline completion event is signaled."""
        event = self._pipeline_events.get(job_id)
        if event:
            await event.wait()

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        if job_id in self._running_tasks:
            task = self._running_tasks[job_id]
            task.cancel()
            logger.info(f"Cancellation requested for job {job_id}")
            return True
        
        data = self._get_storage(job_id)
        if data:
            status = data.get("status")
            if status in [JobStatus.PENDING.value, "pending"]:
                self.update_job_status(
                    job_id,
                    JobStatus.CANCELLED,
                    error="Job cancelled before execution",
                )
                return True
        return False

    def store_file(self, byte_file: bytes, file_name: str) -> Path:
        """Store a file and return its path."""
        try:
            extension = file_name.split(".")[-1]
            file_path = self.assets_file_path / f"{uuid.uuid4()}.{extension}"
            self.assets_file_path.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(byte_file)
            return file_path
        except Exception as e:
            logger.error(f"The file cannot be saved: {e}")
            raise OSError(e) from e

    def cleanup_old_tasks(self, max_age_hours: int | None = None):
        """Clean up old tasks older than max_age_hours."""
        max_age = max_age_hours or self.settings.cleanup_hours
        current_time = datetime.now(UTC)
        to_remove = []
        
        for task_id, task_data in self._task_storage.items():
            if "updated_at" in task_data:
                updated_at = task_data["updated_at"]
                if isinstance(updated_at, str):
                    updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                age = (current_time - updated_at).total_seconds() / 3600
                if age > max_age and task_id not in self._running_tasks:
                    to_remove.append(task_id)

        for task_id in to_remove:
            self._delete_storage(task_id)
            logger.info(f"Cleaned up old task {task_id}")
