from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageDriver(ABC):
    """
    Abstract base class for storage drivers.

    Defines the interface that all storage drivers (Local, S3, etc.) must implement.
    """

    @abstractmethod
    def connect(self) -> None:
        """
        Establish connection to the storage backend.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close connection to the storage backend.
        """
        pass

    @abstractmethod
    def fetch_images(self, project_id: str, destination_path: Path) -> list[Path]:
        """
        Fetch images from storage for a given project.

        Args:
            project_id: Unique identifier for the project
            destination_path: Local path where images should be downloaded

        Returns:
            List of paths to downloaded images

        Raises:
            FileNotFoundError: If project images don't exist
            IOError: If download fails
        """
        pass

    @abstractmethod
    def push_results(self, project_id: str, source_path: Path, run_id: int) -> None:
        """
        Push processing results to storage.

        Args:
            project_id: Unique identifier for the project
            source_path: Local path containing results to upload
            run_id: Run identifier (e.g., 1, 2, 3)

        Raises:
            IOError: If upload fails
        """
        pass

    @abstractmethod
    def list_images(self, project_id: str) -> list[str]:
        """
        List available images for a project.

        Args:
            project_id: Unique identifier for the project

        Returns:
            List of image filenames
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if a path exists in storage.

        Args:
            path: Path to check (relative to storage root)

        Returns:
            True if path exists, False otherwise
        """
        pass

    @abstractmethod
    def delete_project(self, project_id: str) -> None:
        """
        Delete all data for a project.

        Args:
            project_id: Unique identifier for the project

        Raises:
            IOError: If deletion fails
        """
        pass

    def fetch_auxiliary_files(
        self,
        project_id: str,
        destination_path: Path,
    ) -> list[Path]:
        """
        Download non-image auxiliary files (PPK/GNSS data) for a project.

        Downloads files whose extensions match the PPK/GNSS auxiliary set:
        ``.nav``, ``.obs``, ``.bin``, ``.mrk`` (case-insensitive).

        Searches both the ``images/`` prefix (common for bulk DJI uploads where
        all files sit in the same S3 folder) and a dedicated ``ppk/`` prefix.

        The default implementation returns an empty list.  Override in drivers
        that support auxiliary-file storage.

        Args:
            project_id: Unique identifier for the project
            destination_path: Local directory where files should be saved

        Returns:
            List of paths to downloaded auxiliary files (may be empty)
        """
        return []
