"""Unit tests for multispectral orthorectification algorithms."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import numpy as np

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

mock_gdal = MagicMock()
mock_osr = MagicMock()
sys.modules.setdefault("osgeo", MagicMock())
sys.modules.setdefault("osgeo.gdal", mock_gdal)
sys.modules.setdefault("osgeo.osr", mock_osr)

from services.orthomosaic_generation.app.core.algorithms.ms_orthorectification import (
    orthorectify_bands,
    stack_bands,
    _median_composite_band,
    _warp_band_images,
    _phase_correlation_shift,
    _capture_key,
    _assign_flight_strips,
    _compute_shared_strip_gains,
    _warp_reflectance_image,
    _build_original_image_map,
    _extract_gps_from_image,
    _dms_to_decimal,
    _read_dsm_metadata,
    _run_cmd,
    SPECTRAL_BANDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_dsm_info():
    return {
        "width": 100,
        "height": 100,
        "geotransform": (500000.0, 0.1, 0.0, 5000000.0, 0.0, -0.1),
        "projection": "PROJCS[UTM]",
    }


# ---------------------------------------------------------------------------
# _run_cmd
# ---------------------------------------------------------------------------

class TestRunCmd(unittest.TestCase):
    """Tests for _run_cmd helper."""

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        _run_cmd(["echo", "hi"], "test")
        mock_run.assert_called_once()

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.subprocess.run")
    def test_failure(self, mock_run):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "cmd", stderr="fail")
        with self.assertRaises(CalledProcessError):
            _run_cmd(["bad"], "test")


# ---------------------------------------------------------------------------
# _read_dsm_metadata
# ---------------------------------------------------------------------------

class TestReadDsmMetadata(unittest.TestCase):

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    def test_success(self, mg):
        ds = MagicMock()
        ds.RasterXSize = 100
        ds.RasterYSize = 200
        ds.GetGeoTransform.return_value = (0, 1, 0, 0, 0, -1)
        ds.GetProjection.return_value = "EPSG:4326"
        mg.Open.return_value = ds
        result = _read_dsm_metadata(Path("/tmp/dsm.tif"))
        self.assertEqual(result["width"], 100)
        self.assertEqual(result["height"], 200)
        self.assertEqual(result["geotransform"], (0, 1, 0, 0, 0, -1))

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    def test_file_not_found(self, mg):
        mg.Open.return_value = None
        result = _read_dsm_metadata(Path("/tmp/missing.tif"))
        self.assertIsNone(result)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    def test_empty_projection_returns_none(self, mg):
        """DSM with no CRS (empty projection string) returns None with an error log."""
        ds = MagicMock()
        ds.RasterXSize = 100
        ds.RasterYSize = 100
        ds.GetGeoTransform.return_value = (0, 1, 0, 0, 0, -1)
        ds.GetProjection.return_value = ""  # ← no CRS written to DSM
        mg.Open.return_value = ds

        result = _read_dsm_metadata(Path("/tmp/dsm_no_crs.tif"))

        self.assertIsNone(result, "Expected None when DSM projection is empty")

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    def test_none_projection_returns_none(self, mg):
        """DSM where GetProjection() returns None also returns None."""
        ds = MagicMock()
        ds.RasterXSize = 50
        ds.RasterYSize = 50
        ds.GetGeoTransform.return_value = (0, 1, 0, 0, 0, -1)
        ds.GetProjection.return_value = None
        mg.Open.return_value = ds

        result = _read_dsm_metadata(Path("/tmp/dsm_null_crs.tif"))

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# stack_bands
# ---------------------------------------------------------------------------

class TestStackBands(unittest.TestCase):

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._run_cmd")
    def test_stack_success(self, mock_cmd):
        paths = {"green": "/tmp/g.tif", "red": "/tmp/r.tif", "nir": "/tmp/n.tif"}
        result = stack_bands(paths, "/tmp/stacked.tif")
        self.assertEqual(result, "/tmp/stacked.tif")
        mock_cmd.assert_called_once()
        cmd = mock_cmd.call_args[0][0]
        self.assertIn("gdal_merge.py", cmd)

    def test_stack_no_bands(self):
        with self.assertRaises(ValueError):
            stack_bands({}, "/tmp/out.tif")

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._run_cmd")
    def test_stack_preserves_order(self, mock_cmd):
        paths = {"nir": "/tmp/n.tif", "green": "/tmp/g.tif", "red": "/tmp/r.tif", "red_edge": "/tmp/re.tif"}
        stack_bands(paths, "/tmp/out.tif")
        cmd = mock_cmd.call_args[0][0]
        ordered_paths = cmd[cmd.index("-ot") + 2:]
        self.assertEqual(ordered_paths, ["/tmp/g.tif", "/tmp/r.tif", "/tmp/re.tif", "/tmp/n.tif"])


# ---------------------------------------------------------------------------
# _dms_to_decimal
# ---------------------------------------------------------------------------

class TestDmsToDecimal(unittest.TestCase):

    def test_north(self):
        self.assertAlmostEqual(_dms_to_decimal((51, 30, 0), "N"), 51.5, places=4)

    def test_south(self):
        self.assertAlmostEqual(_dms_to_decimal((51, 30, 0), "S"), -51.5, places=4)

    def test_east(self):
        self.assertAlmostEqual(_dms_to_decimal((0, 0, 3600), "E"), 1.0, places=6)

    def test_west(self):
        self.assertAlmostEqual(_dms_to_decimal((1, 0, 0), "W"), -1.0, places=6)

    def test_zero(self):
        self.assertAlmostEqual(_dms_to_decimal((0, 0, 0), "N"), 0.0, places=6)


# ---------------------------------------------------------------------------
# _extract_gps_from_image
# ---------------------------------------------------------------------------

class TestExtractGpsFromImage(unittest.TestCase):

    def _make_mock_exif(self, lat_dms, lat_ref, lon_dms, lon_ref, alt=100.0, alt_ref=0):
        gps_ifd = {
            1: lat_ref,    # GPSLatitudeRef
            2: lat_dms,    # GPSLatitude
            3: lon_ref,    # GPSLongitudeRef
            4: lon_dms,    # GPSLongitude
            5: alt_ref,    # GPSAltitudeRef
            6: alt,        # GPSAltitude
        }
        mock_exif = MagicMock()
        mock_exif.get_ifd.return_value = {
            "GPSLatitudeRef": lat_ref,
            "GPSLatitude": lat_dms,
            "GPSLongitudeRef": lon_ref,
            "GPSLongitude": lon_dms,
            "GPSAltitudeRef": alt_ref,
            "GPSAltitude": alt,
        }
        return mock_exif

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._PILImage")
    def test_extracts_gps(self, mock_pil):
        mock_img = MagicMock()
        mock_exif = self._make_mock_exif((51, 28, 0), "N", (7, 0, 0), "E", alt=100.0)
        mock_img.getexif.return_value = mock_exif
        mock_pil.open.return_value.__enter__.return_value = mock_img

        result = _extract_gps_from_image(Path("/tmp/img.tif"))

        self.assertIsNotNone(result)
        lat, lon, alt = result
        self.assertAlmostEqual(lat, 51 + 28 / 60, places=2)
        self.assertAlmostEqual(lon, 7.0, places=1)
        self.assertAlmostEqual(alt, 100.0)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._PILImage")
    def test_missing_gps_ifd_returns_none(self, mock_pil):
        mock_img = MagicMock()
        mock_exif = MagicMock()
        mock_exif.get_ifd.return_value = {}
        mock_img.getexif.return_value = mock_exif
        mock_pil.open.return_value.__enter__.return_value = mock_img

        result = _extract_gps_from_image(Path("/tmp/img.tif"))
        self.assertIsNone(result)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._PILImage")
    def test_no_exif_returns_none(self, mock_pil):
        mock_img = MagicMock()
        mock_img.getexif.return_value = None
        mock_pil.open.return_value.__enter__.return_value = mock_img

        result = _extract_gps_from_image(Path("/tmp/img.tif"))
        self.assertIsNone(result)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._PILImage")
    def test_exception_returns_none(self, mock_pil):
        mock_pil.open.side_effect = OSError("bad file")
        result = _extract_gps_from_image(Path("/tmp/img.tif"))
        self.assertIsNone(result)

    def test_returns_none_when_pil_unavailable(self):
        with patch(
            "services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._PILImage",
            None,
        ):
            result = _extract_gps_from_image(Path("/tmp/img.tif"))
        self.assertIsNone(result)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._PILImage")
    def test_below_sea_level_altitude(self, mock_pil):
        """GPSAltitudeRef=1 means below sea level → negative altitude."""
        mock_img = MagicMock()
        mock_exif = self._make_mock_exif((10, 0, 0), "N", (10, 0, 0), "E", alt=50.0, alt_ref=1)
        mock_img.getexif.return_value = mock_exif
        mock_pil.open.return_value.__enter__.return_value = mock_img

        lat, lon, alt = _extract_gps_from_image(Path("/tmp/img.tif"))
        self.assertLess(alt, 0)


# ---------------------------------------------------------------------------
# _build_original_image_map
# ---------------------------------------------------------------------------

class TestBuildOriginalImageMap(unittest.TestCase):

    def _manifest(self, band_name, paths):
        return {
            "bands": {
                band_name: {
                    "images": [{"file_path": p} for p in paths],
                }
            }
        }

    def test_builds_stem_map(self):
        manifest = self._manifest("red", ["/data/img_001.tif", "/data/img_002.tif"])
        result = _build_original_image_map(manifest, "red")
        self.assertEqual(result["img_001"], "/data/img_001.tif")
        self.assertEqual(result["img_002"], "/data/img_002.tif")

    def test_returns_empty_for_none_manifest(self):
        result = _build_original_image_map(None, "red")
        self.assertEqual(result, {})

    def test_returns_empty_for_non_dict_manifest(self):
        result = _build_original_image_map("invalid", "red")
        self.assertEqual(result, {})

    def test_returns_empty_for_missing_band(self):
        manifest = self._manifest("green", ["/data/img.tif"])
        result = _build_original_image_map(manifest, "red")
        self.assertEqual(result, {})

    def test_skips_empty_file_paths(self):
        manifest = {"bands": {"nir": {"images": [{"file_path": ""}]}}}
        result = _build_original_image_map(manifest, "nir")
        self.assertEqual(result, {})

    def test_handles_non_dict_images(self):
        """file_path may come from a Pydantic model (hasattr style)."""
        img = MagicMock()
        img.file_path = "/data/img_abc.tif"
        manifest = {"bands": {"nir": {"images": [img]}}}
        result = _build_original_image_map(manifest, "nir")
        self.assertEqual(result["img_abc"], "/data/img_abc.tif")


# ---------------------------------------------------------------------------
# _median_composite_band (legacy fallback)
# ---------------------------------------------------------------------------

class TestMedianCompositeBand(unittest.TestCase):

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    def test_composite_creates_output(self, mg):
        arr = np.ones((10, 10), dtype=np.float32)
        mock_band = MagicMock()
        mock_band.ReadAsArray.return_value = arr
        mock_ds = MagicMock()
        mock_ds.GetRasterBand.return_value = mock_band
        mg.Open.return_value = mock_ds

        mock_out_band = MagicMock()
        mock_out_ds = MagicMock()
        mock_out_ds.GetRasterBand.return_value = mock_out_band
        mock_driver = MagicMock()
        mock_driver.Create.return_value = mock_out_ds
        mg.GetDriverByName.return_value = mock_driver
        mg.GDT_Float32 = 6

        _median_composite_band([Path("/tmp/a.tif")], Path("/tmp/out.tif"), _sample_dsm_info())

        mock_out_band.WriteArray.assert_called_once()
        mock_out_ds.FlushCache.assert_called_once()

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    def test_composite_no_valid_images(self, mg):
        mg.Open.return_value = None
        with self.assertRaises(RuntimeError):
            _median_composite_band([Path("/tmp/bad.tif")], Path("/tmp/out.tif"), _sample_dsm_info())


# ---------------------------------------------------------------------------
# _warp_reflectance_image
# ---------------------------------------------------------------------------

class TestWarpReflectanceImage(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dsm_info = _sample_dsm_info()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.subprocess.run")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._extract_gps_from_image")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.osr")
    def test_returns_true_on_success(self, mock_osr, mock_gdal, mock_gps, mock_run):
        mock_gps.return_value = (51.5, 7.0, 80.0)

        # Fake source dataset
        src_ds = MagicMock()
        src_ds.RasterXSize = 640
        src_ds.RasterYSize = 512
        arr = np.zeros((512, 640), dtype=np.float32)
        src_ds.GetRasterBand.return_value.ReadAsArray.return_value = arr
        mock_gdal.Open.return_value = src_ds

        # Fake output dataset
        geo_ds = MagicMock()
        mock_gdal.GetDriverByName.return_value.Create.return_value = geo_ds

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        refl = self.tmp / "img_reflectance.tif"
        refl.write_text("fake")
        warped_out = self.tmp / "warped.tif"

        result = _warp_reflectance_image(refl, "/orig/img.tif", self.dsm_info, warped_out, self.tmp)

        self.assertTrue(result)
        mock_gps.assert_called_once_with(Path("/orig/img.tif"))
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("gdalwarp", cmd)
        self.assertIn("EPSG:4326", cmd)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._extract_gps_from_image")
    def test_returns_false_when_no_gps(self, mock_gps):
        mock_gps.return_value = None
        refl = self.tmp / "img.tif"
        refl.write_text("fake")
        result = _warp_reflectance_image(refl, "/orig/img.tif", self.dsm_info, self.tmp / "out.tif", self.tmp)
        self.assertFalse(result)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.subprocess.run")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._extract_gps_from_image")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.osr")
    def test_returns_false_on_gdalwarp_failure(self, mock_osr, mock_gdal, mock_gps, mock_run):
        mock_gps.return_value = (51.5, 7.0, 80.0)

        src_ds = MagicMock()
        src_ds.RasterXSize = 100
        src_ds.RasterYSize = 100
        src_ds.GetRasterBand.return_value.ReadAsArray.return_value = np.zeros((100, 100), dtype=np.float32)
        mock_gdal.Open.return_value = src_ds
        mock_gdal.GetDriverByName.return_value.Create.return_value = MagicMock()
        mock_run.return_value = MagicMock(returncode=1, stderr="projection error")

        refl = self.tmp / "img.tif"
        refl.write_text("fake")
        result = _warp_reflectance_image(refl, "/orig/img.tif", self.dsm_info, self.tmp / "out.tif", self.tmp)
        self.assertFalse(result)

    def test_returns_false_when_gdal_unavailable(self):
        with patch(
            "services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal",
            None,
        ):
            result = _warp_reflectance_image(
                self.tmp / "x.tif", "/orig/x.tif", self.dsm_info, self.tmp / "out.tif", self.tmp
            )
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Cross-band shared strip gains (the NDVI banding fix)
# ---------------------------------------------------------------------------

class TestSharedStripGains(unittest.TestCase):

    def test_single_image_no_correction(self):
        gains = _compute_shared_strip_gains(["a"], np.array([0.0]), np.array([0.0]), {})
        self.assertEqual(gains, {"a": 1.0})

    def test_strip_assignment_separates_two_strips(self):
        # Two parallel E-W strips: along-track is longitude (5 images each,
        # ~55 m long) and the two strips are offset ~20 m in latitude — so the
        # along-track extent exceeds the strip spacing, as in a real survey.
        lon_steps = np.array([0.0, 0.0001, 0.0002, 0.0003, 0.0004])
        jit = 2e-6  # ~0.2 m cross-track GPS jitter
        lats = np.concatenate([
            np.full(5, 0.0) + jit * np.array([0, 1, -1, 1, -1]),
            np.full(5, 0.00018) + jit * np.array([0, 1, -1, 1, -1]),
        ])
        lons = np.concatenate([lon_steps, lon_steps])
        strip_id, n_strips = _assign_flight_strips(lats, lons)
        self.assertEqual(n_strips, 2)
        self.assertEqual(len(set(strip_id[:5])), 1)
        self.assertEqual(len(set(strip_id[5:])), 1)
        self.assertNotEqual(strip_id[0], strip_id[5])

    def test_gain_is_identical_across_bands_for_same_image(self):
        """The core invariant: a given image gets ONE gain shared by all bands."""
        stems = [f"s{i}" for i in range(10)]
        lon_steps = np.array([0.0, 0.0001, 0.0002, 0.0003, 0.0004])
        jit = 2e-6
        lats = np.concatenate([
            np.full(5, 0.0) + jit * np.array([0, 1, -1, 1, -1]),
            np.full(5, 0.00018) + jit * np.array([0, 1, -1, 1, -1]),
        ])
        lons = np.concatenate([lon_steps, lon_steps])
        # Strip 1 (s0-s4) is dim, strip 2 (s5-s9) is bright — in BOTH bands, but
        # the two bands have very different absolute scales (NIR >> Red).
        band_means = {
            "red": {s: (0.10 if i < 5 else 0.20) for i, s in enumerate(stems)},
            "nir": {s: (2.00 if i < 5 else 4.00) for i, s in enumerate(stems)},
        }
        gains = _compute_shared_strip_gains(stems, lats, lons, band_means)
        # Same gain for every image within a strip.
        self.assertAlmostEqual(gains["s0"], gains["s1"])
        self.assertAlmostEqual(gains["s0"], gains["s4"])
        # The dim strip is scaled UP relative to the bright strip.
        self.assertGreater(gains["s0"], gains["s5"])
        # Crucially: gain depends only on stem, not band — so applying it to red
        # and nir preserves nir/red and therefore NDVI.

    def test_no_strips_returns_unity(self):
        # All images on one line → single strip → no correction.
        lats = np.zeros(4)
        lons = np.array([0.0, 0.0001, 0.0002, 0.0003])
        gains = _compute_shared_strip_gains(
            ["a", "b", "c", "d"], lats, lons,
            {"red": {"a": 1, "b": 1, "c": 1, "d": 1}},
        )
        self.assertTrue(all(abs(v - 1.0) < 1e-9 for v in gains.values()))


# ---------------------------------------------------------------------------
# _warp_band_images / _blend_band_with_gains
# ---------------------------------------------------------------------------

class TestWarpBandImages(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dsm_info = _sample_dsm_info()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._extract_gps_from_image")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification.gdal")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._warp_reflectance_image")
    def test_records_stem_and_gps(self, mock_warp, mock_gdal, mock_gps):
        img1 = self.tmp / "img_001_reflectance.tif"
        img1.write_text("fake")
        orig_map = {"img_001": "/orig/img_001.tif"}
        mock_gps.return_value = (41.1, 23.4, 90.0)

        def fake_warp(refl, orig, dsm, out, tmp, gps=None, reference_refl_path=None):
            out.write_text("warped")
            return True
        mock_warp.side_effect = fake_warp

        # gdal.Open returns a dataset whose band reads a positive-mean array.
        ds = MagicMock()
        ds.GetRasterBand.return_value.ReadAsArray.return_value = np.full((4, 4), 0.3, np.float32)
        mock_gdal.Open.return_value = ds

        items = _warp_band_images([img1], self.dsm_info, orig_map, self.tmp)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["stem"], "img_001")
        self.assertAlmostEqual(items[0]["lat"], 41.1)
        self.assertGreater(items[0]["mean"], 0)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._warp_reflectance_image")
    def test_returns_empty_when_not_in_map(self, mock_warp):
        img = self.tmp / "img_999_reflectance.tif"
        img.write_text("fake")
        items = _warp_band_images([img], self.dsm_info, {}, self.tmp)
        self.assertEqual(items, [])
        mock_warp.assert_not_called()


# ---------------------------------------------------------------------------
# Inter-band registration (phase correlation)
# ---------------------------------------------------------------------------

class TestPhaseCorrelationShift(unittest.TestCase):

    def test_recovers_known_shift(self):
        rng = np.random.default_rng(0)
        ref = rng.standard_normal((64, 64)).astype(np.float32)
        # shift ref by (dy=5, dx=-3) to make the moving image
        mov = np.roll(np.roll(ref, 5, axis=0), -3, axis=1)
        dy, dx = _phase_correlation_shift(ref, mov)
        # shifting mov by (dy,dx) should bring it back onto ref → (-5, +3)
        self.assertEqual((dy, dx), (-5, 3))

    def test_zero_shift_for_identical(self):
        rng = np.random.default_rng(1)
        a = rng.standard_normal((32, 32)).astype(np.float32)
        self.assertEqual(_phase_correlation_shift(a, a), (0, 0))

    def test_rejects_large_shift(self):
        rng = np.random.default_rng(2)
        ref = rng.standard_normal((64, 64)).astype(np.float32)
        mov = np.roll(ref, 30, axis=0)  # 30 > default max_shift 40? no; use small cap
        dy, dx = _phase_correlation_shift(ref, mov, max_shift_px=10)
        self.assertEqual((dy, dx), (0, 0))  # 30 px exceeds cap → rejected

    def test_shape_mismatch_returns_zero(self):
        self.assertEqual(
            _phase_correlation_shift(np.zeros((10, 10)), np.zeros((8, 8))),
            (0, 0),
        )


class TestCaptureKey(unittest.TestCase):

    def test_extracts_dji_sequence(self):
        p = Path("DJI_20240719091257_0001_MS_NIR_reflectance.tif")
        self.assertEqual(_capture_key(p), "0001")

    def test_falls_back_to_stem(self):
        p = Path("weird_name.tif")
        self.assertEqual(_capture_key(p), "weird_name")


# ---------------------------------------------------------------------------
# orthorectify_bands (integration of routing logic)
# ---------------------------------------------------------------------------

class TestOrthorectifyBands(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.cal_root = self.tmpdir / "calibration"
        self.output_dir = self.tmpdir / "output"
        self.dsm = self.tmpdir / "dsm.tif"
        self.dsm.write_text("fake")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._median_composite_band")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._read_dsm_metadata")
    def test_skips_missing_bands(self, mock_read, mock_comp):
        mock_read.return_value = _sample_dsm_info()
        result = orthorectify_bands(str(self.cal_root), "/tmp/sfm", str(self.dsm), str(self.output_dir))
        self.assertEqual(result, {})
        mock_comp.assert_not_called()

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._read_dsm_metadata")
    def test_raises_when_no_manifest(self, mock_read):
        """Without band_manifest, GPS-guided warping is impossible → RuntimeError."""
        mock_read.return_value = _sample_dsm_info()
        green_dir = self.cal_root / "green"
        green_dir.mkdir(parents=True)
        (green_dir / "img_reflectance.tif").write_text("fake")

        with self.assertRaises(RuntimeError):
            orthorectify_bands(
                str(self.cal_root), "/tmp/sfm", str(self.dsm), str(self.output_dir),
                band_manifest=None,
            )

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._blend_band_with_gains")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._compute_shared_strip_gains")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._warp_band_images")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._read_dsm_metadata")
    def test_uses_gps_composite_when_manifest_provided(
        self, mock_read, mock_warp, mock_gains, mock_blend,
    ):
        """With a valid band_manifest, the two-pass GPS composite runs."""
        mock_read.return_value = _sample_dsm_info()
        green_dir = self.cal_root / "green"
        green_dir.mkdir(parents=True)
        (green_dir / "img_001_reflectance.tif").write_text("fake")

        mock_warp.return_value = [
            {"path": Path("/tmp/w.tif"), "stem": "img_001", "mean": 0.3,
             "lat": 41.1, "lon": 23.4},
        ]
        mock_gains.return_value = {"img_001": 1.0}

        band_manifest = {
            "bands": {"green": {"images": [{"file_path": "/orig/img_001.tif"}]}}
        }

        result = orthorectify_bands(
            str(self.cal_root), "/tmp/sfm", str(self.dsm), str(self.output_dir),
            band_manifest=band_manifest,
        )

        self.assertIn("green", result)
        mock_warp.assert_called_once()
        mock_gains.assert_called_once()
        mock_blend.assert_called_once()

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._median_composite_band")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._read_dsm_metadata")
    def test_raises_on_bad_dsm(self, mock_read, mock_comp):
        mock_read.return_value = None
        with self.assertRaises(RuntimeError):
            orthorectify_bands(str(self.cal_root), "/tmp/sfm", str(self.dsm), str(self.output_dir))

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._read_dsm_metadata")
    def test_raises_when_manifest_band_absent(self, mock_read):
        """Manifest provided but a calibrated band missing from it → RuntimeError.

        GPS-guided warping needs original image paths for every band; a silent
        median fallback would reintroduce the misalignment artifact, so the code
        fails loudly instead.
        """
        mock_read.return_value = _sample_dsm_info()
        red_dir = self.cal_root / "red"
        red_dir.mkdir(parents=True)
        (red_dir / "img_reflectance.tif").write_text("fake")

        # Manifest has "green" but not "red"
        band_manifest = {"bands": {"green": {"images": [{"file_path": "/orig/g.tif"}]}}}

        with self.assertRaises(RuntimeError):
            orthorectify_bands(
                str(self.cal_root), "/tmp/sfm", str(self.dsm), str(self.output_dir),
                band_manifest=band_manifest,
            )

    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._blend_band_with_gains")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._compute_shared_strip_gains")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._warp_band_images")
    @patch("services.orthomosaic_generation.app.core.algorithms.ms_orthorectification._read_dsm_metadata")
    def test_processes_multiple_bands(self, mock_read, mock_warp, mock_gains, mock_blend):
        mock_read.return_value = _sample_dsm_info()
        manifest_bands = {}
        for band in ("green", "red", "nir"):
            d = self.cal_root / band
            d.mkdir(parents=True)
            (d / "img_001_reflectance.tif").write_text("fake")
            manifest_bands[band] = {"images": [{"file_path": "/orig/img_001.tif"}]}

        mock_warp.return_value = [
            {"path": Path("/tmp/w.tif"), "stem": "img_001", "mean": 0.3,
             "lat": 41.1, "lon": 23.4},
        ]
        mock_gains.return_value = {"img_001": 1.0}

        result = orthorectify_bands(
            str(self.cal_root), "/tmp/sfm", str(self.dsm), str(self.output_dir),
            band_manifest={"bands": manifest_bands},
        )
        self.assertSetEqual(set(result.keys()), {"green", "red", "nir"})
        self.assertEqual(mock_warp.call_count, 3)
        # Gains computed exactly once across all bands (the cross-band fix).
        mock_gains.assert_called_once()
        self.assertEqual(mock_blend.call_count, 3)


# ---------------------------------------------------------------------------
# SPECTRAL_BANDS constant
# ---------------------------------------------------------------------------

class TestSpectralBandsConstant(unittest.TestCase):

    def test_expected_bands(self):
        self.assertEqual(SPECTRAL_BANDS, ["blue", "green", "red", "red_edge", "nir"])


if __name__ == "__main__":
    unittest.main()

