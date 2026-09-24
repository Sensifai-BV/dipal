"""Local filesystem shared storage backend."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from infrastructure.logging import get_logger
from infrastructure.storage.s3_settings import TempStorageSettings

from .base import SharedStorageBackend

logger = get_logger(__name__)


class LocalSharedStorage(SharedStorageBackend):
    """
    Local filesystem shared storage.

    Uses a local directory (typically a Docker named volume) for
    shared data between services running on the same host.

    Args:
        settings: Temp storage settings with base_path and cleanup_days
    """

    def __init__(self, settings: TempStorageSettings | None = None):
        self._settings = settings or TempStorageSettings()
        self._base_path = Path(self._settings.base_path)

    def get_base_path(self) -> Path:
        """Return the root path for all shared data."""
        return self._base_path

    def get_dataset_path(self, dataset_id: str) -> Path:
        """
        Return the dataset directory path.

        Args:
            dataset_id: Unique dataset identifier

        Returns:
            Path to datasets/{dataset_id}
        """
        return self._base_path / "datasets" / dataset_id

    def get_job_workspace(self, job_id: str, service: str) -> Path:
        """
        Return the job workspace directory.

        Args:
            job_id: Unique job identifier
            service: Service name (radiometric, sfm, orthomosaic)

        Returns:
            Path to jobs/{service}/{job_id}
        """
        return self._base_path / "jobs" / service / job_id

    def ensure_directory(self, path: Path) -> Path:
        """
        Create directory with parents.

        Args:
            path: Directory path to create

        Returns:
            The path that was created
        """
        path.mkdir(parents=True, exist_ok=True)
        return path

    def cleanup_job(self, job_id: str) -> None:
        """
        Remove all data for a job across all services.

        Args:
            job_id: Job identifier
        """
        jobs_root = self._base_path / "jobs"
        if not jobs_root.exists():
            return

        cleaned = []
        for service_dir in jobs_root.iterdir():
            if not service_dir.is_dir():
                continue
            for job_dir in service_dir.iterdir():
                if job_dir.is_dir() and job_id in job_dir.name:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    cleaned.append(str(job_dir))

        if cleaned:
            logger.info(f"Cleaned up job {job_id}: {len(cleaned)} directories removed")

    def cleanup_dataset(self, dataset_id: str) -> None:
        """
        Remove downloaded data for a dataset.

        Args:
            dataset_id: Dataset identifier
        """
        dataset_path = self.get_dataset_path(dataset_id)
        if dataset_path.exists():
            shutil.rmtree(dataset_path, ignore_errors=True)
            logger.info(f"Cleaned up dataset {dataset_id}")

    def cleanup_stale(self, max_age_days: int) -> list[str]:
        """
        Remove directories older than max_age_days based on mtime.

        Args:
            max_age_days: Maximum age in days

        Returns:
            List of removed paths
        """
        cutoff = time.time() - (max_age_days * 86400)
        cleaned: list[str] = []

        for category in ["datasets", "jobs"]:
            category_path = self._base_path / category
            if not category_path.exists():
                continue

            for item in category_path.rglob("*"):
                if not item.is_dir():
                    continue
                try:
                    if item.stat().st_mtime < cutoff:
                        shutil.rmtree(item, ignore_errors=True)
                        cleaned.append(str(item))
                except OSError:
                    continue

        if cleaned:
            logger.info(f"Stale cleanup removed {len(cleaned)} directories (max_age={max_age_days}d)")
        return cleaned

    def get_disk_usage(self) -> dict:
        """
        Return disk usage for the shared storage mount.

        Returns:
            Dict with total, used, free in bytes
        """
        try:
            usage = shutil.disk_usage(self._base_path)
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent_used": round(usage.used / usage.total * 100, 1) if usage.total else 0,
            }
        except OSError as e:
            logger.error(f"Failed to get disk usage: {e}")
            return {"total": 0, "used": 0, "free": 0, "percent_used": 0}

    def is_healthy(self) -> bool:
        """
        Check local storage is accessible.

        Returns:
            True if base path exists and is writable
        """
        try:
            self._base_path.mkdir(parents=True, exist_ok=True)
            probe = self._base_path / ".health_check"
            probe.write_text("ok")
            probe.unlink()
            return True
        except OSError as e:
            logger.error(f"Local shared storage health check failed: {e}")
            return False
