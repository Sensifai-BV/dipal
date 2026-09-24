"""Unit tests for ColmapService methods."""
import json
import subprocess
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

sys.modules.setdefault("pycolmap", MagicMock())
sys.modules.setdefault("psygnal", MagicMock())

from services.sfm.app.core.services.colmap_service import ColmapService, ColmapSettings


class TestColmapServiceInit(unittest.TestCase):
    """Tests for ColmapService initialization."""

    def test_default_init(self):
        svc = ColmapService()
        self.assertIsInstance(svc.settings, ColmapSettings)
        self.assertEqual(svc._projects, {})

    def test_init_with_settings(self):
        svc = ColmapService({"feature_type": "orb"})
        self.assertEqual(svc.settings.feature_type, "orb")


class TestColmapServiceWorkspace(unittest.TestCase):
    """Tests for workspace management."""

    def test_get_workspace_not_found(self):
        svc = ColmapService()
        with self.assertRaises(ValueError):
            svc._get_workspace("missing")

    def test_get_workspace_found(self):
        svc = ColmapService()
        svc._projects["p1"] = Path("/tmp/p1")
        self.assertEqual(svc._get_workspace("p1"), Path("/tmp/p1"))

    def test_get_database_path(self):
        svc = ColmapService()
        svc._projects["p1"] = Path("/tmp/p1")
        db = svc._get_database_path("p1")
        self.assertTrue(str(db).endswith("database.db"))

    def test_get_image_path_flat(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = ColmapService()
            svc._projects["p1"] = tmpdir
            (tmpdir / "images").mkdir()
            result = svc._get_image_path("p1")
            self.assertEqual(result, tmpdir / "images")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_image_path_prefer_rgb(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = ColmapService()
            svc._projects["p1"] = tmpdir
            (tmpdir / "images").mkdir()
            (tmpdir / "rgb").mkdir()
            (tmpdir / "rgb" / "img.jpg").write_text("fake")
            result = svc._get_image_path("p1")
            self.assertEqual(result, tmpdir / "rgb")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_sparse_path(self):
        svc = ColmapService()
        svc._projects["p1"] = Path("/tmp/p1")
        sparse = svc._get_sparse_path("p1")
        self.assertTrue(str(sparse).endswith("sparse"))

    def test_get_dense_path(self):
        svc = ColmapService()
        svc._projects["p1"] = Path("/tmp/p1")
        dense = svc._get_dense_path("p1")
        self.assertTrue(str(dense).endswith("dense"))


class TestColmapServiceRunCommand(unittest.TestCase):
    """Tests for _run_command."""

    @patch("subprocess.Popen")
    def test_stream_success(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.__iter__ = MagicMock(return_value=iter(["line1\n", "line2\n", ""]))
        mock_process.stdout.readline.side_effect = ["line1\n", "line2\n", ""]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        svc = ColmapService()
        result = svc._run_command(["echo", "test"], Path("/tmp"))
        self.assertIn("line1", result)

    @patch("subprocess.Popen")
    def test_stream_failure(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["output\n", ""]
        mock_process.wait.return_value = None
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        svc = ColmapService()
        with self.assertRaises(RuntimeError):
            svc._run_command(["false"], Path("/tmp"))

    @patch("subprocess.run")
    def test_no_stream_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="output", stderr="")
        svc = ColmapService()
        result = svc._run_command(["echo"], Path("/tmp"), stream_output=False)
        self.assertEqual(result, "output")

    @patch("subprocess.run")
    def test_no_stream_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "cmd", output="out", stderr="err"
        )
        svc = ColmapService()
        with self.assertRaises(RuntimeError):
            svc._run_command(["false"], Path("/tmp"), stream_output=False)

    def test_command_not_found(self):
        svc = ColmapService()
        with self.assertRaises(RuntimeError):
            svc._run_command(
                ["/nonexistent_binary_xyzabc123"],
                Path("/tmp"),
                stream_output=True,
            )


class TestColmapServiceGPU(unittest.TestCase):
    """Tests for _check_gpu_availability."""

    @patch("subprocess.run")
    def test_gpu_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="NVIDIA RTX 3090\n")
        svc = ColmapService()
        self.assertTrue(svc._check_gpu_availability())

    @patch("subprocess.run")
    def test_gpu_not_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        svc = ColmapService()
        self.assertFalse(svc._check_gpu_availability())

    @patch("subprocess.run")
    def test_nvidia_smi_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        svc = ColmapService()
        self.assertFalse(svc._check_gpu_availability())

    @patch("subprocess.run")
    def test_nvidia_smi_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("nvidia-smi", 5)
        svc = ColmapService()
        self.assertFalse(svc._check_gpu_availability())

    @patch("subprocess.run")
    def test_nvidia_smi_exception(self, mock_run):
        mock_run.side_effect = OSError("unexpected")
        svc = ColmapService()
        self.assertFalse(svc._check_gpu_availability())


class TestColmapServiceCreateConfig(unittest.TestCase):
    """Tests for create_processing_config."""

    def test_create_processing_config(self):
        svc = ColmapService()
        svc.create_processing_config()


class TestColmapServiceExtractMetadata(unittest.TestCase):
    """Tests for extract_metadata."""

    def test_extract_metadata(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = ColmapService()
            svc._projects["p1"] = tmpdir
            (tmpdir / "images").mkdir()

            pycolmap_mod = sys.modules["pycolmap"]
            mock_db = MagicMock()
            pycolmap_mod.Database.return_value = mock_db
            pycolmap_mod.CameraMode.AUTO = "auto"

            svc.extract_metadata("p1")
            pycolmap_mod.import_images.assert_called()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestColmapServiceExtractFeatures(unittest.TestCase):
    """Tests for extract_features."""

    @patch("subprocess.Popen")
    def test_extract_features_success(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["feature output\n", ""]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = ColmapService()
            svc._projects["p1"] = tmpdir
            (tmpdir / "images").mkdir()
            run_dir = tmpdir / svc.settings.run_path
            run_dir.mkdir(parents=True, exist_ok=True)

            svc.extract_features("p1")
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            self.assertEqual(cmd[0], "colmap")
            self.assertEqual(cmd[1], "feature_extractor")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestColmapServiceMatchFeatures(unittest.TestCase):
    """Tests for match_features."""

    @patch("subprocess.Popen")
    def test_match_features_sequential(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["matching\n", ""]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = ColmapService()
            svc._projects["p1"] = tmpdir
            run_dir = tmpdir / svc.settings.run_path
            run_dir.mkdir(parents=True, exist_ok=True)

            svc.match_features("p1")
            cmd = mock_popen.call_args[0][0]
            self.assertIn("colmap", cmd[0])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestExtractGpsFromImages(unittest.TestCase):
    """Tests for the _extract_gps_from_images helper."""

    def _make_gps_ifd(self, lat_d, lat_ref, lon_d, lon_ref, alt=None, alt_ref=0):
        """Build a GPS IFD dict keyed by numeric GPSTAGS IDs (as returned by get_ifd)."""
        from PIL.ExifTags import GPSTAGS

        def _tag_id(name):
            return next(k for k, v in GPSTAGS.items() if v == name)

        ifd = {
            _tag_id("GPSLatitude"): lat_d,
            _tag_id("GPSLatitudeRef"): lat_ref,
            _tag_id("GPSLongitude"): lon_d,
            _tag_id("GPSLongitudeRef"): lon_ref,
        }
        if alt is not None:
            ifd[_tag_id("GPSAltitude")] = alt
            ifd[_tag_id("GPSAltitudeRef")] = alt_ref
        return ifd

    def _mock_img_with_gps(self, gps_ifd):
        """Return a context-manager mock whose getexif().get_ifd(0x8825) returns gps_ifd."""
        mock_exif = MagicMock()
        mock_exif.get_ifd.return_value = gps_ifd
        mock_img = MagicMock()
        mock_img.getexif.return_value = mock_exif
        mock_img.__enter__ = lambda s: mock_img
        mock_img.__exit__ = MagicMock(return_value=False)
        return mock_img

    def test_returns_empty_when_no_images(self):
        from services.sfm.app.core.services.colmap_service import _extract_gps_from_images
        tmpdir = Path(tempfile.mkdtemp())
        try:
            result = _extract_gps_from_images(tmpdir)
            self.assertEqual(result, [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_skips_image_without_gps_exif(self):
        from services.sfm.app.core.services.colmap_service import _extract_gps_from_images
        tmpdir = Path(tempfile.mkdtemp())
        try:
            (tmpdir / "img.jpg").write_bytes(b"fake")
            mock_img = self._mock_img_with_gps({})  # empty GPS IFD
            with patch("services.sfm.app.core.services.colmap_service.Image.open", return_value=mock_img):
                result = _extract_gps_from_images(tmpdir)
            self.assertEqual(result, [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_skips_tiff_without_gps_ifd(self):
        """get_ifd returns empty dict for TIFFs without GPS — must be skipped."""
        from services.sfm.app.core.services.colmap_service import _extract_gps_from_images
        tmpdir = Path(tempfile.mkdtemp())
        try:
            (tmpdir / "img.tif").write_bytes(b"fake")
            mock_img = self._mock_img_with_gps({})
            with patch("services.sfm.app.core.services.colmap_service.Image.open", return_value=mock_img):
                result = _extract_gps_from_images(tmpdir)
            self.assertEqual(result, [])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_extracts_lat_lon_alt(self):
        from services.sfm.app.core.services.colmap_service import _extract_gps_from_images
        tmpdir = Path(tempfile.mkdtemp())
        try:
            (tmpdir / "img.tif").write_bytes(b"fake")
            # lat = 51°30'0" N = 51.5, lon = 0°7'30" E = 0.125, alt = 120.0 m
            gps_ifd = self._make_gps_ifd(
                lat_d=(51, 30, 0), lat_ref="N",
                lon_d=(0, 7, 30), lon_ref="E",
                alt=120.0, alt_ref=0,
            )
            with patch("services.sfm.app.core.services.colmap_service.Image.open",
                       return_value=self._mock_img_with_gps(gps_ifd)):
                result = _extract_gps_from_images(tmpdir)

            self.assertEqual(len(result), 1)
            filename, lat, lon, alt = result[0]
            self.assertEqual(filename, "img.tif")
            self.assertAlmostEqual(lat, 51.5, places=4)
            self.assertAlmostEqual(lon, 0.125, places=4)
            self.assertAlmostEqual(alt, 120.0, places=1)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_altitude_defaults_to_zero_when_absent(self):
        from services.sfm.app.core.services.colmap_service import _extract_gps_from_images
        tmpdir = Path(tempfile.mkdtemp())
        try:
            (tmpdir / "img.tif").write_bytes(b"fake")
            gps_ifd = self._make_gps_ifd(
                lat_d=(48, 0, 0), lat_ref="N",
                lon_d=(11, 0, 0), lon_ref="E",
            )
            with patch("services.sfm.app.core.services.colmap_service.Image.open",
                       return_value=self._mock_img_with_gps(gps_ifd)):
                result = _extract_gps_from_images(tmpdir)

            self.assertEqual(len(result), 1)
            _, _, _, alt = result[0]
            self.assertAlmostEqual(alt, 0.0, places=3)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_below_sea_level_altitude_is_negative(self):
        from services.sfm.app.core.services.colmap_service import _extract_gps_from_images
        tmpdir = Path(tempfile.mkdtemp())
        try:
            (tmpdir / "img.tif").write_bytes(b"fake")
            gps_ifd = self._make_gps_ifd(
                lat_d=(31, 0, 0), lat_ref="N",
                lon_d=(35, 0, 0), lon_ref="E",
                alt=50.0, alt_ref=1,  # below sea level
            )
            with patch("services.sfm.app.core.services.colmap_service.Image.open",
                       return_value=self._mock_img_with_gps(gps_ifd)):
                result = _extract_gps_from_images(tmpdir)

            _, _, _, alt = result[0]
            self.assertAlmostEqual(alt, -50.0, places=1)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestGeoRegister(unittest.TestCase):
    """Tests for ColmapService.geo_register."""

    SVC_MOD = "services.sfm.app.core.services.colmap_service"

    def _make_service_with_workspace(self, tmpdir: Path) -> ColmapService:
        svc = ColmapService()
        svc._projects["p1"] = tmpdir
        sparse = tmpdir / svc.settings.run_path / "sparse" / "0"
        sparse.mkdir(parents=True, exist_ok=True)
        return svc

    def test_skips_when_no_gps_exif(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = self._make_service_with_workspace(tmpdir)
            with patch(f"{self.SVC_MOD}._extract_gps_from_images", return_value=[]):
                svc.geo_register("p1")
            geo_ref = tmpdir / svc.settings.run_path / "geo_reference.json"
            self.assertFalse(geo_ref.exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("subprocess.Popen")
    def test_writes_ref_images_txt(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["aligning\n", ""]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = self._make_service_with_workspace(tmpdir)
            entries = [
                ("img1.jpg", 51.5, 0.1, 100.0),
                ("img2.jpg", 51.6, 0.2, 101.0),
            ]
            with patch(f"{self.SVC_MOD}._extract_gps_from_images", return_value=entries):
                svc.geo_register("p1")

            ref_txt = tmpdir / svc.settings.run_path / "ref_images.txt"
            self.assertTrue(ref_txt.exists())
            lines = ref_txt.read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("img1.jpg", lines[0])
            self.assertIn("51.50000000", lines[0])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("subprocess.Popen")
    def test_model_aligner_uses_custom_alignment_with_ref_is_gps(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["done\n", ""]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = self._make_service_with_workspace(tmpdir)
            entries = [("img.jpg", 48.0, 11.0, 500.0)]
            with patch(f"{self.SVC_MOD}._extract_gps_from_images", return_value=entries):
                svc.geo_register("p1")

            cmd = mock_popen.call_args[0][0]
            self.assertIn("model_aligner", cmd)
            self.assertIn("--alignment_type", cmd)
            idx = cmd.index("--alignment_type")
            self.assertEqual(cmd[idx + 1], "custom")
            self.assertIn("--ref_is_gps", cmd)
            idx2 = cmd.index("--ref_is_gps")
            self.assertEqual(cmd[idx2 + 1], "1")
            # --ref_images_path must point to a .txt file, not a directory
            self.assertIn("--ref_images_path", cmd)
            idx3 = cmd.index("--ref_images_path")
            self.assertTrue(cmd[idx3 + 1].endswith(".txt"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("subprocess.Popen")
    def test_geo_reference_json_written_on_success(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["done\n", ""]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = self._make_service_with_workspace(tmpdir)
            entries = [("img.jpg", 48.137, 11.575, 520.0)]
            with patch(f"{self.SVC_MOD}._extract_gps_from_images", return_value=entries):
                svc.geo_register("p1")

            geo_ref = tmpdir / svc.settings.run_path / "geo_reference.json"
            self.assertTrue(geo_ref.exists())
            data = json.loads(geo_ref.read_text())
            self.assertIn("utm_epsg", data)
            self.assertIn("centroid_lat", data)
            self.assertAlmostEqual(data["centroid_lat"], 48.137, places=3)
            self.assertEqual(data["input_srs"], "EPSG:4978")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("subprocess.Popen")
    def test_geo_reference_json_not_written_on_aligner_failure(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["error\n", ""]
        mock_process.wait.return_value = None
        mock_process.returncode = 1  # non-zero → _run_command raises
        mock_popen.return_value = mock_process

        tmpdir = Path(tempfile.mkdtemp())
        try:
            svc = self._make_service_with_workspace(tmpdir)
            entries = [("img.jpg", 48.0, 11.0, 500.0)]
            with patch(f"{self.SVC_MOD}._extract_gps_from_images", return_value=entries):
                svc.geo_register("p1")  # must NOT raise

            geo_ref = tmpdir / svc.settings.run_path / "geo_reference.json"
            self.assertFalse(geo_ref.exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
