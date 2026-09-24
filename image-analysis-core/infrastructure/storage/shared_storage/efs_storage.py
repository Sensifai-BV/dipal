"""AWS EFS shared storage backend."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from infrastructure.logging import get_logger

from .base import SharedStorageBackend
from .settings import EFSSettings

logger = get_logger(__name__)


class EFSSharedStorage(SharedStorageBackend):
    """
    AWS EFS shared storage backend.

    EFS is mounted as a POSIX filesystem (e.g. via ECS task definition
    or docker volume plugin). File I/O uses standard pathlib operations.
    The boto3 client is used only for management APIs (describe, lifecycle).

    Args:
        settings: EFS specific configuration
    """

    def __init__(self, settings: EFSSettings | None = None):
        self._settings = settings or EFSSettings()
        self._base_path = Path(self._settings.mount_point)
        self._efs_client: boto3.client | None = None

    @property
    def _client(self) -> boto3.client:
        """Lazy-init boto3 EFS client for management operations."""
        if self._efs_client is None:
            kwargs: dict = {"region_name": self._settings.aws_region}
            if self._settings.access_key_id and self._settings.secret_access_key:
                kwargs["aws_access_key_id"] = self._settings.access_key_id
                kwargs["aws_secret_access_key"] = self._settings.secret_access_key
            self._efs_client = boto3.client("efs", **kwargs)
        return self._efs_client

    def get_base_path(self) -> Path:
        """Return the EFS mount point root."""
        return self._base_path

    def get_dataset_path(self, dataset_id: str) -> Path:
        """
        Return dataset directory on EFS.

        Args:
            dataset_id: Unique dataset identifier

        Returns:
            Path to datasets/{dataset_id}
        """
        return self._base_path / "datasets" / dataset_id

    def get_job_workspace(self, job_id: str, service: str) -> Path:
        """
        Return job workspace directory on EFS.

        Args:
            job_id: Unique job identifier
            service: Service name (radiometric, sfm, orthomosaic)

        Returns:
            Path to jobs/{service}/{job_id}
        """
        return self._base_path / "jobs" / service / job_id

    def ensure_directory(self, path: Path) -> Path:
        """
        Create directory with parents on EFS.

        Args:
            path: Directory to create

        Returns:
            Created path
        """
        path.mkdir(parents=True, exist_ok=True)
        return path

    def cleanup_job(self, job_id: str) -> None:
        """
        Remove all job data from EFS.

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
            logger.info(f"[EFS] Cleaned up job {job_id}: {len(cleaned)} directories")

    def cleanup_dataset(self, dataset_id: str) -> None:
        """
        Remove dataset data from EFS.

        Args:
            dataset_id: Dataset identifier
        """
        dataset_path = self.get_dataset_path(dataset_id)
        if dataset_path.exists():
            shutil.rmtree(dataset_path, ignore_errors=True)
            logger.info(f"[EFS] Cleaned up dataset {dataset_id}")

    def cleanup_stale(self, max_age_days: int) -> list[str]:
        """
        Remove directories older than max_age_days.

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
            logger.info(f"[EFS] Stale cleanup removed {len(cleaned)} directories")
        return cleaned

    def get_disk_usage(self) -> dict:
        """
        Return EFS usage from AWS API if available, else from filesystem.

        Returns:
            Dict with total, used, free bytes
        """
        if self._settings.file_system_id:
            try:
                return self._get_efs_metrics()
            except (ClientError, Exception) as e:
                logger.warning(f"[EFS] Could not get EFS metrics via API: {e}")

        try:
            usage = shutil.disk_usage(self._base_path)
            return {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent_used": round(usage.used / usage.total * 100, 1) if usage.total else 0,
            }
        except OSError as e:
            logger.error(f"[EFS] Failed to get disk usage: {e}")
            return {"total": 0, "used": 0, "free": 0, "percent_used": 0}

    def _get_efs_metrics(self) -> dict:
        """
        Query EFS describe-file-systems for size info.

        Returns:
            Dict with EFS size metrics

        Raises:
            ClientError: If AWS API call fails
        """
        response = self._client.describe_file_systems(
            FileSystemId=self._settings.file_system_id
        )
        fs = response["FileSystems"][0]
        size_bytes = fs.get("SizeInBytes", {})
        used = size_bytes.get("Value", 0)
        return {
            "total": 0,
            "used": used,
            "free": 0,
            "efs_file_system_id": self._settings.file_system_id,
            "lifecycle_state": fs.get("LifeCycleState", "unknown"),
            "performance_mode": fs.get("PerformanceMode", "unknown"),
            "throughput_mode": fs.get("ThroughputMode", "unknown"),
        }

    def is_healthy(self) -> bool:
        """
        Check EFS mount is accessible and writable.

        Returns:
            True if mount point exists and is writable
        """
        try:
            self._base_path.mkdir(parents=True, exist_ok=True)
            probe = self._base_path / ".efs_health_check"
            probe.write_text("ok")
            probe.unlink()

            if self._settings.file_system_id:
                response = self._client.describe_file_systems(
                    FileSystemId=self._settings.file_system_id
                )
                state = response["FileSystems"][0].get("LifeCycleState")
                if state != "available":
                    logger.warning(f"[EFS] Filesystem state: {state}")
                    return False

            return True
        except (OSError, ClientError) as e:
            logger.error(f"[EFS] Health check failed: {e}")
            return False

    def describe_filesystem(self) -> dict:
        """
        Return EFS filesystem metadata from AWS API.

        Returns:
            Filesystem description dict

        Raises:
            ClientError: If API call fails
            ValueError: If no file_system_id configured
        """
        if not self._settings.file_system_id:
            raise ValueError("EFS_FILE_SYSTEM_ID not configured")

        response = self._client.describe_file_systems(
            FileSystemId=self._settings.file_system_id
        )
        return response["FileSystems"][0]
