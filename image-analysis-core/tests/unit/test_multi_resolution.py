"""Unit tests for multi-resolution output generation."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from services.orthomosaic_generation.app.core.services.orthomosaic_service import (
    OrthomosaicService,
)


class TestGenerateMultiResolutionOutputs(unittest.TestCase):
    """Test multi-resolution output generation from OrthomosaicService."""

    def setUp(self):
        """Set up service with mocked workspace."""
        self.service = OrthomosaicService()
        self.project_id = "test_project_abc123"

    @patch.object(OrthomosaicService, "_read_pixel_size", return_value=0.05)
    @patch.object(OrthomosaicService, "add_overviews")
    @patch.object(OrthomosaicService, "_run_command")
    def test_default_scale_factors(
        self, mock_run, mock_overviews, mock_pixel_size
    ):
        """Default scale factors should be [2, 4, 8]."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            ortho = workspace / "orthomosaic_rgb.tif"
            ortho.write_bytes(b"fake-geotiff")

            self.service._projects[self.project_id] = workspace

            products = self.service.generate_multi_resolution_outputs(
                self.project_id
            )

            self.assertIn("orthomosaic_rgb_2x", products)
            self.assertIn("orthomosaic_rgb_4x", products)
            self.assertIn("orthomosaic_rgb_8x", products)
            self.assertEqual(len(products), 3)

    @patch.object(OrthomosaicService, "_read_pixel_size", return_value=0.05)
    @patch.object(OrthomosaicService, "add_overviews")
    @patch.object(OrthomosaicService, "_run_command")
    def test_custom_scale_factors(
        self, mock_run, mock_overviews, mock_pixel_size
    ):
        """Custom scale factors should produce matching outputs."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            ortho = workspace / "orthomosaic_rgb.tif"
            ortho.write_bytes(b"fake-geotiff")

            self.service._projects[self.project_id] = workspace

            products = self.service.generate_multi_resolution_outputs(
                self.project_id, scale_factors=[2, 16]
            )

            self.assertIn("orthomosaic_rgb_2x", products)
            self.assertIn("orthomosaic_rgb_16x", products)
            self.assertEqual(len(products), 2)

    @patch.object(OrthomosaicService, "_read_pixel_size", return_value=0.03)
    @patch.object(OrthomosaicService, "add_overviews")
    @patch.object(OrthomosaicService, "_run_command")
    def test_gdal_translate_called_per_factor(
        self, mock_run, mock_overviews, mock_pixel_size
    ):
        """gdal_translate should be called once per scale factor."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            ortho = workspace / "orthomosaic_rgb.tif"
            ortho.write_bytes(b"fake-geotiff")

            self.service._projects[self.project_id] = workspace

            self.service.generate_multi_resolution_outputs(self.project_id)

            self.assertEqual(mock_run.call_count, 3)
            descriptions = [c.args[1] for c in mock_run.call_args_list]
            self.assertTrue(any("2×" in d for d in descriptions))
            self.assertTrue(any("4×" in d for d in descriptions))
            self.assertTrue(any("8×" in d for d in descriptions))

    @patch.object(OrthomosaicService, "_read_pixel_size", return_value=0.05)
    @patch.object(OrthomosaicService, "add_overviews")
    @patch.object(OrthomosaicService, "_run_command")
    def test_overviews_added_to_native(
        self, mock_run, mock_overviews, mock_pixel_size
    ):
        """add_overviews should be called on the native orthomosaic."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            ortho = workspace / "orthomosaic_rgb.tif"
            ortho.write_bytes(b"fake-geotiff")

            self.service._projects[self.project_id] = workspace

            self.service.generate_multi_resolution_outputs(self.project_id)

            mock_overviews.assert_called_once_with(ortho)

    def test_missing_input_raises(self):
        """Missing input raster should raise FileNotFoundError."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            self.service._projects[self.project_id] = workspace

            with self.assertRaises(FileNotFoundError):
                self.service.generate_multi_resolution_outputs(self.project_id)


class TestReadPixelSize(unittest.TestCase):
    """Test GSD reading from GeoTIFF metadata."""

    @patch("subprocess.run")
    def test_reads_geotransform(self, mock_run):
        """Should extract pixel size from geoTransform[1]."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {"geoTransform": [500000.0, 0.05, 0.0, 6000000.0, 0.0, -0.05]}
            )
        )
        result = OrthomosaicService._read_pixel_size(
            OrthomosaicService(), Path("/fake/raster.tif")
        )
        self.assertAlmostEqual(result, 0.05)

    @patch("subprocess.run")
    def test_negative_pixel_size(self, mock_run):
        """Should return absolute value even if geoTransform[1] is negative."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {"geoTransform": [0, -0.1, 0, 0, 0, 0.1]}
            )
        )
        result = OrthomosaicService._read_pixel_size(
            OrthomosaicService(), Path("/fake/raster.tif")
        )
        self.assertAlmostEqual(result, 0.1)


if __name__ == "__main__":
    unittest.main()
