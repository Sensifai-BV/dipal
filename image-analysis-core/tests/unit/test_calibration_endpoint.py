"""Unit tests for calibration_endpoint helper functions."""
import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from shared.band_detection.models import (
    BandGroup,
    BandType,
    DatasetBandManifest,
    DroneManufacturer,
    ImageBandInfo,
)


CAL_MOD = "services.radiometric_calibration.app.api.v1.endpoints.calibration_endpoint"


def _patch_settings():
    """Patch module-level settings to avoid env file reads."""
    return patch.multiple(
        CAL_MOD,
        callback_settings=MagicMock(callback_url="http://gw/cb", timeout_seconds=5),
        s3_settings=MagicMock(),
        temp_settings=MagicMock(base_path="/tmp/test_cal"),
    )


def _import_cal_module():
    """Import calibration_endpoint after patching settings."""
    module = sys.modules.get(CAL_MOD)
    if module:
        return module
    if "cv2" not in sys.modules:
        sys.modules["cv2"] = MagicMock()
    with _patch_settings():
        import services.radiometric_calibration.app.api.v1.endpoints.calibration_endpoint as mod
    return mod


class TestSendCallback(unittest.IsolatedAsyncioTestCase):
    """Tests for send_callback."""

    async def test_success(self):
        mod = _import_cal_module()
        with _patch_settings():
            with patch(f"{CAL_MOD}.httpx.AsyncClient") as mock_cls:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                await mod.send_callback("j1_calibration", "completed", result={"status": "ok"})

    async def test_non_200_response(self):
        mod = _import_cal_module()
        with _patch_settings():
            with patch(f"{CAL_MOD}.httpx.AsyncClient") as mock_cls:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.text = "err"
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                await mod.send_callback("j1", "failed", error="boom")

    async def test_network_error(self):
        mod = _import_cal_module()
        with _patch_settings():
            with patch(f"{CAL_MOD}.httpx.AsyncClient") as mock_cls:
                mock_cls.side_effect = Exception("conn refused")
                await mod.send_callback("j1", "failed", error="boom")


class TestDownloadImages(unittest.IsolatedAsyncioTestCase):
    """Tests for _download_images."""

    async def test_images_already_present(self):
        mod = _import_cal_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            img_dir = base / "datasets" / "ds1" / "images"
            img_dir.mkdir(parents=True)
            (img_dir / "img.tif").write_text("fake")

            result = await mod._download_images("ds1", "http://url", base)
            self.assertEqual(result, img_dir)

    async def test_presigned_url_list(self):
        mod = _import_cal_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with patch(f"{CAL_MOD}.StorageDriverFactory") as mock_factory:
                mock_driver = MagicMock()
                mock_factory.create.return_value = mock_driver
                with patch(f"{CAL_MOD}.Dataset") as mock_dataset_cls:
                    mock_ds = MagicMock()
                    mock_dataset_cls.return_value = mock_ds

                    urls = [{"url": "http://s3/img1.tif"}, {"url": "http://s3/img2.tif"}]
                    result = await mod._download_images("ds1", urls, base)

                    mock_factory.create.assert_called_once_with(
                        "presigned_url",
                        {"project_urls": {"ds1": {"images": urls}}},
                    )
                    mock_driver.connect.assert_called_once()
                    mock_driver.disconnect.assert_called_once()

    async def test_s3_uri(self):
        mod = _import_cal_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with patch(f"{CAL_MOD}.StorageDriverFactory") as mock_factory:
                mock_driver = MagicMock()
                mock_factory.create.return_value = mock_driver
                with patch(f"{CAL_MOD}.Dataset") as mock_dataset_cls:
                    mock_ds = MagicMock()
                    mock_dataset_cls.return_value = mock_ds

                    result = await mod._download_images("ds1", "s3://mybucket/prefix/data", base)

                    mock_factory.create.assert_called_once_with(
                        "s3",
                        {"bucket_name": "mybucket", "prefix": "prefix"},
                    )

    async def test_single_presigned_url(self):
        mod = _import_cal_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            with patch(f"{CAL_MOD}.StorageDriverFactory") as mock_factory:
                mock_driver = MagicMock()
                mock_factory.create.return_value = mock_driver
                with patch(f"{CAL_MOD}.Dataset") as mock_dataset_cls:
                    mock_ds = MagicMock()
                    mock_dataset_cls.return_value = mock_ds

                    result = await mod._download_images("ds1", "https://example.com/archive.zip", base)

                    mock_factory.create.assert_called_once_with(
                        "presigned_url",
                        {"project_urls": {"ds1": {"download_url": "https://example.com/archive.zip"}}},
                    )


class TestCalibrateMultispectral(unittest.TestCase):
    """Tests for _calibrate_multispectral_images."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.dataset_dir = self.tmpdir / "dataset"
        self.output_dir = self.tmpdir / "output"
        self.dataset_dir.mkdir()
        self.output_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_manifest(self, bands=None):
        if bands is None:
            bands = {}
        return DatasetBandManifest(
            dataset_id="ds1",
            total_images=10,
            is_multispectral=True,
            manufacturer=DroneManufacturer.DJI,
            bands=bands,
        )

    def test_no_bands(self):
        mod = _import_cal_module()
        manifest = self._make_manifest()
        processor = MagicMock()
        result = mod._calibrate_multispectral_images(
            manifest, self.dataset_dir, self.output_dir, processor,
        )
        self.assertEqual(result["total_processed"], 0)

    def test_processes_green_band(self):
        mod = _import_cal_module()
        img_path = self.dataset_dir / "green" / "img1.tif"
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"\x00" * 100)

        bands = {
            "green": BandGroup(
                band_type=BandType.GREEN,
                images=[ImageBandInfo(
                    file_path=str(img_path),
                    file_name="img1.tif",
                    band_type=BandType.GREEN,
                )],
            ),
        }
        manifest = self._make_manifest(bands)
        processor = MagicMock()
        processor.calculate_reflectance.return_value = np.zeros((100, 100), dtype=np.float32)

        with patch(f"{CAL_MOD}._save_reflectance_image"):
            result = mod._calibrate_multispectral_images(
                manifest, self.dataset_dir, self.output_dir, processor,
            )

        self.assertEqual(result["calibrated_counts"]["green"], 1)
        self.assertEqual(result["reflectance_counts"]["green"], 1)
        self.assertEqual(result["total_processed"], 1)
        processor.load_image.assert_called_once()
        processor.process_all_steps.assert_called_once()

    def test_handles_processing_error(self):
        mod = _import_cal_module()
        img_path = self.dataset_dir / "nir" / "img1.tif"
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"\x00" * 100)

        bands = {
            "nir": BandGroup(
                band_type=BandType.NIR,
                images=[ImageBandInfo(
                    file_path=str(img_path),
                    file_name="img1.tif",
                    band_type=BandType.NIR,
                )],
            ),
        }
        manifest = self._make_manifest(bands)
        processor = MagicMock()
        processor.load_image.side_effect = RuntimeError("corrupt image")

        result = mod._calibrate_multispectral_images(
            manifest, self.dataset_dir, self.output_dir, processor,
        )

        self.assertEqual(result["total_failed"], 1)
        self.assertIn("img1.tif", result["failed_images"][0])

    def test_copies_rgb_passthrough(self):
        mod = _import_cal_module()
        img_path = self.dataset_dir / "rgb" / "img_rgb.jpg"
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"\x00" * 100)

        bands = {
            "rgb": BandGroup(
                band_type=BandType.RGB,
                images=[ImageBandInfo(
                    file_path=str(img_path),
                    file_name="img_rgb.jpg",
                    band_type=BandType.RGB,
                )],
            ),
        }
        manifest = self._make_manifest(bands)
        processor = MagicMock()

        result = mod._calibrate_multispectral_images(
            manifest, self.dataset_dir, self.output_dir, processor,
        )

        self.assertEqual(result["calibrated_counts"]["rgb"], 1)
        rgb_out = self.output_dir / "calibrated_images" / "rgb" / "img_rgb.jpg"
        self.assertTrue(rgb_out.exists())


class TestCalibrateRGBOnly(unittest.TestCase):
    """Tests for _calibrate_rgb_only."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.dataset_dir = self.tmpdir / "dataset"
        self.output_dir = self.tmpdir / "output"
        self.dataset_dir.mkdir()
        self.output_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_copies_rgb_images(self):
        mod = _import_cal_module()
        img_path = self.dataset_dir / "rgb" / "img1.jpg"
        img_path.parent.mkdir(parents=True)
        img_path.write_bytes(b"\xff" * 50)

        bands = {
            "rgb": BandGroup(
                band_type=BandType.RGB,
                images=[ImageBandInfo(
                    file_path=str(img_path),
                    file_name="img1.jpg",
                    band_type=BandType.RGB,
                )],
            ),
        }
        manifest = DatasetBandManifest(
            dataset_id="ds1",
            total_images=1,
            is_multispectral=False,
            manufacturer=DroneManufacturer.DJI,
            bands=bands,
        )
        result = mod._calibrate_rgb_only(manifest, self.dataset_dir, self.output_dir)
        self.assertEqual(result["total_processed"], 1)
        self.assertEqual(result["calibrated_counts"]["rgb"], 1)

    def test_no_rgb_raises(self):
        mod = _import_cal_module()
        manifest = DatasetBandManifest(
            dataset_id="ds1",
            total_images=0,
            is_multispectral=False,
            manufacturer=DroneManufacturer.DJI,
            bands={},
        )
        with self.assertRaises(ValueError):
            mod._calibrate_rgb_only(manifest, self.dataset_dir, self.output_dir)


class TestSaveImages(unittest.TestCase):
    """Tests for _save_reflectance_image, _extract_gps_for_reflectance, and _save_image."""

    # ------------------------------------------------------------------
    # _save_reflectance_image — fallback (no GPS / no source path)
    # ------------------------------------------------------------------

    def test_save_reflectance_image_no_source_falls_back_to_cv2(self):
        """Without source_image_path, cv2.imwrite is used."""
        mod = _import_cal_module()
        arr = np.random.rand(10, 10).astype(np.float32)
        with patch(f"{CAL_MOD}.cv2.imwrite") as mock_write:
            mod._save_reflectance_image(arr, Path("/tmp/out.tif"))
            mock_write.assert_called_once()
            saved_arr = mock_write.call_args[0][1]
            self.assertEqual(saved_arr.dtype, np.float32)

    def test_save_reflectance_image_no_gdal_falls_back_to_cv2(self):
        """When _gdal is None (not installed), cv2.imwrite is used even with GPS."""
        mod = _import_cal_module()
        arr = np.ones((10, 10), dtype=np.float32)
        with patch(f"{CAL_MOD}._gdal", None), \
             patch(f"{CAL_MOD}.cv2.imwrite") as mock_write:
            mod._save_reflectance_image(arr, Path("/tmp/out.tif"), source_image_path=Path("/src/img.tif"))
            mock_write.assert_called_once()

    def test_save_reflectance_image_no_gps_falls_back_to_cv2(self):
        """When GPS extraction returns None, cv2.imwrite is used."""
        mod = _import_cal_module()
        arr = np.ones((8, 8), dtype=np.float32)
        with patch(f"{CAL_MOD}._extract_gps_for_reflectance", return_value=None), \
             patch(f"{CAL_MOD}.cv2.imwrite") as mock_write:
            mod._save_reflectance_image(arr, Path("/tmp/out.tif"), source_image_path=Path("/src/img.tif"))
            mock_write.assert_called_once()

    def test_save_reflectance_image_with_gps_uses_gdal(self):
        """With valid GPS and GDAL, a georeferenced GeoTIFF is written via GDAL."""
        mod = _import_cal_module()
        arr = np.ones((16, 16), dtype=np.float32)

        mock_gdal = MagicMock()
        mock_osr = MagicMock()
        mock_ds = MagicMock()
        mock_band = MagicMock()
        mock_ds.GetRasterBand.return_value = mock_band
        mock_gdal.GetDriverByName.return_value.Create.return_value = mock_ds
        mock_gdal.GDT_Float32 = 6

        with patch(f"{CAL_MOD}._gdal", mock_gdal), \
             patch(f"{CAL_MOD}._osr", mock_osr), \
             patch(f"{CAL_MOD}._extract_gps_for_reflectance", return_value=(51.5, 7.0, 80.0)), \
             patch(f"{CAL_MOD}.cv2.imwrite") as mock_cv2:
            mod._save_reflectance_image(arr, Path("/tmp/geo.tif"), source_image_path=Path("/src/img.tif"))

        mock_cv2.assert_not_called()
        mock_gdal.GetDriverByName.assert_called_with("GTiff")
        mock_ds.SetGeoTransform.assert_called_once()
        mock_ds.SetProjection.assert_called_once()
        mock_band.WriteArray.assert_called_once()
        mock_ds.FlushCache.assert_called_once()

    def test_save_reflectance_image_geotransform_matches_gps(self):
        """The geotransform upper-left corner corresponds to the GPS position."""
        import math
        mod = _import_cal_module()
        arr = np.ones((100, 200), dtype=np.float32)
        lat, lon, alt = 51.5, 7.0, 100.0

        captured_gt = {}

        mock_gdal = MagicMock()
        mock_osr = MagicMock()
        mock_ds = MagicMock()
        mock_ds.GetRasterBand.return_value = MagicMock()
        mock_gdal.GetDriverByName.return_value.Create.return_value = mock_ds
        mock_gdal.GDT_Float32 = 6
        mock_ds.SetGeoTransform.side_effect = lambda gt: captured_gt.update({"gt": gt})

        with patch(f"{CAL_MOD}._gdal", mock_gdal), \
             patch(f"{CAL_MOD}._osr", mock_osr), \
             patch(f"{CAL_MOD}._extract_gps_for_reflectance", return_value=(lat, lon, alt)):
            mod._save_reflectance_image(arr, Path("/tmp/gt.tif"), source_image_path=Path("/src/img.tif"))

        gt = captured_gt["gt"]
        # upper-left lon should be west of centre
        self.assertLess(gt[0], lon)
        # upper-left lat should be north of centre
        self.assertGreater(gt[3], lat)
        # pixel size in x should be positive
        self.assertGreater(gt[1], 0)
        # pixel size in y should be negative (north-up)
        self.assertLess(gt[5], 0)

    # ------------------------------------------------------------------
    # _extract_gps_for_reflectance
    # ------------------------------------------------------------------

    def test_extract_gps_returns_none_when_pil_unavailable(self):
        mod = _import_cal_module()
        with patch(f"{CAL_MOD}._PILImage", None):
            result = mod._extract_gps_for_reflectance(Path("/tmp/img.tif"))
        self.assertIsNone(result)

    def test_extract_gps_returns_none_on_missing_gps_ifd(self):
        mod = _import_cal_module()
        mock_img = MagicMock()
        mock_exif = MagicMock()
        mock_exif.get_ifd.return_value = {}
        mock_img.getexif.return_value = mock_exif

        mock_pil = MagicMock()
        mock_pil.open.return_value.__enter__.return_value = mock_img

        with patch(f"{CAL_MOD}._PILImage", mock_pil):
            result = mod._extract_gps_for_reflectance(Path("/tmp/img.tif"))
        self.assertIsNone(result)

    def test_extract_gps_returns_coordinates(self):
        mod = _import_cal_module()
        mock_img = MagicMock()
        mock_exif = MagicMock()
        mock_exif.get_ifd.return_value = {
            "GPSLatitudeRef": "N",
            "GPSLatitude": (51, 30, 0),
            "GPSLongitudeRef": "E",
            "GPSLongitude": (7, 0, 0),
            "GPSAltitudeRef": 0,
            "GPSAltitude": 120.0,
        }
        mock_img.getexif.return_value = mock_exif

        mock_pil = MagicMock()
        mock_pil.open.return_value.__enter__.return_value = mock_img

        with patch(f"{CAL_MOD}._PILImage", mock_pil):
            result = mod._extract_gps_for_reflectance(Path("/tmp/img.tif"))

        self.assertIsNotNone(result)
        lat, lon, alt = result
        self.assertAlmostEqual(lat, 51.5, places=3)
        self.assertAlmostEqual(lon, 7.0, places=3)
        self.assertAlmostEqual(alt, 120.0)

    def test_save_image_float64(self):
        mod = _import_cal_module()
        arr = np.array([[0.5, 1.0], [0.0, 0.25]], dtype=np.float64)
        with patch(f"{CAL_MOD}.cv2.imwrite") as mock_write:
            mod._save_image(arr, Path("/tmp/out.tif"))
            saved = mock_write.call_args[0][1]
            self.assertEqual(saved.dtype, np.uint16)
            self.assertEqual(saved[0, 1], 65535)

    def test_save_image_zeros(self):
        mod = _import_cal_module()
        arr = np.zeros((5, 5), dtype=np.float32)
        with patch(f"{CAL_MOD}.cv2.imwrite") as mock_write:
            mod._save_image(arr, Path("/tmp/out.tif"))
            saved = mock_write.call_args[0][1]
            self.assertEqual(saved.dtype, np.uint16)
            self.assertTrue(np.all(saved == 0))

    def test_save_image_uint16_passthrough(self):
        mod = _import_cal_module()
        arr = np.array([[100, 200]], dtype=np.uint16)
        with patch(f"{CAL_MOD}.cv2.imwrite") as mock_write:
            mod._save_image(arr, Path("/tmp/out.tif"))
            saved = mock_write.call_args[0][1]
            self.assertEqual(saved.dtype, np.uint16)


class TestHasExistingResults(unittest.TestCase):
    """Tests for _has_existing_results."""

    def test_no_directory(self):
        mod = _import_cal_module()
        self.assertFalse(mod._has_existing_results(Path("/tmp/nonexistent_xyz_999")))

    def test_empty_directory(self):
        mod = _import_cal_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertFalse(mod._has_existing_results(Path(tmpdir)))

    def test_with_files(self):
        mod = _import_cal_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "result.tif").write_text("data")
            self.assertTrue(mod._has_existing_results(Path(tmpdir)))


class TestSendCachedResult(unittest.IsolatedAsyncioTestCase):
    """Tests for _send_cached_result."""

    async def test_returns_result_with_skip_flag(self):
        mod = _import_cal_module()
        with _patch_settings():
            with patch(f"{CAL_MOD}.send_callback", new_callable=AsyncMock) as mock_cb:
                result = await mod._send_cached_result(
                    "j1", "ds1", Path("/data/ds1"), Path("/data/jobs/j1"),
                )
                self.assertTrue(result["skipped_processing"])
                self.assertEqual(result["status"], "completed")
                mock_cb.assert_called_once_with("j1", "completed", result=result)


class TestCreateProcessor(unittest.TestCase):
    """Tests for _create_processor."""

    def test_explicit_drone_type(self):
        mod = _import_cal_module()
        manifest = MagicMock()
        with patch(f"{CAL_MOD}.DroneImageProcessorFactory") as mock_fac:
            mock_fac.create.return_value = MagicMock()
            result = mod._create_processor(manifest, {"drone_type": "dji_mavic_3_m"})
            mock_fac.create.assert_called_once()

    def test_from_model_name(self):
        mod = _import_cal_module()
        manifest = MagicMock()
        manifest.drone_model = "M3M"
        with patch(f"{CAL_MOD}.DroneImageProcessorFactory") as mock_fac:
            mock_fac.create_from_model_name.return_value = MagicMock()
            result = mod._create_processor(manifest, {})
            mock_fac.create_from_model_name.assert_called_once_with("M3M")

    def test_fallback_to_manufacturer(self):
        mod = _import_cal_module()
        manifest = MagicMock()
        manifest.drone_model = "UNKNOWN_XYZ"
        manifest.manufacturer = DroneManufacturer.DJI
        with patch(f"{CAL_MOD}.DroneImageProcessorFactory") as mock_fac:
            mock_fac.create_from_model_name.side_effect = ValueError("unknown")
            mock_fac.create_from_manufacturer.return_value = MagicMock()
            result = mod._create_processor(manifest, {})
            mock_fac.create_from_manufacturer.assert_called_once()

    def test_no_model_uses_manufacturer(self):
        mod = _import_cal_module()
        manifest = MagicMock()
        manifest.drone_model = None
        manifest.manufacturer = DroneManufacturer.MICASENSE
        with patch(f"{CAL_MOD}.DroneImageProcessorFactory") as mock_fac:
            mock_fac.create_from_manufacturer.return_value = MagicMock()
            result = mod._create_processor(manifest, {})
            mock_fac.create_from_manufacturer.assert_called_once()


class TestRunCalibrationTask(unittest.IsolatedAsyncioTestCase):
    """Tests for run_calibration_task."""

    async def test_cached_result_path(self):
        mod = _import_cal_module()
        with _patch_settings():
            with patch(f"{CAL_MOD}._has_existing_results", return_value=True):
                with patch(f"{CAL_MOD}._send_cached_result", new_callable=AsyncMock) as mock_cached:
                    mock_cached.return_value = {"status": "completed", "skipped_processing": True}
                    result = await mod.run_calibration_task("j1", "ds1", "http://url", {})
                    self.assertTrue(result["skipped_processing"])

    async def test_full_pipeline_rgb_only(self):
        mod = _import_cal_module()
        mock_manifest = MagicMock()
        mock_manifest.is_multispectral = False
        mock_manifest.total_images = 5
        mock_manifest.manufacturer = MagicMock(value="dji")
        mock_manifest.model_dump.return_value = {}

        with _patch_settings():
            with patch(f"{CAL_MOD}._has_existing_results", return_value=False):
                with patch(f"{CAL_MOD}._load_or_scan_images", new_callable=AsyncMock, return_value=mock_manifest):
                    with patch(f"{CAL_MOD}.asyncio.to_thread") as mock_thread:
                        mock_thread.return_value = {
                            "calibrated_dir": "/out/cal", "calibrated_counts": {"rgb": 5},
                            "total_processed": 5, "total_failed": 0, "failed_images": [],
                        }
                        with patch(f"{CAL_MOD}.send_callback", new_callable=AsyncMock):
                            result = await mod.run_calibration_task("j1", "ds1", "http://url", {})
                            self.assertEqual(result["status"], "completed")
                            self.assertEqual(result["total_processed"], 5)

    async def test_pipeline_error_sends_failure_callback(self):
        mod = _import_cal_module()
        with _patch_settings():
            with patch(f"{CAL_MOD}._has_existing_results", return_value=False):
                with patch(f"{CAL_MOD}._load_or_scan_images", new_callable=AsyncMock, side_effect=RuntimeError("download fail")):
                    with patch(f"{CAL_MOD}.send_callback", new_callable=AsyncMock) as mock_cb:
                        with self.assertRaises(RuntimeError):
                            await mod.run_calibration_task("j1", "ds1", "http://url", {})
                        mock_cb.assert_called_once_with("j1", "failed", error="RuntimeError: download fail")

    async def test_full_pipeline_multispectral(self):
        mod = _import_cal_module()
        mock_manifest = MagicMock()
        mock_manifest.is_multispectral = True
        mock_manifest.total_images = 10
        mock_manifest.manufacturer = MagicMock(value="dji")
        mock_manifest.model_dump.return_value = {}

        with _patch_settings():
            with patch(f"{CAL_MOD}._has_existing_results", return_value=False):
                with patch(f"{CAL_MOD}._load_or_scan_images", new_callable=AsyncMock, return_value=mock_manifest):
                    with patch(f"{CAL_MOD}._create_processor") as mock_proc:
                        mock_proc.return_value = MagicMock()
                        with patch(f"{CAL_MOD}.asyncio.to_thread") as mock_thread:
                            mock_thread.return_value = {
                                "calibrated_dir": "/out/cal", "calibrated_counts": {"green": 2},
                                "reflectance_counts": {"green": 2}, "has_reflectance": True,
                                "total_processed": 2, "total_failed": 0, "failed_images": [],
                            }
                            with patch(f"{CAL_MOD}.send_callback", new_callable=AsyncMock):
                                result = await mod.run_calibration_task("j1", "ds1", "http://url", {})
                                self.assertTrue(result["is_multispectral"])
                                self.assertTrue(result["has_reflectance"])


if __name__ == "__main__":
    unittest.main()
