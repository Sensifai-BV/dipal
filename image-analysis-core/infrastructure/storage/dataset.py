from __future__ import annotations

import shutil
from pathlib import Path

from .drivers.base import StorageDriver
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class Dataset:
    """
    Dataset manager for PhotoGear processing pipeline.

    Handles fetching images from storage, managing temporary workspace,
    and pushing results back to storage.
    """

    def __init__(
        self,
        project_id: str,
        storage_driver: StorageDriver,
        temp_base_path: Path | None = None,
    ):
        """
        Initialize dataset for a project.

        Args:
            project_id: Unique identifier for the project (dataset_id)
            storage_driver: Storage driver instance (connected)
            temp_base_path: Base path for temporary workspace (defaults to /app/data/temp)
        """
        self.project_id = project_id  # This is the dataset_id
        self.storage_driver = storage_driver
        self.temp_base_path = temp_base_path or Path("/app/data/temp")

        # Shared dataset directory (reused across jobs)
        self.dataset_path = self.temp_base_path / "datasets" / project_id
        self.images_path = self.dataset_path / "images"
        
        # Legacy compatibility - still support project_temp_path
        self.project_temp_path = self.dataset_path

        # Track current run number
        self._current_run_id: int | None = None
        self._current_run_path: Path | None = None

        logger.info(f"Initialized dataset for project {project_id}")

    def initialize_dataset(self) -> None:
        """
        Initialize the dataset workspace.

        Creates the necessary directory structure for the project.
        """
        try:
            self.project_temp_path.mkdir(parents=True, exist_ok=True)
            self.images_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initialized dataset workspace at {self.project_temp_path}")
        except Exception as e:
            logger.error(f"Failed to initialize dataset workspace: {e}")
            raise OSError(f"Failed to initialize dataset workspace: {e}")

    def fetch_images(self) -> Path:
        """
        Fetch images from storage to the local workspace.
        
        Checks if images already exist locally. If so, skips download and reuses them.

        Returns:
            Path to the images directory

        Raises:
            FileNotFoundError: If no images found for the project
            IOError: If fetching fails
        """
        # Check if images already exist locally — either in images/ directly, or in
        # per-band subdirectories (rgb/, green/, nir/, red/, red_edge/, blue/) that
        # calibration creates when it runs organize_by_band(move=True).  Without this
        # second check the band-organised images are invisible and all 595 images get
        # re-downloaded, mixing every band back into images/ and ruining SFM.
        image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}

        if self.images_path.exists():
            existing_images = [f for f in self.images_path.rglob('*')
                                if f.is_file() and f.suffix.lower() in image_extensions]
            if existing_images:
                logger.info(
                    f"Dataset {self.project_id} images already exist locally "
                    f"({len(existing_images)} files in images/). Skipping download."
                )
                return self.images_path

        # Band subdirectories written by calibration's organize_by_band()
        band_dirs = ["rgb", "green", "nir", "red", "red_edge", "blue"]
        for band_dir in band_dirs:
            band_path = self.dataset_path / band_dir
            if band_path.exists():
                band_images = [f for f in band_path.rglob('*')
                                if f.is_file() and f.suffix.lower() in image_extensions]
                if band_images:
                    logger.info(
                        f"Dataset {self.project_id} images already organised into band "
                        f"directories ({len(band_images)} files found in {band_dir}/). "
                        f"Skipping download."
                    )
                    return self.dataset_path
        
        logger.info(f"Fetching images for project {self.project_id}")

        try:
            images = self.storage_driver.fetch_images(
                project_id=self.project_id,
                destination_path=self.images_path,
            )

            logger.info(
                f"Successfully fetched {len(images)} images to {self.images_path}",
            )
            return self.images_path

        except Exception as e:
            logger.error(f"Failed to fetch images: {e}")
            raise

    def fetch_ppk_files(self) -> list[Path]:
        """
        Download PPK/GNSS auxiliary files to the dataset root.

        Calls the storage driver's ``fetch_auxiliary_files()`` which searches
        for ``.nav``, ``.obs``, ``.bin``, and ``.mrk``/``.MRK`` files in both
        the ``images/`` and ``ppk/`` prefixes.  Files are saved directly into
        ``dataset_path`` (the workspace root) so that ``geo_register()`` can
        locate the ``.MRK`` file via ``workspace.glob("*.MRK")``.

        Returns:
            List of paths to downloaded auxiliary files (empty if none found or
            not supported by the current storage driver)
        """
        ppk_extensions = {".nav", ".obs", ".bin", ".mrk", ".MRK"}

        existing = [
            f for f in self.dataset_path.iterdir()
            if f.is_file() and f.suffix.lower() in {ext.lower() for ext in ppk_extensions}
        ] if self.dataset_path.exists() else []

        if existing:
            logger.info(
                f"PPK auxiliary files already present for project {self.project_id} "
                f"({len(existing)} file(s)). Skipping download."
            )
            return existing

        logger.info(f"Fetching PPK auxiliary files for project {self.project_id}")

        try:
            downloaded = self.storage_driver.fetch_auxiliary_files(
                project_id=self.project_id,
                destination_path=self.dataset_path,
            )
            if downloaded:
                logger.info(
                    f"Downloaded {len(downloaded)} PPK auxiliary file(s) "
                    f"to {self.dataset_path}"
                )
            else:
                logger.debug(
                    f"No PPK auxiliary files found for project {self.project_id} "
                    "(geo-registration will use EXIF GPS)"
                )
            return downloaded
        except Exception as e:
            logger.warning(
                f"Failed to fetch PPK auxiliary files for project {self.project_id}: {e} "
                "(non-fatal — pipeline will continue without PPK data)"
            )
            return []

    def create_run(self) -> Path:
        """
        Create a new run directory for processing.

        Automatically determines the next run number based on existing runs.

        Returns:
            Path to the new run directory
        """
        # Find next run number
        run_id = 1
        while True:
            run_path = self.project_temp_path / f"run_{run_id}"
            if not run_path.exists():
                break
            run_id += 1

        # Create the run directory
        run_path.mkdir(parents=True, exist_ok=True)

        self._current_run_id = run_id
        self._current_run_path = run_path

        logger.info(f"Created run directory: {run_path}")
        return run_path

    def get_run_path(self, run_id: int | None = None) -> Path:
        """
        Get path to a specific run directory.

        Args:
            run_id: Run identifier. If None, returns current run path.

        Returns:
            Path to the run directory

        Raises:
            ValueError: If no current run and run_id not provided
        """
        if run_id is None:
            if self._current_run_path is None:
                raise ValueError(
                    "No current run. Call create_run() first or provide run_id.",
                )
            return self._current_run_path

        return self.project_temp_path / f"run_{run_id}"

    def push_results(
        self,
        source_path: Path | None = None,
        run_id: int | None = None,
    ) -> None:
        """
        Push processing results to storage.

        Args:
            source_path: Path to results to upload. Defaults to current run path.
            run_id: Run identifier. Defaults to current run.

        Raises:
            ValueError: If no current run and parameters not provided
            IOError: If upload fails
        """
        if source_path is None:
            if self._current_run_path is None:
                raise ValueError(
                    "No current run. Call create_run() first or provide source_path.",
                )
            source_path = self._current_run_path

        if run_id is None:
            if self._current_run_id is None:
                raise ValueError(
                    "No current run. Call create_run() first or provide run_id.",
                )
            run_id = self._current_run_id

        logger.info(f"Pushing results for project {self.project_id}, run {run_id}")

        try:
            self.storage_driver.push_results(
                project_id=self.project_id,
                source_path=source_path,
                run_id=run_id,
            )
            logger.info(f"Successfully pushed results for run {run_id}")

        except Exception as e:
            logger.error(f"Failed to push results: {e}")
            raise

    def cleanup(self, keep_results: bool = False) -> None:
        """
        Clean up temporary workspace.

        Args:
            keep_results: If True, only removes images. If False, removes entire project temp dir.
        """
        try:
            if keep_results:
                # Only remove images directory
                if self.images_path.exists():
                    shutil.rmtree(self.images_path)
                    logger.info("Cleaned up images directory")
            else:
                # Remove entire project temp directory
                if self.project_temp_path.exists():
                    shutil.rmtree(self.project_temp_path)
                    logger.info(
                        f"Cleaned up project workspace: {self.project_temp_path}",
                    )

        except Exception as e:
            logger.warning(f"Failed to cleanup workspace: {e}")

    def list_images(self) -> list[str]:
        """
        List images available for this project.

        Returns:
            List of image filenames
        """
        return self.storage_driver.list_images(self.project_id)

    def get_images_path(self) -> Path:
        """
        Get the path to the images directory.

        Returns:
            Path to images directory
        """
        return self.images_path

    @property
    def current_run_id(self) -> int | None:
        """
        Get the current run identifier.

        Returns:
            Current run ID or None if no run created
        """
        return self._current_run_id

    @property
    def current_run_path(self) -> Path | None:
        """
        Get the current run path.

        Returns:
            Current run path or None if no run created
        """
        return self._current_run_path
