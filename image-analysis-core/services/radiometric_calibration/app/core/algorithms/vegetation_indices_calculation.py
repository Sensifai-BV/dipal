"""Vegetation index calculation using drone image processors."""
from __future__ import annotations

from ..services.factory import DroneImageProcessorFactory, DroneType
import numpy as np


class VegetationIndicesCalculator:
    """Calculate vegetation indices using a drone-specific image processor."""

    def __init__(self, drone_type: DroneType) -> None:
        """
        Initialise with a drone-specific processor.

        Args:
            drone_type: Type of drone to create processor for
        """
        self.drone_image_processor = DroneImageProcessorFactory.create(
            drone_type=drone_type,
        )

    def calculate_vegetation_indices_from_paths(
        self, red_path: str, nir_path: str
    ) -> "np.ndarray":
        """
        Calculate NDVI from source image paths using the full radiometric pipeline.

        Loads each band via the drone processor (which applies vignetting correction,
        lens distortion correction, and homography alignment), then converts DN values
        to calibrated reflectance before computing NDVI.  This is the correct entry
        point for agronomic applications where accurate reflectance values matter.

        Args:
            red_path: Absolute path to the Red band source image
            nir_path: Absolute path to the NIR band source image

        Returns:
            NDVI array clipped to [-1, 1]
        """
        self.drone_image_processor.load_image(red_path, "Red")
        self.drone_image_processor.load_image(nir_path, "NIR")
        return self.drone_image_processor.calculate_ndvi()

    def calculate_vegetation_indices(
        self, red_band: "np.ndarray", nir_band: "np.ndarray"
    ) -> "np.ndarray":
        """
        Calculate NDVI from already-calibrated reflectance arrays.

        Both inputs must already be calibrated reflectance values (0–1 range).
        For raw DN input use ``calculate_vegetation_indices_from_paths`` instead,
        which applies the full radiometric correction chain before computing NDVI.

        Args:
            red_band: Calibrated Red reflectance array
            nir_band: Calibrated NIR reflectance array

        Returns:
            NDVI array clipped to [-1, 1]
        """
        import numpy as np

        ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-10)
        return np.clip(ndvi, -1.0, 1.0)
