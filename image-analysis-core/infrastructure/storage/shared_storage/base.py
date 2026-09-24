"""Abstract interface for shared storage backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class SharedStorageBackend(ABC):
    """
    Abstract interface for shared storage between AI services.

    Provides a unified filesystem-like API that works with both
    local Docker volumes and AWS EFS.
    """

    @abstractmethod
    def get_base_path(self) -> Path:
        """
        Return the root path for all shared data.

        Returns:
            Base directory path
        """
        ...

    @abstractmethod
    def get_dataset_path(self, dataset_id: str) -> Path:
        """
        Return the path for a dataset's downloaded images.

        Args:
            dataset_id: Unique dataset identifier

        Returns:
            Path to dataset images root (contains band subfolders)
        """
        ...

    @abstractmethod
    def get_job_workspace(self, job_id: str, service: str) -> Path:
        """
        Return the workspace path for a specific job and service.

        Args:
            job_id: Unique job identifier
            service: Service name (radiometric, sfm, orthomosaic)

        Returns:
            Path to job workspace directory
        """
        ...

    @abstractmethod
    def ensure_directory(self, path: Path) -> Path:
        """
        Create a directory and all parents if they don't exist.

        Args:
            path: Directory path to create

        Returns:
            The created directory path
        """
        ...

    @abstractmethod
    def cleanup_job(self, job_id: str) -> None:
        """
        Remove all data associated with a job.

        Args:
            job_id: Job identifier to clean up
        """
        ...

    @abstractmethod
    def cleanup_dataset(self, dataset_id: str) -> None:
        """
        Remove all downloaded data for a dataset.

        Args:
            dataset_id: Dataset identifier to clean up
        """
        ...

    @abstractmethod
    def cleanup_stale(self, max_age_days: int) -> list[str]:
        """
        Remove data older than max_age_days.

        Args:
            max_age_days: Maximum age in days before cleanup

        Returns:
            List of paths that were cleaned up
        """
        ...

    @abstractmethod
    def get_disk_usage(self) -> dict:
        """
        Return disk usage information for the shared storage.

        Returns:
            Dict with total, used, free bytes
        """
        ...

    @abstractmethod
    def is_healthy(self) -> bool:
        """
        Check if the storage backend is accessible and writable.

        Returns:
            True if healthy
        """
        ...
