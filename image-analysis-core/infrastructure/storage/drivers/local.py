from __future__ import annotations

import shutil
from pathlib import Path

from .base import StorageDriver
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class LocalStorageDriver(StorageDriver):
    """
    Local filesystem storage driver.

    Manages files on the local filesystem. Useful for development and testing.
    """

    def __init__(self, base_path: Path):
        """
        Initialize local storage driver.

        Args:
            base_path: Root directory for storage
        """
        self.base_path = Path(base_path)
        self._connected = False

    def connect(self) -> None:
        """
        Establish connection (ensure base path exists).
        """
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            self._connected = True
            logger.info(f"Connected to local storage at {self.base_path}")
        except Exception as e:
            logger.error(f"Failed to connect to local storage: {e}")
            raise ConnectionError(f"Cannot create storage directory: {e}")

    def disconnect(self) -> None:
        """
        Close connection (no-op for local storage).
        """
        self._connected = False
        logger.info("Disconnected from local storage")

    def fetch_images(self, project_id: str, destination_path: Path) -> list[Path]:
        """
        Copy images from storage to destination.

        Args:
            project_id: Unique identifier for the project
            destination_path: Local path where images should be copied

        Returns:
            List of paths to copied images
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        source_dir = self.base_path / project_id / "images"

        if not source_dir.exists():
            raise FileNotFoundError(
                f"Images not found for project {project_id} at {source_dir}",
            )

        destination_path.mkdir(parents=True, exist_ok=True)

        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".tif",
            ".tiff",
            ".JPG",
            ".JPEG",
            ".PNG",
            ".TIF",
            ".TIFF",
        }
        copied_images = []

        for image_file in source_dir.iterdir():
            if image_file.is_file() and image_file.suffix in image_extensions:
                dest_file = destination_path / image_file.name
                shutil.copy2(image_file, dest_file)
                copied_images.append(dest_file)
                logger.debug(f"Copied {image_file} to {dest_file}")

        logger.info(f"Fetched {len(copied_images)} images for project {project_id}")
        return copied_images

    def push_results(self, project_id: str, source_path: Path, run_id: int) -> None:
        """
        Copy processing results to storage.

        Args:
            project_id: Unique identifier for the project
            source_path: Local path containing results to upload
            run_id: Run identifier
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        if not source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        dest_dir = self.base_path / project_id / f"run_{run_id}"
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy all files and directories from source to destination
        if source_path.is_file():
            shutil.copy2(source_path, dest_dir / source_path.name)
            logger.info(
                f"Pushed file {source_path.name} for project {project_id}, run {run_id}",
            )
        elif source_path.is_dir():
            # Copy directory contents
            for item in source_path.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(source_path)
                    dest_file = dest_dir / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)
            logger.info(f"Pushed results for project {project_id}, run {run_id}")

    def list_images(self, project_id: str) -> list[str]:
        """
        List available images for a project.

        Args:
            project_id: Unique identifier for the project

        Returns:
            List of image filenames
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        source_dir = self.base_path / project_id / "images"

        if not source_dir.exists():
            return []

        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".tif",
            ".tiff",
            ".JPG",
            ".JPEG",
            ".PNG",
            ".TIF",
            ".TIFF",
        }
        images = [
            f.name
            for f in source_dir.iterdir()
            if f.is_file() and f.suffix in image_extensions
        ]

        return sorted(images)

    def exists(self, path: str) -> bool:
        """
        Check if a path exists in storage.

        Args:
            path: Path to check (relative to storage root)

        Returns:
            True if path exists, False otherwise
        """
        full_path = self.base_path / path
        return full_path.exists()

    def delete_project(self, project_id: str) -> None:
        """
        Delete all data for a project.

        Args:
            project_id: Unique identifier for the project
        """
        if not self._connected:
            raise ConnectionError("Storage driver not connected")

        project_dir = self.base_path / project_id

        if project_dir.exists():
            shutil.rmtree(project_dir)
            logger.info(f"Deleted project {project_id}")
        else:
            logger.warning(f"Project {project_id} does not exist")
