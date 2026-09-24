"""Unit tests for orthomosaic service, settings, and vegetation indices."""
import json
import subprocess
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import numpy as np

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from services.orthomosaic_generation.app.core.services.orthomosaic_service import (
    OrthomosaicSettings,
    OrthomosaicService,
)


class TestOrthomosaicSettings(unittest.TestCase):
    """Tests for OrthomosaicSettings."""

    def test_defaults(self):
        s = OrthomosaicSettings(_env_file=None)
        self.assertAlmostEqual(s.dsm_resolution, 0.01)
        self.assertEqual(s.dsm_output_type, "max")
        self.assertEqual(s.cog_compression, "LZW")
        self.assertEqual(s.cog_blocksize, 512)
        self.assertAlmostEqual(s.ortho_resolution, 0.01)

    def test_custom(self):
        s = OrthomosaicSettings(dsm_resolution=0.05, cog_compression="ZSTD", _env_file=None)
        self.assertAlmostEqual(s.dsm_resolution, 0.05)
        self.assertEqual(s.cog_compression, "ZSTD")


class TestOrthomosaicService(unittest.TestCase):
    """Tests for OrthomosaicService."""

    def test_init(self):
        svc = OrthomosaicService()
        self.assertIsNotNone(svc.settings)
        self.assertEqual(svc._projects, {})

    def test_get_workspace_not_found(self):
        svc = OrthomosaicService()
        with self.assertRaises(ValueError):
            svc._get_workspace("missing_project")

    def test_get_workspace_exists(self):
        svc = OrthomosaicService()
        svc._projects["p1"] = Path("/tmp/p1")
        ws = svc._get_workspace("p1")
        self.assertEqual(ws, Path("/tmp/p1"))

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="OK", stderr="", returncode=0
        )
        svc = OrthomosaicService()
        result = svc._run_command(["echo", "test"], "test command")
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_command_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "cmd", output="out", stderr="err"
        )
        svc = OrthomosaicService()
        with self.assertRaises(RuntimeError):
            svc._run_command(["false"], "failing command")

    def test_generate_dsm_no_project(self):
        svc = OrthomosaicService()
        with self.assertRaises(ValueError):
            svc.generate_dsm_from_pointcloud("missing")

    @patch("subprocess.run")
    def test_generate_dsm_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        tmpdir = tempfile.mkdtemp()
        try:
            svc = OrthomosaicService()
            svc._projects["p1"] = Path(tmpdir)

            dense_dir = Path(tmpdir) / "dense"
            dense_dir.mkdir()
            (dense_dir / "fused.ply").write_text("fake ply")

            result = svc.generate_dsm_from_pointcloud("p1")
            self.assertEqual(result, Path(tmpdir) / "dsm.tif")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_generate_dsm_no_pointcloud(self):
        tmpdir = tempfile.mkdtemp()
        try:
            svc = OrthomosaicService()
            svc._projects["p1"] = Path(tmpdir)
            with self.assertRaises(FileNotFoundError):
                svc.generate_dsm_from_pointcloud("p1")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_generate_rgb_no_pointcloud(self):
        tmpdir = tempfile.mkdtemp()
        try:
            svc = OrthomosaicService()
            svc._projects["p1"] = Path(tmpdir)
            with self.assertRaises(FileNotFoundError):
                svc.generate_rgb_orthomosaic("p1")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestVegetationIndices(unittest.TestCase):
    """Tests for vegetation_indices module."""

    @patch("services.orthomosaic_generation.app.core.algorithms.vegetation_indices.gdal", None)
    def test_normalised_difference_no_gdal(self):
        from services.orthomosaic_generation.app.core.algorithms.vegetation_indices import (
            _normalised_difference,
        )
        with self.assertRaises(RuntimeError):
            _normalised_difference("a.tif", "b.tif", "out.tif", "TEST")

    @patch("services.orthomosaic_generation.app.core.algorithms.vegetation_indices.gdal")
    def test_normalised_difference_missing_band(self, mock_gdal):
        from services.orthomosaic_generation.app.core.algorithms.vegetation_indices import (
            _normalised_difference,
        )
        mock_gdal.Open.return_value = None
        with self.assertRaises(FileNotFoundError):
            _normalised_difference("a.tif", "b.tif", "out.tif", "TEST")

    @patch("services.orthomosaic_generation.app.core.algorithms.vegetation_indices.gdal")
    def test_normalised_difference_success(self, mock_gdal):
        from services.orthomosaic_generation.app.core.algorithms.vegetation_indices import (
            _normalised_difference,
        )

        nir_data = np.ones((10, 10), dtype=np.float32) * 0.8
        red_data = np.ones((10, 10), dtype=np.float32) * 0.2

        mock_ds_a = MagicMock()
        mock_ds_a.RasterXSize = 10
        mock_ds_a.RasterYSize = 10
        mock_ds_a.GetGeoTransform.return_value = (0, 1, 0, 0, 0, -1)
        mock_ds_a.GetProjection.return_value = "EPSG:4326"
        mock_ds_a.GetRasterBand.return_value.ReadAsArray.return_value = nir_data

        mock_ds_b = MagicMock()
        mock_ds_b.GetRasterBand.return_value.ReadAsArray.return_value = red_data

        mock_gdal.Open.side_effect = [mock_ds_a, mock_ds_b]
        mock_gdal.GA_ReadOnly = 0
        mock_gdal.GDT_Float32 = 6

        mock_driver = MagicMock()
        mock_out_ds = MagicMock()
        mock_driver.Create.return_value = mock_out_ds
        mock_gdal.GetDriverByName.return_value = mock_driver

        _normalised_difference("nir.tif", "red.tif", "ndvi.tif", "NDVI")

        mock_out_ds.GetRasterBand.return_value.WriteArray.assert_called_once()

    @patch("services.orthomosaic_generation.app.core.algorithms.vegetation_indices.gdal")
    def test_compute_vegetation_indices(self, mock_gdal):
        from services.orthomosaic_generation.app.core.algorithms.vegetation_indices import (
            compute_vegetation_indices,
        )

        tmpdir = tempfile.mkdtemp()
        try:
            nir_data = np.ones((5, 5), dtype=np.float32)
            red_data = np.ones((5, 5), dtype=np.float32) * 0.5

            mock_ds = MagicMock()
            mock_ds.RasterXSize = 5
            mock_ds.RasterYSize = 5
            mock_ds.GetGeoTransform.return_value = (0, 1, 0, 0, 0, -1)
            mock_ds.GetProjection.return_value = ""
            mock_ds.GetRasterBand.return_value.ReadAsArray.return_value = nir_data

            mock_gdal.Open.return_value = mock_ds
            mock_gdal.GA_ReadOnly = 0
            mock_gdal.GDT_Float32 = 6
            mock_gdal.GetDriverByName.return_value = MagicMock()

            bands = {"nir": "nir.tif", "red": "red.tif"}
            result = compute_vegetation_indices(bands, tmpdir)
            self.assertIn("ndvi", result)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("subprocess.run")
    def test_convert_index_to_cog(self, mock_run):
        from services.orthomosaic_generation.app.core.algorithms.vegetation_indices import (
            convert_index_to_cog,
        )
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        result = convert_index_to_cog("ndvi.tif", "ndvi_cog.tif")
        self.assertEqual(result, "ndvi_cog.tif")
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_convert_index_to_cog_default_output(self, mock_run):
        from services.orthomosaic_generation.app.core.algorithms.vegetation_indices import (
            convert_index_to_cog,
        )
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        result = convert_index_to_cog("/data/ndvi.tif")
        self.assertTrue(result.endswith("ndvi_cog.tif"))

    def test_compute_indices_no_bands(self):
        from services.orthomosaic_generation.app.core.algorithms.vegetation_indices import (
            compute_vegetation_indices,
        )
        tmpdir = tempfile.mkdtemp()
        try:
            result = compute_vegetation_indices({}, tmpdir)
            self.assertEqual(result, {})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
