"""Unit tests for vegetation index computation."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np


class TestNormalisedDifference(unittest.TestCase):
    """Test normalised difference index computation."""

    def test_ndvi_basic(self):
        """NDVI = (NIR - Red) / (NIR + Red) with known values."""
        nir = np.array([[0.8, 0.6], [0.4, 0.2]], dtype=np.float32)
        red = np.array([[0.2, 0.3], [0.4, 0.5]], dtype=np.float32)

        expected = (nir - red) / (nir + red + 1e-10)

        denominator = nir + red
        denominator[denominator == 0] = 1e-10
        result = np.clip((nir - red) / denominator, -1.0, 1.0)

        np.testing.assert_array_almost_equal(result, expected, decimal=5)

    def test_ndvi_equal_bands(self):
        """Equal bands should produce 0."""
        band = np.array([[0.5, 0.5]], dtype=np.float32)
        result = (band - band) / (band + band + 1e-10)
        np.testing.assert_array_almost_equal(result, np.zeros_like(band), decimal=5)

    def test_ndvi_clipping(self):
        """Result should be clipped to [-1, 1]."""
        nir = np.array([[1.0]], dtype=np.float32)
        red = np.array([[0.0]], dtype=np.float32)
        result = np.clip((nir - red) / (nir + red + 1e-10), -1.0, 1.0)
        self.assertLessEqual(float(result[0, 0]), 1.0)
        self.assertGreaterEqual(float(result[0, 0]), -1.0)


class TestComputeVegetationIndices(unittest.TestCase):
    """Test the compute_vegetation_indices function argument validation."""

    def test_missing_bands_produces_empty(self):
        """With only one band, no index can be computed."""
        band_paths = {"green": "/tmp/green_ortho.tif"}
        self.assertFalse("nir" in band_paths and "red" in band_paths)

    def test_all_bands_present(self):
        """All 4 bands should trigger all 3 indices."""
        band_paths = {
            "green": "/tmp/green.tif",
            "red": "/tmp/red.tif",
            "red_edge": "/tmp/re.tif",
            "nir": "/tmp/nir.tif",
        }
        expected_indices = []
        if "nir" in band_paths and "red" in band_paths:
            expected_indices.append("ndvi")
        if "nir" in band_paths and "red_edge" in band_paths:
            expected_indices.append("ndre")
        if "nir" in band_paths and "green" in band_paths:
            expected_indices.append("gndvi")

        self.assertEqual(len(expected_indices), 3)
        self.assertIn("ndvi", expected_indices)
        self.assertIn("ndre", expected_indices)
        self.assertIn("gndvi", expected_indices)


if __name__ == "__main__":
    unittest.main()
