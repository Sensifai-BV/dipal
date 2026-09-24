from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.logging import get_logger
from infrastructure.redis import RedisClient, RedisSettings

from .models import JobState, ProcessingStage, StageStatus

__all__ = ["JobStateManager", "JobStateSettings"]

logger = get_logger(__name__)


class JobStateSettings(BaseSettings):
    """Job state manager settings."""

    key_prefix: str = "photogear:job:"
    ttl_hours: int = 72  # Jobs expire after 72 hours

    model_config = SettingsConfigDict(
        env_prefix="JOB_STATE_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


class JobStateManager:
    """
    Persistent job state manager using Redis.
    
    Handles:
    - Job lifecycle management
    - Stage tracking and transitions
    - Result storage between stages
    - Resume capability
    """

    def __init__(
        self,
        redis_client: RedisClient,
        settings: JobStateSettings | None = None,
    ):
        self.redis = redis_client
        self.settings = settings or JobStateSettings()
        self._key_prefix = self.settings.key_prefix
        self._ttl_seconds = self.settings.ttl_hours * 3600

    def _get_key(self, job_id: str) -> str:
        """Generate Redis key for job."""
        return f"{self._key_prefix}{job_id}"

    def create_job(
        self,
        job_id: str,
        backend_job_id: str | None = None,
        dataset_id: str | None = None,
        download_url: str | list | None = None,
        parameters: dict | None = None,
        starting_stage: str | None = None,
    ) -> JobState:
        """
        Create a new job state in Redis.

        Args:
            job_id: Unique job identifier
            backend_job_id: Backend's job ID for callbacks
            dataset_id: Dataset to process
            download_url: Image source URL(s)
            parameters: Processing parameters
            starting_stage: Stage to start from (for resume)

        Returns:
            Created JobState
        """
        now = datetime.now(UTC).isoformat()

        # Determine starting stage
        current_stage = ProcessingStage.PENDING
        if starting_stage:
            try:
                parsed = ProcessingStage(starting_stage)
                _terminal = {ProcessingStage.FAILED, ProcessingStage.CANCELLED, ProcessingStage.COMPLETED}
                if parsed in _terminal:
                    logger.warning(f"starting_stage '{starting_stage}' is a terminal state, using PENDING")
                    current_stage = ProcessingStage.PENDING
                else:
                    current_stage = parsed
            except ValueError:
                logger.warning(f"Invalid starting_stage: {starting_stage}, using PENDING")
                current_stage = ProcessingStage.PENDING

        # Initialize stage statuses
        stage_statuses = {
            ProcessingStage.RADIOMETRIC_CALIBRATION.value: StageStatus.PENDING.value,
            ProcessingStage.SFM.value: StageStatus.PENDING.value,
            ProcessingStage.ORTHOMOSAIC.value: StageStatus.PENDING.value,
            ProcessingStage.UPLOADING.value: StageStatus.PENDING.value,
        }

        # If resuming, mark earlier stages as skipped
        if starting_stage:
            stage_order = [
                ProcessingStage.RADIOMETRIC_CALIBRATION,
                ProcessingStage.SFM,
                ProcessingStage.ORTHOMOSAIC,
                ProcessingStage.UPLOADING,
            ]
            for stage in stage_order:
                if stage.value == starting_stage:
                    break
                stage_statuses[stage.value] = StageStatus.SKIPPED.value

        job_state = JobState(
            job_id=job_id,
            backend_job_id=backend_job_id or job_id,
            dataset_id=dataset_id,
            download_url=download_url,
            parameters=parameters,
            current_stage=current_stage,
            status="pending",
            progress=ProcessingStage.get_stage_progress(current_stage),
            stage_statuses=stage_statuses,
            stage_results={},
            created_at=now,
            updated_at=now,
        )

        key = self._get_key(job_id)
        self.redis.set(key, job_state.to_dict(), ttl=self._ttl_seconds)
        logger.info(f"Created job state: {job_id}, starting_stage={starting_stage}")

        return job_state

    def get_job(self, job_id: str) -> JobState | None:
        """Get job state from Redis."""
        key = self._get_key(job_id)
        data = self.redis.get(key)
        if data:
            return JobState.from_dict(data)
        return None

    def update_job(
        self,
        job_id: str,
        status: str | None = None,
        current_stage: ProcessingStage | str | None = None,
        progress: float | None = None,
        error: str | None = None,
    ) -> JobState | None:
        """Update job state fields."""
        job = self.get_job(job_id)
        if not job:
            logger.warning(f"Job not found for update: {job_id}")
            return None

        if status:
            job.status = status
        if current_stage:
            if isinstance(current_stage, str):
                try:
                    current_stage = ProcessingStage(current_stage)
                except ValueError:
                    pass
            if isinstance(current_stage, ProcessingStage):
                job.current_stage = current_stage
        if progress is not None:
            job.progress = progress
        if error:
            job.error = error

        job.updated_at = datetime.now(UTC).isoformat()

        key = self._get_key(job_id)
        self.redis.set(key, job.to_dict(), ttl=self._ttl_seconds)
        return job

    def start_stage(self, job_id: str, stage: ProcessingStage | str) -> JobState | None:
        """Mark a stage as running and record start timestamp."""
        job = self.get_job(job_id)
        if not job:
            return None

        stage_key = stage.value if isinstance(stage, ProcessingStage) else stage
        now = datetime.now(UTC).isoformat()

        job.stage_statuses[stage_key] = StageStatus.RUNNING.value
        job.current_stage = ProcessingStage(stage_key) if isinstance(stage, str) else stage
        job.status = "running"
        job.progress = ProcessingStage.get_stage_progress(job.current_stage)
        job.updated_at = now

        if stage_key not in job.stage_timestamps:
            job.stage_timestamps[stage_key] = {}
        job.stage_timestamps[stage_key]["started_at"] = now

        key = self._get_key(job_id)
        self.redis.set(key, job.to_dict(), ttl=self._ttl_seconds)
        logger.info(f"Job {job_id}: stage {stage_key} started")
        return job

    def complete_stage(
        self,
        job_id: str,
        stage: ProcessingStage | str,
        result: dict | None = None,
    ) -> tuple[JobState | None, ProcessingStage | None]:
        """
        Mark a stage as completed, record timestamp, and determine next stage.

        Returns:
            Tuple of (updated JobState, next stage to trigger or None if pipeline complete)
        """
        job = self.get_job(job_id)
        if not job:
            return None, None

        stage_key = stage.value if isinstance(stage, ProcessingStage) else stage
        now = datetime.now(UTC).isoformat()

        job.stage_statuses[stage_key] = StageStatus.COMPLETED.value

        if stage_key not in job.stage_timestamps:
            job.stage_timestamps[stage_key] = {}
        job.stage_timestamps[stage_key]["completed_at"] = now

        # Compute stage duration and persist to Redis metrics
        started_at = job.stage_timestamps[stage_key].get("started_at")
        if started_at:
            try:
                start_dt = datetime.fromisoformat(started_at)
                end_dt = datetime.fromisoformat(now)
                duration = (end_dt - start_dt).total_seconds()
                job.stage_timestamps[stage_key]["duration_seconds"] = duration
                self._record_stage_duration(stage_key, duration)
            except (ValueError, TypeError):
                pass

        # Store stage result
        if result:
            job.stage_results[stage_key] = result

        # Determine next stage
        current = ProcessingStage(stage_key) if isinstance(stage, str) else stage
        next_stage = ProcessingStage.get_next_stage(current)

        # Skip to next non-skipped stage
        while next_stage and job.stage_statuses.get(next_stage.value) == StageStatus.SKIPPED.value:
            next_stage = ProcessingStage.get_next_stage(next_stage)

        if next_stage and next_stage != ProcessingStage.COMPLETED:
            job.current_stage = next_stage
            job.progress = ProcessingStage.get_stage_progress(next_stage)
        else:
            # Pipeline complete
            job.current_stage = ProcessingStage.COMPLETED
            job.status = "completed"
            job.progress = 100.0
            next_stage = None

        job.updated_at = datetime.now(UTC).isoformat()

        key = self._get_key(job_id)
        self.redis.set(key, job.to_dict(), ttl=self._ttl_seconds)
        logger.info(f"Job {job_id}: stage {stage_key} completed, next={next_stage}")

        return job, next_stage

    def fail_stage(
        self,
        job_id: str,
        stage: ProcessingStage | str,
        error: str,
    ) -> JobState | None:
        """Mark a stage and job as failed."""
        job = self.get_job(job_id)
        if not job:
            return None

        stage_key = stage.value if isinstance(stage, ProcessingStage) else stage
        job.stage_statuses[stage_key] = StageStatus.FAILED.value
        job.status = "failed"
        job.error = error
        job.updated_at = datetime.now(UTC).isoformat()

        key = self._get_key(job_id)
        self.redis.set(key, job.to_dict(), ttl=self._ttl_seconds)
        logger.error(f"Job {job_id}: stage {stage_key} failed - {error}")

        return job

    def get_stage_result(self, job_id: str, stage: ProcessingStage | str) -> dict | None:
        """Get the result of a completed stage."""
        job = self.get_job(job_id)
        if not job:
            return None

        stage_key = stage.value if isinstance(stage, ProcessingStage) else stage
        return job.stage_results.get(stage_key)

    def update_stage_result(
        self,
        job_id: str,
        stage_key: str,
        result: dict,
    ) -> JobState | None:
        """
        Update or insert a stage result entry in Redis.

        Args:
            job_id: Job identifier
            stage_key: Key in stage_results dict (e.g. 'sfm', 'upload_results')
            result: Dict to store

        Returns:
            Updated JobState or None if job not found
        """
        job = self.get_job(job_id)
        if not job:
            logger.warning(f"Job not found for stage result update: {job_id}")
            return None

        job.stage_results[stage_key] = result
        job.updated_at = datetime.now(UTC).isoformat()

        key = self._get_key(job_id)
        self.redis.set(key, job.to_dict(), ttl=self._ttl_seconds)
        logger.info(f"Job {job_id}: stage_results['{stage_key}'] updated in Redis")
        return job

    def delete_job(self, job_id: str) -> bool:
        """Delete job state from Redis."""
        key = self._get_key(job_id)
        deleted = self.redis.delete(key)
        if deleted:
            logger.info(f"Deleted job state: {job_id}")
        return deleted > 0

    def job_exists(self, job_id: str) -> bool:
        """Check if job exists in Redis."""
        key = self._get_key(job_id)
        return self.redis.exists(key)

    # ------------------------------------------------------------------
    # Metrics persistence helpers
    # ------------------------------------------------------------------

    _METRICS_KEY = "photogear:metrics"

    def _record_stage_duration(self, stage: str, duration_seconds: float) -> None:
        """Accumulate stage duration in Redis hash for aggregate metrics."""
        try:
            pipe = self.redis.client.pipeline()
            pipe.hincrbyfloat(self._METRICS_KEY, f"stage:{stage}:total_seconds", duration_seconds)
            pipe.hincrby(self._METRICS_KEY, f"stage:{stage}:count", 1)
            pipe.execute()
        except Exception as e:
            logger.warning(f"Failed to record stage metric: {e}")

    def record_job_metrics(self, duration_seconds: float, succeeded: bool) -> None:
        """Record job-level metrics in Redis (called on job completion/failure)."""
        try:
            pipe = self.redis.client.pipeline()
            if succeeded:
                pipe.hincrby(self._METRICS_KEY, "jobs_processed", 1)
                pipe.hincrbyfloat(self._METRICS_KEY, "total_processing_seconds", duration_seconds)
            else:
                pipe.hincrby(self._METRICS_KEY, "jobs_failed", 1)
            pipe.execute()
        except Exception as e:
            logger.warning(f"Failed to record job metric: {e}")

    def record_queue_wait(self, wait_seconds: float) -> None:
        """Record queue wait time in Redis."""
        try:
            pipe = self.redis.client.pipeline()
            pipe.hincrbyfloat(self._METRICS_KEY, "queue_wait_total_seconds", wait_seconds)
            pipe.hincrby(self._METRICS_KEY, "queue_wait_count", 1)
            pipe.execute()
        except Exception as e:
            logger.warning(f"Failed to record queue wait metric: {e}")

    def get_metrics_summary(self) -> dict:
        """Read aggregate metrics from Redis for the /metrics/ endpoint."""
        try:
            raw = self.redis.client.hgetall(self._METRICS_KEY)
            if not raw:
                return {}
            return {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in raw.items()}
        except Exception as e:
            logger.warning(f"Failed to read metrics summary: {e}")
            return {}

    def count_active_jobs(self) -> int:
        """Count jobs currently in non-terminal state."""
        try:
            cursor, keys = self.redis.client.scan(
                cursor=0, match=f"{self._key_prefix}*", count=500
            )
            count = 0
            for key in keys:
                raw = self.redis.client.get(key)
                if raw:
                    import json
                    data = json.loads(raw)
                    status = data.get("status", "")
                    if status in ("pending", "running", "queued"):
                        count += 1
            while cursor:
                cursor, keys = self.redis.client.scan(
                    cursor=cursor, match=f"{self._key_prefix}*", count=500
                )
                for key in keys:
                    raw = self.redis.client.get(key)
                    if raw:
                        import json
                        data = json.loads(raw)
                        status = data.get("status", "")
                        if status in ("pending", "running", "queued"):
                            count += 1
            return count
        except Exception as e:
            logger.warning(f"Failed to count active jobs: {e}")
            return 0

