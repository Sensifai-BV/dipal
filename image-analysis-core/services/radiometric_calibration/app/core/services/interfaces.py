"""Interfaces for drone image processors and calibration results."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class CalibrationMetadata:
    """Metadata needed for radiometric calibration of a single image."""

    band_name: str
    sensor_gain: float = 1.0
    exposure_time_us: float = 1000.0
    black_level: float = 3200.0
    sensor_gain_adjustment: float = 1.0
    irradiance: float = 1.0
    # The DLS Irradiance reading is a raw sensor count captured with its own
    # exposure and gain.  To use it as a normalisation factor it must be divided
    # by (irradiance_exposure_time * irradiance_gain) so it is on the same
    # per-unit basis as the camera signal.  Defaults of 1.0 leave irradiance
    # unchanged for sensors that do not report these fields.
    irradiance_exposure_time: float = 1.0
    irradiance_gain: float = 1.0
    bit_depth: int = 16
    vignetting_center_x: float | None = None
    vignetting_center_y: float | None = None
    vignetting_coefficients: list[float] = field(default_factory=list)
    dewarp_params: list[float] = field(default_factory=list)
    homography_matrix: list[float] = field(default_factory=list)
    focal_length: float | None = None
    image_width: int = 0
    image_height: int = 0
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CalibrationResult:
    """Result of processing a single image or band."""

    band_name: str
    input_path: Path
    output_path: Path
    corrected_image: np.ndarray | None = None
    reflectance_image: np.ndarray | None = None
    metadata: CalibrationMetadata | None = None
    success: bool = True
    error: str | None = None


@dataclass
class DatasetCalibrationResult:
    """Aggregated result of calibrating an entire dataset."""

    dataset_id: str
    job_id: str
    band_results: dict[str, list[CalibrationResult]] = field(default_factory=dict)
    vegetation_indices: dict[str, Path] = field(default_factory=dict)
    total_processed: int = 0
    total_failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if processing completed with no failures."""
        return self.total_failed == 0

    @property
    def partial_success(self) -> bool:
        """True if at least some images were processed."""
        return self.total_processed > 0


class IDroneImageProcessor(ABC):
    """Interface for drone-specific image processors."""

    @abstractmethod
    def load_image(self, image_path: str | Path, band_name: str) -> None:
        """
        Load an image and extract its metadata.

        Args:
            image_path: Path to the image file
            band_name: Spectral band name
        """

    @abstractmethod
    def extract_calibration_metadata(
        self, image_path: str | Path
    ) -> CalibrationMetadata:
        """
        Extract calibration metadata from an image without loading pixel data.

        Args:
            image_path: Path to the image file

        Returns:
            CalibrationMetadata with vendor-specific values parsed
        """

    @abstractmethod
    def process_all_steps(self, band_name: str) -> np.ndarray:
        """
        Apply all correction steps to a loaded band.

        Args:
            band_name: Band to process

        Returns:
            Fully corrected image array
        """

    @abstractmethod
    def calculate_reflectance(self, band_name: str) -> np.ndarray:
        """
        Calculate calibrated reflectance for a band.

        Args:
            band_name: Band name

        Returns:
            Reflectance array (0-1 range)
        """

    @abstractmethod
    def calculate_ndvi(self) -> np.ndarray:
        """
        Calculate NDVI from NIR and Red bands.

        Returns:
            NDVI array with values between -1 and 1
        """

    @abstractmethod
    def calculate_vegetation_indices(self) -> dict[str, np.ndarray]:
        """
        Calculate all supported vegetation indices.

        Returns:
            Dictionary mapping index name to array (e.g., ndvi, ndre, gndvi)
        """

    @abstractmethod
    def get_supported_bands(self) -> list[str]:
        """
        Return the list of band names this processor supports.

        Returns:
            List of band name strings
        """

    @abstractmethod
    def get_corrected_image(self, band_name: str) -> np.ndarray | None:
        """
        Return the corrected image for a band if available.

        Args:
            band_name: Band name

        Returns:
            Corrected image array or None
        """
