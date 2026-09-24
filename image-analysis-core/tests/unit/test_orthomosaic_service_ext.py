"""Extended unit tests for OrthomosaicService — remaining methods."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from services.orthomosaic_generation.app.core.services.orthomosaic_service import (
    OrthomosaicService,
    OrthomosaicSettings,
)


_SETTINGS_PATCH = patch(
    "services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicSettings",
    return_value=OrthomosaicSettings(_env_file=None),
)


def _make_service_with_workspace():
    """Create a service instance + temp workspace for testing."""
    tmpdir = Path(tempfile.mkdtemp())
    ws = tmpdir / "workspace"
    ws.mkdir()
    with _SETTINGS_PATCH:
        svc = OrthomosaicService()
    svc._projects["proj1"] = ws
    return svc, ws, tmpdir


class TestGenerateRGBOrthomosaic(unittest.TestCase):
    """Tests for generate_rgb_orthomosaic."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service_with_workspace()
        (self.ws / "dense").mkdir()
        (self.ws / "dense" / "meshed-poisson.ply").write_text("fake")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    def test_success(self, mock_cmd):
        result = self.svc.generate_rgb_orthomosaic("proj1")
        self.assertEqual(result, self.ws / "orthomosaic_rgb.tif")
        self.assertEqual(mock_cmd.call_count, 4)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    def test_custom_paths(self, mock_cmd):
        pc = self.ws / "custom.ply"
        pc.write_text("fake")
        out = self.ws / "custom_out.tif"
        result = self.svc.generate_rgb_orthomosaic("proj1", input_pointcloud=pc, output_orthomosaic=out)
        self.assertEqual(result, out)

    def test_no_pointcloud_raises(self):
        (self.ws / "dense" / "meshed-poisson.ply").unlink()
        with self.assertRaises(FileNotFoundError):
            self.svc.generate_rgb_orthomosaic("proj1")


class TestGenerateHillshade(unittest.TestCase):
    """Tests for generate_hillshade."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service_with_workspace()
        (self.ws / "dsm_filled.tif").write_text("fake")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    def test_success(self, mock_cmd):
        result = self.svc.generate_hillshade("proj1")
        self.assertEqual(result, self.ws / "hillshade.tif")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("gdaldem", cmd)
        self.assertIn("hillshade", cmd)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    def test_custom_angles(self, mock_cmd):
        self.svc.generate_hillshade("proj1", azimuth=180.0, altitude=60.0)
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("180.0", cmd)
        self.assertIn("60.0", cmd)

    def test_missing_dsm_raises(self):
        (self.ws / "dsm_filled.tif").unlink()
        with self.assertRaises(FileNotFoundError):
            self.svc.generate_hillshade("proj1")


class TestFillDsmHoles(unittest.TestCase):
    """Tests for fill_dsm_holes."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service_with_workspace()
        (self.ws / "dsm.tif").write_text("fake")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    def test_success(self, mock_cmd):
        result = self.svc.fill_dsm_holes("proj1")
        self.assertEqual(result, self.ws / "dsm_filled.tif")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("gdal_fillnodata.py", cmd)

    def test_missing_dsm_raises(self):
        (self.ws / "dsm.tif").unlink()
        with self.assertRaises(FileNotFoundError):
            self.svc.fill_dsm_holes("proj1")


class TestConvertToCog(unittest.TestCase):
    """Tests for convert_to_cog."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service_with_workspace()
        (self.ws / "dsm_filled.tif").write_text("fake")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    def test_success(self, mock_cmd):
        result = self.svc.convert_to_cog("proj1")
        self.assertEqual(result, self.ws / "dsm_filled_cog.tif")
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("gdal_translate", cmd)
        self.assertIn("COG", cmd)

    def test_missing_input_raises(self):
        (self.ws / "dsm_filled.tif").unlink()
        with self.assertRaises(FileNotFoundError):
            self.svc.convert_to_cog("proj1")


class TestAddOverviews(unittest.TestCase):
    """Tests for add_overviews."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service_with_workspace()
        self.input_file = self.ws / "test.tif"
        self.input_file.write_text("fake")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    def test_default_levels(self, mock_cmd):
        result = self.svc.add_overviews(self.input_file)
        self.assertEqual(result, self.input_file)
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("gdaladdo", cmd)
        self.assertIn("2", cmd)
        self.assertIn("16", cmd)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    def test_custom_levels(self, mock_cmd):
        self.svc.add_overviews(self.input_file, levels=[2, 4])
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("2", cmd)
        self.assertIn("4", cmd)
        self.assertNotIn("16", cmd)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.svc.add_overviews(self.ws / "missing.tif")


class TestGenerateMultiResolution(unittest.TestCase):
    """Tests for generate_multi_resolution_outputs."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service_with_workspace()
        (self.ws / "orthomosaic_rgb.tif").write_text("fake")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._read_pixel_size", return_value=0.05)
    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService.add_overviews")
    def test_success(self, mock_ov, mock_px, mock_cmd):
        result = self.svc.generate_multi_resolution_outputs("proj1")
        self.assertEqual(len(result), 3)
        self.assertIn("orthomosaic_rgb_2x", result)
        self.assertIn("orthomosaic_rgb_4x", result)
        self.assertIn("orthomosaic_rgb_8x", result)
        self.assertEqual(mock_cmd.call_count, 3)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._run_command")
    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService._read_pixel_size", return_value=0.1)
    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.OrthomosaicService.add_overviews")
    def test_custom_scales(self, mock_ov, mock_px, mock_cmd):
        result = self.svc.generate_multi_resolution_outputs("proj1", scale_factors=[2])
        self.assertEqual(len(result), 1)

    def test_missing_raster_raises(self):
        (self.ws / "orthomosaic_rgb.tif").unlink()
        with self.assertRaises(FileNotFoundError):
            self.svc.generate_multi_resolution_outputs("proj1")


class TestReadPixelSize(unittest.TestCase):
    """Tests for _read_pixel_size."""

    def setUp(self):
        with _SETTINGS_PATCH:
            self.svc = OrthomosaicService()

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.subprocess.run")
    def test_reads_gsd(self, mock_run):
        gdalinfo = {"geoTransform": [0, 0.05, 0, 0, 0, -0.05]}
        mock_run.return_value = MagicMock(stdout=json.dumps(gdalinfo), returncode=0)
        result = self.svc._read_pixel_size(Path("/tmp/test.tif"))
        self.assertAlmostEqual(result, 0.05)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.subprocess.run")
    def test_default_geotransform(self, mock_run):
        mock_run.return_value = MagicMock(stdout=json.dumps({}), returncode=0)
        result = self.svc._read_pixel_size(Path("/tmp/test.tif"))
        self.assertAlmostEqual(result, 1.0)


class TestGenerateStatistics(unittest.TestCase):
    """Tests for generate_statistics."""

    def setUp(self):
        self.svc, self.ws, self.tmpdir = _make_service_with_workspace()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.subprocess.run")
    def test_with_existing_files(self, mock_run):
        (self.ws / "dsm.tif").write_bytes(b"\x00" * 1024)
        gdalinfo = {"size": [100, 200], "bands": [{}], "geoTransform": [0, 1, 0, 0, 0, -1], "coordinateSystem": {"wkt": "GEOGCS"}}
        mock_run.return_value = MagicMock(stdout=json.dumps(gdalinfo), returncode=0)
        stats = self.svc.generate_statistics("proj1")
        self.assertEqual(stats["project_id"], "proj1")
        self.assertTrue(stats["outputs"]["dsm.tif"]["exists"])
        self.assertEqual(stats["outputs"]["dsm.tif"]["width"], 100)
        self.assertTrue((self.ws / "orthomosaic_statistics.json").exists())

    def test_no_files(self):
        stats = self.svc.generate_statistics("proj1")
        for v in stats["outputs"].values():
            self.assertFalse(v["exists"])

    @patch("services.orthomosaic_generation.app.core.services.orthomosaic_service.subprocess.run")
    def test_gdalinfo_fails_gracefully(self, mock_run):
        (self.ws / "dsm.tif").write_bytes(b"\x00" * 100)
        mock_run.side_effect = Exception("gdalinfo not found")
        stats = self.svc.generate_statistics("proj1")
        self.assertTrue(stats["outputs"]["dsm.tif"]["exists"])
        self.assertNotIn("width", stats["outputs"]["dsm.tif"])


class TestServiceLifecycle(unittest.TestCase):
    """Tests for start, stop, clean."""

    def setUp(self):
        with _SETTINGS_PATCH:
            self.svc = OrthomosaicService()
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_start_success(self):
        project_id = self.svc.start(self.tmpdir)
        self.assertIn("OrthomosaicService", project_id)
        self.assertIn(project_id, self.svc._projects)

    def test_start_relative_path_raises(self):
        with self.assertRaises(ValueError):
            self.svc.start(Path("relative"))

    def test_start_nonexistent_raises(self):
        with self.assertRaises(ValueError):
            self.svc.start(Path("/tmp/nonexistent_xyz_09876"))

    def test_stop_noop(self):
        project_id = self.svc.start(self.tmpdir)
        self.svc.stop(project_id)
        self.assertIn(project_id, self.svc._projects)

    def test_clean_removes_tracking(self):
        project_id = self.svc.start(self.tmpdir)
        self.svc.clean(project_id)
        self.assertNotIn(project_id, self.svc._projects)

    def test_clean_unknown_project(self):
        self.svc.clean("nonexistent")


if __name__ == "__main__":
    unittest.main()
